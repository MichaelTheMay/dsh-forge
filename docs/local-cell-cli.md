# Local-cell CLI and lifecycle contract

This contract is the shared automation boundary for the launcher UI and the
fail-closed Apptainer cell runner. It provides durable cell identity, recovery,
lifecycle events, lineage, logs, and artifact discovery. Community promotion
remains a separate policy.

## Current boundary

The CLI can repeatedly start official or personal local Harness installations
inside a pinned Apptainer SIF. These cells use unique IDs, process groups,
managed homes, managed workspaces, and automatic web ports. Registry state is written
atomically to `~/.local/state/dsh-forge/cells.json`, guarded by a cross-process
file lock, and recovered by PID plus process-start identity after a launcher or
CLI restart.

The source checkout is mounted read-only, launcher secrets are excluded, and
the host home and current working directory are hidden. If the image pin,
capability probe, resource flags, executable digest, mounts, or process creation
fails, launch stops with no direct Harness host fallback. Foreign/community
trees remain blocked from complete-cell launch pending promotion.

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

Failures use the same envelope on standard error and a nonzero exit code.
Unavailable prompt/session transports return `capability_unavailable`, while an
unavailable or failed Apptainer runner returns `launcher_error` before spawn.

## Lifecycle commands

First copy a tree ID from `versions list`. A web cell receives an automatic
loopback port; a headless cell requires a task:

```bash
python3 -m dsh_forge --scan-root ~/src/deepseek-harness cells start \
  --tree tree_0123456789ab --surface web

python3 -m dsh_forge --scan-root ~/src/deepseek-harness cells start \
  --tree tree_0123456789ab --surface headless --task "inspect this checkout"
```

The remaining implemented operations are:

```bash
python3 -m dsh_forge cells inspect CELL_ID
python3 -m dsh_forge cells logs CELL_ID --follow
python3 -m dsh_forge cells open-url CELL_ID
python3 -m dsh_forge cells artifacts CELL_ID
python3 -m dsh_forge cells clone CELL_ID
python3 -m dsh_forge cells restart CELL_ID
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

- `persistent_registry`, `parallel_local_cells`, `sandboxed_cells`,
  `runtime_logs`, and managed `artifacts` are available when the runner probe
  passes;
- `prompt_delivery` and `session_transcript` are unavailable.

## Apptainer cell acceptance boundary

The runner preserves the CLI envelope and applies this boundary:

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
- integration tests run a complete fake Harness session through the supervised
  Apptainer command boundary, not only `--help`.

Loom testing on DeltaAI should verify the exact local SIF and system policy
before any community promotion. Prompt transport, adaptive scheduling,
worktree/file claims, fleet panels, and normalized session archive/export can
then be added as independent adapters against this lifecycle contract.
