import os, re, time, html
from collections import defaultdict, deque
import bcrypt, jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .db import get_db
from .models import User

SECRET = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or "dev-only-insecure-secret-change-me"
PROD = os.getenv("ENV", "development") == "production"
if PROD and SECRET.startswith("dev-only"):
    raise RuntimeError("Set JWT_SECRET (or SECRET_KEY) in production.")
COOKIE = "network_session"


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt(12)).decode()


def check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], h.encode())
    except ValueError:
        return False


def make_token(uid: int) -> str:
    return jwt.encode({"uid": uid, "exp": int(time.time()) + 30 * 86400}, SECRET, algorithm="HS256")


def read_token(tok: str | None) -> int | None:
    if not tok:
        return None
    try:
        return int(jwt.decode(tok, SECRET, algorithms=["HS256"])["uid"])
    except Exception:
        return None


def set_session(resp, uid: int):
    resp.set_cookie(COOKIE, make_token(uid), httponly=True, samesite="lax", secure=PROD, max_age=30 * 86400, path="/")


def token_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return request.cookies.get(COOKIE)


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    uid = read_token(token_from_request(request))
    return db.get(User, uid) if uid else None


def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise HTTPException(401, "Please log in first.")
    return user


# ---- DB-backed sliding-window rate limiter: correct across processes and instances ----
NEW_ACCOUNT_HOURS = 24
_hits: dict = {}  # kept for backwards compatibility; unused


def reset_rate_limits():
    from .db import SessionLocal
    from .models import RateHit
    with SessionLocal() as db:
        db.query(RateHit).delete(); db.commit()


def rate_limit(name: str, limit: int, window: int, new_limit: int | None = None):
    """`new_limit` applies instead of `limit` to accounts younger than 24h (stricter limits for new accounts)."""
    def dep(request: Request):
        from datetime import datetime, timezone
        from sqlalchemy import select, func, delete
        from .db import SessionLocal
        from .models import RateHit
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
        uid = read_token(token_from_request(request))
        key = f"{name}:{uid}" if uid else f"{name}:ip:{ip}"
        t = time.time()
        with SessionLocal() as db:
            lim = limit
            if new_limit is not None and uid:
                u = db.get(User, uid)
                if u:
                    ca = u.created_at if u.created_at.tzinfo else u.created_at.replace(tzinfo=timezone.utc)
                    if (datetime.now(timezone.utc) - ca).total_seconds() < NEW_ACCOUNT_HOURS * 3600: lim = new_limit
            n = db.scalar(select(func.count(RateHit.id)).where(RateHit.key == key, RateHit.ts > t - window)) or 0
            if n >= lim:
                raise HTTPException(429, "Too many requests. Slow down and try again shortly."
                                    + (" New accounts have lower limits for their first 24 hours." if lim != limit else ""))
            db.add(RateHit(key=key, ts=t))
            if int(t) % 50 == 0: db.execute(delete(RateHit).where(RateHit.ts < t - 86400))
            db.commit()
    return Depends(dep)


ADMIN_USERNAMES = {x.strip().lower() for x in os.getenv("ADMIN_USERNAMES", "").split(",") if x.strip()}


def is_platform_admin(u) -> bool:
    """Platform admins are configured only via the ADMIN_USERNAMES env var, never through the UI."""
    return bool(u) and u.username.lower() in {x.strip().lower() for x in os.getenv("ADMIN_USERNAMES", "").split(",") if x.strip()}


def suspended(u) -> bool:
    from datetime import datetime, timezone
    if not u or not u.suspended_until: return False
    su = u.suspended_until if u.suspended_until.tzinfo else u.suspended_until.replace(tzinfo=timezone.utc)
    return su > datetime.now(timezone.utc)


def ensure_active(u):
    if suspended(u):
        until = u.suspended_until
        indefinite = until.year >= 9000
        raise HTTPException(403, "Your account is suspended" + ("" if indefinite else f" until {until:%Y-%m-%d %H:%M} UTC") + ". You can't post, message or endorse.")


# ---- input cleaning: strip tags/control chars; output is always escaped client-side too ----
_TAG = re.compile(r"<[^>]*>")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(s, max_len=2000) -> str:
    s = html.unescape(_TAG.sub("", str(s or "")))
    return _CTRL.sub("", s).strip()[:max_len]


def clean_url(s) -> str:
    s = clean(s, 500)
    if not s:
        return ""
    if s.startswith("/uploads/") or s.startswith("/media/") or re.match(r"^https?://[^\s<>\"']+$", s):
        return s
    raise HTTPException(400, "Image/link must be an http(s) URL or an uploaded file.")


SOL_ADDR = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def extract_tags(body: str) -> str:
    tags = []
    for m in re.finditer(r"\$([A-Za-z][A-Za-z0-9]{0,14})\b|#([A-Za-z0-9_]{2,30})|\b([1-9A-HJ-NP-Za-km-z]{32,44})\b", body):
        t = f"${m.group(1).upper()}" if m.group(1) else (f"#{m.group(2).lower()}" if m.group(2) else m.group(3))
        if t not in tags:
            tags.append(t)
    return " ".join(tags[:10])


def extract_mentions(body: str) -> list[str]:
    return list(dict.fromkeys(m.lower() for m in re.findall(r"@([A-Za-z0-9_]{3,20})\b", body)))[:10]
