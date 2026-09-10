#!/usr/bin/env python3
"""Self-contained read-mostly MCP server copied into a Forge Assistant cell.

This file deliberately has no imports from DSH Forge.  The launcher copies it
and a bounded catalog snapshot into the cell's disposable workspace.  Its only
write operation creates an inert JSON draft inside that same workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any


def result(value: Any, error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, indent=2, sort_keys=True)}],
        "structuredContent": value,
        "isError": error,
    }


class AssistantServer:
    def __init__(self, catalog_path: Path, draft_dir: Path):
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
            raise ValueError("catalog snapshot is invalid")
        self.entries = [entry for entry in payload["entries"] if isinstance(entry, dict)][:2048]
        self.versions = [entry for entry in payload.get("saved_versions", []) if isinstance(entry, dict)][:128]
        self.draft_dir = draft_dir
        self.draft_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catalog_search",
                "description": "Search offline DSH Forge package, plugin, and fork metadata. Evidence is not a verification claim.",
                "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
                    "query": {"type": "string", "maxLength": 500},
                    "type": {"enum": ["all", "package", "plugin", "fork"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                }},
                "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
            },
            {
                "name": "catalog_compare",
                "description": "Compare up to eight exact catalog identities, preserving compatibility and risk evidence.",
                "inputSchema": {"type": "object", "additionalProperties": False, "required": ["ids"], "properties": {
                    "ids": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string", "maxLength": 240}},
                }},
                "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
            },
            {
                "name": "configuration_save_draft",
                "description": "Write an inert configuration draft to the disposable Assistant workspace for later human review.",
                "inputSchema": {"type": "object", "additionalProperties": False, "required": ["name", "version_id", "selections"], "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 80},
                    "description": {"type": "string", "maxLength": 4000},
                    "version_id": {"type": "string", "pattern": "^version_[0-9a-f]{12}$"},
                    "selections": {"type": "array", "minItems": 1, "maxItems": 64, "items": {
                        "type": "object", "additionalProperties": False, "required": ["type", "id"],
                        "properties": {"type": {"enum": ["package", "plugin", "fork"]}, "id": {"type": "string", "maxLength": 240}},
                    }},
                }},
                "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
            },
        ]

    def call(self, name: str, args: Any) -> dict[str, Any]:
        values = args if isinstance(args, dict) else {}
        try:
            if name == "catalog_search":
                query = str(values.get("query") or "").strip().casefold()
                kind = str(values.get("type") or "all")
                limit = values.get("limit", 20)
                if kind not in {"all", "package", "plugin", "fork"} or type(limit) is not int or not 1 <= limit <= 50:
                    raise ValueError("invalid catalog filters")
                terms = query.split()
                rows = []
                for entry in self.entries:
                    if kind != "all" and entry.get("type") != kind:
                        continue
                    searchable = json.dumps(entry, sort_keys=True).casefold()
                    if terms and not all(term in searchable for term in terms):
                        continue
                    rows.append(entry)
                return result({"count": len(rows), "results": rows[:limit]})
            if name == "catalog_compare":
                identities = values.get("ids")
                if not isinstance(identities, list) or not 1 <= len(identities) <= 8:
                    raise ValueError("choose one to eight identities")
                wanted = {str(item) for item in identities}
                rows = [entry for entry in self.entries if entry.get("id") in wanted]
                missing = sorted(wanted - {str(entry.get("id")) for entry in rows})
                return result({"artifacts": rows, "missing": missing, "verification": "metadata-only"})
            if name == "configuration_save_draft":
                return result(self.save_draft(values))
            return result({"error": "unknown tool"}, True)
        except (OSError, ValueError) as error:
            return result({"error": str(error)}, True)

    def save_draft(self, values: dict[str, Any]) -> dict[str, Any]:
        name = str(values.get("name") or "").strip()
        description = str(values.get("description") or "").strip()
        version_id = str(values.get("version_id") or "")
        selections = values.get("selections")
        if not 1 <= len(name) <= 80 or len(description) > 4000:
            raise ValueError("draft name or description is invalid")
        if not re.fullmatch(r"version_[a-f0-9]{12}", version_id):
            raise ValueError("choose a saved Harness version")
        if version_id not in {str(item.get("id")) for item in self.versions}:
            raise ValueError("saved Harness version is not in this Assistant snapshot")
        if not isinstance(selections, list) or not 1 <= len(selections) <= 64:
            raise ValueError("choose one to 64 catalog artifacts")
        known = {(str(item.get("type")), str(item.get("id"))) for item in self.entries}
        normalized: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for selection in selections:
            if not isinstance(selection, dict):
                raise ValueError("selection must be an object")
            key = (str(selection.get("type") or ""), str(selection.get("id") or ""))
            if key not in known:
                raise ValueError("draft references an unknown catalog artifact")
            if key not in seen:
                normalized.append({"type": key[0], "id": key[1]})
                seen.add(key)
        now = int(time.time() * 1000)
        material = json.dumps([name, version_id, normalized, now], separators=(",", ":"), sort_keys=True).encode()
        identity = "config_" + hashlib.sha256(material).hexdigest()[:20]
        draft = {
            "schema": "dsh-forge.configuration-draft/v1",
            "id": identity,
            "name": name,
            "description": description,
            "version_id": version_id,
            "selections": normalized,
            "status": "draft",
            "source": "forge-assistant",
            "created_at": now,
            "execution_authorized": False,
        }
        destination = self.draft_dir / f"{identity}.json"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.draft_dir,
                prefix=".draft-", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                os.chmod(temporary, 0o600)
                handle.write(json.dumps(draft, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        return {**draft, "saved_to": str(destination)}

    def dispatch(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
        request_id = message.get("id")
        if request_id is None:
            return None
        method = message.get("method")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        if method == "initialize":
            requested = str(params.get("protocolVersion") or "")
            supported = {"2025-06-18", "2025-03-26", "2024-11-05"}
            protocol = requested if requested in supported else "2025-06-18"
            value = {
                "protocolVersion": protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "dsh-forge-assistant", "version": "0.1.0"},
                "instructions": (
                    "Search and compare DSH Forge catalog evidence to propose complementary Harness "
                    "configurations. Separate claims from metadata, explain compatibility and risk gaps, "
                    "and save only inert drafts. Never claim verification, install packages, or run code."
                ),
            }
        elif method == "ping":
            value = {}
        elif method == "tools/list":
            value = {"tools": self.tools()}
        elif method == "tools/call":
            value = self.call(str(params.get("name") or ""), params.get("arguments"))
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": value}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--draft-dir", type=Path, required=True)
    args = parser.parse_args()
    server = AssistantServer(args.catalog, args.draft_dir)
    for raw in sys.stdin:
        try:
            response = server.dispatch(json.loads(raw))
        except (json.JSONDecodeError, ValueError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
