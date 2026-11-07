"""Extension-only PKCE authorization code flow; opaque one-hour bearer sessions.
No provider tokens are stored. Codes are one-use, hashed and valid for 60 seconds.
"""
import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from .db import get_db
from .models import ExtensionAuthRequest, ExtensionSession, User
from .services import utcnow, aware
from .security import PROD, ensure_active, rate_limit, set_session
from .extension import extension_origins

router = APIRouter()
BIND_COOKIE = "network_extension_bind"
SESSION_SECONDS = 3600


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def challenge_for(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def allowed_id(eid):
    return "chrome-extension://" + eid in extension_origins()


def require_origin(request):
    origin = request.headers.get("origin", "")
    eid = request.headers.get("x-network-extension", "")
    # Chrome host-permitted worker requests can omit Origin. The explicit extension
    # header is a CSRF/CORS boundary, not authentication: token/PKCE remains mandatory.
    if origin:
        if origin not in extension_origins() or (eid and origin != "chrome-extension://" + eid):
            raise HTTPException(403, "Unregistered extension origin.")
        return origin.removeprefix("chrome-extension://")
    if eid and allowed_id(eid):
        return eid
    raise HTTPException(403, "Unregistered extension origin.")



def pending_auth(db, request, rid):
    row = db.get(ExtensionAuthRequest, rid)
    bind = request.cookies.get(BIND_COOKIE, "")
    if (not row or row.used or row.code_hash or not allowed_id(row.extension_id)
            or aware(row.expires_at) <= utcnow() or not bind or not secrets.compare_digest(row.browser, digest(bind))):
        raise HTTPException(400, "Invalid or expired extension authorization. Start again.")
    return row


@router.get("/api/extension/auth/start", dependencies=[rate_limit("extension_auth", 20, 600)])
def auth_start(response: Response, extension_id: str = Query(pattern=r"^[a-p]{32}$"),
               challenge: str = Query(pattern=r"^[A-Za-z0-9_-]{43}$"),
               state: str = Query(pattern=r"^[A-Za-z0-9_-]{32,128}$"), db: Session = Depends(get_db)):
    if not allowed_id(extension_id): raise HTTPException(403, "Unregistered extension.")
    rid, bind = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute(delete(ExtensionAuthRequest).where(ExtensionAuthRequest.expires_at < utcnow()))
    db.add(ExtensionAuthRequest(id=rid, extension_id=extension_id, challenge=challenge, state=state,
                               browser=digest(bind), expires_at=utcnow() + timedelta(minutes=10)))
    db.commit()
    result = RedirectResponse("/api/auth/oauth/x/start?" + urlencode({"extension_request": rid}), status_code=302)
    result.set_cookie(BIND_COOKIE, bind, httponly=True, secure=PROD, samesite="lax", max_age=600, path="/api/")
    result.headers["Cache-Control"] = "no-store"
    return result


def finish_auth(db, request, rid, user):
    row = pending_auth(db, request, rid)
    ensure_active(user)
    code = secrets.token_urlsafe(32)
    row.code_hash, row.user_id, row.expires_at = digest(code), user.id, utcnow() + timedelta(seconds=60)
    db.commit()
    # Chrome intercepts this exact extension-owned redirect; never a configurable open redirect.
    redirect = f"https://{row.extension_id}.chromiumapp.org/network?" + urlencode({"code": code, "state": row.state})
    result = RedirectResponse(redirect, status_code=303)
    result.delete_cookie(BIND_COOKIE, path="/api/")
    result.delete_cookie("network_oauth", path="/api/auth/oauth")
    set_session(result, user.id)  # normal top-level browser session, not shared with extension
    result.headers["Cache-Control"] = "no-store"
    result.headers["Referrer-Policy"] = "no-referrer"
    return result


def fail_auth(db, request, rid, error):
    """Return known OAuth failures to the initiating identity window instead of hanging it."""
    row = db.get(ExtensionAuthRequest, rid)
    bind = request.cookies.get(BIND_COOKIE, "")
    if not row or not bind or not allowed_id(row.extension_id) or not secrets.compare_digest(row.browser, digest(bind)):
        raise HTTPException(400, "Invalid extension authorization.")
    row.used = True
    db.commit()
    result = RedirectResponse(f"https://{row.extension_id}.chromiumapp.org/network?" + urlencode({"error": error, "state": row.state}), status_code=303)
    result.delete_cookie(BIND_COOKIE, path="/api/")
    result.delete_cookie("network_oauth", path="/api/auth/oauth")
    result.headers["Cache-Control"] = "no-store"
    result.headers["Referrer-Policy"] = "no-referrer"
    return result


class ExchangeIn(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{40,64}$")
    verifier: str = Field(pattern=r"^[A-Za-z0-9._~-]{43,128}$")


@router.post("/api/extension/auth/exchange", dependencies=[rate_limit("extension_exchange", 30, 600)])
def exchange(data: ExchangeIn, request: Request, response: Response, db: Session = Depends(get_db)):
    eid = require_origin(request)
    row = db.scalar(select(ExtensionAuthRequest).where(ExtensionAuthRequest.code_hash == digest(data.code)))
    if (not row or row.extension_id != eid or row.used or aware(row.expires_at) <= utcnow()
            or not secrets.compare_digest(row.challenge, challenge_for(data.verifier))):
        raise HTTPException(400, "Invalid or expired authorization code.")
    user = db.get(User, row.user_id)
    if not user: raise HTTPException(400, "Invalid authorization.")
    ensure_active(user)
    # Single conditional DB update, not a race-prone read/modify/write consume.
    claimed = db.execute(update(ExtensionAuthRequest).where(ExtensionAuthRequest.id == row.id,
        ExtensionAuthRequest.used.is_(False), ExtensionAuthRequest.expires_at > utcnow()).values(used=True).returning(ExtensionAuthRequest.id).execution_options(synchronize_session=False)).first()
    if not claimed:
        db.rollback(); raise HTTPException(400, "Authorization code already consumed.")
    raw = secrets.token_urlsafe(32)
    expiry = utcnow() + timedelta(seconds=SESSION_SECONDS)
    db.execute(delete(ExtensionSession).where(ExtensionSession.expires_at < utcnow()))
    db.add(ExtensionSession(token_hash=digest(raw), user_id=user.id, extension_id=eid, expires_at=expiry))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"token": raw, "expires_at": expiry.isoformat(), "user": {"id": user.id, "username": user.username}}


def optional_extension_user(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    if not auth: return None  # never trust a site's session cookie on this surface
    eid = require_origin(request)
    if not auth.startswith("Bearer "): raise HTTPException(401, "Extension sign-in required.")
    row = db.scalar(select(ExtensionSession).where(ExtensionSession.token_hash == digest(auth[7:])))
    if not row or row.extension_id != eid or aware(row.expires_at) <= utcnow():
        raise HTTPException(401, "Extension session expired. Sign in again.")
    user = db.get(User, row.user_id)
    if not user: raise HTTPException(401, "Extension session expired.")
    ensure_active(user)
    return user


def extension_user(user: User | None = Depends(optional_extension_user)):
    if not user: raise HTTPException(401, "Sign in to the extension first.")
    return user


@router.get("/api/extension/me")
def me(response: Response, user: User = Depends(extension_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"id": user.id, "username": user.username}


@router.post("/api/extension/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(extension_user), db: Session = Depends(get_db)):
    db.execute(delete(ExtensionSession).where(ExtensionSession.token_hash == digest(request.headers["authorization"][7:])))
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True}
