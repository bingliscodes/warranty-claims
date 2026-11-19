import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Claim, ClaimRead, ClaimStatus, Photo, PhotoKind, Role, User


def make_claim(db):
    tech = User(name="Tess Tech", role=Role.tech)
    claim = Claim(
        owner=tech,
        warranty_company="Assurant",
        customer_first_name="Jane",
        customer_last_name="Smith",
        vin="1M8GDM9AXKP042788",
        submission_tz="America/New_York",
        form_data={"customer_zip": "27519", "vehicle_year": 2024},
    )
    db.add(claim)
    db.flush()
    return claim


def test_claim_defaults_and_form_data_round_trip(db):
    claim = make_claim(db)
    db.expire_all()
    loaded = db.get(Claim, claim.id)
    assert loaded.status == ClaimStatus.submitted
    assert loaded.form_data == {"customer_zip": "27519", "vehicle_year": 2024}
    assert loaded.created_at.tzinfo is not None
    assert loaded.claim_number is None


def test_photo_storage_key_is_unique(db):
    claim = make_claim(db)
    for _ in range(2):
        db.add(
            Photo(
                claim=claim,
                kind=PhotoKind.damage,
                storage_key="claims/1/a.jpg",
                content_type="image/jpeg",
                description="Wheel.RF",
                added_by=claim.owner,
            )
        )
    with pytest.raises(IntegrityError):
        db.flush()


def test_one_read_state_per_user_and_claim(db):
    claim = make_claim(db)
    db.add_all(
        [
            ClaimRead(user_id=claim.owner_id, claim_id=claim.id),
            ClaimRead(user_id=claim.owner_id, claim_id=claim.id),
        ]
    )
    with pytest.raises(IntegrityError):
        db.flush()
