import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from .models import NETWORK_TYPES, ENDORSE_CATS, OPP_CATS, PROJECT_STAGES

USER_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    username: str
    email: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=50)

    @field_validator("username")
    @classmethod
    def v_user(cls, v):
        if not USER_RE.match(v): raise ValueError("Username must be 3–20 letters, numbers or underscores.")
        return v

    @field_validator("email")
    @classmethod
    def v_email(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v) or len(v) > 254: raise ValueError("Enter a valid email address.")
        return v

    @field_validator("password")
    @classmethod
    def v_pw(cls, v):
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)): raise ValueError("Password needs at least one letter and one number.")
        return v


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ProfileIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=50)
    bio: str = Field(default="", max_length=300)
    avatar_url: str = Field(default="", max_length=500)
    x_handle: str = Field(default="", max_length=20)
    wallet_address: str = Field(default="", max_length=64)
    telegram: str = Field(default="", max_length=40)
    website: str = Field(default="", max_length=200)
    show_wallet: bool | None = None
    show_socials: bool | None = None
    show_networks: bool | None = None
    show_endorsements: bool | None = None
    show_contributions: bool | None = None
    show_achievements: bool | None = None

    @field_validator("telegram")
    @classmethod
    def tg(cls, v):
        v = v.strip().lstrip("@")
        if v and not re.match(r"^[A-Za-z0-9_]{5,32}$", v): raise ValueError("Telegram: 5–32 letters, numbers or underscores.")
        return v

    @field_validator("website")
    @classmethod
    def web(cls, v):
        v = v.strip()
        if v and not re.match(r"^https?://[^\s]{3,}$", v): raise ValueError("Website must start with http:// or https://")
        return v

    @field_validator("x_handle")
    @classmethod
    def v_x(cls, v):
        v = v.strip().lstrip("@")
        if v and not re.match(r"^[A-Za-z0-9_]{1,15}$", v): raise ValueError("X handle: up to 15 letters, numbers or underscores.")
        return v

    @field_validator("wallet_address")
    @classmethod
    def v_w(cls, v):
        v = v.strip()
        if v and not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", v): raise ValueError("Wallet must be a Solana address (base58, 32–44 chars).")
        return v


class PostIn(BaseModel):
    body: str = Field(default="", max_length=2000)
    image_url: str = Field(default="", max_length=500)
    network_id: int | None = None
    parent_id: int | None = None
    kind: str = "post"
    share_with_connections: bool = False

    @field_validator("kind")
    @classmethod
    def v_kind(cls, v):
        if v not in ("post", "announcement", "update"): raise ValueError("Invalid post type.")
        return v


class NetworkIn(BaseModel):
    name: str = Field(min_length=3, max_length=60)
    slug: str = Field(default="", max_length=40)
    type: str
    description: str = Field(default="", max_length=1000)
    is_private: bool = False
    avatar_url: str = Field(default="", max_length=500)
    cover_url: str = Field(default="", max_length=500)

    @field_validator("type")
    @classmethod
    def v_type(cls, v):
        if v not in NETWORK_TYPES: raise ValueError(f"Type must be one of: {', '.join(NETWORK_TYPES)}.")
        return v


class NetworkUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=60)
    description: str | None = Field(default=None, max_length=1000)
    is_private: bool | None = None
    avatar_url: str | None = Field(default=None, max_length=500)
    cover_url: str | None = Field(default=None, max_length=500)
    stage: str | None = None
    launch_at: datetime | None = None
    team_info: str | None = Field(default=None, max_length=3000)
    roadmap: str | None = Field(default=None, max_length=3000)
    token_address: str | None = Field(default=None, max_length=64)
    members_can_post: bool | None = None
    accept_connections: bool | None = None

    @field_validator("stage")
    @classmethod
    def v_stage(cls, v):
        if v is not None and v not in PROJECT_STAGES: raise ValueError("Invalid stage.")
        return v


class MemberAction(BaseModel):
    action: str

    @field_validator("action")
    @classmethod
    def v(cls, v):
        if v not in ("approve", "reject", "make_admin", "make_member", "remove"): raise ValueError("Invalid action.")
        return v


class PostEdit(BaseModel):
    body: str = Field(default="", max_length=2000)


class Perms(BaseModel):
    share_announcements: bool = False
    share_selected: bool = False
    share_opportunities: bool = False
    share_events: bool = False
    share_activity: bool = False
    display_public: bool = False
    activity_types: list[str] = Field(default_factory=list, max_length=10)


class AdminPerms(BaseModel):
    perm_members: bool = True
    perm_announce: bool = True
    perm_connections: bool = True
    perm_settings: bool = False
    perm_moderate: bool = True
    perm_opportunities: bool = True


class InviteIn(BaseModel):
    username: str = Field(default="", max_length=20)
    max_uses: int = Field(default=25, ge=1, le=500)
    days: int = Field(default=7, ge=1, le=60)


class EventIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)
    starts_at: datetime
    link: str = Field(default="", max_length=300)
    is_public: bool = True


class VerifyIn(BaseModel):
    kind: str
    network_slug: str = Field(default="", max_length=40)
    detail: str = Field(default="", max_length=300)

    @field_validator("kind")
    @classmethod
    def k(cls, v):
        if v not in ("wallet", "identity", "project"): raise ValueError("Kind must be wallet, identity or project (trading is verified automatically by the tracker).")
        return v


class OppStatus(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def st(cls, v):
        if v not in ("open", "filled", "closed"): raise ValueError("Status must be open, filled or closed.")
        return v


class ConnectionIn(BaseModel):
    target_slug: str = Field(min_length=1, max_length=40)
    message: str = Field(default="", max_length=500)
    permissions: Perms = Perms()


class ConnectionDecision(BaseModel):
    action: str
    permissions: Perms = Perms()

    @field_validator("action")
    @classmethod
    def v(cls, v):
        if v not in ("approve", "reject"): raise ValueError("Invalid action.")
        return v


class OpportunityIn(BaseModel):
    category: str
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=20, max_length=3000)
    requirements: str = Field(default="", max_length=2000)
    compensation: str = Field(default="", max_length=120)
    negotiable: bool = False
    deadline: datetime | None = None
    network_id: int | None = None

    @field_validator("category")
    @classmethod
    def v(cls, v):
        if v not in OPP_CATS: raise ValueError("Pick a valid category.")
        return v


class ApplyIn(BaseModel):
    kind: str = "interest"
    message: str = Field(default="", max_length=2000)

    @field_validator("kind")
    @classmethod
    def v(cls, v):
        if v not in ("interest", "application"): raise ValueError("Invalid type.")
        return v


class AppDecision(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def v(cls, v):
        if v not in ("accepted", "rejected", "completed"): raise ValueError("Invalid status.")
        return v


class EndorseIn(BaseModel):
    category: str
    note: str = Field(default="", max_length=300)

    @field_validator("category")
    @classmethod
    def v(cls, v):
        if v not in ENDORSE_CATS: raise ValueError("Pick a valid endorsement category.")
        return v


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CallIn(BaseModel):
    token_address: str
    notes: str = Field(default="", max_length=500)
    network_id: int | None = None

    @field_validator("token_address")
    @classmethod
    def v(cls, v):
        v = v.strip()
        if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", v): raise ValueError("Enter a valid Solana token contract address.")
        return v


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class ReportCreate(BaseModel):
    target_type: str = Field(pattern="^(post|user|network)$")
    target: str = Field(min_length=1, max_length=40)  # post id, username or network slug
    reason: str = Field(min_length=3, max_length=300)


class ResolveIn(BaseModel):
    action: str = Field(pattern="^(dismiss|hide_post|remove_post|suspend_user)$")
    note: str = Field(default="", max_length=300)
    suspend_hours: int | None = Field(default=None, ge=1, le=24 * 365)  # None = indefinite


class OnboardingIn(BaseModel):
    role: str = Field("", max_length=20)
    interests: list[str] = Field(default_factory=list, max_length=20)
