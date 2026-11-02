# NETWORK — Build Your Network. Build Your Net Worth.

Social and business networking for crypto/Solana people: Networks (Personal, Trading, KOL, Alpha Communities, Marketing, Project), Network-to-Network connections with per-type sharing permissions, Opportunities, Network Passport, earned reputation, Network Rankings, Project Launch Rooms, real-time chat and DMs.

**Stack:** FastAPI · SQLAlchemy 2 · Alembic · SQLite locally, PostgreSQL (psycopg 3) in production · bcrypt + PyJWT (httpOnly cookie) · vanilla JS SPA (no build step) · in-process WebSocket hub · DexScreener public API (free, keyless).

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
Health check: `GET /health` → `{"ok": true, "db": "postgresql"}`.

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
4. Wait for "Live", then open `https://<service>.onrender.com/health`. It should show `{"ok":true,"db":"postgresql"}`.
5. **Make yourself admin:** open the site, sign up with exactly the username you put in `ADMIN_USERNAMES`, then reload. A **Moderation** link (platform queue, suspensions) works for you. To change admins later, go to Render → your service → **Environment**, edit `ADMIN_USERNAMES` and save. It redeploys automatically.
6. Demo data is **not** loaded in production. To load it on purpose, set `SEED_DEMO=true` and run `python -m app.seed` in the Render Shell.

Free-tier caveats:
- Free Postgres **expires after about 30 days**. Upgrade it or back it up (`pg_dump`) before then.
- Free web services sleep when idle, so the first request takes about 30–60 s.
- Uploaded images live in the database (2 MB cap each). For heavy use, switch to S3/R2 (`STORAGE_BACKEND=s3` plus the `S3_*` settings and `boto3`).
- **Single instance required.** The realtime WebSocket hub (chat, notifications, calls) is in-process. `render.yaml` pins `numInstances: 1`. Rate limits are stored in the database, so they survive restarts.

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
- **Dev wallet verified: signed by the creator of $TICKER (method: …):** the signer is the token's creator. That is the pump.fun bonding-curve creator, else the earliest transaction signer, else the Metaplex/Helius authority. This proves control of the creator wallet only, not that the project is safe. One token can belong to one Network. Re-checkable. The creator wallet balance is shown read-only.
- **Metadata authority verified:** the signer is the token's Metaplex update authority.
- **CTO (community takeover):** holders sign support. Balances are re-read live. The threshold is ≥ `CTO_MIN_BACKERS` wallets holding ≥ `CTO_MIN_PCT`% of circulating supply. Dev, curve, pool and burn addresses are excluded. Wallets younger than 24 h count half. Shared-funder clusters are shown. Support lapses when holders sell. Competing claims are shown as leading or competing.
- **Identity:** stays "needs KYC provider". No provider is connected, so it is never marked verified.

## Safety principles
- Never asks for or stores seed phrases or private keys. Wallet flows only sign a human-readable message that says it is not a transaction.
- Nothing is labelled "verified" unless the server checked it. "Trading" means calls tracked server-side with DexScreener's price at post time.
- Reputation is earned from records only. Member or follower counts are not a ranking factor, and nothing can be bought. Rankings are snapshots refreshed every `RANKINGS_TTL` seconds ("Updated X min ago").
- CSRF uses a required `x-csrf: 1` header plus SameSite cookies. Other protections: DB-backed rate limits, upload magic-byte and size validation, CSP and security headers, audit logs, and private content and activity-sharing choices enforced server-side.
