# Community browsers implementation boundary

The Community page contains three deliberately separate browsers: Plugins,
Forks, and Packages. Plugins starts with a bounded, manually reviewed seed;
Forks retains the ten-row upstream snapshot; Packages is a real route and empty
collection. The signed metadata schema and offline composer now exist, but no
publication endpoint or acquisition path is connected. It does not add
Forge-native stars, accounts, publishing, installation, or social voting.

## Current implementation

`web/index.html` retains the supplied DC template and launcher layout. Its
catalog is presented as the Community page. The application logic is a
precompiled same-origin script in `web/launcher.js`; `web/support.js` consumes
that class without evaluating the inline design export as JavaScript.
The page supports search, sort, type routing, details, source/package links, and
copying a captured commit URL. Stable routes are `#plugins`, `#forks`, and
`#packages`; the old `#public-repos` link continues to resolve to Forks.

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

Six plugin records are stored in `supplemental_entries`. Each record has an
exact npm or MCPB version, registry integrity, an immutable repository commit,
taxonomy labels, compatibility notes, a static-review rank, and explicit
unexecuted verification state. The ranking considers capability evidence,
compatibility, maintenance, reported license, and security risk. Stars are
shown but do not affect the recommendation order. Presence of manifests,
tests, or workflows is evidence that files exist—not evidence that tests pass.

`package_entries` must remain empty in this release. The Packages browser is
for future user-published, multi-plugin bundles rather than individual npm or
MCPB artifacts. `scripts/embed_catalog.py` rejects non-empty package data until
uploader authorization, moderation, signed registry metadata, trust-root
distribution, and immutable blob storage exist. The local
`dsh-forge.package/v1` schema, DSSE/Ed25519 signing path, trust root, and offline
composer are documented in [Signed packages](signed-packages.md).

## Connecting the ingester later

The collaborator owns the registry/ingester. Do not add an automatic scraper to
this launcher. `scripts/seed_catalog.py` is a manually invoked maintenance tool,
not a service and not an app-startup action.

Future plugin records remain separate from the top-ten fork ranking with
`seed_rank: null`. Classify plugins using manifest and provenance evidence, not
only a repository name, topic, store listing, or the presence of plugin-like
code. A fork must not enter the ranked ten unless it actually ranks there.

The future registry adapter should import a validated, signed, versioned
snapshot from the registry transactionally and use its local index. This
prototype does not implement that backend. Its unsigned status, absent source
analysis, unknown compatibility, and lack of security verification remain
visible.

Metadata is rendered as text. The embedding script rejects noncanonical source
URLs, checks identity and commit shape, and escapes script delimiters. It will
not treat a production signature as verified without a real verifier.

## Deferred actions

Browser-based composition, upload, download, and integration into an existing
version remain disabled. Offline metadata composition and signature verification
are available through the CLI. No code from a Community catalog entry is cloned,
installed, built, or executed by either path. If a community checkout is already present in an
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
They also enforce the three browser routes, exact plugin package pins, empty
package collection, and separation between manifest review and execution.
Browser layout testing and production runtime adapters remain release tasks.
This is not a complete production launcher. The bounded Apptainer probe is an
initial foreign-code test boundary, not a claim of complete hostile-code safety.
