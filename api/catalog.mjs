import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';

const REPOSITORY = 'MichaelTheMay/dsh-forge';
const RELEASE_ROOT = `https://github.com/${REPOSITORY}/releases/download/catalog-latest`;
const FEED_URL = `${RELEASE_ROOT}/registry-feed.json`;
const ASSET_URLS = {
  registry: `${RELEASE_ROOT}/registry.json.gz`,
  hidden_gems: `${RELEASE_ROOT}/hidden-gems.json.gz`
};
const CACHE_MS = 10 * 60 * 1000;
const MAX_CURSOR = 50_000;
const MAX = {
  feed: 64 * 1024,
  registryCompressed: 8 * 1024 * 1024,
  registryExpanded: 64 * 1024 * 1024,
  researchCompressed: 2 * 1024 * 1024,
  researchExpanded: 8 * 1024 * 1024
};

let cached;
let expiresAt = 0;
let loading;

function fail(message, status = 502) {
  const error = new Error(message);
  error.status = status;
  throw error;
}

function digest(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

async function download(url, limit) {
  const response = await fetch(url, {
    redirect: 'follow',
    headers: { Accept: 'application/octet-stream', 'User-Agent': 'dsh-forge-public-catalog/1' },
    signal: AbortSignal.timeout(20_000)
  });
  if (!response.ok) fail(`Catalog publisher returned ${response.status}`);
  const declared = Number(response.headers.get('content-length') || 0);
  if (declared > limit) fail('Published catalog asset exceeds its size limit');
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length > limit) fail('Published catalog asset exceeds its size limit');
  return bytes;
}

function assertClaims(claims) {
  if (!claims || claims.metadata_only !== true || claims.executed !== false || claims.security_verified !== false) {
    fail('Published catalog has unsupported trust claims');
  }
}

export function parseVerifiedGzip(bytes, metadata, compressedLimit, expandedLimit) {
  if (!metadata || metadata.compression !== 'gzip' || metadata.media_type !== 'application/json') {
    fail('Published catalog asset metadata is invalid');
  }
  if (!Number.isSafeInteger(metadata.compressed_bytes) || metadata.compressed_bytes !== bytes.length || bytes.length > compressedLimit) {
    fail('Published catalog compressed length does not match');
  }
  if (digest(bytes) !== metadata.compressed_sha256) fail('Published catalog compressed digest does not match');
  let expanded;
  try {
    expanded = gunzipSync(bytes, { maxOutputLength: expandedLimit });
  } catch {
    fail('Published catalog could not be decompressed');
  }
  if (!Number.isSafeInteger(metadata.uncompressed_bytes) || metadata.uncompressed_bytes !== expanded.length) {
    fail('Published catalog expanded length does not match');
  }
  if (digest(expanded) !== metadata.uncompressed_sha256) fail('Published catalog expanded digest does not match');
  try {
    return JSON.parse(expanded.toString('utf8'));
  } catch {
    fail('Published catalog is not valid JSON');
  }
}

function validateFeed(feed) {
  if (!feed || feed.schema !== 'dsh-forge.registry-feed/v1' || feed.source_repository !== REPOSITORY) {
    fail('Published catalog feed is not a supported DSH Forge feed');
  }
  assertClaims(feed.claims);
  for (const [name, expected] of Object.entries(ASSET_URLS)) {
    if (!feed.assets || !feed.assets[name] || feed.assets[name].url !== expected) {
      fail('Published catalog points to an unexpected asset');
    }
  }
}

async function loadFeed() {
  const bytes = await download(FEED_URL, MAX.feed);
  try {
    const feed = JSON.parse(bytes.toString('utf8'));
    validateFeed(feed);
    return feed;
  } catch (error) {
    if (error.status) throw error;
    fail('Published catalog feed is not valid JSON');
  }
}

function validateCatalog(feed, registry, research) {
  const entries = Array.isArray(registry && registry.entries) ? registry.entries : [];
  const plugins = Array.isArray(registry && registry.supplemental_entries) ? registry.supplemental_entries : [];
  const packages = Array.isArray(registry && registry.package_entries) ? registry.package_entries : [];
  const candidates = Array.isArray(research && research.candidates) ? research.candidates : [];
  if (registry.schema_version !== 1 || research.schema !== 'dsh-forge.discovery-queue/v2') fail('Published catalog schema is unsupported');
  if (registry.snapshot_id !== feed.snapshot_id || research.snapshot_id !== feed.snapshot_id) fail('Published catalog snapshots do not agree');
  assertClaims(research.claims);
  if (entries.length !== feed.counts.forks || plugins.length !== feed.counts.plugins ||
      packages.length !== feed.counts.packages || candidates.length !== feed.counts.candidates) {
    fail('Published catalog counts do not agree');
  }
  const artifacts = [...entries, ...plugins, ...packages];
  const byId = new Map(artifacts.map(item => [item.artifact_id, item]));
  const hiddenGems = new Map(candidates.map(item => [item.research.artifact_id, item.research]));
  return { feed, artifacts, byId, hiddenGems };
}

async function loadCatalog() {
  if (cached && Date.now() < expiresAt) return cached;
  if (loading) return loading;
  loading = (async () => {
    const feed = await loadFeed();
    if (cached && cached.feed.snapshot_id === feed.snapshot_id) {
      expiresAt = Date.now() + CACHE_MS;
      return cached;
    }
    const [registryBytes, researchBytes] = await Promise.all([
      download(ASSET_URLS.registry, MAX.registryCompressed),
      download(ASSET_URLS.hidden_gems, MAX.researchCompressed)
    ]);
    const registry = parseVerifiedGzip(
      registryBytes, feed.assets.registry, MAX.registryCompressed, MAX.registryExpanded
    );
    const research = parseVerifiedGzip(
      researchBytes, feed.assets.hidden_gems, MAX.researchCompressed, MAX.researchExpanded
    );
    cached = validateCatalog(feed, registry, research);
    expiresAt = Date.now() + CACHE_MS;
    return cached;
  })().finally(() => { loading = null; });
  return loading;
}

function textFor(artifact) {
  return [
    artifact.full_name, artifact.name, artifact.owner, artifact.description,
    artifact.language, artifact.artifact_type, ...(artifact.topics || []),
    artifact.package && artifact.package.name
  ].filter(Boolean).join(' ').toLowerCase();
}

function tagsOf(artifact) {
  const enrichment = artifact.enrichment;
  return enrichment && Array.isArray(enrichment.tags) ? enrichment.tags : [];
}

function knownLicense(artifact) {
  const spdx = String((artifact.license && artifact.license.spdx) || '').toUpperCase();
  return !!spdx && spdx !== 'NOASSERTION' && spdx !== 'UNKNOWN';
}

function relevance(artifact, terms) {
  if (!terms.length) return 0;
  const fullName = String(artifact.full_name || '').toLowerCase();
  const name = String(artifact.name || '').toLowerCase();
  const haystack = textFor(artifact);
  if (!terms.every(term => haystack.includes(term))) return -1;
  return terms.reduce((score, term) => score + (name === term ? 12 : name.startsWith(term) ? 8 : fullName.includes(term) ? 4 : 1), 0);
}

function compareText(a, b) {
  return String(a.full_name || a.name || '').localeCompare(String(b.full_name || b.name || ''));
}

export function queryCatalog(catalog, url) {
  const type = url.searchParams.get('type') || 'plugin';
  if (!['plugin', 'fork', 'package'].includes(type)) fail('Unknown catalog type', 400);
  const sort = url.searchParams.get('sort') || 'rank';
  if (!['rank', 'relevance', 'stars', 'recent', 'name'].includes(sort)) fail('Unknown catalog sort', 400);
  const query = (url.searchParams.get('q') || '').trim().toLowerCase();
  if (query.length > 120) fail('Catalog query is too long', 400);
  const terms = query.split(/\s+/).filter(Boolean);
  const licensed = url.searchParams.get('licensed') === '1';
  const differentiated = url.searchParams.get('differentiated') === '1';
  const rawTags = (url.searchParams.get('tags') || '').trim();
  if (rawTags.length > 200) fail('Too many catalog tag filters', 400);
  // Every requested tag must be present, so filters narrow rather than widen.
  const tags = rawTags ? rawTags.split(',').map(value => value.trim()).filter(Boolean).slice(0, 12) : [];
  const limit = Math.min(50, Math.max(1, Number.parseInt(url.searchParams.get('limit') || '50', 10) || 50));
  const cursorText = url.searchParams.get('cursor') || '0';
  if (!/^\d+$/.test(cursorText)) fail('Invalid catalog cursor', 400);
  const offset = Number(cursorText);
  if (!Number.isSafeInteger(offset) || offset < 0 || offset > MAX_CURSOR) fail('Invalid catalog cursor', 400);

  const scored = [];
  for (const artifact of catalog.artifacts) {
    if (artifact.artifact_type !== type || (licensed && !knownLicense(artifact))) continue;
    if (differentiated && artifact.enrichment && artifact.enrichment.differentiated === false) continue;
    if (tags.length) {
      const own = tagsOf(artifact);
      if (!tags.every(tag => own.includes(tag))) continue;
    }
    const score = relevance(artifact, terms);
    if (score >= 0) scored.push({ artifact, score, rank: catalog.hiddenGems.get(artifact.artifact_id)?.rank ?? Infinity });
  }
  scored.sort((a, b) => {
    if (sort === 'name') return compareText(a.artifact, b.artifact);
    if (sort === 'recent') return (Date.parse(b.artifact.pushed_at) || 0) - (Date.parse(a.artifact.pushed_at) || 0) || compareText(a.artifact, b.artifact);
    if (sort === 'stars') return (b.artifact.github_stars ?? -1) - (a.artifact.github_stars ?? -1) || compareText(a.artifact, b.artifact);
    if (sort === 'relevance' && b.score !== a.score) return b.score - a.score;
    return a.rank - b.rank || (b.artifact.github_stars ?? -1) - (a.artifact.github_stars ?? -1) || compareText(a.artifact, b.artifact);
  });
  const page = scored.slice(offset, offset + limit).map(item => item.artifact);
  return {
    artifacts: page,
    total: scored.length,
    next_cursor: offset + limit < scored.length ? String(offset + limit) : '',
    research: Object.fromEntries(page.flatMap(item => {
      const report = catalog.hiddenGems.get(item.artifact_id);
      return report ? [[item.artifact_id, report]] : [];
    }))
  };
}

function storeMetadata(catalog) {
  const { feed } = catalog;
  return {
    available: true,
    public: true,
    artifact_count: feed.counts.forks + feed.counts.plugins + feed.counts.packages,
    counts: { fork: feed.counts.forks, plugin: feed.counts.plugins, package: feed.counts.packages },
    coverage: feed.coverage,
    snapshot_id: feed.snapshot_id,
    fetched_at: feed.published_at,
    claims: feed.claims
  };
}

export async function GET(request) {
  try {
    const url = new URL(request.url);
    const catalog = await loadCatalog();
    const id = url.searchParams.get('id');
    let body;
    if (id) {
      if (id.length > 160) fail('Catalog artifact id is too long', 400);
      const artifact = catalog.byId.get(id);
      if (!artifact) fail('Unknown catalog artifact', 404);
      body = { ...artifact, hidden_gem: catalog.hiddenGems.get(id) || null };
    } else {
      body = { ...queryCatalog(catalog, url), catalog_store: storeMetadata(catalog) };
    }
    return Response.json(body, {
      headers: { 'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=3600' }
    });
  } catch (error) {
    const status = Number(error.status) || 503;
    if (status >= 500) console.error('Public catalog unavailable:', error.message);
    return Response.json(
      { error: status >= 500 ? 'The live catalog is temporarily unavailable' : error.message },
      { status, headers: { 'Cache-Control': 'no-store' } }
    );
  }
}
