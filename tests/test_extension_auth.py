"""Extension auth/permissions are exercised against Alembic's real isolated test schema."""
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlparse, parse_qs
import pytest
from test_oauth import fake  # reuse the provider transport mock, never a production auth bypass
from app.db import SessionLocal
from app.models import ExtensionAuthRequest, ExtensionSession, User, LinkedAccount, Call, Post
from app.extension_auth import digest, challenge_for
from app.services import utcnow
from app import security
from app.log_safety import AuthQueryFilter

ORIGIN = "chrome-extension://" + "a" * 32
OTHER = "chrome-extension://" + "b" * 32


def handoff(c, fake, monkeypatch):
    monkeypatch.setenv("EXTENSION_ORIGINS", ORIGIN + "," + OTHER)
    verifier, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    r = c.get("/api/extension/auth/start", params={"extension_id": "a" * 32, "challenge": challenge_for(verifier), "state": state}, follow_redirects=False)
    assert r.status_code == 302
    r = c.get(r.headers["location"], follow_redirects=False)
    assert r.status_code == 302
    identity = {"id": secrets.token_hex(8), "username": "ext_" + secrets.token_hex(5)}
    code, provider_state = fake.authorize(r.headers["location"], identity, "x")
    r = c.get("/api/auth/oauth/x/callback", params={"state": provider_state, "code": code}, follow_redirects=False)
    redirect = urlparse(r.headers["location"])
    assert redirect.scheme == "https" and redirect.hostname == "a" * 32 + ".chromiumapp.org"
    assert redirect.path == "/network"
    assert r.headers["referrer-policy"] == "no-referrer"
    q = parse_qs(redirect.query)
    assert q["state"] == [state] and set(q) == {"code", "state"}
    return q["code"][0], verifier


def exchange(c, code, verifier, origin=ORIGIN):
    return c.post("/api/extension/auth/exchange", headers={"Origin": origin}, json={"code": code, "verifier": verifier})


def test_pkce_one_time_origin_binding_logout_and_web_scope(anon, fake, monkeypatch):
    code, verifier = handoff(anon, fake, monkeypatch)
    assert exchange(anon, code, "z" * 43).status_code == 400
    assert exchange(anon, code, verifier, OTHER).status_code == 400
    assert exchange(anon, code, verifier, "https://evil.invalid").status_code == 403
    result = exchange(anon, code, verifier)
    assert result.status_code == 200
    token = result.json()["token"]
    assert result.headers["cache-control"] == "no-store"
    assert exchange(anon, code, verifier).status_code == 400
    with SessionLocal() as db:
        assert db.query(ExtensionAuthRequest).filter_by(code_hash=digest(code), used=True).one()
        row = db.query(ExtensionSession).filter_by(token_hash=digest(token)).one()
        assert row.token_hash != token and row.expires_at is not None
    headers = {"Origin": ORIGIN, "Authorization": "Bearer " + token}
    assert anon.get("/api/extension/me", headers=headers).status_code == 200
    # Chrome host-permitted worker fetch omits Origin; explicit registered ID + bearer is required.
    assert anon.get("/api/extension/me", headers={"x-network-extension": "a" * 32, "Authorization": "Bearer " + token}).status_code == 200
    assert anon.get("/api/extension/me", headers={"Authorization": "Bearer " + token}).status_code == 403
    assert anon.get("/api/extension/me", headers={**headers, "x-network-extension": "b" * 32}).status_code == 403
    assert anon.get("/api/extension/me", headers={"Origin": OTHER, "Authorization": "Bearer " + token}).status_code == 401
    # Top-level OAuth created a website cookie too; neither surface accepts the other's credential.
    assert anon.get("/api/extension/me", headers={"Origin": ORIGIN}).status_code == 401
    assert anon.get("/api/me", headers={"Authorization": "Bearer " + token}).json() is None
    assert anon.post("/api/extension/auth/logout", headers=headers).status_code == 200
    assert anon.get("/api/extension/me", headers=headers).status_code == 401


def test_expired_codes_sessions_and_missing_bind(anon, fake, monkeypatch):
    code, verifier = handoff(anon, fake, monkeypatch)
    with SessionLocal() as db:
        row = db.query(ExtensionAuthRequest).filter_by(code_hash=digest(code)).one()
        row.expires_at = utcnow() - timedelta(seconds=1); db.commit()
    assert exchange(anon, code, verifier).status_code == 400
    code, verifier = handoff(anon, fake, monkeypatch)
    token = exchange(anon, code, verifier).json()["token"]
    with SessionLocal() as db:
        row = db.query(ExtensionSession).filter_by(token_hash=digest(token)).one()
        row.expires_at = utcnow() - timedelta(seconds=1); db.commit()
    assert anon.get("/api/extension/me", headers={"Origin": ORIGIN, "Authorization": "Bearer " + token}).status_code == 401
    r = anon.get("/api/extension/auth/start", params={"extension_id": "a" * 32, "challenge": challenge_for(verifier), "state": secrets.token_urlsafe(32)}, follow_redirects=False)
    anon.cookies.clear()
    assert anon.get(r.headers["location"], follow_redirects=False).status_code == 400


def session_for(c, uid):
    token = secrets.token_urlsafe(32)
    with SessionLocal() as db:
        db.add(ExtensionSession(user_id=uid, token_hash=digest(token), extension_id="a" * 32, expires_at=utcnow() + timedelta(hours=1)))
        db.get(User, uid).created_at = utcnow() - timedelta(days=3)
        db.commit()
    return {"Origin": ORIGIN, "Authorization": "Bearer " + token}


def test_authenticated_permissions_actions_csrf_and_public_context(mk, monkeypatch):
    monkeypatch.setenv("EXTENSION_ORIGINS", ORIGIN)
    owner, outsider = mk(), mk()
    network = owner.ok("POST", "/api/networks", json={"name": "Extension membership", "type": "Trading", "is_private": True})
    private = owner.ok("POST", "/api/posts", json={"body": "PRIVATE EXTENSION CONTENT", "network_id": network["id"]})
    public = owner.ok("POST", "/api/posts", json={"body": "public extension context"})
    own_h, other_h = session_for(owner, owner.id), session_for(outsider, outsider.id)
    assert private["id"] in [p["id"] for p in owner.get("/api/extension/feed", headers=own_h).json()["posts"]]
    assert private["id"] not in [p["id"] for p in outsider.get("/api/extension/feed", headers=other_h).json()["posts"]]
    assert outsider.post("/api/extension/posts", headers=other_h, json={"body": "unauthorized", "network_id": network["id"]}).status_code == 403
    assert outsider.post(f"/api/extension/posts/{private['id']}/like", headers=other_h).status_code == 404
    assert outsider.post("/api/extension/posts", headers=other_h, json={"body": "unauthorized reply", "parent_id": private["id"]}).status_code == 404
    security.reset_rate_limits()
    post = owner.post("/api/extension/posts", headers=own_h, json={"body": "member extension post", "network_id": network["id"]})
    assert post.status_code == 200
    pid = post.json()["id"]
    assert owner.post(f"/api/extension/posts/{pid}/like", headers=own_h).json()["liked"] is True
    reply = owner.post("/api/extension/posts", headers=own_h, json={"body": "member extension reply", "parent_id": pid})
    assert reply.status_code == 200
    assert owner.get(f"/api/extension/posts/{pid}", headers=own_h).json()["replies"][0]["id"] == reply.json()["id"]
    assert owner.post("/api/extension/posts", headers={**own_h, "x-csrf": ""}, json={"body": "CSRF"}).status_code == 403
    assert owner.post("/api/extension/posts", headers={**own_h, "Origin": "https://evil.invalid"}, json={"body": "CSRF"}).status_code == 403
    with SessionLocal() as db:
        db.add(LinkedAccount(user_id=owner.id, provider="x", subject="context-" + str(owner.id), handle="ctx_member"))
        for p in (private, public):
            db.add(Call(user_id=owner.id, post_id=p["id"], network_id=p.get("network", {}).get("id") if p.get("network") else None, symbol="CTX", token_address="1" * 32))
        db.commit()
    context = owner.get("/api/extension/context?symbol=CTX&handle=ctx_member", headers=own_h).json()
    assert context["scope"] == "public" and len(context["calls"]) == 1
    assert context["calls"][0]["post_id"] == public["id"]
    assert "email" not in context["profiles"][0]
    with SessionLocal() as db:
        db.get(User, owner.id).suspended_until = utcnow() + timedelta(hours=1); db.commit()
    assert owner.post(f"/api/extension/posts/{pid}/like", headers=own_h).status_code == 403


def test_auth_queries_redacted_from_access_logs():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 1, "%s %s %s %s %s", ("client", "GET", "/api/extension/auth/start?code=do-not-log", "HTTP/1.1", 302), None)
    AuthQueryFilter().filter(record)
    assert "do-not-log" not in record.getMessage()


def test_authorization_code_cannot_be_consumed_concurrently(anon, fake, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from app.main import app
    code, verifier = handoff(anon, fake, monkeypatch)
    def claim(_):
        with TestClient(app) as c:
            return c.post("/api/extension/auth/exchange", headers={"Origin": ORIGIN, "x-csrf": "1"}, json={"code": code, "verifier": verifier}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    assert sorted(results) == [200, 400]


def test_provider_denial_closes_extension_handoff_without_a_session(anon, fake, monkeypatch):
    monkeypatch.setenv("EXTENSION_ORIGINS", ORIGIN)
    state = secrets.token_urlsafe(32)
    r = anon.get("/api/extension/auth/start", params={"extension_id": "a" * 32, "challenge": challenge_for(secrets.token_urlsafe(32)), "state": state}, follow_redirects=False)
    r = anon.get(r.headers["location"], follow_redirects=False)
    provider_state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = anon.get("/api/auth/oauth/x/callback", params={"state": provider_state, "error": "access_denied"}, follow_redirects=False)
    redirect = urlparse(r.headers["location"])
    assert redirect.hostname == "a" * 32 + ".chromiumapp.org"
    assert parse_qs(redirect.query) == {"error": ["denied"], "state": [state]}
    assert anon.get("/api/extension/me", headers={"Origin": ORIGIN}).status_code == 401
