// Likes for plugins, forks, and packs.
//   GET  /api/likes?ids=a,b,c   → counts and which of them this viewer liked
//   GET  /api/likes?top=20      → most-liked ids (signed-in likes weigh 1, anonymous 0.5)
// Anonymous likes count once per network address per item.
//   POST /api/likes {id, liked} → set this viewer's like
// Viewers are a signed-in GitHub account or an anonymous browser id sent in
// the X-Forge-Visitor header. Writes are rate-limited by a keyed hash of the IP.
import { createHmac } from 'node:crypto';
import { authConfig, json, kvPipeline, sameOrigin, sessionUser } from './_lib/session.mjs';

const ID = /^(?:github:\d{1,12}|pack:[a-z0-9-]{1,64})$/;
const VISITOR = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const MAX_IDS = 60;
const SIGNED_WEIGHT = 1;
const ANONYMOUS_WEIGHT = 0.5;
const WRITES_PER_HOUR = 120;
const PREFIX = 'dsh-forge:likes:v1:';

function viewerOf(request, config) {
  const session = config.configured ? sessionUser(request, config) : null;
  const visitor = String(request.headers.get('x-forge-visitor') || '').toLowerCase();
  return {
    signed: session ? session.sub : null,
    anonymous: VISITOR.test(visitor) ? visitor : null
  };
}

function viewerKey(viewer) {
  return viewer.signed ? 'u:' + viewer.signed : (viewer.anonymous ? 'a:' + viewer.anonymous : null);
}

function clientHash(request, config) {
  const forwarded = String(request.headers.get('x-forwarded-for') || '').split(',')[0].trim() || 'unknown';
  return createHmac('sha256', config.secret || config.kvToken).update(forwarded).digest('hex').slice(0, 32);
}

export async function handleLikes(request, { env = process.env, fetcher = fetch, now = Date.now() } = {}) {
  const config = authConfig(env);
  if (!config.likes) return json({ error: 'Likes are not configured for this deployment' }, 503);
  const url = new URL(request.url);
  const viewer = viewerOf(request, config);
  const key = viewerKey(viewer);
  try {
    if (request.method === 'GET' && url.searchParams.has('top')) {
      const limit = Math.min(50, Math.max(1, Number.parseInt(url.searchParams.get('top'), 10) || 20));
      const [flat] = await kvPipeline(config, [['ZREVRANGE', PREFIX + 'rank', '0', String(limit - 1), 'WITHSCORES']], fetcher);
      const top = [];
      for (let index = 0; index + 1 < (flat || []).length; index += 2) {
        if (ID.test(flat[index]) && Number(flat[index + 1]) > 0) top.push({ id: flat[index], score: Number(flat[index + 1]) });
      }
      return json({ top }, 200, { 'Cache-Control': 'public, s-maxage=60' });
    }
    if (request.method === 'GET') {
      const ids = [...new Set(String(url.searchParams.get('ids') || '').split(',').filter(id => ID.test(id)))].slice(0, MAX_IDS);
      if (!ids.length) return json({ counts: {}, liked: [] });
      // Two commands whatever the page size: counts live in one sorted set.
      const commands = [['ZMSCORE', PREFIX + 'count', ...ids]];
      if (key) commands.push(['SMISMEMBER', PREFIX + 'viewer:' + key, ...ids]);
      const [scores, membership = []] = await kvPipeline(config, commands, fetcher);
      const counts = Object.fromEntries(ids.map((id, index) => [id, Math.max(0, Math.round(Number((scores || [])[index]) || 0))]));
      return json({ counts, liked: key ? ids.filter((_, index) => Number(membership[index]) === 1) : [] });
    }
    if (request.method !== 'POST') return json({ error: 'Method not allowed' }, 405, { Allow: 'GET, POST' });
    if (!sameOrigin(request)) return json({ error: 'Same-origin request required' }, 403);
    if (!key) return json({ error: 'Sign in or allow this browser to keep a visitor id to like things' }, 400);
    let body;
    try { body = JSON.parse(await request.text()); } catch { return json({ error: 'Body must be JSON' }, 400); }
    const id = String((body && body.id) || '');
    if (!ID.test(id) || typeof body.liked !== 'boolean') return json({ error: 'id and liked are required' }, 400);
    const address = clientHash(request, config);
    const hour = Math.floor(now / 3_600_000);
    const limitKey = PREFIX + 'rate:' + address + ':' + hour;
    const [writes] = await kvPipeline(config, [['INCR', limitKey], ['EXPIRE', limitKey, '3600']], fetcher);
    if (Number(writes) > WRITES_PER_HOUR) return json({ error: 'Too many likes for now; try again later' }, 429);

    const viewerSet = PREFIX + 'viewer:' + key;
    const signedSet = PREFIX + id + ':u';
    const anonymousSet = PREFIX + id + ':a';
    // One anonymous like per network address per item: fresh visitor ids from one
    // address can't stack likes. Signing in is how a second person there counts.
    const addressSet = PREFIX + id + ':addr';
    if (viewer.signed) {
      const commands = body.liked
        ? [['SADD', signedSet, viewer.signed], ['SADD', viewerSet, id]]
        : [['SREM', signedSet, viewer.signed], ['SREM', viewerSet, id]];
      if (viewer.anonymous) {
        // A signed-in like replaces this browser's anonymous one, so one person counts once.
        commands.push(['SREM', anonymousSet, viewer.anonymous], ['SREM', PREFIX + 'viewer:a:' + viewer.anonymous, id]);
      }
      const results = await kvPipeline(config, commands, fetcher);
      if (viewer.anonymous && Number(results[2]) === 1) await kvPipeline(config, [['SREM', addressSet, address]], fetcher);
    } else if (body.liked) {
      const [, already, first] = await kvPipeline(config, [
        ['SADD', viewerSet, id], ['SISMEMBER', anonymousSet, viewer.anonymous], ['SADD', addressSet, address]
      ], fetcher);
      if (Number(already) === 0 && Number(first) === 1) await kvPipeline(config, [['SADD', anonymousSet, viewer.anonymous]], fetcher);
    } else {
      const [, removed] = await kvPipeline(config, [['SREM', viewerSet, id], ['SREM', anonymousSet, viewer.anonymous]], fetcher);
      if (Number(removed) === 1) await kvPipeline(config, [['SREM', addressSet, address]], fetcher);
    }
    // Counts and ranking are rewritten from the sets on every write, so a write that
    // failed halfway is repaired by the next one instead of drifting forever.
    const [signed, anonymous] = await kvPipeline(config, [['SCARD', signedSet], ['SCARD', anonymousSet]], fetcher);
    const count = Number(signed || 0) + Number(anonymous || 0);
    const score = SIGNED_WEIGHT * Number(signed || 0) + ANONYMOUS_WEIGHT * Number(anonymous || 0);
    await kvPipeline(config, count
      ? [['ZADD', PREFIX + 'count', String(count), id], ['ZADD', PREFIX + 'rank', String(score), id]]
      : [['ZREM', PREFIX + 'count', id], ['ZREM', PREFIX + 'rank', id]], fetcher);
    return json({ id, liked: body.liked, count });
  } catch {
    return json({ error: 'Likes are temporarily unavailable' }, 503);
  }
}

export function GET(request) { return handleLikes(request); }
export function POST(request) { return handleLikes(request); }
