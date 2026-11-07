def test_wallet_signature_features_are_off_when_not_opted_in(mk, monkeypatch):
    monkeypatch.setenv("ENABLE_WALLET_FEATURES", "0")
    c = mk("scopecheck")
    r = c.post("/api/verify/nonce", json={
        "purpose": "wallet",
        "address": "11111111111111111111111111111111",
        "subject": "",
    })
    assert r.status_code == 404


def test_legacy_devwallet_recheck_is_disabled(mk, monkeypatch):
    c = mk()
    n = c.ok("POST", "/api/networks", json={"name": "Wallet Off Recheck", "type": "Project"})
    monkeypatch.setenv("ENABLE_WALLET_FEATURES", "0")
    assert c.post(f"/api/networks/{n['slug']}/verify/devwallet/recheck").status_code == 404
