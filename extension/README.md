# NETWORK X Companion — beta

## Install and configure

1. Use Chrome 116+; enable Developer mode at `chrome://extensions` and Load unpacked `extension/`.
2. Configure Render `EXTENSION_ORIGINS=chrome-extension://<actual-32-letter-id>` and restart. Multiple exact IDs are comma-separated; no wildcards. Use the stable Store ID for distribution, not an ephemeral test/unpacked ID. Keep web `CORS_ORIGINS` separate.
3. Retain `PUBLIC_BASE_URL`, `X_CLIENT_ID`, `X_CLIENT_SECRET`, `JWT_SECRET` and persistent PostgreSQL `DATABASE_URL`. The X developer callback remains `https://<domain>/api/auth/oauth/x/callback`. The server—not X—redirects the final one-time code to the extension's canonical chromiumapp.org URL. No additional provider secret goes in the extension.
4. Keep `ENABLE_WALLET_FEATURES=0`. Run migrations from the repository root, including `9c2e4a701b36`.
5. Open the toolbar popup or X launcher. Sign in with X; choose a feed/audience, publish a post, like or reply. Log out when finished. Opt in to public context separately.

## Auth and permission boundaries

The user explicitly starts a top-level Chrome identity authorization window, never an iframe. NETWORK uses the existing X OAuth PKCE/browser-bound state flow. A second extension-generated PKCE verifier binds a single-use, 60-second code to its initiator. The registered ID fixes the chromiumapp.org redirect; arbitrary redirect URIs are not accepted. A conditional DB update atomically consumes the code. No reusable token appears in a URL.

A one-hour opaque bearer session is hashed in the DB and bound to the registered extension ID. It is accepted only on extension endpoints with the matching extension ID, never on the web API. Origin, when supplied, must match that registered ID. Chrome host-permitted worker fetch can omit Origin; those requests require `x-network-extension` plus the scoped bearer credential. The header is a CSRF/CORS boundary, not authentication by itself. Site cookies do not authenticate extension requests. GET/POST CORS permits only exact configured extension origins, required headers and no credentials/cookies. POSTs require `x-csrf: 1`; the worker always uses `credentials: omit`.

The worker stores credentials only in `chrome.storage.session` with `TRUSTED_CONTEXTS`; this is not true httpOnly storage. Packaged trusted extension code can access it; X/content scripts cannot. Runtime message handlers only allow member operations from the packaged panel URL. Content scripts get public context and the launcher only. Browser restart clears storage; sessions expire after one hour. Logout revokes the current token and clears local state. Offline logout warns if server revocation cannot be confirmed. It does not end the separate website session. No refresh token is used.

Member actions reuse web handlers: network membership/privacy, blocks, scoped bans, suspension and post/reply permissions remain enforced server-side. API responses are no-store. Application auth query strings are redacted from uvicorn access logs; infrastructure logging outside the app must also be reviewed by the operator.

## Contextual cards

Context is off by default. When enabled, a throttled/viewport-bounded MutationObserver scans X post article adapters, including legacy test-id and newer public SSR markup. Only the author handle, first cashtag and first Solana-like address are sent. No full tweet text, images, X cookies or private messages are sent. A bounded worker cache limits repeated lookups. Cards use textContent and public linked profiles/published call records; no private NETWORK data is inserted into X. Cashtags may identify multiple tokens; an address mention is not proof of a token. No match is not a safety claim. X layout changes remain a compatibility risk.

## Build for the Chrome Web Store

```bash
python scripts/build_extension.py --output dist/network-x-companion.zip
```

The ZIP has manifest.json at its root, only allowlisted runtime assets and official node-N icons at 16/32/48/128. It excludes mock provider/test/probe code, local config, credentials and documentation drafts. Build validates the public production host and permission set; it does not submit or publish anything. See STORE_LISTING.md for listing text, permission explanations, data-use disclosures and remaining manual review. Publish the `/extension-privacy` policy route before submitting its URL to the Store. Have the operator approve listing/disclosure text and product screenshots; do not submit private member data or test screenshots as real product claims.

## Repeatable checks

```bash
pytest -q
python scripts/check_rules.py
pip install playwright
playwright install chromium
python tests/extension2_browser_check.py --shots /workspace/network-new/shots
# Skip the best-effort unsigned live X compatibility read:
python tests/extension2_browser_check.py --shots /workspace/network-new/shots --skip-real-x
```

The browser check copies the packaged extension to a temporary directory, changes only local public endpoint/host/CSP, and adds a test-only isolated-world security probe. A migrated isolated DB and local X OAuth transport mock are used. It invokes the real Chrome identity API and tests code exchange, session storage, private-allowed feeds, posting, like, reply, context opt-in, DOM mutation, content-script denial and logout revocation. No production credentials or authenticated X browser profile are used. Screenshots use `ext2-*.png`. The optional public `x.com/solana` attempt is read-only; structural fixture tests remain deterministic.

The old `tests/extension_browser_check.py` runner delegates to this check. Native popup/panel document rendering is checked in an extension tab; native browser chrome is not visually certified. Production X consent, Store installation/review and live Render/PostgreSQL remain separate release gates. Never call the project “100% verified” based only on local mocks.
