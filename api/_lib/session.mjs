// Shared helpers for GitHub sign-in and synced favorites on the hosted site.
// Files under api/_lib are not deployed as routes.
import { createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto';

export const SESSION_COOKIE = '__Host-dsh_session';
export const STATE_COOKIE = '__Host-dsh_oauth';
export const SESSION_TTL_SECONDS = 30 * 24 * 60 * 60;
export const STATE_TTL_SECONDS = 10 * 60;
export const MAX_FAVORITES = 200;
const RETURN_ROUTE = /^#[A-Za-z0-9/_:%.-]{0,200}$/;
const AVATAR = /^https:\/\/avatars\.githubusercontent\.com\/(?:u\/\d{1,12}|[A-Za-z0-9-]{1,39})(?:\?[A-Za-z0-9=&._-]{0,64})?$/;
const LOGIN = /^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$/;
const ARTIFACT_ID = /^[A-Za-z0-9:_.-]{1,160}$/;
const REPOSITORY_URL = /^https:\/\/github\.com\/[A-Za-z0-9-]{1,39}\/[A-Za-z0-9_.-]{1,100}$/;
const SHA = /^[0-9a-f]{40}$/;

export function authConfig(env = process.env) {
  const clientId = env.GITHUB_OAUTH_CLIENT_ID || '';
  const clientSecret = env.GITHUB_OAUTH_CLIENT_SECRET || '';
  const secret = env.DSH_FORGE_SESSION_SECRET || '';
  const kvUrl = env.KV_REST_API_URL || env.UPSTASH_REDIS_REST_URL || '';
  const kvToken = env.KV_REST_API_TOKEN || env.UPSTASH_REDIS_REST_TOKEN || '';
  const configured = !!(clientId && clientSecret && secret.length >= 32);
  const store = /^https:\/\//.test(kvUrl) && !!kvToken;
  return {
    configured,
    clientId,
    clientSecret,
    secret,
    // Likes need only the store: anonymous visitors can like without sign-in.
    likes: store,
    sync: configured && store,
    kvUrl: kvUrl.replace(/\/+$/, ''),
    kvToken
  };
}

export function base64url(buffer) {
  return Buffer.from(buffer).toString('base64').replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
}

function fromBase64url(text) {
  return Buffer.from(String(text).replace(/-/g, '+').replace(/_/g, '/'), 'base64');
}

function mac(value, secret) {
  return createHmac('sha256', secret).update(value).digest();
}

export function sign(payload, secret) {
  const body = base64url(JSON.stringify(payload));
  return body + '.' + base64url(mac(body, secret));
}

export function verify(token, secret, now = Math.floor(Date.now() / 1000)) {
  if (typeof token !== 'string' || token.length > 4096 || !secret) return null;
  const parts = token.split('.');
  if (parts.length !== 2 || !parts[0] || !parts[1]) return null;
  const expected = mac(parts[0], secret);
  const actual = fromBase64url(parts[1]);
  if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) return null;
  let payload;
  try {
    payload = JSON.parse(fromBase64url(parts[0]).toString('utf8'));
  } catch {
    return null;
  }
  if (!payload || typeof payload !== 'object' || !Number.isSafeInteger(payload.exp) || payload.exp <= now) return null;
  return payload;
}

export function parseCookies(header) {
  const cookies = {};
  for (const part of String(header || '').split(';')) {
    const index = part.indexOf('=');
    if (index < 1) continue;
    const name = part.slice(0, index).trim();
    if (name && !(name in cookies)) cookies[name] = part.slice(index + 1).trim();
  }
  return cookies;
}

export function cookie(name, value, maxAge) {
  return name + '=' + value + '; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=' + Math.max(0, Math.floor(maxAge));
}

export function clearCookie(name) {
  return cookie(name, '', 0);
}

export function randomToken(bytes = 32) {
  return base64url(randomBytes(bytes));
}

export function pkceChallenge(verifier) {
  return base64url(createHash('sha256').update(verifier).digest());
}

export function safeReturn(value) {
  return typeof value === 'string' && RETURN_ROUTE.test(value) ? value : '#plugins';
}

export function sessionUser(request, config) {
  const token = parseCookies(request.headers.get('cookie'))[SESSION_COOKIE];
  const payload = verify(token, config.secret);
  if (!payload || typeof payload.sub !== 'string' || !/^github:\d{1,12}$/.test(payload.sub)) return null;
  return payload;
}

export function publicUser(session) {
  if (!session) return null;
  return {
    id: session.sub,
    login: session.login,
    name: session.name || session.login,
    avatar_url: session.avatar || ''
  };
}

export function userFromGithub(profile, now = Math.floor(Date.now() / 1000)) {
  if (!profile || !Number.isSafeInteger(profile.id) || profile.id <= 0 || !LOGIN.test(String(profile.login || ''))) {
    throw new Error('GitHub returned an unexpected profile');
  }
  const avatar = typeof profile.avatar_url === 'string' && AVATAR.test(profile.avatar_url) ? profile.avatar_url : '';
  const name = typeof profile.name === 'string' ? profile.name.replace(/[\u0000-\u001f\u007f]/g, '').slice(0, 80) : '';
  return {
    sub: 'github:' + profile.id,
    login: profile.login,
    name: name || profile.login,
    avatar,
    iat: now,
    exp: now + SESSION_TTL_SECONDS
  };
}

// Mutations must come from this site; SameSite=Lax already withholds the cookie
// from cross-site subrequests, and this check also rejects cross-origin fetches.
export function sameOrigin(request) {
  const origin = request.headers.get('origin');
  if (!origin) return false;
  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false;
  }
}

export function json(body, status = 200, headers = {}) {
  return Response.json(body, {
    status,
    headers: { 'Cache-Control': 'no-store', ...headers }
  });
}

function text(value, limit) {
  return typeof value === 'string' ? value.replace(/[\u0000-\u001f\u007f]/g, ' ').slice(0, limit) : '';
}

// Favorites are stored as small display records, never as trusted catalog data:
// the browser re-reads catalog records by id before acting on them.
export function sanitizeFavorites(value) {
  if (!Array.isArray(value)) throw new Error('favorites must be an array');
  const seen = new Set();
  const favorites = [];
  for (const item of value.slice(0, MAX_FAVORITES * 2)) {
    if (!item || typeof item !== 'object') continue;
    const id = String(item.id || '');
    if (!ARTIFACT_ID.test(id) || seen.has(id) || !['plugin', 'fork'].includes(item.type)) continue;
    seen.add(id);
    const url = typeof item.url === 'string' && REPOSITORY_URL.test(item.url) ? item.url : '';
    favorites.push({
      id,
      type: item.type,
      slug: text(item.slug, 200),
      owner: text(item.owner, 80),
      name: text(item.name, 120),
      description: text(item.description, 300),
      url,
      head_sha: typeof item.head_sha === 'string' && SHA.test(item.head_sha) ? item.head_sha : null,
      starsLabel: text(item.starsLabel, 16),
      github_stars: Number.isSafeInteger(item.github_stars) && item.github_stars >= 0 ? item.github_stars : null,
      language: text(item.language, 40),
      licenseLabel: text(item.licenseLabel, 60),
      licenseOk: item.licenseOk === true,
      pushed_at: typeof item.pushed_at === 'string' && Number.isFinite(Date.parse(item.pushed_at)) ? item.pushed_at.slice(0, 32) : null,
      topics: Array.isArray(item.topics) ? item.topics.filter(topic => typeof topic === 'string').slice(0, 8).map(topic => text(topic, 40)) : [],
      saved_at: Number.isSafeInteger(item.saved_at) ? item.saved_at : null
    });
    if (favorites.length >= MAX_FAVORITES) break;
  }
  return favorites;
}

export async function kv(config, command, fetcher = fetch) {
  const response = await fetcher(config.kvUrl, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + config.kvToken, 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
    signal: AbortSignal.timeout(8000)
  });
  if (!response.ok) throw new Error('Favorites store returned ' + response.status);
  const payload = await response.json();
  if (payload && payload.error) throw new Error('Favorites store rejected the request');
  return payload ? payload.result : null;
}

export function favoritesKey(session) {
  return 'dsh-forge:favorites:v1:' + session.sub;
}

export async function kvPipeline(config, commands, fetcher = fetch) {
  const response = await fetcher(config.kvUrl + '/pipeline', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + config.kvToken, 'Content-Type': 'application/json' },
    body: JSON.stringify(commands),
    signal: AbortSignal.timeout(8000)
  });
  if (!response.ok) throw new Error('Store returned ' + response.status);
  const payload = await response.json();
  if (!Array.isArray(payload) || payload.length !== commands.length || payload.some(item => !item || item.error)) {
    throw new Error('Store rejected the request');
  }
  return payload.map(item => item.result);
}
