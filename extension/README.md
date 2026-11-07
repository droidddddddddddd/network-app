# NETWORK X Companion (experimental)

Load `extension/` unpacked in a recent Chrome browser. The toolbar popup and side panel are packaged HTML/JS, **not an iframe**. They read the anonymous public NETWORK feed. An X/Twitter launcher opens the panel; **Open NETWORK / Sign in with X** opens the full site in a regular tab.

## Setup

1. Enable Developer mode at `chrome://extensions`, select **Load unpacked**, choose this directory.
2. Copy the extension ID (32 letters a–p). Configure Render `EXTENSION_ORIGINS=chrome-extension://<id>`, then restart. Multiple IDs are comma-separated; no wildcards. Unpacked IDs may differ between machines/paths; a store-published ID is stable.
3. Keep `ENABLE_WALLET_FEATURES=0`. Keep all OAuth credentials on the server.
4. Open the toolbar popup, use Refresh, or click the NETWORK launcher on X. Existing X tabs may need a reload after installation.

The public feed is credential-free, GET-only, no-store and always anonymous even if a caller supplies a session cookie. It excludes private Networks and hidden/removed posts. Chrome's host permission can allow privileged requests independent of server CORS: the public endpoint is not an access-controlled data source. CORS is not auth. No cookies/token/session handoff is implemented. No scraping, posting to X or wallet access.

The site remains protected by `X-Frame-Options: DENY` and `frame-ancestors 'none'`. The extension CSP disallows frames and remote scripts. Feed text uses `textContent` to prevent markup execution. It requests only `sidePanel` plus the NETWORK host permission; X content-script matches only add a button. The logo is copied verbatim from the official node-N asset.

## Local browser validation

Install dev dependencies and Playwright, with bundled Chromium available:

```bash
pip install -r requirements.txt -r requirements-dev.txt playwright
playwright install chromium
python tests/extension_browser_check.py --shots /workspace/network-new/shots
```

The script starts an isolated, migrated local server and test database, copies the extension to a temporary directory and changes only its public base URL/host permission/CSP for localhost. It launches real headless Chromium with `--load-extension`, loads the actual extension-owned page, checks successful API data rendering, privacy filtering, empty/error/retry states, safe text rendering, normal-tab links and the X launcher on a mocked X document, including trusted clicks on both the popup button and X launcher whose native `sidePanel.open` requests resolve. Screenshots are `ext-*.png`. No production credentials or real X session is used. It also verifies exact-ID CORS and unchanged site anti-framing headers against the server.

Not yet verified: real provider X login, live X DOM/launcher interaction, interactive native side-panel/browser toolbar chrome, Chrome Web Store install/review, and authenticated extension sessions (not implemented). The headless check renders the packaged popup/side-panel document in an extension tab, not a screenshot of Chrome's native panel chrome.
