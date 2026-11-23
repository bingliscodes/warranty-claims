"""A claim's photos after submission: list, add, edit and export (design §9, §12)."""

import zipfile
from collections.abc import Iterator
from tempfile import SpooledTemporaryFile
from typing import IO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_reviewer, require_tech
from app.claims.access import get_visible_claim
from app.claims.schemas import PhotoAdd, PhotoOut, PhotoRef, PhotoUpdate, UserBrief
from app.db import get_db
from app.models import Claim, ClaimStatus, Photo, PhotoKind, User
from app.photos.attach import attach_photos, delete_uploads
from app.photos.naming import KIND_ORDER, export_filenames, zip_filename
from app.storage import PhotoStorage, get_storage

router = APIRouter(prefix="/api/claims/{claim_id}/photos")

# The zip is built in memory up to this size, then spills over to a temporary file on disk.
ZIP_MEMORY_LIMIT = 32 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


# --- Rules that need the saved claim (design §8) ---------------------------------


def check_claim_accepts(claim: Claim, refs: list[PhotoRef]) -> None:
    """Raise HTTPException if this claim can't take these photos right now.

    Runs after PhotoAdd's own rules have passed
    """
    if claim.status == ClaimStatus.closed:
        raise HTTPException(409, "Claim is closed")

    sends_mileage = any(r.kind == PhotoKind.mileage for r in refs)
    has_mileage = any(p.kind == PhotoKind.mileage for p in claim.photos)
    if sends_mileage and has_mileage:
        raise HTTPException(422, "This claim already has a mileage photo")


def check_photo_edit(photo: Photo, body: PhotoUpdate) -> None:
    """Raise HTTPException 422 if this edit doesn't fit the photo's kind (design §12)."""
    if photo.kind in [PhotoKind.mileage, PhotoKind.vin] and body.description is not None:
        raise HTTPException(422, "Can only add description to damage photos")


# --- Helpers ----------------------------------------------------------------------


def to_photo_out(photo: Photo, storage: PhotoStorage, names: dict[int, str]) -> PhotoOut:
    """names is export_filenames(claim): every photo's name is worked out together,
    because a repeated label's -2 depends on the photos before it."""
    return PhotoOut(
        id=photo.id,
        kind=photo.kind,
        description=photo.description,
        excluded=photo.excluded,
        original_filename=photo.original_filename,
        added_by=UserBrief.model_validate(photo.added_by),
        created_at=photo.created_at,
        url=storage.presign_download(photo.storage_key),
        export_filename=names.get(photo.id),  # excluded photos have no name
    )


def get_claim_photo(claim: Claim, photo_id: int) -> Photo:
    """The photo, if it belongs to this claim. A photo ID from another claim is a 404,
    so the URL's claim always matches the photo being changed."""
    for photo in claim.photos:
        if photo.id == photo_id:
            return photo
    raise HTTPException(404, "Photo not found")


def build_zip(claim: Claim, names: dict[int, str], storage: PhotoStorage) -> IO[bytes]:
    """Write every named photo into a zip, and return the file rewound to the start.

    The whole zip is built before the first byte is sent. If storage fails partway, the
    reviewer gets an error rather than a download that looks fine but is cut short.
    Photos are already compressed (JPEG, PNG), so entries are stored as they are
    (ZIP_STORED) rather than compressed again for no gain.
    """
    photos = {photo.id: photo for photo in claim.photos}
    # Not a `with` block: the file must stay open after this returns, while the response
    # streams it. read_and_close() closes it, and the except below closes it on failure.
    archive = SpooledTemporaryFile(max_size=ZIP_MEMORY_LIMIT)  # noqa: SIM115
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
            for photo_id, name in names.items():
                with zf.open(name, "w") as entry:
                    for chunk in storage.iter_object(photos[photo_id].storage_key, CHUNK_SIZE):
                        entry.write(chunk)
    except BaseException:
        archive.close()
        raise
    archive.seek(0)
    return archive


def read_and_close(file: IO[bytes]) -> Iterator[bytes]:
    """Hand the file out a chunk at a time, then close it (deleting it if on disk)."""
    try:
        while chunk := file.read(CHUNK_SIZE):
            yield chunk
    finally:
        file.close()


# --- Routes -----------------------------------------------------------------------


@router.get("", response_model=list[PhotoOut])
def list_photos(
    claim_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: PhotoStorage = Depends(get_storage),
) -> list[PhotoOut]:
    claim = get_visible_claim(claim_id, user, db)
    names = export_filenames(claim)
    # The same order as the export: VIN, then mileage, then damage, each oldest first.
    photos = sorted(claim.photos, key=lambda p: (KIND_ORDER[p.kind], p.id))
    return [to_photo_out(photo, storage, names) for photo in photos]


@router.post("", status_code=201, response_model=list[PhotoOut])
def add_photos(
    claim_id: int,
    body: PhotoAdd,
    user: User = Depends(require_tech),
    db: Session = Depends(get_db),
    storage: PhotoStorage = Depends(get_storage),
) -> list[PhotoOut]:
    claim = get_visible_claim(claim_id, user, db)  # another tech's claim is a 404
    check_claim_accepts(claim, body.photos)
    photos = attach_photos(db, storage, claim, body.photos, user)
    db.commit()
    # Copy now, delete later, as on submit (design §8).
    delete_uploads(storage, [ref.key for ref in body.photos])
    names = export_filenames(claim)
    return [to_photo_out(photo, storage, names) for photo in photos]


@router.patch("/{photo_id}", response_model=PhotoOut)
def update_photo(
    claim_id: int,
    photo_id: int,
    body: PhotoUpdate,
    user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
    storage: PhotoStorage = Depends(get_storage),
) -> PhotoOut:
    claim = get_visible_claim(claim_id, user, db)
    photo = get_claim_photo(claim, photo_id)
    check_photo_edit(photo, body)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(photo, field, value)
    db.commit()
    return to_photo_out(photo, storage, export_filenames(claim))


@router.get("/export")
def export_photos(
    claim_id: int,
    user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
    storage: PhotoStorage = Depends(get_storage),
) -> StreamingResponse:
    claim = get_visible_claim(claim_id, user, db)
    names = export_filenames(claim)  # in export order, excluded photos left out
    if not names:
        raise HTTPException(409, "No photos to export")
    archive = build_zip(claim, names, storage)
    return StreamingResponse(
        read_and_close(archive),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename(claim)}"'},
    )
