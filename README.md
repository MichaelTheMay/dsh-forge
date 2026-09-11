# DSH Forge

DSH Forge is the open-source local launcher and catalog client for discovering,
inspecting, and running trusted DeepSeek Harness installations.

The source-neutral crawler publishes a checksum-verified, compressed public
catalog from this repository. The local launcher consumes that feed without a
GitHub credential and keeps the imported search store on the user's machine.

## Status

The local fleet launcher, **Community** browser, saved configurations, and an
isolated **Assistant** surface are available.
The loopback sidecar discovers configured DSH trees without executing candidate
code and repeatedly starts
trusted local cells with automatic ports, separate writable homes, managed
workspaces, process groups, recent logs, clone/restart controls, and a live
inspector. It controls only processes whose PID and process-start identity it
recorded. The front page shows only DSH versions and profiles detected on the
user's machine; the disconnected demo does not substitute release cards.
Community contains a small offline snapshot of real plugins and forks. A
connected launcher can sync the continuously refreshed Forge feed, currently
covering thousands of plugins and tens of thousands of forks, into the local search store.
Forge adds an explainable, bounded hidden-gem research queue over that full
inventory. Only curator-reviewed, signed recipes appear as packages on the
front page; provisional generated packages remain hidden.

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

Browse the permanent disconnected demo at
<https://dsh-forge.vercel.app/>. It exposes the full application
shell and embedded community catalog. Local detection, installation, and launch
controls remain disabled until the loopback sidecar below is running.

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
# refresh the full Forge catalog once before opening the launcher
python3 scripts/serve.py --sync-catalog
# refresh the public plugin catalog once before opening the launcher
python3 scripts/serve.py --sync-plugins
```

The disconnected preview shows an empty local-version state rather than sample
releases. A live sidecar automatically finds Harness checkouts under
`~/dsh-versions` and also
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

## Installed local profiles

Forge auto-detects the DSH profiles already installed on this machine by
reading `$DSH_HOME/profiles/*/package.json`. Detection never runs profile code,
lifecycle scripts, or installed plugins, and it skips symlinked entries instead
of following them.

- `web` and `headless` profiles get a one-click run; `terminal` and `service`
  profiles show their exact command instead of a button that cannot work.
- One-click runs are confirmed on the standard preview screen, which states
  plainly that an existing profile runs **directly on the host rather than
  inside Apptainer** and lists the credential key names it will inherit.
- Web profiles bind loopback only and refuse protected, managed, or occupied
  ports. Headless profiles require an explicit task.
- Profile cells can be stopped and restarted but never cloned, because their
  home is the user's real profile directory rather than a disposable copy.
- Resolved paths stay on internal fields the API never serializes.

```bash
python3 -m dsh_forge profiles list
python3 -m dsh_forge profiles run profile_REPLACE_ME
```

This is intentionally a weaker boundary than the signed-package path, and
`capabilities.local_profiles` reports `sandboxed: false` rather than implying
otherwise. See [docs/local-profiles.md](docs/local-profiles.md).

## Catalog store and scale

The embedded snapshot in `web/launcher.js` stays the corpus for the
disconnected preview, which must remain a single self-contained file. A
connected sidecar reads from an imported FTS5-indexed SQLite store instead —
the only path that scales to a fork network with tens of thousands of entries.
Ten forks remain embedded for disconnected preview use.

```bash
python3 -m dsh_forge catalog sync
python3 -m dsh_forge catalog sync-plugins
python3 scripts/index_registry.py --output registry.json
python3 -m dsh_forge catalog import registry.json
python3 -m dsh_forge catalog import data/public-repos.seed.json   --package-feed data/package-catalog.seed.json
python3 -m dsh_forge catalog search "agent teams" --limit 10
python3 -m dsh_forge catalog search --type fork --sort stars
python3 -m dsh_forge research gems "project memory" --limit 25
```

Import is offline and inert. A snapshot produced by a registry Forge does not
run can be signed and verified against an explicit local trust root, reusing the
same DSSE/Ed25519 boundary as signed packages with a catalog-specific payload
type. Verification is the only thing that raises recorded trust: the snapshot's
own provenance is still stored verbatim and repeated in every search response,
so a verified envelope around an unsigned development seed reports both facts
rather than collapsing them. Builds are atomic, so a
failed import leaves the previous store intact. Page size, query length, and
paging depth are all bounded.

`catalog sync` downloads the current 3-4 MB compressed Forge registry from the
stable `catalog-latest` GitHub Release, checks the compressed and expanded
SHA-256 digests, bounds expansion to 128 MB, then atomically rebuilds the local
store. The feed is unsigned metadata and never authorizes installation.

`scripts/serve.py --sync-catalog` performs the same full-catalog refresh before
starting the desktop shell. `catalog sync-plugins` (or
`scripts/serve.py --sync-plugins`) remains the narrower
networked adapter for the public
[DSH Plugin Marketplace](https://github.com/w2112515/dsh-plugin-marketplace),
whose scanner publishes a daily full catalog. Forge bounds the download to 15
MB, requires credential-free HTTPS, rechecks redirects, validates entry identity
and the feed's logical SHA-256 digest, and imports metadata only. The upstream
digest detects corruption but is not a signature or a Forge security verdict.
The normalized SQLite store and hidden-gem ranker are source-neutral: future
adapters for other agentic development tools can emit the same artifact rows
without changing the browser, search path, or research policy. A scheduled
workflow refreshes the neutral registry and a bounded metadata-only review
queue daily, then publishes compressed feed assets. It cannot sign or publish
installable packages. Fork pagination includes a
coverage ledger. Forge says `complete` only when pagination ends and the
root and recursive child pages reconcile with unchanged reported counts. The
claim covers visible API results; inaccessible forks can still make it
incomplete.
See [Registry indexing](docs/registry-indexer.md) and
[Hidden-gem research and publication](docs/hidden-gem-pipeline.md).

When a store is imported the Community browser searches it instead of the
embedded snapshot, pages with a **Load more results** button, and names the
corpus in use on the result line. Without a sidecar — or with no store imported
— it reads the embedded snapshot exactly as before, so the portable preview is
unchanged. See [docs/catalog-store.md](docs/catalog-store.md).

## Community browsers

- Raw plugins with a verified npm identity hand over an exact-version
  `dsh plugin add` command targeting a detected local profile; other entries
  remain browse-only. Forks offer a source archive pinned to the captured commit.
  Forge copies or downloads; it never extracts or executes community code.
- Browse Plugins and Forks through stable, shareable routes. The package
  composition and installation contract remains available through the CLI, but
  provisional package recipes are not promoted in the primary browser.
- Search names, authors, descriptions, capabilities, and taxonomy labels.
- Sort by static-review recommendation, GitHub stars, most recent push, or name.
- See an H-rank, reproducible score, positive signals, and evidence gaps for the
  top 250 metadata candidates while retaining the entire imported inventory.
- Inspect source links, exact package versions and integrity, captured commit
  references, compatibility notes, reported licenses, risk, and provenance.
- Browse seven evidence-ranked plugin records and ten captured forks without
  network access, or explicitly sync the public marketplace into the connected
  store for full-catalog search. Package publication stays disabled until a
  research process proposes a coherent combination and a curator reviews and
  signs its exact components. Certified local recipes then appear on the front
  page with a sandbox-gated **Verify, test & install** action.

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

## Configurations and Forge Assistant

Any catalog page can save a configuration against a stable local Harness
version. Locally trusted signed packages can become runnable after their exact
profile passes the install transaction; raw plugin and fork selections remain
inert drafts. Configurations can be listed and run through the UI or the
versioned CLI. See [Saved Harness configurations](docs/saved-configurations.md).

Forge also provides a dependency-free stdio [MCP server](docs/mcp-server.md)
for catalog search, saved-version inspection, configuration listing, and draft
creation. It intentionally exposes no install or execution tool.

The second launcher tab starts an [embedded Forge Assistant](docs/forge-assistant.md)
as a disposable DSH Web cell. Its local MCP tools help search and compare
complementary package, plugin, and fork metadata, while all trust, install,
promotion, and run decisions remain explicit launcher or CLI actions.

## Development

Feature and fix pull requests target `main`. See the
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
