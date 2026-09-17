"""Prepare a catalog fork as a launchable Harness tree.

A plugin installs *into* a harness. A fork **is** a harness — it is a fork of
deepseek-harness itself — so running one means acquiring that version's source at
a pinned commit and launching it as its own tree, not installing anything.

The acquisition half keeps the guarantees the plugin lane has: credential-free
HTTPS to an allowlisted host, a commit-pinned URL, bounded bytes and time, a
recorded digest, and an extraction that cannot escape its directory or carry a
link out of it.

The one guarantee it cannot keep is scripts. A launchable tree needs a CLI
entrypoint, and for most forks that file is build output their source archive
does not ship. Producing it means running the fork's own install and build
scripts, which the plugin lane deliberately refuses to do. So this module
separates the two cases and never blurs them: a fork that already ships an
entrypoint launches with no scripts at all, and a fork that needs a build is
reported as needing one so the decision stays with the operator rather than
being taken quietly here.
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from typing import Any, Mapping

from .acquisition import SOURCE_HOSTS, _open_https
from .community import CommunityError, archive_url

FORK_TREE_SCHEMA = "dsh-forge.fork-tree/v1"
#: A harness source tree is far smaller than this; refuse anything larger rather
#: than expand an unbounded archive onto the disk.
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_ENTRIES = 100_000
MAX_PATH_BYTES = 4096
DOWNLOAD_TIMEOUT_SECONDS = 300.0

#: Entrypoints that make a tree launchable without a build. Mirrors the
#: signatures `Launcher._source_candidate` accepts; a built entrypoint means no
#: scripts have to run.
PREBUILT_ENTRYPOINTS = (
    "apps/cli/lib/bin.js",
    "lib/bin.js",
    "packages/cli/bin/dsh.js",
    "packages/cli/dist/bin/dsh.js",
    "bin/dsh",
    "dsh",
)
#: Source entrypoints. Present means it is a harness, but a build is needed.
SOURCE_ENTRYPOINTS = ("apps/cli/src/bin.ts", "src/bin.ts")


class ForkError(ValueError):
    """Preparing a fork tree failed closed."""

    def __init__(self, message: str, code: str = "fork_prepare_failed"):
        super().__init__(message)
        self.code = code


def _require(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise ForkError(message, code)


def _safe_member_path(raw: str) -> PurePosixPath:
    """Validate one archive member name, or refuse the archive."""

    _require(
        isinstance(raw, str) and raw and len(raw.encode("utf-8", errors="ignore")) <= MAX_PATH_BYTES,
        "Archive contains an invalid or overlong path",
        "unsafe_archive",
    )
    _require(
        "\\" not in raw and "\x00" not in raw and not any(ord(char) < 32 for char in raw),
        "Archive path contains forbidden characters",
        "unsafe_archive",
    )
    path = PurePosixPath(raw)
    _require(
        not path.is_absolute() and not any(part in {"", ".", ".."} for part in path.parts),
        f"Archive path is not confined: {raw}",
        "unsafe_archive",
    )
    return path


def download_archive(url: str, destination: Path, *, opener: Any = None,
                     timeout: float = DOWNLOAD_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Stream a source archive to disk under the same limits as Lane A."""

    open_https = opener or _open_https
    response, final_url, redirects = open_https({"url": url}, SOURCE_HOSTS["github_archive"], timeout)
    digest = hashlib.sha256()
    total = 0
    try:
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise ForkError("Source archive exceeds the download limit", "artifact_too_large")
                digest.update(chunk)
                handle.write(chunk)
    except ForkError:
        raise
    except OSError as error:
        raise ForkError(f"Source archive download failed: {error}", "download_failed") from error
    finally:
        response.close()
    _require(total > 0, "Source archive was empty", "response_rejected")
    return {"integrity": "sha256-" + digest.hexdigest(), "bytes": total,
            "final_url": final_url, "redirects": list(redirects)}


def extract_tree(archive_path: Path, destination: Path) -> dict[str, Any]:
    """Expand a codeload tarball into ``destination``, stripping its root.

    Every member is validated before anything is written. Links, devices, and
    anything that is not a regular file or directory are refused outright rather
    than skipped, so a hostile archive cannot smuggle a path out of the tree.
    """

    destination.mkdir(parents=True, exist_ok=True)
    roots: set[str] = set()
    entries = 0
    expanded = 0
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = []
            for member in archive:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ForkError("Source archive has too many entries", "unsafe_archive")
                path = _safe_member_path(member.name)
                _require(
                    member.isfile() or member.isdir(),
                    f"Archive member is not a regular file or directory: {member.name}",
                    "unsafe_archive",
                )
                _require(
                    not (member.issym() or member.islnk()),
                    f"Archive contains a link: {member.name}",
                    "unsafe_archive",
                )
                if member.isfile():
                    expanded += max(0, int(member.size))
                    if expanded > MAX_EXPANDED_BYTES:
                        raise ForkError("Source archive expands beyond the size limit", "artifact_too_large")
                roots.add(path.parts[0])
                members.append((member, path))
            _require(len(roots) == 1, "Source archive must contain exactly one root directory", "unsafe_archive")
            for member, path in members:
                relative = PurePosixPath(*path.parts[1:])
                if not relative.parts:
                    continue
                target = destination / Path(*relative.parts)
                resolved_root = destination.resolve()
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                # Belt and braces: confirm the write lands inside the tree even
                # after the filesystem has had its say about the path.
                if resolved_root not in target.parent.resolve().parents and target.parent.resolve() != resolved_root:
                    raise ForkError(f"Archive member escaped the tree: {member.name}", "unsafe_archive")
                source = archive.extractfile(member)
                if source is None:
                    raise ForkError(f"Archive member could not be read: {member.name}", "unsafe_archive")
                with source, target.open("wb") as handle:
                    shutil.copyfileobj(source, handle, length=64 * 1024)
    except ForkError:
        raise
    except (tarfile.TarError, OSError, EOFError) as error:
        raise ForkError(f"Source archive could not be expanded: {error}", "unsafe_archive") from error
    return {"entries": entries, "expanded_bytes": expanded, "root": sorted(roots)[0]}


def classify_tree(root: Path) -> dict[str, Any]:
    """Decide whether the extracted tree can launch without running scripts."""

    prebuilt = [name for name in PREBUILT_ENTRYPOINTS if (root / name).is_file()]
    sources = [name for name in SOURCE_ENTRYPOINTS if (root / name).is_file()]
    has_manifest = (root / "package.json").is_file()
    if prebuilt:
        return {
            "launchable": True, "build_required": False, "entrypoint": prebuilt[0],
            "reason": "Ships a built entrypoint, so it launches without running any scripts.",
        }
    if sources or has_manifest:
        return {
            "launchable": False, "build_required": True, "entrypoint": sources[0] if sources else "",
            "reason": (
                "Only source is published, so this fork has to be built before it can run. "
                "Building executes the fork's own install and build scripts."
            ),
        }
    return {
        "launchable": False, "build_required": False, "entrypoint": "",
        "reason": "No Harness entrypoint was found in this fork, so Forge cannot launch it.",
    }


def prepare_fork(
    record: Mapping[str, Any],
    destination: str | Path,
    *,
    known_pin: Mapping[str, Any] | None = None,
    opener: Any = None,
) -> dict[str, Any]:
    """Acquire and expand one fork at its pinned commit, then classify it.

    Nothing is executed. The result says whether the tree can be launched as-is,
    needs a build, or cannot be launched at all.
    """

    _require(isinstance(record, Mapping), "A catalog record is required", "invalid_record")
    commit = str(record.get("head_sha") or "")
    try:
        # Shared with the plugin lane, but its errors must surface as this
        # module's type so callers only have one thing to catch.
        url = archive_url(str(record.get("repository_url") or ""), commit)
    except CommunityError as error:
        raise ForkError(str(error), error.code) from error
    root = Path(destination).expanduser()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        archive_path = Path(scratch) / "source.tar.gz"
        pin = download_archive(url, archive_path, opener=opener)
        if known_pin:
            _require(
                str(known_pin.get("integrity")) == pin["integrity"],
                "The source archive for this commit no longer matches the digest recorded earlier",
                "integrity_mismatch",
            )
        layout = extract_tree(archive_path, root)
    classification = classify_tree(root)
    return {
        "schema": FORK_TREE_SCHEMA,
        "artifact_id": str(record.get("artifact_id") or ""),
        "slug": str(record.get("full_name") or ""),
        "commit": commit,
        "path": str(root),
        "pin": pin,
        "layout": layout,
        **classification,
        "claims": {
            "executed": False,
            "scripts_run": False,
            "curator_reviewed": False,
            "security_verified": False,
            "commit_pinned": True,
        },
    }
