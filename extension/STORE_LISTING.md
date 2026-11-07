# Chrome Web Store listing draft (not submitted)

Name: NETWORK — X Companion
Short description: Your NETWORK feed, posts and public crypto context alongside X. Secure X sign-in; no wallet access.
Category: Social & Communication
Language: English
Homepage: https://network-app-65f6.onrender.com/
Privacy policy URL (after approved deployment): https://network-app-65f6.onrender.com/extension-privacy

## Detailed description

Build Your Network. Build Your Net Worth.

Keep NETWORK alongside X with a native popup and side panel. Sign in securely with X in a top-level authorization window, then browse your permission-filtered community feeds, publish posts, like and reply. Choose your public profile or a Network you belong to as the audience. Your companion session lasts one hour; log out whenever you choose.

Opt in to inline public NETWORK cards for X posts mentioning an author, cashtag or address. See linked account profiles and published call records without sending full tweet text. Private NETWORK posts never appear in X cards. Context starts off; you control it.

NETWORK is a social crypto research service, not an exchange. Published calls and market snapshots are not proof of executed trades, realized returns or project safety. Cashtags can refer to different assets; verify the mint. No wallet connections, swaps, transaction signing, seed phrases or private keys.

This is a beta companion. X layout changes and provider availability can affect features. A NETWORK deployment configured for the published extension ID is required. Real X consent and store distribution must be release-tested; local mock-provider tests are not production certification.

## Permission justifications

- identity: top-level X OAuth handoff via launchWebAuthFlow, PKCE and a single-use code; never Google identity/token access.
- storage: in-memory, trusted-context-only one-hour companion session; persistent local context opt-in preference. No token in persistent storage.
- sidePanel: user-requested companion beside X.
- NETWORK host permission: authenticated NETWORK API calls and public reference lookups. No arbitrary destinations.
- X/Twitter content-script matching: add launcher and optional inline public context from extracted author/cashtag/address references; no automated X actions or bulk scraping.

## Data-use disclosure preparation

Disclose authentication information (short-lived NETWORK credential), user-generated content (explicit NETWORK posts/replies/actions), and website content (opt-in extracted public author/cashtag/address references). Explain NETWORK server processing and existing account deletion. No advertising, sale, analytics or unrelated browsing history. Review actual Store disclosure categories and certify them truthfully before submission; this draft is not a submitted certification.

## Store assets/release gates

Official node-N icons included at 16/32/48/128; no new branding. Use approved, non-sensitive product screenshots sized to current Store requirements. Test with the actual stable Store ID and production X provider before publishing. Do not upload test fixtures, credentials or private feed screenshots. This file and packaging do not submit/publish anything.
