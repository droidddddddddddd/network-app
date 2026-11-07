# Changelog

## v0.4.0-beta (2026-11-07)
- Public sign-in is X only (OAuth 2.0 + PKCE). Password accounts can recover via the unlinked `#/legacy-login` route, then link X. Google buttons removed; legacy Google records are kept.
- Wallet signing, wallet verification and CTO holder backing are switched off (`ENABLE_WALLET_FEATURES=0`; those APIs return 404). Read-only token and creator research stays.
- Wallet address field and its privacy toggle removed from profile settings.
- Replaced the blank iframe extension with packaged, experimental popup/side-panel UI and a public read-only feed API. X sign-in/full functionality open in a normal tab; no auth tokens enter the extension. Official node-N assets preserved.
- Exact-ID `EXTENSION_ORIGINS` CORS applies only to GET `/api/extension/feed`, without credentials. Main-site anti-framing protections remain unchanged. Feed content is text-only and excludes private/hidden/removed posts even when supplied a member cookie.
- Password registration now returns 403; existing password login remains. Added opt-in, existing-linked-account-only Google recovery (`ENABLE_GOOGLE_RECOVERY`), with a tested mocked-provider recovery → link X flow and admin runbook.
- Wallet-off mode hides stale profile wallet addresses/badges, ignores wallet profile edits and preserves stored records. Production now refuses missing/SQLite database URLs.
- Restored PWA installation, environment reference, verification policy and safety documentation with v0.4 scope; updated extension/build/release docs.
- Added API/security regressions, a repeatable rules check and an isolated Playwright Chromium extension smoke check (see extension/README.md for limits).
- Added RELEASE_SCOPE.md and BUILD_NOTES.md.

## v0.3.1-beta (2026-11-02)
New official NETWORK logo: a node-style "N".
- Hand-built SVG mark: four neon-green (`#22f08a`, the app's `--green`) nodes joined by a left vertical, a top-left to bottom-right diagonal and a right vertical, so it reads clearly as an N. It stays legible at 16px.
- `static/img/logo.svg` (used in the header, mobile header and auth screen) is now the new mark. Brand masters are in `static/img/brand/`: `logo_mark.svg`, `logo_full.svg` (the mark plus the NETWORK wordmark set in Montserrat ExtraBold and converted to paths), `logo_full_hero.svg` (with a soft glow on a dark background) and `logo_horizontal.svg`.
- All PWA icons in `static/icons/` were regenerated from the new mark: 192, 512, maskable 512 with safe padding, the 180 apple-touch-icon, favicon-32 and `favicon.ico` (16/32/48). The manifest, offline page and install banner already point to these paths.

## v0.3.0-beta (2026-11-02)
NETWORK can now be installed on phones as a Progressive Web App (PWA).
- **Web app manifest** at `/manifest.webmanifest`, served as `application/manifest+json`. It sets the name and short name NETWORK, the slogan, `start_url`/`scope` `/`, standalone display, and the dark `#07090a` background and theme colour.
- **Icons** made from the official neon-green NETWORK "N" mark on the dark background: 192, 512, maskable 512 with safe padding, the 180 apple-touch-icon, and the favicon (`/favicon.ico` plus a 32px PNG). They are in `static/icons/`.
- **Service worker** at `/sw.js` with root scope. It is served with `Cache-Control: no-store` and `Service-Worker-Allowed: /`.
  - It caches the app shell and static assets. The cache name includes a hash of `static/`, so every deploy creates a new cache and old caches are deleted on activate.
  - Page navigations always go to the network first. When offline, they fall back to a branded offline page.
  - `/api/*`, `/ws`, `/uploads/*` and anything authenticated are never cached.
  - `skipWaiting` and `clients.claim` are used with a single reload, so a new deploy takes effect on the next visit.
- **Install affordance:**
  - Android/Chrome shows an Install button in a small dismissible banner and an "Install app" card in Settings, only after the browser fires `beforeinstallprompt`.
  - iOS Safari shows "Tap the Share button, then Add to Home Screen" instead.
  - Both are hidden when the app is already running standalone.
- iOS meta tags were added: apple-mobile-web-app-capable, status-bar-style and title. Safe-area padding was added for the iPhone notch in standalone mode.
- CSP adds `manifest-src 'self'; worker-src 'self'`. Everything else is unchanged.

## v0.2.1-beta (2026-11-02)
Fixes from the live audit of the Render deployment:
- **Account deletion:** `DELETE /api/me` with a Settings "Delete account" card. You must type your username and enter your password. It removes the user's data. A founded Network is deleted only when you are its sole member; otherwise the request returns 409.
- **Production no longer serves `/openapi.json`.** Docs were already disabled.
- **Mobile layout:** Network cards and file inputs no longer cause horizontal scrolling on Discover, Networks and Settings.

## v0.2.0-beta (2026-11-02)
- **Sign in with X (OAuth 2.0 PKCE) and Google (OpenID Connect):** sign up, log in, or link to an existing Passport.
  - Badges "X account verified (@handle)" and "Google account verified" are labelled account ownership, not government ID.
  - Stored: provider subject, handle or email, and verified flags only. No tokens.
  - Security: single-use state bound to the browser cookie with a 10-minute TTL, a PKCE S256 verifier, and Google nonce/iss/aud/exp checks. Login CSRF is blocked.
  - Collisions handled: an email already in use is never auto-merged, and an account already linked elsewhere is refused. Unlinking keeps at least one login method. A user can set a password from Settings.
  - The buttons are hidden unless both the client id and secret are set.
  - X account age and follower count are shown as light anti-sybil context, without adding reputation.
  - The KYC "identity" placeholder was removed, and `/api/verifications` returns 410.
- **Creator discovery rewritten:**
  - The oldest signature comes from Helius `getTransactionsForAddress` (oldest first) or bounded backward paging.
  - Version-1 transactions are supported.
  - The pump.fun create/create_v2 `creator` argument is parsed, with a fee-payer fallback. The old "any signer" match was removed because bundled launches have several signers.
  - Helius DAS counts only verified creators. The Token-2022 metadata update authority is read.
  - Results are cached in a new `chain_cache` table.
  - The fallback message is "Couldn't determine the creator".
- **Dev wallet evidence:** the creator's token-account history is parsed into sold (DEX swap, venue named), transferred (destination shown, "may be the dev's own wallet"), burned/unclassified and acquired, with transaction links. The panel notes when only part of the history was checked.
- **Network-scoped bans:** Founders and moderating Admins can ban members for N hours or indefinitely. The Founder is protected, and only the Founder can ban an Admin. A banned member can't post, reply or rejoin. Each ban is audit-logged and notified. There is one appeal per ban, and moderators can lift bans. A "Ban from Network" action was added to the Network moderation queue.
- **Optional realtime backend `REALTIME_BACKEND=postgres`:** LISTEN/NOTIFY fan-out between several app instances, tested with two processes. The default stays in-process.
- RPC errors no longer include the RPC URL, which carries the Helius key. Public RPC 429s are retried with backoff.
- New migration `77105a1d036a` adds linked_accounts, oauth_states, network_bans and chain_cache.

## v0.1.0-beta (2026-11-02)
First deployable beta.
- Real Postgres support (tested on PostgreSQL 17) with Alembic migrations run on every start. SQLite for local dev.
- Upload storage: database-backed media table by default in production (2 MB cap, immutable cache headers). Optional S3/R2. Local disk in dev. One-time migration of existing local uploads.
- Moderation: reports on posts, users and Networks. Network moderator queue and platform admin queue (`ADMIN_USERNAMES`). Actions: dismiss, hide, remove, suspend (timed or indefinite). Audit log and reporter notifications. Stricter limits for accounts younger than 24 h.
- Wallet ownership verification via signMessage (SIWS-style, single-use 10-minute nonces).
- Project domain verification (DNS TXT or /.well-known file). Dev wallet verification (pump.fun creator → earliest signer → Metaplex/Helius) with re-check and read-only creator balance. Metadata authority verification.
- Community takeover claims: holder-signed backing, live balances, exclusions, anti-sybil weighting, lapse on sale, leading and competing claims, hourly re-check.
- Rankings snapshots with "Updated X min ago".
- Per-connection activity-type sharing picker, enforced server-side. "From Connected Networks" activity feed.
- Achievements & XP page replaces the old Rewards placeholder.
- DB-backed rate limiter. Single-instance pin documented in render.yaml.
- Demo seed refuses to run in production unless `SEED_DEMO=true`.

## v0.4.0-beta (2026-11-05)
- Public sign-in / signup UI now offers X only. First X authorization creates a Passport; later authorizations log in.
- OAuth provider discovery advertises only X. Legacy Google callback code and legacy account data are retained for migration safety but are no longer exposed as a public login option.
- Wallet connection/signature features are excluded from this release. Wallet-dependent API endpoints return 404 unless `ENABLE_WALLET_FEATURES=1`; Render defaults this setting to `0`.
- Removed wallet entry/signing controls from the public profile and Project Network trust UI. Read-only Solana market and creator research remain.
- Added a Chrome Manifest V3 X companion launcher and side panel for the existing NETWORK app.
- Added `RELEASE_SCOPE.md` and `BUILD_NOTES.md`; updated deployment and testing instructions.
- No live-trading, swap, buy/sell, or transaction-execution functionality is included.
