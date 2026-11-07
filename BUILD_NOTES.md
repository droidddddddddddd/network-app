# NETWORK v0.4 build notes

## Companion implementation

- Native popup/side-panel UI replaces framing; original main-site anti-framing/CSP protections remain.
- X sign-in uses the existing server-side OAuth PKCE flow plus a browser-bound, extension-generated PKCE handoff. Canonical chromiumapp.org redirect carries only one-time code/state (or a fixed failure code); authorization codes expire after 60 seconds and are atomically single-use.
- One-hour opaque bearer sessions are hashed server-side, extension-ID-bound, revocable, and scoped only to `/api/extension/*`. The worker uses trusted-only `chrome.storage.session`, never persistent auth storage or content-script credentials. Browser restart clears credentials. Cookie auth is not accepted by the extension API. Supplied Origin must match; host-permitted Chrome worker requests without Origin require the registered `x-network-extension` header plus bearer/PKCE and CSRF protection.
- Authenticated feeds, joined-Network audiences, post/like/reply actions reuse the web permission handlers. Popup/panel sessions synchronize, and response-generation guards prevent stale private-feed responses after logout.
- Opt-in X context uses bounded/throttled DOM adapters and a bounded public-data cache. It sends extracted handle/cashtag/address references only. Public linked profiles and published calls are shown; no private feed reaches X. Cashtags/addresses do not imply verified assets or executed trades.
- Added Alembic `9c2e4a701b36`, auth access-query redaction, deterministic Store archive build, official node-N icon sizes, policy page and listing/disclosure draft. No store action or production deploy is performed by packaging.

## Repeatable validation

```bash
pytest -q
python scripts/check_rules.py
python tests/extension2_browser_check.py --shots /workspace/network-new/shots
python scripts/build_extension.py --output dist/network-x-companion.zip
```

Use `--skip-real-x` for deterministic browser tests without the best-effort unsigned public X navigation. The browser harness starts a local, isolated, Alembic-migrated database and mock X provider transport, and invokes the real `chrome.identity.launchWebAuthFlow` with a real unpacked extension. Test-only code is never included in the upload archive.

Real production X credentials/consent, live Google recovery, Store review/install, native browser chrome visual rendering and live Render/PostgreSQL remain separate release gates. Public X compatibility can be blocked by the site; the saved structural fixture includes legacy test-id markup and the public SSR article structure observed on November 7, 2026. No claim of universal DOM compatibility or 100% production certification is made.

Production continues to require persistent PostgreSQL; SQLite is used only in isolated local tests. The box has no PostgreSQL server binary, and package repository access failed during the prior review. PostgreSQL DDL rendering is available, but is not a substitute for a real PostgreSQL run.

## Final local validation — November 7, 2026

- Full suite: **76 passed, 5 skipped**, one upstream TestClient deprecation warning. Skips are four opt-in live-chain checks and the PostgreSQL multi-process realtime check.
- Real unpacked MV3 extension in headless full Chromium **156.0.8078.4**, using the real `chrome.identity.launchWebAuthFlow` and a local mock X provider: passed. Verified PKCE handoff, trusted session storage, public/private-allowed feeds, public/private posting, like, reply/count update, safe text rendering, content-script denial, context opt-in, both structural X adapters, mutation handling, native sidePanel.open from popup/launcher, cross-view session sync and server logout revocation. No page errors.
- The separate unsigned live Chromium visit to `https://x.com/solana` was denied with **HTTP 403** (recorded in `ext2-real-x-attempt.png`). Deterministic contextual-card checks used `tests/fixtures/x-context.html`; current public SSR structure was additionally inspected from public HTML. Live X frontend compatibility is not certified.
- Successful screenshots in `/workspace/network-new/shots/`: `ext2-public.png`, `ext2-auth-actions.png`, `ext2-private-feed.png`, `ext2-context-fixture.png`, `ext2-logout.png`. They show the packaged extension document in an extension tab and the explicit structural X fixture, not production credentials/data or native browser chrome.
- Rules, Python/JavaScript syntax and whitespace checks passed. All migrations, including the new extension tables, rendered as PostgreSQL DDL. No real PostgreSQL server test or production deployment was performed.
- Store ZIP build is deterministic and tested to contain only allowlisted runtime files, official node-N assets and the privacy page. Listing/privacy/disclosure drafts still require operator review and actual Store submission; no upload, publication or push was performed.
