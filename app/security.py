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


# ---- in-memory sliding-window rate limiter (single instance; fine for Render free tier) ----
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(name: str, limit: int, window: int):
    def dep(request: Request):
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
        key = f"{name}:{ip}:{read_token(token_from_request(request)) or ''}"
        q, t = _hits[key], time.time()
        while q and q[0] < t - window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "Too many requests — slow down and try again shortly.")
        q.append(t)
    return Depends(dep)


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
    if s.startswith("/uploads/") or re.match(r"^https?://[^\s<>\"']+$", s):
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
