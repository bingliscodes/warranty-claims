import uuid

import pytest
from botocore.exceptions import ClientError

from app.models import Claim, Photo


def storage_error(operation: str) -> ClientError:
    """What boto3 raises when S3 answers with an error, for example while it's down."""
    return ClientError({"Error": {"Code": "503", "Message": "Service Unavailable"}}, operation)


def test_tech_submits_claim(tech_client, claim_payload, tech, storage, db):
    payload = claim_payload(tech)
    payload["vin"] = " 1m8gdm9axkp042788 "
    r = tech_client.post("/api/claims", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "submitted" and body["vin"] == "1M8GDM9AXKP042788"
    assert body["form_data"]["customer_phone"] == "6085550134"
    assert body["owner"]["id"] == tech.id
    photos = db.query(Photo).filter_by(claim_id=body["id"]).all()
    assert {p.kind for p in photos} == {"vin", "damage"}
    assert all(p.storage_key.startswith(f"claims/{body['id']}/") for p in photos)
    assert storage.head(payload["photos"][0]["key"]) is None


def test_reviewer_cannot_submit(reviewer_client, claim_payload, reviewer):
    assert reviewer_client.post("/api/claims", json=claim_payload(reviewer)).status_code == 403


@pytest.mark.parametrize(
    "field, value",
    [
        ("vin", "1M8GDM9AXKPO42788"),
        ("vin", "1M8GDM9AXKP04278"),
        ("warranty_company", ""),
        ("submission_tz", "Mars/Olympus"),
    ],
)
def test_top_level_validation(tech_client, claim_payload, tech, field, value):
    payload = claim_payload(tech)
    payload[field] = value
    assert tech_client.post("/api/claims", json=payload).status_code == 422


@pytest.mark.parametrize(
    "field, value",
    [
        ("customer_zip", "2751"),
        ("customer_state", "XX"),
        ("customer_phone", "608555013"),
        ("customer_phone", "2 (608) 555-0134"),  # 11 digits, but the first isn't a country code
        ("vehicle_year", 1899),
        ("customer_city", ""),
    ],
)
def test_form_validation(tech_client, claim_payload, tech, field, value):
    payload = claim_payload(tech)
    payload["form_data"][field] = value
    assert tech_client.post("/api/claims", json=payload).status_code == 422


def test_phone_country_code_is_dropped(tech_client, claim_payload, tech):
    # Design §7: iPhone autofill adds +1. US area codes never start with 1, so it's dropped.
    payload = claim_payload(tech)
    payload["form_data"]["customer_phone"] = "+1 (608) 555-0134"
    r = tech_client.post("/api/claims", json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["form_data"]["customer_phone"] == "6085550134"


def test_photo_rules(tech_client, claim_payload, tech, put_upload):
    def post(photos):
        payload = claim_payload(tech)
        payload["photos"] = photos
        return tech_client.post("/api/claims", json=payload).status_code

    def vin():
        return {"key": put_upload(tech), "kind": "vin"}

    def damage(description="Wheel RF"):
        return {"key": put_upload(tech), "kind": "damage", "description": description}

    def mileage():
        return {"key": put_upload(tech), "kind": "mileage"}

    assert post([damage(), damage()]) == 422  # no VIN photo
    assert post([vin(), vin(), damage()]) == 422  # two VIN photos
    assert post([vin(), mileage()]) == 422  # no damage photo
    assert post([vin(), damage("  ")]) == 422  # blank description
    assert post([vin(), damage("Door LF")]) == 422  # not a damage label (design §8)
    assert post([vin(), mileage(), mileage(), damage()]) == 422  # two mileage photos
    twice = damage()
    assert post([vin(), twice, twice]) == 422  # same key twice (design §8)
    assert post([vin(), mileage(), damage()]) == 201


def test_forged_or_reused_photo_keys_rejected(
    tech_client, claim_payload, tech, make_user, put_upload, storage, db
):
    other = make_user(name="Other Tech")
    first = claim_payload(tech)
    assert tech_client.post("/api/claims", json=first).status_code == 201
    for bad_key in [
        put_upload(other),  # someone else's upload
        f"uploads/{tech.id}/{uuid.uuid4().hex}.jpg",  # the right shape, but never uploaded
        first["photos"][0]["key"],  # already attached to the first claim
    ]:
        payload = claim_payload(tech)
        payload["photos"][1]["key"] = bad_key
        assert tech_client.post("/api/claims", json=payload).status_code == 422
        assert storage.head(payload["photos"][0]["key"]) is not None  # nothing was moved
    assert db.query(Claim).count() == 1


def test_odd_photo_keys_rejected_before_storage_is_asked(
    tech_client, claim_payload, tech, make_user, put_upload, storage, monkeypatch
):
    # Design §8: a key must have the exact shape the upload route hands out. Dev storage
    # (SeaweedFS) answers 400 to a key with "..", which would come back as a 500, so odd
    # keys are turned away before storage is asked about them.
    other_upload = put_upload(make_user(name="Other Tech"))  # uploads/{other id}/{hex}.jpg
    odd_keys = [
        # climbs out of the tech's folder into the other tech's
        f"uploads/{tech.id}/../{other_upload.removeprefix('uploads/')}",
        # in the tech's folder, but not a name the upload route makes
        f"uploads/{tech.id}/photo.jpg",
    ]
    asked = []
    real_head = storage.head

    def head_and_note(key):
        asked.append(key)
        return real_head(key)

    monkeypatch.setattr(storage, "head", head_and_note)
    for key in odd_keys:
        payload = claim_payload(tech)
        payload["photos"][1]["key"] = key
        assert tech_client.post("/api/claims", json=payload).status_code == 422
    assert not set(odd_keys) & set(asked)


def test_copy_failure_saves_nothing_and_retry_works(
    tech_client, claim_payload, tech, storage, db, monkeypatch
):
    # Design §8, "Copy now, delete later": if storage fails partway through submit, no
    # claim is saved and the originals stay in uploads/, so the tech can just submit again.
    payload = claim_payload(tech)
    real_copy = storage.copy_to_claim
    copied = []

    def copy_then_fail(upload_key, claim_id):
        if copied:  # the first photo copies; storage goes down on the second
            raise storage_error("CopyObject")
        copied.append(upload_key)
        return real_copy(upload_key, claim_id)

    monkeypatch.setattr(storage, "copy_to_claim", copy_then_fail)
    with pytest.raises(ClientError):  # a real server would answer 500
        tech_client.post("/api/claims", json=payload)
    assert db.query(Claim).count() == 0
    assert all(storage.head(photo["key"]) is not None for photo in payload["photos"])

    monkeypatch.setattr(storage, "copy_to_claim", real_copy)  # storage is back
    assert tech_client.post("/api/claims", json=payload).status_code == 201


def test_cleanup_failure_still_saves_claim(
    tech_client, claim_payload, tech, storage, monkeypatch, caplog
):
    # Design §8: once the claim is saved, failing to delete the uploads/ originals doesn't
    # fail submit (uploads/ expires after 7 days anyway). It's logged, not silent.
    def delete_fails(_key):
        raise storage_error("DeleteObject")

    monkeypatch.setattr(storage, "delete", delete_fails)
    assert tech_client.post("/api/claims", json=claim_payload(tech)).status_code == 201
    assert "Couldn't delete upload" in caplog.text
