import os, re, uuid, asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, WebSocket, WebSocketDisconnect, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import get_db, SessionLocal, IS_SQLITE
from .models import (User, Follow, Block, Network, Membership, Connection, Post, Like, Report, Endorsement, Opportunity,
                     Application, Message, Notification, Call, ChatMessage, Conversation, Event, Invite, Verification, Achievement,
                     AuditLog, Nonce, Media, RankingSnapshot, NetworkActivity, CtoClaim, CtoBacking, ACTIVITY_TYPES, NETWORK_TYPES, ENDORSE_CATS, OPP_CATS, PROJECT_STAGES, SHARE_KEYS, ADMIN_PERMS, PRIVACY_KEYS, USER_ROLES)
import secrets
from fastapi.middleware.cors import CORSMiddleware
from .schemas import *  # noqa: F403
from .security import (hash_pw, check_pw, set_session, COOKIE, optional_user, current_user, rate_limit, clean, clean_url,
                       extract_tags, extract_mentions, read_token, PROD, is_platform_admin, ensure_active, suspended)
from .services import *  # noqa: F403
from .services import RANKING_METHOD
from .realtime import hub
from . import dex, storage

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
UPLOADS = Path(os.getenv("UPLOAD_DIR", ROOT / "uploads"))
UPLOADS.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app):
    hub.loop = asyncio.get_running_loop()
    from .db import URL as _DBURL
    await asyncio.to_thread(hub.start, _DBURL)  # no-op unless REALTIME_BACKEND=postgres
    task = asyncio.create_task(dex.tracker_loop()) if os.getenv("DISABLE_TRACKER") != "1" else None
    cto_task = asyncio.create_task(cto_loop()) if os.getenv("DISABLE_TRACKER") != "1" else None
    yield
    hub.stop()
    for t in (task, cto_task):
        if t: t.cancel()


async def cto_loop():
    every = int(os.getenv("CTO_RECHECK_SECONDS", "3600"))
    await asyncio.sleep(30)
    while True:
        try:
            from .trust import recheck_all
            await asyncio.to_thread(recheck_all)
        except Exception as e:
            print("[cto] error:", e)
        await asyncio.sleep(every)


app = FastAPI(title="NETWORK", version="1.0.0", lifespan=lifespan, docs_url=None if PROD else "/api/docs", redoc_url=None,
              openapi_url=None if PROD else "/openapi.json")  # no schema dump in production
# CORS: same-origin by default. Only origins listed in CORS_ORIGINS (comma separated) may call the API cross-site.
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["content-type", "x-csrf", "authorization"])


def ip_of(request: Request | None):
    return (request.client.host if request and request.client else "") or ""


# ---------------------------------------------------------------- security middleware
@app.middleware("http")
async def security(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
        # CSRF: SameSite=Lax cookie + mandatory custom header (cross-site forms can't set it; no CORS is enabled)
        if request.headers.get("x-csrf") != "1":
            return JSONResponse({"detail": "CSRF check failed."}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' https: data: blob:; style-src 'self' 'unsafe-inline'; "
                                               "script-src 'self'; connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if PROD:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    msgs = []
    for e in exc.errors():
        field = ".".join(str(x) for x in e.get("loc", [])[1:])
        m = str(e.get("msg", "Invalid value")).replace("Value error, ", "")
        msgs.append(f"{field}: {m}" if field else m)
    return JSONResponse({"detail": "; ".join(msgs) or "Invalid input."}, status_code=422)


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That already exists or conflicts with existing data.")


def get_network(db, slug) -> Network:
    n = db.scalar(select(Network).where(Network.slug == slug))
    if not n: raise HTTPException(404, "Network not found.")
    return n


def get_user_by_name(db, username) -> User:
    u = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
    if not u: raise HTTPException(404, "User not found.")
    return u


def me_out(db, u: User):
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == u.id, Notification.read.is_(False))) or 0
    unread_dm = db.scalar(select(func.count(Message.id)).where(Message.recipient_id == u.id, Message.read.is_(False))) or 0
    rep = user_reputation(db, u.id)
    from .oauth import has_password, PLACEHOLDER_EMAIL
    return {**user_brief(u), "email": "" if u.email.endswith(PLACEHOLDER_EMAIL) else u.email, "has_password": has_password(u),
            "linked_accounts": linked_accounts_out(db, u.id, True), "bio": u.bio, "x_handle": u.x_handle, "telegram": u.telegram, "website": u.website,
            "wallet_address": u.wallet_address, "wallet_verified": u.wallet_verified,
            "privacy": {k: getattr(u, k) for k in PRIVACY_KEYS}, "unread_notifications": unread, "unread_messages": unread_dm,
            "level": rep["level"], "xp": rep["xp"], "level_progress": rep["level_progress"],
            "role": u.role or "", "interests": [x for x in (u.interests or "").split(",") if x],
            "is_platform_admin": is_platform_admin(u), "suspended": suspended(u),
            "suspended_until": iso(u.suspended_until) if suspended(u) else None, "suspend_reason": u.suspend_reason if suspended(u) else "",
            "new_account": (utcnow() - aware(u.created_at)).total_seconds() < 86400}


# ================================================================= AUTH
@app.post("/api/auth/register", dependencies=[rate_limit("auth", 10, 900)])
def register(data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(func.lower(User.username) == data.username.lower())):
        raise HTTPException(409, "That username is taken.")
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(409, "An account with that email already exists.")
    u = User(username=data.username, email=data.email, password_hash=hash_pw(data.password),
             display_name=clean(data.display_name, 50) or data.username)
    db.add(u); commit(db)
    set_session(response, u.id)
    return me_out(db, u)


@app.post("/api/auth/login", dependencies=[rate_limit("auth", 10, 900)])
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    key = data.login.strip().lower()
    u = db.scalar(select(User).where(or_(User.email == key, func.lower(User.username) == key)))
    if not u or not check_pw(data.password, u.password_hash):
        raise HTTPException(401, "Wrong username/email or password.")
    set_session(response, u.id)
    return me_out(db, u)


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return me_out(db, user) if user else None


@app.put("/api/me")
def update_me(data: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.display_name = clean(data.display_name, 50) or user.username
    user.bio = clean(data.bio, 300)
    user.avatar_url = clean_url(data.avatar_url)
    user.x_handle = data.x_handle
    user.telegram = data.telegram
    user.website = clean_url(data.website) if data.website else ""
    for k in PRIVACY_KEYS:
        v = getattr(data, k)
        if v is not None: setattr(user, k, v)
    if data.wallet_address != user.wallet_address:
        user.wallet_verified = False  # changing the wallet never carries verification over
    user.wallet_address = data.wallet_address
    commit(db)
    return me_out(db, user)


# ================================================================= UPLOADS
@app.post("/api/upload", dependencies=[rate_limit("upload", 20, 600)])
async def upload(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = await file.read(storage.MAX_BYTES + 1)
    try:
        url = storage.save(db, data, file.content_type, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"url": url, "backend": storage.backend()}


@app.get("/media/{key}")
def media(key: str, db: Session = Depends(get_db)):
    m = db.scalar(select(Media).where(Media.key == key[:80]))
    if not m: raise HTTPException(404, "Not found.")
    return Response(m.data, media_type=m.content_type, headers={"Cache-Control": "public, max-age=31536000, immutable",
                                                                 "X-Content-Type-Options": "nosniff", "Content-Length": str(m.size)})


# ================================================================= USERS / PASSPORT
@app.get("/api/users/{username}")
def get_profile(username: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    u = get_user_by_name(db, username)
    vid = viewer.id if viewer else 0
    followers = db.scalar(select(func.count(Follow.id)).where(Follow.followee_id == u.id)) or 0
    following = db.scalar(select(func.count(Follow.id)).where(Follow.follower_id == u.id)) or 0
    is_following = bool(vid and db.scalar(select(Follow.id).where(Follow.follower_id == vid, Follow.followee_id == u.id)))
    blocked = bool(vid and db.scalar(select(Block.id).where(Block.blocker_id == vid, Block.blocked_id == u.id)))
    viewer_nets = my_network_ids(db, vid)
    # networks: hide private networks unless viewer is a member
    ms = db.execute(select(Membership, Network).join(Network, Network.id == Membership.network_id)
                    .where(Membership.user_id == u.id, Membership.status == "active")).all()
    nets = [{**network_brief(n, member_count(db, n.id)), "role": m.role} for m, n in ms if not n.is_private or n.id in viewer_nets or vid == u.id]
    founded = [x for x in nets if x["role"] == "founder"]
    joined = [x for x in nets if x["role"] != "founder"]
    # network connections of networks they founded (public ones only, or both sides agreed to display)
    fids = [x["id"] for x in founded]
    conns = []
    if fids:
        for c in db.scalars(select(Connection).where(Connection.status == "approved", or_(Connection.requester_id.in_(fids), Connection.target_id.in_(fids)))):
            other = db.get(Network, c.target_id if c.requester_id in fids else c.requester_id)
            public = c.req_display_public and c.tgt_display_public
            if public or other.id in viewer_nets or vid == u.id:
                conns.append(network_brief(other))
    projects = [x for x in nets if x["type"] == "Project" and x["role"] != "founder"]
    rep = user_reputation(db, u.id)
    endorsements = [{"category": e.category, "note": e.note, "from": user_brief(db.get(User, e.from_id)), "created_at": iso(e.created_at)}
                    for e in db.scalars(select(Endorsement).where(Endorsement.to_id == u.id).order_by(desc(Endorsement.created_at)).limit(30))]
    my_end = [e.category for e in db.scalars(select(Endorsement).where(Endorsement.from_id == vid, Endorsement.to_id == u.id))] if vid else []
    contrib = []
    for a, o in db.execute(select(Application, Opportunity).join(Opportunity, Opportunity.id == Application.opportunity_id)
                           .where(Application.applicant_id == u.id, Application.status.in_(["accepted", "completed"])).limit(20)).all():
        contrib.append({"title": o.title, "category": o.category, "status": a.status, "opportunity_id": o.id})
    ind = rep["indicators"]
    ach = award_user_achievements(db, u, rep, len(founded), len(joined), len(conns))
    snapshot_reputation(db, "user", u.id, rep["xp"], rep["level"])
    db.commit()
    # collaboration history: both sides of accepted/completed opportunity work
    collab = []
    for a, o in db.execute(select(Application, Opportunity).join(Opportunity, Opportunity.id == Application.opportunity_id).where(
            Application.status.in_(["accepted", "completed"]), or_(Application.applicant_id == u.id, Opportunity.creator_id == u.id))
            .order_by(desc(Application.id)).limit(20)).all():
        other = db.get(User, a.applicant_id if o.creator_id == u.id else o.creator_id)
        collab.append({"title": o.title, "category": o.category, "status": a.status, "opportunity_id": o.id, "with": user_brief(other)})
    me_view = vid == u.id
    show = {k: (me_view or getattr(u, k)) for k in PRIVACY_KEYS}
    calls = [call_out(c) for c in db.scalars(select(Call).where(Call.user_id == u.id).order_by(desc(Call.created_at)).limit(20))
             if not c.network_id or c.network_id in viewer_nets or not db.get(Network, c.network_id).is_private]
    hidden = [k for k in PRIVACY_KEYS if not getattr(u, k)]
    return {**user_brief(u), "bio": u.bio, "created_at": iso(u.created_at),
            "x_handle": u.x_handle if show["show_socials"] else "", "telegram": u.telegram if show["show_socials"] else "",
            "website": u.website if show["show_socials"] else "",
            "wallet_address": u.wallet_address if show["show_wallet"] else "",
            "verification": verification_status(db, "user", u.id, ind["verified_trading_performance"]),
            "linked_accounts": linked_accounts_out(db, u.id, me_view),
            "followers": followers, "following": following, "is_following": is_following, "blocked": blocked, "is_me": me_view,
            "networks_founded": founded if show["show_networks"] else [], "networks_joined": joined if show["show_networks"] else [],
            "network_connections": conns if show["show_networks"] else [], "projects_supported": projects if show["show_networks"] else [],
            "reputation": rep, "endorsements": endorsements if show["show_endorsements"] else [],
            "endorsement_summary": ind["endorsements"]["detail"] if show["show_endorsements"] else {}, "my_endorsements": my_end,
            "contributions": contrib if show["show_contributions"] else [], "collaborations": collab if show["show_contributions"] else [],
            "achievements": ach if show["show_achievements"] else [], "calls": calls,
            "privacy": {k: getattr(u, k) for k in PRIVACY_KEYS} if me_view else None, "hidden_sections": hidden if not me_view else []}


@app.get("/api/users/{username}/posts")
def user_posts(username: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    u = get_user_by_name(db, username)
    vid = viewer.id if viewer else 0
    f, *_ = visible_filter(db, vid)
    posts = list(db.scalars(select(Post).where(f, Post.author_id == u.id, Post.parent_id.is_(None)).order_by(desc(Post.id)).limit(50)))
    return posts_out(db, posts, vid)


@app.post("/api/users/{username}/follow")
def follow(username: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = get_user_by_name(db, username)
    if u.id == user.id: raise HTTPException(400, "You can't follow yourself.")
    f = db.scalar(select(Follow).where(Follow.follower_id == user.id, Follow.followee_id == u.id))
    if f:
        db.delete(f); commit(db); return {"following": False}
    db.add(Follow(follower_id=user.id, followee_id=u.id))
    notify(db, u.id, user.id, "follow", f"@{user.username} followed you", f"#/u/{user.username}")
    commit(db)
    return {"following": True}


@app.post("/api/users/{username}/block")
def block(username: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = get_user_by_name(db, username)
    if u.id == user.id: raise HTTPException(400, "You can't block yourself.")
    b = db.scalar(select(Block).where(Block.blocker_id == user.id, Block.blocked_id == u.id))
    if b:
        db.delete(b); commit(db); return {"blocked": False}
    db.add(Block(blocker_id=user.id, blocked_id=u.id))
    for f in db.scalars(select(Follow).where(or_(and_(Follow.follower_id == user.id, Follow.followee_id == u.id),
                                                 and_(Follow.follower_id == u.id, Follow.followee_id == user.id)))):
        db.delete(f)
    commit(db)
    return {"blocked": True}


@app.post("/api/users/{username}/endorse", dependencies=[rate_limit("endorse", 10, 3600, new_limit=3)])
def endorse(username: str, data: EndorseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_active(user)
    u = get_user_by_name(db, username)
    if u.id == user.id: raise HTTPException(400, "You can't endorse yourself.")
    if db.scalar(select(Endorsement.id).where(Endorsement.from_id == user.id, Endorsement.to_id == u.id, Endorsement.category == data.category)):
        raise HTTPException(409, f"You already endorsed @{u.username} for {data.category}.")
    # anti-manipulation: must actually have worked together (shared network or a collaboration)
    shared = my_network_ids(db, user.id) & my_network_ids(db, u.id)
    collab = db.scalar(select(Application.id).join(Opportunity, Opportunity.id == Application.opportunity_id).where(
        Application.status.in_(["accepted", "completed"]),
        or_(and_(Application.applicant_id == user.id, Opportunity.creator_id == u.id),
            and_(Application.applicant_id == u.id, Opportunity.creator_id == user.id))))
    if not shared and not collab:
        raise HTTPException(403, "You can only endorse people you share a network with or have collaborated with.")
    today = db.scalar(select(func.count(Endorsement.id)).where(Endorsement.from_id == user.id, Endorsement.created_at >= utcnow() - timedelta(days=1))) or 0
    if today >= 5: raise HTTPException(429, "Daily endorsement limit reached (5 per day) — endorsements should be meaningful.")
    if utcnow() - aware(user.created_at) < timedelta(hours=int(os.getenv("ENDORSE_MIN_ACCOUNT_HOURS", "0"))):
        raise HTTPException(403, "Your account is too new to endorse others.")
    db.add(Endorsement(from_id=user.id, to_id=u.id, category=data.category, note=clean(data.note, 300),
                       basis="collaboration" if collab else "shared network"))
    notify(db, u.id, user.id, "endorsement", f"@{user.username} endorsed you for {data.category}", f"#/passport/{u.username}")
    commit(db)
    return {"ok": True}


# ================================================================= POSTS & FEEDS
@app.get("/api/feed")
def feed(tab: str = "network", before: int | None = None, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    vid = viewer.id if viewer else 0
    f, my_nets, g = visible_filter(db, vid)
    stmt = select(Post).where(f, Post.parent_id.is_(None))
    if tab == "announcements":
        stmt = stmt.where(Post.kind == "announcement")
    if tab == "network" and vid:
        followed = select(Follow.followee_id).where(Follow.follower_id == vid)
        conds = shared_conditions(my_nets, g) + [and_(Post.network_id.is_(None), or_(Post.author_id == vid, Post.author_id.in_(followed)))]
        stmt = stmt.where(or_(*conds))
    elif tab == "following" and vid:
        followed = select(Follow.followee_id).where(Follow.follower_id == vid)
        stmt = stmt.where(or_(Post.author_id.in_(followed), Post.author_id == vid))
    elif tab.startswith("tag:"):
        t = tab[4:][:45]
        stmt = stmt.where(or_(Post.tags.like(f"% {t} %"), Post.tags.like(f"{t} %"), Post.tags.like(f"% {t}"), Post.tags == t))
    if before: stmt = stmt.where(Post.id < before)
    return posts_out(db, list(db.scalars(stmt.order_by(desc(Post.id)).limit(30))), vid)


@app.post("/api/posts", dependencies=[rate_limit("post", 20, 60, new_limit=5), rate_limit("post_day", 300, 86400, new_limit=30)])
def create_post(data: PostIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_active(user)
    body = clean(data.body, 2000)
    img = clean_url(data.image_url)
    if not body and not img: raise HTTPException(400, "Write something or add an image.")
    net = None
    kind = data.kind
    if data.parent_id:
        parent = db.get(Post, data.parent_id)
        if not parent or parent.removed or not can_see_post(db, user.id, parent): raise HTTPException(404, "Post not found.")
        net_id, kind = parent.network_id, "post"
        if net_id and not is_active(membership(db, net_id, user.id)) and db.get(Network, net_id).is_private:
            raise HTTPException(403, "Only members can reply inside this private network.")
    else:
        net_id = data.network_id
    if net_id:
        net = db.get(Network, net_id)
        if not net: raise HTTPException(404, "Network not found.")
        from .trust import active_network_ban
        if active_network_ban(db, net_id, user.id): raise HTTPException(403, "You're banned from this Network.")
        m = membership(db, net_id, user.id)
        if not data.parent_id and not is_active(m): raise HTTPException(403, "Join this network to post in it.")
        if not data.parent_id and m.role == "member" and not net.members_can_post: raise HTTPException(403, "In this Network only the founder and admins can post.")
        if kind in ("announcement", "update") and not can(m, "perm_announce"): raise HTTPException(403, "Only the founder and admins with announcement permission can post announcements/updates.")
        if data.share_with_connections and not can(m, "perm_announce"): raise HTTPException(403, "Only the founder and admins with announcement permission can select posts to share with connected Networks.")
    elif kind != "post":
        raise HTTPException(400, "Announcements must be posted inside a network.")
    p = Post(author_id=user.id, network_id=net_id, parent_id=data.parent_id, kind=kind, body=body, image_url=img,
             share_with_connections=bool(data.share_with_connections and net_id), tags=extract_tags(body))
    db.add(p); db.flush()
    if data.parent_id:
        notify(db, parent.author_id, user.id, "reply", f"@{user.username} replied: {body[:80]}", f"#/post/{parent.id}")
    for name in extract_mentions(body):
        mu = db.scalar(select(User).where(func.lower(User.username) == name))
        if mu and can_see_post(db, mu.id, p):
            notify(db, mu.id, user.id, "mention", f"@{user.username} mentioned you: {body[:80]}", f"#/post/{p.id}")
    if kind == "announcement" and net:
        for uid in db.scalars(select(Membership.user_id).where(Membership.network_id == net.id, Membership.status == "active")):
            notify(db, uid, user.id, "announcement", f"📣 {net.name}: {body[:90]}", f"#/n/{net.slug}")
    commit(db)
    (hub.to_room(net_id, {"type": "new_post", "id": p.id}) if net and net.is_private else hub.to_all({"type": "new_post", "id": p.id}))
    return posts_out(db, [p], user.id)[0]


@app.get("/api/posts/{pid}")
def get_post(pid: int, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    vid = viewer.id if viewer else 0
    p = db.get(Post, pid)
    if not p or not can_see_post(db, vid, p): raise HTTPException(404, "Post not found or not visible to you.")
    f, *_ = visible_filter(db, vid)
    replies = list(db.scalars(select(Post).where(f, Post.parent_id == pid).order_by(Post.id)))
    return {"post": posts_out(db, [p], vid)[0], "replies": posts_out(db, replies, vid)}


@app.post("/api/posts/{pid}/like")
def like(pid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Post, pid)
    if not p or not can_see_post(db, user.id, p): raise HTTPException(404, "Post not found.")
    l = db.scalar(select(Like).where(Like.user_id == user.id, Like.post_id == pid))
    if l:
        db.delete(l)
    else:
        db.add(Like(user_id=user.id, post_id=pid))
        notify(db, p.author_id, user.id, "like", f"@{user.username} endorsed your Network Post", f"#/post/{pid}")
    commit(db)
    return {"liked": not l, "likes": db.scalar(select(func.count(Like.id)).where(Like.post_id == pid))}


@app.post("/api/posts/{pid}/renetwork", dependencies=[rate_limit("post", 20, 60)])
def renetwork(pid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_active(user)
    p = db.get(Post, pid)
    if not p or not can_see_post(db, user.id, p): raise HTTPException(404, "Post not found.")
    if p.renetwork_of: p = db.get(Post, p.renetwork_of)
    if p.network_id and db.get(Network, p.network_id).is_private:
        raise HTTPException(403, "Posts from private networks can't be Re-Networked publicly.")
    ex = db.scalar(select(Post).where(Post.author_id == user.id, Post.renetwork_of == p.id, Post.removed.is_(False)))
    if ex:
        db.delete(ex); commit(db); return {"renetworked": False}
    db.add(Post(author_id=user.id, renetwork_of=p.id, body=""))
    notify(db, p.author_id, user.id, "renetwork", f"@{user.username} Re-Networked your post", f"#/post/{p.id}")
    commit(db)
    return {"renetworked": True}


@app.post("/api/posts/{pid}/report", dependencies=[rate_limit("report", 10, 600)])
def report(pid: int, data: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .trust import file_report
    return file_report(db, user, "post", str(pid), data.reason)


@app.delete("/api/posts/{pid}")
def remove_post(pid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Post, pid)
    if not p or p.removed: raise HTTPException(404, "Post not found.")
    allowed = p.author_id == user.id or (p.network_id and can(membership(db, p.network_id, user.id), "perm_moderate"))
    if not allowed: raise HTTPException(403, "Only the author or this Network's founder/moderating admins can remove this post.")
    p.removed = True
    if p.author_id != user.id:
        notify(db, p.author_id, user.id, "moderation", "A Network admin removed one of your posts.", "")
        audit(db, user.id, p.network_id, "post.remove", f"post:{p.id}", f"author:{p.author_id}", ip_of(request))
    commit(db)
    return {"ok": True}


@app.put("/api/posts/{pid}")
def edit_post(pid: int, data: PostEdit, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Post, pid)
    if not p or p.removed: raise HTTPException(404, "Post not found.")
    if p.author_id != user.id: raise HTTPException(403, "You can only edit your own posts.")
    if p.renetwork_of: raise HTTPException(400, "A Re-Network can't be edited.")
    body = clean(data.body, 2000)
    if not body and not p.image_url: raise HTTPException(400, "A post can't be empty.")
    p.body, p.tags, p.edited_at = body, extract_tags(body), utcnow()
    commit(db)
    return posts_out(db, [p], user.id)[0]


@app.get("/api/trending")
def trending_tags(db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=7)
    counts = {}
    for tags in db.scalars(select(Post.tags).join(Network, Network.id == Post.network_id, isouter=True).where(
            Post.created_at >= since, Post.removed.is_(False), Post.tags != "", or_(Post.network_id.is_(None), Network.is_private.is_(False)))):
        for t in tags.split():
            if t[0] in "#$": counts[t] = counts.get(t, 0) + 1
    return [{"tag": t, "posts": n} for t, n in sorted(counts.items(), key=lambda x: -x[1])[:8]]


# ================================================================= NETWORKS
def network_detail(db, n: Network, vid: int):
    m = membership(db, n.id, vid)
    member = is_active(m)
    my_nets = my_network_ids(db, vid)
    conns = []
    for c in db.scalars(select(Connection).where(or_(Connection.requester_id == n.id, Connection.target_id == n.id))):
        other = db.get(Network, c.target_id if c.requester_id == n.id else c.requester_id)
        public = c.status == "approved" and c.req_display_public and c.tgt_display_public
        if not (member or public):
            continue
        if c.status != "approved" and not is_admin(m):
            continue
        conns.append({"id": c.id, "status": c.status, "network": network_brief(other), "incoming": c.target_id == n.id,
                      "message": c.message if is_admin(m) else "", "created_at": iso(c.created_at),
                      "we_share": {**granted_by(c, n.id), "activity_types": sorted(activity_types_of(c, n.id))} if is_admin(m) else None,
                      "they_share": {**granted_by(c, other.id), "activity_types": sorted(activity_types_of(c, other.id))} if member else None})
    founder = db.get(User, n.founder_id)
    pending = db.scalar(select(func.count(Membership.id)).where(Membership.network_id == n.id, Membership.status == "pending")) if can(m, "perm_members") else 0
    can_view = (not n.is_private) or member
    rep = network_reputation(db, n)
    approved = sum(1 for c in conns if c["status"] == "approved")
    if rep["members"] >= 10: award(db, "network", n.id, "ten_members", "10 Members", "Reached 10 active members")
    if approved: award(db, "network", n.id, "connected", "Connected", "Has an approved connection with another Network")
    if rep["eligible"]: award(db, "network", n.id, "ranked", "Ranked", "Eligible for public rankings (3+ active members)")
    if db.new: commit(db)
    return {**network_brief(n, member_count(db, n.id)), "founder": user_brief(founder), "created_at": iso(n.created_at),
            "my_role": m.role if member else None, "my_status": m.status if m else None, "can_view": can_view,
            "stage": n.stage, "launch_at": iso(n.launch_at), "team_info": n.team_info if can_view else "",
            "roadmap": n.roadmap if can_view else "", "token_address": n.token_address, "project_verified": n.project_verified,
            "connections": conns, "pending_requests": pending, "reputation": rep,
            "members_can_post": n.members_can_post, "accept_connections": n.accept_connections,
            "my_perms": perms_of(m), "verification": verification_status(db, "network", n.id, rep["indicators"]["verified_trading_performance"])}


@app.get("/api/networks")
def list_networks(q: str = "", type: str = "", mine: int = 0, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    vid = viewer.id if viewer else 0
    my = my_network_ids(db, vid)
    stmt = select(Network)
    if mine:
        stmt = stmt.where(Network.id.in_(my))
    if q:
        like_ = f"%{q.strip()[:40].lower()}%"
        stmt = stmt.where(or_(func.lower(Network.name).like(like_), func.lower(Network.description).like(like_), Network.slug.like(like_)))
    if type in NETWORK_TYPES: stmt = stmt.where(Network.type == type)
    out = []
    for n in db.scalars(stmt.order_by(Network.id).limit(100)):
        d = network_brief(n, member_count(db, n.id))
        if n.is_private and n.id not in my:
            d["description"] = d["description"][:140]
        m = membership(db, n.id, vid)
        d["my_status"] = m.status if m else None
        d["my_role"] = m.role if is_active(m) else None
        out.append(d)
    out.sort(key=lambda x: -x["members"])
    return out


@app.post("/api/networks", dependencies=[rate_limit("create_net", 5, 3600)])
def create_network(data: NetworkIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    slug = re.sub(r"[^a-z0-9]+", "-", (data.slug or data.name).lower()).strip("-")[:40]
    if len(slug) < 3: raise HTTPException(400, "Slug must be at least 3 letters/numbers.")
    if slug in ("new", "create", "api", "admin"): raise HTTPException(400, "That URL is reserved.")
    if db.scalar(select(Network.id).where(Network.slug == slug)): raise HTTPException(409, f"The URL /{slug} is already taken — pick another.")
    n = Network(slug=slug, name=clean(data.name, 60), type=data.type, description=clean(data.description, 1000), is_private=data.is_private,
                avatar_url=clean_url(data.avatar_url), cover_url=clean_url(data.cover_url), founder_id=user.id)
    db.add(n); db.flush()
    db.add(Membership(network_id=n.id, user_id=user.id, role="founder", status="active", joined_at=utcnow()))
    commit(db)
    return network_detail(db, n, user.id)


@app.get("/api/networks/{slug}")
def get_net(slug: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return network_detail(db, get_network(db, slug), viewer.id if viewer else 0)


@app.put("/api/networks/{slug}")
def update_net(slug: str, data: NetworkUpdate, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if not can(membership(db, n.id, user.id), "perm_settings"): raise HTTPException(403, "Only the founder and admins with settings permission can edit this Network.")
    audit(db, user.id, n.id, "network.update", n.slug, ",".join(sorted(data.model_dump(exclude_unset=True))), ip_of(request))
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is None: continue
        if k in ("avatar_url", "cover_url"): v = clean_url(v)
        elif k == "launch_at": v = aware(v)
        elif isinstance(v, str): v = clean(v, 3000)
        if k == "stage" and v != n.stage and v in ("Launch", "Growth"):
            record_activity(db, n.id, "launches", f"{n.name} moved to stage: {v}", f"#/n/{n.slug}/launch")
        if k == "launch_at" and v and (not n.launch_at or aware(n.launch_at) != v):
            record_activity(db, n.id, "launches", f"{n.name} set a launch date: {v:%Y-%m-%d %H:%M} UTC", f"#/n/{n.slug}/launch")
        setattr(n, k, v)
    commit(db)
    return network_detail(db, n, user.id)


@app.post("/api/networks/{slug}/join", dependencies=[rate_limit("join", 30, 600)])
def join(slug: str, invite: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    m = membership(db, n.id, user.id)
    if is_active(m): raise HTTPException(400, "You're already a member.")
    from .trust import active_network_ban
    from .models import NetworkBan
    ban = active_network_ban(db, n.id, user.id)
    if ban: raise HTTPException(403, "You're banned from this Network" + (f" until {iso(ban.until)}" if ban.until else "") + ". You can appeal from the Network page.")
    if m and m.status == "removed" and db.scalar(select(NetworkBan.id).where(NetworkBan.network_id == n.id, NetworkBan.user_id == user.id)):
        m.status = "left"  # a ban that expired or was lifted: they may rejoin normally
    inv = valid_invite(db, invite, n.id, user.id) if invite else None
    if m and m.status == "pending" and not inv: raise HTTPException(400, "Your request is already pending.")
    if m and m.status == "removed" and not inv: raise HTTPException(403, "You were removed from this Network.")
    status = "active" if (inv or not n.is_private) else "pending"
    if inv: inv.uses += 1
    if m:
        m.status, m.role, m.requested_at, m.joined_at, m.left_at = status, "member", utcnow(), (utcnow() if status == "active" else None), None
    else:
        db.add(Membership(network_id=n.id, user_id=user.id, status=status, joined_at=utcnow() if status == "active" else None))
    if status == "active": record_activity(db, n.id, "new_members", f"@{user.username} joined {n.name}", f"#/u/{user.username}")
    for uid in db.scalars(select(Membership.user_id).where(Membership.network_id == n.id, Membership.status == "active", Membership.role.in_(["founder", "admin"]))):
        notify(db, uid, user.id, "join_request" if status == "pending" else "join",
               f"@{user.username} {'requested to join' if status == 'pending' else 'joined'} {n.name}", f"#/n/{n.slug}/members")
    commit(db)
    return {"status": status}


@app.post("/api/networks/{slug}/leave")
def leave(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    m = membership(db, n.id, user.id)
    if not m or m.status not in ("active", "pending"): raise HTTPException(400, "You're not a member.")
    if m.role == "founder": raise HTTPException(400, "Founders can't leave their own network.")
    m.status, m.left_at, m.role = ("left" if m.status == "active" else "rejected"), utcnow(), "member"
    commit(db)
    return {"ok": True}


@app.get("/api/networks/{slug}/members")
def members(slug: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    vid = viewer.id if viewer else 0
    m = membership(db, n.id, vid)
    if n.is_private and not is_active(m): raise HTTPException(403, "Member list is private.")
    statuses = ["active", "pending"] if can(m, "perm_members") else ["active"]
    rows = db.execute(select(Membership, User).join(User, User.id == Membership.user_id)
                      .where(Membership.network_id == n.id, Membership.status.in_(statuses)).order_by(Membership.id)).all()
    order = {"founder": 0, "admin": 1, "member": 2}
    out = [{**user_brief(u), "role": mm.role, "status": mm.status, "joined_at": iso(mm.joined_at),
            "perms": perms_of(mm) if mm.role == "admin" and is_admin(m) else None} for mm, u in rows]
    return sorted(out, key=lambda x: (x["status"] != "pending", order[x["role"]]))


@app.post("/api/networks/{slug}/members/{uid}")
def member_action(slug: str, uid: int, data: MemberAction, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    me_m = membership(db, n.id, user.id)
    if not can(me_m, "perm_members"): raise HTTPException(403, "Only the founder and admins with member-management permission can manage members.")
    t = membership(db, n.id, uid)
    if not t: raise HTTPException(404, "Member not found.")
    if t.role == "founder": raise HTTPException(403, "The founder can't be changed.")
    a = data.action
    if a in ("approve", "reject"):
        if t.status != "pending": raise HTTPException(400, "No pending request.")
        t.status = "active" if a == "approve" else "rejected"
        if a == "approve":
            t.joined_at = utcnow()
            nu = db.get(User, uid)
            record_activity(db, n.id, "new_members", f"@{nu.username} joined {n.name}", f"#/u/{nu.username}")
        notify(db, uid, user.id, "join_decision", f"Your request to join {n.name} was {'approved ✅' if a == 'approve' else 'declined'}", f"#/n/{n.slug}")
    elif a in ("make_admin", "make_member"):
        if me_m.role != "founder": raise HTTPException(403, "Only the founder can change roles.")
        if t.status != "active": raise HTTPException(400, "Not an active member.")
        t.role = "admin" if a == "make_admin" else "member"
        notify(db, uid, user.id, "role", f"You are now {'a Network Admin' if t.role == 'admin' else 'a member'} of {n.name}", f"#/n/{n.slug}")
    elif a == "remove":
        if t.role == "admin" and me_m.role != "founder": raise HTTPException(403, "Only the founder can remove admins.")
        t.status, t.role, t.left_at = "removed", "member", utcnow()
    audit(db, user.id, n.id, f"member.{a}", f"user:{uid}", "", ip_of(request))
    commit(db)
    return {"ok": True}


@app.put("/api/networks/{slug}/members/{uid}/perms")
def set_admin_perms(slug: str, uid: int, data: AdminPerms, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if (membership(db, n.id, user.id) or Membership()).role != "founder" or not is_active(membership(db, n.id, user.id)):
        raise HTTPException(403, "Only the Network Founder can configure admin permissions.")
    t = membership(db, n.id, uid)
    if not t or t.role != "admin" or t.status != "active": raise HTTPException(400, "That user is not an admin of this Network.")
    for k, v in data.model_dump().items(): setattr(t, k, v)
    audit(db, user.id, n.id, "admin.perms", f"user:{uid}", ",".join(k for k, v in data.model_dump().items() if v), ip_of(request))
    commit(db)
    return {"ok": True, "perms": perms_of(t)}


@app.get("/api/networks/{slug}/feed")
def network_feed(slug: str, kind: str = "", viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    vid = viewer.id if viewer else 0
    m = membership(db, n.id, vid)
    if n.is_private and not is_active(m): raise HTTPException(403, "This network is private. Request to join to see its posts.")
    f, my_nets, g = visible_filter(db, vid)
    stmt = select(Post).where(f, Post.network_id == n.id, Post.parent_id.is_(None))
    if kind in ("announcement", "update", "post"): stmt = stmt.where(Post.kind == kind)
    if kind == "connected":  # activity shared TO this network by its connected networks (members only)
        if not is_active(m): raise HTTPException(403, "Members only.")
        conds = shared_conditions(set(), connection_grants(db, {n.id}))
        if not conds: return []
        stmt = select(Post).where(f, Post.parent_id.is_(None), or_(*conds))
    return posts_out(db, list(db.scalars(stmt.order_by(desc(Post.id)).limit(50))), vid)


@app.get("/api/networks/{slug}/chat")
def chat_history(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if not is_active(membership(db, n.id, user.id)): raise HTTPException(403, "Members only.")
    rows = db.execute(select(ChatMessage, User).join(User, User.id == ChatMessage.user_id).where(ChatMessage.network_id == n.id)
                      .order_by(desc(ChatMessage.id)).limit(60)).all()
    return [{"id": c.id, "body": c.body, "created_at": iso(c.created_at), "user": user_brief(u)} for c, u in reversed(rows)]


@app.post("/api/networks/{slug}/chat", dependencies=[rate_limit("chat", 30, 60, new_limit=10)])
def chat_send(slug: str, data: MessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_active(user)
    n = get_network(db, slug)
    if not is_active(membership(db, n.id, user.id)): raise HTTPException(403, "Members only.")
    body = clean(data.body, 1000)
    if not body: raise HTTPException(400, "Message is empty.")
    c = ChatMessage(network_id=n.id, user_id=user.id, body=body)
    db.add(c); commit(db)
    out = {"id": c.id, "body": c.body, "created_at": iso(c.created_at), "user": user_brief(user)}
    hub.to_room(n.id, {"type": "chat", "network_id": n.id, "message": out})
    return out


# ================================================================= CONNECTIONS
@app.post("/api/networks/{slug}/connections", dependencies=[rate_limit("connect", 10, 3600, new_limit=2)])
def request_connection(slug: str, data: ConnectionIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if not can(membership(db, n.id, user.id), "perm_connections"): raise HTTPException(403, "Only the founder and admins with connection permission can request connections.")
    t = get_network(db, data.target_slug.strip().lower())
    if t.id == n.id: raise HTTPException(400, "A Network can't connect to itself.")
    if not t.accept_connections: raise HTTPException(403, f"{t.name} isn't accepting connection requests right now.")
    ex = db.scalar(select(Connection).where(or_(and_(Connection.requester_id == n.id, Connection.target_id == t.id),
                                                and_(Connection.requester_id == t.id, Connection.target_id == n.id))))
    if ex and ex.status in ("pending", "approved"): raise HTTPException(409, f"A connection with {t.name} is already {ex.status}.")
    if ex: db.delete(ex); db.flush()
    p = data.permissions
    c = Connection(requester_id=n.id, target_id=t.id, requested_by=user.id, message=clean(data.message, 500),
                   **perm_cols("req_", p))
    db.add(c)
    audit(db, user.id, n.id, "connection.request", t.slug, "", ip_of(request))
    for mm in db.scalars(select(Membership).where(Membership.network_id == t.id, Membership.status == "active", Membership.role.in_(["founder", "admin"]))):
        if can(mm, "perm_connections"): notify(db, mm.user_id, user.id, "connection_request", f"{n.name} wants to connect with {t.name}", f"#/n/{t.slug}/connections")
    commit(db)
    return {"id": c.id, "status": c.status}


def perm_cols(prefix, p) -> dict:
    d = p.model_dump()
    types = [t for t in d.pop("activity_types", []) if t in ACTIVITY_TYPES]
    out = {prefix + k: v for k, v in d.items()}
    out[prefix + "activity_types"] = ",".join(dict.fromkeys(types))
    return out


def conn_side_admin(db, c: Connection, uid):
    for nid in (c.requester_id, c.target_id):
        if can(membership(db, nid, uid), "perm_connections"):
            return nid
    return None


@app.post("/api/connections/{cid}/decide")
def decide_connection(cid: int, data: ConnectionDecision, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Connection, cid)
    if not c: raise HTTPException(404, "Connection not found.")
    if not can(membership(db, c.target_id, user.id), "perm_connections"): raise HTTPException(403, "Only the receiving Network's founder or authorized admins can decide.")
    if c.status != "pending": raise HTTPException(400, "This request was already decided.")
    c.status = "approved" if data.action == "approve" else "rejected"
    c.decided_at = utcnow()
    if c.status == "approved":
        p = data.permissions
        for k, v in perm_cols("tgt_", data.permissions).items(): setattr(c, k, v)
    audit(db, user.id, c.target_id, f"connection.{c.status}", f"connection:{c.id}", "", ip_of(request))
    rn, tn = db.get(Network, c.requester_id), db.get(Network, c.target_id)
    for uid in db.scalars(select(Membership.user_id).where(Membership.network_id == rn.id, Membership.status == "active", Membership.role.in_(["founder", "admin"]))):
        notify(db, uid, user.id, "connection_approved" if c.status == "approved" else "connection_decision", f"{tn.name} {c.status} your connection request", f"#/n/{rn.slug}/connections")
    commit(db)
    return {"status": c.status}


@app.put("/api/connections/{cid}/permissions")
def update_perms(cid: int, data: Perms, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Connection, cid)
    if not c: raise HTTPException(404, "Connection not found.")
    side = conn_side_admin(db, c, user.id)
    if not side: raise HTTPException(403, "Only founders/admins of a connected network can change what it shares.")
    pre = "req_" if side == c.requester_id else "tgt_"
    for k, v in perm_cols(pre, data).items():
        setattr(c, k, v)
    audit(db, user.id, side, "connection.permissions", f"connection:{c.id}", ",".join(k for k, v in data.model_dump().items() if v), ip_of(request))
    commit(db)
    return {"ok": True, "we_share": {**granted_by(c, side), "activity_types": sorted(activity_types_of(c, side))}}


@app.delete("/api/connections/{cid}")
def remove_connection(cid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Connection, cid)
    if not c: raise HTTPException(404, "Connection not found.")
    side = conn_side_admin(db, c, user.id)
    if not side: raise HTTPException(403, "Not allowed.")
    audit(db, user.id, side, "connection.remove", f"connection:{c.id}", f"{c.requester_id}<->{c.target_id}", ip_of(request))
    db.delete(c); commit(db)
    return {"ok": True}


# ================================================================= OPPORTUNITIES
def opp_visible(db, o: Opportunity, vid, my_nets=None, g=None):
    """Public-network and personal opportunities are public. Private-network opportunities: members, or connected
    networks that were explicitly granted 'partnership opportunities' sharing."""
    if not o.network_id: return True
    n = db.get(Network, o.network_id)
    if not n.is_private: return True
    my_nets = my_network_ids(db, vid) if my_nets is None else my_nets
    if o.network_id in my_nets: return True
    if g is None: g = connection_grants(db, my_nets)
    return o.network_id in g["share_opportunities"]


def opp_out(db, o: Opportunity, vid):
    apps = db.scalar(select(func.count(Application.id)).where(Application.opportunity_id == o.id)) or 0
    mine = db.scalar(select(Application).where(Application.opportunity_id == o.id, Application.applicant_id == vid)) if vid else None
    n = db.get(Network, o.network_id) if o.network_id else None
    manage = o.creator_id == vid or bool(n and can(membership(db, n.id, vid), "perm_opportunities"))
    expired = bool(o.deadline and aware(o.deadline) < utcnow())
    return {"id": o.id, "category": o.category, "title": o.title, "description": o.description, "requirements": o.requirements,
            "compensation": o.compensation, "negotiable": o.negotiable, "deadline": iso(o.deadline), "expired": expired,
            "status": o.status, "created_at": iso(o.created_at), "is_demo": o.is_demo, "creator": user_brief(db.get(User, o.creator_id)),
            "network": network_brief(n) if n else None, "applicants": apps, "is_mine": o.creator_id == vid, "can_manage": manage,
            "my_application": {"kind": mine.kind, "status": mine.status} if mine else None}


@app.get("/api/opportunities")
def list_opps(category: str = "", q: str = "", status: str = "open", network: str = "", mine: int = 0, relevant: int = 0,
              offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=50),
              viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    vid = viewer.id if viewer else 0
    stmt = select(Opportunity)
    if status in ("open", "closed", "filled"): stmt = stmt.where(Opportunity.status == status)
    if category in OPP_CATS: stmt = stmt.where(Opportunity.category == category)
    if network:
        nn = db.scalar(select(Network).where(Network.slug == network[:40]))
        stmt = stmt.where(Opportunity.network_id == (nn.id if nn else -1))
    if mine and vid: stmt = stmt.where(Opportunity.creator_id == vid)
    if q:
        lk = f"%{q.strip()[:50].lower()}%"
        stmt = stmt.where(or_(func.lower(Opportunity.title).like(lk), func.lower(Opportunity.description).like(lk), func.lower(Opportunity.requirements).like(lk)))
    my = my_network_ids(db, vid)
    g = connection_grants(db, my)
    if relevant and vid:  # from my networks, networks sharing opportunities with me, or creators I follow
        followed = select(Follow.followee_id).where(Follow.follower_id == vid)
        stmt = stmt.where(or_(Opportunity.network_id.in_(my | g["share_opportunities"]), Opportunity.creator_id.in_(followed)))
    rows = [o for o in db.scalars(stmt.order_by(desc(Opportunity.id)).offset(offset).limit(limit * 2)) if opp_visible(db, o, vid, my, g)]
    return [opp_out(db, o, vid) for o in rows[:limit]]


@app.post("/api/opportunities", dependencies=[rate_limit("opp", 10, 3600)])
def create_opp(data: OpportunityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.network_id and not can(membership(db, data.network_id, user.id), "perm_opportunities"):
        raise HTTPException(403, "Only the founder and admins with opportunity permission can publish on behalf of a Network.")
    if data.deadline and aware(data.deadline) < utcnow(): raise HTTPException(400, "The deadline must be in the future.")
    if not data.compensation.strip() and not data.negotiable: raise HTTPException(400, "Enter compensation or mark it negotiable.")
    o = Opportunity(creator_id=user.id, network_id=data.network_id, category=data.category, title=clean(data.title, 120),
                    description=clean(data.description, 3000), requirements=clean(data.requirements, 2000),
                    compensation=clean(data.compensation, 120), negotiable=data.negotiable, deadline=aware(data.deadline))
    db.add(o); commit(db)
    return opp_out(db, o, user.id)


ROLE_HINTS = {"Trader": ["Trading", "Alpha Communities", "Trading"], "Founder": ["Project", "Partnership", "Investment"], "KOL": ["KOL", "Marketing", "Promotion"],
              "Developer": ["Project", "Development"], "Marketer": ["Marketing", "Promotion"], "Researcher": ["Alpha Communities", "Research"],
              "Community builder": ["Personal", "Community"], "Investor": ["Project", "Investment"]}


def interest_terms(u: User):
    terms = [x for x in (u.interests or "").split(",") if x] + ROLE_HINTS.get(u.role or "", [])
    return [t.lower() for t in terms]


@app.put("/api/me/onboarding")
def onboarding(data: OnboardingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    allowed = set(NETWORK_TYPES) | set(OPP_CATS)
    if data.role and data.role not in USER_ROLES: raise HTTPException(400, "Unknown role.")
    user.role = data.role
    user.interests = ",".join([i for i in dict.fromkeys(data.interests) if i in allowed])
    commit(db)
    return me_out(db, user)


def suggested_opps(db, user: User, limit=5):
    terms = interest_terms(user)
    my = my_network_ids(db, user.id); g = connection_grants(db, my)
    applied = select(Application.opportunity_id).where(Application.applicant_id == user.id)
    out = []
    for o in db.scalars(select(Opportunity).where(Opportunity.status == "open", Opportunity.creator_id != user.id, Opportunity.id.not_in(applied))
                        .order_by(desc(Opportunity.id)).limit(200)):
        if o.deadline and aware(o.deadline) < utcnow(): continue
        if not opp_visible(db, o, user.id, my, g): continue
        hay = f"{o.category} {o.title} {o.description}".lower()
        score = sum(2 if t == o.category.lower() else 1 for t in terms if t in hay) + (3 if o.network_id in my else 0)
        if score > 0: out.append((score, o))
    out.sort(key=lambda x: (-x[0], -x[1].id))
    return [{**opp_out(db, o, user.id), "match": sc} for sc, o in out[:limit]]


@app.get("/api/opportunities/suggested")
def opps_suggested(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return suggested_opps(db, user)


@app.get("/api/suggestions")
def suggestions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    terms = interest_terms(user)
    my = my_network_ids(db, user.id)
    nets = []
    for n in db.scalars(select(Network).where(Network.is_private.is_(False)).limit(300)):
        if n.id in my: continue
        hay = f"{n.type} {n.name} {n.description}".lower()
        sc = sum(2 if t == n.type.lower() else 1 for t in terms if t in hay)
        if sc or not terms: nets.append((sc, member_count(db, n.id), n))
    nets.sort(key=lambda x: (-x[0], -x[1]))
    return {"networks": [network_brief(n, m) for _, m, n in nets[:6]], "opportunities": suggested_opps(db, user, 6)}


@app.get("/api/opportunities/{oid}")
def get_opp(oid: int, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    vid = viewer.id if viewer else 0
    o = db.get(Opportunity, oid)
    if not o or not opp_visible(db, o, vid): raise HTTPException(404, "Opportunity not found.")
    d = opp_out(db, o, vid)
    if d["can_manage"]:
        d["applications"] = [{"id": a.id, "kind": a.kind, "message": a.message, "status": a.status, "created_at": iso(a.created_at),
                              "applicant": user_brief(db.get(User, a.applicant_id))}
                             for a in db.scalars(select(Application).where(Application.opportunity_id == oid).order_by(Application.id))]
    return d


@app.post("/api/opportunities/{oid}/apply", dependencies=[rate_limit("apply", 20, 3600)])
def apply(oid: int, data: ApplyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = db.get(Opportunity, oid)
    if not o or not opp_visible(db, o, user.id): raise HTTPException(404, "Opportunity not found.")
    if o.status != "open": raise HTTPException(400, "This opportunity is no longer open.")
    if o.deadline and aware(o.deadline) < utcnow(): raise HTTPException(400, "The application deadline has passed.")
    if o.creator_id == user.id: raise HTTPException(400, "You can't apply to your own opportunity.")
    if data.kind == "application" and len(data.message.strip()) < 20: raise HTTPException(400, "Applications need a message of at least 20 characters.")
    ex = db.scalar(select(Application).where(Application.opportunity_id == oid, Application.applicant_id == user.id))
    if ex:
        if ex.kind == "interest" and data.kind == "application":
            ex.kind, ex.message = "application", clean(data.message, 2000)
        else:
            raise HTTPException(409, "You've already responded to this opportunity.")
    else:
        db.add(Application(opportunity_id=oid, applicant_id=user.id, kind=data.kind, message=clean(data.message, 2000)))
    label = "applied to" if data.kind == "application" else "is interested in"
    notify(db, o.creator_id, user.id, "opportunity_application", f"@{user.username} {label} “{o.title}”", f"#/opportunities/{o.id}")
    commit(db)
    return {"ok": True}


@app.post("/api/applications/{aid}")
def decide_application(aid: int, data: AppDecision, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Application, aid)
    if not a: raise HTTPException(404, "Application not found.")
    o = db.get(Opportunity, a.opportunity_id)
    if not opp_out(db, o, user.id)["can_manage"]: raise HTTPException(403, "Only the opportunity creator or authorized Network admins can do that.")
    if data.status == "completed" and a.status != "accepted": raise HTTPException(400, "Only accepted collaborations can be marked completed.")
    if data.status in ("accepted", "rejected") and a.status != "pending": raise HTTPException(400, "Already decided.")
    a.status = data.status
    if data.status == "accepted":
        conv = conversation_for(db, user.id, a.applicant_id); conv.last_at = utcnow()
        db.add(Message(conversation_id=conv.id, sender_id=user.id, recipient_id=a.applicant_id, body=f"Hi! I accepted your response to “{o.title}”. Let's talk details here."))
    notify(db, a.applicant_id, user.id, "opportunity_decision", f"Your response to “{o.title}” was {data.status}", f"#/opportunities/{o.id}")
    commit(db)
    return {"ok": True}


@app.post("/api/opportunities/{oid}/status")
def opp_status(oid: int, data: OppStatus, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = db.get(Opportunity, oid)
    if not o or not opp_out(db, o, user.id)["can_manage"]: raise HTTPException(403, "Only the creator or authorized Network admins can change its status.")
    was = o.status
    o.status = data.status
    if o.network_id and o.status == "filled" and was != "filled":
        record_activity(db, o.network_id, "opportunities_filled", f"Opportunity filled: {o.title}", f"#/opp/{o.id}")
    commit(db)
    return {"ok": True, "status": o.status}


# ================================================================= MESSAGES (DMs)
@app.get("/api/messages")
def conversations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for c in db.scalars(select(Conversation).where(or_(Conversation.user_a_id == user.id, Conversation.user_b_id == user.id))
                        .order_by(desc(Conversation.last_at)).limit(100)):
        other = c.user_b_id if c.user_a_id == user.id else c.user_a_id
        last = db.scalar(select(Message).where(Message.conversation_id == c.id).order_by(desc(Message.id)).limit(1))
        unread = db.scalar(select(func.count(Message.id)).where(Message.conversation_id == c.id, Message.recipient_id == user.id, Message.read.is_(False))) or 0
        out.append({"id": c.id, "user": user_brief(db.get(User, other)), "last": last.body[:80] if last else "", "at": iso(c.last_at), "unread": unread})
    return out


@app.get("/api/messages/{username}")
def thread(username: str, before: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = get_user_by_name(db, username)
    c = conversation_for(db, user.id, o.id, create=False)
    if not c: return {"user": user_brief(o), "messages": [], "has_more": False}
    stmt = select(Message).where(Message.conversation_id == c.id)
    if before: stmt = stmt.where(Message.id < before)
    msgs = list(reversed(list(db.scalars(stmt.order_by(desc(Message.id)).limit(51)))))
    more = len(msgs) > 50
    msgs = msgs[-50:]
    for m in db.scalars(select(Message).where(Message.conversation_id == c.id, Message.recipient_id == user.id, Message.read.is_(False))):
        m.read = True
    commit(db)
    return {"user": user_brief(o), "has_more": more,
            "messages": [{"id": m.id, "mine": m.sender_id == user.id, "body": m.body, "created_at": iso(m.created_at)} for m in msgs]}


@app.post("/api/messages/{username}", dependencies=[rate_limit("dm", 30, 60, new_limit=10), rate_limit("dm_day", 500, 86400, new_limit=40)])
def send_dm(username: str, data: MessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_active(user)
    o = get_user_by_name(db, username)
    if o.id == user.id: raise HTTPException(400, "You can't message yourself.")
    if db.scalar(select(Block.id).where(or_(and_(Block.blocker_id == o.id, Block.blocked_id == user.id), and_(Block.blocker_id == user.id, Block.blocked_id == o.id)))):
        raise HTTPException(403, "You can't message this user.")
    # anti-spam: first contact requires a shared network, a follow-back, or an opportunity relationship
    prior = db.scalar(select(Message.id).where(Message.sender_id == o.id, Message.recipient_id == user.id))
    shared = my_network_ids(db, user.id) & my_network_ids(db, o.id)
    follows_me = db.scalar(select(Follow.id).where(Follow.follower_id == o.id, Follow.followee_id == user.id))
    opp = db.scalar(select(Application.id).join(Opportunity, Opportunity.id == Application.opportunity_id).where(
        or_(and_(Application.applicant_id == user.id, Opportunity.creator_id == o.id), and_(Application.applicant_id == o.id, Opportunity.creator_id == user.id))))
    if not (prior or shared or follows_me or opp):
        raise HTTPException(403, "To prevent spam, you can message people who share a network with you, follow you, or are linked by an opportunity.")
    body = clean(data.body, 2000)
    if not body: raise HTTPException(400, "Message is empty.")
    conv = conversation_for(db, user.id, o.id); conv.last_at = utcnow()
    m = Message(conversation_id=conv.id, sender_id=user.id, recipient_id=o.id, body=body)
    db.add(m)
    notify(db, o.id, user.id, "message", f"New message from @{user.username}", f"#/messages/{user.username}", push=False)
    commit(db)
    out = {"id": m.id, "body": m.body, "created_at": iso(m.created_at)}
    hub.to_user(o.id, {"type": "dm", "from": user.username, "message": {**out, "mine": False}})
    return {**out, "mine": True}


# ================================================================= NOTIFICATIONS
@app.get("/api/notifications")
def notifications(before: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if before: stmt = stmt.where(Notification.id < before)
    ns = list(db.scalars(stmt.order_by(desc(Notification.id)).limit(40)))
    return [{"id": n.id, "type": n.type, "text": n.text, "link": n.link, "read": n.read, "created_at": iso(n.created_at)} for n in ns]


@app.post("/api/notifications/{nid}/read")
def mark_one_read(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id: raise HTTPException(404, "Notification not found.")
    n.read = True; commit(db)
    return {"ok": True}


@app.post("/api/notifications/read")
def mark_read(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))):
        n.read = True
    commit(db)
    return {"ok": True}


# ================================================================= CALLS (independently tracked)
@app.post("/api/calls", dependencies=[rate_limit("call", 10, 3600)])
def create_call(data: CallIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_active(user)
    if data.network_id and not is_active(membership(db, data.network_id, user.id)): raise HTTPException(403, "Join the network to post calls in it.")
    try:
        t = dex.fetch_token(data.token_address)
    except Exception:
        raise HTTPException(502, "Couldn't reach DexScreener right now — try again in a minute.")
    if not t or not t["price"]: raise HTTPException(400, "DexScreener has no Solana trading pair for that address.")
    notes = clean(data.notes, 500)
    body = f"📈 Call: ${t['symbol']} at ${t['price']:.10g} (MC ${t['mcap']:,.0f})" + (f"\n{notes}" if notes else "")
    p = Post(author_id=user.id, network_id=data.network_id, body=body, tags=extract_tags(f"${t['symbol']} {data.token_address}"))
    db.add(p); db.flush()
    c = Call(user_id=user.id, network_id=data.network_id, post_id=p.id, token_address=data.token_address, symbol=t["symbol"][:30],
             name=t["name"][:80], notes=notes, entry_price=t["price"], entry_mcap=t["mcap"], entry_liquidity=t["liquidity"],
             current_price=t["price"], current_mcap=t["mcap"], current_liquidity=t["liquidity"], peak_price=t["price"])
    db.add(c)
    for uid in db.scalars(select(Follow.follower_id).where(Follow.followee_id == user.id)):
        if not data.network_id or is_active(membership(db, data.network_id, uid)) or not db.get(Network, data.network_id).is_private:
            notify(db, uid, user.id, "call", f"🚨 @{user.username} called ${t['symbol']}", f"#/post/{p.id}")
    commit(db)
    hub.to_all({"type": "new_post", "id": p.id})
    return call_out(c)


@app.get("/api/calls")
def list_calls(viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    vid = viewer.id if viewer else 0
    my = my_network_ids(db, vid)
    out = []
    for c, u in db.execute(select(Call, User).join(User, User.id == Call.user_id).order_by(desc(Call.id)).limit(100)).all():
        if c.network_id and c.network_id not in my and db.get(Network, c.network_id).is_private: continue
        out.append({**call_out(c), "user": user_brief(u)})
    return out


@app.post("/api/calls/refresh")
def refresh_calls(user: User = Depends(current_user)):
    return {"checked": dex.track_once()}


@app.get("/api/tokens/trending")
def tokens_trending():
    try:
        return dex.trending(6)
    except Exception:
        return []


# ================================================================= RANKINGS / DASHBOARD / SEARCH
RANKINGS_TTL = lambda: int(os.getenv("RANKINGS_TTL", "300"))


@app.get("/api/rankings")
def rankings(type: str = "", refresh: bool = False, db: Session = Depends(get_db)):
    """Served from a stored snapshot refreshed every RANKINGS_TTL seconds (default 5 min), so ranking cost doesn't grow with traffic."""
    import json
    key = type if type in NETWORK_TYPES else ""
    snap = db.scalar(select(RankingSnapshot).where(RankingSnapshot.key == key).order_by(desc(RankingSnapshot.id)).limit(1))
    if snap and not refresh and (utcnow() - aware(snap.computed_at)).total_seconds() < RANKINGS_TTL():
        out = json.loads(snap.data)
    else:
        out = compute_rankings(key, db)
        db.query(RankingSnapshot).filter(RankingSnapshot.key == key).delete()
        snap = RankingSnapshot(key=key, data=json.dumps(out), computed_at=utcnow())
        db.add(snap); commit(db)
    return {**out, "computed_at": iso(snap.computed_at), "ttl_seconds": RANKINGS_TTL()}


def compute_rankings(type: str, db: Session):
    """Eight ranking categories, all computed from stored records. Nothing can be bought."""
    rows = []
    for n in db.scalars(select(Network).where(Network.is_private.is_(False)).limit(500)):
        if type in NETWORK_TYPES and n.type != type: continue
        r = network_reputation(db, n)
        month = utcnow() - timedelta(days=30)
        posts30 = db.scalar(select(func.count(Post.id)).where(Post.network_id == n.id, Post.removed.is_(False), Post.created_at >= month)) or 0
        chats30 = db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.network_id == n.id, ChatMessage.created_at >= month)) or 0
        rows.append({**network_brief(n, r["members"]), **{k: r[k] for k in ("score", "score_parts", "indicators", "eligible")},
                     "growth": r["indicators"]["organic_growth"]["value"], "activity": posts30 + chats30})
    def ranked(items, key, eligible=lambda r: r["eligible"]):
        el = sorted([r for r in items if eligible(r)], key=key, reverse=True)
        return [{**r, "rank": i} for i, r in enumerate(el, 1)][:25]
    users = []
    for u in db.scalars(select(User).limit(500)):
        rep = user_reputation(db, u.id)
        ind = rep["indicators"]
        es = ind["endorsements"]["detail"]
        users.append({**user_brief(u), "_id": u.id, "xp": rep["xp"], "level": rep["level"], "trading": ind["verified_trading_performance"],
                      "endorsements": ind["endorsements"]["value"], "reliability": ind["reliability"]["value"],
                      "collaborations": ind["collaboration_history"]["value"], "contributions": ind["community_contributions"]["value"],
                      "research": es.get("Research", 0) + es.get("Trading research", 0)})
    xp_of = {u["_id"]: u["xp"] for u in users}
    for u in users:
        # weight = 0.5 + 0.5 * min(1, endorser XP / 1000): endorsements from people with earned reputation count more
        ws = [0.5 + 0.5 * min(1.0, xp_of.get(fid, 0) / 1000) for fid in db.scalars(select(Endorsement.from_id).where(Endorsement.to_id == u["_id"]))]
        u["endorsements_weighted"] = round(sum(ws), 2)
    for u in users: u.pop("_id")
    def uranked(key):
        el = sorted([u for u in users if key(u) > 0], key=key, reverse=True)
        return [{**u, "rank": i} for i, u in enumerate(el, 1)][:25]
    cats = [
        {"key": "top", "title": "Top Networks", "kind": "network", "metric": "Score (0–100)",
         "how": "Weighted score below. Networks need 3+ active members.", "rows": ranked(rows, lambda r: r["score"])},
        {"key": "growing", "title": "Fastest-growing Networks", "kind": "network", "metric": "New members in 7 days ÷ existing members",
         "how": "Organic joins only; members can't be bought or imported.", "rows": ranked(rows, lambda r: r["growth"] or 0, lambda r: r["eligible"] and (r["growth"] or 0) > 0)},
        {"key": "active", "title": "Most active Networks", "kind": "network", "metric": "Posts + chat messages in 30 days",
         "how": "Removed posts don't count. Raw likes are not counted.", "rows": ranked(rows, lambda r: r["activity"], lambda r: r["eligible"] and r["activity"] > 0)},
        {"key": "projects", "title": "Project Networks", "kind": "network", "metric": "Score (0–100)",
         "how": "Top Networks filtered to the Project category.", "rows": ranked([r for r in rows if r["type"] == "Project"], lambda r: r["score"])},
        {"key": "collaborators", "title": "Top collaborators", "kind": "user", "metric": "Accepted collaborations",
         "how": "Opportunity applications accepted by the other side (either direction).", "rows": uranked(lambda u: u["collaborations"])},
        {"key": "contributors", "title": "Top contributors", "kind": "user", "metric": "Network posts + replies",
         "how": "Posts inside Networks and replies to others. Re-Networks don't count.", "rows": uranked(lambda u: u["contributions"])},
        {"key": "endorsed", "title": "Most endorsed users", "kind": "user", "metric": "Peer endorsements",
         "how": "Only from people who share a Network or collaborated; one per category per person; max 5/day. Each endorsement is weighted 0.5–1.0 by the endorser's earned XP (0.5 + 0.5 × min(1, XP/1000)), so new or throwaway accounts count for less.", "rows": uranked(lambda u: u["endorsements_weighted"])},
        {"key": "research", "title": "Top research contributors", "kind": "user", "metric": "Research + Trading research endorsements",
         "how": "Peer endorsements in research categories. There is no automated research-quality score yet.", "rows": uranked(lambda u: u["research"])},
        {"key": "callers", "title": "Top Callers", "kind": "user", "metric": "Share of tracked calls that hit 1.5× (min 3 tracked calls)",
         "how": "Entry price is fetched server-side from DexScreener when the call is posted and can't be edited; peaks are tracked afterwards. Labelled 'Tracked call (DexScreener price at post time)', not verified trading.",
         "rows": uranked(lambda u: (u["trading"]["win_rate"] or 0) + 1e-6 if u["trading"]["tracked_calls"] >= 3 else 0)},
    ]
    allranked = ranked(rows, lambda r: r["score"])
    rank_of = {r["id"]: r["rank"] for r in allranked}
    networks = sorted(rows, key=lambda r: (r["id"] not in rank_of, rank_of.get(r["id"], 0)))
    for r in networks: r["rank"] = rank_of.get(r["id"])
    users.sort(key=lambda x: -x["xp"])
    return {"categories": cats, "networks": networks, "users": users[:25],
            "method": [{"factor": f, "weight": w, "how": h} for f, w, h in RANKING_METHOD],
            "notes": ["Rankings use only on-platform records and DexScreener data. Nothing can be bought.",
                      "Member/follower count is not a ranking factor; Networks need at least 3 members to be ranked.",
                      "Private Networks are not ranked publicly.",
                      "Research quality has no automated measure yet; it is shown only as peer endorsements."]}


@app.get("/api/meta")
def meta():
    return {"network_types": NETWORK_TYPES, "endorse_categories": ENDORSE_CATS, "opportunity_categories": OPP_CATS, "project_stages": PROJECT_STAGES,
            "share_keys": SHARE_KEYS, "admin_perms": ADMIN_PERMS, "privacy_keys": PRIVACY_KEYS, "roles": USER_ROLES}


@app.get("/api/search")
def search(q: str = Query("", max_length=60), type: str = "", viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    q = q.strip()
    empty = {"users": [], "networks": [], "projects": [], "opportunities": [], "posts": []}
    if len(q) < 2: return empty
    vid = viewer.id if viewer else 0
    lk = f"%{q.lower()}%"
    users = [user_brief(u) for u in db.scalars(select(User).where(or_(func.lower(User.username).like(lk), func.lower(User.display_name).like(lk), func.lower(User.bio).like(lk))).limit(10))]
    nstmt = select(Network).where(or_(func.lower(Network.name).like(lk), Network.slug.like(lk), func.lower(Network.description).like(lk)))
    if type in NETWORK_TYPES: nstmt = nstmt.where(Network.type == type)
    nets = [network_brief(n, member_count(db, n.id)) for n in db.scalars(nstmt.limit(15))]
    my = my_network_ids(db, vid); g = connection_grants(db, my)
    opps = [opp_out(db, o, vid) for o in db.scalars(select(Opportunity).where(Opportunity.status == "open", or_(
        func.lower(Opportunity.title).like(lk), func.lower(Opportunity.description).like(lk), func.lower(Opportunity.category).like(lk))).limit(20))
        if opp_visible(db, o, vid, my, g)][:10]
    f, *_ = visible_filter(db, vid)
    posts = posts_out(db, list(db.scalars(select(Post).where(f, func.lower(Post.body).like(lk)).order_by(desc(Post.id)).limit(10))), vid)
    return {"users": users, "networks": [n for n in nets if n["type"] != "Project"], "projects": [n for n in nets if n["type"] == "Project"],
            "opportunities": opps, "posts": posts}


@app.get("/api/health")
@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"ok": True, "realtime": "postgres" if hub._thread else "local", "db": "sqlite" if IS_SQLITE else "postgresql"}


# ================================================================= INVITES
def valid_invite(db, code, network_id, uid):
    inv = db.scalar(select(Invite).where(Invite.code == code[:40]))
    if not inv or inv.network_id != network_id or inv.revoked: raise HTTPException(404, "Invalid Network Invite.")
    if aware(inv.expires_at) < utcnow(): raise HTTPException(400, "This Network Invite has expired.")
    if inv.uses >= inv.max_uses: raise HTTPException(400, "This Network Invite has been used up.")
    if inv.invitee_id and inv.invitee_id != uid: raise HTTPException(403, "This Network Invite was issued to someone else.")
    return inv


@app.post("/api/networks/{slug}/invites", dependencies=[rate_limit("invite", 30, 3600)])
def create_invite(slug: str, data: InviteIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if not can(membership(db, n.id, user.id), "perm_members"): raise HTTPException(403, "Only the founder and admins with member permission can create Network Invites.")
    invitee = None
    if data.username.strip():
        invitee = get_user_by_name(db, data.username.strip().lstrip("@"))
        if is_active(membership(db, n.id, invitee.id)): raise HTTPException(400, f"@{invitee.username} is already a member.")
    inv = Invite(code=secrets.token_urlsafe(12), network_id=n.id, created_by=user.id, invitee_id=invitee.id if invitee else None,
                 max_uses=1 if invitee else data.max_uses, expires_at=utcnow() + timedelta(days=data.days))
    db.add(inv)
    if invitee: notify(db, invitee.id, user.id, "invite", f"@{user.username} invited you to join {n.name}", f"#/invite/{inv.code}")
    audit(db, user.id, n.id, "invite.create", invitee.username if invitee else "link", f"uses:{inv.max_uses}", ip_of(request))
    commit(db)
    return {"code": inv.code, "link": f"#/invite/{inv.code}", "expires_at": iso(inv.expires_at), "max_uses": inv.max_uses,
            "invitee": user_brief(invitee) if invitee else None}


@app.get("/api/networks/{slug}/invites")
def list_invites(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if not can(membership(db, n.id, user.id), "perm_members"): raise HTTPException(403, "Not allowed.")
    return [{"id": i.id, "code": i.code, "uses": i.uses, "max_uses": i.max_uses, "expires_at": iso(i.expires_at), "revoked": i.revoked,
             "invitee": user_brief(db.get(User, i.invitee_id)) if i.invitee_id else None}
            for i in db.scalars(select(Invite).where(Invite.network_id == n.id).order_by(desc(Invite.id)).limit(50))]


@app.delete("/api/invites/{iid}")
def revoke_invite(iid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    i = db.get(Invite, iid)
    if not i or not can(membership(db, i.network_id, user.id), "perm_members"): raise HTTPException(403, "Not allowed.")
    i.revoked = True; commit(db)
    return {"ok": True}


@app.get("/api/invites/{code}")
def invite_preview(code: str, db: Session = Depends(get_db)):
    i = db.scalar(select(Invite).where(Invite.code == code[:40]))
    if not i or i.revoked: raise HTTPException(404, "Invalid Network Invite.")
    n = db.get(Network, i.network_id)
    return {"network": network_brief(n, member_count(db, n.id)), "expired": aware(i.expires_at) < utcnow() or i.uses >= i.max_uses,
            "inviter": user_brief(db.get(User, i.created_by)), "personal": bool(i.invitee_id)}


# ================================================================= EVENTS
def event_out(e, n):
    return {"id": e.id, "title": e.title, "description": e.description, "starts_at": iso(e.starts_at), "link": e.link,
            "is_public": e.is_public, "is_demo": e.is_demo, "network": network_brief(n)}


@app.post("/api/networks/{slug}/events", dependencies=[rate_limit("event", 20, 3600)])
def create_event(slug: str, data: EventIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if not can(membership(db, n.id, user.id), "perm_announce"): raise HTTPException(403, "Only the founder and admins with announcement permission can create events.")
    if aware(data.starts_at) < utcnow() - timedelta(hours=1): raise HTTPException(400, "The event must be in the future.")
    e = Event(network_id=n.id, created_by=user.id, title=clean(data.title, 120), description=clean(data.description, 1000),
              starts_at=aware(data.starts_at), link=clean_url(data.link) if data.link else "", is_public=data.is_public)
    db.add(e)
    if data.is_public: record_activity(db, n.id, "events", f"{n.name} scheduled: {e.title} ({e.starts_at:%Y-%m-%d %H:%M} UTC)", f"#/n/{n.slug}")
    commit(db)
    return event_out(e, n)


@app.get("/api/networks/{slug}/events")
def list_events(slug: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    member = is_active(membership(db, n.id, viewer.id if viewer else 0))
    if n.is_private and not member:
        g = connection_grants(db, my_network_ids(db, viewer.id if viewer else 0))
        if n.id not in g["share_events"]: raise HTTPException(403, "This Network's events are private.")
    stmt = select(Event).where(Event.network_id == n.id, Event.starts_at >= utcnow() - timedelta(days=1))
    if not member: stmt = stmt.where(Event.is_public.is_(True))
    return [event_out(e, n) for e in db.scalars(stmt.order_by(Event.starts_at).limit(30))]


@app.delete("/api/events/{eid}")
def delete_event(eid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(Event, eid)
    if not e or not can(membership(db, e.network_id, user.id), "perm_announce"): raise HTTPException(403, "Not allowed.")
    db.delete(e); commit(db)
    return {"ok": True}


# ================================================================= VERIFICATION (pluggable; no provider connected)
@app.post("/api/verifications")
def request_verification():
    """Retired. Identity is now account linking (X / Google sign-in, see app/oauth.py); wallet, domain, dev-wallet,
    metadata-authority and CTO verification have real flows under /api/verify/*. No third-party KYC is used."""
    raise HTTPException(410, "Identity checks now use account linking: link X or Google from Settings. This is account ownership, not a government ID check.")


# ================================================================= NETWORK INTELLIGENCE
@app.get("/api/intelligence")
def intelligence(user: User = Depends(current_user), db: Session = Depends(get_db)):
    my = my_network_ids(db, user.id)
    g = connection_grants(db, my)
    connected = set()
    for c in db.scalars(select(Connection).where(Connection.status == "approved", or_(Connection.requester_id.in_(my), Connection.target_id.in_(my)))):
        for x in (c.requester_id, c.target_id):
            if x not in my: connected.add(x)
    conn_nets = [network_brief(n, member_count(db, n.id)) for n in db.scalars(select(Network).where(Network.id.in_(connected)).limit(12))] if connected else []
    # related projects: Project networks connected to mine, or that members of my networks also joined
    co_members = select(Membership.user_id).where(Membership.network_id.in_(my), Membership.status == "active")
    related = select(Membership.network_id).where(Membership.user_id.in_(co_members), Membership.status == "active")
    proj = [network_brief(n, member_count(db, n.id)) for n in db.scalars(select(Network).where(
        Network.type == "Project", Network.id.not_in(my), or_(Network.id.in_(connected), and_(Network.id.in_(related), Network.is_private.is_(False))))
        .limit(6))] if my else []
    f, _, _ = visible_filter(db, user.id)
    ann_conds = shared_conditions(my, g)
    anns = posts_out(db, list(db.scalars(select(Post).where(f, Post.kind == "announcement", or_(*ann_conds)).order_by(desc(Post.id)).limit(5)))
                     , user.id) if ann_conds else []
    partner = []
    for c in db.scalars(select(Connection).where(Connection.status == "approved").order_by(desc(Connection.decided_at)).limit(40)):
        a, b = db.get(Network, c.requester_id), db.get(Network, c.target_id)
        public = c.req_display_public and c.tgt_display_public
        if public or a.id in my or b.id in my:
            partner.append({"a": network_brief(a), "b": network_brief(b), "at": iso(c.decided_at)})
        if len(partner) >= 6: break
    my_opps = select(Opportunity.id).where(Opportunity.creator_id == user.id)
    collab = {}
    for a, o in db.execute(select(Application, Opportunity).join(Opportunity, Opportunity.id == Application.opportunity_id).where(
            Application.status.in_(["accepted", "completed"]), or_(Application.applicant_id == user.id, Application.opportunity_id.in_(my_opps)))).all():
        other = a.applicant_id if o.creator_id == user.id else o.creator_id
        collab[other] = collab.get(other, 0) + 1
    collaborators = [{**user_brief(db.get(User, k)), "count": v} for k, v in sorted(collab.items(), key=lambda x: -x[1])[:6]]
    week = utcnow() - timedelta(days=7)
    growing = []
    for n in db.scalars(select(Network).where(Network.is_private.is_(False)).limit(300)):
        new7 = db.scalar(select(func.count(Membership.id)).where(Membership.network_id == n.id, Membership.status == "active", Membership.joined_at >= week)) or 0
        if new7: growing.append({**network_brief(n, member_count(db, n.id)), "new_members_7d": new7})
    growing.sort(key=lambda x: -x["new_members_7d"])
    activity = []
    for n in db.scalars(select(Network).where(Network.id.in_(my))) if my else []:
        posts7 = db.scalar(select(func.count(Post.id)).where(Post.network_id == n.id, Post.removed.is_(False), Post.created_at >= week)) or 0
        chats7 = db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.network_id == n.id, ChatMessage.created_at >= week)) or 0
        activity.append({**network_brief(n), "posts_7d": posts7, "chat_7d": chats7})
    followed = select(Follow.followee_id).where(Follow.follower_id == user.id)
    opps = [opp_out(db, o, user.id) for o in db.scalars(select(Opportunity).where(Opportunity.status == "open", Opportunity.creator_id != user.id, or_(
        Opportunity.network_id.in_(my | g["share_opportunities"] | connected), Opportunity.creator_id.in_(followed))).order_by(desc(Opportunity.id)).limit(12))
        if opp_visible(db, o, user.id, my, g)][:5]
    events = []
    ev_nets = my | g["share_events"]
    if ev_nets:
        for e in db.scalars(select(Event).where(Event.network_id.in_(ev_nets), Event.starts_at >= utcnow()).order_by(Event.starts_at).limit(10)):
            if e.network_id in my or e.is_public: events.append(event_out(e, db.get(Network, e.network_id)))
    return {"connected_networks": conn_nets, "related_projects": proj, "recent_announcements": anns, "partnership_activity": partner,
            "collaborators": collaborators, "growing_communities": growing[:6], "network_activity": activity,
            "relevant_opportunities": opps, "upcoming_events": events[:6]}


# ================================================================= WEBSOCKET
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    uid = read_token(websocket.cookies.get(COOKIE))
    await websocket.accept()
    hub.register(websocket)
    rooms = set()
    if uid: hub.users[uid].add(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "join_network" and uid:
                db = SessionLocal()
                try:
                    n = db.scalar(select(Network).where(Network.slug == str(msg.get("slug", ""))[:40]))
                    if n and is_active(membership(db, n.id, uid)):
                        hub.rooms[n.id].add(websocket); rooms.add(n.id)
                        await websocket.send_json({"type": "joined", "network_id": n.id})
                finally:
                    db.close()
            elif msg.get("type") == "leave_networks":
                for r in rooms: hub.rooms[r].discard(websocket)
                rooms.clear()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        hub.unregister(websocket)
        if uid: hub.users[uid].discard(websocket)
        for r in rooms: hub.rooms[r].discard(websocket)


# ================================================================= TRUST: moderation, verification, CTO, activity
from . import trust, oauth, account  # noqa: E402  (router modules import helpers from this module)
app.include_router(trust.router)
app.include_router(account.router)
app.include_router(oauth.router)


# ================================================================= STATIC SPA
app.mount("/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
