"""Read-only live checks against Solana mainnet. Opt-in: NETWORK_LIVE_TESTS=1 (uses public RPC, or HELIUS_API_KEY if set)."""
import os
import pytest
from app import chain

pytestmark = pytest.mark.skipif(os.getenv("NETWORK_LIVE_TESTS") != "1", reason="live network tests are opt-in")
PUMP_MINT = os.getenv("LIVE_PUMP_MINT", "8s4bNqEztH1JP7mkU747uMr7AckCQdiV47FDqYnDpump")
PUMP_CREATOR = os.getenv("LIVE_PUMP_CREATOR", "AoEEgeHgLMbANGd2zyRH8wTy2ekvxFNduSTFTxuVydeF")


def test_live_pump_creator_lookup():
    p = chain.pump_creator(PUMP_MINT)
    assert p and p["creator"] == PUMP_CREATOR
    r = chain.find_creator(PUMP_MINT, PUMP_CREATOR)
    assert r["matched"] and r["method"] == "pump.fun bonding-curve creator field"
    assert not chain.find_creator(PUMP_MINT, "So11111111111111111111111111111111111111112")["matched"]


def test_live_balance_lookup():
    s = chain.token_supply(PUMP_MINT)
    assert s["raw"] > 0
    b = chain.token_balance(PUMP_CREATOR, PUMP_MINT)
    assert b["raw"] >= 0 and isinstance(b["accounts"], list)
    top = chain.largest_holders(PUMP_MINT)
    assert top and all("owner" in h for h in top)


def test_live_creation_tx():
    r = chain.creation_tx(PUMP_MINT)
    if chain.is_helius():
        assert r["creator"] == PUMP_CREATOR and "create instruction" in r["method"]
    else:  # busy token: public RPC can't page back far enough, and must say so instead of guessing
        assert r.get("creator") == PUMP_CREATOR or (r.get("incomplete") and not r.get("creator"))


def test_live_dev_token_flows():
    f = chain.dev_token_flows(PUMP_CREATOR, PUMP_MINT)
    assert f["checked_txs"] >= 1 and f["acquired"] > 0
    assert f["sold"] > 0 and "PumpSwap" in f["venues"] and f["transferred"] == 0
