# NETWORK X Companion (Chrome starter)

This is a lightweight Manifest V3 companion for the existing NETWORK web app. It adds a floating NETWORK launcher on X and opens the current NETWORK app in Chrome's side panel.

## Install locally
1. Extract the project ZIP.
2. Open `chrome://extensions` in Chrome.
3. Turn on **Developer mode**.
4. Choose **Load unpacked** and select this `extension` folder.
5. Open `https://x.com` and click the NETWORK launcher at the lower-right, or click the extension toolbar icon.

## Current scope and limitations
- This opens the existing NETWORK app beside X; it does not yet inject contextual cards into individual X posts.
- Sign in through the NETWORK X OAuth flow inside the side panel.
- No X posting, automated likes/follows, scraping, or access to private X data.
- No wallet connection, wallet signing, swap, buy/sell, or transaction execution.
- A later contextual overlay should use a short-lived, one-time server handoff; never put OAuth client secrets or session-signing secrets in the extension.

The app URL is currently the existing Render deployment. If the app URL changes, update the iframe URL and the `host_permissions` entry in `manifest.json`.
