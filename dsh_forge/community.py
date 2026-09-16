"""The community install lane: unsigned catalog records, same sandbox.

Lane A installs a package a curator signed. That covers almost nothing: the
published catalog is GitHub repositories, and a record only becomes installable
once someone has produced a signed recipe for it, so in practice nothing in the
browser can be run.

This lane closes that gap without weakening Lane A. It does not relax the
acquisition, inspection, or sandbox boundary, and it does not add a second
install path through them. Instead it *builds a manifest* for a catalog record
pinned to the exact commit the crawler recorded, signs it with a key generated
on this machine, and hands it to the existing signed pipeline. Every byte still
goes through the same host allowlist, size and time caps, archive inspection,
and networkless Apptainer smoke test, and a sandbox failure still fails closed.

What changes is only *who vouched for the artifact*: the person running Forge,
explicitly, instead of a curator. Receipts record the lane so that distinction
is never lost, and nothing here implies the code was reviewed.

The digest is learned on first acquisition rather than known in advance. GitHub
does not publish one for a source archive, so the first install pins whatever it
received and every later install of that commit must match it. That detects a
changed artifact after the fact; it cannot vouch for the first download.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
from pathlib import Path
import stat
import subprocess
from typing import Any, Mapping

from .acquisition import (
    AcquisitionError,
    SOURCE_HOSTS,
    _open_https,
)
from .packages import PackageError, compose, create_trust_root, sign

LANE = "community-unverified"
SPEC_SCHEMA = "dsh-forge.package-spec/v1"
PIN_SCHEMA = "dsh-forge.community-pin/v1"
DEFAULT_IDENTITY_ROOT = Path("~/.local/state/dsh-forge/community")
#: Source archives are far smaller than a built package; refuse anything larger
#: rather than stream an unbounded download to learn a digest.
MAX_PROBE_BYTES = 128 * 1024 * 1024
PROBE_TIMEOUT_SECONDS = 120.0
_COMMIT_LENGTH = 40


class CommunityError(ValueError):
    """A community-lane install failed closed."""

    def __init__(self, message: str, code: str = "community_install_failed"):
        super().__init__(message)
        self.code = code


def _require(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise CommunityError(message, code)


def archive_url(repository_url: str, commit: str) -> str:
    """The codeload URL for one immutable commit."""

    _require(
        isinstance(commit, str) and len(commit) == _COMMIT_LENGTH and all(
            char in "0123456789abcdef" for char in commit
        ),
        "A community install requires a full lowercase commit SHA",
        "commit_not_pinned",
    )
    _require(
        isinstance(repository_url, str) and repository_url.startswith("https://github.com/"),
        "A community install requires a github.com repository URL",
        "source_not_allowed",
    )
    path = repository_url[len("https://github.com/"):].strip("/")
    parts = path.split("/")
    _require(len(parts) == 2 and all(parts), "Repository URL must be owner/name", "source_not_allowed")
    owner, name = parts
    return f"https://codeload.github.com/{owner}/{name}/tar.gz/{commit}"


def probe_archive(url: str, *, max_bytes: int = MAX_PROBE_BYTES, timeout: float = PROBE_TIMEOUT_SECONDS,
                  opener: Any = None) -> dict[str, Any]:
    """Learn a source archive's digest, under the same limits as an acquisition.

    ``opener`` exists only as a test seam; production callers use the hardened
    credential-free HTTPS path shared with Lane A.
    """

    allowed = SOURCE_HOSTS["github_archive"]
    open_https = opener or _open_https
    response, final_url, redirects = open_https({"url": url}, allowed, timeout)
    digest = hashlib.sha256()
    total = 0
    try:
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise CommunityError("Source archive exceeds the probe byte limit", "artifact_too_large")
            digest.update(chunk)
    except CommunityError:
        raise
    except OSError as error:
        raise CommunityError(f"Source archive probe failed: {error}", "download_failed") from error
    finally:
        response.close()
    _require(total > 0, "Source archive was empty", "response_rejected")
    return {
        "schema": PIN_SCHEMA,
        "integrity": "sha256-" + digest.hexdigest(),
        "bytes": total,
        "final_url": final_url,
        "redirects": list(redirects),
        "pinned_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def _identifier(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "-" for char in str(value).lower())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:64] or "community-artifact"


def community_spec(record: Mapping[str, Any], pin: Mapping[str, Any]) -> dict[str, Any]:
    """Build a single-plugin package spec for one catalog record."""

    repository_url = str(record.get("repository_url") or "")
    commit = str(record.get("head_sha") or "")
    url = archive_url(repository_url, commit)
    name = _identifier(record.get("name") or record.get("full_name") or "")
    full_name = str(record.get("full_name") or name)
    # The archive has no release version of its own, so the commit identifies it.
    version = "0.0.0+" + commit[:12]
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    license_value = record.get("license")
    spdx = license_value.get("spdx") if isinstance(license_value, Mapping) else None
    return {
        "schema": SPEC_SCHEMA,
        "package": {
            "id": "community-" + name,
            "name": full_name[:128],
            "version": version,
            "description": (str(record.get("description") or "").strip())[:512],
            "license": spdx if isinstance(spdx, str) and spdx and spdx not in {"NOASSERTION", "UNKNOWN"} else "NOASSERTION",
            "created_at": now,
        },
        "compatibility": {"dsh": "*", "node": "*", "platforms": ["linux"]},
        "plugins": [{
            "id": name,
            "source": {
                "kind": "github_archive",
                "name": full_name,
                "version": version,
                "url": url,
                "integrity": str(pin["integrity"]),
            },
            "repository": {"url": repository_url, "commit": commit},
            # The lane grants nothing beyond the sandbox default. A community
            # record does not get to ask for capabilities on its own say-so.
            "permissions": [],
            "requires": [],
            "conflicts_with": [],
        }],
        "load_order": [name],
        "provenance": {
            "created_by": f"DSH Forge {LANE}",
            "source": "user_composed",
            "evidence": "metadata_only_unexecuted",
        },
    }


def local_identity(root: str | Path = DEFAULT_IDENTITY_ROOT, *, runner: Any = subprocess.run) -> dict[str, Any]:
    """Generate or load this machine's community signing key and trust root.

    The key never leaves this machine and vouches for nothing beyond "the person
    at this machine asked for this". It exists so the community lane can reuse
    the signed pipeline instead of opening a second, unverified way in.
    """

    base = Path(root).expanduser()
    try:
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(base, 0o700)
    except OSError as error:
        raise CommunityError(f"Could not prepare {base}: {error}", "local_io_error") from error
    private = base / "community-signing.key"
    public = base / "community-signing.pub"
    if not private.exists() or not public.exists():
        try:
            runner(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(private)],
                   check=True, capture_output=True)
            os.chmod(private, 0o600)
            runner(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                   check=True, capture_output=True)
        except (subprocess.CalledProcessError, OSError) as error:
            raise CommunityError(f"Could not create a local signing key: {error}", "key_generation_failed") from error
    try:
        mode = stat.S_IMODE(private.stat().st_mode)
    except OSError as error:
        raise CommunityError(f"Could not stat the local signing key: {error}", "local_io_error") from error
    if os.name == "posix" and mode & 0o077:
        raise CommunityError(
            "The local signing key must not be readable by group or other",
            "insecure_key_permissions",
        )
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=365)).replace(microsecond=0)
    try:
        trust_root = create_trust_root(public, "dsh-forge-community-local", expires.isoformat().replace("+00:00", "Z"))
    except PackageError as error:
        raise CommunityError(f"Could not build the local trust root: {error}", "trust_root_invalid") from error
    return {"private_key": private, "public_key": public, "trust_root": trust_root, "lane": LANE}


def prepare_install(
    record: Mapping[str, Any],
    *,
    identity_root: str | Path = DEFAULT_IDENTITY_ROOT,
    known_pin: Mapping[str, Any] | None = None,
    probe: Any = None,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    """Produce a locally signed envelope and trust root for a catalog record.

    ``known_pin`` is a digest recorded by an earlier install of this exact
    commit. When one exists the freshly probed archive must match it, so a
    changed artifact at a pinned commit fails closed instead of installing.
    """

    _require(isinstance(record, Mapping), "A catalog record is required", "invalid_record")
    commit = str(record.get("head_sha") or "")
    url = archive_url(str(record.get("repository_url") or ""), commit)
    pin = (probe or probe_archive)(url)
    if known_pin:
        _require(
            str(known_pin.get("integrity")) == str(pin["integrity"]),
            "The source archive for this commit no longer matches the digest recorded earlier",
            "integrity_mismatch",
        )
    identity = local_identity(identity_root, runner=runner)
    try:
        manifest = compose(community_spec(record, pin))
        envelope = sign(manifest, identity["private_key"])
    except PackageError as error:
        raise CommunityError(f"Could not build a community package: {error}", "manifest_invalid") from error
    return {
        "lane": LANE,
        "envelope": envelope,
        "trust_root": identity["trust_root"],
        "manifest": manifest,
        "pin": pin,
        "claims": {
            "curator_reviewed": False,
            "security_verified": False,
            "signed_by": "local-operator",
            "commit_pinned": True,
            "sandboxed": True,
        },
    }
