# Community browsers implementation boundary

The Community page exposes two primary browsers: Plugins and Forks. Plugins has
a bounded, manually reviewed seven-row offline seed; Forks retains the ten-row
upstream snapshot. A connected launcher can replace either artifact type with
every entry from an imported external catalog; types absent from the import keep
their offline rows. Provisional package recipes and the featured strip are not
shown as recommendations. The signed package schema, offline
composer, and separate CLI quarantine acquirer remain available without
claiming that the current recipes are genuinely useful bundles.

## Current implementation

`web/index.html` retains the supplied DC template and launcher layout. Its
catalog is presented as the Community page. The application logic is a
precompiled same-origin script in `web/launcher.js`; `web/support.js` consumes
that class without evaluating the inline design export as JavaScript.
The page supports search, sort, type routing, details, source/package links, and
copying a captured commit URL. Stable primary routes are `#plugins` and
`#forks`; the old `#public-repos` link continues to resolve to Forks. Existing
`#packages/<slug>` routes remain compatible but are not linked from the primary
browser.

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

Seven plugin records are stored in `supplemental_entries`. Each record has an
exact npm or MCPB version, registry integrity, an immutable repository commit,
taxonomy labels, compatibility notes, a static-review rank, and explicit
unexecuted verification state. The ranking considers capability evidence,
compatibility, maintenance, reported license, and security risk. Stars are
shown but do not affect the recommendation order. Presence of manifests,
tests, or workflows is evidence that files exist—not evidence that tests pass.

The raw launcher seed keeps `package_entries` empty so plugin/fork capture and
package publication remain separate inputs. The bounded, networkless
`scripts/ingest_package_catalog.py` validates
`data/package-catalog.sources.json` against the exact plugin metadata, emits
`data/package-catalog.seed.json`. `scripts/embed_catalog.py` retains that feed
for package-contract compatibility, but the primary UI no longer promotes it.
The three initial package pages are unsigned curation records, not publisher
uploads or current recommendations. Uploader authorization,
moderation, signed registry metadata, trust-root distribution, and immutable
blob storage remain deferred. The local
`dsh-forge.package/v1` schema, DSSE/Ed25519 signing path, trust root, and offline
composer are documented in [Signed packages](signed-packages.md). The package
feed contract and proposed hosted-service boundary are documented in
[Package catalog](package-catalog.md).

## External plugin catalog

The first external adapter consumes the daily catalog published by
`w2112515/dsh-plugin-marketplace`:

```bash
python3 -m dsh_forge catalog sync-plugins
```

The current feed contains thousands of statically validated `dsh-plugin` topic
repositories. Forge downloads at most 15 MB over credential-free HTTPS,
rechecks redirect policy, verifies the feed's logical SHA-256 digest and
critical identities, and atomically replaces the FTS5 store. It imports
metadata only. The feed is not signed, no source is executed, and upstream
installability remains an external claim rather than a Forge authorization.

The collector stays outside the launcher. `scripts/seed_catalog.py` remains a
manually invoked maintenance tool, not a service or an app-startup scraper. New
agentic development tool adapters should normalize their registries, fork
networks, topics, and curated directories into the same snapshot rows. The
browser and local search store should not contain provider-specific crawlers.

Plugin records remain separate from the top-ten fork ranking with
`seed_rank: null`. Classify plugins using manifest and provenance evidence, not
only a repository name, topic, store listing, or the presence of plugin-like
code. A fork must not enter the ranked ten unless it actually ranks there.

Forge now creates a bounded, explainable metadata research queue, resolves exact
npm pins for curator-selected proposals, and publishes a local recipe only after
four explicit reviews and an Ed25519 signature. The daily workflow cannot sign.
Unsigned status, absent source analysis, unknown compatibility, and lack of
security verification remain visible until each later stage supplies evidence.
See [Hidden-gem research and publication](hidden-gem-pipeline.md).

Metadata is rendered as text. The embedding script rejects noncanonical source
URLs, checks identity and commit shape, and escapes script delimiters. It will
not treat a production signature as verified without a real verifier.

## Deferred actions

Browser-based composition and public uploads remain disabled. The CLI research
path can create and certify a local proposal, and the front page can run the
complete signed acquisition and sandbox-install transaction for that certified
recipe. Acquisition cannot start from an unsigned browser entry. If a
community checkout is already present in an
explicit scan root, the launcher can run only its captured CLI help probe in the
separate, pinned, networkless Apptainer sandbox. Passing does not promote it or
enable host launch. An isolated port or writable home alone is not a security
sandbox.

Broader adapters still need to pin revisions and normalize their metadata.
Curators must assess compatibility and expose conflicts; sandbox checks pass
before promotion. Forge does not promise automatic integration of every fork.

## Readiness

The Python server now supplies a loopback-only launcher alpha API. It discovers
only strong DSH signatures in configured roots, previews exact argv and
environment keys, and controls processes it started after verifying process
identity. The portable HTML export remains an explicitly disconnected preview
with no fake live cells.

Tests cover catalog behavior, metadata safety, session-protected API access,
scanner false positives, protected ports, process ownership, logs, and stop.
They also enforce the two primary browser routes, backward-compatible package
routes, exact plugin package pins, deterministic package feed, disabled unsigned acquisition,
and separation between manifest review and execution.
Browser layout testing and production runtime adapters remain release tasks.
This is not a complete production launcher. The bounded Apptainer probe is an
initial foreign-code test boundary, not a claim of complete hostile-code safety.
