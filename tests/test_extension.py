"""Credential-free extension surface, exact CORS allowlist, and unchanged framing protection."""
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.extension import ExtensionCORSMiddleware, WebCORSMiddleware, extension_origins
from app.db import SessionLocal
from app.models import User, Verification

ORIGIN = "chrome-extension://" + "a" * 32


def test_extension_cors_is_exact_get_only_and_scoped(monkeypatch):
    monkeypatch.setenv("EXTENSION_ORIGINS", ORIGIN)
    a = FastAPI()
    @a.get("/api/extension/feed")
    @a.get("/api/me")
    def data(): return {"ok": True}
    a.add_middleware(WebCORSMiddleware, allow_origins=["https://trusted.example"], allow_credentials=True, allow_methods=["GET", "POST"])
    a.add_middleware(ExtensionCORSMiddleware)
    c = TestClient(a)
    for origin, allowed in ((ORIGIN, True), ("chrome-extension://" + "b" * 32, False),
                            ("https://evil.example", False), ("null", False)):
        r = c.get("/api/extension/feed", headers={"Origin": origin})
        assert (r.headers.get("access-control-allow-origin") == origin) == allowed
        assert "access-control-allow-credentials" not in r.headers
    assert "access-control-allow-origin" not in c.get("/api/me", headers={"Origin": ORIGIN}).headers
    assert c.options("/api/extension/feed", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}).status_code == 400
    for method, code in (("GET", 200), ("POST", 400), ("DELETE", 400)):
        r = c.options("/api/extension/feed", headers={"Origin": ORIGIN, "Access-Control-Request-Method": method})
        assert r.status_code == code
        assert r.headers["access-control-allow-methods"] == "GET"


def test_empty_allowlist_denies_cross_origin(monkeypatch):
    monkeypatch.delenv("EXTENSION_ORIGINS", raising=False)
    assert extension_origins() == []


@pytest.mark.parametrize("value", ["*", "chrome-extension://*", "https://x.com", ORIGIN + "/", "chrome-extension://" + "z" * 32])
def test_extension_origins_fail_closed(monkeypatch, value):
    monkeypatch.setenv("EXTENSION_ORIGINS", value)
    with pytest.raises(ValueError): extension_origins()


def test_main_site_keeps_anti_framing(anon):
    rejected = anon.post("/api/posts", headers={"x-csrf": ""}, json={"body": "blocked"})
    assert rejected.status_code == 403 and rejected.headers["x-frame-options"] == "DENY"
    for path in ("/", "/api/extension/feed", "/api/me"):
        r = anon.get(path)
        assert r.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_extension_feed_never_includes_private_or_hidden_posts(mk, anon):
    a = mk()
    public = a.ok("POST", "/api/posts", json={"body": "extension public post"})
    n = a.ok("POST", "/api/networks", json={"name": "Extension Private", "type": "Personal", "is_private": True})
    private = a.ok("POST", "/api/posts", json={"body": "extension private secret", "network_id": n["id"]})
    from app.models import Post
    hidden = a.ok("POST", "/api/posts", json={"body": "extension hidden secret"})
    with SessionLocal() as db:
        db.get(Post, hidden["id"]).hidden = True
        db.commit()
    for c in (a, anon):  # a is a member; even their cookie must not personalize extension data
        r = c.get("/api/extension/feed")
        assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
        data = r.json()
        assert data["scope"] == "public" and data["read_only"] is True
        ids = [p["id"] for p in data["posts"]]
        assert public["id"] in ids and private["id"] not in ids and hidden["id"] not in ids
        assert "password" not in r.text and "@ex.com" not in r.text
        assert set(data["posts"][0]) == {"id", "body", "author", "is_demo", "created_at"}


def test_password_signup_disabled_but_existing_login_works(anon, mk):
    r = anon.post("/api/auth/register", json={"username": "no_signup", "email": "none@example.invalid", "password": "password123"})
    assert r.status_code == 403 and "Continue with X" in r.text
    with SessionLocal() as db:
        assert db.query(User).filter_by(username="no_signup").first() is None
    a = mk()
    a.ok("POST", "/api/auth/logout")
    a.ok("POST", "/api/auth/login", json={"login": a.username, "password": "password123"})


def test_wallet_records_preserved_but_not_exposed_when_off(mk, anon, monkeypatch):
    a = mk()
    address = "11111111111111111111111111111111"
    with SessionLocal() as db:
        u = db.get(User, a.id); u.wallet_address = address; u.wallet_verified = True
        db.add(Verification(subject_type="user", subject_id=a.id, kind="wallet", status="verified", value=address))
        db.commit()
    monkeypatch.setenv("ENABLE_WALLET_FEATURES", "0")
    me = a.ok("GET", "/api/me")
    assert me["wallet_address"] == "" and me["wallet_verified"] is False
    for c in (a, anon):
        profile = c.ok("GET", "/api/users/" + a.username)
        assert profile["wallet_address"] == "" and "wallet" not in profile["verification"]
        assert address not in json.dumps(profile)
    a.ok("PUT", "/api/me", json={"display_name": "Edited"})
    with SessionLocal() as db:
        u = db.get(User, a.id)
        assert u.wallet_address == address and u.wallet_verified is True


def test_extension_has_no_frames_or_secrets_and_uses_official_logo():
    root = Path(__file__).resolve().parents[1]
    html = (root / "extension/sidepanel.html").read_text()
    js = (root / "extension/sidepanel.js").read_text()
    assert "<iframe" not in html and "credentials: 'omit'" in js and "textContent" in js
    assert (root / "extension/logo.svg").read_bytes() == (root / "static/img/logo.svg").read_bytes()
    manifest = json.loads((root / "extension/manifest.json").read_text())
    assert manifest["permissions"] == ["sidePanel"]
    assert "frame-src 'none'" in manifest["content_security_policy"]["extension_pages"]
