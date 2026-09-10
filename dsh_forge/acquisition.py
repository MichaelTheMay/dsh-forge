"""Authenticated, content-addressed acquisition into a non-executable quarantine.

The acquisition boundary verifies signed package metadata before opening a
network connection, downloads only from a small HTTPS host policy, checks the
signed artifact integrity while streaming, and stores immutable bytes by their
locally computed SHA-256 digest.  It never extracts, imports, installs, or
executes downloaded content.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from typing import Any, BinaryIO, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from .file_lock import lock as lock_file, unlock as unlock_file

from .packages import PackageError, verify


RECEIPT_SCHEMA = "dsh-forge.quarantine-receipt/v1"
DEFAULT_QUARANTINE_ROOT = Path("~/.local/state/dsh-forge/quarantine")
DEFAULT_MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
HARD_MAX_ARTIFACT_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 1024 * 1024 * 1024
HARD_MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_TOTAL_TIMEOUT_SECONDS = 300.0
MAX_REDIRECTS = 3
CHUNK_BYTES = 1024 * 1024

# Hosts are intentionally static in v1. The downloader sends no credentials.
# Supporting a private registry needs a separate credential-scoping design.
SOURCE_HOSTS = {
    "npm": frozenset({"registry.npmjs.org"}),
    "github_archive": frozenset({"github.com", "codeload.github.com"}),
    "mcpb": frozenset(
        {
            "github.com",
            "release-assets.githubusercontent.com",
            "objects.githubusercontent.com",
        }
    ),
}

_SHA256_INTEGRITY = re.compile(r"sha256-([0-9a-f]{64})")
_SHA512_INTEGRITY = re.compile(r"sha512-([A-Za-z0-9+/]+={0,2})")


class AcquisitionError(PackageError):
    """A fail-closed package acquisition failure."""

    def __init__(self, message: str, code: str = "acquisition_failed"):
        super().__init__(message, code)


class _RedirectPolicy(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: frozenset[str]):
        super().__init__()
        self.allowed_hosts = allowed_hosts
        self.chain: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if code not in {301, 302, 303, 307, 308}:
            raise AcquisitionError(f"Unsupported redirect status: {code}", "redirect_rejected")
        if len(self.chain) >= MAX_REDIRECTS:
            raise AcquisitionError("Artifact redirect limit exceeded", "redirect_rejected")
        target = _validated_url(
            urljoin(req.full_url, newurl),
            self.allowed_hosts,
            "redirect target",
            allow_query=True,
        )
        self.chain.append(_redacted_url(target))
        return Request(
            target,
            headers={
                "Accept": "application/octet-stream",
                "Accept-Encoding": "identity",
                "User-Agent": "dsh-forge-acquirer/1",
            },
            method="GET",
        )


def _validated_url(
    value: str,
    allowed_hosts: frozenset[str],
    label: str,
    *,
    allow_query: bool = False,
) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise AcquisitionError(f"{label} is malformed", "source_not_allowed") from error
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not hostname
        or hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or (parsed.query and not allow_query)
        or port not in {None, 443}
    ):
        raise AcquisitionError(
            f"{label} must be credential-free HTTPS on an approved source host",
            "source_not_allowed",
        )
    return value


def _redacted_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _source_policy(plugin: dict[str, Any]) -> frozenset[str]:
    source = plugin["source"]
    try:
        allowed = SOURCE_HOSTS[source["kind"]]
    except KeyError as error:
        raise AcquisitionError(f"Unsupported source kind: {source.get('kind')}", "source_not_allowed") from error
    url = _validated_url(source["url"], allowed, f"{plugin['id']} source URL")
    parsed = urlsplit(url)
    if source["kind"] == "npm":
        if not parsed.path.endswith(".tgz") or f"-{source['version']}.tgz" not in parsed.path:
            raise AcquisitionError(
                f"{plugin['id']} npm URL does not encode its exact signed version",
                "source_not_allowed",
            )
    if source["kind"] == "github_archive" and plugin["repository"]["commit"] not in parsed.path:
        raise AcquisitionError(
            f"{plugin['id']} GitHub archive URL does not contain its signed commit",
            "source_not_allowed",
        )
    if source["kind"] == "mcpb" and source["version"] not in parsed.path:
        raise AcquisitionError(
            f"{plugin['id']} MCPB URL does not encode its exact signed version",
            "source_not_allowed",
        )
    return allowed


def _expected_digest(source: dict[str, str]) -> tuple[str, bytes]:
    integrity = source["integrity"]
    if source["kind"] == "npm":
        match = _SHA512_INTEGRITY.fullmatch(integrity)
        if not match:
            raise AcquisitionError("npm artifact is missing a valid SHA-512 SRI pin", "integrity_invalid")
        try:
            expected = base64.b64decode(match.group(1), validate=True)
        except binascii.Error as error:
            raise AcquisitionError("npm SHA-512 SRI is invalid base64", "integrity_invalid") from error
        if len(expected) != hashlib.sha512().digest_size:
            raise AcquisitionError("npm SHA-512 SRI has the wrong digest size", "integrity_invalid")
        return "sha512", expected
    match = _SHA256_INTEGRITY.fullmatch(integrity)
    if not match:
        raise AcquisitionError("artifact is missing a valid SHA-256 pin", "integrity_invalid")
    return "sha256", bytes.fromhex(match.group(1))


def _secure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        details = path.lstat()
    except OSError as error:
        raise AcquisitionError(f"Could not inspect quarantine directory {path}: {error}", "quarantine_io_error") from error
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise AcquisitionError(f"Quarantine path is not a real directory: {path}", "unsafe_quarantine")
    if details.st_mode & 0o077:
        try:
            path.chmod(0o700)
        except OSError as error:
            raise AcquisitionError(f"Could not restrict quarantine directory {path}: {error}", "unsafe_quarantine") from error


def _quarantine_layout(root: str | Path) -> dict[str, Path]:
    base = Path(root).expanduser().absolute()
    paths = {
        "root": base,
        "incoming": base / ".incoming",
        "objects": base / "objects" / "sha256",
        "receipts": base / "receipts" / "sha256",
    }
    for path in paths.values():
        _secure_directory(path)
    return paths


@contextlib.contextmanager
def _exclusive_lock(root: Path):
    lock_path = root / ".acquire.lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise AcquisitionError(f"Could not open quarantine lock: {error}", "quarantine_io_error") from error
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        else:
            os.chmod(lock_path, 0o600)
        lock_file(descriptor)
        yield
    finally:
        with contextlib.suppress(OSError):
            unlock_file(descriptor)
        os.close(descriptor)


def _open_https(source: dict[str, str], allowed_hosts: frozenset[str], timeout: float):
    url = _validated_url(source["url"], allowed_hosts, "artifact URL")
    redirects = _RedirectPolicy(allowed_hosts)
    # Ignore ambient proxy variables so signed URLs and request metadata are not
    # silently disclosed to a process-configured proxy.
    opener = build_opener(ProxyHandler({}), HTTPSHandler(), redirects)
    request = Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "Accept-Encoding": "identity",
            "User-Agent": "dsh-forge-acquirer/1",
        },
        method="GET",
    )
    try:
        response = opener.open(request, timeout=timeout)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise AcquisitionError(f"HTTPS acquisition failed: {error}", "download_failed") from error
    final_url = _validated_url(
        response.geturl(),
        allowed_hosts,
        "final response URL",
        allow_query=True,
    )
    if getattr(response, "status", 200) != 200:
        response.close()
        raise AcquisitionError(f"Artifact server returned HTTP {response.status}", "download_failed")
    encoding = (response.headers.get("Content-Encoding") or "identity").lower()
    if encoding != "identity":
        response.close()
        raise AcquisitionError("Compressed HTTP transfer encoding is not accepted", "response_rejected")
    return response, _redacted_url(final_url), redirects.chain


def _stream_artifact(
    plugin: dict[str, Any],
    destination: BinaryIO,
    *,
    max_bytes: int,
    timeout: float,
) -> dict[str, Any]:
    source = plugin["source"]
    allowed_hosts = _source_policy(plugin)
    algorithm, expected = _expected_digest(source)
    response, final_url, redirects = _open_https(source, allowed_hosts, timeout)
    sha256 = hashlib.sha256()
    expected_hasher = hashlib.new(algorithm)
    size = 0
    started = time.monotonic()
    try:
        raw_length = response.headers.get("Content-Length")
        declared: int | None = None
        if raw_length is not None:
            try:
                declared = int(raw_length)
            except ValueError as error:
                raise AcquisitionError("Artifact Content-Length is invalid", "response_rejected") from error
            if declared < 0 or declared > max_bytes:
                raise AcquisitionError("Artifact exceeds the configured byte limit", "artifact_too_large")
        while True:
            if time.monotonic() - started > timeout:
                raise AcquisitionError("Artifact download exceeded its wall-clock timeout", "download_timeout")
            chunk = response.read(min(CHUNK_BYTES, max_bytes - size + 1))
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise AcquisitionError("Artifact exceeds the configured byte limit", "artifact_too_large")
            destination.write(chunk)
            sha256.update(chunk)
            expected_hasher.update(chunk)
        if declared is not None and size != declared:
            raise AcquisitionError("Artifact length did not match Content-Length", "response_rejected")
    except AcquisitionError:
        raise
    except (OSError, TimeoutError, URLError) as error:
        raise AcquisitionError(f"Artifact stream failed: {error}", "download_failed") from error
    finally:
        response.close()
    actual_expected = expected_hasher.digest()
    if not hmac.compare_digest(actual_expected, expected):
        raise AcquisitionError(f"Integrity mismatch for {plugin['id']}", "integrity_mismatch")
    return {
        "bytes": size,
        "content_sha256": "sha256:" + sha256.hexdigest(),
        "original_url": source["url"],
        "final_url": final_url,
        "redirect_chain": redirects,
    }


def _existing_object(path: Path, digest_hex: str, expected_size: int) -> bool:
    if not path.exists():
        return False
    try:
        details = path.lstat()
    except OSError as error:
        raise AcquisitionError(f"Could not inspect quarantine object: {error}", "quarantine_io_error") from error
    if not stat.S_ISREG(details.st_mode) or details.st_size != expected_size:
        raise AcquisitionError("Existing quarantine object has an invalid type or size", "quarantine_corrupt")
    hasher = hashlib.sha256()
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            while True:
                chunk = handle.read(CHUNK_BYTES)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError as error:
        raise AcquisitionError(f"Could not verify quarantine object: {error}", "quarantine_io_error") from error
    if not hmac.compare_digest(hasher.hexdigest(), digest_hex):
        raise AcquisitionError("Existing quarantine object failed its content address", "quarantine_corrupt")
    return True


def _file_sha256(path: Path) -> tuple[int, str]:
    size = 0
    hasher = hashlib.sha256()
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            while True:
                chunk = handle.read(CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                hasher.update(chunk)
    except OSError as error:
        raise AcquisitionError(f"Could not verify staged artifact: {error}", "quarantine_io_error") from error
    return size, hasher.hexdigest()


def _verify_staged_integrity(path: Path, source: dict[str, str]) -> None:
    algorithm, expected = _expected_digest(source)
    hasher = hashlib.new(algorithm)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            while True:
                chunk = handle.read(CHUNK_BYTES)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError as error:
        raise AcquisitionError(f"Could not verify staged artifact integrity: {error}", "quarantine_io_error") from error
    if not hmac.compare_digest(hasher.digest(), expected):
        raise AcquisitionError("Staged bytes do not match signed artifact integrity", "integrity_mismatch")


def _validate_download_metadata(
    plugin: dict[str, Any],
    downloaded: dict[str, Any],
) -> None:
    allowed = _source_policy(plugin)
    if downloaded["original_url"] != plugin["source"]["url"]:
        raise AcquisitionError("Downloader changed the signed source URL", "download_failed")
    final_url = _validated_url(downloaded["final_url"], allowed, "final response URL")
    if final_url != _redacted_url(final_url):
        raise AcquisitionError("Final response URL was not query-redacted", "download_failed")
    chain = downloaded["redirect_chain"]
    if not isinstance(chain, list) or len(chain) > MAX_REDIRECTS or any(not isinstance(item, str) for item in chain):
        raise AcquisitionError("Downloader returned an invalid redirect chain", "download_failed")
    for item in chain:
        redirect = _validated_url(item, allowed, "redirect receipt URL")
        if redirect != _redacted_url(redirect):
            raise AcquisitionError("Redirect receipt URL was not query-redacted", "download_failed")


def _finalize_object(temporary: Path, objects: Path, metadata: dict[str, Any]) -> tuple[Path, bool]:
    digest_hex = metadata["content_sha256"].removeprefix("sha256:")
    directory = objects / digest_hex[:2] / digest_hex
    _secure_directory(directory.parent)
    _secure_directory(directory)
    destination = directory / "artifact"
    reused = _existing_object(destination, digest_hex, metadata["bytes"])
    if reused:
        temporary.unlink(missing_ok=True)
        return destination, True
    try:
        temporary.chmod(0o400)
        # A hard link provides create-if-absent semantics; unlike replace(), it
        # cannot overwrite an object created by a concurrent writer.
        try:
            os.link(temporary, destination, follow_symlinks=False)
        except FileExistsError:
            if not _existing_object(destination, digest_hex, metadata["bytes"]):
                raise AcquisitionError("Concurrent quarantine object could not be verified", "quarantine_corrupt")
            temporary.unlink(missing_ok=True)
            return destination, True
        temporary.unlink()
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise AcquisitionError(f"Could not finalize quarantine object: {error}", "quarantine_io_error") from error
    return destination, False


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    rendered = (json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".receipt-", delete=False) as handle:
            temporary = Path(handle.name)
            if hasattr(os, "fchmod"):
                os.fchmod(handle.fileno(), 0o600)
            else:
                os.chmod(temporary, 0o600)
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o400)
    except OSError as error:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise AcquisitionError(f"Could not write quarantine receipt: {error}", "quarantine_io_error") from error


Downloader = Callable[[dict[str, Any], BinaryIO], dict[str, Any]]


def acquire(
    envelope: dict[str, Any],
    trust_root: dict[str, Any],
    quarantine_root: str | Path = DEFAULT_QUARANTINE_ROOT,
    *,
    max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    total_timeout_seconds: float = DEFAULT_TOTAL_TIMEOUT_SECONDS,
    downloader: Downloader | None = None,
) -> dict[str, Any]:
    """Verify, acquire, and quarantine every exact artifact in a package.

    ``downloader`` exists only as a test seam. Production callers always use
    the direct credential-free HTTPS implementation above.
    """

    if type(max_artifact_bytes) is not int or not 1 <= max_artifact_bytes <= HARD_MAX_ARTIFACT_BYTES:
        raise AcquisitionError(
            f"max_artifact_bytes must be between 1 and {HARD_MAX_ARTIFACT_BYTES}",
            "invalid_acquisition_limit",
        )
    if type(max_total_bytes) is not int or not 1 <= max_total_bytes <= HARD_MAX_TOTAL_BYTES:
        raise AcquisitionError(
            f"max_total_bytes must be between 1 and {HARD_MAX_TOTAL_BYTES}",
            "invalid_acquisition_limit",
        )
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 300:
        raise AcquisitionError("timeout_seconds must be between 1 and 300", "invalid_acquisition_limit")
    if (
        not isinstance(total_timeout_seconds, (int, float))
        or isinstance(total_timeout_seconds, bool)
        or not 1 <= total_timeout_seconds <= 3600
    ):
        raise AcquisitionError("total_timeout_seconds must be between 1 and 3600", "invalid_acquisition_limit")

    # This must happen before quarantine creation or any network operation.
    verification = verify(envelope, trust_root)
    manifest = verification["manifest"]
    for plugin in manifest["plugins"]:
        _source_policy(plugin)
        _expected_digest(plugin["source"])
    layout = _quarantine_layout(quarantine_root)
    artifacts: list[dict[str, Any]] = []
    total_bytes = 0
    package_started = time.monotonic()

    with _exclusive_lock(layout["root"]):
        for plugin in manifest["plugins"]:
            temporary: Path | None = None
            try:
                # Enforce source identity and host policy even when a test
                # downloader supplies the bytes.
                _source_policy(plugin)
                descriptor, name = tempfile.mkstemp(prefix="artifact-", dir=layout["incoming"])
                temporary = Path(name)
                if hasattr(os, "fchmod"):
                    os.fchmod(descriptor, 0o600)
                else:
                    os.chmod(temporary, 0o600)
                with os.fdopen(descriptor, "w+b") as handle:
                    remaining_time = float(total_timeout_seconds) - (time.monotonic() - package_started)
                    if remaining_time <= 0:
                        raise AcquisitionError("Package acquisition exceeded its total timeout", "download_timeout")
                    remaining_bytes = max_total_bytes - total_bytes
                    if remaining_bytes <= 0:
                        raise AcquisitionError("Package exceeds the configured total byte limit", "artifact_too_large")
                    if downloader is None:
                        downloaded = _stream_artifact(
                            plugin,
                            handle,
                            max_bytes=min(max_artifact_bytes, remaining_bytes),
                            timeout=min(float(timeout_seconds), remaining_time),
                        )
                    else:
                        downloaded = downloader(plugin, handle)
                    handle.flush()
                    os.fsync(handle.fileno())

                if set(downloaded) != {"bytes", "content_sha256", "original_url", "final_url", "redirect_chain"}:
                    raise AcquisitionError("Downloader returned an invalid result", "download_failed")
                _validate_download_metadata(plugin, downloaded)
                size = downloaded["bytes"]
                digest = downloaded["content_sha256"]
                if type(size) is not int or not 0 <= size <= max_artifact_bytes:
                    raise AcquisitionError("Downloader returned an invalid artifact size", "download_failed")
                if total_bytes + size > max_total_bytes:
                    raise AcquisitionError("Package exceeds the configured total byte limit", "artifact_too_large")
                if time.monotonic() - package_started > total_timeout_seconds:
                    raise AcquisitionError("Package acquisition exceeded its total timeout", "download_timeout")
                if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                    raise AcquisitionError("Downloader returned an invalid content digest", "download_failed")
                actual_size, actual_digest = _file_sha256(temporary)
                if actual_size != size or not hmac.compare_digest(digest, "sha256:" + actual_digest):
                    raise AcquisitionError("Downloader result does not match staged bytes", "integrity_mismatch")
                _verify_staged_integrity(temporary, plugin["source"])

                destination, reused = _finalize_object(temporary, layout["objects"], downloaded)
                temporary = None
                artifacts.append(
                    {
                        "plugin_id": plugin["id"],
                        "source_kind": plugin["source"]["kind"],
                        "source_name": plugin["source"]["name"],
                        "source_version": plugin["source"]["version"],
                        "signed_integrity": plugin["source"]["integrity"],
                        **downloaded,
                        "object": str(destination.relative_to(layout["root"])),
                        "reused": reused,
                    }
                )
                total_bytes += size
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

        payload_hex = verification["payload_digest"].removeprefix("sha256:")
        receipt_path = layout["receipts"] / f"{payload_hex}.json"
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "package": manifest["package"],
            "payload_digest": verification["payload_digest"],
            "composition_digest": manifest["composition_digest"],
            "valid_signers": verification["valid_signers"],
            "threshold": verification["threshold"],
            "acquired_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "quarantine_root": str(layout["root"]),
            "limits": {
                "max_artifact_bytes": max_artifact_bytes,
                "max_total_bytes": max_total_bytes,
                "artifact_timeout_seconds": float(timeout_seconds),
                "total_timeout_seconds": float(total_timeout_seconds),
            },
            "artifacts": artifacts,
            "credentials_forwarded": False,
            "archives_extracted": False,
            "installation_authorized": False,
            "execution_authorized": False,
        }
        _write_receipt(receipt_path, receipt)
        receipt["receipt"] = str(receipt_path)
        return receipt
