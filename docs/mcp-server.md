# DSH Forge MCP server

Forge exposes its already-ingested catalog, saved Harness versions, and saved
configurations through a dependency-free MCP server over stdio:

```bash
cd ~/dsh-forge
python3 -m dsh_forge.mcp_server
```

Configure an MCP client to launch that command from the repository checkout.
The server writes newline-delimited JSON-RPC messages only to stdout, as
required by the MCP stdio transport. It adds no runtime dependency and supports
Python 3.9+, matching the launcher.

Available tools:

- `catalog_search`: bounded search across the cached package, plugin, and fork
  snapshot.
- `versions_list`: saved local Harness identities and readiness.
- `configurations_list`: saved configurations with fail-closed run readiness.
- `configuration_save_draft`: create an inert draft for later human review.

Resources expose the same catalog, version, and configuration views to clients
that support MCP resources. The `build-harness` prompt asks a client to compare
compatibility and risk and save only a draft.

There is deliberately no MCP tool for trust-root changes, acquisition,
installation, profile promotion, or cell execution. Those stay behind the
local UI and CLI review boundaries. The server reads only bounded local catalog
files and does not turn directory inclusion or model output into a verification
claim.

Forge currently implements the connection-level initialization lifecycle through
MCP `2025-06-18`; it does not advertise the incompatible per-request negotiation
introduced in `2026-07-28`. Protocol references: [2025-06-18 lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)
and [stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).
