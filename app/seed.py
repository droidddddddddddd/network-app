"""Demo data. Run: python -m app.seed  (idempotent: skips if demo users exist). Everything is flagged is_demo."""
from datetime import timedelta
from sqlalchemy import select
from .db import SessionLocal
from .models import (User, Follow, Network, Membership, Connection, Post, Like, Endorsement, Opportunity, Application,
                     Call, Event, ChatMessage, now)
from .security import hash_pw
from . import dex

PW = "demo1234"
USERS = [
    ("alpha_annie", "Annie (Alpha)", "Researcher", "On-chain research, Solana memes & infra.", "Alpha Communities,Research,Trading"),
    ("solsurfer", "Sol Surfer", "Trader", "Swing trader. Liquidity first, narrative second.", "Trading,Alpha Communities"),
    ("buildooor", "Dev Dana", "Developer", "Rust/Anchor dev building Solana tooling.", "Project,Development"),
    ("kol_kai", "Kai", "KOL", "Spaces host, 40k on X. Honest reviews only.", "KOL,Marketing,Promotion"),
    ("mkt_mia", "Mia Marketing", "Marketer", "Growth for web3 launches.", "Marketing,Promotion"),
    ("founder_fin", "Fin", "Founder", "Founder @ OrbitPay (pre-launch).", "Project,Partnership,Investment"),
]


def run():
    import os
    if os.getenv("ENV") == "production" and os.getenv("SEED_DEMO", "").lower() != "true":
        raise SystemExit("Refusing to load demo data in production. Set SEED_DEMO=true to override.")
    db = SessionLocal()
    if db.scalar(select(User).where(User.username == "alpha_annie")):
        print("demo data already present"); return
    t = now()
    U = {}
    for un, dn, role, bio, ints in USERS:
        u = User(username=un, email=f"{un}@example.com", password_hash=hash_pw(PW), display_name=dn, bio=bio, role=role, interests=ints,
                 x_handle=un.replace("_", "")[:15], is_demo=True, created_at=t - timedelta(days=40))
        db.add(u); U[un] = u
    db.flush()
    nets = [("annies-alpha", "Annie's Alpha", "Alpha Communities", "alpha_annie", False, "Research-first alpha. Calls tracked with DexScreener."),
            ("sol-traders", "Sol Traders Desk", "Trading", "solsurfer", False, "Trade ideas, risk management, post-mortems."),
            ("kai-circle", "Kai's Circle", "KOL", "kol_kai", False, "KOL collabs and honest reviews."),
            ("launch-lab", "Launch Lab Marketing", "Marketing", "mkt_mia", False, "Marketing playbooks for launches."),
            ("orbitpay", "OrbitPay", "Project", "founder_fin", False, "Solana Pay checkout for creators. Launch room open."),
            ("dana-builds", "Dana Builds", "Personal", "buildooor", False, "My personal Network: dev logs."),
            ("inner-desk", "Inner Desk (private)", "Trading", "solsurfer", True, "Private desk. Request to join.")]
    N = {}
    for slug, name, typ, founder, priv, desc in nets:
        n = Network(slug=slug, name=name, type=typ, description=desc, is_private=priv, founder_id=U[founder].id, is_demo=True,
                    created_at=t - timedelta(days=30))
        if typ == "Project":
            n.stage = "Community"; n.launch_at = t + timedelta(days=21)
            n.team_info = "Fin (founder), Dana (smart contracts)"; n.roadmap = "Q1: beta\nQ2: merchant SDK\nQ3: mainnet launch"
        db.add(n); N[slug] = n
    db.flush()

    def mem(slug, un, role="member", days=20, status="active"):
        db.add(Membership(network_id=N[slug].id, user_id=U[un].id, role=role, status=status, joined_at=t - timedelta(days=days) if status == "active" else None))
    for slug, _, _, founder, _, _ in nets: mem(slug, founder, "founder", 30)
    for slug, uns in {"annies-alpha": ["solsurfer", "kol_kai", "buildooor", "mkt_mia"], "sol-traders": ["alpha_annie", "kol_kai", "founder_fin"],
                      "kai-circle": ["mkt_mia", "alpha_annie", "founder_fin"], "launch-lab": ["kol_kai", "founder_fin", "alpha_annie"],
                      "orbitpay": ["buildooor", "mkt_mia", "alpha_annie", "kol_kai"], "dana-builds": ["founder_fin"], "inner-desk": ["alpha_annie"]}.items():
        for i, un in enumerate(uns): mem(slug, un, "admin" if i == 0 and slug in ("annies-alpha", "orbitpay") else "member", 25 - i * 5)
    mem("inner-desk", "kol_kai", status="pending")
    db.add(Connection(requester_id=N["annies-alpha"].id, target_id=N["sol-traders"].id, requested_by=U["alpha_annie"].id, status="approved",
                      message="Research + execution", decided_at=t - timedelta(days=10), req_share_announcements=True, tgt_share_announcements=True,
                      req_share_opportunities=True, tgt_share_opportunities=True, req_display_public=True, tgt_display_public=True, req_share_events=True, tgt_share_events=True))
    db.add(Connection(requester_id=N["orbitpay"].id, target_id=N["launch-lab"].id, requested_by=U["founder_fin"].id, status="approved",
                      decided_at=t - timedelta(days=5), req_share_announcements=True, tgt_share_announcements=True, req_share_opportunities=True,
                      tgt_share_opportunities=True, req_display_public=True, tgt_display_public=True, req_share_selected=True, tgt_share_selected=True))
    db.add(Connection(requester_id=N["kai-circle"].id, target_id=N["orbitpay"].id, requested_by=U["kol_kai"].id, status="pending",
                      message="Want to cover your launch", req_share_announcements=True))
    for a, b in [("solsurfer", "alpha_annie"), ("kol_kai", "alpha_annie"), ("alpha_annie", "buildooor"), ("mkt_mia", "founder_fin"), ("buildooor", "founder_fin")]:
        db.add(Follow(follower_id=U[a].id, followee_id=U[b].id))
    posts = [("alpha_annie", "annies-alpha", "announcement", "Weekly research call Thursday. Bring one thesis and one risk. #research", True),
             ("alpha_annie", None, "post", "Liquidity > hype. Before any call I check LP depth, holder concentration and dev wallet activity. $SOL", False),
             ("solsurfer", "sol-traders", "post", "Post-mortem on last week: sized too big on a thin pool. Rule: max 1% of pool liquidity. #risk", False),
             ("founder_fin", "orbitpay", "announcement", "OrbitPay beta is live for 20 creators. Looking for marketing partners. See Opportunities.", True),
             ("buildooor", "dana-builds", "update", "Shipped the Anchor program for escrowed payouts. Tests green.", True),
             ("kol_kai", "kai-circle", "post", "I only cover projects I've used myself. DM if you want an honest review.", False),
             ("mkt_mia", "launch-lab", "announcement", "New playbook: 30-day pre-launch community plan. #marketing", True),
             ("solsurfer", "inner-desk", "post", "Private desk note: watching SOL majors only this week.", False)]
    P = []
    for i, (un, slug, kind, body, share) in enumerate(posts):
        p = Post(author_id=U[un].id, network_id=N[slug].id if slug else None, kind=kind, body=body, share_with_connections=share,
                 tags=" ".join(w.lower() for w in body.split() if w[:1] in "#$"), is_demo=True, created_at=t - timedelta(hours=30 - i * 3))
        db.add(p); P.append(p)
    db.flush()
    db.add(Post(author_id=U["solsurfer"].id, parent_id=P[1].id, body="Same checklist here, plus I check the top 10 holders.", is_demo=True))
    for un in ["solsurfer", "kol_kai", "buildooor"]: db.add(Like(user_id=U[un].id, post_id=P[1].id))
    db.add(Like(user_id=U["mkt_mia"].id, post_id=P[3].id))
    for a, b, cat, note in [("solsurfer", "alpha_annie", "Research", "Her pre-call checklists saved me twice."), ("kol_kai", "alpha_annie", "Trading research", ""),
                            ("buildooor", "alpha_annie", "Reliability", ""), ("alpha_annie", "solsurfer", "Trading research", "Great post-mortems."),
                            ("founder_fin", "buildooor", "Development", "Shipped escrow on time."), ("mkt_mia", "kol_kai", "Marketing", ""),
                            ("alpha_annie", "buildooor", "Collaboration", "")]:
        db.add(Endorsement(from_id=U[a].id, to_id=U[b].id, category=cat, note=note, basis="shared network"))
    o1 = Opportunity(creator_id=U["founder_fin"].id, network_id=N["orbitpay"].id, category="Marketing", title="Launch marketing partner for OrbitPay",
                     description="We need a marketing lead for our 30-day pre-launch campaign: content calendar, KOL outreach and community events.",
                     requirements="2+ Solana launches. Portfolio links.", compensation="3,000 USDC + bonus", deadline=t + timedelta(days=14), is_demo=True)
    o2 = Opportunity(creator_id=U["buildooor"].id, category="Development", title="Anchor auditor for review (paid)",
                     description="Looking for a second pair of eyes on an escrow program (~600 lines). Written report expected.",
                     compensation="", negotiable=True, deadline=t + timedelta(days=10), is_demo=True)
    o3 = Opportunity(creator_id=U["kol_kai"].id, network_id=N["kai-circle"].id, category="KOL", title="Co-host for weekly Spaces",
                     description="Co-host weekly Solana ecosystem Spaces. Must be comfortable doing live Q&A with founders.", compensation="Rev share", is_demo=True)
    o4 = Opportunity(creator_id=U["alpha_annie"].id, network_id=N["annies-alpha"].id, category="Research", title="Research analyst (part-time)",
                     description="Write two deep-dive reports a month on early Solana projects. Methodology over hype.", compensation="1,500 USDC / month",
                     deadline=t + timedelta(days=20), is_demo=True)
    db.add_all([o1, o2, o3, o4]); db.flush()
    db.add(Application(opportunity_id=o1.id, applicant_id=U["mkt_mia"].id, kind="application", status="accepted",
                       message="Ran pre-launch for 3 Solana projects; playbook in Launch Lab."))
    db.add(Application(opportunity_id=o1.id, applicant_id=U["kol_kai"].id, kind="interest", status="pending"))
    db.add(Application(opportunity_id=o4.id, applicant_id=U["solsurfer"].id, kind="application", status="completed", message="Happy to cover trading-side research."))
    db.add(Event(network_id=N["annies-alpha"].id, created_by=U["alpha_annie"].id, title="Thursday research call", description="Bring a thesis.",
                 starts_at=t + timedelta(days=3), is_public=True, is_demo=True))
    db.add(Event(network_id=N["orbitpay"].id, created_by=U["founder_fin"].id, title="OrbitPay community AMA", starts_at=t + timedelta(days=7), is_public=True, is_demo=True))
    for un, body in [("alpha_annie", "gm! research call notes are pinned"), ("solsurfer", "thanks, reading now"), ("kol_kai", "anyone covering the new LST?")]:
        db.add(ChatMessage(network_id=N["annies-alpha"].id, user_id=U[un].id, body=body))
    try:
        toks = dex.trending(4)
    except Exception as e:  # network unavailable: skip calls
        print("DexScreener unavailable, skipping demo calls:", e); toks = []
    for tok, un in zip(toks, ["alpha_annie", "solsurfer", "alpha_annie", "kol_kai"]):
        db.add(Call(user_id=U[un].id, network_id=N["annies-alpha"].id if un == "alpha_annie" else None, token_address=tok["address"], symbol=tok["symbol"],
                    name=tok["name"], notes="Demo call (entry = live DexScreener price at seed time).", entry_price=tok["price"], entry_mcap=tok["mcap"],
                    entry_liquidity=tok["liquidity"], current_price=tok["price"], current_mcap=tok["mcap"], current_liquidity=tok["liquidity"],
                    peak_price=tok["price"], is_demo=True))
    db.commit()
    print(f"seeded {len(U)} users, {len(N)} networks, {len(toks)} calls. Log in as alpha_annie / {PW}")


if __name__ == "__main__":
    run()
