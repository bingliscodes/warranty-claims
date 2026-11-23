"""Who can see which claims (design §5): a tech sees only their own, a reviewer sees all."""

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Claim, Role, User


def visible_claims(user: User) -> Select[tuple[Claim]]:
    """A query for the claims this user may see. The list route adds search, filters,
    sorting and paging on top of it.

    - reviewer: every claim
    - tech: only claims where they're the owner
    """
    stmt = select(Claim)

    if user.role != Role.reviewer:
        stmt = stmt.where(Claim.owner_id == user.id)

    return stmt


def get_visible_claim(claim_id: int, user: User, db: Session) -> Claim:
    """The claim, if this user may see it.

    Raises HTTPException 404 {"detail": "Claim not found"} when the claim doesn't exist,
    or when the user is a tech who doesn't own it. A tech gets 404 rather than 403, so
    they can't tell someone else's claim from one that doesn't exist.
    """

    stmt = visible_claims(user).where(Claim.id == claim_id)

    claim = db.scalar(stmt)

    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    return claim
