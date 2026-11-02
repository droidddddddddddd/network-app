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
