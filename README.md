# DSH Forge

DSH Forge is the open-source local launcher and catalog client for discovering,
inspecting, and running trusted DeepSeek Harness installations.

The public ecosystem crawler and catalog publisher live in the separate
`dsh-forge-registry` repository.

## Status

The first local launcher alpha and **Public Repos** interface are available.
The loopback sidecar discovers configured DSH trees without executing candidate
code, previews an exact launch, starts trusted local trees, and controls only
processes whose PID and process-start identity it recorded. Public Repos contains
a dated metadata snapshot of ten real community forks.

This is state isolation, not a hostile-code security sandbox. Public repository
download, installation, merging, and execution remain disabled.

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

The alpha supports the current `dsh web` surface and one-shot `dsh headless`
tasks. It recognizes the current upstream `apps/cli/lib/bin.js` build artifact
as well as older compatible CLI layouts. Because upstream is still a developer
preview, the exact command is always shown for confirmation before launch.

Open <http://127.0.0.1:3090/> for Launch, or
<http://127.0.0.1:3090/#public-repos> for the separate browser. The server binds
only to loopback. Stop it with Ctrl+C. If port 3090 is occupied, choose another
port with `--port 3091`; the script does not stop existing processes.

See [Delta setup](docs/delta-setup.md) for remote access through an SSH tunnel.
To produce a single HTML file that can be downloaded and opened locally as a
disconnected, non-runnable preview:

```bash
python3 scripts/package_preview.py dist/DSH_Forge_Launcher_Preview.html
```

## Launcher safety boundary

- Discovery is bounded to configured roots plus a `dsh` executable on `PATH`.
- Scanning reads recognized artifacts, package metadata, and Git identity; it
  never runs repository code or package scripts.
- Trees whose Git remote is not the canonical upstream are view-only until the
  container backend is available. The later import/integration skill will
  validate, sandbox-test, and explicitly promote compatible forks before this
  launcher may run them.
- Ports 3080 and 3090 are protected. An unmanaged occupant is reported and is
  never killed or replaced.
- A writable DSH home has one live writer. Fresh and sanitized-clone homes are
  launcher-managed alternatives.
- Mutation APIs require a loopback Host, same-origin request, and an HttpOnly
  session cookie. Credential presence is shown by key only; values are not
  returned to the page or intentionally logged.
- Loader readiness is honestly reported as `not observed` until a supported
  runtime adapter exists.

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

No frontend dependencies need to be installed. The supplied export runtime is
preserved in `web/support.js`; pinned React 18.3.1 files and their MIT license
are included in `web/vendor/`. Google Fonts is optional; system fonts are used
when it is unavailable.

```bash
python3 scripts/embed_catalog.py
node --test tests/catalog.test.cjs
python3 -m unittest discover -s tests -p 'test_*.py'
```

Node 18+ is required only for the JavaScript tests; CI uses Node 22.
To deliberately refresh the manual seed, run `python3 scripts/seed_catalog.py`
and then the development checks above. This bounded maintenance script never
runs on app startup and is not the registry crawler. An optional `GITHUB_TOKEN`
may be supplied in the environment; never embed credentials in the frontend.

Current UI scope, the registry connection contract, and deferred execution
features are documented in [Public Repos implementation](docs/public-repos.md).
The existing research notes remain in `docs/research/`.
