# DSH Forge

DSH Forge is the open-source local launcher and catalog client for discovering,
inspecting, and running trusted DeepSeek Harness installations.

The public ecosystem crawler and catalog publisher live in the separate
`dsh-forge-registry` repository.

## Status

The first launcher and **Public Repos** interface is available as a local UI
prototype. Public Repos contains a dated snapshot of ten real community forks;
the original local launcher controls still use sample state. This is not yet a
process controller, installer, merger, or security sandbox.

## Open the UI

Python 3.9+ is sufficient to serve the app. There is no package installation or
build step, and no API key is needed.

```bash
git clone https://github.com/MichaelTheMay/dsh-forge.git
cd dsh-forge
python3 scripts/serve.py
```

Open <http://127.0.0.1:3090/> for Launch, or
<http://127.0.0.1:3090/#public-repos> for the separate browser. The server binds
only to loopback. Stop it with Ctrl+C. If port 3090 is occupied, choose another
port with `--port 3091`; the script does not stop existing processes.

See [Delta setup](docs/delta-setup.md) for remote access through an SSH tunnel.
To produce a single HTML file that can be downloaded and opened locally:

```bash
python3 scripts/package_preview.py dist/DSH_Forge_Public_Repos.html
```

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
