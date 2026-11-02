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
def rpc(method, params):
    r = httpx.post(rpc_url(), json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=TIMEOUT)
    r.raise_for_status()
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


def earliest_tx_signers(mint: str, max_pages: int | None = None) -> dict | None:
    max_pages = max_pages or int(os.getenv("CHAIN_MAX_SIG_PAGES", "10"))
    before, oldest = None, None
    for _ in range(max_pages):
        opts = {"limit": 1000, **({"before": before} if before else {})}
        page = rpc("getSignaturesForAddress", [mint, opts]) or []
        if not page: break
        oldest = page[-1]; before = oldest["signature"]
        if len(page) < 1000: break
    else:
        return {"signers": [], "method": "earliest mint transaction", "incomplete": True}
    if not oldest: return None
    tx = rpc("getTransaction", [oldest["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    keys = ((tx or {}).get("transaction") or {}).get("message", {}).get("accountKeys", [])
    signers = [k["pubkey"] for k in keys if isinstance(k, dict) and k.get("signer")]
    return {"signers": signers, "fee_payer": signers[0] if signers else "", "signature": oldest["signature"],
            "block_time": oldest.get("blockTime"), "method": "fee payer / signer of the mint's earliest transaction"}


def metadata_authority(mint: str) -> dict | None:
    """Metaplex metadata account: byte 0 = key, bytes 1..33 = update authority, 33..65 = mint."""
    pda = find_pda([b"metadata", b58decode(METAPLEX_PROGRAM), b58decode(mint)], METAPLEX_PROGRAM)
    d = account_data(pda)
    if not d or len(d) < 65: return None
    return {"update_authority": b58encode(d[1:33]), "method": "Metaplex metadata update authority"}


def helius_asset(mint: str) -> dict | None:
    key = os.getenv("HELIUS_API_KEY")
    if not key: return None
    r = httpx.post(f"https://mainnet.helius-rpc.com/?api-key={key}", json={"jsonrpc": "2.0", "id": 1, "method": "getAsset", "params": {"id": mint}}, timeout=TIMEOUT)
    r.raise_for_status()
    a = r.json().get("result") or {}
    return {"authorities": [x["address"] for x in a.get("authorities", [])], "creators": [x["address"] for x in a.get("creators", [])],
            "symbol": ((a.get("content") or {}).get("metadata") or {}).get("symbol", ""), "method": "Metaplex authority/creators via Helius DAS getAsset"}


def find_creator(mint: str, address: str) -> dict:
    """Try each source in order; report which matched. Never guesses."""
    tried, candidates = [], set()
    def attempt(name, fn):
        try: return fn()
        except Exception as e:
            tried.append(f"{name}: unavailable ({str(e)[:80]})"); return None
    p = attempt("pump.fun", lambda: pump_creator(mint))
    if p:
        candidates.add(p["creator"]); tried.append(f"pump.fun creator = {p['creator']}")
        if p["creator"] == address: return {"matched": True, "method": p["method"], "creator": p["creator"], "tried": tried}
    e = attempt("earliest tx", lambda: earliest_tx_signers(mint))
    if e:
        if e.get("incomplete"): tried.append("earliest tx: history too long to page fully")
        else:
            candidates.update(e["signers"]); tried.append(f"earliest tx signers = {', '.join(e['signers'])}")
            if address in e["signers"]: return {"matched": True, "method": e["method"], "creator": address, "tried": tried}
    h = attempt("helius", lambda: helius_asset(mint))
    if h:
        cs = set(h["authorities"]) | set(h["creators"]); candidates |= cs
        tried.append(f"Helius authorities/creators = {', '.join(cs) or 'none'}")
        if address in cs: return {"matched": True, "method": h["method"], "creator": address, "tried": tried}
    else:
        m = attempt("metadata", lambda: metadata_authority(mint))
        if m:
            candidates.add(m["update_authority"]); tried.append(f"metadata update authority = {m['update_authority']}")
            if m["update_authority"] == address: return {"matched": True, "method": m["method"], "creator": address, "tried": tried}
    if not candidates: reason = "Creator could not be determined from on-chain data."
    else: reason = "The signing wallet is not the token's on-chain creator. If this is a community takeover, use a CTO claim instead."
    return {"matched": False, "reason": reason, "candidates": sorted(candidates), "tried": tried,
            "creator": p["creator"] if p else (e["fee_payer"] if e and e.get("fee_payer") else "")}


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
        tx = rpc("getTransaction", [oldest["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
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
