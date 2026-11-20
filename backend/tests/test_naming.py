from datetime import UTC, datetime

import pytest
from app.photos.naming import (
    description_segment,
    export_filename,
    export_filenames,
    submission_month_year,
    upper_segment,
    zip_filename,
)

from app.models import Claim, Photo, PhotoKind

NOV_13 = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)


def test_export_filename_matches_convention():
    assert (
        export_filename(
            warranty_company="Assurant",
            vin="1M8GDM9AXKP042788",
            last_name="Smith",
            description="Wheel.RF",
            created_at=NOV_13,
            tz_name="America/New_York",
            content_type="image/jpeg",
        )
        == "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg"
    )


def test_png_extension():
    assert export_filename(
        warranty_company="Assurant",
        vin="1M8GDM9AXKP042788",
        last_name="Smith",
        description="VIN",
        created_at=NOV_13,
        tz_name="America/New_York",
        content_type="image/png",
    ).endswith(".VIN.11.26.png")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("de la Cruz", "DELACRUZ"),
        ("Muñoz", "MUNOZ"),
        ("O'Brien", "OBRIEN"),
        ("Smith-Jones", "SMITH-JONES"),
        ("CNA National", "CNANATIONAL"),
        ("李", "UNKNOWN"),
    ],
)
def test_upper_segment(raw, expected):
    assert upper_segment(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (" Wheel RF ", "Wheel.RF"),
        ("PDR.LQP", "PDR.LQP"),
        ("door ding / LF", "door.ding.LF"),
        ("rear-bumper_LF", "rear-bumper_LF"),
        ("--Wheel RF..", "Wheel.RF"),
        ("///", ""),
    ],
)
def test_description_segment(raw, expected):
    assert description_segment(raw) == expected


@pytest.mark.parametrize(
    "utc, tz, expected",
    [
        (datetime(2026, 12, 1, 3, 30, tzinfo=UTC), "America/New_York", ("11", "26")),
        (datetime(2026, 12, 1, 3, 30, tzinfo=UTC), "America/Los_Angeles", ("11", "26")),
        (datetime(2026, 12, 1, 3, 30, tzinfo=UTC), "UTC", ("12", "26")),
        (datetime(2027, 1, 1, 4, 59, tzinfo=UTC), "America/New_York", ("12", "26")),
    ],
)
def test_month_follows_submission_time_zone(utc, tz, expected):
    assert submission_month_year(utc, tz) == expected


def build_claim(*damage, excluded=()):
    claim = Claim(
        id=1,
        warranty_company="Assurant",
        customer_last_name="Smith",
        vin="1M8GDM9AXKP042788",
        created_at=NOV_13,
        submission_tz="America/New_York",
    )
    photos = [
        Photo(id=20, kind=PhotoKind.mileage, content_type="image/jpeg", excluded=False),
        Photo(id=10, kind=PhotoKind.vin, content_type="image/jpeg", excluded=False),
    ]
    for photo_id, desc in enumerate(damage, start=11):
        photos.append(
            Photo(
                id=photo_id,
                kind=PhotoKind.damage,
                description=desc,
                content_type="image/jpeg",
                excluded=photo_id in excluded,
            )
        )
    claim.photos = photos
    return claim


def test_export_filenames_defaults_dedupes_and_skips_excluded():
    assert export_filenames(build_claim("Wheel.RF", "wheel.rf", "PDR.LQP", excluded={13})) == {
        10: "ASSURANT.KP042788.SMITH.VIN.11.26.jpg",
        20: "ASSURANT.KP042788.SMITH.Mileage.11.26.jpg",
        11: "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg",
        12: "ASSURANT.KP042788.SMITH.wheel.rf-2.11.26.jpg",
    }


def test_zip_filename():
    assert zip_filename(build_claim("Wheel.RF")) == "ASSURANT.KP042788.SMITH.11.26.zip"


def damage_names(claim):
    """Just the damage photos' filenames, in id order."""
    names = export_filenames(claim)
    return [names[photo.id] for photo in claim.photos if photo.kind == PhotoKind.damage]


def test_duplicate_suffix_counts_up_past_taken_names():
    claim = build_claim("Wheel.RF", "Wheel.RF", "Wheel.RF-2", "WHEEL.RF")
    assert damage_names(claim) == [
        "ASSURANT.KP042788.SMITH.Wheel.RF.11.26.jpg",
        "ASSURANT.KP042788.SMITH.Wheel.RF-2.11.26.jpg",
        "ASSURANT.KP042788.SMITH.Wheel.RF-2-2.11.26.jpg",
        "ASSURANT.KP042788.SMITH.WHEEL.RF-3.11.26.jpg",
    ]


def test_description_that_cleans_to_nothing_exports_as_damage():
    claim = build_claim("///", "李", "damage")
    assert damage_names(claim) == [
        "ASSURANT.KP042788.SMITH.Damage.11.26.jpg",
        "ASSURANT.KP042788.SMITH.Damage-2.11.26.jpg",
        "ASSURANT.KP042788.SMITH.damage-3.11.26.jpg",
    ]
