# Technical assessment of the previous MVP (NETWORK_fullstack_mvp.zip)

Inspected: `app/main.py` (226 lines), `models.py`, `security.py`, `schemas.py`, `database.py`, `static/` (index.html, app.js 135 lines, styles.css 1 line), `requirements.txt`, `network.db`.

## What it actually implemented
| Area | Status | Notes |
|---|---|---|
| Register / login / `/api/me` | Implemented | Hand-rolled scrypt hashing (sound) and a hand-rolled HS256 JWT (works, but custom crypto code is a maintenance risk). Bearer token only, stored by the frontend. |
| Networks: list / create / join | Basic | Public join auto-creates membership. Private networks are simply **blocked** (403) — no request/approval workflow, no roles beyond owner/moderator strings. |
| Token calls | Basic | Calls store a user-entered `entry_price`; "performance" comes from `mark-price`, a **manual price typed by the caller**. Correctly labeled "not independently verified", but there is no market-data source. |
| Leaderboard | Basic | Ranks networks only by average manually-marked return — gameable by the caller. |
| Network chat (WebSocket) | Implemented for public networks | Token in query string; one DB session for the socket lifetime; private networks excluded. Pattern reused. |
| Alerts | Basic | Only self-alerts on publishing a call. |

## Not present (despite the brief's summary)
No posts, replies, likes, reposts, follows, global/following feeds or trending hashtags/tickers exist in this code — no models or routes for them. No migrations (`create_all` only), no rate limiting, no CSRF handling, no network-to-network connections, no sharing permissions, no Passport, Opportunities, Endorsements, Launch Rooms, or mobile layout.

## Decision
| Keep / reuse | Replace |
|---|---|
| FastAPI + SQLAlchemy stack, SQLite local fallback | `create_all` → **Alembic migrations** |
| WebSocket room-broadcast pattern for chat | Custom JWT → **PyJWT**; scrypt → **bcrypt** (both standard libs) |
| Honest labeling of unverified prices | Manual price marks → **DexScreener tracker** (only tracker data counts as "independently verified trading performance") |
| Pydantic input validation idea | Private-network 403 → join requests + founder/admin approval |
| | Leaderboard → transparent multi-factor Network Rankings |
| | 1-line CSS / 135-line JS → new dashboard UI matching the official mockup, with mobile bottom nav |

The old `network.db` was not migrated (demo data only) and is excluded from the new repo.

## Status at v0.1.0-beta (2026-11-02)
| Area | Status |
|---|---|
| Postgres, migrations, DB media storage, DB rate limiter | Done; full suite passes on SQLite and PostgreSQL 17 |
| Moderation (posts/users/Networks, two queues, suspensions, audit, notifications, new-account limits) | Done |
| Wallet / domain / dev-wallet / metadata verification | Done (signMessage only) |
| CTO claims | Done, with limits below |
| Identity verification | **Partial by design:** stays "needs KYC provider" (no provider) |
| Earliest-transaction creator lookup | **Partial:** pages back at most `CHAIN_MAX_SIG_PAGES`×1000 signatures; busy mints return "incomplete" and the pump.fun / Metaplex methods are relied on |
| Dev abandonment evidence | **Partial:** shows "holds none now"; cannot prove *sold* vs transferred |
| Suspensions | Platform admins only; Network moderators can hide/remove but not suspend |
| Realtime | Single instance only (in-process hub); scaling out needs Redis pub/sub |

## Status at v0.2.0-beta (2026-11-02)
| Area | Status |
|---|---|
| Identity | Replaced by **account linking** (X OAuth 2.0 PKCE, Google OIDC). Labelled account ownership, not government ID. Tested with mocked providers only; **real X/Google sign-in is untested** until the owner registers apps |
| Earliest-tx / creator lookup | Done with Helius (oldest-first, one request; live-checked on $ANAKIN → pump create `creator` argument). Without Helius, busy mints still return "couldn't determine" after `CHAIN_MAX_SIG_PAGES` pages. The pump.fun curve field usually answers first anyway |
| Dev abandonment evidence | Done: sold (DEX venue) vs transferred (destination) vs burned/unclassified, from the latest `CHAIN_MAX_FLOW_TXS` token txs. Live-checked: $ANAKIN creator sold its full buy via PumpSwap. Venues are classified by program id; an unknown aggregator route can show as "transferred" or "unclassified", never as a false sale |
| Suspensions / bans | Platform suspensions (admins) plus **Network-scoped bans** with appeal and lift |
| Realtime | In-process by default; optional Postgres LISTEN/NOTIFY backend (tested with two local processes, not on Render). NOTIFY payloads over ~7.9 KB fall back to local-only delivery |
| Live tests on public RPC | `getTokenLargestAccounts` is often rate-limited (429) on the free public RPC; the app shows it as unavailable. Passes with Helius |
