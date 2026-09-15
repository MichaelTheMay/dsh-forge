"""Packaged-application paths, capabilities, and release update checks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


RELEASE_API_URL = "https://api.github.com/repos/MichaelTheMay/dsh-forge/releases/latest"
MAX_UPDATE_RESPONSE_BYTES = 1_000_000
_VERSION = re.compile(
    r"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$"
)


def packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Return the repository root or PyInstaller's extracted data root."""
    if packaged():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def application_version() -> str:
    """Read build metadata embedded by a desktop packaging job."""
    try:
        value = json.loads((bundle_root() / "build-version.json").read_text(encoding="utf-8-sig"))
        version = str(value.get("version") or "") if isinstance(value, dict) else ""
    except (OSError, UnicodeError, json.JSONDecodeError):
        version = ""
    return version if _VERSION.fullmatch(version) else "development"


def default_state_root() -> Path:
    configured = os.environ.get("DSH_FORGE_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    if packaged() and os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "DSH Forge"
    if packaged() and sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "DSH Forge"
    return Path.home() / ".local" / "state" / "dsh-forge"


def application_status() -> dict[str, Any]:
    windows = os.name == "nt"
    linux = sys.platform.startswith("linux")
    return {
        "name": "DSH Forge",
        "version": application_version(),
        "packaged": packaged(),
        "platform": "windows" if windows else ("macos" if sys.platform == "darwin" else "linux"),
        "updates": {
            "available": packaged(),
            "mechanism": "signed-installer-release-page" if packaged() else "source-checkout",
        },
        "native_sandbox": {
            "available": linux,
            "backend": "apptainer" if linux else None,
            "message": (
                "Local DSH detection and catalog browsing run natively on Windows. "
                "Secure plugin, fork, and isolated cell execution requires WSL2 or a remote "
                "Linux host with Apptainer, so Forge keeps those actions disabled here."
                if windows else (
                    "Isolated execution is enabled only after the local Apptainer capability probe passes."
                    if linux else
                    "Secure plugin, fork, and isolated cell execution requires a Linux host with Apptainer."
                )
            ),
        },
    }


def acquire_windows_instance() -> Any:
    """Hold a per-user mutex for a packaged Windows launcher process."""
    if not packaged() or os.name != "nt":
        return True
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, "Local\\MichaelTheMay.DSHForge")
    if not handle:
        raise OSError(ctypes.get_last_error(), "Could not create the DSH Forge instance mutex")
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return False
    return handle


def _version_key(value: str) -> tuple[Any, ...]:
    match = _VERSION.fullmatch(value)
    if not match:
        raise ValueError("Release version is not valid semantic versioning")
    prerelease = match.group(4)
    identifiers: tuple[Any, ...] = ()
    if prerelease is not None:
        identifiers = tuple(
            (0, int(item)) if item.isdigit() else (1, item.casefold())
            for item in prerelease.split(".")
        )
    return (
        int(match.group(1)), int(match.group(2)), int(match.group(3)),
        1 if prerelease is None else 0, identifiers,
    )


def check_for_update(
    current_version: str | None = None,
    *,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Check the official latest-release record without downloading executable code."""
    current = current_version or application_version()
    base = {"current_version": current, "latest_version": None, "release_url": None}
    if current == "development":
        return {**base, "status": "disabled", "reason": "Update checks are enabled in packaged builds."}
    try:
        current_key = _version_key(current)
        request = Request(
            RELEASE_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"DSH-Forge/{current}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with opener(request, timeout=5) as response:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "api.github.com":
                raise ValueError("The release API redirected to an unexpected host")
            raw = response.read(MAX_UPDATE_RESPONSE_BYTES + 1)
        if len(raw) > MAX_UPDATE_RESPONSE_BYTES:
            raise ValueError("The release response is too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("The release response is not an object")
        latest = str(payload.get("tag_name") or "").removeprefix("v")
        latest_key = _version_key(latest)
        release_url = str(payload.get("html_url") or "")
        parsed_release = urlsplit(release_url)
        if (
            parsed_release.scheme != "https"
            or parsed_release.hostname != "github.com"
            or not parsed_release.path.startswith("/MichaelTheMay/dsh-forge/releases/")
            or parsed_release.query
            or parsed_release.fragment
        ):
            raise ValueError("The release link is not an official DSH Forge release URL")
        return {
            **base,
            "status": "available" if latest_key > current_key else "current",
            "latest_version": latest,
            "release_url": release_url,
            "reason": "A newer signed installer is available." if latest_key > current_key else "DSH Forge is current.",
        }
    except Exception as error:
        return {**base, "status": "unavailable", "reason": f"Could not check for updates: {error}"}
