# Accounts and synced favorites

The hosted site (<https://dsh-forge.vercel.app/>) can offer **Sign in with
GitHub**. Signing in only syncs favorites across devices; browsing, favorites
in the current browser, and the desktop launcher all work without an account.

## What Forge stores

- A signed, HttpOnly, `Secure`, `SameSite=Lax` session cookie
  (`__Host-dsh_session`, 30 days) holding your GitHub user ID, login, display
  name, and avatar URL.
- One favorites record per user in the configured key-value store: up to 200
  small display records (id, type, name, owner, description, repository URL,
  and similar). Favorites are never treated as trusted catalog data; the page
  re-reads the catalog before acting on an item.

Forge requests **no OAuth scopes**. It uses the one-time GitHub token only to
read your public profile, then revokes it; no GitHub token is stored.

## How sign-in works

`/api/auth/login` redirects to GitHub with a random `state` and a PKCE
(`S256`) challenge, both bound to a short-lived signed cookie.
`/api/auth/callback` verifies the state, exchanges the code with the PKCE
verifier, reads the profile, revokes the token, and sets the session cookie.
`/api/auth/session` reports the signed-in user; `POST /api/auth/session` signs
out. `/api/favorites` supports `GET`, `PUT`, and `DELETE`; writes must come
from the same origin.

On first sign-in, favorites already saved in the browser are merged with the
account's list (account items first), so nothing is lost.

## Enabling it on a deployment

Sign-in stays hidden until all three auth variables are set; sync additionally
needs the key-value store.

| Variable | Purpose |
| --- | --- |
| `GITHUB_OAUTH_CLIENT_ID` | GitHub OAuth app client ID |
| `GITHUB_OAUTH_CLIENT_SECRET` | GitHub OAuth app client secret |
| `DSH_FORGE_SESSION_SECRET` | 32+ random characters used to sign cookies (`openssl rand -base64 48`) |
| `KV_REST_API_URL`, `KV_REST_API_TOKEN` | Upstash Redis REST endpoint (Vercel's Upstash integration sets these; `UPSTASH_REDIS_REST_*` also work) |

1. Create a GitHub OAuth app. Set the **Authorization callback URL** to
   `https://<your-domain>/api/auth/callback`.
2. Add an Upstash Redis store to the Vercel project.
3. Add the variables above to the Vercel project and redeploy.

Rotating `DSH_FORGE_SESSION_SECRET` signs everyone out. Deleting a user's key
(`dsh-forge:favorites:v1:github:<id>`) or calling `DELETE /api/favorites`
removes their synced list.
