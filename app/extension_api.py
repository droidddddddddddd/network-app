"""Extension actions reuse the web handlers and their server-side permission checks."""
from fastapi import APIRouter, Depends, Response, Query, HTTPException
from sqlalchemy import select, desc, func, or_
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Post, Call, LinkedAccount
from .security import rate_limit
from .services import visible_filter, posts_out, user_brief, call_out
from .schemas import PostIn
from .extension_auth import optional_extension_user, extension_user

router = APIRouter()


def output_post(p):
    return {**p, "author": p["author"]["username"], "is_demo": bool(p["is_demo"] or p["author"].get("is_demo"))}


@router.get("/api/extension/feed")
def extension_feed(response: Response, tab: str = "discover", before: int | None = None,
                   user: User | None = Depends(optional_extension_user), db: Session = Depends(get_db)):
    from .main import feed
    if tab not in ("network", "discover", "following", "mine"): raise HTTPException(400, "Unknown feed.")
    if tab == "mine":
        if not user: raise HTTPException(401, "Sign in to see your feed.")
        visible, *_ = visible_filter(db, user.id)
        stmt = select(Post).where(visible, Post.author_id == user.id, Post.parent_id.is_(None))
        if before: stmt = stmt.where(Post.id < before)
        rows = posts_out(db, list(db.scalars(stmt.order_by(desc(Post.id)).limit(30))), user.id)
    else:
        rows = feed(tab=tab, before=before, viewer=user, db=db)
    response.headers["Cache-Control"] = "no-store"
    return {"posts": [output_post(p) for p in rows], "scope": "member" if user else "public", "read_only": not bool(user)}


@router.get("/api/extension/networks")
def networks(response: Response, user: User = Depends(extension_user), db: Session = Depends(get_db)):
    from .main import list_networks
    response.headers["Cache-Control"] = "no-store"
    return list_networks(q="", type="", mine=1, viewer=user, db=db)


@router.post("/api/extension/posts", dependencies=[rate_limit("post", 20, 60, new_limit=5), rate_limit("post_day", 300, 86400, new_limit=30)])
def post(data: PostIn, user: User = Depends(extension_user), db: Session = Depends(get_db)):
    from .main import create_post
    return output_post(create_post(data=data, user=user, db=db))


@router.post("/api/extension/posts/{pid}/like", dependencies=[rate_limit("extension_like", 60, 60)])
def like(pid: int, user: User = Depends(extension_user), db: Session = Depends(get_db)):
    from .main import like as web_like
    return web_like(pid=pid, user=user, db=db)


@router.get("/api/extension/posts/{pid}")
def thread(pid: int, user: User = Depends(extension_user), db: Session = Depends(get_db)):
    from .main import get_post
    result = get_post(pid=pid, viewer=user, db=db)
    return {"post": output_post(result["post"]), "replies": [output_post(p) for p in result["replies"]]}


@router.get("/api/extension/context", dependencies=[rate_limit("extension_context", 120, 60)])
def context(response: Response, handle: str = Query(default="", pattern=r"^[A-Za-z0-9_]{0,15}$"),
            symbol: str = Query(default="", pattern=r"^[A-Za-z0-9]{0,12}$"),
            mint: str = Query(default="", pattern=r"^(?:[1-9A-HJ-NP-Za-km-z]{32,44})?$"), db: Session = Depends(get_db)):
    # Always public, even when the extension is signed in: never leak private data onto X pages.
    response.headers["Cache-Control"] = "no-store"
    matches = []
    if handle:
        matches = list(db.scalars(select(User).join(LinkedAccount, LinkedAccount.user_id == User.id)
            .where(LinkedAccount.provider == "x", func.lower(LinkedAccount.handle) == handle.lower()).limit(3)))
    visible, *_ = visible_filter(db, 0)
    filters = []
    if mint: filters.append(Call.token_address == mint)
    elif symbol: filters.append(func.lower(Call.symbol) == symbol.lower())
    elif matches: filters.append(Call.user_id.in_([u.id for u in matches]))
    calls = []
    if filters:
        for c in db.scalars(select(Call).join(Post, Post.id == Call.post_id).where(visible, *filters)
                            .order_by(desc(Call.id)).limit(5)):
            calls.append({**call_out(c), "author": db.get(User, c.user_id).username, "post_id": c.post_id})
    return {"scope": "public", "profiles": [user_brief(u) for u in matches], "calls": calls,
            "query": {"handle": handle, "symbol": symbol, "mint": mint},
            "notice": "Published calls, not executed trades. Cashtags can refer to different tokens; check the mint. No matching record is not a safety assessment."}
