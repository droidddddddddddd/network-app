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

## Deploy: GitHub + Render (free)
1. Create an empty GitHub repo (no README), then:
   ```bash
   git remote add origin https://github.com/<you>/network-app.git
   git push -u origin main
   ```
2. Render → **New → Blueprint** → pick the repo. `render.yaml` (at the repo root, no `rootDir`) creates a free web service plus a free Postgres database, wires `DATABASE_URL`, generates `JWT_SECRET` and sets `ENV=production`.
3. Wait for the deploy, then open `https://<service>.onrender.com/health`.
4. Optional: open the Render Shell and run `python -m app.seed` for demo data.

Free-tier caveats:
- Free Postgres **expires after about 30 days**. Upgrade it or back it up (`pg_dump`) before then.
- Free web services sleep when idle, so the first request takes about 30–60 s.
- The disk is ephemeral, so uploaded images disappear on redeploy. Use object storage (S3/R2) for persistence.
- The WebSocket hub and rate limiter live in memory, so run a single instance (that's how the free tier works). Scaling out needs Redis.

## Safety principles
- Never asks for or stores seed phrases or private keys. Wallet addresses are display-only until a real verification provider exists.
- There are four separate verification types: wallet, identity, project and trading. Wallet, identity and project only create *pending* requests because no provider is connected. "Trading" only means calls tracked server-side with DexScreener's price at post time, labelled "Tracked call (DexScreener price at post time)". Nothing is labelled "verified" unless it really was.
- Reputation is earned from records only. Member or follower counts are not a ranking factor, and nothing can be bought.
- CSRF uses a required `x-csrf: 1` header plus SameSite cookies. Other protections: rate limits, upload type/size validation, CSP and security headers, audit logs for admin actions, and private content enforced server-side.
