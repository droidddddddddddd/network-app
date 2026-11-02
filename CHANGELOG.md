# Changelog

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
