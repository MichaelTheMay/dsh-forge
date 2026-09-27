// GitHub sign-in and synced favorites for the hosted site. No network: GitHub
// and the key-value store are replaced with in-memory fakes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  SESSION_COOKIE, STATE_COOKIE, parseCookies, sanitizeFavorites, sign, verify
} from '../api/_lib/session.mjs';
import { handleLogin } from '../api/auth/login.mjs';
import { handleCallback } from '../api/auth/callback.mjs';
import { handleLogout, handleSession } from '../api/auth/session.mjs';
import { handleFavorites } from '../api/favorites.mjs';

const ORIGIN = 'https://forge.example';
const SECRET = 's'.repeat(48);
const ENV = {
  GITHUB_OAUTH_CLIENT_ID: 'client-id',
  GITHUB_OAUTH_CLIENT_SECRET: 'client-secret',
  DSH_FORGE_SESSION_SECRET: SECRET,
  KV_REST_API_URL: 'https://kv.example',
  KV_REST_API_TOKEN: 'kv-token'
};

function cookieValue(response, name) {
  const all = response.headers.getSetCookie ? response.headers.getSetCookie() : [response.headers.get('set-cookie')];
  const line = all.find(item => item && item.startsWith(name + '='));
  return line ? line.slice(name.length + 1).split(';')[0] : null;
}

function sessionCookie(now = Math.floor(Date.now() / 1000)) {
  return SESSION_COOKIE + '=' + sign({ sub: 'github:9', login: 'octo', name: 'Octo', avatar: '', iat: now, exp: now + 60 }, SECRET);
}

function fakeKv() {
  const store = new Map();
  const calls = [];
  const fetcher = async (url, options) => {
    assert.equal(url, 'https://kv.example');
    assert.equal(options.headers.Authorization, 'Bearer kv-token');
    const [command, key, value] = JSON.parse(options.body);
    calls.push(command);
    if (command === 'GET') return Response.json({ result: store.has(key) ? store.get(key) : null });
    if (command === 'SET') { store.set(key, value); return Response.json({ result: 'OK' }); }
    if (command === 'DEL') { store.delete(key); return Response.json({ result: 1 }); }
    return Response.json({ error: 'unknown' });
  };
  return { store, calls, fetcher };
}

test('session tokens are signed, expiring, and tamper-evident', () => {
  const token = sign({ sub: 'github:1', exp: 2_000 }, SECRET);
  assert.equal(verify(token, SECRET, 1_000).sub, 'github:1');
  assert.equal(verify(token, SECRET, 2_000), null);
  assert.equal(verify(token, 'x'.repeat(48), 1_000), null);
  const [body, mac] = token.split('.');
  const forged = Buffer.from(JSON.stringify({ sub: 'github:2', exp: 2_000 })).toString('base64url');
  assert.equal(verify(forged + '.' + mac, SECRET, 1_000), null);
  assert.equal(verify(body, SECRET, 1_000), null);
});

test('sign-in is hidden until the deployment is fully configured', async () => {
  const missing = await handleSession(new Request(ORIGIN + '/api/auth/session'), { env: {} }).json();
  assert.deepEqual(missing, { configured: false, sync: false, user: null });
  const weakSecret = handleLogin(new Request(ORIGIN + '/api/auth/login'), { env: { ...ENV, DSH_FORGE_SESSION_SECRET: 'short' } });
  assert.equal(weakSecret.status, 503);
  const noSync = await handleSession(new Request(ORIGIN + '/api/auth/session'), { env: { ...ENV, KV_REST_API_URL: '' } }).json();
  assert.equal(noSync.configured, true);
  assert.equal(noSync.sync, false);
});

test('login redirects to GitHub with state, PKCE, no scopes, and a safe return route', () => {
  const response = handleLogin(new Request(ORIGIN + '/api/auth/login?return=%23forks%2Fgithub%3A1'), { env: ENV, now: 1_000 });
  assert.equal(response.status, 302);
  const location = new URL(response.headers.get('location'));
  assert.equal(location.origin + location.pathname, 'https://github.com/login/oauth/authorize');
  assert.equal(location.searchParams.get('redirect_uri'), ORIGIN + '/api/auth/callback');
  assert.equal(location.searchParams.get('scope'), '');
  assert.equal(location.searchParams.get('code_challenge_method'), 'S256');
  const pending = verify(cookieValue(response, STATE_COOKIE), SECRET, 1_000);
  assert.equal(pending.state, location.searchParams.get('state'));
  assert.equal(pending.return, '#forks/github:1');
  assert.match(response.headers.get('set-cookie'), /HttpOnly; Secure; SameSite=Lax/);
  const unsafe = handleLogin(new Request(ORIGIN + '/api/auth/login?return=https://evil.example'), { env: ENV, now: 1_000 });
  assert.equal(verify(cookieValue(unsafe, STATE_COOKIE), SECRET, 1_000).return, '#plugins');
});

test('callback exchanges the code with PKCE, sets a session, and revokes the GitHub token', async () => {
  const login = handleLogin(new Request(ORIGIN + '/api/auth/login?return=%23forks'), { env: ENV, now: 1_000 });
  const state = new URL(login.headers.get('location')).searchParams.get('state');
  const pending = cookieValue(login, STATE_COOKIE);
  const requests = [];
  const fetcher = async (url, options = {}) => {
    requests.push({ url, options });
    if (url === 'https://github.com/login/oauth/access_token') {
      const body = JSON.parse(options.body);
      assert.equal(body.code, 'good-code');
      assert.equal(body.code_verifier, verify(pending, SECRET, 1_000).verifier);
      return Response.json({ access_token: 'gho_abc' });
    }
    if (url === 'https://api.github.com/user') {
      assert.equal(options.headers.Authorization, 'Bearer gho_abc');
      return Response.json({ id: 9, login: 'octo', name: 'Octo Cat', avatar_url: 'https://avatars.githubusercontent.com/u/9?v=4' });
    }
    if (url.includes('/applications/client-id/token')) return new Response(null, { status: 204 });
    throw new Error('unexpected ' + url);
  };
  const request = new Request(ORIGIN + '/api/auth/callback?code=good-code&state=' + state, {
    headers: { cookie: STATE_COOKIE + '=' + pending }
  });
  const response = await handleCallback(request, { env: ENV, fetcher, now: 1_000 });
  assert.equal(response.status, 302);
  assert.equal(response.headers.get('location'), '/#forks');
  const session = verify(cookieValue(response, SESSION_COOKIE), SECRET, 1_000);
  assert.equal(session.sub, 'github:9');
  assert.equal(session.login, 'octo');
  assert.equal(JSON.stringify(session).includes('gho_abc'), false);
  assert.equal(cookieValue(response, STATE_COOKIE), '');
  await new Promise(resolve => setImmediate(resolve));
  assert(requests.some(item => item.url.endsWith('/applications/client-id/token') && item.options.method === 'DELETE'));
});

test('callback rejects a missing or mismatched state before contacting GitHub', async () => {
  let called = false;
  const fetcher = async () => { called = true; return Response.json({}); };
  const pending = sign({ state: 'expected', verifier: 'v', return: '#plugins', exp: 2_000 }, SECRET);
  for (const [query, cookie] of [
    ['code=c&state=other', STATE_COOKIE + '=' + pending],
    ['code=c&state=expected', ''],
    ['code=c&state=expected', STATE_COOKIE + '=' + sign({ state: 'expected', exp: 500 }, SECRET)]
  ]) {
    const response = await handleCallback(new Request(ORIGIN + '/api/auth/callback?' + query, { headers: { cookie } }), { env: ENV, fetcher, now: 1_000 });
    assert.equal(response.status, 302);
    assert.match(response.headers.get('location'), /^\/\?signin=expired#/);
  }
  assert.equal(called, false);
});

test('session reports the signed-in user and logout requires same origin', async () => {
  const request = new Request(ORIGIN + '/api/auth/session', { headers: { cookie: sessionCookie() } });
  const body = await handleSession(request, { env: ENV }).json();
  assert.deepEqual(body.user, { id: 'github:9', login: 'octo', name: 'Octo', avatar_url: '' });
  const crossSite = await handleLogout(new Request(ORIGIN + '/api/auth/session', { method: 'POST', headers: { origin: 'https://evil.example' } }), { env: ENV });
  assert.equal(crossSite.status, 403);
  const logout = await handleLogout(new Request(ORIGIN + '/api/auth/session', { method: 'POST', headers: { origin: ORIGIN } }), { env: ENV });
  assert.equal(logout.status, 200);
  assert.equal(cookieValue(logout, SESSION_COOKIE), '');
});

test('favorites sync per user, sanitized, and only from this origin', async () => {
  const kv = fakeKv();
  const headers = { cookie: sessionCookie(), origin: ORIGIN, 'content-type': 'application/json' };
  const anonymous = await handleFavorites(new Request(ORIGIN + '/api/favorites'), { env: ENV, fetcher: kv.fetcher });
  assert.equal(anonymous.status, 401);
  const empty = await handleFavorites(new Request(ORIGIN + '/api/favorites', { headers }), { env: ENV, fetcher: kv.fetcher }).then(r => r.json());
  assert.deepEqual(empty, { favorites: [], updated_at: null });
  const favorites = [
    { id: 'github:1', type: 'fork', name: 'one', url: 'https://github.com/octo/one', head_sha: 'a'.repeat(40), extra: 'dropped' },
    { id: 'github:1', type: 'fork', name: 'duplicate' },
    { id: 'github:2', type: 'package', name: 'wrong type' },
    { id: 'github:3', type: 'plugin', name: 'x'.repeat(500), url: 'javascript:alert(1)' }
  ];
  const put = await handleFavorites(new Request(ORIGIN + '/api/favorites', { method: 'PUT', headers, body: JSON.stringify({ favorites }) }), { env: ENV, fetcher: kv.fetcher, now: 5 });
  assert.equal(put.status, 200);
  const saved = await put.json();
  assert.deepEqual(saved.favorites.map(item => item.id), ['github:1', 'github:3']);
  assert.equal(saved.favorites[0].extra, undefined);
  assert.equal(saved.favorites[1].url, '');
  assert.equal(saved.favorites[1].name.length, 120);
  assert.deepEqual([...kv.store.keys()], ['dsh-forge:favorites:v1:github:9']);
  const read = await handleFavorites(new Request(ORIGIN + '/api/favorites', { headers }), { env: ENV, fetcher: kv.fetcher }).then(r => r.json());
  assert.deepEqual(read, saved);
  const crossSite = await handleFavorites(new Request(ORIGIN + '/api/favorites', { method: 'PUT', headers: { ...headers, origin: 'https://evil.example' }, body: '{"favorites":[]}' }), { env: ENV, fetcher: kv.fetcher });
  assert.equal(crossSite.status, 403);
  const deleted = await handleFavorites(new Request(ORIGIN + '/api/favorites', { method: 'DELETE', headers }), { env: ENV, fetcher: kv.fetcher });
  assert.equal(deleted.status, 200);
  assert.equal(kv.store.size, 0);
});

test('favorites fail closed without storage and cap the list', async () => {
  const unconfigured = await handleFavorites(new Request(ORIGIN + '/api/favorites', { headers: { cookie: sessionCookie() } }), { env: { ...ENV, KV_REST_API_TOKEN: '' } });
  assert.equal(unconfigured.status, 503);
  const many = Array.from({ length: 450 }, (_, index) => ({ id: 'github:' + index, type: 'plugin' }));
  assert.equal(sanitizeFavorites(many).length, 200);
  assert.throws(() => sanitizeFavorites('nope'));
  assert.deepEqual(parseCookies('a=1; b=2; a=3'), { a: '1', b: '2' });
});
