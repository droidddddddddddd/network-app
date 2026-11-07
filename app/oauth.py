"""Public sign in / link with X (OAuth 2.0 + PKCE). Legacy Google callback support is retained for migration only.

What this proves: the person controls their X account. It is NOT a government identity check.
What is stored: provider subject id, X handle, verified flag, X account age + follower count.
Provider access/refresh tokens are used once to read the profile and then discarded; they are never stored.
A provider whose CLIENT_ID/CLIENT_SECRET env vars are unset is disabled and its buttons are hidden."""
import base64, hashlib, json, os, re, secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, LinkedAccount, OAuthState
from .security import current_user, optional_user, rate_limit, set_session, hash_pw, check_pw, PROD, COOKIE
from .services import utcnow, aware, audit
from .main import commit, ip_of

router = APIRouter()
BIND_COOKIE = "network_oauth"
STATE_TTL = 600
PLACEHOLDER_EMAIL = "@oauth.invalid"  # accounts created via X have no email; never shown

PROVIDERS = {
    "x": {"name": "X", "authorize": "https://x.com/i/oauth2/authorize", "token": "https://api.x.com/2/oauth2/token",
          "userinfo": "https://api.x.com/2/users/me?user.fields=created_at,public_metrics,username,name,profile_image_url",
          "scope": "users.read tweet.read", "id_env": "X_CLIENT_ID", "secret_env": "X_CLIENT_SECRET"},
    "google": {"name": "Google", "authorize": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
               "userinfo": "https://openidconnect.googleapis.com/v1/userinfo", "scope": "openid email profile",
               "id_env": "GOOGLE_CLIENT_ID", "secret_env": "GOOGLE_CLIENT_SECRET"},
}


def creds(p):
    c = PROVIDERS[p]
    return os.getenv(c["id_env"], "").strip(), os.getenv(c["secret_env"], "").strip()


def enabled(p) -> bool:
    return p in PROVIDERS and all(creds(p))


def provider_or_404(p):
    if p not in PROVIDERS: raise HTTPException(404, "Unknown provider.")
    if not enabled(p): raise HTTPException(404, f"{PROVIDERS[p]['name']} sign-in isn't configured on this server.")
    return PROVIDERS[p]


def redirect_uri(request: Request, p: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/auth/oauth/{p}/callback"


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def has_password(u: User) -> bool:
    return bool(u.password_hash and u.password_hash.startswith("$2"))


def login_methods(db, u: User) -> int:
    return int(has_password(u)) + (db.scalar(select(func.count(LinkedAccount.id)).where(LinkedAccount.user_id == u.id)) or 0)


def done(code: str, p: str, status=303):
    r = RedirectResponse(f"/#/oauth/{code}/{p}", status_code=status)
    r.delete_cookie(BIND_COOKIE, path="/api/auth/oauth")
    return r


# ---------------------------------------------------------------- provider calls (monkeypatched in tests)
def exchange_code(p: str, code: str, verifier: str, redirect: str) -> dict:
    cid, secret = creds(p)
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect, "code_verifier": verifier, "client_id": cid}
    if p == "x":  # confidential client: HTTP Basic auth
        r = httpx.post(PROVIDERS[p]["token"], data=data, auth=(cid, secret), timeout=10)
    else:
        r = httpx.post(PROVIDERS[p]["token"], data={**data, "client_secret": secret}, timeout=10)
    if r.status_code != 200: raise ValueError(f"token endpoint returned {r.status_code}")
    return r.json()


def fetch_userinfo(p: str, access_token: str) -> dict:
    r = httpx.get(PROVIDERS[p]["userinfo"], headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if r.status_code != 200: raise ValueError(f"userinfo returned {r.status_code}")
    return r.json()


def id_token_claims(tok: str) -> dict:
    # Received directly from Google's token endpoint over TLS, so per OIDC Core 3.1.3.7 the TLS server check stands in for
    # signature validation; we still enforce iss, aud, exp and nonce.
    try:
        payload = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except Exception:
        raise ValueError("malformed id_token")


def profile_from(p: str, tokens: dict, nonce: str) -> dict:
    at = tokens.get("access_token")
    if not at: raise ValueError("no access token")
    if p == "x":
        d = (fetch_userinfo(p, at) or {}).get("data") or {}
        if not d.get("id") or not d.get("username"): raise ValueError("X profile missing id/username")
        created = None
        if d.get("created_at"):
            try: created = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
            except ValueError: pass
        return {"subject": str(d["id"]), "handle": d["username"][:100], "name": d.get("name", ""), "email": "", "email_verified": False,
                "account_created_at": created, "followers": (d.get("public_metrics") or {}).get("followers_count")}
    cid, _ = creds(p)
    c = id_token_claims(tokens.get("id_token") or "")
    if c.get("iss") not in ("https://accounts.google.com", "accounts.google.com"): raise ValueError("bad issuer")
    aud = c.get("aud"); aud = aud if isinstance(aud, list) else [aud]
    if cid not in aud: raise ValueError("bad audience")
    if int(c.get("exp", 0)) < utcnow().timestamp(): raise ValueError("id_token expired")
    if not nonce or not secrets.compare_digest(str(c.get("nonce", "")), nonce): raise ValueError("nonce mismatch")
    info = fetch_userinfo(p, at)
    if str(info.get("sub")) != str(c.get("sub")): raise ValueError("userinfo subject mismatch")
    return {"subject": str(c["sub"]), "handle": "", "name": info.get("name", ""), "email": (info.get("email") or "").lower()[:254],
            "email_verified": info.get("email_verified") is True, "account_created_at": None, "followers": None}


# ---------------------------------------------------------------- endpoints
@router.get("/api/auth/oauth/providers")
def providers():
    # NETWORK's public authentication choice is X only. Google support remains in
    # the legacy callback code solely to avoid corrupting already-linked records.
    return {"x": enabled("x")}


@router.get("/api/auth/oauth/{p}/start", dependencies=[rate_limit("oauth", 20, 600)])
def start(p: str, request: Request, mode: str = "login", user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    cfg = provider_or_404(p)
    if mode not in ("login", "link"): raise HTTPException(400, "mode must be login or link")
    if mode == "link" and not user: return done("login_required", p)
    db.execute(delete(OAuthState).where(OAuthState.created_at < utcnow() - timedelta(seconds=STATE_TTL)))
    state, verifier, nonce, bind = secrets.token_urlsafe(32), secrets.token_urlsafe(64), secrets.token_urlsafe(24), secrets.token_urlsafe(32)
    db.add(OAuthState(state=state, browser=sha(bind), provider=p, mode=mode, user_id=user.id if mode == "link" else None,
                      verifier=verifier, nonce=nonce if p == "google" else ""))
    commit(db)
    q = {"response_type": "code", "client_id": creds(p)[0], "redirect_uri": redirect_uri(request, p), "scope": cfg["scope"], "state": state,
         "code_challenge": b64url(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256"}
    if p == "google": q.update(nonce=nonce, prompt="select_account")
    r = RedirectResponse(cfg["authorize"] + "?" + urlencode(q, quote_via=quote), status_code=302)
    r.set_cookie(BIND_COOKIE, bind, max_age=STATE_TTL, httponly=True, samesite="lax", secure=PROD, path="/api/auth/oauth")
    return r


def unique_username(db, base: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "", base)[:16] or "user"
    if len(base) < 3: base = (base + "user")[:16]
    cand = base
    while db.scalar(select(User.id).where(func.lower(User.username) == cand.lower())):
        cand = f"{base}{secrets.randbelow(9000) + 1000}"
    return cand


def apply_profile(la: LinkedAccount, prof: dict):
    la.handle, la.email, la.email_verified = prof["handle"], prof["email"], prof["email_verified"]
    la.account_created_at, la.followers, la.refreshed_at = prof["account_created_at"], prof["followers"], utcnow()


@router.get("/api/auth/oauth/{p}/callback", dependencies=[rate_limit("oauth_cb", 30, 600)])
def callback(p: str, request: Request, code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    provider_or_404(p)
    st = db.scalar(select(OAuthState).where(OAuthState.state == state)) if state else None
    bind = request.cookies.get(BIND_COOKIE, "")
    if not st or st.provider != p or not bind or not secrets.compare_digest(st.browser, sha(bind)):
        return done("bad_state", p)
    db.delete(st); commit(db)  # single use, even if what follows fails
    if (utcnow() - aware(st.created_at)).total_seconds() > STATE_TTL: return done("expired", p)
    if error or not code: return done("denied", p)
    try:
        prof = profile_from(p, exchange_code(p, code, st.verifier, redirect_uri(request, p)), st.nonce)
    except Exception:
        return done("provider_error", p)
    existing = db.scalar(select(LinkedAccount).where(LinkedAccount.provider == p, LinkedAccount.subject == prof["subject"]))
    ip = ip_of(request)
    if st.mode == "link":
        from .security import read_token
        uid = read_token(request.cookies.get(COOKIE))
        if not uid or uid != st.user_id: return done("session_changed", p)
        if existing and existing.user_id != uid: return done("taken", p)
        mine = db.scalar(select(LinkedAccount).where(LinkedAccount.user_id == uid, LinkedAccount.provider == p))
        if mine and mine.subject != prof["subject"]: return done("already_linked", p)
        if p == "google" and not prof["email_verified"]: return done("email_unverified", p)
        la = mine or LinkedAccount(user_id=uid, provider=p, subject=prof["subject"])
        apply_profile(la, prof); db.add(la)
        u = db.get(User, uid)
        if p == "x" and not u.x_handle: u.x_handle = prof["handle"][:20]
        audit(db, uid, None, f"oauth.link.{p}", f"user:{uid}", "", ip); commit(db)
        return done("linked", p)
    # login / sign up
    if existing:
        apply_profile(existing, prof)
        audit(db, existing.user_id, None, f"oauth.login.{p}", f"user:{existing.user_id}", "", ip); commit(db)
        r = done("logged_in", p); set_session(r, existing.user_id); return r
    if p == "google":
        if not prof["email_verified"]: return done("email_unverified", p)
        if db.scalar(select(User.id).where(User.email == prof["email"])):
            # never auto-merge by email: the owner must log in with their password and link Google from Settings
            return done("email_exists", p)
    u = User(username=unique_username(db, prof["handle"] or prof["email"].split("@")[0]),
             email=prof["email"] if p == "google" else f"x_{prof['subject']}{PLACEHOLDER_EMAIL}",
             password_hash="", display_name=(prof["name"] or prof["handle"] or "New member")[:50],
             x_handle=prof["handle"][:20] if p == "x" else "")
    db.add(u); db.flush()
    la = LinkedAccount(user_id=u.id, provider=p, subject=prof["subject"]); apply_profile(la, prof); db.add(la)
    audit(db, u.id, None, f"oauth.signup.{p}", f"user:{u.id}", "", ip); commit(db)
    r = done("signed_up", p); set_session(r, u.id); return r


@router.delete("/api/auth/oauth/{p}")
def unlink(p: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if p not in PROVIDERS: raise HTTPException(404, "Unknown provider.")
    la = db.scalar(select(LinkedAccount).where(LinkedAccount.user_id == user.id, LinkedAccount.provider == p))
    if not la: raise HTTPException(404, "That account isn't linked.")
    if login_methods(db, user) <= 1:
        raise HTTPException(400, "This is your only way to log in. Set a password or link another account first.")
    db.delete(la)
    audit(db, user.id, None, f"oauth.unlink.{p}", f"user:{user.id}", "", ip_of(request)); commit(db)
    return {"ok": True}


class VisibilityIn(BaseModel):
    show_email: bool


@router.put("/api/auth/oauth/google/visibility")
def google_visibility(data: VisibilityIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    la = db.scalar(select(LinkedAccount).where(LinkedAccount.user_id == user.id, LinkedAccount.provider == "google"))
    if not la: raise HTTPException(404, "Google isn't linked.")
    la.show_email = data.show_email; commit(db)
    return {"ok": True, "show_email": la.show_email}


class PasswordIn(BaseModel):
    current: str = Field(default="", max_length=128)
    new: str = Field(min_length=8, max_length=128)


@router.post("/api/me/password", dependencies=[rate_limit("pw", 10, 900)])
def set_password(data: PasswordIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if has_password(user) and not check_pw(data.current, user.password_hash):
        raise HTTPException(403, "Current password is wrong.")
    user.password_hash = hash_pw(data.new)
    audit(db, user.id, None, "auth.password_set", f"user:{user.id}", "", ip_of(request)); commit(db)
    return {"ok": True}
