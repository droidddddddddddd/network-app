"""Moderation, signature-based verification (wallet, dev wallet, metadata authority), domain verification,
holder-backed community-takeover (CTO) claims and selectively shared Network activity.

Wallet flows use signMessage only. NETWORK never asks for, builds or relays a transaction, and never asks for a seed phrase or private key."""
import json, os, re, secrets
from datetime import timedelta
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import Session
from .db import get_db
from .models import (User, Network, Membership, Connection, Post, Report, Verification, Nonce, NetworkActivity, CtoClaim, CtoBacking,
                     ACTIVITY_TYPES)
from .security import current_user, optional_user, rate_limit, clean, is_platform_admin, ensure_active
from .services import (utcnow, aware, iso, notify, audit, membership, is_active, can, network_brief, user_brief, my_network_ids,
                       activity_types_of, record_activity, can_see_post)
from . import chain
from .main import commit, get_network, get_user_by_name, ip_of

router = APIRouter()
NONCE_TTL = timedelta(minutes=10)


def short(a: str) -> str:
    return f"{a[:4]}…{a[-4:]}" if a and len(a) > 10 else a


def ticker_of(mint: str) -> str:
    try:
        from . import dex
        t = dex.fetch_token(mint)
        if t and t.get("symbol"): return t["symbol"]
    except Exception: pass
    return short(mint)


# ================================================================= MODERATION
class ReportCreate(BaseModel):
    target_type: str = Field(pattern="^(post|user|network)$")
    target: str = Field(min_length=1, max_length=40)
    reason: str = Field(min_length=3, max_length=300)


class ResolveIn(BaseModel):
    action: str = Field(pattern="^(dismiss|hide_post|remove_post|suspend_user)$")
    note: str = Field(default="", max_length=300)
    suspend_hours: int | None = Field(default=None, ge=1, le=24 * 365)  # None = indefinite


def file_report(db, user, target_type, target, reason):
    reason = clean(reason, 300)
    if len(reason) < 3: raise HTTPException(400, "Give a short reason.")
    scope = None
    if target_type == "post":
        p = db.get(Post, int(target)) if str(target).isdigit() else None
        if not p or p.removed or not can_see_post(db, user.id, p): raise HTTPException(404, "Post not found.")
        if p.author_id == user.id: raise HTTPException(400, "You can't report your own post.")
        tid, scope, label, link = p.id, p.network_id, f"post #{p.id}", f"#/post/{p.id}"
    elif target_type == "user":
        u = get_user_by_name(db, target)
        if u.id == user.id: raise HTTPException(400, "You can't report yourself.")
        tid, label, link = u.id, f"@{u.username}", f"#/u/{u.username}"
    else:
        n = get_network(db, target)
        tid, label, link = n.id, n.name, f"#/n/{n.slug}"
    if db.scalar(select(Report.id).where(Report.reporter_id == user.id, Report.target_type == target_type, Report.target_id == tid)):
        raise HTTPException(409, "You already reported this.")
    r = Report(reporter_id=user.id, target_type=target_type, target_id=tid, post_id=tid if target_type == "post" else None,
               network_id=scope, reason=reason)
    db.add(r)
    if scope:
        n = db.get(Network, scope)
        for m in db.scalars(select(Membership).where(Membership.network_id == n.id, Membership.status == "active", Membership.role.in_(["founder", "admin"]))):
            if can(m, "perm_moderate"): notify(db, m.user_id, None, "report", f"A post in {n.name} was reported: {reason[:80]}", f"#/n/{n.slug}/moderation")
    for u in db.scalars(select(User).where(func.lower(User.username).in_([x.strip().lower() for x in os.getenv("ADMIN_USERNAMES", "").split(",") if x.strip()] or ["\0"]))):
        notify(db, u.id, None, "report", f"New report on {label}: {reason[:80]}", "#/moderation")
    commit(db)
    return {"ok": True, "id": r.id}


@router.post("/api/reports", dependencies=[rate_limit("report", 10, 600)])
def create_report(data: ReportCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return file_report(db, user, data.target_type, data.target, data.reason)


def report_out(db, r: Report):
    rep = db.get(User, r.reporter_id)
    o = {"id": r.id, "target_type": r.target_type, "target_id": r.target_id, "reason": r.reason, "status": r.status, "resolution": r.resolution,
         "created_at": iso(r.created_at), "resolved_at": iso(r.resolved_at), "reporter": user_brief(rep) if rep else None,
         "network": network_brief(db.get(Network, r.network_id)) if r.network_id else None}
    if r.target_type == "post":
        p = db.get(Post, r.target_id)
        a = db.get(User, p.author_id) if p else None
        o["target"] = {"body": (p.body or "")[:400] if p else "", "author": user_brief(a) if a else None, "hidden": bool(p and p.hidden),
                       "removed": bool(p and p.removed), "link": f"#/post/{r.target_id}"}
    elif r.target_type == "user":
        u = db.get(User, r.target_id)
        o["target"] = {"user": user_brief(u) if u else None, "link": f"#/u/{u.username}" if u else ""}
    else:
        n = db.get(Network, r.target_id)
        o["target"] = {"network": network_brief(n) if n else None, "link": f"#/n/{n.slug}" if n else ""}
    o["count"] = db.scalar(select(func.count(Report.id)).where(Report.target_type == r.target_type, Report.target_id == r.target_id)) or 1
    return o


@router.get("/api/moderation/queue")
def queue(network: str = "", status: str = "open", user: User = Depends(current_user), db: Session = Depends(get_db)):
    """network=<slug>: that Network's queue (perm_moderate). No network: platform queue (ADMIN_USERNAMES only)."""
    stmt = select(Report)
    if network:
        n = get_network(db, network)
        if not can(membership(db, n.id, user.id), "perm_moderate"): raise HTTPException(403, "Only this Network's moderators can see its queue.")
        stmt = stmt.where(Report.network_id == n.id)
    elif not is_platform_admin(user):
        raise HTTPException(403, "Only platform admins can see the platform queue.")
    stmt = stmt.where(Report.status == ("resolved" if status == "resolved" else "open"))
    return [report_out(db, r) for r in db.scalars(stmt.order_by(desc(Report.id)).limit(100))]


@router.post("/api/reports/{rid}/resolve")
def resolve(rid: int, data: ResolveIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Report, rid)
    if not r: raise HTTPException(404, "Report not found.")
    platform = is_platform_admin(user)
    net_mod = bool(r.network_id and can(membership(db, r.network_id, user.id), "perm_moderate"))
    if not (platform or net_mod): raise HTTPException(403, "You can't moderate this report.")
    if r.status != "open": raise HTTPException(400, "This report is already resolved.")
    a = data.action
    if a in ("hide_post", "remove_post"):
        if r.target_type != "post": raise HTTPException(400, "That action applies to post reports.")
        p = db.get(Post, r.target_id)
        if p:
            if a == "hide_post": p.hidden = True
            else: p.removed = True
            notify(db, p.author_id, None, "moderation", f"A moderator {'hid' if a == 'hide_post' else 'removed'} your post." + (f" Note: {clean(data.note, 200)}" if data.note else ""), "")
    elif a == "suspend_user":
        if not platform: raise HTTPException(403, "Only platform admins can suspend accounts.")
        uid = r.target_id if r.target_type == "user" else (db.get(Post, r.target_id).author_id if r.target_type == "post" and db.get(Post, r.target_id) else None)
        if not uid: raise HTTPException(400, "Suspension applies to user or post reports.")
        if uid == user.id: raise HTTPException(400, "You can't suspend yourself.")
        u = db.get(User, uid)
        u.suspended_until = utcnow() + timedelta(hours=data.suspend_hours) if data.suspend_hours else aware(__import__("datetime").datetime(9999, 1, 1))
        u.suspend_reason = clean(data.note, 300) or r.reason
        notify(db, u.id, None, "moderation", "Your account was suspended" + (f" for {data.suspend_hours}h" if data.suspend_hours else " indefinitely") + f". Reason: {u.suspend_reason}", "")
    # resolve every open report on the same target, and tell each reporter
    same = db.scalars(select(Report).where(Report.target_type == r.target_type, Report.target_id == r.target_id, Report.status == "open")).all()
    for x in same:
        x.status, x.resolution, x.resolved_by, x.resolved_at = "resolved", a, user.id, utcnow()
        notify(db, x.reporter_id, None, "report_resolved", f"Your report was reviewed. Outcome: {a.replace('_', ' ')}.", "")
    audit(db, user.id, r.network_id, f"moderation.{a}", f"{r.target_type}:{r.target_id}",
          f"report:{r.id}; scope:{'platform' if platform and not net_mod else 'network'}; {clean(data.note, 200)}" + (f"; hours:{data.suspend_hours}" if a == "suspend_user" else ""), ip_of(request))
    commit(db)
    return {"ok": True, "resolved": len(same)}


@router.post("/api/admin/users/{username}/unsuspend")
def unsuspend(username: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not is_platform_admin(user): raise HTTPException(403, "Only platform admins can lift suspensions.")
    u = get_user_by_name(db, username)
    u.suspended_until, u.suspend_reason = None, ""
    audit(db, user.id, None, "moderation.unsuspend", f"user:{u.id}", "", ip_of(request))
    notify(db, u.id, None, "moderation", "Your suspension was lifted.", "")
    commit(db)
    return {"ok": True}


# ================================================================= SIGN-IN-WITH-SOLANA STYLE NONCES
PURPOSES = {"wallet": "Prove you control this wallet", "devwallet": "Prove you control the token's creator wallet",
            "metadata": "Prove you control the token's metadata update authority", "cto_back": "Back a community takeover claim"}


class NonceIn(BaseModel):
    purpose: str = Field(pattern="^(wallet|devwallet|metadata|cto_back)$")
    address: str = Field(min_length=32, max_length=44)
    subject: str = Field(default="", max_length=120)  # mint for devwallet/metadata (with network slug), claim id for cto_back


class SignedIn(BaseModel):
    nonce: str = Field(min_length=8, max_length=64)
    signature: str = Field(min_length=64, max_length=200)


def build_message(db, user, purpose, address, subject):
    nonce = secrets.token_urlsafe(18)
    now = utcnow()
    head = PURPOSES[purpose]
    if purpose == "cto_back":
        c = db.get(CtoClaim, int(subject)) if subject.isdigit() else None
        if not c or c.status != "active": raise HTTPException(404, "Claim not found.")
        n = db.get(Network, c.network_id)
        head = f"I support @{n.slug} as the community team for {c.mint}"
        subject = str(c.id)
    lines = [f"NETWORK: {head}", "", f"Account: @{user.username}", f"Wallet: {address}"]
    if subject and purpose != "cto_back": lines.append(f"Subject: {subject}")
    lines += [f"Nonce: {nonce}", f"Issued At: {now.isoformat()}", f"Expires At: {(now + NONCE_TTL).isoformat()}", "",
              "Signing this message is free. It is not a transaction and cannot move funds."]
    return nonce, "\n".join(lines), subject


@router.post("/api/verify/nonce", dependencies=[rate_limit("nonce", 30, 600)])
def issue_nonce(data: NonceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not chain.valid_address(data.address): raise HTTPException(400, "That isn't a valid Solana address.")
    nonce, msg, subject = build_message(db, user, data.purpose, data.address, clean(data.subject, 120))
    db.add(Nonce(user_id=user.id, purpose=data.purpose, nonce=nonce, message=msg, address=data.address, subject=subject,
                 expires_at=utcnow() + NONCE_TTL))
    commit(db)
    return {"nonce": nonce, "message": msg, "expires_in": int(NONCE_TTL.total_seconds())}


def consume(db, user, data: SignedIn, purpose) -> Nonce:
    n = db.scalar(select(Nonce).where(Nonce.nonce == data.nonce))
    if not n or n.user_id != user.id or n.purpose != purpose: raise HTTPException(400, "Unknown challenge. Request a new one.")
    if n.used: raise HTTPException(400, "This challenge was already used. Request a new one.")
    if aware(n.expires_at) < utcnow(): raise HTTPException(400, "This challenge expired. Request a new one.")
    n.used = True  # single use even when the signature is wrong
    if not chain.verify_signature(n.address, n.message, data.signature):
        commit(db); raise HTTPException(400, "Signature check failed: it wasn't made by this wallet over this exact message.")
    return n


def upsert_verif(db, st, sid, kind, **kw):
    v = db.scalar(select(Verification).where(Verification.subject_type == st, Verification.subject_id == sid, Verification.kind == kind).order_by(desc(Verification.id)).limit(1))
    if not v:
        v = Verification(subject_type=st, subject_id=sid, kind=kind); db.add(v)
    for k, x in kw.items(): setattr(v, k, x)
    v.decided_at = utcnow()
    return v


@router.post("/api/verify/wallet", dependencies=[rate_limit("verify_sig", 20, 600)])
def verify_wallet(data: SignedIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = consume(db, user, data, "wallet")
    other = db.scalar(select(User).where(User.wallet_address == n.address, User.wallet_verified.is_(True), User.id != user.id))
    if other: commit(db); raise HTTPException(409, "This wallet is already verified by another account.")
    user.wallet_address, user.wallet_verified = n.address, True
    upsert_verif(db, "user", user.id, "wallet", status="verified", provider="NETWORK (ed25519 signMessage)", method="ed25519 signMessage",
                 address=n.address, value=n.address, requested_by=user.id,
                 detail=f"Wallet ownership verified ({short(n.address)}). Proves control only, not trustworthiness or trading performance.")
    audit(db, user.id, None, "verify.wallet", f"user:{user.id}", n.address, ip_of(request))
    commit(db)
    return {"ok": True, "wallet_address": n.address, "label": "Wallet ownership verified"}


def founder_or_settings(db, n, user):
    if not can(membership(db, n.id, user.id), "perm_settings"): raise HTTPException(403, "Only the founder or admins with settings permission can do this.")
    if n.type != "Project": raise HTTPException(400, "This verification is for Project Networks.")


# ================================================================= DOMAIN
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def norm_domain(d: str) -> str:
    d = clean(d, 260).lower().strip()
    d = re.sub(r"^https?://", "", d).split("/")[0].split(":")[0].rstrip(".")
    if not DOMAIN_RE.match(d) or d.endswith((".local", ".internal", ".localhost")): raise HTTPException(400, "Enter a public domain name like example.com.")
    return d


def fetch_well_known(domain: str) -> str:
    r = httpx.get(f"https://{domain}/.well-known/network-verify.txt", timeout=8, follow_redirects=False, headers={"user-agent": "NETWORK-verify/1"})
    return r.text[:2000] if r.status_code == 200 else ""


def fetch_txt(domain: str) -> list[str]:
    r = httpx.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": "TXT"}, headers={"accept": "application/dns-json"}, timeout=8)
    return [a.get("data", "").strip('"') for a in r.json().get("Answer", []) if a.get("type") == 16]


def check_domain(domain: str, token: str) -> str | None:
    want = f"network-verify={token}"
    try:
        if any(want in t.replace('" "', "") for t in fetch_txt(domain)): return "DNS TXT record"
    except Exception: pass
    try:
        if want in fetch_well_known(domain) or token in fetch_well_known(domain).split(): return "/.well-known/network-verify.txt"
    except Exception: pass
    return None


class DomainIn(BaseModel):
    domain: str = Field(min_length=4, max_length=260)


@router.post("/api/networks/{slug}/verify/domain", dependencies=[rate_limit("verify", 10, 3600)])
def start_domain(slug: str, data: DomainIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug); founder_or_settings(db, n, user)
    d = norm_domain(data.domain)
    token = secrets.token_hex(16)
    upsert_verif(db, "network", n.id, "project", status="pending", value=d, challenge=token, method="", requested_by=user.id, provider="",
                 detail=f"Pending: add the TXT record or file for {d}, then press Check.")
    commit(db)
    return {"domain": d, "token": token, "txt": f"network-verify={token}", "file_url": f"https://{d}/.well-known/network-verify.txt",
            "file_content": f"network-verify={token}"}


@router.post("/api/networks/{slug}/verify/domain/check", dependencies=[rate_limit("verify_check", 20, 3600)])
def check_domain_ep(slug: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug); founder_or_settings(db, n, user)
    v = db.scalar(select(Verification).where(Verification.subject_type == "network", Verification.subject_id == n.id, Verification.kind == "project").order_by(desc(Verification.id)).limit(1))
    if not v or not v.challenge: raise HTTPException(400, "Start domain verification first.")
    how = check_domain(v.value, v.challenge)
    v.decided_at = utcnow()
    if how:
        v.status, v.method, v.provider = "verified", how, "NETWORK domain check"
        v.detail = f"Project domain verified ({v.value})"
        audit(db, user.id, n.id, "verify.domain", v.value, how, ip_of(request))
    else:
        v.status = "pending"
        v.detail = f"Not found yet: no TXT record network-verify=… on {v.value} and no matching /.well-known/network-verify.txt."
    commit(db)
    return {"verified": bool(how), "method": how or "", "detail": v.detail}


# ================================================================= DEV WALLET + METADATA AUTHORITY
def network_mint(db, n) -> str:
    return n.token_address or ""


@router.post("/api/networks/{slug}/verify/devwallet", dependencies=[rate_limit("verify_sig", 20, 600)])
def verify_devwallet(slug: str, data: SignedIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug); founder_or_settings(db, n, user)
    nn = consume(db, user, data, "devwallet")
    mint = nn.subject
    if not chain.valid_address(mint): commit(db); raise HTTPException(400, "Enter the token's mint address.")
    taken = db.scalar(select(Verification).where(Verification.kind == "devwallet", Verification.value == mint, Verification.status == "verified",
                                                 Verification.subject_id != n.id))
    if taken: commit(db); raise HTTPException(409, "This token's dev wallet is already verified by another Network. One token belongs to one Network.")
    return _devwallet_result(db, n, user, mint, nn.address, request)


def _devwallet_result(db, n, user, mint, address, request=None):
    res = chain.find_creator(mint, address)
    sym = ticker_of(mint)
    if res["matched"]:
        if not n.token_address: n.token_address = mint
        v = upsert_verif(db, "network", n.id, "devwallet", status="verified", value=mint, address=address, method=res["method"],
                         provider="NETWORK on-chain check", requested_by=user.id,
                         detail=f"Dev wallet verified: signed by the creator of ${sym} (method: {res['method']}). Proves control of the creator wallet only, not that the project is safe.")
    else:
        v = upsert_verif(db, "network", n.id, "devwallet", status="failed", value=mint, address=address, method="",
                         provider="NETWORK on-chain check", requested_by=user.id, detail=f"Not verified: {res['reason']}")
    audit(db, user.id, n.id, "verify.devwallet", mint, f"{address} matched={res['matched']} {res.get('method', '')}", ip_of(request))
    commit(db)
    return {"verified": res["matched"], "method": res.get("method", ""), "detail": v.detail, "tried": res.get("tried", [])}


@router.post("/api/networks/{slug}/verify/devwallet/recheck", dependencies=[rate_limit("verify_check", 20, 3600)])
def recheck_devwallet(slug: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug); founder_or_settings(db, n, user)
    v = db.scalar(select(Verification).where(Verification.subject_type == "network", Verification.subject_id == n.id, Verification.kind == "devwallet").order_by(desc(Verification.id)).limit(1))
    if not v or not v.address: raise HTTPException(400, "Sign with the dev wallet first.")
    return _devwallet_result(db, n, user, v.value, v.address, request)


@router.post("/api/networks/{slug}/verify/metadata", dependencies=[rate_limit("verify_sig", 20, 600)])
def verify_metadata(slug: str, data: SignedIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug); founder_or_settings(db, n, user)
    nn = consume(db, user, data, "metadata")
    mint = nn.subject
    try:
        m = chain.metadata_authority(mint)
    except Exception as e:
        commit(db); raise HTTPException(502, f"Couldn't read the token metadata right now ({str(e)[:80]}). Try again.")
    ok = bool(m and m["update_authority"] == nn.address)
    reason = "no Metaplex metadata account found" if not m else f"the update authority is {short(m['update_authority'])}, not the signing wallet"
    v = upsert_verif(db, "network", n.id, "metadata", status="verified" if ok else "failed", value=mint, address=nn.address,
                     method="Metaplex metadata update authority" if ok else "", provider="NETWORK on-chain check", requested_by=user.id,
                     detail=(f"Metadata authority verified for ${ticker_of(mint)}. Proves control of the update-authority wallet only." if ok else f"Not verified: {reason}."))
    audit(db, user.id, n.id, "verify.metadata", mint, f"{nn.address} ok={ok}", ip_of(request))
    commit(db)
    return {"verified": ok, "detail": v.detail}


def dev_evidence(mint: str, dev: str) -> dict:
    """Read-only: the original dev wallet's current holding of the token."""
    try:
        b, s = chain.token_balance(dev, mint), chain.token_supply(mint)
        pct = (b["raw"] / s["raw"] * 100) if s["raw"] else 0
        out = {"wallet": dev, "wallet_short": short(dev), "balance": b["ui"], "pct": round(pct, 4)}
        out["summary"] = f"Original dev wallet holds {pct:.2f}% of supply" + (" (holds none now)" if b["raw"] == 0 else "")
        try:
            la = chain.last_activity(dev, mint) if b["accounts"] else None
            out["last_activity"] = la
        except Exception: out["last_activity"] = None
        return out
    except Exception as e:
        return {"wallet": dev, "wallet_short": short(dev), "error": f"Balance lookup unavailable ({str(e)[:60]})"}


@router.get("/api/networks/{slug}/token-trust")
def token_trust(slug: str, mint: str = "", viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if n.is_private and not is_active(membership(db, n.id, viewer.id if viewer else 0)): raise HTTPException(403, "Private Network.")
    dv = db.scalar(select(Verification).where(Verification.subject_type == "network", Verification.subject_id == n.id, Verification.kind == "devwallet").order_by(desc(Verification.id)).limit(1))
    mint = mint if chain.valid_address(mint) else (n.token_address or (dv.value if dv else ""))
    out = {"mint": mint, "devwallet": None, "metadata": None, "domain": None, "dev_evidence": None, "claims": []}
    if dv: out["devwallet"] = {"status": dv.status, "detail": dv.detail, "method": dv.method, "address_short": short(dv.address), "checked_at": iso(dv.decided_at)}
    mv = db.scalar(select(Verification).where(Verification.subject_type == "network", Verification.subject_id == n.id, Verification.kind == "metadata").order_by(desc(Verification.id)).limit(1))
    if mv: out["metadata"] = {"status": mv.status, "detail": mv.detail}
    pv = db.scalar(select(Verification).where(Verification.subject_type == "network", Verification.subject_id == n.id, Verification.kind == "project").order_by(desc(Verification.id)).limit(1))
    if pv: out["domain"] = {"status": pv.status, "detail": pv.detail, "domain": pv.value, "method": pv.method}
    if mint:
        creator = dv.address if dv and dv.status == "verified" else ""
        if not creator:
            try: creator = (chain.cached(f"pc:{mint}", 600, lambda: chain.pump_creator(mint)) or {}).get("creator", "")
            except Exception: creator = ""
        if creator: out["dev_evidence"] = chain.cached(f"ev:{mint}:{creator}", 120, lambda: dev_evidence(mint, creator))
        out["claims"] = claims_for_mint(db, mint)
    return out


# ================================================================= CTO CLAIMS
MIN_BACKERS = lambda: int(os.getenv("CTO_MIN_BACKERS", "10"))
MIN_PCT = lambda: float(os.getenv("CTO_MIN_PCT", "10"))
FLAG_HOURS = 24


class ClaimIn(BaseModel):
    mint: str = Field(min_length=32, max_length=44)


@router.post("/api/networks/{slug}/cto", dependencies=[rate_limit("cto", 10, 3600)])
def create_claim(slug: str, data: ClaimIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = get_network(db, slug); founder_or_settings(db, n, user)
    if not chain.valid_address(data.mint): raise HTTPException(400, "Enter the token's mint address.")
    if db.scalar(select(CtoClaim.id).where(CtoClaim.network_id == n.id, CtoClaim.mint == data.mint)): raise HTTPException(409, "This Network already claims that token.")
    c = CtoClaim(network_id=n.id, mint=data.mint, symbol=ticker_of(data.mint)[:30], created_by=user.id)
    db.add(c)
    audit(db, user.id, n.id, "cto.claim", data.mint, "", ip_of(request))
    commit(db)
    return {"id": c.id, "link": f"#/cto/{c.id}"}


def label_of(c: CtoClaim) -> str:
    if c.verified:
        return f"Community takeover: backed by {c.backers_count} holder wallets holding {c.backed_pct:.2f}% of supply (checked {iso(c.last_checked)})"
    if c.last_checked: return "CTO claim, not enough holder support"
    return "CTO claim, not checked yet"


def evaluate_mint(db, mint: str) -> dict:
    """Live evaluation of every claim on `mint`. Balances are read now, each wallet backs at most one claim (DB unique),
    and curve/pool/program-owned, dev and burned holdings are excluded from both the denominator and the backers."""
    supply = chain.token_supply(mint)
    excluded, excluded_raw = {chain.INCINERATOR}, 0
    try:
        p = chain.pump_creator(mint)
        if p: excluded |= {p["creator"], p["curve"]}
    except Exception: p = None
    for v in db.scalars(select(Verification.address).where(Verification.kind == "devwallet", Verification.value == mint, Verification.status == "verified")):
        excluded.add(v)
    seen_accounts = set()
    for h in chain.largest_holders(mint):
        if h["owner"] in excluded or chain.is_program_owned_address(h["owner"]):
            excluded.add(h["owner"]); excluded_raw += h["raw"]; seen_accounts.add(h["account"])
    for w in [x for x in excluded if x and chain.valid_address(x) and not chain.is_program_owned_address(x)]:
        try:
            b = chain.token_balance(w, mint)
            if not set(b["accounts"]) & seen_accounts: excluded_raw += b["raw"]  # not already counted via largest holders
        except Exception: pass
    circ = max(supply["raw"] - excluded_raw, 1)
    now = utcnow()
    claims = db.scalars(select(CtoClaim).where(CtoClaim.mint == mint, CtoClaim.status == "active")).all()
    results = {}
    for c in claims:
        rows, total_w, distinct, funders, counted_raw = [], 0.0, 0, {}, 0
        for b in db.scalars(select(CtoBacking).where(CtoBacking.claim_id == c.id)):
            row = {"wallet": short(b.wallet), "amount": 0.0, "counted": False, "note": ""}
            if b.wallet in excluded:
                row["note"] = "excluded (dev, curve, pool or burn wallet)"; rows.append(row); continue
            try: bal = chain.token_balance(b.wallet, mint)
            except Exception: row["note"] = "balance lookup failed"; rows.append(row); continue
            row["amount"] = bal["ui"]
            if bal["raw"] <= 0: row["note"] = "holds 0 now"; rows.append(row); continue
            fresh = bool(b.first_seen and (now - aware(b.first_seen)).total_seconds() < FLAG_HOURS * 3600)
            weight = 0.5 if fresh else 1.0
            total_w += bal["raw"] * weight
            if not fresh: distinct += 1
            row.update(counted=True, weight=weight, note="new wallet (<24h): counted at 50%, not toward the wallet minimum" if fresh else "")
            counted_raw += bal["raw"]
            if b.first_funder:
                f = funders.setdefault(b.first_funder, [0, 0]); f[0] += 1; f[1] += bal["raw"]
            rows.append(row)
        pct = total_w / circ * 100
        groups = [v[1] for v in funders.values() if v[0] >= 2]  # 2+ backing wallets funded by the same first funder
        shared = (max(groups) / counted_raw * 100) if groups and counted_raw else 0.0
        c.backers_count, c.backed_pct = distinct, round(pct, 4)
        c.verified = distinct >= MIN_BACKERS() and pct >= MIN_PCT()
        c.last_checked = now
        res = {"backers": rows, "distinct": distinct, "pct": round(pct, 4), "circulating_raw": circ, "supply_raw": supply["raw"],
               "excluded_raw": excluded_raw, "threshold": {"wallets": MIN_BACKERS(), "pct": MIN_PCT()},
               "shared_funder_pct": round(shared, 2), "checked_at": iso(now)}
        c.result = json.dumps(res)
        results[c.id] = res
    commit(db)
    return results


def claims_for_mint(db, mint):
    claims = db.scalars(select(CtoClaim).where(CtoClaim.mint == mint, CtoClaim.status == "active")).all()
    best = max(claims, key=lambda c: (c.backed_pct, c.backers_count), default=None)
    out = []
    for c in claims:
        n = db.get(Network, c.network_id)
        role = "leading claim" if c is best and c.backed_pct > 0 else "competing claim"
        if len(claims) == 1: role = "only claim"
        out.append({"id": c.id, "network": network_brief(n), "verified": c.verified, "label": label_of(c), "role": role,
                    "backers_count": c.backers_count, "backed_pct": c.backed_pct, "last_checked": iso(c.last_checked), "link": f"#/cto/{c.id}"})
    return out


@router.get("/api/cto/{cid}")
def get_claim(cid: int, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    c = db.get(CtoClaim, cid)
    if not c or c.status != "active": raise HTTPException(404, "Claim not found.")
    n = db.get(Network, c.network_id)
    res = json.loads(c.result) if c.result else {}
    dv = db.scalar(select(Verification).where(Verification.kind == "devwallet", Verification.value == c.mint, Verification.status == "verified").limit(1))
    mine = None
    if viewer:
        b = db.scalar(select(CtoBacking).where(CtoBacking.mint == c.mint, CtoBacking.user_id == viewer.id, CtoBacking.claim_id == c.id))
        mine = short(b.wallet) if b else None
    return {"id": c.id, "mint": c.mint, "symbol": c.symbol, "network": network_brief(n), "verified": c.verified, "label": label_of(c),
            "backers_count": c.backers_count, "backed_pct": c.backed_pct, "last_checked": iso(c.last_checked), "result": res,
            "claims": claims_for_mint(db, c.mint), "support_text": f"I support @{n.slug} as the community team for {c.mint}",
            "dev_verification": {"network": network_brief(db.get(Network, dv.subject_id)), "detail": dv.detail} if dv else None,
            "my_backing": mine, "what_it_means": "A CTO label means token holders signed messages backing this team, with balances checked live. "
            "It does not mean the project is safe, and it is not financial advice."}


@router.post("/api/cto/{cid}/back", dependencies=[rate_limit("verify_sig", 20, 600)])
def back_claim(cid: int, data: SignedIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_active(user)
    c = db.get(CtoClaim, cid)
    if not c or c.status != "active": raise HTTPException(404, "Claim not found.")
    nn = consume(db, user, data, "cto_back")
    if nn.subject != str(c.id): commit(db); raise HTTPException(400, "That signature was for a different claim.")
    b = db.scalar(select(CtoBacking).where(CtoBacking.mint == c.mint, CtoBacking.wallet == nn.address))
    switched = bool(b and b.claim_id != c.id)
    if b:
        b.claim_id, b.user_id, b.signature, b.created_at = c.id, user.id, data.signature[:120], utcnow()
    else:
        first_seen, funder = None, ""
        try:
            h = chain.wallet_history(nn.address)
            if h.get("first_seen"):
                from datetime import datetime, timezone
                first_seen = datetime.fromtimestamp(h["first_seen"], timezone.utc)
            funder = h.get("first_funder", "")
        except Exception: pass
        b = CtoBacking(claim_id=c.id, mint=c.mint, wallet=nn.address, user_id=user.id, signature=data.signature[:120], first_seen=first_seen, first_funder=funder)
        db.add(b)
    audit(db, user.id, c.network_id, "cto.back", f"claim:{c.id}", f"{nn.address} switched={switched}", ip_of(request))
    commit(db)
    try: evaluate_mint(db, c.mint)
    except Exception: pass
    return {"ok": True, "switched": switched, "label": label_of(db.get(CtoClaim, c.id))}


@router.post("/api/cto/{cid}/recheck", dependencies=[rate_limit("cto_check", 10, 600)])
def recheck_claim(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(CtoClaim, cid)
    if not c: raise HTTPException(404, "Claim not found.")
    try: evaluate_mint(db, c.mint)
    except Exception as e: raise HTTPException(502, f"On-chain check unavailable right now ({str(e)[:80]}).")
    return get_claim(cid, user, db)


def recheck_all():
    """Periodic re-evaluation (called from the background loop)."""
    from .db import SessionLocal
    with SessionLocal() as db:
        for mint in set(db.scalars(select(CtoClaim.mint).where(CtoClaim.status == "active"))):
            try: evaluate_mint(db, mint)
            except Exception: pass


# ================================================================= SELECTED ACTIVITY SHARING
def activity_out(a, n):
    return {"id": a.id, "type": a.type, "text": a.text, "link": a.link, "created_at": iso(a.created_at), "network": network_brief(n)}


@router.get("/api/networks/{slug}/activity")
def own_activity(slug: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    n = get_network(db, slug)
    if n.is_private and not is_active(membership(db, n.id, viewer.id if viewer else 0)): raise HTTPException(403, "Private Network.")
    return [activity_out(a, n) for a in db.scalars(select(NetworkActivity).where(NetworkActivity.network_id == n.id).order_by(desc(NetworkActivity.id)).limit(30))]


@router.get("/api/activity/connected")
def connected_activity(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Only activity types each connected Network chose to share. Enforced here, not in the UI."""
    my = my_network_ids(db, user.id)
    allowed: dict[int, set] = {}
    if my:
        for c in db.scalars(select(Connection).where(Connection.status == "approved", or_(Connection.requester_id.in_(my), Connection.target_id.in_(my)))):
            for mine, partner in ((c.requester_id, c.target_id), (c.target_id, c.requester_id)):
                if mine in my and partner not in my:
                    allowed.setdefault(partner, set()).update(activity_types_of(c, partner))
    out = []
    for nid, types in allowed.items():
        if not types: continue
        n = db.get(Network, nid)
        out += [activity_out(a, n) for a in db.scalars(select(NetworkActivity).where(NetworkActivity.network_id == nid, NetworkActivity.type.in_(types))
                                                        .order_by(desc(NetworkActivity.id)).limit(20))]
    out.sort(key=lambda x: x["created_at"], reverse=True)
    return out[:50]
