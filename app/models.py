from datetime import datetime, timezone
from sqlalchemy import (String, Integer, Text, Boolean, DateTime, ForeignKey, Float, LargeBinary, BigInteger,
                        UniqueConstraint, CheckConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def now():
    return datetime.now(timezone.utc)


TS = lambda: mapped_column(DateTime(timezone=True), default=now, nullable=False)  # noqa: E731
FK = lambda t, **kw: mapped_column(ForeignKey(t, ondelete="CASCADE"), **kw)  # noqa: E731

NETWORK_TYPES = ["Personal", "Trading", "KOL", "Alpha Communities", "Marketing", "Project"]
ROLES = ["founder", "admin", "member"]
ENDORSE_CATS = ["Research", "Reliability", "Collaboration", "Leadership", "Development", "Marketing",
                "Community building", "Trading research"]
OPP_CATS = ["KOL partnerships", "Marketing campaigns", "Project launches", "Research collaborations",
            "Developer recruitment", "Community partnerships", "Sponsorships", "Trading collaborations",
            "Content creation", "Business partnerships"]
# What a network can share with a connected network (each side sets its own, default nothing)
SHARE_KEYS = ["share_announcements", "share_selected", "share_opportunities", "share_events", "share_activity", "display_public"]
# Configurable admin permissions (founder always has all)
ADMIN_PERMS = ["perm_members", "perm_announce", "perm_connections", "perm_settings", "perm_moderate", "perm_opportunities"]
VERIFY_KINDS = ["wallet", "identity", "project", "trading", "devwallet", "metadata"]
ACTIVITY_TYPES = ["new_members", "opportunities_filled", "launches", "events", "achievements"]
USER_ROLES = ["Trader", "Founder", "KOL", "Developer", "Marketer", "Researcher", "Community builder", "Investor"]
PRIVACY_KEYS = ["show_wallet", "show_socials", "show_networks", "show_endorsements", "show_contributions", "show_achievements"]
PROJECT_STAGES = ["Idea", "Community", "Connections", "Launch", "Growth"]


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(50))
    bio: Mapped[str] = mapped_column(String(300), default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    x_handle: Mapped[str] = mapped_column(String(20), default="")
    telegram: Mapped[str] = mapped_column(String(40), default="")
    website: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(20), default="")
    interests: Mapped[str] = mapped_column(String(600), default="")  # comma-separated
    # Passport privacy controls: what is shown to other people
    show_wallet: Mapped[bool] = mapped_column(Boolean, default=False)
    show_socials: Mapped[bool] = mapped_column(Boolean, default=True)
    show_networks: Mapped[bool] = mapped_column(Boolean, default=True)
    show_endorsements: Mapped[bool] = mapped_column(Boolean, default=True)
    show_contributions: Mapped[bool] = mapped_column(Boolean, default=True)
    show_achievements: Mapped[bool] = mapped_column(Boolean, default=True)
    wallet_address: Mapped[str] = mapped_column(String(64), default="")  # display only, NOT verified
    # Separate verification types. None can be self-set; all False until a real integration exists.
    wallet_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspend_reason: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = TS()


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "followee_id"), CheckConstraint("follower_id <> followee_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    follower_id: Mapped[int] = FK("users.id", index=True)
    followee_id: Mapped[int] = FK("users.id", index=True)
    created_at: Mapped[datetime] = TS()


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("blocker_id", "blocked_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    blocker_id: Mapped[int] = FK("users.id", index=True)
    blocked_id: Mapped[int] = FK("users.id", index=True)


class Network(Base):
    __tablename__ = "networks"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(60))
    type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(1000), default="")
    cover_url: Mapped[str] = mapped_column(String(500), default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    founder_id: Mapped[int] = FK("users.id", index=True)
    # Project Launch Room fields (used when type == Project)
    stage: Mapped[str] = mapped_column(String(20), default="Idea")
    launch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    team_info: Mapped[str] = mapped_column(Text, default="")
    roadmap: Mapped[str] = mapped_column(Text, default="")
    token_address: Mapped[str] = mapped_column(String(64), default="")
    project_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # set only from a Verification record
    # membership / connection settings
    members_can_post: Mapped[bool] = mapped_column(Boolean, default=True)
    accept_connections: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("network_id", "user_id"),
                      CheckConstraint("role in ('founder','admin','member')"),
                      CheckConstraint("status in ('active','pending','left','removed','rejected')"))
    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = FK("networks.id", index=True)
    user_id: Mapped[int] = FK("users.id", index=True)
    role: Mapped[str] = mapped_column(String(10), default="member")
    status: Mapped[str] = mapped_column(String(10), default="active")
    requested_at: Mapped[datetime] = TS()
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # configurable admin permissions (only meaningful when role == admin)
    perm_members: Mapped[bool] = mapped_column(Boolean, default=True)
    perm_announce: Mapped[bool] = mapped_column(Boolean, default=True)
    perm_connections: Mapped[bool] = mapped_column(Boolean, default=True)
    perm_settings: Mapped[bool] = mapped_column(Boolean, default=False)
    perm_moderate: Mapped[bool] = mapped_column(Boolean, default=True)
    perm_opportunities: Mapped[bool] = mapped_column(Boolean, default=True)


class Connection(Base):
    """Network-to-network link. Each side controls what IT shares with the other side."""
    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("requester_id", "target_id"), CheckConstraint("requester_id <> target_id"),
                      CheckConstraint("status in ('pending','approved','rejected')"))
    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = FK("networks.id", index=True)
    target_id: Mapped[int] = FK("networks.id", index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    message: Mapped[str] = mapped_column(String(500), default="")
    requested_by: Mapped[int] = FK("users.id")
    # permissions granted BY requester TO target (req_*) and BY target TO requester (tgt_*)
    req_share_announcements: Mapped[bool] = mapped_column(Boolean, default=False)
    req_share_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    req_share_opportunities: Mapped[bool] = mapped_column(Boolean, default=False)
    req_share_events: Mapped[bool] = mapped_column(Boolean, default=False)
    req_share_activity: Mapped[bool] = mapped_column(Boolean, default=False)
    req_display_public: Mapped[bool] = mapped_column(Boolean, default=False)
    tgt_share_announcements: Mapped[bool] = mapped_column(Boolean, default=False)
    tgt_share_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    tgt_share_opportunities: Mapped[bool] = mapped_column(Boolean, default=False)
    tgt_share_events: Mapped[bool] = mapped_column(Boolean, default=False)
    tgt_share_activity: Mapped[bool] = mapped_column(Boolean, default=False)
    tgt_display_public: Mapped[bool] = mapped_column(Boolean, default=False)
    req_activity_types: Mapped[str] = mapped_column(String(200), default="")  # comma list of ACTIVITY_TYPES the requester shares
    tgt_activity_types: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = TS()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (CheckConstraint("kind in ('post','announcement','update')"), Index("ix_posts_created", "created_at"))
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = FK("users.id", index=True)
    network_id: Mapped[int | None] = FK("networks.id", nullable=True, index=True)
    parent_id: Mapped[int | None] = FK("posts.id", nullable=True, index=True)
    renetwork_of: Mapped[int | None] = FK("posts.id", nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(15), default="post")
    body: Mapped[str] = mapped_column(String(2000), default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    # "selected post": founder/admin marks a network post as shareable with connected networks
    share_with_connections: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[str] = mapped_column(String(500), default="")  # space separated $TICKERS / #tags / addresses
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)  # hidden by a moderator (visible to author only)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = FK("users.id", index=True)
    post_id: Mapped[int] = FK("posts.id", index=True)


class Report(Base):
    """A report about a post, user or Network. Post reports inside a Network go to that Network's moderators;
    everything is also visible to platform admins (ADMIN_USERNAMES)."""
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("reporter_id", "target_type", "target_id"),
                      CheckConstraint("target_type in ('post','user','network')"), Index("ix_reports_status", "status"))
    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = FK("users.id")
    target_type: Mapped[str] = mapped_column(String(10), default="post")
    target_id: Mapped[int] = mapped_column(Integer, default=0)
    post_id: Mapped[int | None] = FK("posts.id", nullable=True, index=True)
    network_id: Mapped[int | None] = FK("networks.id", nullable=True, index=True)  # moderation scope
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="open")
    resolution: Mapped[str] = mapped_column(String(40), default="")
    resolved_by: Mapped[int | None] = FK("users.id", nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = TS()


class Endorsement(Base):
    __tablename__ = "endorsements"
    __table_args__ = (UniqueConstraint("from_id", "to_id", "category"), CheckConstraint("from_id <> to_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    from_id: Mapped[int] = FK("users.id", index=True)
    to_id: Mapped[int] = FK("users.id", index=True)
    category: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(String(300), default="")
    basis: Mapped[str] = mapped_column(String(100), default="")  # why endorser is eligible (shared network / collaboration)
    created_at: Mapped[datetime] = TS()


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (CheckConstraint("status in ('open','filled','closed')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = FK("users.id", index=True)
    network_id: Mapped[int | None] = FK("networks.id", nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(3000))
    requirements: Mapped[str] = mapped_column(String(2000), default="")
    compensation: Mapped[str] = mapped_column(String(120), default="")
    negotiable: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("opportunity_id", "applicant_id"),
                      CheckConstraint("kind in ('interest','application')"),
                      CheckConstraint("status in ('pending','accepted','rejected','completed')"))
    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = FK("opportunities.id", index=True)
    applicant_id: Mapped[int] = FK("users.id", index=True)
    kind: Mapped[str] = mapped_column(String(12), default="interest")
    message: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[str] = mapped_column(String(10), default="pending")
    created_at: Mapped[datetime] = TS()


class Conversation(Base):
    """1:1 conversation. user_a_id < user_b_id so each pair has exactly one row."""
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id"), CheckConstraint("user_a_id < user_b_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    user_a_id: Mapped[int] = FK("users.id", index=True)
    user_b_id: Mapped[int] = FK("users.id", index=True)
    last_at: Mapped[datetime] = TS()


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = FK("conversations.id", index=True)
    sender_id: Mapped[int] = FK("users.id", index=True)
    recipient_id: Mapped[int] = FK("users.id", index=True)
    body: Mapped[str] = mapped_column(String(2000))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = FK("users.id", index=True)
    actor_id: Mapped[int | None] = FK("users.id", nullable=True)
    type: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(String(300))
    link: Mapped[str] = mapped_column(String(200), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class Call(Base):
    """Token call. Prices come ONLY from the DexScreener tracker; `tracked` means independently checked."""
    __tablename__ = "calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = FK("users.id", index=True)
    network_id: Mapped[int | None] = FK("networks.id", nullable=True, index=True)
    post_id: Mapped[int | None] = FK("posts.id", nullable=True)
    token_address: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(30), default="")
    name: Mapped[str] = mapped_column(String(80), default="")
    notes: Mapped[str] = mapped_column(String(500), default="")
    entry_price: Mapped[float] = mapped_column(Float, default=0)
    entry_mcap: Mapped[float] = mapped_column(Float, default=0)
    entry_liquidity: Mapped[float] = mapped_column(Float, default=0)
    current_price: Mapped[float] = mapped_column(Float, default=0)
    current_mcap: Mapped[float] = mapped_column(Float, default=0)
    current_liquidity: Mapped[float] = mapped_column(Float, default=0)
    peak_price: Mapped[float] = mapped_column(Float, default=0)
    result_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    rugged: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[int] = mapped_column(Integer, default=0)  # tracker checks after the entry snapshot
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = FK("networks.id", index=True)
    user_id: Mapped[int] = FK("users.id", index=True)
    body: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = TS()


class Event(Base):
    """Network event (AMA, spaces, launch). Public events can be shared with connected networks."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = FK("networks.id", index=True)
    created_by: Mapped[int] = FK("users.id")
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(1000), default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    link: Mapped[str] = mapped_column(String(300), default="")
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class Invite(Base):
    """Network Invite: a code link, optionally addressed to one user."""
    __tablename__ = "invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    network_id: Mapped[int] = FK("networks.id", index=True)
    created_by: Mapped[int] = FK("users.id")
    invitee_id: Mapped[int | None] = FK("users.id", nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=25)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class Verification(Base):
    """One record per verification attempt. Kinds are separate: wallet / identity / project / trading.
    Providers are pluggable; in this beta no external provider is connected, so nothing is marked verified
    except trading performance, which comes from the platform's own DexScreener tracker (computed, not stored)."""
    __tablename__ = "verifications"
    __table_args__ = (CheckConstraint("kind in ('wallet','identity','project','trading','devwallet','metadata')"),
                      CheckConstraint("status in ('pending','verified','rejected','revoked','failed')"),
                      CheckConstraint("subject_type in ('user','network')"), Index("ix_verif_subject", "subject_type", "subject_id"))
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(10))
    subject_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    provider: Mapped[str] = mapped_column(String(40), default="")
    detail: Mapped[str] = mapped_column(String(300), default="")
    requested_by: Mapped[int | None] = FK("users.id", nullable=True)
    method: Mapped[str] = mapped_column(String(80), default="")      # e.g. "ed25519 signMessage", "pump.fun bonding curve creator"
    value: Mapped[str] = mapped_column(String(200), default="")      # wallet / mint / domain being verified
    address: Mapped[str] = mapped_column(String(64), default="")     # signing wallet
    challenge: Mapped[str] = mapped_column(String(80), default="")   # domain token
    created_at: Mapped[datetime] = TS()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Achievement(Base):
    """Earned achievements for users or networks, awarded by rules in services.award_achievements."""
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("subject_type", "subject_id", "code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(10))
    subject_id: Mapped[int] = mapped_column(Integer, index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(200))
    awarded_at: Mapped[datetime] = TS()


class ReputationRecord(Base):
    """Snapshot of computed reputation (history / growth over time). Written at most hourly per subject."""
    __tablename__ = "reputation_records"
    __table_args__ = (Index("ix_rep_subject", "subject_type", "subject_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(10))
    subject_id: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    level: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = TS()


class AuditLog(Base):
    """Audit trail of sensitive admin / founder actions."""
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = FK("users.id", nullable=True, index=True)
    network_id: Mapped[int | None] = FK("networks.id", nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50))
    target: Mapped[str] = mapped_column(String(120), default="")
    detail: Mapped[str] = mapped_column(String(500), default="")
    ip: Mapped[str] = mapped_column(String(45), default="")
    created_at: Mapped[datetime] = TS()


class Nonce(Base):
    """One-time sign-in-with-Solana style challenge. Only message signing; never a transaction."""
    __tablename__ = "nonces"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = FK("users.id", index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    nonce: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    message: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(String(64), default="")
    subject: Mapped[str] = mapped_column(String(120), default="")  # mint / network slug / claim id
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = TS()


class Media(Base):
    """Uploaded images stored in the database (default in production; survives Render's ephemeral disk)."""
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    content_type: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    owner_id: Mapped[int | None] = FK("users.id", nullable=True)
    created_at: Mapped[datetime] = TS()


class RateHit(Base):
    """DB-backed sliding-window rate limiting: safe across processes / instances."""
    __tablename__ = "rate_hits"
    __table_args__ = (Index("ix_rate_key_ts", "key", "ts"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160))
    ts: Mapped[float] = mapped_column(Float)


class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), default="", index=True)
    data: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = TS()


class NetworkActivity(Base):
    """Structured activity updates a Network can selectively share with connected Networks."""
    __tablename__ = "network_activity"
    __table_args__ = (Index("ix_activity_net", "network_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = FK("networks.id")
    type: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(String(300))
    link: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = TS()


class CtoClaim(Base):
    """A Project Network's community-takeover claim on a token mint, backed by signed holder wallets."""
    __tablename__ = "cto_claims"
    __table_args__ = (UniqueConstraint("network_id", "mint"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = FK("networks.id", index=True)
    mint: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(30), default="")
    created_by: Mapped[int] = FK("users.id")
    status: Mapped[str] = mapped_column(String(10), default="active")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    backers_count: Mapped[int] = mapped_column(Integer, default=0)
    backed_pct: Mapped[float] = mapped_column(Float, default=0)
    result: Mapped[str] = mapped_column(Text, default="")  # JSON of the last evaluation
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = TS()


class CtoBacking(Base):
    """One backing per wallet per mint (switching moves it). Balances are read live at evaluation time."""
    __tablename__ = "cto_backings"
    __table_args__ = (UniqueConstraint("mint", "wallet"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = FK("cto_claims.id", index=True)
    mint: Mapped[str] = mapped_column(String(64), index=True)
    wallet: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = FK("users.id")
    signature: Mapped[str] = mapped_column(String(120))
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_funder: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = TS()
