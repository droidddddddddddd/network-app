"""Section 22 acceptance tests, run against a real Alembic-migrated SQLite DB through the HTTP API."""
from datetime import datetime, timedelta, timezone
from app import security
import pytest


def net(c, name, typ="Trading", private=False):
    return c.ok("POST", "/api/networks", json={"name": name, "type": typ, "is_private": private, "description": "test network"})


def test_health_and_meta(anon):
    assert anon.ok("GET", "/health")["ok"] is True
    m = anon.ok("GET", "/api/meta")
    assert m["network_types"] == ["Personal", "Trading", "KOL", "Alpha Communities", "Marketing", "Project"]
    assert len(m["endorse_categories"]) == 8 and m["roles"]


def test_user_login_logout_profile(mk, anon):
    a = mk("alice1")
    assert a.ok("GET", "/api/me")["username"] == "alice1"
    a.ok("POST", "/api/auth/logout")
    assert a.get("/api/me").json() is None
    a.ok("POST", "/api/auth/login", json={"login": "alice1", "password": "password123"})
    r = a.post("/api/auth/login", json={"login": "alice1", "password": "wrongpass1"}); assert r.status_code == 401
    me = a.ok("PUT", "/api/me", json={"display_name": "Alice", "bio": "hi", "website": "https://ex.com", "telegram": "alice_tg", "show_socials": False})
    assert me["display_name"] == "Alice" and me["privacy"]["show_socials"] is False
    p = anon.ok("GET", "/api/users/alice1")
    assert p["telegram"] == "" and p["website"] == "" and "show_socials" in p["hidden_sections"]  # privacy enforced server-side


def test_csrf_and_auth_required(anon):
    r = anon.c.post("/api/posts", json={"body": "x"}, headers={"x-csrf": ""}); assert r.status_code in (401, 403)
    r = anon.post("/api/posts", json={"body": "x"}); assert r.status_code == 401


def test_post_reply_endorse_renetwork_notifications(mk):
    a, b = mk(), mk()
    p = a.ok("POST", "/api/posts", json={"body": "hello $SOL #alpha"})
    b.ok("POST", "/api/posts", json={"body": "nice reply", "parent_id": p["id"]})
    b.ok("POST", f"/api/posts/{p['id']}/like")
    b.ok("POST", f"/api/posts/{p['id']}/renetwork")
    got = a.ok("GET", f"/api/posts/{p['id']}")
    post = got.get("post", got)
    assert post["likes"] == 1
    ns = a.ok("GET", "/api/notifications")
    types = {n["type"] for n in ns}
    assert {"reply", "like", "renetwork"} <= types, types
    one = ns[0]["id"]
    a.ok("POST", f"/api/notifications/{one}/read")
    assert next(n for n in a.ok("GET", "/api/notifications") if n["id"] == one)["read"]
    a.ok("POST", "/api/notifications/read")
    assert a.ok("GET", "/api/me")["unread_notifications"] == 0
    e = a.ok("PUT", f"/api/posts/{p['id']}", json={"body": "edited"}); assert "edited" in str(e)
    r = b.delete(f"/api/posts/{p['id']}"); assert r.status_code == 403


def test_networks_join_request_approve_reject_private_content(mk, anon):
    f, x, y, z = mk(), mk(), mk(), mk()
    pub = net(f, "Public Club"); priv = net(f, "Secret Desk", private=True)
    assert x.ok("POST", f"/api/networks/{pub['slug']}/join")["status"] == "active"
    f.ok("POST", "/api/posts", json={"body": "members only secret", "network_id": priv["id"]})
    for u in (x, y): assert u.ok("POST", f"/api/networks/{priv['slug']}/join")["status"] == "pending"
    # private content protected for pending, outsider and anonymous
    for u in (x, y, z, anon):
        assert u.get(f"/api/networks/{priv['slug']}/feed").status_code in (401, 403)
        assert "members only secret" not in u.get("/api/feed?tab=discover").text
        assert "members only secret" not in u.get("/api/search?q=secret").text
    assert z.get(f"/api/networks/{priv['slug']}/members").status_code == 403
    assert x.post(f"/api/networks/{priv['slug']}/members/{y.id}", json={"action": "approve"}).status_code == 403  # non-admin
    f.ok("POST", f"/api/networks/{priv['slug']}/members/{x.id}", json={"action": "approve"})
    f.ok("POST", f"/api/networks/{priv['slug']}/members/{y.id}", json={"action": "reject"})
    assert "members only secret" in x.get(f"/api/networks/{priv['slug']}/feed").text
    assert y.get(f"/api/networks/{priv['slug']}/feed").status_code == 403
    assert any(n["type"] == "join_decision" for n in y.ok("GET", "/api/notifications"))
    # admin permissions are configurable
    f.ok("POST", f"/api/networks/{priv['slug']}/members/{x.id}", json={"action": "make_admin"})
    f.ok("PUT", f"/api/networks/{priv['slug']}/members/{x.id}/perms", json={"perm_members": False})
    assert x.post(f"/api/networks/{priv['slug']}/members/{z.id}", json={"action": "remove"}).status_code in (403, 404)
    assert x.put(f"/api/networks/{priv['slug']}", json={"description": "hack"}).status_code == 403


def test_connections_and_sharing_permissions(mk):
    fa, fb, ma, mb, out = mk(), mk(), mk(), mk(), mk()
    A = net(fa, "Net Alpha"); B = net(fb, "Net Beta")
    ma.ok("POST", f"/api/networks/{A['slug']}/join"); mb.ok("POST", f"/api/networks/{B['slug']}/join")
    fa.ok("POST", "/api/posts", json={"body": "A announcement shared", "network_id": A["id"], "kind": "announcement"})
    fa.ok("POST", "/api/posts", json={"body": "A normal post not shared", "network_id": A["id"]})
    c = fa.ok("POST", f"/api/networks/{A['slug']}/connections", json={"target_slug": B["slug"], "permissions": {"share_announcements": True}})
    assert ma.post(f"/api/connections/{c['id']}/decide", json={"action": "approve"}).status_code == 403
    assert fa.post(f"/api/connections/{c['id']}/decide", json={"action": "approve"}).status_code == 403  # requester can't approve
    fb.ok("POST", f"/api/connections/{c['id']}/decide", json={"action": "approve", "permissions": {}})
    # B members see A's announcement (A shares announcements), but not A's normal post
    shared = mb.get(f"/api/networks/{B['slug']}/feed?kind=connected").text
    assert "A announcement shared" in shared and "A normal post not shared" not in shared
    assert "A announcement shared" in mb.get("/api/feed?tab=network").text
    # A members get nothing from B (B granted nothing)
    fb.ok("POST", "/api/posts", json={"body": "B announcement private", "network_id": B["id"], "kind": "announcement"})
    assert "B announcement private" not in ma.get(f"/api/networks/{A['slug']}/feed?kind=connected").text
    # outsider cannot read connected feed
    assert out.get(f"/api/networks/{B['slug']}/feed?kind=connected").status_code == 403
    # revoking the permission removes access (backend-enforced)
    fa.ok("PUT", f"/api/connections/{c['id']}/permissions", json={"share_announcements": False})
    assert "A announcement shared" not in mb.get(f"/api/networks/{B['slug']}/feed?kind=connected").text
    # rejected connection
    C_ = net(out, "Net Gamma")
    c2 = out.ok("POST", f"/api/networks/{C_['slug']}/connections", json={"target_slug": A["slug"]})
    assert fa.ok("POST", f"/api/connections/{c2['id']}/decide", json={"action": "reject"})["status"] == "rejected"


def test_private_network_opportunity_hidden_and_sharing(mk):
    f, outsider = mk(), mk()
    P = net(f, "Hidden Opps", private=True)
    o = f.ok("POST", "/api/opportunities", json={"category": "Marketing campaigns", "title": "Secret gig", "description": "x" * 30, "compensation": "1 SOL", "network_id": P["id"]})
    assert outsider.get(f"/api/opportunities/{o['id']}").status_code in (403, 404)
    assert "Secret gig" not in outsider.get("/api/opportunities").text


def test_opportunity_apply_decide_contact(mk):
    f, a, b = mk(), mk(), mk()
    cats = f.ok("GET", "/api/meta")["opportunity_categories"]
    bad = f.post("/api/opportunities", json={"category": cats[0], "title": "No pay listed", "description": "x" * 30})
    assert bad.status_code == 400  # compensation or negotiable required
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert f.post("/api/opportunities", json={"category": cats[0], "title": "Past deadline", "description": "x" * 30, "negotiable": True, "deadline": past}).status_code == 400
    dl = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    o = f.ok("POST", "/api/opportunities", json={"category": cats[0], "title": "Need a KOL", "description": "Looking for a KOL partner for launch", "requirements": "10k followers", "compensation": "2 SOL", "deadline": dl})
    assert a.post(f"/api/opportunities/{o['id']}/apply", json={"kind": "application", "message": "short"}).status_code == 400
    a.ok("POST", f"/api/opportunities/{o['id']}/apply", json={"kind": "application", "message": "I have run many KOL campaigns before."})
    b.ok("POST", f"/api/opportunities/{o['id']}/apply", json={"kind": "interest"})
    assert a.post(f"/api/opportunities/{o['id']}/apply", json={"kind": "interest"}).status_code in (400, 409)
    full = f.ok("GET", f"/api/opportunities/{o['id']}")
    assert len(full["applications"]) == 2 and "applications" not in a.ok("GET", f"/api/opportunities/{o['id']}") or a.ok("GET", f"/api/opportunities/{o['id']}").get("applications") is None
    apps = {x["applicant"]["username"]: x["id"] for x in full["applications"]}
    assert a.post(f"/api/applications/{apps[b.username]}", json={"status": "accepted"}).status_code == 403
    f.ok("POST", f"/api/applications/{apps[a.username]}", json={"status": "accepted"})
    f.ok("POST", f"/api/applications/{apps[b.username]}", json={"status": "rejected"})
    f.ok("POST", f"/api/applications/{apps[a.username]}", json={"status": "completed"})
    assert any(n["type"] == "opportunity_decision" for n in a.ok("GET", "/api/notifications"))
    f.ok("POST", f"/api/messages/{a.username}", json={"body": "Let's start Monday"})  # contact applicant
    f.ok("POST", f"/api/opportunities/{o['id']}/status", json={"status": "filled"})
    assert a.ok("GET", f"/api/opportunities/{o['id']}")["status"] == "filled"
    assert "Need a KOL" in f.get(f"/api/opportunities?status=filled&q=KOL").text
    # collaboration shows on passport + endorsement allowed via collaboration
    a.ok("POST", f"/api/users/{f.username}/endorse", json={"category": "Collaboration"})
    assert a.post(f"/api/users/{f.username}/endorse", json={"category": "Collaboration"}).status_code == 409
    assert b.post(f"/api/users/{a.username}/endorse", json={"category": "Research"}).status_code == 403  # no shared history
    assert f.ok("GET", f"/api/users/{a.username}")["collaborations"]


def test_messages_unread_and_ws(mk):
    a, b, stranger = mk(), mk(), mk()
    assert stranger.post(f"/api/messages/{b.username}", json={"body": "cold spam"}).status_code == 403  # anti-spam
    b.ok("POST", f"/api/users/{a.username}/follow")
    with b.c.websocket_connect("/ws") as ws:
        a.ok("POST", f"/api/messages/{b.username}", json={"body": "gm"})
        got = ws.receive_json()
        while got["type"] != "dm": got = ws.receive_json()
        assert got["type"] == "dm" and got["message"]["body"] == "gm"
    assert b.ok("GET", "/api/me")["unread_messages"] == 1
    convos = b.ok("GET", "/api/messages"); assert convos[0]["unread"] == 1
    th = b.ok("GET", f"/api/messages/{a.username}"); assert th["messages"][0]["body"] == "gm"
    assert b.ok("GET", "/api/me")["unread_messages"] == 0
    b.ok("POST", f"/api/messages/{a.username}", json={"body": "gm back"})
    assert [m["body"] for m in a.ok("GET", f"/api/messages/{b.username}")["messages"]] == ["gm", "gm back"]
    b.ok("POST", f"/api/users/{a.username}/block")
    assert a.post(f"/api/messages/{b.username}", json={"body": "spam"}).status_code == 403


def test_network_chat_ws_members_only(mk):
    f, m, o = mk(), mk(), mk()
    N = net(f, "Chat Net"); m.ok("POST", f"/api/networks/{N['slug']}/join")
    assert o.post(f"/api/networks/{N['slug']}/chat", json={"body": "hi"}).status_code == 403
    with m.c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join_network", "slug": N["slug"]}); assert ws.receive_json()["type"] == "joined"
        f.ok("POST", f"/api/networks/{N['slug']}/chat", json={"body": "hello room"})
        while True:
            x = ws.receive_json()
            if x["type"] == "chat": break
        assert x["message"]["body"] == "hello room"


def test_invites_expiry_and_limits(mk):
    f, a, b = mk(), mk(), mk()
    P = net(f, "Invite Only", private=True)
    inv = f.ok("POST", f"/api/networks/{P['slug']}/invites", json={"max_uses": 1, "days": 1})
    code = inv["code"]
    assert a.ok("POST", f"/api/networks/{P['slug']}/join?invite={code}")["status"] == "active"
    assert b.post(f"/api/networks/{P['slug']}/join?invite={code}").status_code in (400, 403, 410)


def test_rankings_from_real_records(mk):
    f = mk(); N = net(f, "Ranked Net")
    r = f.ok("GET", "/api/rankings")
    keys = [c["key"] for c in r["categories"]]
    assert {"top", "growing", "active", "projects", "collaborators", "contributors", "endorsed", "research"} <= set(keys)
    assert all(c["metric"] and c["how"] for c in r["categories"])
    top = next(c for c in r["categories"] if c["key"] == "top")
    assert all(x["id"] != N["id"] for x in top["rows"])  # 1 member: not eligible
    for _ in range(3): mk_ = mk(); mk_.ok("POST", f"/api/networks/{N['slug']}/join")
    top = next(c for c in f.ok("GET", "/api/rankings")["categories"] if c["key"] == "top")
    assert any(x["id"] == N["id"] for x in top["rows"])


def test_search_and_pagination(mk):
    a = mk("searchy9")
    net(a, "Searchable Guild")
    for i in range(35):
        if i % 15 == 0: security._hits.clear()
        a.ok("POST", "/api/posts", json={"body": f"page post {i}"})
    p1 = a.ok("GET", "/api/feed?tab=network"); assert len(p1) == 30
    p2 = a.ok("GET", f"/api/feed?tab=network&before={p1[-1]['id']}"); assert len(p2) >= 5
    s = a.ok("GET", "/api/search?q=searchable")
    assert s["networks"] and a.ok("GET", "/api/search?q=searchy")["users"]


def test_verification_never_fake(mk):
    a = mk()
    v = a.ok("POST", "/api/verifications", json={"kind": "wallet"})
    p = a.ok("GET", f"/api/users/{a.username}")
    assert all(not x["verified"] for x in p["verification"].values())
    assert p["verification"]["wallet"]["status"] == "pending"
    assert a.post("/api/verifications", json={"kind": "trading"}).status_code == 422


def test_onboarding_suggestions(mk):
    f, a = mk(), mk()
    net(f, "Marketing Guild", typ="Marketing")
    me = a.ok("PUT", "/api/me/onboarding", json={"role": "Marketer", "interests": ["Marketing", "bogus"]})
    assert me["role"] == "Marketer" and me["interests"] == ["Marketing"]
    s = a.ok("GET", "/api/suggestions")
    assert any(n["name"] == "Marketing Guild" for n in s["networks"])
    assert isinstance(a.ok("GET", "/api/opportunities/suggested"), list)


def test_upload_validation(mk):
    a = mk()
    r = a.post("/api/upload", files={"file": ("x.png", b"not an image", "image/png")}); assert r.status_code == 400
    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6300010000050001" "0d0a2db40000000049454e44ae426082")
    r = a.post("/api/upload", files={"file": ("x.png", png, "image/png")}); assert r.status_code == 200, r.text


def test_weighted_endorsements_and_top_callers(mk):
    f, a = mk(), mk()
    N = net(f, "Weight Net"); a.ok("POST", f"/api/networks/{N['slug']}/join")
    a.ok("POST", f"/api/users/{f.username}/endorse", json={"category": "Leadership"})
    r = f.ok("GET", "/api/rankings")
    cats = {c["key"]: c for c in r["categories"]}
    assert "callers" in cats and "DexScreener" in cats["callers"]["how"]
    row = next(u for u in cats["endorsed"]["rows"] if u["username"] == f.username)
    assert 0.5 <= row["endorsements_weighted"] < 1.0  # new endorser (low XP) counts for less than 1
    assert "weighted" in cats["endorsed"]["how"]


def test_call_entry_price_is_server_side(mk, monkeypatch):
    from app import dex
    a = mk()
    addr = "So11111111111111111111111111111111111111112"
    monkeypatch.setattr(dex, "fetch_token", lambda x: {"address": addr, "symbol": "WSOL", "name": "Wrapped SOL", "price": 150.0, "mcap": 1e9, "liquidity": 1e7, "change24h": 0, "url": ""})
    c = a.ok("POST", "/api/calls", json={"token_address": addr, "notes": "test", "entry_price": 0.000001})
    body = c.get("call", c)
    assert body["entry_price"] == 150.0  # client-supplied price ignored
