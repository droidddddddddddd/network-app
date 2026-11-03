# NETWORK — Build Your Network. Build Your Net Worth.

Social and business networking for crypto/Solana people: Networks (Personal, Trading, KOL, Alpha Communities, Marketing, Project), Network-to-Network connections with per-type sharing permissions, Opportunities, Network Passport, earned reputation, Network Rankings, Project Launch Rooms, real-time chat and DMs.

**Stack:** FastAPI · SQLAlchemy 2 · Alembic · SQLite locally, PostgreSQL (psycopg 3) in production · bcrypt + PyJWT (httpOnly cookie) · vanilla JS SPA (no build step) · in-process WebSocket hub · DexScreener public API (free, keyless).

## Install on your phone (PWA)
NETWORK installs like an app, with its own home-screen icon and a full-screen window. Open the live site over HTTPS first.
- **iPhone / iPad (Safari):** open the site in Safari, tap the **Share** button (square with an arrow), scroll down, tap **Add to Home Screen**, then tap **Add**. Other iOS browsers may not offer this, so use Safari.
- **Android (Chrome):** open the site. Tap **Install** on the "Install NETWORK" banner, or go to Settings → Install app. You can also use Chrome's ⋮ menu → **Install app** / **Add to Home screen**.
- Updates install automatically: after a deploy, the app picks up the new version the next time it is opened. Offline, the app shows an "You're offline" page. Your data is never stored in the offline cache.

## Local development
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head          # creates ./network.db (SQLite)
python -m app.seed            # optional demo data (all flagged DEMO); login alpha_annie / demo1234
uvicorn app.main:app --reload --port 8793
# open http://localhost:8793
```
Set `DISABLE_TRACKER=1` to stop the background DexScreener price tracker.

## Tests and checks
```bash
python -m pytest -q                    # API acceptance tests (Alembic-migrated temp DB) + restart-persistence test
TEST_DATABASE_URL=postgresql://user@127.0.0.1:5432/network_test python -m pytest -q   # same suite on Postgres (+ two-process realtime test). WARNING: drops that DB's public schema
NETWORK_LIVE_TESTS=1 python -m pytest -q tests/test_live.py   # read-only Solana mainnet checks (public RPC, or HELIUS_API_KEY)
python -m py_compile app/*.py && node --check static/app.js
DATABASE_URL=postgresql://u:p@localhost/x alembic upgrade head --sql > /dev/null   # Postgres DDL renders
```

## Environment variables
| Var | Required | Notes |
|---|---|---|
| `DATABASE_URL` | prod | Postgres URL. `postgres://` / `postgresql://` are converted to the psycopg 3 driver automatically. Empty → SQLite `./network.db`. |
| `JWT_SECRET` (or `SECRET_KEY`) | prod | Signs session tokens. With `ENV=production` the app refuses to start without it. Never commit it. |
| `ENV` | prod | `production` enables secure cookies and the secret check. |
| `CORS_ORIGINS` | no | Comma-separated extra allowed origins. |
| `DISABLE_TRACKER` | no | `1` disables the DexScreener tracker loop. |
| `UPLOAD_DIR` | no | Upload directory (default `./uploads`). |
| `ENDORSE_MIN_ACCOUNT_HOURS` | no | Minimum account age before endorsing. |
| `PUBLIC_BASE_URL` | with OAuth | Public https address of the site, used to build the OAuth callback URLs. |
| `X_CLIENT_ID`, `X_CLIENT_SECRET` | no | "Continue with X". The buttons are hidden unless both are set. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | no | "Continue with Google". The buttons are hidden unless both are set. |
| `REALTIME_BACKEND` | no | `local` (default, single instance) or `postgres` (LISTEN/NOTIFY fan-out across several instances sharing one Postgres). |
| `CHAIN_MAX_FLOW_TXS` | no | How many of the dev wallet's latest token transactions are parsed for sold/transferred evidence (default 60). |

## Migrations
Schema changes go through Alembic only:
```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
Production runs `alembic upgrade head` on every start (see `render.yaml`).

## Production start command
```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```
Health check: `GET /health` → `{"ok": true, "realtime": "local", "db": "postgresql"}`.

## Deploy: GitHub + Render (free), step by step for non-developers
You need a GitHub account and a free Render account (render.com, "Sign in with GitHub").
1. Put the code on GitHub (a developer or your assistant can do this; your repo must be empty first):
   ```bash
   git remote add origin https://github.com/<you>/network-app.git
   git push -u origin main --tags
   ```
2. In Render click **New → Blueprint**, choose the `network-app` repo and click **Apply**. `render.yaml` (at the repo root) creates a free web service plus a free Postgres database. It also connects them, generates a random `JWT_SECRET`, and sets `ENV=production` and `STORAGE_BACKEND=db` (images are stored in the database, so they survive redeploys).
3. Render asks for the values marked "sync: false". You can leave them all blank except **ADMIN_USERNAMES**:
   - `ADMIN_USERNAMES`: the username you'll sign up with, e.g. `chris` (several: `chris,alice`). This is the only way to become a platform admin.
   - `HELIUS_API_KEY`: optional. It gives faster, more reliable Solana lookups. Without it the free public RPC is used.
   - `S3_*`, `SOLANA_RPC_URL`, `CORS_ORIGINS`: leave blank.
   - `PUBLIC_BASE_URL`, `X_*`, `GOOGLE_*`: leave blank for now. Fill them in later using "Sign in with X / Google" below. Until they're set, only password sign-up is shown.
4. Wait for "Live", then open `https://<service>.onrender.com/health`. It should show `{"ok":true,"db":"postgresql"}`.
5. **Make yourself admin:** open the site, sign up with exactly the username you put in `ADMIN_USERNAMES`, then reload. A **Moderation** link (platform queue, suspensions) works for you. To change admins later, go to Render → your service → **Environment**, edit `ADMIN_USERNAMES` and save. It redeploys automatically.
6. Demo data is **not** loaded in production. To load it on purpose, set `SEED_DEMO=true` and run `python -m app.seed` in the Render Shell.

Free-tier caveats:
- Free Postgres **expires after about 30 days**. Upgrade it or back it up (`pg_dump`) before then.
- Free web services sleep when idle, so the first request takes about 30–60 s.
- Uploaded images live in the database (2 MB cap each). For heavy use, switch to S3/R2 (`STORAGE_BACKEND=s3` plus the `S3_*` settings and `boto3`).
- **Single instance by default.** The realtime WebSocket hub (chat, notifications, calls) is in-process, and `render.yaml` pins `numInstances: 1`. To run more than one instance, set `REALTIME_BACKEND=postgres`. Every instance then relays realtime events through Postgres LISTEN/NOTIFY on the shared database (tested locally with two processes; not tested on Render). Rate limits are stored in the database, so they survive restarts.

## Sign in with X / Google (account linking), step by step
This lets people sign up, log in, and add **"X account verified (@handle)"** and **"Google account verified"** badges to their Network Passport. The badges prove the person controls that X or Google account. **They are not a government ID check**, and the app says so everywhere. NETWORK stores only the provider's account id, the X handle or the Google email, and the verified flag. Access tokens are thrown away immediately, and the app requests no permission to post. A Google email stays private unless the user turns on "Show email on Passport".

First, find your site address in Render (e.g. `https://network-app.onrender.com`). In Render → your service → **Environment**, set `PUBLIC_BASE_URL` to exactly that address, with no trailing slash. The two callback URLs are:
- X: `https://<render-url>/api/auth/oauth/x/callback`
- Google: `https://<render-url>/api/auth/oauth/google/callback`

**X (Twitter)**
1. Go to https://developer.x.com and sign in with the X account that will own the app. Sign up for the **Free** developer tier if asked, and describe the use as "Sign in with X for my community site".
2. In the Developer Portal open **Projects & Apps** and select your app (or create one), then click **User authentication settings → Set up**.
3. Choose these settings:
   - App permissions: **Read**.
   - Type of App: **Web App, Automated App or Bot** (a "confidential client").
   - Callback URI / Redirect URL: the X callback URL above.
   - Website URL: your site address.
   
   Save.
4. Open **Keys and tokens** and find **OAuth 2.0 Client ID and Client Secret**. Copy both. The secret is only shown once.
5. In Render → Environment, set `X_CLIENT_ID` and `X_CLIENT_SECRET` and save. The site redeploys, and **Continue with X** appears on the login page.

**Google**
1. Go to https://console.cloud.google.com, create a project (e.g. "NETWORK") and select it.
2. Open **APIs & Services → OAuth consent screen** (also called "Google Auth Platform → Branding/Audience").
   - Choose **External**.
   - Fill in the app name, your support email and your site address.
   - Scopes: `openid`, `email`, `profile` (the defaults; no sensitive scopes).
   - While the app is in "Testing", only the test users you add can sign in. Click **Publish app** when you're ready for everyone. These basic scopes don't need Google review.
3. Open **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   - Application type: **Web application**.
   - Authorized JavaScript origins: your site address.
   - Authorized redirect URIs: the Google callback URL above.
   
   Create, then copy the **Client ID** and **Client secret**.
4. In Render → Environment, set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` and save. **Continue with Google** appears after the redeploy.

How it behaves:
- The flow is OAuth 2.0 with PKCE. It uses a single-use `state` tied to the browser by a cookie, with a 10-minute expiry. Google sign-in also checks the OpenID nonce, issuer, audience and expiry.
- Signing in with a Google account whose email already belongs to a password account does **not** merge the accounts. The person is told to log in with their password and link Google from **Settings → Linked accounts & login**.
- An X or Google account can be linked to only one Passport. You can't unlink your last way to log in, so set a password first. Accounts created through X get no email; they can set a password in Settings.
- X account age and follower count (as reported by X at sign-in) are shown as light context against throwaway accounts. They add no reputation and can't be bought.
- **Not yet tested against the real X and Google services.** The full flow is covered by tests against a mocked provider (PKCE, state, nonce, collisions). The first real sign-in can only happen after the apps above are registered.

## Network bans
Network Founders, and Admins who have the "moderate" permission, can ban a member from **their own Network**. The ban can last N hours or be indefinite. Use the **Ban** button on the Network Members tab, or "Ban from Network" in the Network moderation queue. Rules:
- A banned person can't post, reply or rejoin in that Network. The rest of NETWORK is unaffected.
- The Founder can't be banned, and only the Founder can ban an Admin.
- Each ban is audit-logged and the person is notified. On the Network page they see the reason and can send **one appeal**, which notifies the moderators.
- Moderators lift bans from the "Banned from this Network" list. Lifting restores the previous membership.
- Platform-wide suspensions remain for `ADMIN_USERNAMES` only.

## Environment variables
See `.env.example` for the full list with comments.

## Moderation
- Anyone can report a post, a user (Passport → Report) or a Network (header → Report).
- Network moderators (role permission "moderate") see their Network's queue under the **Moderation** tab. They can dismiss, hide a post or remove a post.
- Platform admins (`ADMIN_USERNAMES`) see every report at `#/moderation` and can also suspend users, either for N hours or indefinitely. Suspended users can't post, chat, DM, endorse or start calls.
- Every action is audit-logged and every reporter is notified. Accounts younger than 24 h get stricter rate limits.

## Verification (what each label proves)
- **Wallet ownership verified:** the user signed a one-time NETWORK message with that wallet (signMessage only, never a transaction).
- **Project domain verified (example.com):** a DNS TXT record or `/.well-known/network-verify.txt` matched a code we issued.
- **Dev wallet verified: signed by the creator of $TICKER (method: …):** the signer is the token's creator. The creator is found in this order:
  1. The pump.fun bonding-curve creator field.
  2. The creation transaction. NETWORK finds the mint's oldest signature (one oldest-first request with Helius, otherwise paging back up to `CHAIN_MAX_SIG_PAGES`×1000). From that transaction it takes the pump.fun create instruction's `creator` argument if present, otherwise the fee payer. It never treats "any signer" as the creator, because bundled launches have several signers. A found creator is cached permanently.
  3. Helius DAS verified creators or authority.
  4. The Metaplex or Token-2022 metadata update authority.
  
  If none of these settles it, the result is **"Couldn't determine the creator"**, never a guess. Verification proves control of the creator wallet only, not that the project is safe. One token can belong to one Network. Re-checkable.
- **Dev wallet evidence (read-only):** shows the creator wallet's current holding, plus what happened to its tokens, parsed from its token-account history:
  - **Sold:** the tokens left the wallet in a transaction that ran a DEX program (pump.fun, PumpSwap, Raydium, Jupiter, Meteora, Orca). The venue is named.
  - **Transferred:** a plain transfer to another wallet, with the destination shown. That wallet may belong to the dev, so it is not called a sale.
  - **Burned / unclassified:** the tokens left with no recipient.
  
  Only the latest `CHAIN_MAX_FLOW_TXS` token transactions are checked, and the panel says so when history was cut off.
- **Metadata authority verified:** the signer is the token's Metaplex (or Token-2022 metadata extension) update authority.
- **CTO (community takeover):** holders sign support. Balances are re-read live. The threshold is ≥ `CTO_MIN_BACKERS` wallets holding ≥ `CTO_MIN_PCT`% of circulating supply. Dev, curve, pool and burn addresses are excluded. Wallets younger than 24 h count half. Shared-funder clusters are shown. Support lapses when holders sell. Competing claims are shown as leading or competing.
- **X account verified (@handle) / Google account verified:** account-ownership linking through OAuth sign-in, **not a government ID check**. There is no "identity verified" label. The old KYC placeholder was removed, and `/api/verifications` now returns 410.

## Safety principles
- Never asks for or stores seed phrases or private keys. Wallet flows only sign a human-readable message that says it is not a transaction.
- Nothing is labelled "verified" unless the server checked it. "Trading" means calls tracked server-side with DexScreener's price at post time.
- Reputation is earned from records only. Member or follower counts are not a ranking factor, and nothing can be bought. Rankings are snapshots refreshed every `RANKINGS_TTL` seconds ("Updated X min ago").
- CSRF uses a required `x-csrf: 1` header plus SameSite cookies. Other protections: DB-backed rate limits, upload magic-byte and size validation, CSP and security headers, audit logs, and private content and activity-sharing choices enforced server-side.
