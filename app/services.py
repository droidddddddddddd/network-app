import math
from datetime import datetime, timedelta, timezone
from statistics import median
from sqlalchemy import select, func, or_, and_, not_, exists
from sqlalchemy.orm import Session
from .models import (NetworkActivity, ACTIVITY_TYPES, User, Network, Membership, Connection, Post, Like, Follow, Block, Notification, Endorsement,
                     Opportunity, Application, Call, ChatMessage, Report, Conversation, Verification, Achievement,
                     AuditLog, ReputationRecord, Event, SHARE_KEYS, ADMIN_PERMS)
from .realtime import hub


def utcnow():
    return datetime.now(timezone.utc)


def aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt):
    return aware(dt).astimezone(timezone.utc).isoformat() if dt else None  # always UTC (Postgres returns session-tz values)


# ---------------------------------------------------------------- notifications
def notify(db: Session, user_id: int, actor_id: int | None, type_: str, text: str, link: str = "", push: bool = True):
    if not user_id or user_id == actor_id:
        return
    if actor_id and db.scalar(select(Block.id).where(Block.blocker_id == user_id, Block.blocked_id == actor_id)):
        return
    n = Notification(user_id=user_id, actor_id=actor_id, type=type_, text=text[:300], link=link)
    db.add(n)
    db.flush()
    hub.to_user(user_id, {"type": "notification", "text": n.text, "link": link, "silent": not push})


# ---------------------------------------------------------------- membership helpers
def membership(db, network_id, user_id):
    if not user_id:
        return None
    return db.scalar(select(Membership).where(Membership.network_id == network_id, Membership.user_id == user_id))


def is_active(m):
    return bool(m and m.status == "active")


def is_admin(m):
    return bool(m and m.status == "active" and m.role in ("founder", "admin"))


def can(m, perm: str) -> bool:
    """Founder: everything. Admin: only permissions the founder enabled. Member: nothing admin-level."""
    if not is_active(m): return False
    if m.role == "founder": return True
    return m.role == "admin" and bool(getattr(m, perm, False))


def perms_of(m):
    if not is_active(m) or m.role == "member": return {k: False for k in ADMIN_PERMS}
    return {k: can(m, k) for k in ADMIN_PERMS}


def audit(db, actor_id, network_id, action, target="", detail="", ip=""):
    db.add(AuditLog(actor_id=actor_id, network_id=network_id, action=action, target=str(target)[:120], detail=str(detail)[:500], ip=ip[:45]))


def my_network_ids(db, uid) -> set[int]:
    if not uid:
        return set()
    return set(db.scalars(select(Membership.network_id).where(Membership.user_id == uid, Membership.status == "active")))


def granted_by(conn: Connection, side_network_id: int) -> dict:
    """Permissions that network `side_network_id` grants to the other side of `conn`."""
    p = "req_" if conn.requester_id == side_network_id else "tgt_"
    return {k: bool(getattr(conn, p + k)) for k in SHARE_KEYS}


def connection_grants(db, my_nets: set[int]) -> dict:
    """For a viewer in `my_nets`: {share_key: set(partner network ids that grant it)}."""
    g = {k: set() for k in SHARE_KEYS}
    if not my_nets:
        return g
    conns = db.scalars(select(Connection).where(Connection.status == "approved",
                                                or_(Connection.requester_id.in_(my_nets), Connection.target_id.in_(my_nets))))
    for c in conns:
        for mine, partner in ((c.requester_id, c.target_id), (c.target_id, c.requester_id)):
            if mine in my_nets and partner not in my_nets:
                for k, v in granted_by(c, partner).items():
                    if v: g[k].add(partner)
    return g


def shared_conditions(my_nets, g):
    """Post visibility from explicit sharing grants. Private content never flows without a grant."""
    conds = []
    if my_nets: conds.append(Post.network_id.in_(my_nets))
    if g["share_announcements"]: conds.append(and_(Post.network_id.in_(g["share_announcements"]), Post.kind == "announcement"))
    if g["share_activity"]: conds.append(and_(Post.network_id.in_(g["share_activity"]), Post.kind == "update"))
    if g["share_selected"]: conds.append(and_(Post.network_id.in_(g["share_selected"]), Post.share_with_connections.is_(True)))
    return conds


def visible_filter(db, uid):
    """Server-side visibility: public networks + own networks + only what connected networks explicitly share."""
    my_nets = my_network_ids(db, uid)
    g = connection_grants(db, my_nets)
    public_nets = select(Network.id).where(Network.is_private.is_(False))
    conds = [Post.network_id.is_(None), Post.network_id.in_(public_nets)] + shared_conditions(my_nets, g)
    f = and_(Post.removed.is_(False), or_(*conds))
    f = and_(f, or_(Post.hidden.is_(False), Post.author_id == (uid or 0)))  # moderator-hidden posts stay visible to their author only
    if uid:
        blocked = select(Block.blocked_id).where(Block.blocker_id == uid)
        blockers = select(Block.blocker_id).where(Block.blocked_id == uid)
        f = and_(f, Post.author_id.not_in(blocked), Post.author_id.not_in(blockers))
    return f, my_nets, g


def can_see_post(db, uid, post: Post) -> bool:
    f, *_ = visible_filter(db, uid)
    return bool(db.scalar(select(Post.id).where(Post.id == post.id, f)))


# ---------------------------------------------------------------- serializers
def user_brief(u: User):
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "avatar_url": u.avatar_url,
            "is_demo": u.is_demo, "identity_verified": u.identity_verified}


def network_brief(n: Network, members=None):
    d = {"id": n.id, "slug": n.slug, "name": n.name, "type": n.type, "avatar_url": n.avatar_url, "cover_url": n.cover_url,
         "is_private": n.is_private, "description": n.description, "is_demo": n.is_demo}
    if members is not None:
        d["members"] = members
    return d


def member_count(db, nid):
    return db.scalar(select(func.count(Membership.id)).where(Membership.network_id == nid, Membership.status == "active")) or 0


def call_out(c: Call):
    e = c.entry_price or 0
    m = lambda v: (v / e) if e and v else None  # noqa: E731
    return {"id": c.id, "user_id": c.user_id, "network_id": c.network_id, "token_address": c.token_address,
            "symbol": c.symbol, "name": c.name, "notes": c.notes, "is_demo": c.is_demo,
            "entry_price": c.entry_price, "entry_mcap": c.entry_mcap, "entry_liquidity": c.entry_liquidity,
            "current_price": c.current_price, "current_mcap": c.current_mcap, "current_liquidity": c.current_liquidity,
            "current_multiple": m(c.current_price), "peak_multiple": m(c.peak_price),
            "result_1h": c.result_1h, "result_24h": c.result_24h, "result_7d": c.result_7d, "rugged": c.rugged,
            # "tracked" = at least one independent DexScreener check after the entry snapshot
            "independently_tracked": c.checks > 0, "checks": c.checks,
            "last_checked": iso(c.last_checked), "created_at": iso(c.created_at),
            "source": "DexScreener (api.dexscreener.com)"}


def posts_out(db, posts: list[Post], uid):
    if not posts:
        return []
    ids = [p.id for p in posts]
    orig_ids = [p.renetwork_of for p in posts if p.renetwork_of]
    originals = {}
    if orig_ids:
        f, *_ = visible_filter(db, uid)
        for o in db.scalars(select(Post).where(Post.id.in_(orig_ids), f)):
            originals[o.id] = o
    all_ids = ids + list(originals)
    cnt = lambda col, flt: dict(db.execute(select(col, func.count()).where(col.in_(all_ids), *flt).group_by(col)).all())  # noqa
    likes = cnt(Like.post_id, [])
    replies = cnt(Post.parent_id, [Post.removed.is_(False)])
    renets = cnt(Post.renetwork_of, [Post.removed.is_(False)])
    liked = set(db.scalars(select(Like.post_id).where(Like.user_id == uid, Like.post_id.in_(all_ids)))) if uid else set()
    renetted = set(db.scalars(select(Post.renetwork_of).where(Post.author_id == uid, Post.renetwork_of.in_(all_ids), Post.removed.is_(False)))) if uid else set()
    authors = {u.id: u for u in db.scalars(select(User).where(User.id.in_({p.author_id for p in posts} | {o.author_id for o in originals.values()})))}
    nets = {n.id: n for n in db.scalars(select(Network).where(Network.id.in_({p.network_id for p in list(posts) + list(originals.values()) if p.network_id})))}
    calls = {c.post_id: c for c in db.scalars(select(Call).where(Call.post_id.in_(all_ids)))}
    my_nets = my_network_ids(db, uid)

    def one(p: Post):
        n = nets.get(p.network_id)
        return {"id": p.id, "body": p.body, "image_url": p.image_url, "kind": p.kind, "parent_id": p.parent_id,
                "tags": p.tags.split() if p.tags else [], "created_at": iso(p.created_at), "is_demo": p.is_demo,
                "share_with_connections": p.share_with_connections, "edited": bool(p.edited_at),
                "author": user_brief(authors[p.author_id]),
                "network": network_brief(n) if n else None,
                "from_connection": bool(n and n.id not in my_nets and uid),
                "likes": likes.get(p.id, 0), "replies": replies.get(p.id, 0), "renetworks": renets.get(p.id, 0),
                "liked": p.id in liked, "renetworked": p.id in renetted,
                "call": call_out(calls[p.id]) if p.id in calls else None}

    out = []
    for p in posts:
        d = one(p)
        if p.renetwork_of:
            o = originals.get(p.renetwork_of)
            if not o:
                continue
            d["renetwork"] = one(o)
        out.append(d)
    return out


# ---------------------------------------------------------------- reputation (earned only)
def call_stats(calls: list[Call]):
    tracked = [c for c in calls if c.checks > 0 and c.entry_price > 0]
    peaks = [(c.peak_price / c.entry_price) if c.peak_price else 0 for c in tracked]
    wins = sum(1 for p in peaks if p >= 1.5)
    rugs = sum(1 for c in tracked if c.rugged)
    return {"total_calls": len(calls), "tracked_calls": len(tracked), "wins": wins, "rugs": rugs,
            "win_rate": wins / len(tracked) if tracked else None,
            "avg_peak": sum(peaks) / len(peaks) if peaks else None,
            "median_peak": median(peaks) if peaks else None,
            "verified": len(tracked) > 0,
            "label": "Tracked calls (DexScreener price at post time)" if tracked else "No tracked calls yet"}


def endorsement_summary(db, uid):
    rows = db.execute(select(Endorsement.category, func.count()).where(Endorsement.to_id == uid).group_by(Endorsement.category)).all()
    return {c: n for c, n in rows}


def user_reputation(db, uid):
    posts = db.scalar(select(func.count(Post.id)).where(Post.author_id == uid, Post.renetwork_of.is_(None), Post.removed.is_(False))) or 0
    my_posts = select(Post.id).where(Post.author_id == uid)
    engagers = db.scalar(select(func.count(func.distinct(Like.user_id))).where(Like.post_id.in_(my_posts), Like.user_id != uid)) or 0
    repliers = db.scalar(select(func.count(func.distinct(Post.author_id))).where(Post.parent_id.in_(my_posts), Post.author_id != uid)) or 0
    reports = db.scalar(select(func.count(Report.id)).where(Report.post_id.in_(my_posts))) or 0
    replies_given = db.scalar(select(func.count(Post.id)).where(Post.author_id == uid, Post.parent_id.is_not(None))) or 0
    net_posts = db.scalar(select(func.count(Post.id)).where(Post.author_id == uid, Post.network_id.is_not(None))) or 0
    my_opps = select(Opportunity.id).where(Opportunity.creator_id == uid)
    accepted = db.scalar(select(func.count(Application.id)).where(Application.status.in_(["accepted", "completed"]),
                                                                    or_(Application.applicant_id == uid, Application.opportunity_id.in_(my_opps)))) or 0
    completed = db.scalar(select(func.count(Application.id)).where(Application.status == "completed",
                                                                     or_(Application.applicant_id == uid, Application.opportunity_id.in_(my_opps)))) or 0
    founded = db.scalar(select(func.count(Network.id)).where(Network.founder_id == uid)) or 0
    endorsements = endorsement_summary(db, uid)
    e_total = sum(endorsements.values())
    calls = call_stats(list(db.scalars(select(Call).where(Call.user_id == uid))))
    eng_quality = min(100, ((engagers + repliers * 2) / max(posts, 1)) * 25 * min(1, (engagers + repliers) / 5)) - reports * 5
    indicators = {
        "reliability": {"value": (completed / accepted) if accepted else None, "detail": f"{completed} of {accepted} accepted collaborations completed"},
        "engagement_quality": {"value": max(0, round(eng_quality, 1)), "detail": f"{engagers} distinct likers, {repliers} distinct repliers across {posts} posts"},
        "collaboration_history": {"value": accepted, "detail": f"{accepted} accepted collaborations"},
        "fulfilled_commitments": {"value": completed, "detail": f"{completed} marked completed by both sides' workflow"},
        "community_contributions": {"value": replies_given + net_posts, "detail": f"{net_posts} network posts, {replies_given} replies"},
        "endorsements": {"value": e_total, "detail": endorsements},
        "verified_trading_performance": calls,
    }
    xp = int(max(0, eng_quality) * 10 + completed * 150 + accepted * 50 + (replies_given + net_posts) * 5 + e_total * 40 + founded * 100
             + (calls["wins"] * 50 if calls["verified"] else 0))
    level = int(math.sqrt(xp / 50)) + 1
    nxt = (level ** 2) * 50
    prev = ((level - 1) ** 2) * 50
    return {"indicators": indicators, "xp": xp, "level": level, "level_progress": (xp - prev) / max(1, nxt - prev), "next_level_xp": nxt,
            "founded": founded}


def network_reputation(db, n: Network):
    now = utcnow()
    week = now - timedelta(days=7)
    ms = list(db.scalars(select(Membership).where(Membership.network_id == n.id, Membership.status.in_(["active", "left"]))))
    active = [m for m in ms if m.status == "active"]
    old = [m for m in ms if m.joined_at and aware(m.joined_at) < week]
    retained = [m for m in old if m.status == "active"]
    retention = (len(retained) / len(old)) if old else (len(active) / len(ms) if ms else None)
    new7 = [m for m in active if m.joined_at and aware(m.joined_at) >= week]
    growth = len(new7) / max(1, len(active) - len(new7))
    month = now - timedelta(days=30)
    posts = db.scalar(select(func.count(Post.id)).where(Post.network_id == n.id, Post.removed.is_(False), Post.created_at >= month)) or 0
    posters = db.scalar(select(func.count(func.distinct(Post.author_id))).where(Post.network_id == n.id, Post.created_at >= month)) or 0
    chatters = db.scalar(select(func.count(func.distinct(ChatMessage.user_id))).where(ChatMessage.network_id == n.id, ChatMessage.created_at >= month)) or 0
    engaged_share = min(1, max(posters, chatters) / max(1, len(active)))
    conns = db.scalar(select(func.count(Connection.id)).where(Connection.status == "approved", or_(Connection.requester_id == n.id, Connection.target_id == n.id))) or 0
    opps = select(Opportunity.id).where(Opportunity.network_id == n.id)
    accepted = db.scalar(select(func.count(Application.id)).where(Application.opportunity_id.in_(opps), Application.status.in_(["accepted", "completed"]))) or 0
    completed = db.scalar(select(func.count(Application.id)).where(Application.opportunity_id.in_(opps), Application.status == "completed")) or 0
    calls = call_stats(list(db.scalars(select(Call).where(Call.network_id == n.id))))
    # ---- transparent score (0-100). Member count is NOT a factor beyond the 3-member minimum. ----
    parts = {
        "retention": 25 * (retention or 0),
        "engagement_quality": 25 * engaged_share,
        "organic_growth": 15 * min(1, growth / 0.5),
        "collaboration": 15 * min(1, (conns + accepted) / 5),
        "reliability": 10 * ((completed / accepted) if accepted else 0),
        "verified_performance": 10 * min(1, (calls["win_rate"] or 0) / 0.5) if calls["verified"] else 0,
    }
    return {
        "members": len(active), "eligible": len(active) >= 3,
        "indicators": {
            "member_retention": {"value": retention, "detail": f"{len(retained)} of {len(old)} members who joined 7+ days ago are still here" if old else "Not enough history yet"},
            "organic_growth": {"value": growth, "detail": f"{len(new7)} new members in 7 days (no paid or bought members possible)"},
            "engagement_quality": {"value": engaged_share, "detail": f"{max(posters, chatters)} of {len(active)} members posted or chatted in 30 days"},
            "collaboration_history": {"value": conns + accepted, "detail": f"{conns} approved connections, {accepted} accepted collaborations"},
            "reliability": {"value": (completed / accepted) if accepted else None, "detail": f"{completed} of {accepted} collaborations completed"},
            "verified_trading_performance": calls,
        },
        "score_parts": {k: round(v, 1) for k, v in parts.items()},
        "score": round(sum(parts.values()), 1),
    }


RANKING_METHOD = [
    ("Member retention", 25, "Share of members who joined 7+ days ago and are still active."),
    ("Engagement quality", 25, "Share of members who posted or chatted in the last 30 days — not raw likes."),
    ("Organic growth", 15, "New members in the last 7 days relative to size (full marks at +50%)."),
    ("Collaboration", 15, "Approved network connections + accepted collaborations (full marks at 5)."),
    ("Reliability", 10, "Completed collaborations ÷ accepted collaborations."),
    ("Verified trading performance", 10, "Only calls independently tracked by the DexScreener job count; win = peak ≥ 1.5×. 0 if none tracked."),
]


# ---------------------------------------------------------------- conversations
def conversation_for(db, a: int, b: int, create=True):
    lo, hi = min(a, b), max(a, b)
    c = db.scalar(select(Conversation).where(Conversation.user_a_id == lo, Conversation.user_b_id == hi))
    if not c and create:
        c = Conversation(user_a_id=lo, user_b_id=hi); db.add(c); db.flush()
    return c


# ---------------------------------------------------------------- verification (separate kinds, pluggable providers)
VERIFY_LABELS = {
    "wallet": ("Wallet ownership", "Proves control of a Solana wallet: you signed a one-time message with it (signMessage only, never a transaction). "
               "It says nothing about trustworthiness or trading performance."),
    "identity": ("Identity", "Needs a KYC provider. None is connected in this beta, so identity can't be verified yet."),
    "project": ("Project domain", "Proves the team controls the project's website domain (DNS TXT record or /.well-known/network-verify.txt)."),
    "devwallet": ("Dev wallet", "Proves the Network signed with the wallet that created the token on-chain. It proves control of the creator wallet only, not that the project is safe."),
    "metadata": ("Metadata authority", "Proves the team signed with the token's Metaplex update-authority wallet. Control only, not safety."),
    "trading": ("Tracked calls", "Only calls independently tracked by NETWORK's DexScreener job count. Self-reported results never count."),
}


def verification_status(db, subject_type: str, subject_id: int, trading: dict | None = None):
    rows = {}
    for v in db.scalars(select(Verification).where(Verification.subject_type == subject_type, Verification.subject_id == subject_id).order_by(Verification.id)):
        if v.kind not in rows or v.status == "verified" or rows[v.kind].status != "verified": rows[v.kind] = v
    out = {}
    kinds = ["wallet", "identity", "trading"] if subject_type == "user" else ["project", "devwallet", "metadata", "identity", "trading"]
    for k in kinds:
        label, how = VERIFY_LABELS[k]
        if k == "trading":
            ok = bool(trading and trading.get("verified"))
            out[k] = {"label": label, "verified": ok, "status": "tracked" if ok else "no tracked calls",
                      "provider": "NETWORK DexScreener tracker" if ok else "", "how": how,
                      "detail": trading.get("label", "") if trading else ""}
        elif k == "identity":
            out[k] = {"label": label, "verified": False, "status": "needs KYC provider", "provider": "", "how": how,
                      "detail": "Identity verification: pending, needs a KYC provider (not connected)."}
        else:
            r = rows.get(k)
            out[k] = {"label": label, "verified": bool(r and r.status == "verified"), "status": r.status if r else "unverified",
                      "provider": r.provider if r else "", "how": how, "detail": r.detail if r else "", "method": r.method if r else "",
                      "value": r.value if r else "", "checked_at": iso(r.decided_at) if r and r.decided_at else None}
    return out


def record_activity(db, network_id, type_, text, link=""):
    """Structured activity a Network can selectively share with connected Networks (see connections activity picker)."""
    db.add(NetworkActivity(network_id=network_id, type=type_, text=text[:300], link=link[:200]))


def activity_types_of(conn, side_network_id) -> set:
    p = "req_" if conn.requester_id == side_network_id else "tgt_"
    return {t for t in (getattr(conn, p + "activity_types") or "").split(",") if t in ACTIVITY_TYPES}


# ---------------------------------------------------------------- achievements (earned by rules, persisted)
def award(db, subject_type, subject_id, code, name, desc):
    if not db.scalar(select(Achievement.id).where(Achievement.subject_type == subject_type, Achievement.subject_id == subject_id, Achievement.code == code)):
        db.add(Achievement(subject_type=subject_type, subject_id=subject_id, code=code, name=name, description=desc))
        if subject_type == "network":
            record_activity(db, subject_id, "achievements", f"Earned the achievement: {name}")


def award_user_achievements(db, u, rep, founded_n, joined_n, conns_n):
    ind = rep["indicators"]
    if founded_n: award(db, "user", u.id, "founder", "Network Founder", "Founded a Network")
    if conns_n: award(db, "user", u.id, "connector", "Connector", "Founded a Network with approved connections")
    if ind["endorsements"]["value"] >= 3: award(db, "user", u.id, "endorsed", "Endorsed", "Received 3+ peer endorsements")
    if ind["fulfilled_commitments"]["value"]: award(db, "user", u.id, "delivers", "Delivers", "Completed a collaboration")
    if ind["verified_trading_performance"]["verified"]: award(db, "user", u.id, "tracked_caller", "Tracked Caller", "Has independently tracked calls")
    if joined_n >= 3: award(db, "user", u.id, "community_builder", "Community Builder", "Active in 3+ Networks")
    db.flush()
    return [{"code": a.code, "name": a.name, "desc": a.description, "awarded_at": iso(a.awarded_at)}
            for a in db.scalars(select(Achievement).where(Achievement.subject_type == "user", Achievement.subject_id == u.id).order_by(Achievement.id))]


def snapshot_reputation(db, subject_type, subject_id, score, level=1):
    last = db.scalar(select(ReputationRecord).where(ReputationRecord.subject_type == subject_type, ReputationRecord.subject_id == subject_id)
                     .order_by(ReputationRecord.id.desc()).limit(1))
    if not last or utcnow() - aware(last.created_at) > timedelta(hours=1):
        db.add(ReputationRecord(subject_type=subject_type, subject_id=subject_id, score=score, level=level))
