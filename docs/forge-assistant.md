# Embedded Forge Assistant

The **Assistant** tab starts a disposable DeepSeek Harness inside the same
fail-closed Apptainer cell runner used by the launcher. It is a separate local
Harness surface, not a remote hosted agent.

1. Save a launch-ready local Harness version.
2. Configure and pass the pinned Apptainer capability probe.
3. Open **Assistant**, select the version, and choose **Start isolated
   assistant**.
4. Forge creates a fresh home and managed workspace, copies a bounded
   metadata-only catalog snapshot, and attaches a local stdio MCP server through
   a temporary Cordis patch.
5. The authenticated DSH Web URL appears in the embedded panel. If the Harness
   sends an anti-framing header, open the same authenticated URL in a separate
   local tab instead; the sandbox and MCP boundary are unchanged.

The embedded MCP tools search and compare exact catalog identities and can
write only inert draft JSON files inside that disposable cell workspace. They
cannot access the host Forge registry, change trust roots, acquire packages,
install code, run configurations, or promote profiles. A human must review and
recreate an accepted draft through the Forge configuration UI or CLI.

The selected Harness must include `@deepseek-ai/dsh-mcp-client`; DSH's current
bridge exposes MCP tools as `mcp__<serverName>__<tool>`. Resources and prompts
from the full Forge MCP server are useful to other MCP clients but are not
required by the embedded DSH tool bridge. See the pinned upstream
[DSH MCP client documentation](https://github.com/deepseek-ai/deepseek-harness/blob/b2e3b2a0125854567a4a5fcba75782e42fe84901/packages/mcp/mcp-client/README.md).

On a remote compute node, both the Forge sidecar port and the Assistant cell's
allocated loopback port must be forwarded to the viewing machine. The Launcher
shows that allocated port after the cell starts. Never publish either service
on `0.0.0.0` merely to make it shareable; a public product URL requires a
separate authenticated hosting architecture.
