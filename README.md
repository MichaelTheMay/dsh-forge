# DSH Forge

DSH Forge is the open-source local launcher and catalog client for discovering,
inspecting, and running trusted DeepSeek Harness installations.

The public ecosystem crawler and catalog publisher live in the separate
`dsh-forge-registry` repository.

## Status

The first local fleet launcher and **Public Repos** interface are available.
The loopback sidecar discovers configured DSH trees without executing candidate
code, pins the two current official release installations, and repeatedly starts
trusted local cells with automatic ports, separate writable homes, managed
workspaces, process groups, recent logs, clone/restart controls, and a live
inspector. It controls only processes whose PID and process-start identity it
recorded. Public Repos contains a dated metadata snapshot of ten real community
forks.

Every runnable official or personal cell now requires the **fail-closed
Apptainer backend**. The captured Harness source is read-only; each cell gets a
unique writable home and workspace; launcher secrets are excluded; and accepted
CPU, RAM, PID, and wall-time controls are recorded with the cell. A sandbox
failure never falls back to a direct Harness host process. Web cells explicitly
share the host network so their loopback port is reachable; headless cells
default to a network namespace with no network. Apptainer still shares the host
kernel and is not described as a virtual machine.

Already-present community checkouts remain limited to the separate bounded CLI
capability probe. They are not promoted into complete cells. Public repository
acquisition remains disabled.

## Open the UI

Python 3.9+ is sufficient to serve the app. There is no package installation or
build step, and no API key is needed.

From an existing checkout:

```bash
cd ~/dsh-forge
python3 scripts/serve.py
```

The launcher automatically detects `dsh` on `PATH`. Register one or more source
roots at startup when needed:

```bash
python3 scripts/serve.py --scan-root ~/src/deepseek-harness
```

For the two exact official pins shown in the Versions rail, see
[Fleet sandbox preview](docs/fleet-sandbox-preview.md). When both built source
trees are registered, each **Launch cell** click selects a free loopback port and
creates a separate managed home and workspace.

The alpha supports the current `dsh web` surface and one-shot `dsh headless`
tasks. It recognizes the current upstream `apps/cli/lib/bin.js` build artifact
as well as older compatible CLI layouts. Because upstream is still a developer
preview, the exact command is always shown for confirmation before launch.

The same persistent lifecycle is now scriptable through a versioned CLI. Start
with capability discovery and local version detection:

```bash
python3 -m dsh_forge --scan-root ~/src/deepseek-harness doctor
python3 -m dsh_forge --scan-root ~/src/deepseek-harness versions list
python3 -m dsh_forge cells list
```

See [Local-cell CLI and lifecycle contract](docs/local-cell-cli.md) for
start/stop/restart/clone, live logs, artifacts, stable JSON output, and the
required Apptainer configuration. Prompt delivery and normalized session
transcripts remain fail-closed capabilities for their follow-up adapters.

Open <http://127.0.0.1:3090/> for Launch, or
<http://127.0.0.1:3090/#public-repos> for the separate browser. The server binds
only to loopback. Stop it with Ctrl+C. If port 3090 is occupied, choose another
port with `--port 3091`; the script does not stop existing processes.

See [Delta setup](docs/delta-setup.md) for remote access through an SSH tunnel.
See [Apptainer cell runner](docs/apptainer-sandbox.md) to pin a SIF, enable
complete local cells, and retain the compact **Test** action for detected
community trees.
To produce a single HTML file that can be downloaded and opened locally as a
disconnected, non-runnable preview:

```bash
python3 scripts/package_preview.py dist/DSH_Forge_Launcher_Preview.html
```

## Launcher safety boundary

- Discovery is bounded to configured roots plus a `dsh` executable on `PATH`.
- Scanning reads recognized artifacts, package metadata, and Git identity; it
  never runs repository code or package scripts.
- Trees whose Git remote is not the canonical upstream can only run a bounded
  CLI help probe in the configured networkless Apptainer sandbox. They remain
  ineligible for complete-cell execution even after passing. The later
  import/integration skill must validate and explicitly promote compatible
  forks through a separate policy.
- Every complete local cell requires the pinned Apptainer runner. There is no
  direct Harness host-process fallback.
- Ports 3080 and 3090 are protected. An unmanaged occupant is reported and is
  never killed or replaced.
- Host DSH homes and writable host workspaces are never mounted into a cell.
  Fresh and sanitized-clone state always lives under a unique cell directory.
- One-click fleet launches allocate ports while holding the launcher mutation
  lock and the persistent registry uses an atomic, versioned write guarded by a
  cross-process file lock. Clone Session preserves session state but removes
  secret-like files, locks, sockets, PIDs, caches, symlinks, and heavyweight
  workspace dependencies.
- Mutation APIs require a loopback Host, same-origin request, and an HttpOnly
  session cookie. Credential presence is shown by key only; values are not
  returned to the page or intentionally logged.
- Loader readiness is honestly reported as `not observed` until a supported
  runtime adapter exists.
- The fleet's working/idle state is derived from process identity and recent log
  activity. Blocked is reserved for a future explicit runtime signal.
- Sandbox tests require a clean Git revision and a read-only SIF matching an
  explicit SHA-256 pin. The source is mounted read-only; home and workspace are
  disposable; launcher secrets and network access are excluded.

## Public Repos

- Search repository names, authors, descriptions, and topics.
- Sort by GitHub stars, most recent push, or name.
- Inspect source links, captured commit references, licenses reported by GitHub,
  and collection provenance.
- Browse the seed without GitHub access. Plugins correctly shows an empty state
  until actual plugin records arrive.

The seed comes from the upstream [GitHub forks endpoint, sorted by stars](https://api.github.com/repos/deepseek-ai/deepseek-harness/forks?sort=stargazers&per_page=10&page=1).
It is a **one-time, unsigned development snapshot**, not a complete recursive
fork-network crawl or a production-verified catalog. GitHub stars indicate
popularity, not compatibility or security. No fork source code is included or
executed. The browser never contacts GitHub itself.

## Development

All feature and fix pull requests target `development`; `main` is reserved for
tested release promotions. See the
[development and release workflow](docs/development-workflow.md) for the branch
policy, required checks, and tagged release process.

No frontend dependencies need to be installed. The supplied export runtime
remains in `web/support.js` with a precompiled-logic adapter, while the launcher
logic is precompiled in `web/launcher.js` so the loopback server can retain a
CSP that disallows string evaluation. Pinned React 18.3.1 files and their MIT
license are included in `web/vendor/`. Google Fonts is optional; system fonts
are used when unavailable.

```bash
python3 scripts/embed_catalog.py
node --test tests/catalog.test.cjs
python3 -m unittest discover -s tests -p 'test_*.py'
```

Node 18+ is required only for the DSH Forge JavaScript tests; CI uses Node 22.
Launching the current upstream DeepSeek Harness additionally requires the
upstream-supported Node `^22.19.0` or `>=24.0.0` runtime.
To deliberately refresh the manual seed, run `python3 scripts/seed_catalog.py`
and then the development checks above. This bounded maintenance script never
runs on app startup and is not the registry crawler. An optional `GITHUB_TOKEN`
may be supplied in the environment; never embed credentials in the frontend.

Current UI scope, the registry connection contract, and deferred execution
features are documented in [Public Repos implementation](docs/public-repos.md).
The existing research notes remain in `docs/research/`.
