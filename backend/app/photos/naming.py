import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import Claim, Photo, PhotoKind
from app.photos.content_types import EXTENSIONS


def upper_segment(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode()
    text = text.upper()
    text = re.sub(r"[^A-Z0-9-]", "", text)
    return text or "UNKNOWN"


def description_segment(value: str) -> str:
    text = value.replace(" ", ".")
    return text


def submission_month_year(created_at: datetime, tz_name: str) -> tuple[str, str]:
    """Two-digit month and year of the submission, in the tech's time zone."""
    local = created_at.astimezone(ZoneInfo(tz_name))
    return f"{local.month:02d}", f"{local.year % 100:02d}"


def export_filename(
    *,
    warranty_company: str,
    vin: str,
    last_name: str,
    description: str,
    created_at: datetime,
    tz_name: str,
    content_type: str,
) -> str:
    """The one place the filename pattern lives. `description` is used as given."""
    month, year = submission_month_year(created_at, tz_name)
    parts = [
        upper_segment(warranty_company),
        vin[-8:],
        upper_segment(last_name),
        description,
        month,
        year,
    ]
    return ".".join(parts) + "." + EXTENSIONS[content_type]


KIND_ORDER = {PhotoKind.vin: 0, PhotoKind.mileage: 1, PhotoKind.damage: 2}


def _base_description(photo: Photo) -> str:
    if photo.kind == PhotoKind.vin:
        return "VIN"
    if photo.kind == PhotoKind.mileage:
        return "Mileage"
    return description_segment(photo.description)


def export_filenames(claim: Claim) -> dict[int, str]:
    photos = [p for p in claim.photos if not p.excluded]
    photos = sorted(photos, key=lambda p: (KIND_ORDER[p.kind], p.id))

    taken: set[str] = set()
    names: dict[int, str] = {}

    for photo in photos:
        base = _base_description(photo)

        if base not in taken:
            description = base
        else:
            photo_count = 2
            while f"{base}-{photo_count}" in taken:
                photo_count += 1
            description = f"{base}-{photo_count}"

        taken.add(description)

        names[photo.id] = export_filename(
            warranty_company=claim.warranty_company,
            vin=claim.vin,
            last_name=claim.customer_last_name,
            description=description,
            created_at=claim.created_at,
            tz_name=claim.submission_tz,
            content_type=photo.content_type,
        )
    return names


def zip_filename(claim: Claim) -> str:
    month, year = submission_month_year(claim.created_at, claim.submission_tz)
    parts = [
        upper_segment(claim.warranty_company),
        claim.vin[-8:],
        upper_segment(claim.customer_last_name),
        month,
        year,
    ]
    return ".".join(parts) + ".zip"
