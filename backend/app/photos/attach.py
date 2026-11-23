import logging
import re
from collections.abc import Iterable

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.claims.schemas import PhotoRef
from app.models import Claim, Photo, User
from app.photos.content_types import EXTENSIONS
from app.storage import PhotoStorage

logger = logging.getLogger(__name__)


def attach_photos(
    db: Session, storage: PhotoStorage, claim: Claim, refs: list[PhotoRef], user: User
) -> list[Photo]:
    """Copy each referenced upload into claims/{claim.id}/ and add a Photo row for it.

    The originals in uploads/ are left alone: the route deletes them with
    delete_uploads() once the commit has succeeded.
    """
    not_found = HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Photo upload not found")
    photo_to_object_info_map = {}
    extensions = "|".join(EXTENSIONS.values())
    upload_key = re.compile(rf"uploads/{user.id}/[0-9a-f]{{32}}\.({extensions})")
    for ref in refs:
        if not upload_key.fullmatch(ref.key):
            raise not_found

        head = storage.head(ref.key)
        if head is None:
            raise not_found
        photo_to_object_info_map[ref.key] = head

    photos = []
    for ref in refs:
        storage_key = storage.copy_to_claim(ref.key, claim.id)
        photo = Photo(
            storage_key=storage_key,
            kind=ref.kind,
            claim=claim,
            description=ref.description,
            original_filename=ref.original_filename,
            added_by=user,
            content_type=photo_to_object_info_map[ref.key].content_type,
        )
        photos.append(photo)
        db.add(photo)
    return photos


def delete_uploads(storage: PhotoStorage, keys: Iterable[str]) -> None:
    """Delete the uploads/ originals after the claim is saved."""
    for key in keys:
        try:
            storage.delete(key)
        except (BotoCoreError, ClientError) as exc:
            logger.warning("Couldn't delete upload %s (%s)", key, type(exc).__name__)
