// GET /api/auth/login?return=#forks → GitHub authorization with state and PKCE.
import {
  STATE_COOKIE, STATE_TTL_SECONDS, authConfig, cookie, json, pkceChallenge, randomToken, safeReturn, sign
} from '../_lib/session.mjs';

export function handleLogin(request, { env = process.env, now = Math.floor(Date.now() / 1000) } = {}) {
  const config = authConfig(env);
  if (!config.configured) return json({ error: 'Sign-in is not configured for this deployment' }, 503);
  const url = new URL(request.url);
  const state = randomToken();
  const verifier = randomToken(48);
  const returnTo = safeReturn(url.searchParams.get('return'));
  const authorize = new URL('https://github.com/login/oauth/authorize');
  authorize.searchParams.set('client_id', config.clientId);
  authorize.searchParams.set('redirect_uri', url.origin + '/api/auth/callback');
  // No scopes: Forge only needs the public profile to key synced favorites.
  authorize.searchParams.set('scope', '');
  authorize.searchParams.set('state', state);
  authorize.searchParams.set('code_challenge', pkceChallenge(verifier));
  authorize.searchParams.set('code_challenge_method', 'S256');
  authorize.searchParams.set('allow_signup', 'true');
  const pending = sign({ state, verifier, return: returnTo, exp: now + STATE_TTL_SECONDS }, config.secret);
  return new Response(null, {
    status: 302,
    headers: {
      Location: authorize.toString(),
      'Set-Cookie': cookie(STATE_COOKIE, pending, STATE_TTL_SECONDS),
      'Cache-Control': 'no-store'
    }
  });
}

export function GET(request) {
  return handleLogin(request);
}
