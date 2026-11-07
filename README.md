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
- Responsive web app / PWA and Chrome X companion panel.

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

## Render deployment

1. Push the repository to a GitHub repository.
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

Legacy Google callback code and password authentication data are retained for account-migration safety, but they are not shown as public sign-in choices. Existing password-only members can use the unadvertised `#/legacy-login` route once, then link X from Settings. Do not delete legacy password hashes or linked-account records until a tested recovery/linking path exists for every affected user. Google-only legacy users may require a temporary, explicitly configured recovery path before Google credentials can be retired.

## Proof-of-Call and market research

Calls are published records with a token mint, author, timestamp, and available market snapshot. The tracker periodically compares read-only DexScreener market data with the call's entry snapshot and records performance milestones. This is a record of a published call, not an executed trade and not proof of the author's holdings. Rankings and performance labels should be read with their sample size, status, and methodology.

NETWORK does not route orders or execute transactions. Market data can be delayed, incomplete, or unavailable if a provider is rate-limited.

## Chrome X companion

The `extension/` directory contains a Chrome Manifest V3 starter. Load it from `chrome://extensions` with Developer mode enabled, then choose **Load unpacked** and select the `extension` folder. It adds a NETWORK launcher on X and opens the existing NETWORK web app in a side panel.

This is the companion panel stage, not yet an inline contextual overlay on each X post. The extension does not contain OAuth client secrets or signing keys. If the app's URL changes, update the iframe URL in `extension/sidepanel.html` and the host permission in `extension/manifest.json`.

## Tests and checks

```bash
pytest -q
```

The test suite uses mocked OAuth provider responses and local SQLite migrations. Set `TEST_DATABASE_URL` to a dedicated PostgreSQL test database to run against Postgres. The wallet-related legacy tests explicitly opt into `ENABLE_WALLET_FEATURES=1` in the test process; production must remain at `0` for this release.

Before production launch, run the full suite, verify database migrations, and manually test X sign-in, account linking/recovery, network privacy permissions, messaging, opportunities, calls, and mobile layouts on the deployed Render service.
