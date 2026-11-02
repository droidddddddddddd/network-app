"""Read-only Solana helpers: signature checks and on-chain lookups.

Nothing here ever builds or requests a transaction, and nothing touches private keys or seed phrases.
Every network call has a timeout. Everything is a plain function so tests can monkeypatch it.
"""
import base64, hashlib, os, re, time
import httpx
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from nacl.bindings import crypto_core_ed25519_is_valid_point

PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
METAPLEX_PROGRAM = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
INCINERATOR = "1nc1nerator11111111111111111111111111111111"
TIMEOUT = float(os.getenv("CHAIN_TIMEOUT", "10"))
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
ADDR_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def rpc_url():
    if os.getenv("SOLANA_RPC_URL"): return os.getenv("SOLANA_RPC_URL")
    if os.getenv("HELIUS_API_KEY"): return f"https://mainnet.helius-rpc.com/?api-key={os.getenv('HELIUS_API_KEY')}"
    return "https://api.mainnet-beta.solana.com"


# ---------------------------------------------------------------- base58 / signatures
def b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        i = B58.find(ch)
        if i < 0: raise ValueError("invalid base58")
        n = n * 58 + i
    full = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + full


def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big"); out = ""
    while n: n, r = divmod(n, 58); out = B58[r] + out
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + out


def valid_address(a: str) -> bool:
    if not a or not ADDR_RE.match(a): return False
    try: return len(b58decode(a)) == 32
    except ValueError: return False


def decode_sig(sig: str) -> bytes:
    sig = (sig or "").strip()
    for dec in (b58decode, lambda x: base64.b64decode(x, validate=True)):
        try:
            b = dec(sig)
            if len(b) == 64: return b
        except Exception: pass
    raise ValueError("Signature must be a 64-byte ed25519 signature (base58 or base64).")


def verify_signature(address: str, message: str, signature: str) -> bool:
    """ed25519 check of a wallet's signMessage output over the exact UTF-8 message."""
    if not valid_address(address): return False
    try:
        VerifyKey(b58decode(address)).verify(message.encode(), decode_sig(signature)); return True
    except (BadSignatureError, ValueError): return False


def on_curve(pk: bytes) -> bool:
    return bool(crypto_core_ed25519_is_valid_point(pk))


def find_pda(seeds: list[bytes], program: str) -> str:
    prog = b58decode(program)
    for bump in range(255, -1, -1):
        h = hashlib.sha256(b"".join(seeds) + bytes([bump]) + prog + b"ProgramDerivedAddress").digest()
        if not on_curve(h): return b58encode(h)
    raise ValueError("no PDA")


def is_program_owned_address(addr: str) -> bool:
    """Off-curve owners are PDAs (bonding curves, AMM pools, lockers), never a person's wallet."""
    try: return not on_curve(b58decode(addr))
    except ValueError: return False


# ---------------------------------------------------------------- RPC
def rpc(method, params, retries=3):
    # Errors never include the URL: with Helius it contains the API key.
    for attempt in range(retries + 1):
        try:
            r = httpx.post(rpc_url(), json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            raise RuntimeError(f"RPC {method}: {type(e).__name__}") from None
        if r.status_code == 429 and attempt < retries:  # public RPC rate limit: brief backoff
            time.sleep(min(float(r.headers.get("retry-after") or 0) or 1.5 * 2 ** attempt, 8)); continue
        if r.status_code >= 400: raise RuntimeError(f"RPC {method}: HTTP {r.status_code}")
        break
    j = r.json()
    if j.get("error"): raise RuntimeError(f"RPC {method}: {j['error'].get('message', j['error'])}")
    return j.get("result")


def account_data(addr: str) -> bytes | None:
    res = rpc("getAccountInfo", [addr, {"encoding": "base64"}])
    v = (res or {}).get("value")
    return base64.b64decode(v["data"][0]) if v else None


# ---------------------------------------------------------------- creator lookups (in priority order)
def pump_creator(mint: str) -> dict | None:
    curve = find_pda([b"bonding-curve", b58decode(mint)], PUMP_PROGRAM)
    d = account_data(curve)
    if not d or len(d) < 81: return None
    return {"creator": b58encode(d[49:81]), "curve": curve, "complete": bool(d[48]), "method": "pump.fun bonding-curve creator field"}


TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ATA_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
PUMP_CREATE = {bytes.fromhex("181ec828051c0777"): "create", bytes.fromhex("d6904cec5f8b31b4"): "create_v2"}
DEX_PROGRAMS = {
    PUMP_PROGRAM: "pump.fun bonding curve", "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "PumpSwap",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM", "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "Raydium CPMM",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM", "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj": "Raydium LaunchLab",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tQUs4ZMJXhkDPXo": "Jupiter", "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "Meteora DLMM",
    "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG": "Meteora DAMM v2", "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB": "Meteora DAMM",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
}


def is_helius() -> bool:
    return "helius" in rpc_url()


def get_tx(sig: str) -> dict | None:
    """Fetch a parsed transaction; newer transaction versions first, falling back for older RPC nodes."""
    for ver in (1, 0):
        try:
            return rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": ver, "commitment": "finalized"}])
        except RuntimeError as e:
            if ver == 1 and "version" in str(e).lower(): continue
            raise
    return None


def oldest_signature(address: str, max_pages: int | None = None) -> dict:
    """Oldest transaction touching `address`.
    Helius: getTransactionsForAddress sorted oldest-first (one request, any history length).
    Otherwise: page getSignaturesForAddress backwards up to CHAIN_MAX_SIG_PAGES x 1000; busy addresses come back incomplete."""
    if is_helius():
        try:
            res = rpc("getTransactionsForAddress", [address, {"sortOrder": "asc", "limit": 1, "transactionDetails": "signatures"}])
            d = (res or {}).get("data") or []
            if d: return {"signature": d[0]["signature"], "block_time": d[0].get("blockTime"), "how": "Helius oldest-first history"}
            return {"signature": None}
        except Exception:
            pass  # plan without this method: fall back to paging
    max_pages = max_pages or int(os.getenv("CHAIN_MAX_SIG_PAGES", "10"))
    before, oldest = None, None
    for _ in range(max_pages):
        page = rpc("getSignaturesForAddress", [address, {"limit": 1000, **({"before": before} if before else {})}]) or []
        if not page: break
        oldest = page[-1]; before = oldest["signature"]
        if len(page) < 1000: break
    else:
        return {"incomplete": True}
    return {"signature": oldest["signature"] if oldest else None, "block_time": (oldest or {}).get("blockTime"), "how": "backward signature paging"}


def _keys(tx) -> list[str]:
    return [k["pubkey"] if isinstance(k, dict) else k for k in ((tx or {}).get("transaction") or {}).get("message", {}).get("accountKeys", [])]


def parse_pump_create(tx, mint: str) -> str | None:
    """If the tx contains a pump.fun create/create_v2 instruction for `mint`, return the `creator` argument
    (borsh: 8-byte discriminator, name, symbol, uri strings, then creator pubkey)."""
    for ix in ((tx or {}).get("transaction") or {}).get("message", {}).get("instructions", []):
        if ix.get("programId") != PUMP_PROGRAM or not ix.get("data"): continue
        try:
            d = b58decode(ix["data"])
            if d[:8] not in PUMP_CREATE or (ix.get("accounts") or [None])[0] != mint: continue
            o = 8
            for _ in range(3):
                n = int.from_bytes(d[o:o + 4], "little"); o += 4 + n
            if len(d) >= o + 32: return b58encode(d[o:o + 32])
        except Exception:
            continue
    return None


def creation_tx(mint: str) -> dict:
    """The token's creator from its creation transaction. Never guesses: returns incomplete/unknown instead.
    Bundled launches have several signers (bundle buyers), so only the pump.fun creator argument or the fee payer counts."""
    def compute():
        o = oldest_signature(mint)
        if o.get("incomplete"): return {"incomplete": True, "method": "creation transaction", "reason": "History too long to reach the creation transaction without Helius."}
        if not o.get("signature"): return {"creator": "", "method": "creation transaction", "reason": "No transactions found for this mint."}
        tx = get_tx(o["signature"])
        keys = _keys(tx)
        if mint not in keys: return {"creator": "", "method": "creation transaction", "reason": "Oldest transaction does not include the mint."}
        pc = parse_pump_create(tx, mint)
        if pc: return {"creator": pc, "method": "pump.fun create instruction (creator argument)", "signature": o["signature"], "block_time": o.get("block_time"), "how": o.get("how")}
        return {"creator": keys[0], "method": "fee payer of the mint's creation transaction", "signature": o["signature"], "block_time": o.get("block_time"), "how": o.get("how")}
    return db_cached(f"creation:{mint}", None, compute, keep=lambda r: bool(r.get("creator")))


def metadata_authority(mint: str) -> dict | None:
    """Metaplex metadata account (bytes 1..33 = update authority), or the Token-2022 tokenMetadata extension."""
    pda = find_pda([b"metadata", b58decode(METAPLEX_PROGRAM), b58decode(mint)], METAPLEX_PROGRAM)
    d = account_data(pda)
    if d and len(d) >= 65: return {"update_authority": b58encode(d[1:33]), "method": "Metaplex metadata update authority"}
    v = (rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}]) or {}).get("value") or {}
    for ext in (((v.get("data") or {}).get("parsed") or {}).get("info") or {}).get("extensions", []) if isinstance(v.get("data"), dict) else []:
        if ext.get("extension") == "tokenMetadata":
            ua = (ext.get("state") or {}).get("updateAuthority")
            if ua: return {"update_authority": ua, "method": "Token-2022 metadata update authority"}
    return None


def helius_asset(mint: str) -> dict | None:
    key = os.getenv("HELIUS_API_KEY")
    if not key: return None
    try:
        r = httpx.post(f"https://mainnet.helius-rpc.com/?api-key={key}", json={"jsonrpc": "2.0", "id": 1, "method": "getAsset", "params": {"id": mint}}, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise RuntimeError(f"Helius getAsset: {type(e).__name__}") from None  # never surface the keyed URL
    if r.status_code >= 400: raise RuntimeError(f"Helius getAsset: HTTP {r.status_code}")
    a = r.json().get("result") or {}
    return {"authorities": [x["address"] for x in a.get("authorities", [])], "creators": [x["address"] for x in a.get("creators", []) if x.get("verified")],
            "symbol": ((a.get("content") or {}).get("metadata") or {}).get("symbol", ""), "method": "Metaplex authority / verified creators via Helius DAS getAsset"}


def find_creator(mint: str, address: str) -> dict:
    """Try each source in order; report which matched. Never guesses."""
    tried, candidates = [], set()
    def attempt(name, fn):
        try: return fn()
        except Exception as e:
            tried.append(f"{name}: unavailable ({type(e).__name__})"); return None
    p = attempt("pump.fun", lambda: pump_creator(mint))
    if p:
        candidates.add(p["creator"]); tried.append(f"pump.fun creator = {p['creator']}")
        if p["creator"] == address: return {"matched": True, "method": p["method"], "creator": p["creator"], "tried": tried}
    e = attempt("creation tx", lambda: creation_tx(mint))
    if e:
        if e.get("incomplete") or not e.get("creator"): tried.append(f"creation tx: couldn't determine ({e.get('reason', 'unknown')})")
        else:
            candidates.add(e["creator"]); tried.append(f"creation tx ({e['method']}) = {e['creator']}")
            if address == e["creator"]: return {"matched": True, "method": e["method"], "creator": address, "tried": tried}
    h = attempt("helius", lambda: helius_asset(mint))
    if h:
        cs = set(h["authorities"]) | set(h["creators"]); candidates |= cs
        tried.append(f"Helius authorities/creators = {', '.join(sorted(cs)) or 'none'}")
        if address in cs: return {"matched": True, "method": h["method"], "creator": address, "tried": tried}
    m = attempt("metadata", lambda: metadata_authority(mint))
    if m:
        candidates.add(m["update_authority"]); tried.append(f"{m['method']} = {m['update_authority']}")
        if m["update_authority"] == address: return {"matched": True, "method": m["method"], "creator": address, "tried": tried}
    if not candidates: reason = "Couldn't determine the token's creator from on-chain data, so nothing was verified."
    else: reason = "The signing wallet is not the token's on-chain creator. If this is a community takeover, use a CTO claim instead."
    return {"matched": False, "reason": reason, "candidates": sorted(candidates), "tried": tried,
            "creator": p["creator"] if p else (e.get("creator", "") if e else "")}


# ---------------------------------------------------------------- dev wallet token flows (sold vs transferred)
def ata(owner: str, mint: str, token_program: str) -> str:
    return find_pda([b58decode(owner), b58decode(token_program), b58decode(mint)], ATA_PROGRAM)


def _programs(tx) -> set:
    m = ((tx or {}).get("transaction") or {}).get("message", {})
    progs = {ix.get("programId") for ix in m.get("instructions", [])}
    for inner in ((tx or {}).get("meta") or {}).get("innerInstructions") or []:
        progs |= {ix.get("programId") for ix in inner.get("instructions", [])}
    return {p for p in progs if p}


def classify_flow(tx, owner: str, mint: str) -> dict | None:
    """One transaction's effect on `owner`'s balance of `mint`.
    Decrease + DEX program in the tx = sold. Decrease with another wallet receiving = transferred (destination shown).
    Decrease with no recipient = burned/closed (unclassified). Increase = acquired."""
    meta = (tx or {}).get("meta") or {}
    if meta.get("err"): return None
    def bal(rows, who):
        return sum(int(r["uiTokenAmount"]["amount"]) for r in rows or [] if r.get("mint") == mint and r.get("owner") == who)
    pre, post = meta.get("preTokenBalances"), meta.get("postTokenBalances")
    dec = next((int(r["uiTokenAmount"]["decimals"]) for r in (post or []) + (pre or []) if r.get("mint") == mint), 0)
    delta = bal(post, owner) - bal(pre, owner)
    if delta == 0: return None
    sig = ((tx.get("transaction") or {}).get("signatures") or [""])[0]
    ev = {"signature": sig, "block_time": tx.get("blockTime"), "amount": abs(delta) / 10 ** dec}
    if delta > 0: return {**ev, "kind": "acquired"}
    dex = sorted({DEX_PROGRAMS[p] for p in _programs(tx) if p in DEX_PROGRAMS})
    if dex: return {**ev, "kind": "sold", "venue": ", ".join(dex)}
    owners = {r.get("owner") for r in (post or []) + (pre or []) if r.get("mint") == mint and r.get("owner") and r.get("owner") != owner}
    gains = sorted(((bal(post, o) - bal(pre, o), o) for o in owners), reverse=True)
    gains = [(g, o) for g, o in gains if g > 0]
    if gains: return {**ev, "kind": "transferred", "to": [o for _, o in gains]}
    return {**ev, "kind": "burned_or_unclassified"}


def dev_token_flows(owner: str, mint: str, max_txs: int | None = None) -> dict:
    """Parse the dev wallet's token-account history for this mint (its associated token accounts under both token
    programs, which keep their history even after being closed)."""
    max_txs = max_txs or int(os.getenv("CHAIN_MAX_FLOW_TXS", "60"))
    sigs = []
    for prog in (TOKEN_PROGRAM, TOKEN_2022):
        sigs += [s for s in (rpc("getSignaturesForAddress", [ata(owner, mint, prog), {"limit": max_txs + 1}]) or []) if not s.get("err")]
    sigs.sort(key=lambda s: s.get("blockTime") or 0)
    complete = len(sigs) <= max_txs
    events = []
    for s in sigs[-max_txs:]:
        e = classify_flow(get_tx(s["signature"]), owner, mint)
        if e: events.append(e)
    tot = lambda k: sum(e["amount"] for e in events if e["kind"] == k)
    dests: dict = {}
    for e in events:
        if e["kind"] == "transferred":
            for d in e["to"][:1]: dests[d] = dests.get(d, 0) + e["amount"]
    return {"events": events, "complete": complete, "checked_txs": min(len(sigs), max_txs), "acquired": tot("acquired"), "sold": tot("sold"),
            "transferred": tot("transferred"), "burned_or_unclassified": tot("burned_or_unclassified"),
            "venues": sorted({e["venue"] for e in events if e["kind"] == "sold"}),
            "destinations": [{"wallet": w, "amount": a} for w, a in sorted(dests.items(), key=lambda x: -x[1])]}


# ---------------------------------------------------------------- balances
def token_balance(owner: str, mint: str) -> dict:
    """Live balance of `mint` across all token accounts owned by `owner` (both token programs via mint filter)."""
    res = rpc("getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed"}])
    amt, raw, accts = 0.0, 0, []
    for a in (res or {}).get("value", []):
        ta = a["account"]["data"]["parsed"]["info"]["tokenAmount"]
        amt += float(ta.get("uiAmount") or 0); raw += int(ta["amount"]); accts.append(a["pubkey"])
    return {"ui": amt, "raw": raw, "accounts": accts}


def token_supply(mint: str) -> dict:
    v = rpc("getTokenSupply", [mint])["value"]
    return {"ui": float(v.get("uiAmount") or 0), "raw": int(v["amount"]), "decimals": v["decimals"]}


def largest_holders(mint: str) -> list[dict]:
    """Top token accounts with their owner wallet (for excluding curve/pool/program-owned holdings)."""
    accts = (rpc("getTokenLargestAccounts", [mint]) or {}).get("value", [])
    if not accts: return []
    info = (rpc("getMultipleAccounts", [[a["address"] for a in accts], {"encoding": "jsonParsed"}]) or {}).get("value", [])
    out = []
    for a, i in zip(accts, info):
        owner = (((i or {}).get("data") or {}).get("parsed") or {}).get("info", {}).get("owner", "")
        out.append({"account": a["address"], "owner": owner, "raw": int(a["amount"]), "ui": float(a.get("uiAmount") or 0)})
    return out


def wallet_history(wallet: str) -> dict:
    """Cheap first-activity lookup (max 3 pages): age and first funder (fee payer of the first tx if not the wallet)."""
    before, oldest = None, None
    for _ in range(3):
        page = rpc("getSignaturesForAddress", [wallet, {"limit": 1000, **({"before": before} if before else {})}]) or []
        if not page: break
        oldest = page[-1]; before = oldest["signature"]
        if len(page) < 1000: break
    else:
        return {"first_seen": None, "first_funder": "", "old": True}  # >3000 txs: established wallet
    if not oldest: return {"first_seen": None, "first_funder": "", "old": False}
    funder = ""
    try:
        tx = get_tx(oldest["signature"])
        keys = tx["transaction"]["message"]["accountKeys"]
        payer = keys[0]["pubkey"] if isinstance(keys[0], dict) else keys[0]
        funder = payer if payer != wallet else ""
    except Exception: pass
    return {"first_seen": oldest.get("blockTime"), "first_funder": funder, "old": False}


def last_activity(owner: str, mint: str) -> int | None:
    b = token_balance(owner, mint)
    times = []
    for acct in b["accounts"][:3]:
        s = rpc("getSignaturesForAddress", [acct, {"limit": 1}]) or []
        if s and s[0].get("blockTime"): times.append(s[0]["blockTime"])
    return max(times) if times else None


_cache: dict = {}
def cached(key, ttl, fn):
    v = _cache.get(key)
    if v and time.time() - v[0] < ttl: return v[1]
    r = fn(); _cache[key] = (time.time(), r); return r


def db_cached(key: str, ttl: int | None, fn, keep=lambda r: True):
    """Persistent cache in the chain_cache table (shared by all instances). ttl=None caches forever (immutable facts);
    results rejected by `keep` (e.g. "couldn't determine") are never cached so they're retried."""
    import json as _json
    from datetime import datetime, timezone, timedelta
    from .db import SessionLocal
    from .models import ChainCache
    now = datetime.now(timezone.utc)
    try:
        with SessionLocal() as db:
            row = db.get(ChainCache, key)
            if row and (row.expires_at is None or (row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)) > now):
                return _json.loads(row.value)
    except Exception:
        pass
    r = fn()
    if keep(r):
        try:
            with SessionLocal() as db:
                row = db.get(ChainCache, key) or ChainCache(key=key)
                row.value, row.expires_at = _json.dumps(r), (now + timedelta(seconds=ttl) if ttl else None)
                db.merge(row); db.commit()
        except Exception:
            pass
    return r
