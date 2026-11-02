# Changelog

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
