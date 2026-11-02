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
