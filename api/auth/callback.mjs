// GET /api/auth/callback?code&state → verify, exchange with PKCE, set a signed session.
import { timingSafeEqual } from 'node:crypto';
import {
  SESSION_COOKIE, SESSION_TTL_SECONDS, STATE_COOKIE, authConfig, clearCookie, cookie, parseCookies,
  safeReturn, sign, userFromGithub, verify
} from '../_lib/session.mjs';

function redirect(location, cookies) {
  const headers = new Headers({ Location: location, 'Cache-Control': 'no-store' });
  for (const value of cookies) headers.append('Set-Cookie', value);
  return new Response(null, { status: 302, headers });
}

function sameText(a, b) {
  const left = Buffer.from(String(a || ''));
  const right = Buffer.from(String(b || ''));
  return left.length === right.length && left.length > 0 && timingSafeEqual(left, right);
}

export async function handleCallback(request, { env = process.env, fetcher = fetch, now = Math.floor(Date.now() / 1000) } = {}) {
  const config = authConfig(env);
  const url = new URL(request.url);
  const pending = verify(parseCookies(request.headers.get('cookie'))[STATE_COOKIE], config.secret, now);
  const returnTo = safeReturn(pending && pending.return);
  const failed = reason => redirect('/?signin=' + reason + returnTo, [clearCookie(STATE_COOKIE)]);
  if (!config.configured) return failed('unavailable');
  if (url.searchParams.get('error')) return failed('cancelled');
  const code = url.searchParams.get('code') || '';
  if (!pending || !sameText(pending.state, url.searchParams.get('state')) || !/^[A-Za-z0-9_-]{1,128}$/.test(code)) {
    return failed('expired');
  }
  let access = '';
  try {
    const exchange = await fetcher('https://github.com/login/oauth/access_token', {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'dsh-forge-auth/1' },
      body: JSON.stringify({
        client_id: config.clientId,
        client_secret: config.clientSecret,
        code,
        redirect_uri: url.origin + '/api/auth/callback',
        code_verifier: pending.verifier
      }),
      signal: AbortSignal.timeout(10_000)
    });
    const token = exchange.ok ? await exchange.json() : null;
    access = token && typeof token.access_token === 'string' ? token.access_token : '';
    if (!access) return failed('rejected');
    const profileResponse = await fetcher('https://api.github.com/user', {
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: 'Bearer ' + access,
        'User-Agent': 'dsh-forge-auth/1',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      signal: AbortSignal.timeout(10_000)
    });
    if (!profileResponse.ok) return failed('rejected');
    const session = userFromGithub(await profileResponse.json(), now);
    return redirect('/' + returnTo, [
      clearCookie(STATE_COOKIE),
      cookie(SESSION_COOKIE, sign(session, config.secret), SESSION_TTL_SECONDS)
    ]);
  } catch {
    return failed('unavailable');
  } finally {
    // Forge keeps no GitHub token. Revoke it so it cannot outlive this request.
    if (access) {
      fetcher('https://api.github.com/applications/' + encodeURIComponent(config.clientId) + '/token', {
        method: 'DELETE',
        headers: {
          Accept: 'application/vnd.github+json',
          Authorization: 'Basic ' + Buffer.from(config.clientId + ':' + config.clientSecret).toString('base64'),
          'Content-Type': 'application/json',
          'User-Agent': 'dsh-forge-auth/1'
        },
        body: JSON.stringify({ access_token: access }),
        signal: AbortSignal.timeout(5_000)
      }).catch(() => {});
    }
  }
}

export function GET(request) {
  return handleCallback(request);
}
