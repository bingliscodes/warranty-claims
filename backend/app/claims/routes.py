from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_reviewer, require_tech
from app.claims.access import get_visible_claim, visible_claims
from app.claims.schemas import ClaimCreate, ClaimDetail, ClaimPage, ClaimUpdate, FormOptions
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Claim, ClaimStatus, User
from app.notifications import notify_reviewers_of_new_claim
from app.photos.attach import attach_photos, delete_uploads
from app.photos.labels import DAMAGE_LABELS
from app.storage import PhotoStorage, get_storage
from app.unread import fill_unread

router = APIRouter(prefix="/api")


# --- Search helpers ---------------------------------------------------------------


def escape_like(text: str) -> str:
    r"""Make % and _ match literally in a LIKE pattern.

    In LIKE, % means "any run of characters" and _ means "any one character". A tech
    searching "AUTH_51" means the underscore itself, so each one gets a backslash in
    front ("AUTH\_51"), and the query says backslash is the escape character:
    column.ilike(f"%{escape_like(q)}%", escape="\\").
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_condition(q: str) -> ColumnElement[bool]:
    """True for claims where q appears, ignoring case, in any of: first name, last name,
    "first last" (so "jane smith" matches), VIN, or claim number.

    Use escape_like() so q's % and _ match literally.
    """
    pattern = f"%{escape_like(q)}%"
    stmt = or_(
        Claim.vin.ilike(pattern, escape="\\"),
        Claim.customer_first_name.ilike(pattern, escape="\\"),
        Claim.customer_last_name.ilike(pattern, escape="\\"),
        (Claim.customer_first_name + " " + Claim.customer_last_name).ilike(pattern, escape="\\"),
        Claim.claim_number.ilike(pattern, escape="\\"),
    )

    return stmt


def warranty_company_names(db: Session) -> list[str]:
    """Every warranty company name used on a claim so far, for the phone's suggestions.

    Name spelling derived from earliest claim ("Assurant" and later "assurant" -> just "Assurant").

    Order: most used first (counting every spelling of a name), alphabetical order tie-breaker.
    """
    name = Claim.warranty_company
    stmt = (
        select(func.array_agg(aggregate_order_by(name, Claim.id))[1])
        .group_by(func.lower(name))
        .order_by(func.count().desc(), func.lower(name))
    )
    return db.scalars(stmt).all()


# --- Routes -----------------------------------------------------------------------


@router.post("/claims", status_code=201, response_model=ClaimDetail)
def create_claim(
    body: ClaimCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_tech),
    db: Session = Depends(get_db),
    storage: PhotoStorage = Depends(get_storage),
) -> Claim:
    claim = Claim(
        owner=user,
        warranty_company=body.warranty_company,
        customer_first_name=body.customer_first_name,
        customer_last_name=body.customer_last_name,
        vin=body.vin,
        claim_number=body.claim_number,
        submission_tz=body.submission_tz,
        form_data=body.form_data.model_dump(),
    )
    db.add(claim)
    db.flush()  # assigns claim.id, which the photos' new keys need
    attach_photos(db, storage, claim, body.photos, user)
    db.commit()
    background_tasks.add_task(
        notify_reviewers_of_new_claim,
        claim.id,
        request.app.state.session_factory,
        settings,
    )
    # Only now that the claim is saved: a failure before this point leaves the
    # originals in place, so the tech's retry still works (design §8).
    delete_uploads(storage, [ref.key for ref in body.photos])
    fill_unread(db, user, [claim])
    return claim


@router.get("/claims", response_model=ClaimPage)
def list_claims(
    q: str | None = None,
    status: ClaimStatus | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClaimPage:
    query = visible_claims(user)
    if status is not None:
        query = query.where(Claim.status == status)
    if q and q.strip():
        query = query.where(search_condition(q.strip()))

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(Claim.created_at.desc(), Claim.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    fill_unread(db, user, items)  # one query for the whole page
    return ClaimPage(items=items, total=total, page=page, limit=limit)


@router.get("/claims/{claim_id}", response_model=ClaimDetail)
def read_claim(
    claim_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Claim:
    claim = get_visible_claim(claim_id, user, db)
    fill_unread(db, user, [claim])
    return claim


@router.patch("/claims/{claim_id}", response_model=ClaimDetail)
def update_claim(
    claim_id: int,
    body: ClaimUpdate,
    user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
) -> Claim:
    claim = get_visible_claim(claim_id, user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(claim, field, value)
    db.commit()
    fill_unread(db, user, [claim])
    return claim


@router.get("/options", response_model=FormOptions)
def form_options(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FormOptions:
    return FormOptions(
        damage_labels=list(DAMAGE_LABELS), warranty_companies=warranty_company_names(db)
    )
