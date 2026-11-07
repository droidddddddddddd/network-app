def test_wallet_signature_features_are_off_when_not_opted_in(mk, monkeypatch):
    monkeypatch.setenv("ENABLE_WALLET_FEATURES", "0")
    c = mk("scopecheck")
    r = c.post("/api/verify/nonce", json={
        "purpose": "wallet",
        "address": "11111111111111111111111111111111",
        "subject": "",
    })
    assert r.status_code == 404
