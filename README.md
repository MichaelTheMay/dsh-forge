# DSH Forge

DSH Forge is the open-source local launcher and catalog client for discovering,
inspecting, and running trusted DeepSeek Harness installations.

The public ecosystem crawler and catalog publisher live in the separate
`dsh-forge-registry` repository.

## Status

The first local fleet launcher and **Community** interface are available.
The loopback sidecar discovers configured DSH trees without executing candidate
code, pins the two current official release installations, and repeatedly starts
trusted local cells with automatic ports, separate writable homes, managed
workspaces, process groups, recent logs, clone/restart controls, and a live
inspector. It controls only processes whose PID and process-start identity it
recorded. Community contains a dated metadata snapshot of ten real community
forks, seven evidence-ranked plugin candidates, and three curated package
recipes. Packages are the primary browser; every package has a stable detail
route and schema-defined metadata, but remains unsigned and non-executable.

Every runnable official or personal cell now requires the **fail-closed
Apptainer backend**. The captured Harness source is read-only; each cell gets a
unique writable home and workspace; launcher secrets are excluded; and the
accepted resource scope is recorded with the cell. Apptainer cgroups provide
per-cell CPU/RAM/PID limits when supported; DeltaAI instead supplies a shared
Slurm allocation with a per-cell wall-time supervisor. A sandbox
failure never falls back to a direct Harness host process. Web cells explicitly
share the host network so their loopback port is reachable; headless cells
default to a network namespace with no network. Apptainer still shares the host
kernel and is not described as a virtual machine.

Already-present community checkouts remain limited to the separate bounded CLI
capability probe, and that probe requires per-cell cgroup controls. They are not
promoted into complete cells. Public repository acquisition remains disabled.

## Open the UI

Python 3.9+ is sufficient to serve the app. There is no frontend dependency
installation or build step, and no API key is needed to browse local metadata.

From an existing checkout:

```bash
cd ~/dsh-forge
python3 scripts/serve.py
```

The launcher automatically detects `dsh` on `PATH`. Use **+ Add version** in
the Versions rail to save a checkout directory across launcher restarts, or
register one or more source roots at startup when needed:

```bash
python3 scripts/serve.py --scan-root ~/src/deepseek-harness
```

The disconnected preview shows two immutable official references. A live
sidecar automatically finds Harness checkouts under `~/dsh-versions` and also
lets the user add any other local directory once. Each **Launch** click uses the
saved safe preset, selects a free loopback port, and creates a separate managed
home and workspace. **Forget** removes only the saved path and never deletes or
changes the checkout. See
[Fleet sandbox preview](docs/fleet-sandbox-preview.md).

The alpha supports the current `dsh web` surface and one-shot `dsh headless`
tasks. It recognizes the current upstream `apps/cli/lib/bin.js` build artifact
as well as older compatible CLI layouts. Because upstream is still a developer
preview, the exact command is always shown for confirmation before launch.

The same persistent lifecycle is now scriptable through a versioned CLI. Start
with capability discovery and local version detection:

```bash
python3 -m dsh_forge --scan-root ~/src/deepseek-harness doctor
python3 -m dsh_forge versions add ~/src/deepseek-harness
python3 -m dsh_forge versions list
python3 -m dsh_forge versions configure VERSION_ID --gpu none --no-open-browser
python3 -m dsh_forge cells list
```

See [Local-cell CLI and lifecycle contract](docs/local-cell-cli.md) for
start/stop/restart/clone, live logs, artifacts, stable JSON output, and the
required Apptainer configuration. Prompt delivery and normalized session
transcripts remain fail-closed capabilities for their follow-up adapters.

Open <http://127.0.0.1:3090/> for Launch, or
<http://127.0.0.1:3090/#plugins>, <http://127.0.0.1:3090/#forks>, or
<http://127.0.0.1:3090/#packages> for the separate browsers. The old
`#public-repos` route remains a Forks alias. The server binds
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

## Community browsers

- Browse Packages, Plugins, and Forks through stable, shareable routes.
- Search names, authors, descriptions, capabilities, and taxonomy labels.
- Sort by static-review recommendation, GitHub stars, most recent push, or name.
- Inspect source links, exact package versions and integrity, captured commit
  references, compatibility notes, reported licenses, risk, and provenance.
- Browse three metadata-only package recipes, seven evidence-ranked plugin
  records, and ten captured forks without GitHub or registry access. Package
  detail pages expose exact component versions, integrity pins, source commits,
  compatibility, provenance, license, and risk. Browser acquisition stays
  disabled until a package has a trusted DSSE envelope.

The seed comes from the upstream [GitHub forks endpoint, sorted by stars](https://api.github.com/repos/deepseek-ai/deepseek-harness/forks?sort=stargazers&per_page=10&page=1).
It is a **one-time, unsigned development snapshot**, not a complete recursive
fork-network crawl or a production-verified catalog. GitHub stars indicate
popularity, not compatibility or security. Plugin recommendation order uses
static evidence, compatibility, maintenance, license, and risk—not stars. No
community source code is included or executed. The browser never contacts
GitHub, npm, or the community catalog itself.

## Signed plugin packages

Forge now defines a versioned, offline multi-plugin package contract. The CLI
can compose deterministic manifests from exact plugin versions, artifact
integrity, repository commits, permissions, relations, compatibility, and load
order; sign their canonical bytes with Ed25519 in a DSSE envelope; create an
explicit local trust root; and verify signature threshold, expiry, key identity,
schema, pins, conflicts, and composition digest.

```bash
python3 -m dsh_forge packages compose \
  --spec examples/package-spec.v1.json \
  --output /tmp/review-stack.manifest.json
```

The composer and package-catalog ingester are metadata-only and make no network
requests. The ingester validates the source ledger and emits deterministic
package pages from exact plugin metadata:

```bash
python3 scripts/ingest_package_catalog.py --check
```

Successful verification explicitly returns `execution_authorized: false`. A separate CLI
boundary can verify that signed envelope, download its exact artifacts over
credential-free HTTPS, recompute their signed integrity, and place immutable
bytes in a content-addressed quarantine:

```bash
python3 -m dsh_forge packages acquire \
  --bundle /tmp/review-stack.dsse.json \
  --trust-root /tmp/dsh-forge-dev-root.json
```

Acquisition does not extract archives, install dependencies, alter a Harness
profile, or execute code. Both `installation_authorized` and
`execution_authorized` remain false. See [Signed packages](docs/signed-packages.md)
and [Quarantine acquisition](docs/quarantine-acquisition.md) for the trust model
and enforced limits. See [Package catalog](docs/package-catalog.md) for the
metadata contract, directory-ingestion boundary, dedicated pages, and proposed
hosted-registry API. The separate
[AgentTeams sandbox evaluation](docs/agentteams-sandbox-evaluation.md) pins the
first candidate and installs it only inside a disposable Apptainer profile.

The package page can now connect those boundaries for a locally configured
signed recipe. Select a saved, launch-ready Harness version and choose **Verify,
test & install**. The launcher acquires exact bytes, rejects unsafe npm archives,
installs without network or lifecycle scripts into a disposable profile, checks
composition and DeepSeek Web startup inside Apptainer, and atomically promotes a
versioned profile pointer. A failed transaction leaves the current profile
unchanged and retains bounded evidence. See
[Sandbox package installation](docs/package-installation.md).

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
features are documented in [Community browsers implementation](docs/public-repos.md).
The existing research notes remain in `docs/research/`.
