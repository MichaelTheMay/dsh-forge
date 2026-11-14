"""Stage 2a: measure what is actually inside a repository.

Everything here is read-only arithmetic over files on disk: sizes, counts and
hashes. No file from the repository is executed, imported or evaluated, and no
file content is copied into the result, only numbers and fingerprints.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from . import INSPECTION_SCHEMA

MAX_FILES = 6000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_BYTES = 512 * 1024

SKIP_DIRECTORIES = {
    ".git", "node_modules", "dist", "build", "out", "coverage", "vendor", ".next",
    ".turbo", ".cache", "__pycache__", ".venv", "venv", "target", ".idea", ".vscode",
}
CODE_EXTENSIONS = {
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx", ".vue", ".svelte",
    ".py", ".go", ".rs", ".rb", ".java", ".kt", ".swift", ".c", ".cc", ".cpp", ".h", ".sh",
}
DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".txt"}
LIFECYCLE_SCRIPTS = ("preinstall", "install", "postinstall", "prepare")
FINGERPRINT_MIN_LINES = 20

_TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|specs|e2e)(/|$)|\.(test|spec)\.[a-z]+$", re.IGNORECASE)
_GENERATED_LINE = 400
# Patterns that deserve a human look. Counted, never interpreted as a verdict.
_RISK_PATTERNS = {
    "remote_shell": re.compile(rb"(curl|wget)[^\n|]{0,200}\|\s*(ba)?sh"),
    "encoded_eval": re.compile(rb"eval\s*\(\s*(atob|Buffer\.from)\s*\("),
    "reads_credentials": re.compile(rb"\.ssh/id_|\.aws/credentials|\.npmrc|GITHUB_TOKEN|OPENAI_API_KEY"),
    # Found by a reviewer: a plugin that exempts itself from the package manager's
    # new-release waiting period so it can update itself without that check.
    "weakens_install_checks": re.compile(rb"minimumReleaseAgeExclude|minimum-release-age-exclude"),
}


def _walk(root: Path) -> Iterable[tuple[str, Path]]:
    """Yield (relative posix path, path) for regular files, skipping bulk and links."""
    count = 0
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in SKIP_DIRECTORIES)
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                continue
            count += 1
            if count > MAX_FILES:
                return
            yield path.relative_to(root).as_posix(), path


def _read(path: Path, limit: int = MAX_FILE_BYTES) -> bytes | None:
    try:
        if path.stat().st_size > limit:
            return None
        return path.read_bytes()
    except OSError:
        return None


def _manifest(root: Path) -> dict[str, Any]:
    found = {
        "present": False, "valid": False, "declares_plugin": False, "patch_file_present": False,
        "entry_present": False, "lifecycle_scripts": [], "dependency_count": 0, "has_test_script": False,
    }
    raw = _read(root / "package.json", MAX_MANIFEST_BYTES)
    if raw is None:
        return found
    found["present"] = True
    try:
        data = json.loads(raw)
    except ValueError:
        return found
    if not isinstance(data, dict):
        return found
    found["valid"] = True
    plugin = data.get("dsh")
    found["declares_plugin"] = isinstance(plugin, dict) and bool(plugin)
    bundle = plugin.get("bundle") if isinstance(plugin, dict) else None
    patch = bundle.get("patch") if isinstance(bundle, dict) else None
    patch_path = patch if isinstance(patch, str) else "cordis.patch.yml"
    found["patch_file_present"] = _inside(root, patch_path)
    entry = data.get("main") if isinstance(data.get("main"), str) else "index.js"
    found["entry_present"] = _inside(root, entry) or _inside(root, "index.mjs") or _inside(root, "src/index.ts")
    scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
    found["lifecycle_scripts"] = [name for name in LIFECYCLE_SCRIPTS if isinstance(scripts.get(name), str)]
    test_script = scripts.get("test")
    found["has_test_script"] = isinstance(test_script, str) and "no test specified" not in test_script
    dependencies = data.get("dependencies") if isinstance(data.get("dependencies"), dict) else {}
    found["dependency_count"] = len(dependencies)
    return found


def _inside(root: Path, relative: str) -> bool:
    """True when ``relative`` names an existing regular file that stays inside ``root``."""
    try:
        target = (root / relative).resolve()
        target.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return target.is_file()


def _fingerprint(lines: list[bytes]) -> str:
    normalized = b"\n".join(line.strip() for line in lines if line.strip())
    return hashlib.sha1(normalized).hexdigest()[:16]  # noqa: S324 (not security: a content fingerprint)


def inspect_tree(root: str | Path) -> dict[str, Any]:
    """Measure one checked-out repository. Returns counts and fingerprints only."""
    base = Path(root)
    code_files = code_lines = test_files = test_lines = generated_files = 0
    doc_bytes = readme_bytes = readme_headings = readme_code_blocks = 0
    languages: dict[str, int] = {}
    fingerprints: list[str] = []
    risk = {name: 0 for name in _RISK_PATTERNS}
    has_ci = has_license = has_changelog = False
    file_count = 0

    for relative, path in _walk(base):
        file_count += 1
        lower = relative.lower()
        name = lower.rsplit("/", 1)[-1]
        suffix = os.path.splitext(name)[1]
        if lower.startswith(".github/workflows/") and suffix in {".yml", ".yaml"}:
            has_ci = True
        if name.startswith("license") or name.startswith("licence"):
            has_license = True
        if name.startswith("changelog"):
            has_changelog = True
        if suffix in DOC_EXTENSIONS:
            data = _read(path)
            if data is None:
                continue
            doc_bytes += len(data)
            if "/" not in relative and name.startswith("readme") and len(data) > readme_bytes:
                readme_bytes = len(data)
                readme_headings = sum(1 for line in data.splitlines() if line.lstrip().startswith(b"#"))
                readme_code_blocks = data.count(b"```") // 2
            continue
        if suffix not in CODE_EXTENSIONS:
            continue
        data = _read(path)
        if data is None:
            generated_files += 1
            continue
        lines = [line for line in data.splitlines() if line.strip()]
        if not lines:
            continue
        if max(len(line) for line in lines) > _GENERATED_LINE and len(data) / len(lines) > 200:
            generated_files += 1
            continue
        for label, pattern in _RISK_PATTERNS.items():
            if pattern.search(data):
                risk[label] += 1
        if _TEST_PATH.search(relative):
            test_files += 1
            test_lines += len(lines)
            continue
        code_files += 1
        code_lines += len(lines)
        languages[suffix] = languages.get(suffix, 0) + len(lines)
        if len(lines) >= FINGERPRINT_MIN_LINES:
            fingerprints.append(_fingerprint(lines))

    manifest = _manifest(base)
    return {
        "schema": INSPECTION_SCHEMA,
        "files": file_count,
        "manifest": manifest,
        "code": {
            "files": code_files,
            "lines": code_lines,
            "generated_files": generated_files,
            "languages": dict(sorted(languages.items(), key=lambda item: -item[1])[:5]),
        },
        "tests": {"files": test_files, "lines": test_lines},
        "docs": {
            "bytes": doc_bytes,
            "readme_bytes": readme_bytes,
            "readme_headings": readme_headings,
            "readme_code_blocks": readme_code_blocks,
        },
        "practices": {"ci": has_ci, "license": has_license, "changelog": has_changelog},
        "risk_hints": {name: count for name, count in risk.items() if count},
        "kind": _kind(code_lines, doc_bytes, manifest),
        "fingerprints": sorted(set(fingerprints)),
    }


def _kind(code_lines: int, doc_bytes: int, manifest: Mapping[str, Any]) -> str:
    """A coarse label for what the repository mostly is."""
    if code_lines < 40 and doc_bytes > 4000:
        return "prompt pack"
    if code_lines < 40:
        return "stub"
    if not manifest.get("valid"):
        return "code without a plugin manifest"
    return "plugin"


def copy_overlap(inspections: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    """For each repository, the share of its source files also found under another owner.

    Keys are ``owner/name``. A high value means the project is largely a copy or a
    barely changed template, whatever its own statistics look like.
    """
    owners: dict[str, set[str]] = {}
    for full_name, inspection in inspections.items():
        owner = full_name.split("/", 1)[0].casefold()
        for fingerprint in inspection.get("fingerprints") or []:
            owners.setdefault(fingerprint, set()).add(owner)
    overlap: dict[str, float] = {}
    for full_name, inspection in inspections.items():
        owner = full_name.split("/", 1)[0].casefold()
        prints = inspection.get("fingerprints") or []
        if not prints:
            overlap[full_name] = 0.0
            continue
        shared = sum(1 for fingerprint in prints if owners[fingerprint] - {owner})
        overlap[full_name] = round(shared / len(prints), 3)
    return overlap
