"""Dependency-free MCP stdio facade for the local DSH Forge catalog.

The server intentionally exposes discovery and draft creation, not package
installation or cell execution.  Newline-delimited JSON-RPC keeps the stdio
transport usable on Python 3.9 without adding a runtime dependency.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence, TextIO

from .launcher import Launcher, LauncherError


# Forge currently implements the connection-level initialize handshake used by
# the 2025-06-18 and earlier protocol revisions.  MCP 2026-07-28 moved version
# negotiation into per-request metadata, so advertising it here would be a
# false interoperability claim.
LATEST_PROTOCOL = "2025-06-18"
SUPPORTED_PROTOCOLS = {LATEST_PROTOCOL, "2025-03-26", "2024-11-05"}
SERVER_VERSION = "0.1.0"


def _json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LauncherError(f"Could not read catalog metadata: {error}") from error
    if not isinstance(value, dict):
        raise LauncherError("Catalog metadata must be a JSON object")
    return value


class CatalogIndex:
    """Small bounded view over already-ingested, metadata-only catalog files."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else Path(__file__).resolve().parents[1] / "data"
        public = _json_file(self.root / "public-repos.seed.json")
        packages = _json_file(self.root / "package-catalog.seed.json")
        rows: list[dict[str, Any]] = []
        for raw in public.get("supplemental_entries", []):
            if isinstance(raw, dict):
                rows.append(self._repository(raw, "plugin"))
        for raw in public.get("entries", []):
            if isinstance(raw, dict):
                rows.append(self._repository(raw, "fork"))
        for raw in packages.get("packages", []):
            if isinstance(raw, dict):
                rows.append(self._package(raw))
        self.rows = rows[:2048]
        self.snapshot = {
            "schema": "dsh-forge.mcp-catalog/v1",
            "public_snapshot_id": public.get("snapshot_id"),
            "package_catalog_digest": packages.get("catalog_digest"),
            "counts": {
                kind: sum(row["type"] == kind for row in self.rows)
                for kind in ("package", "plugin", "fork")
            },
        }

    @staticmethod
    def _repository(raw: Mapping[str, Any], kind: str) -> dict[str, Any]:
        curation = raw.get("curation") if isinstance(raw.get("curation"), Mapping) else {}
        package = raw.get("package") if isinstance(raw.get("package"), Mapping) else {}
        return {
            "type": kind,
            "id": str(raw.get("artifact_id") or raw.get("full_name") or ""),
            "name": str(raw.get("name") or ""),
            "owner": str(raw.get("owner") or ""),
            "description": str(raw.get("description") or ""),
            "topics": [str(item) for item in raw.get("topics", []) if isinstance(item, str)][:32],
            "taxonomy": [str(item) for item in curation.get("taxonomy", []) if isinstance(item, str)][:16],
            "risk": str(curation.get("security_risk") or "unassessed"),
            "compatibility": str((raw.get("compatibility") or {}).get("summary") or "Not reproduced"),
            "version": str(package.get("version") or ""),
            "source": str(raw.get("repository_url") or ""),
            "commit": str(raw.get("head_sha") or ""),
            "featured": (
                int(curation.get("rank") or 999) <= 3
                if kind == "plugin"
                else int(raw.get("seed_rank") or 999) <= 3
            ),
            "verification": "metadata-only",
        }

    @staticmethod
    def _package(raw: Mapping[str, Any]) -> dict[str, Any]:
        components = raw.get("components") if isinstance(raw.get("components"), list) else []
        return {
            "type": "package",
            "id": str(raw.get("id") or ""),
            "name": str(raw.get("name") or ""),
            "owner": str((raw.get("publisher") or {}).get("name") or ""),
            "description": str(raw.get("summary") or ""),
            "topics": [],
            "taxonomy": [str(item) for item in raw.get("taxonomy", []) if isinstance(item, str)][:16],
            "risk": str((raw.get("risk") or {}).get("level") or "unassessed"),
            "compatibility": str((raw.get("compatibility") or {}).get("summary") or "Not reproduced"),
            "version": "",
            "source": "",
            "commit": "",
            "featured": raw.get("featured") is True,
            "components": [
                {
                    "id": str(item.get("id") or ""),
                    "name": str((item.get("package") or {}).get("name") or ""),
                    "version": str((item.get("package") or {}).get("version") or ""),
                    "role": str(item.get("role") or ""),
                }
                for item in components if isinstance(item, Mapping)
            ],
            "verification": "metadata-only",
        }

    def search(self, query: str = "", kind: str = "all", limit: int = 20, featured: bool = False) -> dict[str, Any]:
        query = str(query or "").strip().casefold()
        terms = query.split()
        if kind not in {"all", "package", "plugin", "fork"}:
            raise LauncherError("Catalog type must be all, package, plugin, or fork")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise LauncherError("Catalog result limit must be between 1 and 50")
        matches: list[dict[str, Any]] = []
        for row in self.rows:
            if kind != "all" and row["type"] != kind:
                continue
            if featured and not row.get("featured"):
                continue
            haystack = " ".join([
                row["id"], row["name"], row["owner"], row["description"],
                *row.get("topics", []), *row.get("taxonomy", []),
            ]).casefold()
            if terms and not all(term in haystack for term in terms):
                continue
            matches.append(row)
        return {"query": query, "type": kind, "featured": featured, "count": len(matches), "results": matches[:limit]}


def _tool_definitions() -> list[dict[str, Any]]:
    read_only = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
    return [
        {
            "name": "catalog_search",
            "title": "Search the DSH Forge catalog",
            "description": "Search ingested package, plugin, and fork metadata. Results are discovery evidence, not executable trust.",
            "inputSchema": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "query": {"type": "string", "maxLength": 500},
                    "type": {"enum": ["all", "package", "plugin", "fork"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "featured": {"type": "boolean"},
                },
            },
            "annotations": read_only,
        },
        {
            "name": "versions_list",
            "title": "List saved Harness versions",
            "description": "List local saved Harness identities and readiness without executing them.",
            "inputSchema": {"type": "object", "additionalProperties": False},
            "annotations": read_only,
        },
        {
            "name": "configurations_list",
            "title": "List saved configurations",
            "description": "List reviewed configurations and MCP drafts with their fail-closed run readiness.",
            "inputSchema": {"type": "object", "additionalProperties": False},
            "annotations": read_only,
        },
        {
            "name": "configuration_save_draft",
            "title": "Save a configuration draft",
            "description": "Save an inert draft for human review. This never installs packages or launches a Harness.",
            "inputSchema": {
                "type": "object", "additionalProperties": False,
                "required": ["name", "version_id", "selections"],
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 80},
                    "description": {"type": "string", "maxLength": 4000},
                    "version_id": {"type": "string", "pattern": "^version_[0-9a-f]{12}$"},
                    "selections": {
                        "type": "array", "maxItems": 64,
                        "items": {
                            "type": "object", "additionalProperties": False, "required": ["type", "id"],
                            "properties": {
                                "type": {"enum": ["package", "plugin", "fork"]},
                                "id": {"type": "string", "minLength": 1, "maxLength": 240},
                            },
                        },
                    },
                    "surface": {"enum": ["web", "headless"]},
                    "task": {"type": "string", "maxLength": 20000},
                },
            },
            "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
        },
    ]


class ForgeMCP:
    def __init__(self, launcher: Launcher, catalog: CatalogIndex | None = None):
        self.launcher = launcher
        self.catalog = catalog or CatalogIndex()

    @staticmethod
    def _result(value: Any, *, error: bool = False) -> dict[str, Any]:
        rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
        return {"content": [{"type": "text", "text": rendered}], "structuredContent": value, "isError": error}

    def call_tool(self, name: str, arguments: Any) -> dict[str, Any]:
        args = arguments if isinstance(arguments, dict) else {}
        try:
            if name == "catalog_search":
                return self._result(self.catalog.search(
                    query=str(args.get("query") or ""),
                    kind=str(args.get("type") or "all"),
                    limit=args.get("limit", 20),
                    featured=args.get("featured") is True,
                ))
            if name == "versions_list":
                status = self.launcher.status()
                return self._result({"saved_versions": status["saved_versions"]})
            if name == "configurations_list":
                return self._result({"configurations": self.launcher.configurations()})
            if name == "configuration_save_draft":
                surface = str(args.get("surface") or "web")
                return self._result(self.launcher.save_configuration(
                    name=str(args.get("name") or ""),
                    description=str(args.get("description") or ""),
                    version_id=str(args.get("version_id") or ""),
                    selections=args.get("selections"),
                    launch={
                        "surface": surface,
                        "profile": "web",
                        "task": str(args.get("task") or ""),
                        "port": "auto",
                        "open_browser": False,
                        "network": "host" if surface == "web" else "none",
                        "resources": {"gpu": "none"},
                    },
                    draft=True,
                    source="mcp-draft",
                ))
            return self._result({"error": "Unknown tool"}, error=True)
        except LauncherError as exc:
            return self._result({"error": str(exc)}, error=True)

    def dispatch(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None, "error": {"code": -32600, "message": "Invalid Request"}}
        method = message.get("method")
        request_id = message.get("id")
        if request_id is None:
            return None
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        try:
            if method == "initialize":
                requested = str(params.get("protocolVersion") or "")
                protocol = requested if requested in SUPPORTED_PROTOCOLS else LATEST_PROTOCOL
                result = {
                    "protocolVersion": protocol,
                    "capabilities": {"tools": {"listChanged": False}, "resources": {"subscribe": False, "listChanged": False}, "prompts": {"listChanged": False}},
                    "serverInfo": {"name": "dsh-forge", "title": "DSH Forge", "version": SERVER_VERSION},
                    "instructions": "Use catalog evidence to propose complementary Harness packages. Save only drafts; installation and execution require separate local approval.",
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": _tool_definitions()}
            elif method == "tools/call":
                result = self.call_tool(str(params.get("name") or ""), params.get("arguments"))
            elif method == "resources/list":
                result = {"resources": [
                    {"uri": "dsh-forge://catalog", "name": "Catalog snapshot", "mimeType": "application/json"},
                    {"uri": "dsh-forge://versions", "name": "Saved Harness versions", "mimeType": "application/json"},
                    {"uri": "dsh-forge://configurations", "name": "Saved configurations", "mimeType": "application/json"},
                ]}
            elif method == "resources/read":
                uri = str(params.get("uri") or "")
                if uri == "dsh-forge://catalog":
                    value = {**self.catalog.snapshot, "entries": self.catalog.rows}
                elif uri == "dsh-forge://versions":
                    value = {"saved_versions": self.launcher.status()["saved_versions"]}
                elif uri == "dsh-forge://configurations":
                    value = {"configurations": self.launcher.configurations()}
                else:
                    raise LauncherError("Unknown resource")
                result = {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(value, sort_keys=True)}]}
            elif method == "prompts/list":
                result = {"prompts": [{
                    "name": "build-harness", "title": "Build a complementary Harness",
                    "description": "Compare catalog evidence and draft a bounded configuration.",
                    "arguments": [{"name": "goal", "description": "Task the Harness should optimize for", "required": True}],
                }]}
            elif method == "prompts/get":
                if params.get("name") != "build-harness":
                    raise LauncherError("Unknown prompt")
                goal = str((params.get("arguments") or {}).get("goal") or "").strip()
                if not goal:
                    raise LauncherError("The goal argument is required")
                result = {"description": "Evidence-first Harness composition", "messages": [{
                    "role": "user", "content": {"type": "text", "text": (
                        "Design a DeepSeek Harness configuration for this goal: " + goal +
                        ". Search the DSH Forge catalog, compare compatibility and risk, explain conflicts, "
                        "and save only a draft. Do not claim verification, install packages, or run code."
                    )},
                }]}
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except LauncherError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}}
        except Exception:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": "Internal MCP server error"}}


def serve_stdio(server: ForgeMCP, input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> None:
    for raw in input_stream:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            response = server.dispatch(message)
        if response is not None:
            output_stream.write(json.dumps(response, separators=(",", ":"), ensure_ascii=False) + "\n")
            output_stream.flush()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local DSH Forge MCP server over stdio")
    parser.add_argument("--state-dir")
    parser.add_argument("--scan-root", action="append", default=[])
    parser.add_argument("--catalog-dir")
    args = parser.parse_args(argv)
    launcher = Launcher(scan_roots=args.scan_root, state_root=args.state_dir)
    try:
        serve_stdio(ForgeMCP(launcher, CatalogIndex(args.catalog_dir)))
    finally:
        launcher.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
