"""Year, make and model for a VIN, from NHTSA's free vPIC service (design §8).

The lookup only prefills the intake form. So every way vPIC can fail becomes one
VinDecodeError, the route answers 503, and the tech types the fields in instead.
"""

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel

from app.auth import get_current_user
from app.claims.schemas import VIN_PATTERN
from app.config import Settings, get_settings
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vin")


class VinDecodeOut(BaseModel):
    year: int | None
    make: str | None
    model: str | None


class VinDecodeError(Exception):
    """vPIC was slow or down, answered with an error status, or sent a body we can't read."""


def get_vpic_client(request: Request) -> httpx.Client:
    """FastAPI dependency: the shared vPIC client that create_app() made."""
    return request.app.state.vpic_client


def decode_vin(vin: str, client: httpx.Client, base_url: str) -> VinDecodeOut:
    try:
        response = client.get(
            f"{base_url}/vehicles/DecodeVinValues/{vin}", params={"format": "json"}
        )
        response.raise_for_status()
        body = response.json()
        results = body["Results"][0]
        year = int(results["ModelYear"]) if results["ModelYear"].isdigit() else None
        make = results["Make"] if results["Make"] != "" else None
        model = results["Model"] if results["Model"] != "" else None

    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        logger.warning("VIN lookup failed (%s)", type(exc).__name__)
        raise VinDecodeError from exc
    return VinDecodeOut(year=year, make=make, model=model)


@router.get("/{vin}/decode", response_model=VinDecodeOut)
def lookup_vin(
    vin: Annotated[str, Path(pattern=VIN_PATTERN)],
    user: User = Depends(get_current_user),
    client: httpx.Client = Depends(get_vpic_client),
    settings: Settings = Depends(get_settings),
) -> VinDecodeOut:
    try:
        decoded_vin = decode_vin(vin, client, settings.VPIC_BASE_URL)
    except VinDecodeError:
        raise HTTPException(status_code=503, detail="VIN lookup unavailable")
    return decoded_vin
