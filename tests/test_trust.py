"""Moderation, suspension, new-account limits, media storage, wallet/dev-wallet/metadata/domain verification,
CTO claims (mocked chain), activity picker and rankings snapshots."""
import base64, os
import pytest
from nacl.signing import SigningKey
from app import chain, trust, security
from app.db import SessionLocal
from app.models import User
from app.services import utcnow
from datetime import timedelta

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


def kp():
    k = SigningKey.generate()
    return k, chain.b58encode(bytes(k.verify_key))


def addr():
    return kp()[1]


def sign(c, k, a, purpose, subject=""):
    n = c.ok("POST", "/api/verify/nonce", json={"purpose": purpose, "address": a, "subject": subject})
    assert "not a transaction" in n["message"]
    return {"nonce": n["nonce"], "signature": chain.b58encode(k.sign(n["message"].encode()).signature)}, n["message"]


def project(c, name):
    return c.ok("POST", "/api/networks", json={"name": name, "type": "Project", "is_private": False, "description": "project"})


def age(username, hours):
    with SessionLocal() as db:
        u = db.query(User).filter(User.username == username).one()
        u.created_at = utcnow() - timedelta(hours=hours); db.commit()


@pytest.fixture(autouse=True)
def no_ticker(monkeypatch):
    monkeypatch.setattr(trust, "ticker_of", lambda m: "TEST")


# ---------------------------------------------------------------- signatures / wallet
def test_signature_helpers():
    k, a = kp()
    sig = k.sign(b"hi").signature
    assert chain.verify_signature(a, "hi", chain.b58encode(sig))
    assert chain.verify_signature(a, "hi", base64.b64encode(sig).decode())
    assert not chain.verify_signature(a, "hi!", chain.b58encode(sig))
    assert not chain.verify_signature(addr(), "hi", chain.b58encode(sig))
    assert chain.b58decode(chain.b58encode(b"\0\0abc")) == b"\0\0abc"


def test_wallet_ownership_verification(mk):
    a, b = mk(), mk()
    k, w = kp()
    body, msg = sign(a, k, w, "wallet")
    bad = dict(body, signature=chain.b58encode(SigningKey.generate().sign(msg.encode()).signature))
    assert a.post("/api/verify/wallet", json=bad).status_code == 400
    assert a.post("/api/verify/wallet", json=body).status_code == 400  # nonce burned by the failed attempt
    body, _ = sign(a, k, w, "wallet")
    r = a.ok("POST", "/api/verify/wallet", json=body)
    assert r["label"] == "Wallet ownership verified"
    assert a.post("/api/verify/wallet", json=body).status_code == 400  # replay
    p = a.ok("GET", f"/api/users/{a.username}")["verification"]["wallet"]
    assert p["verified"] and "not trustworthiness" in p["detail"]
    body, _ = sign(b, k, w, "wallet")  # another account can't claim the same wallet
    assert b.post("/api/verify/wallet", json=body).status_code == 409
    assert not b.ok("GET", f"/api/users/{b.username}")["verification"]["wallet"]["verified"]
    # someone else's nonce can't be used
    body, _ = sign(a, k, w, "wallet")
    assert b.post("/api/verify/wallet", json=body).status_code == 400


# ---------------------------------------------------------------- domain
def test_domain_verification_mocked(mk, monkeypatch):
    f, x = mk(), mk()
    n = project(f, "Domain Proj")
    assert x.post(f"/api/networks/{n['slug']}/verify/domain", json={"domain": "example.com"}).status_code == 403
    assert f.post(f"/api/networks/{n['slug']}/verify/domain", json={"domain": "127.0.0.1"}).status_code == 400
    s = f.ok("POST", f"/api/networks/{n['slug']}/verify/domain", json={"domain": "https://Example.com/path"})
    assert s["domain"] == "example.com"
    monkeypatch.setattr(trust, "fetch_txt", lambda d: ["unrelated"])
    monkeypatch.setattr(trust, "fetch_well_known", lambda d: "")
    assert not f.ok("POST", f"/api/networks/{n['slug']}/verify/domain/check")["verified"]
    monkeypatch.setattr(trust, "fetch_well_known", lambda d: s["file_content"] + "\n")
    r = f.ok("POST", f"/api/networks/{n['slug']}/verify/domain/check")
    assert r["verified"] and r["method"] == "/.well-known/network-verify.txt"
    v = f.ok("GET", f"/api/networks/{n['slug']}")
    tt = f.ok("GET", f"/api/networks/{n['slug']}/token-trust")
    assert tt["domain"]["detail"] == "Project domain verified (example.com)"


# ---------------------------------------------------------------- dev wallet + metadata
def test_devwallet_verification_mocked(mk, monkeypatch):
    f, g = mk(), mk()
    n, n2 = project(f, "Dev Proj"), project(g, "Other Proj")
    k, w = kp(); mint = addr()
    monkeypatch.setattr(chain, "pump_creator", lambda m: {"creator": w, "curve": addr(), "complete": False, "method": "pump.fun bonding-curve creator field"})
    body, _ = sign(f, k, w, "devwallet", mint)
    r = f.ok("POST", f"/api/networks/{n['slug']}/verify/devwallet", json=body)
    assert r["verified"] and r["method"] == "pump.fun bonding-curve creator field"
    assert "Dev wallet verified: signed by the creator of $TEST (method: pump.fun bonding-curve creator field)" in r["detail"]
    assert "not that the project is safe" in r["detail"]
    # one token belongs to one Network
    body, _ = sign(g, k, w, "devwallet", mint)
    assert g.post(f"/api/networks/{n2['slug']}/verify/devwallet", json=body).status_code == 409
    # a non-creator wallet: earliest-tx fallback also says no -> Not verified with reason
    k2, w2 = kp(); mint2 = addr()
    monkeypatch.setattr(chain, "creation_tx", lambda m: {"creator": w, "method": "fee payer of the mint's creation transaction"})
    monkeypatch.setattr(chain, "helius_asset", lambda m: None)
    monkeypatch.setattr(chain, "metadata_authority", lambda m: None)
    body, _ = sign(g, k2, w2, "devwallet", mint2)
    r = g.ok("POST", f"/api/networks/{n2['slug']}/verify/devwallet", json=body)
    assert not r["verified"] and r["detail"].startswith("Not verified:")
    # earliest-tx method matches when pump says someone else
    body, _ = sign(g, k, w, "devwallet", mint2)
    monkeypatch.setattr(chain, "pump_creator", lambda m: None)
    r = g.ok("POST", f"/api/networks/{n2['slug']}/verify/devwallet", json=body)
    assert r["verified"] and "creation transaction" in r["method"]
    # recheck after the creator changes (e.g. data was wrong) lapses it
    monkeypatch.setattr(chain, "creation_tx", lambda m: {"incomplete": True, "reason": "History too long"})
    assert not g.ok("POST", f"/api/networks/{n2['slug']}/verify/devwallet/recheck")["verified"]
    # Creator wallet balance shown read-only
    monkeypatch.setattr(chain, "token_balance", lambda o, m: {"ui": 0.0, "raw": 0, "accounts": []})
    monkeypatch.setattr(chain, "token_supply", lambda m: {"ui": 1e9, "raw": 10**15, "decimals": 6})
    monkeypatch.setattr(chain, "dev_token_flows", lambda o, m: {"events": [], "complete": True, "checked_txs": 3, "acquired": 100.0, "sold": 60.0,
        "transferred": 40.0, "burned_or_unclassified": 0, "venues": ["PumpSwap"], "destinations": [{"wallet": w2, "amount": 40.0}]})
    tt = f.ok("GET", f"/api/networks/{n['slug']}/token-trust")
    ev = tt["dev_evidence"]
    assert tt["devwallet"]["status"] == "verified" and ev["summary"].startswith("Original dev wallet holds 0.00%")
    assert "sold 60 via PumpSwap" in ev["summary"] and "transferred 40" in ev["summary"] and "not a sale" in ev["summary"]
    assert ev["flows"]["destinations"][0]["wallet"] == w2


def test_metadata_authority(mk, monkeypatch):
    f = mk(); n = project(f, "Meta Proj")
    k, w = kp(); mint = addr()
    monkeypatch.setattr(chain, "metadata_authority", lambda m: {"update_authority": addr()})
    body, _ = sign(f, k, w, "metadata", mint)
    assert not f.ok("POST", f"/api/networks/{n['slug']}/verify/metadata", json=body)["verified"]
    monkeypatch.setattr(chain, "metadata_authority", lambda m: {"update_authority": w})
    body, _ = sign(f, k, w, "metadata", mint)
    r = f.ok("POST", f"/api/networks/{n['slug']}/verify/metadata", json=body)
    assert r["verified"] and r["detail"].startswith("Metadata authority verified")


# ---------------------------------------------------------------- CTO
class FakeChain:
    def __init__(self, mp, supply=1_000_000):
        self.bal, self.supply, self.pool, self.dev = {}, supply, addr(), addr()
        mp.setattr(chain, "token_supply", lambda m: {"ui": self.supply, "raw": self.supply, "decimals": 0})
        mp.setattr(chain, "token_balance", lambda o, m: {"ui": float(self.bal.get(o, 0)), "raw": self.bal.get(o, 0), "accounts": [f"acct-{o}"] if self.bal.get(o) else []})
        mp.setattr(chain, "pump_creator", lambda m: {"creator": self.dev, "curve": addr(), "complete": True, "method": "pump"})
        mp.setattr(chain, "largest_holders", lambda m: [{"account": f"acct-{self.pool}", "owner": self.pool, "raw": self.bal.get(self.pool, 0), "ui": 0}])
        mp.setattr(chain, "is_program_owned_address", lambda a: a == self.pool)
        mp.setattr(chain, "wallet_history", lambda w: {"first_seen": None, "first_funder": "", "old": True})
        mp.setattr(chain, "last_activity", lambda o, m: None)


def back(c, cid, k, w):
    body, msg = sign(c, k, w, "cto_back", str(cid))
    assert msg.startswith("NETWORK: I support @") and "as the community team for" in msg
    return c.ok("POST", f"/api/cto/{cid}/back", json=body)


def test_cto_claim_threshold_lapse_double_count_competing(mk, monkeypatch):
    monkeypatch.setenv("CTO_MIN_BACKERS", "3"); monkeypatch.setenv("CTO_MIN_PCT", "10")
    fc = FakeChain(monkeypatch)
    fc.bal[fc.pool] = 500_000; fc.bal[fc.dev] = 100_000  # circulating = 400,000
    f, g = mk(), mk()
    mint = addr()
    a = f.ok("POST", f"/api/networks/{project(f, 'CTO One')['slug']}/cto", json={"mint": mint})
    b = g.ok("POST", f"/api/networks/{project(g, 'CTO Two')['slug']}/cto", json={"mint": mint})
    holders = [mk() for _ in range(4)]
    keys = [kp() for _ in range(4)]
    for (k, w), amt in zip(keys, [20_000, 20_000, 20_000, 1]): fc.bal[w] = amt
    for h, (k, w) in zip(holders[:3], keys[:3]): back(h, a["id"], k, w)
    c = f.ok("POST", f"/api/cto/{a['id']}/recheck")
    assert c["verified"] and c["backers_count"] == 3 and abs(c["backed_pct"] - 15.0) < 1e-6  # 60k / 400k circulating
    assert c["label"].startswith("Community takeover: backed by 3 holder wallets holding 15.00% of supply (checked ")
    assert len(c["result"]["backers"]) == 3 and "…" in c["result"]["backers"][0]["wallet"]
    # double counting: same wallet backing again (even from a different account) does not add
    back(holders[3], a["id"], *keys[0])
    c = f.ok("POST", f"/api/cto/{a['id']}/recheck"); assert c["backers_count"] == 3
    # dev wallet and pool can't back
    kd = SigningKey.generate(); fc.dev = chain.b58encode(bytes(kd.verify_key)); fc.bal[fc.dev] = 100_000
    back(holders[3], a["id"], kd, fc.dev)
    c = f.ok("POST", f"/api/cto/{a['id']}/recheck")
    assert c["backers_count"] == 3 and any("excluded" in r["note"] for r in c["result"]["backers"])
    # competing claim: a wallet switches to claim B
    r = back(holders[2], b["id"], *keys[2]); assert r["switched"]
    c = f.ok("POST", f"/api/cto/{a['id']}/recheck")
    assert not c["verified"] and c["label"] == "CTO claim, not enough holder support"
    roles = {x["id"]: x["role"] for x in c["claims"]}
    assert roles[a["id"]] == "leading claim" and roles[b["id"]] == "competing claim"
    # live balances: a backer selling drops support (lapse); buying back restores
    back(holders[3], a["id"], *keys[3]); fc.bal[keys[3][1]] = 40_000
    c = f.ok("POST", f"/api/cto/{a['id']}/recheck"); assert c["verified"]
    fc.bal[keys[0][1]] = 0
    c = f.ok("POST", f"/api/cto/{a['id']}/recheck"); assert not c["verified"]
    # public view, no login
    pub = security  # noqa
    assert f.ok("GET", f"/api/cto/{a['id']}")["support_text"].endswith(mint)


def test_cto_new_wallet_downweighted_and_shared_funder(mk, monkeypatch):
    monkeypatch.setenv("CTO_MIN_BACKERS", "2"); monkeypatch.setenv("CTO_MIN_PCT", "10")
    fc = FakeChain(monkeypatch, supply=100_000)
    import time
    monkeypatch.setattr(chain, "wallet_history", lambda w: {"first_seen": time.time() - 3600, "first_funder": "FUNDER", "old": False})
    f = mk(); mint = addr()
    a = f.ok("POST", f"/api/networks/{project(f, 'CTO Fresh')['slug']}/cto", json={"mint": mint})
    for _ in range(2):
        k, w = kp(); fc.bal[w] = 10_000; back(mk(), a["id"], k, w)
    c = f.ok("POST", f"/api/cto/{a['id']}/recheck")
    assert c["backers_count"] == 0 and abs(c["backed_pct"] - 10.0) < 1e-6 and not c["verified"]  # 20k at 50% weight
    assert c["result"]["shared_funder_pct"] == 100.0


# ---------------------------------------------------------------- moderation
def test_reports_queues_actions_suspension(mk):
    adm = mk("padmin")  # ADMIN_USERNAMES=padmin in conftest
    f, mod, bad, rep = mk(), mk(), mk(), mk()
    n = f.ok("POST", "/api/networks", json={"name": "Mod Net", "type": "Trading", "is_private": False, "description": "x"})
    for u in (mod, bad, rep): u.ok("POST", f"/api/networks/{n['slug']}/join")
    f.ok("POST", f"/api/networks/{n['slug']}/members/{mod.id}", json={"action": "make_admin"})
    f.ok("PUT", f"/api/networks/{n['slug']}/members/{mod.id}/perms", json={"perm_moderate": True})
    p = bad.ok("POST", "/api/posts", json={"body": "spam spam", "network_id": n["id"]})
    rep.ok("POST", "/api/reports", json={"target_type": "post", "target": str(p["id"]), "reason": "spam"})
    assert rep.post("/api/reports", json={"target_type": "post", "target": str(p["id"]), "reason": "again"}).status_code == 409
    rep.ok("POST", "/api/reports", json={"target_type": "user", "target": bad.username, "reason": "spammer"})
    rep.ok("POST", "/api/reports", json={"target_type": "network", "target": n["slug"], "reason": "scam network"})
    assert rep.post("/api/reports", json={"target_type": "user", "target": rep.username, "reason": "myself"}).status_code == 400
    # queues
    assert rep.get(f"/api/moderation/queue?network={n['slug']}").status_code == 403
    assert mod.get("/api/moderation/queue").status_code == 403
    q = mod.ok("GET", f"/api/moderation/queue?network={n['slug']}")
    assert [r["target_type"] for r in q] == ["post"]
    pq = adm.ok("GET", "/api/moderation/queue"); assert {r["target_type"] for r in pq} == {"post", "user", "network"}
    assert adm.ok("GET", "/api/me")["is_platform_admin"] and not mod.ok("GET", "/api/me")["is_platform_admin"]
    # network mod hides the post; can't suspend
    assert mod.post(f"/api/reports/{q[0]['id']}/resolve", json={"action": "suspend_user"}).status_code == 403
    mod.ok("POST", f"/api/reports/{q[0]['id']}/resolve", json={"action": "hide_post", "note": "spam"})
    assert rep.get(f"/api/posts/{p['id']}").status_code == 404  # hidden from everyone else
    assert bad.get(f"/api/posts/{p['id']}").status_code == 200  # still visible to its author
    notes = rep.ok("GET", "/api/notifications")
    notes = notes["items"] if isinstance(notes, dict) else notes
    assert any(x["type"] == "report_resolved" for x in notes)
    # platform admin suspends the user temporarily
    ur = [r for r in pq if r["target_type"] == "user"][0]
    adm.ok("POST", f"/api/reports/{ur['id']}/resolve", json={"action": "suspend_user", "suspend_hours": 24, "note": "spam"})
    assert bad.ok("GET", "/api/me")["suspended"]
    assert bad.post("/api/posts", json={"body": "hello"}).status_code == 403
    assert bad.post(f"/api/messages/{rep.username}", json={"body": "hi"}).status_code == 403
    assert bad.post(f"/api/users/{rep.username}/endorse", json={"category": "Research"}).status_code == 403
    adm.ok("POST", f"/api/admin/users/{bad.username}/unsuspend")
    bad.ok("POST", "/api/posts", json={"body": "back"})
    # resolved reports leave the open queue; audit log is written
    assert all(r["id"] != ur["id"] for r in adm.ok("GET", "/api/moderation/queue"))
    from app.models import AuditLog
    with SessionLocal() as db:
        acts = {a.action for a in db.query(AuditLog).all()}
    assert {"moderation.hide_post", "moderation.suspend_user", "moderation.unsuspend"} <= acts


def test_new_account_limits(mk):
    a = mk()
    for i in range(5): a.ok("POST", "/api/posts", json={"body": f"post {i}"})
    r = a.post("/api/posts", json={"body": "six"})
    assert r.status_code == 429 and "New accounts" in r.json()["detail"]
    b = mk(); age(b.username, 48)
    for i in range(6): b.ok("POST", "/api/posts", json={"body": f"post {i}"})
    assert a.ok("GET", "/api/me")["new_account"] and not b.ok("GET", "/api/me")["new_account"]


def test_rate_limit_is_db_backed(mk):
    from app.models import RateHit
    a = mk(); a.ok("POST", "/api/posts", json={"body": "x"})
    with SessionLocal() as db:
        assert db.query(RateHit).filter(RateHit.key.like("post:%")).count() >= 1


# ---------------------------------------------------------------- media storage
def test_db_media_storage(mk, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "db")
    a = mk()
    r = a.ok("POST", "/api/upload", files={"file": ("a.png", PNG, "image/png")})
    assert r["url"].startswith("/media/") and r["backend"] == "db"
    m = a.get(r["url"])
    assert m.status_code == 200 and m.content == PNG and m.headers["content-type"] == "image/png"
    assert "immutable" in m.headers["cache-control"] and m.headers["x-content-type-options"] == "nosniff"
    big = PNG + b"\0" * (2 * 1024 * 1024)
    assert a.post("/api/upload", files={"file": ("b.png", big, "image/png")}).status_code == 400
    assert a.post("/api/upload", files={"file": ("c.png", b"notpng", "image/png")}).status_code == 400
    assert a.get("/media/nope.png").status_code == 404


def test_local_upload_migration(mk, monkeypatch, tmp_path):
    from app import storage
    from app.models import Media
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    a = mk()
    (tmp_path / "abc123.png").write_bytes(PNG)
    with SessionLocal() as db:
        u = db.get(User, a.id); u.avatar_url = "/uploads/abc123.png"; db.commit()
        assert storage.migrate_local_to_db(db) >= 1
        assert db.get(User, a.id).avatar_url == "/media/abc123.png"
        assert db.query(Media).filter(Media.key == "abc123.png").one().data == PNG
        assert storage.migrate_local_to_db(db) == 0  # idempotent
    assert a.get("/media/abc123.png").content == PNG


# ---------------------------------------------------------------- activity picker
def test_activity_picker_enforced(mk):
    fa, fb, mem = mk(), mk(), mk()
    A = fa.ok("POST", "/api/networks", json={"name": "Act A", "type": "Trading", "is_private": False, "description": "x"})
    B = fb.ok("POST", "/api/networks", json={"name": "Act B", "type": "Trading", "is_private": False, "description": "x"})
    c = fa.ok("POST", f"/api/networks/{A['slug']}/connections", json={"target_slug": B["slug"],
              "permissions": {"activity_types": ["new_members", "bogus"]}})
    fb.ok("POST", f"/api/connections/{c['id']}/decide", json={"action": "approve", "permissions": {"activity_types": ["events"]}})
    mem.ok("POST", f"/api/networks/{A['slug']}/join")  # A: new_members (shared)
    fa.ok("POST", f"/api/networks/{A['slug']}/events", json={"title": "AMA", "starts_at": (utcnow() + timedelta(days=1)).isoformat(), "is_public": True})  # A: events (not shared)
    types = {x["type"] for x in fb.ok("GET", "/api/activity/connected")}
    assert types == {"new_members"}
    r = fa.ok("PUT", f"/api/connections/{c['id']}/permissions", json={"activity_types": ["events"]})
    assert r["we_share"]["activity_types"] == ["events"]
    assert {x["type"] for x in fb.ok("GET", "/api/activity/connected")} == {"events"}
    assert mem.put(f"/api/connections/{c['id']}/permissions", json={"activity_types": ["new_members"]}).status_code == 403
    assert {x["type"] for x in fa.ok("GET", "/api/activity/connected")} == set()  # B shares events, B has none yet


# ---------------------------------------------------------------- rankings snapshot
def test_rankings_snapshot(mk, monkeypatch):
    monkeypatch.setenv("RANKINGS_TTL", "300")
    a = mk()
    r1 = a.ok("GET", "/api/rankings?refresh=true")
    r2 = a.ok("GET", "/api/rankings")
    assert r1["computed_at"] == r2["computed_at"] and r2["ttl_seconds"] == 300
    monkeypatch.setenv("RANKINGS_TTL", "0")
    assert a.ok("GET", "/api/rankings")["computed_at"] != r1["computed_at"]


# ---------------------------------------------------------------- creation tx / flows parsing (synthetic transactions)
def _tb(owner, mint, amount, idx=0):
    return {"accountIndex": idx, "mint": mint, "owner": owner, "uiTokenAmount": {"amount": str(amount), "decimals": 6}}


def _tx(sig, programs, pre, post, keys=None, ixs=None):
    return {"blockTime": 1700000000, "meta": {"err": None, "preTokenBalances": pre, "postTokenBalances": post,
            "innerInstructions": [{"instructions": [{"programId": p} for p in programs[1:]]}]},
            "transaction": {"signatures": [sig], "message": {"accountKeys": [{"pubkey": k} for k in (keys or [])],
                            "instructions": ixs or [{"programId": programs[0]}]}}}


def test_classify_sold_transferred_burned():
    dev, other, mint = addr(), addr(), addr()
    sold = chain.classify_flow(_tx("s1", ["ComputeBudget111111111111111111111111111111", "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"],
                                   [_tb(dev, mint, 5_000_000)], [_tb(dev, mint, 0)]), dev, mint)
    assert sold["kind"] == "sold" and sold["venue"] == "PumpSwap" and sold["amount"] == 5
    jup = chain.classify_flow(_tx("s2", ["JUP6LkbZbjS1jKKwapdHNy74zcZ3tQUs4ZMJXhkDPXo"], [_tb(dev, mint, 1_000_000)], [_tb(dev, mint, 0)]), dev, mint)
    assert jup["kind"] == "sold" and jup["venue"] == "Jupiter"
    tr = chain.classify_flow(_tx("t1", [chain.TOKEN_PROGRAM], [_tb(dev, mint, 3_000_000), _tb(other, mint, 0, 1)],
                                 [_tb(dev, mint, 1_000_000), _tb(other, mint, 2_000_000, 1)]), dev, mint)
    assert tr["kind"] == "transferred" and tr["to"] == [other] and tr["amount"] == 2
    burn = chain.classify_flow(_tx("b1", [chain.TOKEN_PROGRAM], [_tb(dev, mint, 1_000_000)], [_tb(dev, mint, 0)]), dev, mint)
    assert burn["kind"] == "burned_or_unclassified"
    buy = chain.classify_flow(_tx("a1", [chain.PUMP_PROGRAM], [], [_tb(dev, mint, 7_000_000)]), dev, mint)
    assert buy["kind"] == "acquired"
    failed = _tx("f1", [chain.PUMP_PROGRAM], [_tb(dev, mint, 1)], [_tb(dev, mint, 0)]); failed["meta"]["err"] = {"x": 1}
    assert chain.classify_flow(failed, dev, mint) is None


def test_creation_tx_pump_create_and_bundles(monkeypatch):
    mint, creator, bundler = addr(), addr(), addr()
    def borsh(s): return len(s).to_bytes(4, "little") + s.encode()
    data = bytes.fromhex("d6904cec5f8b31b4") + borsh("Coin") + borsh("CN") + borsh("https://x") + chain.b58decode(creator)
    # bundled launch: fee payer is a bundler, several signers, but the create instruction names the creator
    tx = _tx("c1", [chain.PUMP_PROGRAM], [], [], keys=[bundler, creator, mint],
             ixs=[{"programId": chain.PUMP_PROGRAM, "data": chain.b58encode(data), "accounts": [mint, addr()]}])
    monkeypatch.setattr(chain, "oldest_signature", lambda a, max_pages=None: {"signature": "c1", "block_time": 1, "how": "test"})
    monkeypatch.setattr(chain, "get_tx", lambda s: tx)
    r = chain.creation_tx(mint)
    assert r["creator"] == creator and "create instruction" in r["method"]
    # a non-pump token: fee payer only (never "any signer")
    mint2 = addr()
    tx2 = _tx("c2", ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"], [], [], keys=[creator, bundler, mint2])
    monkeypatch.setattr(chain, "get_tx", lambda s: tx2)
    r2 = chain.creation_tx(mint2)
    assert r2["creator"] == creator and r2["method"].startswith("fee payer")
    # cached persistently: works even after the RPC goes away
    monkeypatch.setattr(chain, "get_tx", lambda s: (_ for _ in ()).throw(RuntimeError("down")))
    assert chain.creation_tx(mint2)["creator"] == creator
    # busy token without Helius: "couldn't determine", never a guess, and not cached
    mint3 = addr()
    monkeypatch.setattr(chain, "oldest_signature", lambda a, max_pages=None: {"incomplete": True})
    r3 = chain.creation_tx(mint3)
    assert r3["incomplete"] and not r3.get("creator")
    monkeypatch.setattr(chain, "pump_creator", lambda m: None)
    monkeypatch.setattr(chain, "helius_asset", lambda m: None)
    monkeypatch.setattr(chain, "metadata_authority", lambda m: None)
    f = chain.find_creator(mint3, creator)
    assert not f["matched"] and f["reason"].startswith("Couldn't determine") and any("couldn't determine" in t for t in f["tried"])


def test_oldest_signature_paging(monkeypatch):
    monkeypatch.setattr(chain, "is_helius", lambda: False)
    pages = [[{"signature": f"s{p}-{i}", "blockTime": 1} for i in range(1000)] for p in range(3)] + [[{"signature": "first", "blockTime": 0}]]
    calls = []
    def rpc(method, params):
        calls.append(params[1].get("before")); return pages[len(calls) - 1]
    monkeypatch.setattr(chain, "rpc", rpc)
    assert chain.oldest_signature("A", max_pages=10)["signature"] == "first" and calls[1] == "s0-999"
    calls.clear()
    assert chain.oldest_signature("A", max_pages=2) == {"incomplete": True}
    # Helius oldest-first path is a single request
    monkeypatch.setattr(chain, "is_helius", lambda: True)
    monkeypatch.setattr(chain, "rpc", lambda m, p: {"data": [{"signature": "genesis", "blockTime": 5}]} if m == "getTransactionsForAddress" else None)
    assert chain.oldest_signature("A")["signature"] == "genesis"


# ---------------------------------------------------------------- Network-scoped bans
def test_network_ban_appeal_unban(mk):
    f, adm, mem, other = mk(), mk(), mk(), mk()
    n = f.ok("POST", "/api/networks", json={"name": "Ban Guild", "type": "Personal", "is_private": False, "description": "x"})
    s = n["slug"]
    for c in (adm, mem): c.ok("POST", f"/api/networks/{s}/join")
    f.ok("POST", f"/api/networks/{s}/members/{adm.id}", json={"action": "make_admin"})
    # plain members can't ban; admins without moderation permission can't either
    assert mem.post(f"/api/networks/{s}/bans", json={"username": other.username, "reason": "spam"}).status_code == 403
    f.ok("PUT", f"/api/networks/{s}/members/{adm.id}/perms", json={"perm_members": True, "perm_announce": False, "perm_connections": False,
                                                                   "perm_settings": False, "perm_moderate": False, "perm_opportunities": False})
    assert adm.post(f"/api/networks/{s}/bans", json={"username": mem.username, "reason": "spam"}).status_code == 403
    f.ok("PUT", f"/api/networks/{s}/members/{adm.id}/perms", json={"perm_members": True, "perm_announce": False, "perm_connections": False,
                                                                   "perm_settings": False, "perm_moderate": True, "perm_opportunities": False})
    assert adm.post(f"/api/networks/{s}/bans", json={"username": f.username, "reason": "coup"}).status_code == 403  # founder can't be banned
    b = adm.ok("POST", f"/api/networks/{s}/bans", json={"username": mem.username, "reason": "spamming links", "hours": 24})
    assert b["active"] and not b["indefinite"]
    # scoped: banned from this Network only
    assert mem.post("/api/posts", json={"body": "hi", "network_id": n["id"]}).status_code == 403
    assert mem.post(f"/api/networks/{s}/join").status_code == 403
    mem.ok("POST", "/api/posts", json={"body": "still allowed on my own profile"})
    assert mem.ok("GET", f"/api/networks/{s}/my-ban")["reason"] == "spamming links"
    # appeal (once) -> moderators notified; unban restores membership
    mem.ok("POST", f"/api/networks/{s}/bans/appeal", json={"text": "Sorry, that was a mistake, won't happen again."})
    assert mem.post(f"/api/networks/{s}/bans/appeal", json={"text": "Sorry again, please reconsider my ban."}).status_code == 409
    assert any("appealed" in x["text"] for x in f.ok("GET", "/api/notifications"))
    assert f.ok("GET", f"/api/networks/{s}/bans")[0]["appeal"].startswith("Sorry")
    assert f.ok("DELETE", f"/api/networks/{s}/bans/{mem.username}")["membership"] == "active"
    mem.ok("POST", "/api/posts", json={"body": "back", "network_id": n["id"]})
    # a ban of a non-member blocks joining; expiry lets them join again
    f.ok("POST", f"/api/networks/{s}/bans", json={"username": other.username, "reason": "known scammer"})
    assert other.post(f"/api/networks/{s}/join").status_code == 403
    from app.models import NetworkBan, AuditLog
    with SessionLocal() as db:
        nb = db.query(NetworkBan).filter_by(user_id=other.id).one(); nb.until = utcnow() - timedelta(minutes=1); db.commit()
        acts = {a.action for a in db.query(AuditLog).all()}
    assert {"network.ban", "network.unban", "network.ban_appeal"} <= acts
    other.ok("POST", f"/api/networks/{s}/join")
