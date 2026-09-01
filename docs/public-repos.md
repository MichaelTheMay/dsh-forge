# Public Repos implementation boundary

The latest design request preserves the current launcher appearance and adds
Public Repos as a separate page. It explicitly selects ten upstream forks by
their own GitHub star counts. This changes the earlier no-star-ranking scope
for the seed; it does not add Forge-native stars, accounts, or social voting.

## Current implementation

`web/index.html` retains the supplied DC template and launcher layout. Its
catalog is replaced by the Public Repos page. The application logic is a
precompiled same-origin script in `web/launcher.js`; `web/support.js` consumes
that class without evaluating the inline design export as JavaScript.
The new page supports search, sort, filters, details, source links, and copying a
captured commit URL. The Plugins filter has an honest empty state.

The metadata snapshot is embedded from `data/public-repos.seed.json`, with the
ranked REST response retained in `data/github-forks.response.json`. Its source
is `GET /repos/deepseek-ai/deepseek-harness/forks?sort=stargazers&per_page=10&page=1`.
The seed preserves API tie order and does not silently remove archived entries.
Full source-network ancestry and a default-branch commit are fetched separately.
These requests are not an atomic view of GitHub.

The seed makes only a bounded claim about the first ten rows returned by the
sorted REST fork endpoint. It does not implement the recursive network crawl
described in the existing research notes. That belongs in `dsh-forge-registry`.

The `github_id`, `node_id`, canonical URL, and captured SHA are all retained.
`artifact_id: github:<numeric ID>` is the prototype's display-selection key;
the production adapter should follow the registry's opaque `node_id` identity
contract and preserve both identifiers. Never key solely by a mutable name.

## Connecting the ingester later

The collaborator owns the registry/ingester. Do not add an automatic scraper to
this launcher. `scripts/seed_catalog.py` is a manually invoked maintenance tool,
not a service and not an app-startup action.

`supplemental_entries` is empty. After the colleague supplies a real public
repository URL, it can be added separately with `seed_rank: null`; do not insert
it into the top ten unless it actually ranks there. Classify plugins based on
evidence, not just a repository name or the presence of some plugin code.

The future registry adapter should import a validated, signed, versioned
snapshot from the registry transactionally and use its local index. This
prototype does not implement that backend. Its unsigned status, absent source
analysis, unknown compatibility, and lack of security verification remain
visible.

Metadata is rendered as text. The embedding script rejects noncanonical source
URLs, checks identity and commit shape, and escapes script delimiters. It will
not treat a production signature as verified without a real verifier.

## Deferred actions

Download/open locally and integration into an existing version remain disabled.
No code from a Public Repos catalog entry is cloned, installed, built, or
executed by the browser. If a community checkout is already present in an
explicit scan root, the launcher can run only its captured CLI help probe in the
separate, pinned, networkless Apptainer sandbox. Passing does not promote it or
enable host launch. An isolated port or writable home alone is not a security
sandbox.

The intended later skill must pin revisions, assess compatibility, preserve
the original installation through a disposable clone/new profile, and expose
conflicts or unsupported changes. Sandbox checks must pass before promotion.
Do not promise automatic integration of every fork.

## Readiness

The Python server now supplies a loopback-only launcher alpha API. It discovers
only strong DSH signatures in configured roots, previews exact argv and
environment keys, and controls processes it started after verifying process
identity. The portable HTML export remains an explicitly disconnected preview
with no fake live cells.

Tests cover catalog behavior, metadata safety, session-protected API access,
scanner false positives, protected ports, process ownership, logs, and stop.
Browser layout testing and production runtime adapters remain release tasks.
This is not a complete production launcher. The bounded Apptainer probe is an
initial foreign-code test boundary, not a claim of complete hostile-code safety.
