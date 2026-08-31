#!/usr/bin/env python3
"""Serve the static DSH Forge UI on loopback; no runner or catalog execution."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1] / "web"


class StaticUIHandler(SimpleHTTPRequestHandler):
    def list_directory(self, path):
        self.send_error(404, "Directory listing disabled")
        return None

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3090)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose an unprivileged port between 1024 and 65535")
    handler = partial(StaticUIHandler, directory=str(WEB_ROOT))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as error:
        parser.exit(1, f"Could not bind loopback port {args.port}: {error}. Try --port {args.port + 1}.\n")
    print(f"DSH Forge UI prototype: http://127.0.0.1:{args.port}/#public-repos", flush=True)
    print("No local runner is connected. Press Ctrl+C to stop.", flush=True)
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
