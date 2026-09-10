# Installed local profiles

DSH Forge detects the DSH profiles a user already has on this machine and
surfaces them as one-click runs. This is deliberately a different path from the
signed-package boundary described in `docs/package-installation.md`: an
already-installed profile is host software the user chose earlier, so Forge
runs it honestly rather than pretending it is sandboxed.

## Detection

Forge reads `$DSH_HOME/profiles/*/package.json` and keeps only entries that
declare `dsh.profile.bundles` as a list of strings. Detection is metadata-only:

- No profile code, lifecycle script, or `dependencies` entry is imported or run.
- Symlinked profile directories and symlinked manifests are skipped rather than
  followed, so a link cannot pull an unexpected tree into the list.
- Directory names must match `[A-Za-z0-9_.-]{1,64}`, and at most 500 entries per
  home are considered.
- Unreadable homes, malformed JSON, and non-profile packages are skipped
  silently instead of failing the scan.

Homes are, in order, any `--dsh-home` arguments, the `DSH_FORGE_DSH_HOMES`
path list, and then `$DSH_HOME` (falling back to `~/.dsh`). Each detected
profile gets an ID derived from its home and directory name, so the same
profile name in two homes stays distinct and IDs survive a rescan.

Public profile records never include absolute host paths; those stay on
`real_`-prefixed fields the API does not serialize.

## Surfaces and what one-click means

The bundle list and profile name classify each profile into a surface:

| Surface    | Example bundles          | Behavior in Forge                       |
| ---------- | ------------------------ | --------------------------------------- |
| `web`      | `dsh-web-app`            | One-click, bound to `127.0.0.1` on a free port |
| `headless` | `dsh-headless`           | One-click, requires an explicit task     |
| `service`  | `dsh-sdk-app`, `dsh-acp-app` | CLI command only                     |
| `terminal` | anything else            | CLI command only                         |

Only `web` and `headless` are one-click, because those are the two surfaces
Forge can start without owning an interactive terminal. Everything else shows
its exact command instead of a button that would not work.

## Running a profile

One-click runs are confirmed on the same preview screen as sandboxed cells, and
that screen states the boundary plainly:

- The profile runs **directly on the host**, not inside Apptainer.
- The profile and its installed plugins can read the user account and any
  forwarded credential keys. The preview lists the key names; it never echoes a
  secret value.
- Forge passes an exact `argv` with no shell, records the process-start identity
  before managing the process, and refuses to manage it if that identity cannot
  be captured.

Web profiles bind loopback only and refuse protected ports, ports held by a
managed cell, and ports occupied by an unmanaged process — Forge never stops a
process it did not start. Headless profiles require a task of at most 20,000
characters. Profile cells can be stopped and restarted, but not cloned: their
home is the user's real profile directory, not a disposable copy.

The same runs are available from the CLI:

```bash
python3 -m dsh_forge profiles list
python3 -m dsh_forge profiles run profile_REPLACE_ME
python3 -m dsh_forge profiles run profile_REPLACE_ME --task "summarize the repo"
python3 -m dsh_forge profiles run profile_REPLACE_ME -- --verbose
```

`profiles run` executes in the current terminal, so it also covers the
`terminal` and `service` surfaces that have no one-click button. Use `--json`
for the stable `dsh-forge.cli/v1` envelope, and `--dsh-home` to add a home.

## What this path does not claim

`capabilities.local_profiles` reports `sandboxed: false` and
`discovery_executes_code: false`. Detecting a profile is not a security review
of the plugins inside it, and running one grants that code the user's own
access. Community artifacts that are *not* already installed keep the stricter
boundary: signed packages install through the sandbox, raw plugins hand over an
exact-version install command, and forks download a pinned archive.
