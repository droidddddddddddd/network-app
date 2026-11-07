# Build notes

This package preserves the uploaded FastAPI / SQLAlchemy / Alembic / vanilla-JS application and adds the first X companion extension.

## Main changes in this compilation

1. Public OAuth provider discovery now advertises X only.
2. The login and signup screens use one X sign-in flow; X creates an account on first authorization and logs in on later authorizations.
3. Google credentials were removed from the Render Blueprint template. Legacy Google callback code remains to avoid destructive account migration; no Google button is shown.
4. Wallet-signature APIs are disabled unless `ENABLE_WALLET_FEATURES=1`. Production configuration explicitly sets it to `0`.
5. Wallet-signing UI controls and wallet profile editing were removed. Read-only on-chain creator and market research remain.
6. Added `extension/`, a Chrome Manifest V3 companion panel for X.
7. Added `RELEASE_SCOPE.md` documenting included and excluded functionality.

## Important implementation boundaries

- Existing calls are records and read-only market-data tracking; they are not executed trades.
- There is no buy/sell or swap execution path in this release.
- The experimental Chrome extension uses native packaged UI and the public feed API, not an iframe. X sign-in and private features open in a normal browser tab. It does not render contextual cards on individual X posts.
- Existing database fields are preserved to avoid destructive migrations. They are not an invitation to enable wallet features.

## Validation

Run `pytest -q`, `python scripts/check_rules.py`, and `python tests/extension_browser_check.py --shots /workspace/network-new/shots` before release. See extension/README.md for the exact headless test scope and remaining live-provider/browser-UI release gates. No production deployment is implied by local tests.

### Local validation — November 7, 2026

- Full pytest: **68 passed, 5 skipped** (four opt-in live-chain checks and the Postgres multi-process realtime check). One upstream TestClient deprecation warning.
- `scripts/check_rules.py`: passed. Python/JavaScript syntax and `git diff --check`: passed.
- Alembic rendered all migrations as PostgreSQL SQL successfully. A real PostgreSQL run was not available: this box had client tools but no server binary, and the package repository could not be reached. SQLite was used for isolated local tests only; production rejects SQLite/missing database URLs.
- Headless full Chromium **156.0.8078.4**, real unpacked MV3 extension via `--load-extension`: local public feed rendered; private/hidden/removed posts excluded; untrusted markup remained text; empty/offline/retry states passed; workspace opened top-level. Both popup and mocked-X launcher clicks resolved native `sidePanel.open`. No page errors.
- Screenshots: `/workspace/network-new/shots/ext-feed.png`, `ext-empty.png`, `ext-offline.png`, `ext-x-launcher.png`. The feed/empty/offline screenshots show the real packaged extension document in an extension tab; the X document is a fixture. Native Chrome toolbar/side-panel chrome was not visually verified.
- Real X OAuth, real Google recovery, live X-page integration and Web Store distribution remain unverified. Authenticated extension sessions and inline contextual post overlays are not implemented. No production push/deploy was performed.
