// Likes for plugins, forks, and packs on the hosted site. The key-value store is an
// in-memory fake of the Upstash pipeline API; no network.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SESSION_COOKIE, sign } from '../api/_lib/session.mjs';
import { handleLikes } from '../api/likes.mjs';
import { handleSession } from '../api/auth/session.mjs';

const ORIGIN = 'https://forge.example';
const SECRET = 's'.repeat(48);
const KV_ONLY = { KV_REST_API_URL: 'https://kv.example', KV_REST_API_TOKEN: 'kv-token' };
const ENV = {
  ...KV_ONLY,
  GITHUB_OAUTH_CLIENT_ID: 'client-id',
  GITHUB_OAUTH_CLIENT_SECRET: 'client-secret',
  DSH_FORGE_SESSION_SECRET: SECRET
};
const VISITOR = '3f2a1b4c-1d2e-4f3a-8b9c-0d1e2f3a4b5c';
const OTHER = '9a8b7c6d-5e4f-4a3b-9c2d-1e0f9a8b7c6d';

function pipelineKv() {
  const data = new Map();
  const set = key => { if (!data.has(key)) data.set(key, new Set()); return data.get(key); };
  const zset = key => { if (!data.has(key)) data.set(key, new Map()); return data.get(key); };
  const batches = [];
  const fetcher = async (url, options) => {
    assert.equal(url, 'https://kv.example/pipeline');
    assert.equal(options.headers.Authorization, 'Bearer kv-token');
    const commands = JSON.parse(options.body);
    batches.push(commands.map(command => command[0]));
    return Response.json(commands.map(([command, key, ...args]) => {
      switch (command) {
        case 'SADD': { const s = set(key); const had = s.has(args[0]); s.add(args[0]); return { result: had ? 0 : 1 }; }
        case 'SREM': return { result: set(key).delete(args[0]) ? 1 : 0 };
        case 'SCARD': return { result: set(key).size };
        case 'SMISMEMBER': return { result: args.map(member => set(key).has(member) ? 1 : 0) };
        case 'SISMEMBER': return { result: set(key).has(args[0]) ? 1 : 0 };
        case 'ZADD': zset(key).set(args[1], Number(args[0])); return { result: 1 };
        case 'ZREM': return { result: zset(key).delete(args[0]) ? 1 : 0 };
        case 'ZMSCORE': return { result: args.map(member => zset(key).has(member) ? String(zset(key).get(member)) : null) };
        case 'INCR': { const value = (data.get(key) || 0) + 1; data.set(key, value); return { result: value }; }
        case 'EXPIRE': return { result: 1 };
        case 'ZINCRBY': { const z = zset(key); z.set(args[1], (z.get(args[1]) || 0) + Number(args[0])); return { result: String(z.get(args[1])) }; }
        case 'ZREVRANGE': {
          const ranked = [...zset(key)].sort((a, b) => b[1] - a[1]).slice(Number(args[0]), Number(args[1]) + 1);
          return { result: ranked.flatMap(([member, score]) => [member, String(score)]) };
        }
        default: return { error: 'unsupported ' + command };
      }
    }));
  };
  return { data, batches, fetcher };
}

function signedCookie() {
  const now = Math.floor(Date.now() / 1000);
  return SESSION_COOKIE + '=' + sign({ sub: 'github:9', login: 'octo', name: 'Octo', avatar: '', iat: now, exp: now + 60 }, SECRET);
}

function like(kv, id, liked, { visitor = VISITOR, cookie = '', env = ENV, ip = '203.0.113.7', origin = ORIGIN } = {}) {
  const headers = { 'Content-Type': 'application/json', 'X-Forwarded-For': ip };
  if (origin) headers.Origin = origin;
  if (visitor) headers['X-Forge-Visitor'] = visitor;
  if (cookie) headers.Cookie = cookie;
  return handleLikes(new Request(ORIGIN + '/api/likes', { method: 'POST', headers, body: JSON.stringify({ id, liked }) }), { env, fetcher: kv.fetcher });
}

function read(kv, query, { visitor = VISITOR, cookie = '', env = ENV } = {}) {
  const headers = {};
  if (visitor) headers['X-Forge-Visitor'] = visitor;
  if (cookie) headers.Cookie = cookie;
  return handleLikes(new Request(ORIGIN + '/api/likes?' + query, { headers }), { env, fetcher: kv.fetcher });
}

test('likes need only the store, and the session says when they are available', async () => {
  const kv = pipelineKv();
  const off = await handleLikes(new Request(ORIGIN + '/api/likes?ids=github:1'), { env: {}, fetcher: kv.fetcher });
  assert.equal(off.status, 503);
  const session = await handleSession(new Request(ORIGIN + '/api/auth/session'), { env: KV_ONLY }).json();
  assert.equal(session.likes, true);
  assert.equal(session.configured, false);
  // Anonymous visitors can like without sign-in being set up at all.
  const response = await like(kv, 'github:1', true, { env: KV_ONLY });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { id: 'github:1', liked: true, count: 1 });
});

test('anonymous likes count once per browser and can be undone', async () => {
  const kv = pipelineKv();
  await like(kv, 'github:1', true);
  await like(kv, 'github:1', true);
  await like(kv, 'github:1', true, { visitor: OTHER, ip: '198.51.100.20' });
  let page = await (await read(kv, 'ids=github:1,github:2,pack:memory-and-context')).json();
  assert.deepEqual(page.counts, { 'github:1': 2, 'github:2': 0, 'pack:memory-and-context': 0 });
  assert.deepEqual(page.liked, ['github:1']);
  const undone = await (await like(kv, 'github:1', false)).json();
  assert.equal(undone.count, 1);
  page = await (await read(kv, 'ids=github:1')).json();
  assert.deepEqual(page.liked, []);
});

test('signed-in likes weigh more, and replace the same browser\'s anonymous like', async () => {
  const kv = pipelineKv();
  await like(kv, 'github:5', true);
  await like(kv, 'pack:agent-teams', true, { visitor: OTHER, ip: '198.51.100.20' });
  let top = await (await read(kv, 'top=5')).json();
  assert.deepEqual(top.top, [{ id: 'github:5', score: 0.5 }, { id: 'pack:agent-teams', score: 0.5 }]);
  // Signing in on the browser that already liked it: one person, one like, full weight.
  const signed = await (await like(kv, 'github:5', true, { cookie: signedCookie() })).json();
  assert.equal(signed.count, 1);
  top = await (await read(kv, 'top=5')).json();
  assert.deepEqual(top.top[0], { id: 'github:5', score: 1 });
  const page = await (await read(kv, 'ids=github:5', { cookie: signedCookie() })).json();
  assert.deepEqual(page.liked, ['github:5']);
});

test('fresh visitor ids from one address cannot stack anonymous likes', async () => {
  const kv = pipelineKv();
  for (let index = 0; index < 5; index += 1) {
    const visitor = '3f2a1b4c-1d2e-4f3a-8b9c-0d1e2f3a4b5' + index;
    await like(kv, 'github:7', true, { visitor });
  }
  let page = await (await read(kv, 'ids=github:7')).json();
  assert.equal(page.counts['github:7'], 1);
  // A signed-in person on the same network still counts.
  const signed = await (await like(kv, 'github:7', true, { cookie: signedCookie(), visitor: '' })).json();
  assert.equal(signed.count, 2);
  // Once the counted visitor unlikes, someone else at that address can count.
  await like(kv, 'github:7', false, { visitor: '3f2a1b4c-1d2e-4f3a-8b9c-0d1e2f3a4b50' });
  await like(kv, 'github:7', true, { visitor: '3f2a1b4c-1d2e-4f3a-8b9c-0d1e2f3a4b53' });
  page = await (await read(kv, 'ids=github:7')).json();
  assert.equal(page.counts['github:7'], 2);
});

test('counts and ranking are rebuilt from the sets, so a half-failed write heals', async () => {
  const kv = pipelineKv();
  await like(kv, 'github:8', true);
  // Simulate a write that recorded the like but never updated the ranking.
  kv.data.get('dsh-forge:likes:v1:rank').delete('github:8');
  kv.data.get('dsh-forge:likes:v1:count').delete('github:8');
  await like(kv, 'github:8', true);
  const top = await (await read(kv, 'top=5')).json();
  assert.deepEqual(top.top, [{ id: 'github:8', score: 0.5 }]);
  const page = await (await read(kv, 'ids=github:8')).json();
  assert.equal(page.counts['github:8'], 1);
  // Reads cost two store commands however many ids are asked for.
  kv.batches.length = 0;
  await read(kv, 'ids=' + Array.from({ length: 60 }, (_, index) => 'github:' + (index + 1)).join(','));
  assert.deepEqual(kv.batches, [['ZMSCORE', 'SMISMEMBER']]);
});

test('writes are same-origin, validated, need a viewer, and are rate limited', async () => {
  const kv = pipelineKv();
  assert.equal((await like(kv, 'github:1', true, { origin: 'https://evil.example' })).status, 403);
  assert.equal((await like(kv, 'github:1', true, { origin: '' })).status, 403);
  assert.equal((await like(kv, 'javascript:alert(1)', true)).status, 400);
  assert.equal((await like(kv, 'github:1', 'yes')).status, 400);
  assert.equal((await like(kv, 'github:1', true, { visitor: 'not-a-uuid' })).status, 400);
  // Unknown ids are dropped from reads instead of being passed to the store.
  const page = await (await read(kv, 'ids=github:1,../../etc,pack:UPPER')).json();
  assert.deepEqual(Object.keys(page.counts), ['github:1']);
  for (let index = 0; index < 120; index += 1) await like(kv, 'github:2', index % 2 === 0);
  assert.equal((await like(kv, 'github:2', true)).status, 429);
  // Another address has its own budget; the address itself is never stored.
  assert.equal((await like(kv, 'github:2', true, { ip: '198.51.100.4' })).status, 200);
  assert(![...kv.data.keys()].some(key => key.includes('203.0.113.7')));
});

test('a store failure is reported without leaking details', async () => {
  const response = await handleLikes(new Request(ORIGIN + '/api/likes?ids=github:1', { headers: { 'X-Forge-Visitor': VISITOR } }), {
    env: ENV, fetcher: async () => new Response('boom', { status: 500 })
  });
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: 'Likes are temporarily unavailable' });
});
