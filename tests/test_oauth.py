"""X (OAuth 2.0 PKCE) and Google (OIDC) sign-in/linking against MOCKED providers: the provider's HTTP endpoints are
replaced by a fake that checks PKCE, client auth and redirect_uri like the real ones. Real X/Google can't be tested
until the owner registers apps and sets the client id/secret env vars."""
import base64, hashlib, json, time
from urllib.parse import urlparse, parse_qs
import httpx, pytest
from app import oauth
from app.db import SessionLocal
from app.models import LinkedAccount, OAuthState


def b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


class FakeProviders:
    def __init__(self):
        self.codes = {}  # code -> dict(challenge, redirect, identity, nonce, provider)
        self.tokens = {}
        self.calls = []

    def authorize(self, location, identity, provider):
        q = {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}
        assert q["response_type"] == "code" and q["code_challenge_method"] == "S256" and q["state"]
        assert q["client_id"] == f"{provider}-client-id" and q["redirect_uri"].endswith(f"/api/auth/oauth/{provider}/callback")
        code = f"code-{len(self.codes)}"
        self.codes[code] = {"challenge": q["code_challenge"], "redirect": q["redirect_uri"], "identity": identity,
                            "nonce": q.get("nonce", ""), "provider": provider}
        return code, q["state"]

    def post(self, url, data=None, auth=None, timeout=None):
        self.calls.append(("token", url))
        c = self.codes.pop(data["code"], None)  # codes are single use
        if not c: return httpx.Response(400, json={"error": "invalid_grant"})
        p = c["provider"]
        if p == "x": assert auth == ("x-client-id", "x-secret") and url == oauth.PROVIDERS["x"]["token"]
        else: assert data["client_secret"] == "google-secret" and url == oauth.PROVIDERS["google"]["token"]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(data["code_verifier"].encode()).digest()).rstrip(b"=").decode()
        if challenge != c["challenge"] or data["redirect_uri"] != c["redirect"]: return httpx.Response(400, json={"error": "invalid_grant"})
        at = f"at-{len(self.tokens)}"; self.tokens[at] = c
        body = {"access_token": at, "token_type": "bearer", "refresh_token": "rt-should-not-be-stored"}
        if p == "google":
            i = c["identity"]
            body["id_token"] = "e30." + b64({"iss": "https://accounts.google.com", "aud": "google-client-id", "sub": i["sub"],
                                             "exp": int(time.time()) + 300, "nonce": i.get("force_nonce", c["nonce"])}) + ".sig"
        return httpx.Response(200, json=body)

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("userinfo", url))
        c = self.tokens.get(headers["Authorization"].split()[1])
        if not c: return httpx.Response(401)
        i = c["identity"]
        if c["provider"] == "x":
            return httpx.Response(200, json={"data": {"id": i["id"], "username": i["username"], "name": i.get("name", ""),
                                                      "created_at": "2015-06-01T00:00:00.000Z", "public_metrics": {"followers_count": 1234}}})
        return httpx.Response(200, json={"sub": i["sub"], "email": i["email"], "email_verified": i.get("email_verified", True), "name": i.get("name", "")})


@pytest.fixture
def fake(monkeypatch):
    for k, v in {"X_CLIENT_ID": "x-client-id", "X_CLIENT_SECRET": "x-secret", "GOOGLE_CLIENT_ID": "google-client-id",
                 "GOOGLE_CLIENT_SECRET": "google-secret"}.items():
        monkeypatch.setenv(k, v)
    f = FakeProviders()
    monkeypatch.setattr(oauth.httpx, "post", f.post)
    monkeypatch.setattr(oauth.httpx, "get", f.get)
    return f


def flow(c, fake, provider, identity, mode="login", tamper=None):
    r = c.get(f"/api/auth/oauth/{provider}/start?mode={mode}", follow_redirects=False)
    assert r.status_code == 302, r.text
    loc = r.headers["location"]
    assert loc.startswith(oauth.PROVIDERS[provider]["authorize"])
    code, state = fake.authorize(loc, identity, provider)
    if tamper: code, state = tamper(code, state)
    r = c.get(f"/api/auth/oauth/{provider}/callback", params={"code": code, "state": state}, follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"].split("/#/oauth/")[1].split("/")[0]


XID = {"id": "9001", "username": "solana_sam", "name": "Sam"}


def test_disabled_without_env(anon, monkeypatch):
    for k in ("X_CLIENT_ID", "X_CLIENT_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"): monkeypatch.delenv(k, raising=False)
    assert anon.ok("GET", "/api/auth/oauth/providers") == {"x": False}
    assert anon.get("/api/auth/oauth/x/start", follow_redirects=False).status_code == 404
    monkeypatch.setenv("X_CLIENT_ID", "only-id")  # half-configured still counts as disabled
    assert anon.ok("GET", "/api/auth/oauth/providers")["x"] is False


def test_x_signup_login_and_passport(anon, fake, mk):
    assert anon.ok("GET", "/api/auth/oauth/providers") == {"x": True}
    assert flow(anon, fake, "x", XID) == "signed_up"
    me = anon.ok("GET", "/api/me")
    assert me["username"] == "solana_sam" and me["email"] == "" and me["has_password"] is False
    assert me["linked_accounts"][0]["handle"] == "solana_sam" and me["linked_accounts"][0]["followers"] == 1234
    p = mk().ok("GET", "/api/users/solana_sam")
    assert p["verification"]["x_account"]["verified"] and p["verification"]["x_account"]["badge"] == "X account verified (@solana_sam)"
    assert "not a government ID" in p["verification"]["x_account"]["how"]
    x = p["linked_accounts"][0]; assert x["account_age_days"] > 3000 and x["followers"] == 1234
    # nothing token-like is stored anywhere
    with SessionLocal() as db:
        la = db.query(LinkedAccount).filter_by(subject="9001").one()
        assert not any("rt-should" in str(getattr(la, c.name)) or str(getattr(la, c.name)).startswith("at-") for c in LinkedAccount.__table__.columns)
        assert db.query(OAuthState).count() == 0  # state consumed
    # log in again with the same X account from a fresh browser -> same user
    C = type(anon)  # same browser class as the fixture (re-importing conftest would rebuild the test DB)
    b = C()
    assert flow(b, fake, "x", XID) == "logged_in" and b.ok("GET", "/api/me")["username"] == "solana_sam"
    # password login can't be used for an account that has no password
    assert b.post("/api/auth/login", json={"login": "x_9001@oauth.invalid", "password": ""}).status_code in (401, 422)


def test_state_csrf_replay_and_denied(anon, fake):
    C = type(anon)  # same browser class as the fixture (re-importing conftest would rebuild the test DB)
    # state from one browser can't be completed in another (login CSRF)
    r = anon.get("/api/auth/oauth/x/start", follow_redirects=False)
    code, state = fake.authorize(r.headers["location"], XID, "x")
    victim = C()
    r2 = victim.get("/api/auth/oauth/x/callback", params={"code": code, "state": state}, follow_redirects=False)
    assert "/bad_state/" in r2.headers["location"] and victim.ok("GET", "/api/me") is None
    # unknown state, user denial, replayed state
    assert flow(anon, fake, "x", XID, tamper=lambda c, s: (c, "forged")) == "bad_state"
    assert flow(anon, fake, "x", XID, tamper=lambda c, s: ("", s)) == "denied"
    r = anon.get("/api/auth/oauth/x/start", follow_redirects=False)
    code, state = fake.authorize(r.headers["location"], {"id": "77", "username": "replayer"}, "x")
    assert "/signed_up/" in anon.get("/api/auth/oauth/x/callback", params={"code": code, "state": state}, follow_redirects=False).headers["location"]
    assert "/bad_state/" in anon.get("/api/auth/oauth/x/callback", params={"code": code, "state": state}, follow_redirects=False).headers["location"]
    # PKCE: a code exchanged with the wrong verifier is rejected by the provider -> provider_error
    def swap(c, s):
        with SessionLocal() as db:
            st = db.query(OAuthState).filter_by(state=s).one(); st.verifier = "wrong" * 10; db.commit()
        return c, s
    assert flow(C(), fake, "x", {"id": "78", "username": "pkce"}, tamper=swap) == "provider_error"


def test_google_nonce_email_collision_and_privacy(anon, fake, mk):
    C = type(anon)  # same browser class as the fixture (re-importing conftest would rebuild the test DB)
    a = mk("gmailer")  # existing password account with email gmailer@ex.com
    # signing in with a Google account that has the same email does NOT merge accounts
    assert flow(anon, fake, "google", {"sub": "g-1", "email": "gmailer@ex.com"}) == "email_exists"
    assert anon.ok("GET", "/api/me") is None
    # unverified Google email can't sign up
    assert flow(C(), fake, "google", {"sub": "g-2", "email": "new@ex.com", "email_verified": False}) == "email_unverified"
    # wrong nonce in the id_token is rejected
    assert flow(C(), fake, "google", {"sub": "g-3", "email": "n3@ex.com", "force_nonce": "evil"}) == "provider_error"
    # the owner links Google while logged in
    assert flow(a, fake, "google", {"sub": "g-1", "email": "gmailer@ex.com"}, mode="link") == "linked"
    viewer = mk()
    p = viewer.ok("GET", "/api/users/gmailer")
    assert p["verification"]["google_account"]["badge"] == "Google account verified"
    assert "gmailer@ex.com" not in json.dumps(p)  # email never public by default
    a.ok("PUT", "/api/auth/oauth/google/visibility", json={"show_email": True})
    assert viewer.ok("GET", "/api/users/gmailer")["linked_accounts"][0]["email"] == "gmailer@ex.com"
    # and now Google login works for that account
    b = C()
    assert flow(b, fake, "google", {"sub": "g-1", "email": "gmailer@ex.com"}) == "logged_in" and b.ok("GET", "/api/me")["username"] == "gmailer"


def test_link_collisions_and_unlink(anon, fake, mk):
    C = type(anon)  # same browser class as the fixture (re-importing conftest would rebuild the test DB)
    a, b = mk("linker_a"), mk("linker_b")
    assert flow(a, fake, "x", {"id": "500", "username": "a_on_x"}, mode="link") == "linked"
    # same X account can't be linked to a second NETWORK account
    assert flow(b, fake, "x", {"id": "500", "username": "a_on_x"}, mode="link") == "taken"
    # a second, different X account can't be linked while one is linked
    assert flow(a, fake, "x", {"id": "501", "username": "a_alt"}, mode="link") == "already_linked"
    # link mode requires being logged in
    assert "/login_required/" in C().get("/api/auth/oauth/x/start?mode=link", follow_redirects=False).headers["location"]
    # unlink: allowed while a password exists
    a.ok("DELETE", "/api/auth/oauth/x")
    assert a.ok("GET", "/api/me")["linked_accounts"] == []
    # an X-only account can't remove its only login method until it sets a password
    o = C(); assert flow(o, fake, "x", {"id": "600", "username": "only_x"}) == "signed_up"
    assert o.delete("/api/auth/oauth/x").status_code == 400
    o.ok("POST", "/api/me/password", json={"new": "a-strong-pass-1"})
    assert o.ok("GET", "/api/me")["has_password"] is True
    o.ok("DELETE", "/api/auth/oauth/x")
    assert C().ok("POST", "/api/auth/login", json={"login": "only_x", "password": "a-strong-pass-1"})["username"] == "only_x"
    # changing an existing password needs the current one
    assert o.post("/api/me/password", json={"current": "nope", "new": "another-pass-2"}).status_code == 403
