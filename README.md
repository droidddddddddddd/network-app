# NETWORK

**Build Your Network. Build Your Net Worth.**

NETWORK is a social crypto intelligence and networking platform for traders, founders, developers, KOLs, and communities. It combines social feeds, member-owned Networks, collaboration opportunities, reputation, timestamped token calls, and read-only Solana market research.

This repository is the existing FastAPI application, extended with a Chrome companion for X. It is not an exchange or trading terminal.

## Release scope

Included:
- X sign-in / signup using OAuth 2.0 Authorization Code + PKCE.
- Network Passports, profiles, posts, replies, endorsements, feeds, networks, memberships, connection requests, and explicit sharing permissions.
- Opportunities, applications, messages, notifications, invites, events, moderation, achievements, and reputation rankings.
- Proof-of-Call: users publish token calls which are timestamped and tracked against read-only market data. A call is not proof that the author bought or sold the token.
- Read-only Solana and DexScreener research, including token prices, market caps, liquidity, and creator evidence where available.
- Responsive web app / PWA and beta Chrome X companion panel.

Explicitly excluded:
- Live trading, swaps, buy/sell execution, orders, transaction construction, and transaction signing.
- Wallet connections, wallet signing, wallet-based identity, holder backing, and transaction permissions in this release.
- Seed phrase or private-key collection or storage.
- Automated X posting, likes, follows, or scraping.

Wallet-dependent API routes are disabled by default (`ENABLE_WALLET_FEATURES=0`). Existing database fields and legacy records are preserved for migration safety; the application does not ask users to connect or enter a wallet. Re-enabling wallet features requires a separate product decision.

See [RELEASE_SCOPE.md](RELEASE_SCOPE.md) and [BUILD_NOTES.md](BUILD_NOTES.md) for the exact scope and implementation notes.

## Stack

- Python 3.13, FastAPI, SQLAlchemy, Alembic
- PostgreSQL in production; SQLite for local development
- Vanilla HTML/CSS/JavaScript frontend
- DexScreener and Solana RPC reads only
- Render deployment blueprint (`render.yaml`)

## Install on your phone (PWA)
NETWORK installs like an app, with its own home-screen icon and a full-screen window. Open the live site over HTTPS first.
- **iPhone / iPad (Safari):** open the site in Safari, tap the **Share** button (square with an arrow), scroll down, tap **Add to Home Screen**, then tap **Add**. Other iOS browsers may not offer this, so use Safari.
- **Android (Chrome):** open the site. Tap **Install** on the "Install NETWORK" banner, or go to Settings → Install app. You can also use Chrome's ⋮ menu → **Install app** / **Add to Home screen**.
- Updates install automatically: after a deploy, the app picks up the new version the next time it is opened. Offline, the app shows an "You're offline" page. Your data is never stored in the offline cache.

## Local setup

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

For local development, leave `DATABASE_URL` empty to use SQLite. Set a strong `JWT_SECRET` for any shared or deployed environment. The app reads environment variables; it does not automatically load a `.env` file unless your local runner does so. You can export the values in your shell or use a local dotenv runner.

## Environment variables

The full commented reference is `.env.example`; never commit real values.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | production | PostgreSQL URL; `postgres://` / `postgresql://` normalize to psycopg 3. Production refuses missing/SQLite URLs. Empty uses SQLite locally only. |
| `JWT_SECRET` (or `SECRET_KEY`) | production | Strong randomly generated session-signing secret. Never commit, log or share. |
| `ENV` | production | Set `production` for Secure cookies and startup checks. |
| `PUBLIC_BASE_URL` | X sign-in | Exact public HTTPS URL, no trailing slash. |
| `X_CLIENT_ID`, `X_CLIENT_SECRET` | X sign-in | Server-only OAuth credentials; without both, new signup is unavailable (no password fallback). |
| `ENABLE_WALLET_FEATURES` | this release | Keep `0`. Wallet signing/backing endpoints return 404; stale profile wallets are hidden and preserved in the database. |
| `EXTENSION_ORIGINS` | companion CORS | Exact comma-separated `chrome-extension://<id>` origins, no wildcard. Public lookups and origin-bound companion bearer sessions; never web cookies. |
| `ENABLE_GOOGLE_RECOVERY` | no | Default `0`. Temporary `1` permits existing linked Google identities to recover and link X, never Google signup/linking. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | recovery only | Retain until Google-only members have migrated; not advertised as public login. |
| `ADMIN_USERNAMES` | moderation | Comma-separated administrator usernames; not an account-recovery bypass. |
| `CORS_ORIGINS` | no | Extra trusted web origins for the existing credentialed web API. Do not use wildcards or add extension IDs here. |
| `DISABLE_TRACKER` | no | `1` disables background research tracking (use for tests). |
| `REALTIME_BACKEND` | no | `local` for one instance; `postgres` for LISTEN/NOTIFY fan-out with shared Postgres. |
| `STORAGE_BACKEND` | production | `db` (Render default) or `s3`; local disk is development-only. |
| `UPLOAD_DIR`, `S3_*` | no | Optional upload directory or object storage configuration. |
| `SOLANA_RPC_URL`, `HELIUS_API_KEY` | no | Server-only read-only RPC configuration. Never print full RPC URLs or the key. |
| `ENDORSE_MIN_ACCOUNT_HOURS` | no | Minimum account age before endorsing. |
| `CHAIN_MAX_FLOW_TXS` | no | Bounded creator evidence history (default 60); limited history is labelled. |

## Migrations and production start

Schema changes use Alembic; production runs migrations on startup from the repository root:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```

Check `/health` reports `ok: true` and `db: postgresql`. Keep Postgres and uploads persistent across redeploys; do not rely on Render's ephemeral disk or SQLite. For more than one web instance use `REALTIME_BACKEND=postgres`.

## Render deployment

1. Use the repository root (no Render Root Directory override). Push/deploy only after owner approval.
2. In Render, create a Blueprint deployment from that repository and select `render.yaml`.
3. Create the PostgreSQL database and web service from the Blueprint.
4. In the web service's Environment settings, configure:
   - `PUBLIC_BASE_URL` — the public HTTPS site URL.
   - `X_CLIENT_ID` and `X_CLIENT_SECRET` — the X OAuth app credentials.
   - `HELIUS_API_KEY` or `SOLANA_RPC_URL` — optional, for more reliable read-only chain data.
   - `ADMIN_USERNAMES` — comma-separated platform administrator usernames.
   - Any required storage or CORS settings for your deployment.
5. In the X Developer Portal, set the callback URL to:
   `https://YOUR-DOMAIN/api/auth/oauth/x/callback`
6. Confirm the callback URL and `PUBLIC_BASE_URL` match exactly, then redeploy and test X sign-in.

Do not put credentials in source code, GitHub commits, screenshots, or browser-extension files. Rotate any credential that has been exposed. Keep the GitHub repository private unless you intentionally want the source public.

## X authentication

The public login and signup experience offers X only. The first successful X authorization creates a NETWORK account; later authorizations log the user into the same account. X OAuth uses PKCE, a single-use state value bound to the browser, and a short expiry. The current scopes are read-only profile access; NETWORK does not request permission to post to X.

Legacy Google callback code and password authentication data are retained for account-migration safety, but they are not shown as public sign-in choices. Existing password-only members can use the unadvertised `#/legacy-login` route once, then link X from Settings. Do not delete legacy password hashes or linked-account records until a tested recovery/linking path exists for every affected user. Google-only members use the administrator-enabled recovery procedure below; new Google signups and new Google linking are rejected. New password signups are rejected by `/api/auth/register` (403); legacy password login remains available.

### Google-only account recovery (administrator runbook)

1. Keep the existing Google OAuth app and linked-account records. Configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, its exact callback `https://YOUR-DOMAIN/api/auth/oauth/google/callback`, and `PUBLIC_BASE_URL` on the server. Never share these secrets with the extension or put them in support messages.
2. Temporarily set `ENABLE_GOOGLE_RECOVERY=1` in Render. Direct the member to `https://YOUR-DOMAIN/api/auth/oauth/google/start` in a **normal browser tab**. There is deliberately no public Google signup button. Only a Google subject already linked to a NETWORK account can log in; matching email alone never merges accounts. PKCE, nonce and browser-bound state still apply. Unknown identities receive a generic recovery failure, not a new account.
3. After recovering the original account, go to **Settings → Linked accounts & login → Link X**. Do not sign up a separate X account first. Test a fresh X login reaches the same Passport.
4. Set `ENABLE_GOOGLE_RECOVERY=0` after affected members migrate. Do not delete the old records or reset passwords/link identities based merely on an email claim. If Google credentials are unavailable, restore the original provider setup through the administrator; there is no identity-bypass endpoint.

The recovery-to-X flow is covered with mocked providers. Real provider recovery and real X login remain deployment checks.

## Proof-of-Call and market research

Calls are published records with a token mint, author, timestamp, and available market snapshot. The tracker periodically compares read-only DexScreener market data with the call's entry snapshot and records performance milestones. This is a record of a published call, not an executed trade and not proof of the author's holdings. Rankings and performance labels should be read with their sample size, status, and methodology.

NETWORK does not route orders or execute transactions. Market data can be delayed, incomplete, or unavailable if a provider is rate-limited.

## Chrome X companion

The `extension/` directory contains a Manifest V3 **beta** companion: native popup/side panel, X sign-in, member feeds, posting, likes, replies and optional inline public context on X. Load it unpacked from `chrome://extensions` with Developer mode enabled. **Open NETWORK** still opens the full web app in a normal tab; the extension never frames it.

Configure Render `EXTENSION_ORIGINS=chrome-extension://<actual-id>` (comma-separated exact IDs), then restart. Use the ID shown in `chrome://extensions` for unpacked development and the stable Store ID for distribution. IDs can differ by installation path; no wildcard or web origins are accepted. Do not put these IDs in the credentialed `CORS_ORIGINS` setting. The server permits GET/POST only on `/api/extension/*`, with explicit headers and no cookie credentials. Authenticated requests carry a registered extension ID and an ID-bound, extension-only bearer token. An Origin, when present, must match; Chrome host-permitted worker fetches may omit it and must send the explicit `x-network-extension` header instead. The header alone never authenticates a request.

**Sign in with X** starts a user-initiated top-level `chrome.identity.launchWebAuthFlow` window. The existing server-side X OAuth/PKCE flow redirects a one-time, extension-PKCE-bound code to `https://<id>.chromiumapp.org/network`; only that code and state are in the URL, never a session token. Code expiry is 60 seconds; exchange consumes it atomically. Provider secrets stay server-side. The worker stores the resulting one-hour session only in trusted-context `chrome.storage.session`; only a hash is retained in PostgreSQL. This is memory-scoped extension storage, **not an httpOnly cookie**. Content scripts cannot read it or invoke member actions. Browser restart clears it. Logout revokes it server-side; if offline, the UI warns that remote revocation was not confirmed and expiry remains the bound. The separate website session is unaffected.

Feed selectors support Discover, My network, Following and My posts. Posts can target your public profile or a joined Network; likes/replies use the same server permission handlers as the website. Private membership, blocks, bans and suspension checks stay server-side. No wallet or trade execution is added.

Inline contextual cards are **off until opted in**. A throttled MutationObserver recognizes X article adapters and extracts only an author handle, first cashtag and first Solana-like address. These references, not full tweet text, query public NETWORK linked profiles/published calls. Cards never include private/member data, even when signed in. Addresses are mentions, not verified contracts; cashtags are ambiguous. Context uses existing NETWORK records rather than promising universal token coverage. No X posting, likes, follows or bulk scraping are automated.

Build an upload ZIP with `python scripts/build_extension.py --output dist/network-x-companion.zip`. It includes runtime assets and node-N icons only, not tests, credentials or listing drafts; it does not publish anything. [Store listing draft](extension/STORE_LISTING.md), [packaged privacy policy](extension/privacy.html) and the public `/extension-privacy` page accompany it. Read [extension/README.md](extension/README.md) for setup, security boundaries and release gates. Production X authorization, actual Store distribution and Render/PostgreSQL must be verified separately; local provider mocks are not production certification.

## Tests and checks

```bash
pytest -q
python scripts/check_rules.py
# Optional browser smoke check (requires Playwright + full Chromium):
python tests/extension2_browser_check.py --shots /workspace/network-new/shots
```

The test suite uses mocked OAuth provider responses and local SQLite migrations. Set `TEST_DATABASE_URL` to a dedicated PostgreSQL test database to run against Postgres. The wallet-related legacy tests explicitly opt into `ENABLE_WALLET_FEATURES=1` in the test process; production must remain at `0` for this release.

Before production launch, run the full suite, verify database migrations, and manually test X sign-in, account linking/recovery, network privacy permissions, messaging, opportunities, calls, and mobile layouts on the deployed Render service.

## Verification (what each label proves)

- **X account verified (@handle) / historical Google account verified:** OAuth proves control of that provider account, **not government identity**, trading skill or safety. Google email is private unless its owner explicitly shares it.
- **Tracked calls:** only independently checked DexScreener snapshots count; self-reported results never count. Timestamped calls and measured market price changes are **not verified executed trades, realized returns or proof of holdings**. Demo data is explicitly marked DEMO; missing or untracked results must never be labelled verified.
- **Project domain verified:** a DNS TXT record or `/.well-known/network-verify.txt` matched a server-issued code. Domain control is not project safety.
- Historical **wallet ownership**, **dev wallet**, **metadata authority**, and **CTO holder backing** records are retained, but their signing/backing flows are disabled in v0.4. Wallet-based verification badges and profile wallet addresses are not presented while the feature is off. Historical signatures proved control only, never project safety.
- **Read-only dev evidence** distinguishes sold (known DEX program), transferred (may be another wallet of the same dev), burned and unclassified flows. It is bounded by `CHAIN_MAX_FLOW_TXS`. Creator discovery uses on-chain evidence, not arbitrary signers; if unresolved, say **Couldn't determine the creator**, never guess.

## Safety principles

- Never request or store seed phrases or private keys. This release does not connect wallets, sign transactions, execute orders or swaps, or collect wallet credentials.
- Never label unverified trading performance verified; never present published calls as executed trades. Nothing is labelled verified unless the server checked the stated evidence.
- Never hardcode production passwords, API keys, JWT secrets or wallet keys. Keep OAuth/RPC secrets server-side and out of commits, screenshots, logs, URLs and extension packages.
- Reputation comes from records, not purchased placement or follower/member counts. Rankings expose their methodology and refresh age.
- CSRF requires `x-csrf: 1` with SameSite cookies. Server-side permissions, DB-backed rate limits, upload validation, CSP, anti-framing headers, audit logs and privacy choices remain enforced. CORS is not authentication.
- Production uses persistent PostgreSQL, not SQLite. Keep Render at the repository root. Preserve the official node-N logo.
- Do not claim an untested feature works or unfinished functionality is complete. Mock-provider extension tests do not verify production X consent, Chrome Web Store distribution or production deployment. X layout changes can affect inline cards; do not claim universal compatibility.
