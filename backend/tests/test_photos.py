import io
import zipfile
from datetime import UTC, datetime

import pytest

from app.models import ClaimStatus

NOV_13 = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)


@pytest.fixture
def claim(tech, make_claim, db):
    c = make_claim(tech)  # a VIN photo, then a damage photo labelled "Wheel RF"
    c.created_at = NOV_13
    db.flush()
    return c


def photos_url(claim) -> str:
    return f"/api/claims/{claim.id}/photos"


# --- Listing and reviewer edits ----------------------------------------------------


def test_list_photos_with_urls_and_export_names(reviewer_client, claim):
    photos = reviewer_client.get(photos_url(claim)).json()
    assert [p["kind"] for p in photos] == ["vin", "damage"]
    assert photos[1]["export_filename"] == "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg"
    assert all("claims/" in p["url"] for p in photos)


def test_reviewer_edits_description_and_excludes(reviewer_client, claim):
    damage = claim.photos[1]
    r = reviewer_client.patch(
        f"{photos_url(claim)}/{damage.id}", json={"description": "Wheel RR", "excluded": True}
    )
    assert (r.json()["description"], r.json()["excluded"], r.json()["export_filename"]) == (
        "Wheel RR",
        True,
        None,
    )


def test_excluding_a_photo_keeps_its_label(reviewer_client, claim):
    url = f"{photos_url(claim)}/{claim.photos[1].id}"
    reviewer_client.patch(url, json={"excluded": True})
    r = reviewer_client.patch(url, json={"excluded": False})
    assert (r.json()["description"], r.json()["export_filename"]) == (
        "Wheel RF",
        "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg",
    )


@pytest.mark.parametrize(
    "body",
    [
        {"description": " "},  # a damage photo's label can't be blanked
        {"description": None},
        {"excluded": None},  # null is rejected for every photo field
    ],
)
def test_photo_edit_rejects_blank_or_null(reviewer_client, claim, body):
    damage = claim.photos[1]
    assert reviewer_client.patch(f"{photos_url(claim)}/{damage.id}", json=body).status_code == 422


def test_photo_from_another_claim_is_not_found(tech, reviewer_client, claim, make_claim):
    other_photo = make_claim(tech).photos[1]
    r = reviewer_client.patch(f"{photos_url(claim)}/{other_photo.id}", json={"excluded": True})
    assert r.status_code == 404


def test_tech_cannot_edit_photos(tech_client, claim):
    damage = claim.photos[1]
    r = tech_client.patch(f"{photos_url(claim)}/{damage.id}", json={"excluded": True})
    assert r.status_code == 403


# --- Adding photos after submission ------------------------------------------------


def test_owner_adds_damage_and_missing_mileage(tech, tech_client, claim, put_upload):
    r = tech_client.post(
        photos_url(claim),
        json={
            "photos": [
                {"key": put_upload(tech), "kind": "damage", "description": "Wheel LF"},
                {"key": put_upload(tech), "kind": "mileage"},
            ]
        },
    )
    assert r.status_code == 201
    assert {p["kind"] for p in r.json()} == {"damage", "mileage"}
    again = tech_client.post(
        photos_url(claim), json={"photos": [{"key": put_upload(tech), "kind": "mileage"}]}
    )
    assert again.status_code == 422  # the claim already has a mileage photo


@pytest.mark.parametrize("vin_count", [1, 2])
def test_cannot_add_vin_photo(tech, tech_client, claim, put_upload, vin_count):
    vin_photos = [{"key": put_upload(tech), "kind": "vin"} for _ in range(vin_count)]
    r = tech_client.post(photos_url(claim), json={"photos": vin_photos})
    assert r.status_code == 422


def test_cannot_add_two_mileage_photos_at_once(tech, tech_client, claim, put_upload):
    # The claim has no mileage photo yet, so only PhotoAdd's own rule can catch this.
    mileage = [{"key": put_upload(tech), "kind": "mileage"} for _ in range(2)]
    assert tech_client.post(photos_url(claim), json={"photos": mileage}).status_code == 422


def test_same_key_twice_in_one_add_rejected(tech, tech_client, claim, put_upload):
    twice = {"key": put_upload(tech), "kind": "damage", "description": "Wheel LF"}
    assert tech_client.post(photos_url(claim), json={"photos": [twice, twice]}).status_code == 422


def test_vin_and_mileage_photos_take_no_description(
    tech, tech_client, reviewer_client, claim, put_upload
):
    mileage = {"key": put_upload(tech), "kind": "mileage", "description": "Wheel LF"}
    assert tech_client.post(photos_url(claim), json={"photos": [mileage]}).status_code == 422
    vin_photo = claim.photos[0]
    r = reviewer_client.patch(
        f"{photos_url(claim)}/{vin_photo.id}", json={"description": "Wheel LF"}
    )
    assert r.status_code == 422


def test_add_photo_permissions(
    tech, tech_client, claim, put_upload, reviewer, reviewer_client, make_user, client_for, db
):
    def body(user):
        return {"photos": [{"key": put_upload(user), "kind": "damage", "description": "Wheel LR"}]}

    other = make_user(name="Other Tech")
    assert client_for(other).post(photos_url(claim), json=body(other)).status_code == 404
    assert reviewer_client.post(photos_url(claim), json=body(reviewer)).status_code == 403
    claim.status = ClaimStatus.closed
    db.flush()
    assert tech_client.post(photos_url(claim), json=body(tech)).status_code == 409


# --- Export ------------------------------------------------------------------------


def test_export_zip(tech, tech_client, reviewer_client, claim, put_upload):
    tech_client.post(
        photos_url(claim),
        json={
            "photos": [
                {
                    "key": put_upload(tech, body=b"second"),
                    "kind": "damage",
                    "description": "Wheel RF",
                },
                {
                    "key": put_upload(tech, body=b"third"),
                    "kind": "damage",
                    "description": "Wheel RR",
                },
            ]
        },
    )
    photos = reviewer_client.get(photos_url(claim)).json()
    wheel_rr = next(p for p in photos if p["description"] == "Wheel RR")
    reviewer_client.patch(f"{photos_url(claim)}/{wheel_rr['id']}", json={"excluded": True})

    r = reviewer_client.get(f"{photos_url(claim)}/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert 'filename="ASSURANT.KP042788.SMITH.11.26.zip"' in r.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(r.content))
    assert archive.namelist() == [
        "ASSURANT.KP042788.SMITH.VIN.11.26.jpg",
        "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg",
        "ASSURANT.KP042788.SMITH.Wheel.RF-2.11.26.jpg",
    ]
    assert archive.read("ASSURANT.KP042788.SMITH.Wheel.RF-2.11.26.jpg") == b"second"


def test_tech_cannot_export(tech_client, claim):
    assert tech_client.get(f"{photos_url(claim)}/export").status_code == 403


def test_export_refused_when_everything_excluded(reviewer_client, claim):
    for p in claim.photos:
        reviewer_client.patch(f"{photos_url(claim)}/{p.id}", json={"excluded": True})
    assert reviewer_client.get(f"{photos_url(claim)}/export").status_code == 409
