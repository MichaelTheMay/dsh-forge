// GET/PUT/DELETE /api/favorites → the signed-in user's synced favorites.
import {
  authConfig, favoritesKey, json, kv, sameOrigin, sanitizeFavorites, sessionUser
} from './_lib/session.mjs';

const MAX_BODY_BYTES = 256 * 1024;

export async function handleFavorites(request, { env = process.env, fetcher = fetch, now = Date.now() } = {}) {
  const config = authConfig(env);
  if (!config.sync) return json({ error: 'Favorites sync is not configured for this deployment' }, 503);
  const session = sessionUser(request, config);
  if (!session) return json({ error: 'Sign in to sync favorites' }, 401);
  if (request.method !== 'GET' && !sameOrigin(request)) return json({ error: 'Same-origin request required' }, 403);
  const key = favoritesKey(session);
  try {
    if (request.method === 'GET') {
      const stored = await kv(config, ['GET', key], fetcher);
      let record = null;
      try { record = stored ? JSON.parse(stored) : null; } catch {}
      return json({
        favorites: record ? sanitizeFavorites(record.favorites) : [],
        updated_at: record && Number.isSafeInteger(record.updated_at) ? record.updated_at : null
      });
    }
    if (request.method === 'PUT') {
      if (!/^application\/json\b/.test(request.headers.get('content-type') || '')) {
        return json({ error: 'Content-Type must be application/json' }, 415);
      }
      const raw = await request.text();
      if (Buffer.byteLength(raw) > MAX_BODY_BYTES) return json({ error: 'Favorites payload is too large' }, 413);
      let body;
      try { body = JSON.parse(raw); } catch { return json({ error: 'Body must be JSON' }, 400); }
      let favorites;
      try { favorites = sanitizeFavorites(body && body.favorites); } catch (error) { return json({ error: error.message }, 400); }
      const record = { favorites, updated_at: now };
      await kv(config, ['SET', key, JSON.stringify(record)], fetcher);
      return json(record);
    }
    if (request.method === 'DELETE') {
      await kv(config, ['DEL', key], fetcher);
      return json({ favorites: [], updated_at: null });
    }
    return json({ error: 'Method not allowed' }, 405, { Allow: 'GET, PUT, DELETE' });
  } catch {
    return json({ error: 'Favorites are temporarily unavailable' }, 503);
  }
}

export function GET(request) { return handleFavorites(request); }
export function PUT(request) { return handleFavorites(request); }
export function DELETE(request) { return handleFavorites(request); }
