"""Free keyless DexScreener API — GET /tokens/v1/solana/{a,b,...} (≤30 addresses, ~300 req/min)."""
import asyncio, os
from datetime import timedelta
import httpx
from sqlalchemy import select
from .db import SessionLocal
from .models import Call
from .services import utcnow, aware, notify
from .realtime import hub

BASE = "https://api.dexscreener.com"


def fetch_tokens(addresses: list[str]) -> dict:
    out = {}
    with httpx.Client(timeout=10, headers={"accept": "application/json"}) as c:
        for i in range(0, len(addresses), 30):
            chunk = addresses[i:i + 30]
            r = c.get(f"{BASE}/tokens/v1/solana/{','.join(chunk)}")
            r.raise_for_status()
            for p in r.json() or []:
                a = (p.get("baseToken") or {}).get("address")
                if a not in chunk:
                    continue
                liq = float((p.get("liquidity") or {}).get("usd") or 0)
                if a not in out or liq > out[a]["liquidity"]:
                    out[a] = {"address": a, "symbol": p["baseToken"].get("symbol", ""), "name": p["baseToken"].get("name", ""),
                              "price": float(p.get("priceUsd") or 0), "mcap": float(p.get("marketCap") or p.get("fdv") or 0),
                              "liquidity": liq, "change24h": float((p.get("priceChange") or {}).get("h24") or 0),
                              "url": p.get("url", "")}
    return out


def fetch_token(addr: str):
    return fetch_tokens([addr]).get(addr)


def trending(limit=8):
    with httpx.Client(timeout=10) as c:
        boosts = c.get(f"{BASE}/token-boosts/top/v1").json()
    addrs = list(dict.fromkeys(b["tokenAddress"] for b in boosts if b.get("chainId") == "solana"))[:30]
    info = fetch_tokens(addrs)
    return [info[a] for a in addrs if a in info and info[a]["liquidity"] > 5000 and info[a]["price"] > 0][:limit]


def is_rug(c: Call, t) -> bool:
    if t is None:
        return utcnow() - aware(c.created_at) > timedelta(hours=1)
    if c.entry_liquidity and t["liquidity"] < c.entry_liquidity * 0.2 and t["liquidity"] < 5000:
        return True
    return t["liquidity"] < 500


def track_once() -> int:
    db = SessionLocal()
    try:
        since = utcnow() - timedelta(days=8)
        calls = list(db.scalars(select(Call).where(Call.created_at >= since, Call.rugged.is_(False)).limit(300)))
        if not calls:
            return 0
        data = fetch_tokens(list({c.token_address for c in calls}))
        for c in calls:
            t = data.get(c.token_address)
            age = utcnow() - aware(c.created_at)
            c.last_checked = utcnow()
            if is_rug(c, t):
                c.rugged = True
                c.checks += 1
                c.current_liquidity = t["liquidity"] if t else 0
                notify(db, c.user_id, None, "rug", f"Liquidity collapsed on your ${c.symbol} call — flagged as a likely rug.", f"#/calls/{c.id}")
                continue
            if not t or not c.entry_price:
                continue
            c.checks += 1
            c.current_price, c.current_mcap, c.current_liquidity = t["price"], t["mcap"], t["liquidity"]
            c.peak_price = max(c.peak_price or 0, t["price"])
            mult = t["price"] / c.entry_price
            if c.result_1h is None and age >= timedelta(hours=1): c.result_1h = mult
            if c.result_24h is None and age >= timedelta(hours=24): c.result_24h = mult
            if c.result_7d is None and age >= timedelta(days=7): c.result_7d = mult
        db.commit()
        hub.to_all({"type": "calls_updated"})
        return len(calls)
    finally:
        db.close()


async def tracker_loop():
    every = int(os.getenv("TRACK_INTERVAL_SEC", "120"))
    await asyncio.sleep(5)
    while True:
        try:
            n = await asyncio.to_thread(track_once)
            if n: print(f"[tracker] checked {n} calls")
        except Exception as e:  # network errors must not kill the loop
            print("[tracker] error:", e)
        await asyncio.sleep(every)
