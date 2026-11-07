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
- The Chrome extension opens the existing web app; it does not yet render contextual cards on individual X posts.
- Existing database fields are preserved to avoid destructive migrations. They are not an invitation to enable wallet features.

## Validation performed for this package

- Python syntax compilation and JavaScript syntax checks are part of the packaging validation.
- Full pytest execution could not be completed in the build environment because the environment does not have the project's `bcrypt` dependency installed. Run `pip install -r requirements.txt -r requirements-dev.txt` and `pytest -q` before deploying.
