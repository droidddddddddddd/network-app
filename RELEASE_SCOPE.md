# NETWORK — Release build scope (November 2026)

This release builds on the uploaded `network-app` repository. It is a social crypto intelligence and networking platform, not an exchange or trading terminal.

## Included in this release

- X OAuth sign-in as the only public sign-in choice (OAuth 2.0 Authorization Code + PKCE).
- User profiles / Network Passports, posts, replies, endorsements, and feeds.
- Networks, memberships, moderation, connection requests, and explicit sharing permissions.
- Opportunities and applications, messages, notifications, events, invites, achievements, and reputation.
- Proof-of-Call: published token calls are timestamped and tracked against read-only market data. The tracker is not a trade executor and does not prove the caller bought the asset.
- Read-only Solana / DexScreener data and token research, including market price, market cap, liquidity, volume/price movement where available, and creator evidence.
- Responsive web app / PWA and a Chrome X companion side panel.

## Explicitly excluded

- No live trading, swaps, order placement, buy/sell execution, or transaction construction.
- No wallet connection, wallet signing, wallet-based identity, wallet-based holder backing, or transaction permissions in this release.
- No seed phrase or private-key collection, storage, or handling.
- No automatic posting, liking, following, or scraping on X.

Wallet-dependent API routes are disabled by default. `ENABLE_WALLET_FEATURES=0` is the production setting. The existing database fields and historical records are retained for compatibility, but the UI no longer asks users to connect or enter a wallet. Re-enabling wallet features is a future, explicit product decision—not part of this release.

## X sign-in migration note

The public interface offers X only. Existing Google-linked records and legacy password authentication code are retained in the backend for account-recovery/migration safety; they are not presented as public sign-in options. Password registration is rejected. For Google-only members, temporarily enable existing-account-only `ENABLE_GOOGLE_RECOVERY=1`, retain the original Google credentials, recover in a normal tab and link X in Settings (README runbook). Before fully removing legacy login support, every existing password-only or Google-only account needs a tested X-linking/recovery path. Do not delete those account records or password hashes as part of this release.

## Chrome companion status

The experimental extension renders its own public-feed popup/side panel and adds a floating launcher on X. It never frames the site; full NETWORK functionality and X sign-in open in a normal tab. This is a companion panel, not yet a contextual card overlay attached to each X post. Contextual post cards and authenticated extension sessions are not implemented. Configure exact extension IDs in `EXTENSION_ORIGINS`; see extension/README.md for tests and limitations.

## Production release gates

- Set `PUBLIC_BASE_URL`, `X_CLIENT_ID`, and `X_CLIENT_SECRET` in Render; never commit credentials.
- Rotate the X client secret if it was ever pasted into a chat, issue, or public repository.
- Make the GitHub repository private unless public source is intentional.
- Confirm the X callback URL matches `https://<your-domain>/api/auth/oauth/x/callback`.
- Run the full test suite against the same Python version and PostgreSQL major version used in production.
- Verify Render migrations, login, signup, account linking, permissions, calls, and PWA behavior on the deployed service.
- Configure a persistent Postgres database and review Render free-tier sleep/availability constraints before launch.
