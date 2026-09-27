// GET /api/auth/session → who is signed in; POST /api/auth/session {action:"logout"} → sign out.
import { SESSION_COOKIE, authConfig, clearCookie, json, publicUser, sameOrigin, sessionUser } from '../_lib/session.mjs';

export function handleSession(request, { env = process.env } = {}) {
  const config = authConfig(env);
  if (!config.configured) return json({ configured: false, sync: false, user: null });
  return json({ configured: true, sync: config.sync, user: publicUser(sessionUser(request, config)) });
}

export async function handleLogout(request, { env = process.env } = {}) {
  if (!sameOrigin(request)) return json({ error: 'Same-origin request required' }, 403);
  const config = authConfig(env);
  return json({ configured: config.configured, sync: config.sync, user: null }, 200, { 'Set-Cookie': clearCookie(SESSION_COOKIE) });
}

export function GET(request) {
  return handleSession(request);
}

export function POST(request) {
  return handleLogout(request);
}
