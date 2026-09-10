#!/usr/bin/env python3
"""Run the loopback-only DSH Forge launcher and static UI."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from functools import partial
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dsh_forge.launcher import Launcher, LauncherError  # noqa: E402
from dsh_forge.sandbox import ApptainerSandbox, SandboxConfig, SandboxError  # noqa: E402


class LauncherHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, launcher: Launcher, session_token: str | None = None):
        self.launcher = launcher
        self.session_token = session_token or secrets.token_urlsafe(32)
        super().__init__(address, handler)
        self.launcher.protected_ports.add(self.server_address[1])


class LauncherUIHandler(SimpleHTTPRequestHandler):
    """Serve the UI plus a same-origin, session-protected local API."""

    server: LauncherHTTPServer

    def list_directory(self, path):
        self.send_error(404, "Directory listing disabled")
        return None

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self'; frame-src http://127.0.0.1:* http://localhost:*; frame-ancestors 'none'; base-uri 'none'")
        super().end_headers()

    def _loopback_host(self) -> bool:
        try:
            host = urlsplit("//" + (self.headers.get("Host") or "")).hostname
        except ValueError:
            return False
        host = (host or "").lower()
        return host in {"127.0.0.1", "localhost", "::1"}

    def _session_ok(self) -> bool:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        item = cookie.get("dsh_forge_session")
        return bool(item and secrets.compare_digest(item.value, self.server.session_token))

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed = urlsplit(origin)
            host_header = urlsplit("//" + (self.headers.get("Host") or ""))
        except ValueError:
            return False
        return (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.hostname == host_header.hostname
            and parsed.port == host_header.port
        )

    def _api_guard(self, mutation: bool = False) -> bool:
        if not self._loopback_host():
            self._json({"error": "Loopback Host header required"}, HTTPStatus.FORBIDDEN)
            return False
        if mutation and (not self._session_ok() or not self._origin_ok()):
            self._json({"error": "Valid same-origin launcher session required"}, HTTPStatus.FORBIDDEN)
            return False
        return True

    def _json(self, payload, status: HTTPStatus = HTTPStatus.OK, establish_session: bool = False):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if establish_session:
            self.send_header("Set-Cookie", f"dsh_forge_session={self.server.session_token}; HttpOnly; SameSite=Strict; Path=/")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise LauncherError("Invalid Content-Length") from None
        if length > 65536:
            raise LauncherError("Request body is too large")
        if not length:
            return {}
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise LauncherError("Request body must be JSON") from None
        if not isinstance(value, dict):
            raise LauncherError("Request body must be a JSON object")
        return value

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/v1/status":
            if self._api_guard():
                self._json(self.server.launcher.status(), establish_session=True)
            return
        if path == "/api/v1/trees":
            if self._api_guard() and self._session_ok():
                self._json({"trees": self.server.launcher.status()["trees"]})
            elif self._loopback_host():
                self._json({"error": "Launcher session required"}, HTTPStatus.FORBIDDEN)
            return
        if path == "/api/v1/cells":
            if self._api_guard() and self._session_ok():
                self._json({"cells": self.server.launcher.status()["cells"]})
            elif self._loopback_host():
                self._json({"error": "Launcher session required"}, HTTPStatus.FORBIDDEN)
            return
        match = re.fullmatch(r"/api/v1/cells/([^/]+)/logs", path)
        if match:
            if self._api_guard() and self._session_ok():
                try:
                    self._json({"lines": self.server.launcher.logs(match.group(1))})
                except LauncherError as error:
                    self._json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            elif self._loopback_host():
                self._json({"error": "Launcher session required"}, HTTPStatus.FORBIDDEN)
            return
        match = re.fullmatch(r"/api/v1/cells/([^/]+)/open-url", path)
        if match:
            if self._api_guard() and self._session_ok():
                try:
                    self._json({"url": self.server.launcher.open_url(match.group(1))})
                except LauncherError as error:
                    self._json({"error": str(error)}, HTTPStatus.CONFLICT)
            elif self._loopback_host():
                self._json({"error": "Launcher session required"}, HTTPStatus.FORBIDDEN)
            return
        match = re.fullmatch(r"/api/v1/cells/([^/]+)/artifacts", path)
        if match:
            if self._api_guard() and self._session_ok():
                try:
                    self._json({"artifacts": self.server.launcher.artifacts(match.group(1))})
                except LauncherError as error:
                    self._json({"error": str(error)}, HTTPStatus.NOT_FOUND)
            elif self._loopback_host():
                self._json({"error": "Launcher session required"}, HTTPStatus.FORBIDDEN)
            return
        if path.startswith("/api/"):
            self._json({"error": "Unknown API endpoint"}, HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        if not path.startswith("/api/v1/"):
            self._json({"error": "Unknown API endpoint"}, HTTPStatus.NOT_FOUND)
            return
        if not self._api_guard(mutation=True):
            return
        try:
            body = self._body()
            if path == "/api/v1/scan":
                roots = body.get("roots")
                if roots is None:
                    payload = self.server.launcher.scan()
                elif isinstance(roots, list):
                    payload = self.server.launcher.add_scan_roots(roots)
                else:
                    raise LauncherError("roots must be a JSON array")
                self._json(payload)
                return
            if path == "/api/v1/versions/remove":
                version_id = body.get("id")
                if not isinstance(version_id, str):
                    raise LauncherError("id must be a saved local-version ID")
                self._json(self.server.launcher.remove_saved_version(version_id))
                return
            if path == "/api/v1/versions/settings":
                version_id = body.get("id")
                settings = body.get("launch")
                if not isinstance(version_id, str):
                    raise LauncherError("id must be a saved local-version ID")
                if not isinstance(settings, dict):
                    raise LauncherError("launch must be a JSON object")
                self._json(self.server.launcher.update_saved_version(version_id, settings))
                return
            if path == "/api/v1/launches/preview":
                self._json(self.server.launcher.preview(body))
                return
            if path == "/api/v1/packages/install":
                package_slug = body.get("package_slug")
                version_id = body.get("version_id")
                profile = body.get("profile", "web")
                if not isinstance(package_slug, str) or not isinstance(version_id, str) or not isinstance(profile, str):
                    raise LauncherError("package_slug, version_id, and profile must be strings")
                self._json(
                    self.server.launcher.install_trusted_catalog_package(
                        package_slug=package_slug,
                        version_id=version_id,
                        profile=profile,
                    ),
                    HTTPStatus.CREATED,
                )
                return
            if path == "/api/v1/configurations":
                self._json(
                    self.server.launcher.save_configuration(
                        name=body.get("name"),
                        description=body.get("description", ""),
                        version_id=body.get("version_id"),
                        package_slug=body.get("package_slug"),
                        selections=body.get("selections"),
                        launch=body.get("launch"),
                        draft=body.get("draft") is True,
                        source="user",
                    ),
                    HTTPStatus.CREATED,
                )
                return
            if path == "/api/v1/configurations/approve":
                self._json(self.server.launcher.approve_configuration(body.get("id")))
                return
            if path == "/api/v1/configurations/remove":
                self._json({"configurations": self.server.launcher.remove_configuration(body.get("id"))})
                return
            if path == "/api/v1/configurations/run":
                task = body.get("task")
                if task is not None and not isinstance(task, str):
                    raise LauncherError("task must be a string")
                self._json(
                    self.server.launcher.run_configuration(body.get("id"), task=task),
                    HTTPStatus.CREATED,
                )
                return
            if path == "/api/v1/assistant/start":
                version_id = body.get("version_id")
                if not isinstance(version_id, str):
                    raise LauncherError("version_id must be a saved local-version ID")
                self._json(self.server.launcher.launch_assistant(version_id), HTTPStatus.CREATED)
                return
            if path == "/api/v1/cells":
                self._json(self.server.launcher.launch(body), HTTPStatus.CREATED)
                return
            match = re.fullmatch(r"/api/v1/trees/([^/]+)/sandbox-test", path)
            if match:
                self._json(self.server.launcher.sandbox_test(match.group(1)))
                return
            match = re.fullmatch(r"/api/v1/cells/([^/]+)/(stop|restart|clone)", path)
            if match:
                action = match.group(2)
                payload = self.server.launcher.stop(match.group(1)) if action == "stop" else (
                    self.server.launcher.restart(match.group(1)) if action == "restart" else self.server.launcher.clone(match.group(1))
                )
                self._json(payload)
                return
            self._json({"error": "Unknown API endpoint"}, HTTPStatus.NOT_FOUND)
        except LauncherError as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            self.log_error("internal launcher error: %s", error)
            self._json({"error": "Internal launcher error; see the sidecar terminal"}, HTTPStatus.INTERNAL_SERVER_ERROR)


# Compatibility alias used by downstream imports and earlier tests.
StaticUIHandler = LauncherUIHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3090)
    parser.add_argument("--scan-root", action="append", default=[], help="Register an explicit directory for bounded DSH discovery; repeatable")
    parser.add_argument("--state-dir", type=Path, help="Override launcher state/log directory")
    parser.add_argument("--sandbox-image", type=Path, help="Pinned Apptainer SIF required for probes and complete local cells")
    parser.add_argument("--sandbox-image-sha256", help="Expected SHA-256 for --sandbox-image")
    parser.add_argument("--sandbox-binary", help="Apptainer executable name or absolute path")
    parser.add_argument("--sandbox-cpus", help="CPU limit required by the sandbox capability probe")
    parser.add_argument("--sandbox-memory", help="Memory limit required by the sandbox capability probe, for example 8G")
    parser.add_argument("--sandbox-pids-limit", type=int, help="PID limit required by the sandbox capability probe")
    parser.add_argument("--sandbox-timeout", type=int, help="Maximum sandbox test duration in seconds")
    parser.add_argument("--cell-timeout", type=int, help="Maximum complete-cell lifetime in seconds")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose an unprivileged port between 1024 and 65535")
    configured_state = args.state_dir or os.environ.get("DSH_FORGE_STATE_DIR")
    state_root = Path(configured_state).expanduser() if configured_state else Path.home() / ".local" / "state" / "dsh-forge"
    try:
        sandbox_config = SandboxConfig.from_values(
            image=args.sandbox_image or os.environ.get("DSH_FORGE_SANDBOX_IMAGE"),
            image_sha256=args.sandbox_image_sha256 or os.environ.get("DSH_FORGE_SANDBOX_IMAGE_SHA256"),
            binary=args.sandbox_binary or os.environ.get("DSH_FORGE_SANDBOX_BINARY", "apptainer"),
            cpus=args.sandbox_cpus or os.environ.get("DSH_FORGE_SANDBOX_CPUS", "4"),
            memory=args.sandbox_memory or os.environ.get("DSH_FORGE_SANDBOX_MEMORY", "8G"),
            pids_limit=args.sandbox_pids_limit if args.sandbox_pids_limit is not None else int(os.environ.get("DSH_FORGE_SANDBOX_PIDS_LIMIT", "256")),
            timeout_seconds=args.sandbox_timeout if args.sandbox_timeout is not None else int(os.environ.get("DSH_FORGE_SANDBOX_TIMEOUT", "30")),
            cell_timeout_seconds=args.cell_timeout if args.cell_timeout is not None else int(os.environ.get("DSH_FORGE_CELL_TIMEOUT", "14400")),
        )
    except (SandboxError, ValueError) as error:
        parser.error(str(error))
    sandbox = ApptainerSandbox(sandbox_config, state_root / "sandbox")
    launcher = Launcher(args.scan_root, state_root=state_root, sandbox=sandbox)
    handler = partial(LauncherUIHandler, directory=str(WEB_ROOT))
    try:
        server = LauncherHTTPServer(("127.0.0.1", args.port), handler, launcher)
    except OSError as error:
        parser.exit(1, f"Could not bind loopback port {args.port}: {error}. Try --port {args.port + 1}.\n")
    print(f"DSH Forge launcher: http://127.0.0.1:{args.port}/#launch", flush=True)
    status = launcher.status()
    print(f"Detected {len(status['trees'])} trusted/view-only DSH tree(s). Community browsers remain metadata-only.", flush=True)
    if not status["trees"]:
        print("No DSH tree detected. Restart with --scan-root /path/to/deepseek-harness.", flush=True)
    sandbox_status = status["sandbox"]
    print(f"Cell runner: {sandbox_status['mode']} · {'ready' if sandbox_status['ready'] else sandbox_status['reason']}", flush=True)
    print("The sidecar is loopback-only. Press Ctrl+C to stop it and its owned cells.", flush=True)
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            launcher.shutdown()


if __name__ == "__main__":
    main()
