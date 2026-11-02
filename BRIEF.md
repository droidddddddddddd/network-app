# NETWORK — Full project handoff brief (from Christopher Lyons, Nov 2, 2026)

Brand: NETWORK. Slogan: "Build your Network. Build your Net worth."
Positioning: "NETWORK isn't just where you find the next opportunity. It's where you build the connections that create opportunities."
A Solana-focused social + business networking platform for traders, memecoin devs/founders, KOLs, alpha communities, marketing teams, project owners, partners. Familiar like X/Facebook, plus professional networking. Real working app, not a prototype.

## Design (official): first generated desktop dashboard mockup (user will upload; if not available, follow this description)
Premium dark charcoal/black, vibrant neon-green accents, clean modern typography, rounded cards, subtle borders, restrained green glow, professional crypto-tech, familiar social layout.
Desktop 3-column:
- LEFT: NETWORK logo, My Network, Networks, Discover, Opportunities, Network Rankings, Messages, Notifications, My Profile, Network Passport, "Create a Network" button
- CENTER: welcome/banner, My Network Feed, post composer, network posts, images/media, comments, Endorsements, "Re-Network" (repost)
- RIGHT: Your Networks, Top Opportunities, Network Rankings
Mobile: real responsive mobile UX with simplified interface and bottom nav (not a shrunk desktop).

## Core: Network-to-Network connectivity
Personal Network; members join; networks connect with other networks; members see own network + approved connected network activity; founders/admins control sharing.
PRIVACY: connecting NEVER auto-exposes private posts, private member info, or restricted content. Connections require approval. Each connection has explicit permissions: share announcements, share selected posts, allow collaboration, display connection publicly.

## Network types: Personal, Trading, KOL, Alpha Community, Marketing, Project
Each network: name, unique slug/URL, description, cover image, profile image, founder, admins, members, type, public/private, posts & announcements, member management, connection requests, connected networks, activity feed.

## Connection workflow example
Trader creates Trading Network, invites 20, grows to 500, connects with KOL/Alpha/Marketing/Project networks; founder approves incoming requests and picks which announcements/posts are shared; members discover collaboration across approved connections.

## Network Passport (per user)
Profile, bio, networks founded, networks joined, network connections, projects supported, achievements, endorsements, contribution history, reputation. Visually appealing credibility page.

## Opportunities marketplace
Categories: KOL partnerships, Marketing collaborations, Project launches, Research collaborations, Developer recruitment, Sponsorships, Strategic partnerships. Publish, browse, express interest, submit applications, contact creator via proper workflow. Category filters + search.

## Reputation (earned, never purchased)
No buying followers/rank/reputation. Separate indicators: Reliability, Member retention, Organic network growth, Engagement quality, Collaboration history, Fulfilled commitments, Community contributions, Independently verified trading performance.
NEVER label unverified trading performance as verified. Keep wallet-ownership, identity, project, and trading-performance verification SEPARATE. Build framework for later market-data / call verification integration.

## Endorsements
Categories: Research, Reliability, Collaboration, Community leadership, Development, Marketing. Prevent duplicates and basic manipulation; not a popularity contest.

## Project Launch Rooms (Project Networks)
Project intro, team info, roadmap, announcements, community activity, partnership requests, marketing opportunities, launch countdown, post-launch updates. Journey: Idea → Community → Connections → Launch → Growth.

## Network Rankings
Transparent; not only followers/members. Consider organic growth, retention, meaningful engagement, collaboration, reliability, verified contributions, independently verified performance when available. Show how rankings are calculated. Never present unverified info as fact.

## Tech (match previous MVP)
Python, FastAPI, SQLAlchemy, PostgreSQL (prod) + SQLite local fallback, HTML/CSS/JS frontend, JWT auth.
Previous MVP zip NETWORK_fullstack_mvp.zip (user may upload) had: register/login, profiles, follow/unfollow, posts, replies, likes, reposts, global + following feeds, basic networks/membership, token calls, trending hashtags/tickers, basic leaderboard. If the zip arrives, inspect it first and write a technical assessment (implemented / incomplete / replace). Don't assume features exist.

## Priority order
1 auth, 2 network creation/management, 3 membership & permissions, 4 network-to-network connections, 5 explicit sharing permissions, 6 dashboard matching mockup, 7 Passport, 8 Opportunities, 9 Reputation + Endorsements, 10 Launch Rooms, 11 Rankings, 12 responsive mobile, 13 test all major workflows, 14 package for deployment.

## Security/DB
Proper authn/authz, secure password hashing, server-side permission checks, no private-content leakage, input validation, DB constraints, safe connection-request handling, rate limiting, env vars, DB migrations (Alembic). No frontend-only permissions.

## Deployment
GitHub + Render. Provide complete source, requirements.txt, render.yaml at repo root, README (setup, DB config, env vars, deploy, testing). Runs locally and on Render. Free tier where practical; state limitations.

## Expectations
Real product, actual files, no fake buttons. Don't claim something works unless implemented and tested. Build in stages with working code each stage. Deliver ZIP of whole app plus lists: fully implemented, partially implemented, needs external integrations, known bugs/limitations, exact deploy steps.

## Philosophy
Simple, intuitive, not overcrowded with analytics, no unnecessary jargon, familiar to X/Facebook users. Meaningful relationships, communities, opportunities, collaboration.
