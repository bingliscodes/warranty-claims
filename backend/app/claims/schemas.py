"""Request and response shapes for claims (design §7)."""

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Annotated, Any, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models import ClaimStatus, PhotoKind, Role
from app.photos.labels import DamageLabel

US_STATE_CODES: frozenset[str] = frozenset(
    [
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    ]
)

# 17 characters; letters and digits except I, O and Q.
VIN_PATTERN = r"^[A-HJ-NPR-Z0-9]{17}$"


# --- Reusable field types --------------------------------------------------------


def _blank_to_none(value: Any) -> Any:
    """An optional text field left blank ("" or "  ") is stored as None."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _phone_digits(value: Any) -> Any:
    """'+1 (608) 555-0134' -> '6085550134'. Non-strings pass through for Pydantic to reject.

    Keeps only the digits, then drops a leading 1 from an 11-digit number: US area codes
    never start with 1, so that 1 is the country code (design §7).
    """
    if isinstance(value, str):
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        return digits
    return value


def _strip_upper(value: Any) -> Any:
    """' 1m8gdm9axkp042788 ' -> '1M8GDM9AXKP042788', before the pattern is checked."""
    if isinstance(value, str):
        return value.strip().upper()
    return value


def _known_state(value: str) -> str:
    if value not in US_STATE_CODES:
        raise ValueError("Not a US state code")
    return value


Phone = Annotated[str, BeforeValidator(_phone_digits), StringConstraints(pattern=r"^\d{10}$")]
State = Annotated[str, BeforeValidator(_strip_upper), AfterValidator(_known_state)]
Zip = Annotated[str, StringConstraints(pattern=r"^\d{5}$")]
Vin = Annotated[str, BeforeValidator(_strip_upper), StringConstraints(pattern=VIN_PATTERN)]
# Optional text: "" or "  " is stored as None. Lengths go in Field(None, max_length=...).
OptionalStr = Annotated[str | None, BeforeValidator(_blank_to_none)]
OptionalInt = Annotated[int | None, BeforeValidator(_blank_to_none)]


class _Input(BaseModel):
    # Strip leading and trailing spaces from every string before checking it.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


# --- Submitting a claim -----------------------------------------------------------


class ClaimFormData(_Input):
    """The fields stored in Claim.form_data (design §7)."""

    customer_phone: Phone
    customer_address: str = Field(min_length=1, max_length=200)
    customer_city: str = Field(min_length=1, max_length=100)
    customer_state: State
    customer_zip: Zip
    vehicle_year: int
    vehicle_make: str = Field(min_length=1, max_length=60)
    vehicle_model: str = Field(min_length=1, max_length=60)
    mileage: OptionalInt = Field(None, ge=0, le=2_000_000)
    contract_number: OptionalStr = Field(None, max_length=64)

    @field_validator("vehicle_year")
    @classmethod
    def _plausible_year(cls, year: int) -> int:
        # Next year's models go on sale this year, so allow up to two years ahead.
        latest = datetime.now(UTC).year + 2
        if not 1900 <= year <= latest:
            raise ValueError(f"Year must be between 1900 and {latest}")
        return year


class PhotoRef(_Input):
    """A photo the phone already uploaded, referenced by its storage key."""

    key: str
    kind: PhotoKind
    # Blank becomes None, so a damage photo without a label gets the clearer
    # "needs a description" error rather than "not a label".
    description: Annotated[DamageLabel | None, BeforeValidator(_blank_to_none)] = None
    original_filename: OptionalStr = Field(None, max_length=255)


class ClaimCreate(_Input):
    warranty_company: str = Field(min_length=1, max_length=120)
    customer_first_name: str = Field(min_length=1, max_length=100)
    customer_last_name: str = Field(min_length=1, max_length=100)
    vin: Vin
    claim_number: OptionalStr = Field(None, max_length=64)
    submission_tz: str = Field(min_length=1, max_length=64)
    form_data: ClaimFormData
    photos: Annotated[list[PhotoRef], Field(min_length=2, max_length=60)]

    @field_validator("submission_tz")
    @classmethod
    def _real_time_zone(cls, name: str) -> str:
        try:
            ZoneInfo(name)
        except ZoneInfoNotFoundError, ValueError:
            raise ValueError("Unknown time zone") from None
        return name

    @model_validator(mode="after")
    def _photo_rules(self) -> Self:
        kinds = Counter(photo.kind for photo in self.photos)
        if kinds[PhotoKind.vin] != 1:
            raise ValueError("Exactly one VIN photo is required")
        if kinds[PhotoKind.mileage] > 1:
            raise ValueError("At most one mileage photo is allowed")
        if kinds[PhotoKind.damage] < 1:
            raise ValueError("At least one damage photo is required")
        if any(p.kind == PhotoKind.damage and p.description is None for p in self.photos):
            raise ValueError("Every damage photo needs a description")
        keys = [photo.key for photo in self.photos]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate photo key")
        return self


# --- Responses --------------------------------------------------------------------


class _Output(BaseModel):
    # Lets a response be built straight from a SQLAlchemy object's attributes.
    model_config = ConfigDict(from_attributes=True)


class UserBrief(_Output):
    id: int
    name: str
    role: Role


class ClaimSummary(_Output):
    id: int
    status: ClaimStatus
    created_at: datetime
    warranty_company: str
    customer_first_name: str
    customer_last_name: str
    vin: str
    claim_number: str | None
    owner: UserBrief


class ClaimDetail(ClaimSummary):
    form_data: dict[str, Any]
    submission_tz: str
    updated_at: datetime


class ClaimPage(BaseModel):
    items: list[ClaimSummary]
    total: int
    page: int
    limit: int


class FormOptions(BaseModel):
    """The intake form's dropdown lists (design §8, §14)."""

    damage_labels: list[str]
    warranty_companies: list[str]
