# Sector Signal web

The Next.js (App Router) frontend for the sector signal dashboard. It replaces
the Streamlit app in `dashboard/` and reads the same data the pipeline writes.
Design: [`docs/superpowers/specs/2026-10-19-nextjs-frontend-design.md`](../docs/superpowers/specs/2026-10-19-nextjs-frontend-design.md).

Routes:

- `/[sector]/feed`, `/[sector]/patterns`, `/[sector]/themes`, `/[sector]/insights`
- `/login`
- `/api/health`, `/api/ready`
- `/api/logo/[domain]`

Streamlit stays live until cutover.

## Run locally

```
cp .env.example .env.local
# Set AUTH_SECRET in .env.local; sign-in fails without it:
echo "AUTH_SECRET=$(openssl rand -base64 32)" >> .env.local
pnpm install
pnpm dev
```

Open http://localhost:3000 and sign in with `AUTH_DEV_PASSWORD` (the dev
password form only exists under `pnpm dev`).

## Checks

```
pnpm test
pnpm typecheck
```

`test/` holds parity tests: they compare the TypeScript logic with fixtures
exported from the Python dashboard code, so the port keeps matching Streamlit.
To regenerate the fixtures after a change to the Python logic, run from the
repo root:

```
.venv/bin/python scripts/export_parity_fixtures.py
```

The fixtures are the oracle. The Python code is the reference; the Next.js
port must match it, not the other way round.

## Environment

Set in `web/.env.local` locally, or as runtime env on stage. The source of
truth is `.env.example`.

| Variable | Needed | Purpose |
|---|---|---|
| `AUTH_SECRET` | everywhere | Auth.js secret, `openssl rand -base64 32`; sign-in fails without it |
| `AUTH_URL` | stage | Public URL of the app |
| `AUTH_MICROSOFT_ENTRA_ID_ID` | stage | Entra app registration client ID |
| `AUTH_MICROSOFT_ENTRA_ID_SECRET` | stage | Entra client secret |
| `AUTH_MICROSOFT_ENTRA_ID_ISSUER` | stage | `https://login.microsoftonline.com/<tenant id>/v2.0` |
| `AUTH_REQUIRED_GROUP_ID` | stage | Staff group allowed to sign in; unset, production refuses every Entra sign-in |
| `AUTH_DEV_PASSWORD` | local | Password for the dev sign-in; ignored outside `pnpm dev` |
| `DATA_DIR` | optional | Local folder of sector data (default `../data`) |
| `CONFIG_DIR` | optional | Local folder of sector config (default `../config`) |
| `DATA_BASE_URL` | stage | Raw URL of `data/`, ending in `/`; read instead of `DATA_DIR` |
| `CONFIG_BASE_URL` | stage | Raw URL of `config/`, ending in `/`; read instead of `CONFIG_DIR` |
| `LOGO_DEV_TOKEN` | optional | logo.dev token for source logos; server-side only |

Locally, `DATA_BASE_URL` can point at the `main` branch on GitHub to see the
latest data rather than whatever branch is checked out.

### Entra app registration

The app registration needs:

- redirect URI `https://<host>/api/auth/callback/microsoft-entra-id`
  (and `http://localhost:3000/api/auth/callback/microsoft-entra-id` for local
  testing);
- the **groups** claim in the ID token, so `AUTH_REQUIRED_GROUP_ID` can be
  checked.

A user in more than 200 groups gets a groups *overage* claim instead of the
list (Entra puts a Graph link in `_claim_names`), so the check can't see the
staff group and they are denied ("Your account doesn't have access"). If that
bites, limit the claim to groups assigned to the application (Token
configuration -> groups claim -> "Groups assigned to the application").

## Docker

Build from the **repo root** (the Dockerfile copies `data/` and `config/` from
there):

```
docker build -f web/Dockerfile --build-arg BUILD_TAG=local -t sector-signal-web .
docker run --rm -p 3000:3000 \
  -e AUTH_SECRET="$(openssl rand -base64 32)" -e AUTH_URL=http://localhost:3000 \
  -e AUTH_MICROSOFT_ENTRA_ID_ID -e AUTH_MICROSOFT_ENTRA_ID_SECRET -e AUTH_MICROSOFT_ENTRA_ID_ISSUER \
  -e AUTH_REQUIRED_GROUP_ID \
  sector-signal-web
```

The container runs in production mode, so the dev password sign-in is off:
without the Entra variables the login page says "Sign-in isn't set up yet".

`BUILD_TAG` is reported by `/api/health`. The image runs as uid 1001 under
tini. The base image is `registry.pressassociation.io/node`, which needs the PA
VPN.

## Not done yet

From the spec's out-of-scope list:

- Marketplace of verified sources (waits for the source list).
- "New sector", Claude drafting and "Add to watchlist" (need the backend to save).
- `ApiDataSource` (needs the read API).
- Argo chart, CI, secrets and stage deployment.
- Removing Streamlit (one commit at cutover).
