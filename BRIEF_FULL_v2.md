# NETWORK — COMPLETE PROJECT BUILD & DEVELOPMENT HANDOFF (v2, from Christopher, Nov 2 2026 4:39 PM ET)
# NOTE: Complete. Sections 21–25 were sent in a follow-up message and appended below.

1. PROJECT OVERVIEW
Develop NETWORK into a fully functional, polished, responsive social and business networking platform for the crypto ecosystem (Solana traders, memecoin founders, developers, KOLs, marketing teams, researchers, crypto communities). Not simply another social media platform: an interconnected ecosystem where individuals, projects, communities and businesses establish identities, build relationships, collaborate, discover opportunities and grow together.
Brand: NETWORK. Slogan: "Build your Network. Build your Net worth." Supporting message: "Connect. Collaborate. Grow."
Core positioning: "NETWORK isn't just where you find the next opportunity. It's where you build the connections that create opportunities."
Professional, modern, intuitive, familiar (X/Facebook usability) with an original identity. Simple to understand immediately, powerful networking underneath.

2. EXISTING PROJECT FILES
Extract and inspect the whole MVP; understand backend, frontend, DB, deploy config; preserve and improve working functionality; don't rewrite unnecessarily; identify incomplete/broken/insecure/missing parts; build on the foundation; test; package a new ZIP for GitHub + Render.
MVP stack: Python, FastAPI, SQLAlchemy, PostgreSQL prod, SQLite local fallback, HTML/CSS/JS, JWT auth, password hashing, Render config.
MVP supposedly has: accounts, profiles, posts, replies, likes, reposts, feeds, public Networks, memberships, token calls, trending hashtags/tickers, basic rankings. Inspect actual implementation before assuming. Do not claim a feature works unless tested.

3. OFFICIAL DESIGN DIRECTION (VERY IMPORTANT)
The FIRST dashboard mockup (_reference/mockup.png) is definitive. Do not substitute a later design or redesign.
Identity: deep charcoal/black; neon green primary accent; modern crisp typography; rounded cards/panels; subtle borders and tasteful glow; clean spacing/hierarchy; professional crypto-tech; responsive desktop/tablet/mobile. Avoid excessive gradients, unnecessary animations, clutter, oversized analytics, complicated navigation.
Desktop 3-column layout:
LEFT SIDEBAR: My Network, Networks, Discover, Opportunities, Rankings, Messages, Notifications, My Profile.
CENTER: NETWORK welcome/banner; post composer; main Network feed; posts from joined Networks and permitted connected Networks; announcements; opportunity highlights where appropriate.
RIGHT SIDEBAR: Your Networks; Top Opportunities; Network Rankings; Network Passport widget; Create a Network CTA.
Mobile: intentionally designed, not scaled-down. Compact nav, mobile-friendly cards, easy composer, readable text, touch-friendly buttons, bottom navigation where appropriate, NO horizontal overflow, fast loading, minimal unnecessary elements. Both must feel polished.

4. THE CENTRAL CONCEPT: NETWORKS
Users create Networks around identities, projects, businesses, interests. A Network = community identity with membership, founder, admins, posts, announcements, reputation, opportunities, connections to other Networks.
Categories: Personal, Trading, KOL, Alpha Communities, Marketing, Project.
Create with: name, unique handle, description, profile image, cover image, category, public/private visibility, founder, admins, members, posts & announcements, membership settings, connection settings, activity-sharing permissions, creation date, statistics.
Roles: Founder (full control), Administrator (configurable permissions), Member (participate per settings).
Membership: discover public Networks; view Network profiles; join public; request membership in private; accept invitations; leave; view memberships; view Networks founded/administered. Private Networks must not expose restricted content to nonmembers.

5. NETWORK-TO-NETWORK CONNECTION SYSTEM (key differentiator)
Discover other Networks; send connection request; receiving founder/authorized admin approves/rejects; disconnect; show connected Networks on profiles; show pending requests; show status; founders manage connections.
Privacy: connecting must NOT automatically expose private content. Each Network controls what it shares, with explicit sharing permissions for: public announcements, selected Network posts, partnership opportunities, public events, selected activity updates. Private/member-only content stays private unless explicitly shared by an authorized user. Backend authorization checks required; frontend hiding is not sufficient.

6. NETWORK PASSPORT (every user)
Profile picture, username, display name, bio, wallet address (if voluntarily connected), social links, Networks founded, Networks joined, connected Networks, projects supported, collaboration history, achievements, endorsements received, reputation indicators, contribution history, account creation date. Visually appealing, not overloaded. Users control which info is public.

7. NETWORK OPPORTUNITIES (marketplace)
Categories: KOL partnerships, marketing campaigns, project launches, research collaborations, developer recruitment, community partnerships, sponsorships, trading collaborations, content creation, business partnerships.
Users AND Networks can: create listing; pick category; title/description; requirements; compensation or negotiable; application deadline; receive applications/expressions of interest; review applicants; accept/reject; contact applicants; mark open/filled/closed. Search and filtering. Discover opportunities relevant to their Networks and interests. Clean, not a complicated job board.

8. NETWORK REPUTATION
Rewards genuine contribution, reliability, collaboration. Earned, never purchased; no buying reputation, rankings, or followers.
Indicators: engagement quality, member retention, organic growth, consistent activity, collaboration history, fulfilled commitments, endorsements, verified trading performance (only when reliable verification exists), community contributions, research quality. Follower count is not proof of credibility. Don't claim trading performance verified without reliable market data + actual verification process.
Keep separate verification categories: wallet ownership, identity, project, trading performance. Labels transparent about exactly what was verified. Pluggable for future providers/data sources.

9. NETWORK INTELLIGENCE
Section showing: connected Networks, related projects, recent announcements, partnership activity, collaborators, growing communities, Network activity, relevant opportunities. Useful and clear, not an overwhelming analytics dashboard.

10. PROJECT LAUNCH ROOMS
Founder creates a Project Network as a workspace. Each supports: project name, logo, cover, description, team info, roadmap, announcements, community posts, partnership requests, marketing opportunities, launch countdown, project updates, connected Networks, community membership.
Journey: IDEA → COMMUNITY → CONNECTIONS → LAUNCH → GROWTH. Build community pre-token, find collaborators, connect with KOLs, recruit marketers/devs, keep using post-launch. Do NOT require a token launch or wallet connection to create a Project Network.

11. NETWORK ENDORSEMENTS
Categories: Research, Reliability, Collaboration, Leadership, Development, Marketing, Community building, Trading research. Meaningful, not another like button. Anti-manipulation: prevent duplicate/abusive endorsements; consider requiring an established interaction/contribution first. Show endorsement history and categories on Passports.

12. NETWORK RANKINGS
Categories: Top Networks, Fastest-growing Networks, Most active Networks, Top collaborators, Top contributors, Most endorsed users, Top research contributors, Project Networks. Not based only on follower counts. Don't reward spam, artificial engagement, paid activity, purchased endorsements. Clearly explain metrics. Label not-yet-verifiable metrics accurately. Extensible to more data sources.

13. CORE SOCIAL FEATURES
Accounts/profiles: registration, login, logout, secure auth, profiles, editing, profile pictures, bios, social links, optional wallet info.
Posts: create; edit/delete own; reply; like (NETWORK terminology); repost (NETWORK terminology); view threads; view user activity; view Network posts; share permitted posts across connected Networks.
Feed: My Network Feed; joined Networks' posts; permitted connected Networks' posts; public discovery feed; announcements; relevant opportunities. Sensible filtering and pagination.
Messaging: functional private 1:1 conversations, conversation list, history, sending, unread indicators, notification integration. If real-time, proper WebSocket architecture. No static fake messaging screen.
Notifications: new followers/connections, membership requests, membership approvals, Network connection requests, connection approvals, messages, replies, endorsements, opportunity applications, opportunity decisions, relevant Network announcements. Unread indicators + mark as read.

14. OFFICIAL TERMINOLOGY (use consistently)
Followers → Network Members; Following → Connected Networks; Groups → Community Networks; Create Group → Create a Network; Join Group → Join Network; Group Owner → Network Founder; Group Admin → Network Admin; Posts → Network Posts; Reposts → Re-Network; Likes → Endorsements; Feed → My Network Feed; Trending → Network Pulse; Leaderboard → Network Rankings; Invite Link → Network Invite. Don't mix conventional terms in.

15. DATABASE AND BACKEND ARCHITECTURE
Relational model covering at minimum: users, user profiles, networks, network memberships, network roles, network connection requests, network connections, network sharing permissions, posts, replies, endorsements, re-network activity, opportunities, opportunity applications, messages, conversations, notifications, reputation records, verification records, project launch rooms, network achievements, audit/activity records. Proper FKs, indexes, uniqueness constraints, relationships. No important relational data in unstructured JSON. Alembic migrations, safe schema evolution. Postgres prod, easy local dev. Pagination for feeds, messages, opportunities and other large collections; never load the whole DB into the frontend.

16. SECURITY AND PRIVACY (requirement, not future)
Secure password hashing; proper JWT; token expiration; secure secret management; backend authorization checks; input validation; SQLi protection via ORM; rate limiting on sensitive endpoints; no unauthorized data access; correct private Network permissions; correct message privacy; safe file upload validation; appropriate CORS; env-var config; errors without leaking secrets; audit logging for sensitive admin actions. Users can't modify others' profiles, posts, Network settings, roles, messages, opportunities without permission. Clearly defined founder/admin permissions. Never hardcode prod passwords, API keys, JWT secrets, wallet private keys. Never request/store seed phrases or private keys. Wallet integration (if any) uses external signing, never custody.

17. FRONTEND EXPERIENCE
Cohesive frontend wired to the real backend. Every visible control works; no do-nothing buttons; no fake hardcoded content. Loading states, empty states, error messages, success feedback, sensible confirmations. Implement: auth screens, dashboard, user profiles, Network profiles, Network discovery, Network creation, Network settings, membership management, connection management, opportunity marketplace, opportunity detail and application flows, Network Passport, rankings, notifications, messaging, Project Launch Rooms. Intuitive nav, reusable components, consistent styling, real saved data.

18. SEARCH AND DISCOVERY
Search users, Networks, projects, opportunities. Filters for Network type and categories. Useful for finding collaborators. Avoid expensive unbounded searches.

19. FUTURE-READY ARCHITECTURE
Structure so these can be added without rebuild: interactive Network Connection Graph, events and AMAs, advanced Telegram integrations, advanced analytics, wallet integrations, project verification providers, trading-performance verification, premium founder tools, enterprise Networks, advanced notification integrations. Don't add unnecessary complexity before core works. Clear separation of concerns.

20. MONETIZATION PHILOSOPHY
Future: NETWORK Pro subscriptions, premium founder tools, paid opportunity listings, business partnerships, enterprise Networks, optional transparent verification services. NOT a priority in beta. Never sell reputation, never paid rankings, never let paying users buy credibility.

21. DEVELOPMENT PRIORITIES
Build in stages, but deliver a cohesive working beta.
PHASE 1 FOUNDATION: inspect existing MVP; fix existing bugs; authentication; user profiles; core social posts; replies; endorsements; Re-Network; feed; PostgreSQL integration; database migrations; responsive dashboard; search.
PHASE 2 NETWORK ECOSYSTEM: create Networks; Network profiles; membership requests; founder/admin roles; private Networks; Network posts; Network-to-Network connection requests; approval workflows; sharing permissions; connected Network displays.
PHASE 3 BUSINESS AND COLLABORATION: Network Passport; Opportunities marketplace; opportunity applications; Project Launch Rooms; messaging; notifications; collaboration history.
PHASE 4 REPUTATION AND INTELLIGENCE: reputation records; endorsement categories; Network Intelligence; Network Rankings; achievements; verification architecture.
PHASE 5 POLISH AND BETA RELEASE: full desktop testing; full mobile testing; security testing; permission testing; database testing; performance improvements; bug fixes; documentation; GitHub-ready packaging; Render deployment configuration.
Do not spend all the development time on the visual interface while leaving the actual platform nonfunctional.

22. TESTING REQUIREMENTS (test the actual application before declaring complete)
At minimum: create a new user; log in and log out; edit a profile; create a post; reply to a post; endorse a post; Re-Network a post; create a Network; join a public Network; request access to a private Network; approve AND reject membership requests; send and approve Network connection requests; verify private content cannot be accessed without authorization; verify sharing permissions work correctly; create an opportunity; submit an application; send and receive messages; generate and read notifications; verify rankings and reputation data are based on actual records; verify the mobile interface works; verify database persistence after restarting the application.
Add automated tests for important backend endpoints and permissions. Run syntax checks, application startup checks, and database migration checks. Do not claim successful testing if tests were not actually run. Document incomplete features honestly.

23. DEPLOYMENT REQUIREMENTS (GitHub + Render)
Include: requirements.txt; render.yaml; README.md; .gitignore; environment variable documentation; database configuration; migration instructions; production startup command; health-check endpoint; local development instructions.
render.yaml must use the repository ROOT unless a real subdirectory is intentionally created. Do NOT configure a nonexistent root directory such as "frontend".
Env vars: DATABASE_URL; SECRET_KEY or JWT_SECRET; any required external service credentials. Deployment uses PostgreSQL; do not rely on SQLite persistence in production. Document external services needing separate setup. Include instructions for creating the GitHub repo and deploying via Render.

24. FINAL DELIVERABLES (actual application, not mockup/roadmap/suggestions)
Complete updated source code; working backend; working frontend; DB models and migrations; working auth; working Network creation and membership; working Network-to-Network connections and permissions; working core social; working Opportunities; Network Passport; messaging and notifications; reputation and rankings foundations; responsive desktop and mobile UI; automated tests; Render config; complete README and setup instructions; a new downloadable ZIP containing the actual completed project files (not just docs/placeholders).
Before packaging, verify file structure and that render.yaml is at the correct repository root.
Provide a concise summary of what was implemented, what was tested, and what remains incomplete. If a feature can't be completed, implement a properly structured foundation and clearly disclose its status. Never pretend unfinished functionality is complete.

25. PRODUCT PHILOSOPHY
Keep the original vision intact. NETWORK is where crypto people build meaningful relationships and communities. A trader grows from individual to respected member of a trading Network, eventually founding their own. A project founder creates a Project Network, builds community, discovers collaborators, connects with KOLs and marketing teams, grows the project. A KOL establishes professional identity, demonstrates credibility, connects with projects, discovers partnership opportunities. A developer finds projects/communities needing their skills. A marketing team finds projects seeking promotional partnerships. The real value is the relationships, communities, collaborations and opportunities, not just content.
Build your Network. Build your Net worth. NETWORK: Connect. Collaborate. Grow.
