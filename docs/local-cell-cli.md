# Local-cell CLI and lifecycle contract

This contract is the automation boundary between the launcher UI and the next
Apptainer cell runner. It provides durable cell identity, recovery, lifecycle
events, lineage, logs, and artifact discovery before community code is allowed
to execute as a complete session.

## Current boundary

The CLI can repeatedly start **trusted local** Harness installations as host
process previews. These cells use unique IDs, process groups, managed homes,
managed workspaces, and automatic web ports. Registry state is written
atomically to `~/.local/state/dsh-forge/cells.json`, guarded by a cross-process
file lock, and recovered by PID plus process-start identity after a launcher or
CLI restart.

This is not yet the requested hostile-code sandbox. Commands that create a
process require `--allow-host-preview`, foreign/community trees remain blocked,
and there is no fallback from a failed sandbox to the host. The follow-up cell
runner will replace this preview backend with a complete, fail-closed Apptainer
session boundary.

## Machine contract

Run the CLI from the repository root:

```bash
python3 -m dsh_forge --scan-root ~/src/deepseek-harness doctor
python3 -m dsh_forge --scan-root ~/src/deepseek-harness versions list
python3 -m dsh_forge cells list
```

Put global options before `doctor`, `versions`, or `cells`. Add `--json` for a
compact deterministic envelope:

```json
{"api_version":"dsh-forge.cli/v1","ok":true,"command":"cells.list","data":{"cells":[],"registry":{"schema_version":1}}}
```

Failures use the same envelope on standard error and a nonzero exit code. In
particular, unavailable transports return `capability_unavailable`, and an
unacknowledged preview launch returns `host_preview_consent_required`.

## Lifecycle commands

First copy a tree ID from `versions list`. A web cell receives an automatic
loopback port; a headless cell requires a task:

```bash
python3 -m dsh_forge --scan-root ~/src/deepseek-harness cells start \
  --tree tree_0123456789ab --surface web --allow-host-preview

python3 -m dsh_forge --scan-root ~/src/deepseek-harness cells start \
  --tree tree_0123456789ab --surface headless --task "inspect this checkout" \
  --allow-host-preview
```

The remaining implemented operations are:

```bash
python3 -m dsh_forge cells inspect CELL_ID
python3 -m dsh_forge cells logs CELL_ID --follow
python3 -m dsh_forge cells open-url CELL_ID
python3 -m dsh_forge cells artifacts CELL_ID
python3 -m dsh_forge cells clone CELL_ID --allow-host-preview
python3 -m dsh_forge cells restart CELL_ID --allow-host-preview
python3 -m dsh_forge cells stop CELL_ID
```

Clone and restart create a new cell ID and record `parent_cell_id` plus the
lineage action. They copy managed state through the existing sanitized clone
policy, which excludes secret-like files, locks, sockets, PIDs, symlinks,
caches, and heavyweight workspace dependencies.

## Deliberately unavailable

`cells prompt` and `cells session-log` exist so automation can detect the
contract without guessing. They currently fail closed. Process stdout/stderr is
available through `cells logs`, but it is not mislabeled as a normalized
Harness session transcript. Live prompt delivery needs a versioned runtime
adapter rather than writing to stdin: launched cells intentionally have stdin
closed, and resume/session behavior differs across current Harness versions.

`doctor` is the source of truth for these capability flags:

- `persistent_registry`, `parallel_local_cells`, `runtime_logs`, and managed
  `artifacts` are available;
- `sandboxed_cells`, `prompt_delivery`, and `session_transcript` are unavailable.

## Next PR: real Apptainer cells

The next backend must preserve this CLI envelope while changing process
creation to a pinned Apptainer image. Its acceptance boundary is:

- every complete cell runs in Apptainer, including trusted local versions;
- failure to create or probe the sandbox aborts the launch with no host fallback;
- source is read-only and each cell gets a unique writable home and workspace;
- network, secrets, GPU exposure, CPU, RAM, PID, and wall-time policy are
  explicit per cell and reported from enforcement evidence;
- the registry records container identity in addition to the verified host-side
  Apptainer process identity;
- stop/restart/clone remain idempotent across CLI and launcher restarts;
- concurrent launches cannot reuse a port, home, workspace, or active writer
  lease;
- integration tests run a complete fake Harness session, not only `--help`.

Only after that boundary passes should Loom testing begin for complete community
sessions. Prompt transport, adaptive scheduling, worktree/file claims, fleet
panels, and normalized session archive/export can then be added as independent
adapters against this lifecycle contract.
