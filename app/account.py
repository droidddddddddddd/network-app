"""Self-service account deletion (DELETE /api/me).

Removes the user and everything that belongs to them: posts (and replies/likes/reports on them), messages,
memberships, follows, endorsements given and received, opportunities and applications, notifications,
linked X/Google accounts, uploads, verifications/achievements/reputation about them, and any Network they
founded *if they are its only active member*. A founder of a Network that still has other active members
must hand it over or remove the members first, so deleting one account never wipes other people's Network.
A few attribution columns (audit log actor, report resolver, ban lifter, verification requester) are set to
NULL instead of deleting the row, so moderation history about *other* people survives.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, update, func, and_
from sqlalchemy.orm import Session

from .db import get_db
from .models import (Base, User, Network, Membership, Report, Verification, Achievement, ReputationRecord)
from .security import current_user, check_pw, COOKIE, rate_limit

router = APIRouter()

# (table, column) pairs pointing at users.id that are kept with the value nulled out
_NULL_ON_USER_DELETE = {("audit_logs", "actor_id"), ("reports", "resolved_by"), ("network_bans", "lifted_by"),
                        ("verifications", "requested_by"), ("oauth_states", "user_id")}


def _purge(db: Session, table, ids: list[int]):
    """Delete rows `ids` of `table` and, recursively, every row that references them by foreign key."""
    if not ids: return
    for t in Base.metadata.sorted_tables:
        for fk in t.foreign_keys:
            if fk.column.table is not table: continue
            col = fk.parent
            if table.name == "users" and (t.name, col.name) in _NULL_ON_USER_DELETE:
                db.execute(update(t).where(col.in_(ids)).values({col.name: None}))
                continue
            child = [r[0] for r in db.execute(select(t.c.id).where(col.in_(ids)))]
            if t is table: child = [c for c in child if c not in ids]
            _purge(db, t, child)
    db.execute(delete(table).where(table.c.id.in_(ids)))


def _purge_subject(db: Session, kind: str, ids: list[int]):
    if not ids: return
    for M in (Verification, Achievement, ReputationRecord):
        db.execute(delete(M).where(M.subject_type == kind, M.subject_id.in_(ids)))
    db.execute(delete(Report).where(Report.target_type == kind, Report.target_id.in_(ids)))


def delete_account(db: Session, user: User):
    founded = list(db.scalars(select(Network).where(Network.founder_id == user.id)))
    blocked = []
    for n in founded:
        others = db.scalar(select(func.count()).select_from(Membership).where(
            Membership.network_id == n.id, Membership.status == "active", Membership.user_id != user.id))
        if others: blocked.append(n.name)
    if blocked:
        raise HTTPException(409, "You founded Networks that still have other members: " + ", ".join(blocked)
                            + ". Remove those members (or hand the Network over) before deleting your account.")
    nids = [n.id for n in founded]
    _purge_subject(db, "network", nids)
    _purge(db, Network.__table__, nids)
    _purge_subject(db, "user", [user.id])
    _purge(db, User.__table__, [user.id])
    db.commit()


class DeleteAccountIn(BaseModel):
    confirm: str = Field(min_length=1, max_length=40)       # must equal the username
    password: str = Field(default="", max_length=128)        # required when the account has a password


@router.delete("/api/me", dependencies=[rate_limit("delete_account", 5, 3600)])
def delete_me(data: DeleteAccountIn, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.confirm.strip().lstrip("@").lower() != user.username.lower():
        raise HTTPException(400, "Type your username to confirm.")
    from .oauth import has_password
    if has_password(user) and not check_pw(data.password, user.password_hash):
        raise HTTPException(403, "Wrong password.")
    delete_account(db, user)
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
