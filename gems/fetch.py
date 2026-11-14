"""Get one repository's files at one exact commit, without trusting the repository.

The checkout is for reading only. Nothing in it is ever executed here: hooks are
disabled, submodules and LFS are not followed, symlinks are written as plain files,
the user's Git configuration and credentials are not used, and the size is capped.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

MAX_CHECKOUT_BYTES = 200 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 120

_SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


class FetchError(RuntimeError):
    """The repository could not be fetched safely."""


def _git_environment() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "LC_ALL": "C",
    }


def _git(arguments: list[str], cwd: Path, timeout: int) -> None:
    command = [
        "git",
        "-c", "core.hooksPath=" + os.devnull,
        "-c", "core.symlinks=false",
        "-c", "core.fsmonitor=false",
        "-c", "protocol.file.allow=never",
        "-c", "protocol.ext.allow=never",
        "-c", "credential.helper=",
        "-c", "advice.detachedHead=false",
        *arguments,
    ]
    try:
        result = subprocess.run(
            command, cwd=cwd, env=_git_environment(), timeout=timeout,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise FetchError("Fetching took too long") from error
    except OSError as error:
        raise FetchError(f"Git is not available: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["unknown error"]
        raise FetchError(f"git {arguments[0]} failed: {detail[0][:200]}")


def directory_bytes(root: Path) -> int:
    total = 0
    for directory, _names, files in os.walk(root, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(directory, name)).st_size
            except OSError:
                continue
    return total


def fetch_commit(
    full_name: str,
    commit: str,
    destination: str | Path,
    *,
    remote: str | None = None,
    timeout: int = FETCH_TIMEOUT_SECONDS,
    max_bytes: int = MAX_CHECKOUT_BYTES,
) -> Path:
    """Write ``full_name`` at ``commit`` into ``destination`` and return the path.

    ``remote`` overrides the GitHub URL (tests use a local repository). The Git
    metadata directory is removed afterwards so only the files remain.
    """
    if not _SLUG.match(full_name):
        raise FetchError("Not a valid owner/name repository")
    if not _SHA.match(commit):
        raise FetchError("Not a full commit id")
    target = Path(destination).expanduser()
    if target.exists() and any(target.iterdir()):
        raise FetchError("The destination is not empty")
    target.mkdir(parents=True, exist_ok=True)
    url = remote or f"https://github.com/{full_name}.git"
    local = remote is not None
    try:
        _git(["init", "--quiet"], target, 30)
        _git(["remote", "add", "origin", url], target, 30)
        fetch = ["fetch", "--quiet", "--depth", "1", "--no-tags", "--no-recurse-submodules", "origin", commit]
        if local:
            # Local test remotes need the file protocol and may refuse fetches by commit id.
            fetch = ["-c", "protocol.file.allow=always", "-c", "uploadpack.allowAnySHA1InWant=true", *fetch]
        _git(fetch, target, timeout)
        if directory_bytes(target / ".git") > max_bytes:
            raise FetchError("The repository is larger than the reading limit")
        _git(["checkout", "--quiet", "--detach", "FETCH_HEAD"], target, timeout)
    except FetchError:
        shutil.rmtree(target, ignore_errors=True)
        raise
    shutil.rmtree(target / ".git", ignore_errors=True)
    if directory_bytes(target) > max_bytes:
        shutil.rmtree(target, ignore_errors=True)
        raise FetchError("The repository is larger than the reading limit")
    return target
