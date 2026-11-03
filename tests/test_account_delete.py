from app.db import SessionLocal
from app.models import User, Network, Post, Message, Membership, Notification, Opportunity
from sqlalchemy import select, func


def count(M, *w):
    with SessionLocal() as db: return db.scalar(select(func.count()).select_from(M).where(*w))


def test_delete_account_requires_confirmation(mk):
    a = mk()
    a.ok("DELETE", "/api/me", 400, json={"confirm": "someone_else", "password": "password123"})
    a.ok("DELETE", "/api/me", 403, json={"confirm": a.username, "password": "wrongpass1"})
    assert a.ok("GET", "/api/me")["username"] == a.username


def test_delete_account_needs_csrf_header(mk):
    a = mk(); a.c.headers.pop("x-csrf")
    assert a.c.request("DELETE", "/api/me", json={"confirm": a.username, "password": "password123"}).status_code == 403


def test_delete_account_removes_user_data(mk):
    a, b = mk(), mk()
    n = a.ok("POST", "/api/networks", json={"name": "Del Net", "type": "Project", "description": "x"})
    inv = a.ok("POST", f"/api/networks/{n['slug']}/invites", json={"username": b.username})
    b.ok("POST", f"/api/networks/{n['slug']}/join", params={"invite": inv["code"]})
    b.ok("POST", f"/api/networks/{n['slug']}/chat", json={"body": "hi"})
    a.ok("POST", "/api/posts", json={"body": "a post"})
    pb = b.ok("POST", "/api/posts", json={"body": "b post"})
    a.ok("POST", f"/api/posts/{pb['id']}/like")
    a.ok("POST", f"/api/messages/{b.username}", json={"body": "dm"})
    o = a.ok("POST", "/api/opportunities", json={"category": "Project launches", "title": "Some opp", "description": "A long enough description here.", "negotiable": True})
    b.ok("POST", f"/api/opportunities/{o['id']}/apply", json={"message": "interested in this one"})

    # founder can't delete while the Network has other members
    r = a.c.request("DELETE", "/api/me", json={"confirm": a.username, "password": "password123"})
    assert r.status_code == 409 and "Del Net" in r.json()["detail"]

    b.ok("DELETE", "/api/me", json={"confirm": "@" + b.username.upper(), "password": "password123"})
    assert b.ok("GET", "/api/me") is None
    assert count(User, User.id == b.id) == 0 and count(Post, Post.author_id == b.id) == 0
    assert count(Membership, Membership.user_id == b.id) == 0 and count(Message, Message.recipient_id == b.id) == 0
    a.ok("GET", f"/api/users/{b.username}", 404)

    a.ok("DELETE", "/api/me", json={"confirm": a.username, "password": "password123"})
    assert count(User, User.id == a.id) == 0 and count(Network, Network.id == n["id"]) == 0
    assert count(Opportunity, Opportunity.creator_id == a.id) == 0 and count(Notification, Notification.user_id == a.id) == 0
    # the username is free again and the old session is dead
    assert a.c.get("/api/me").json() is None
    mk(a.username)
