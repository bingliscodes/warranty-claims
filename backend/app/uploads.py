import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, StringConstraints

from app.auth import get_current_user
from app.config import Settings, get_settings
from app.models import User
from app.photos.content_types import EXTENSIONS, ContentType
from app.storage import PhotoStorage, get_storage


class UploadRequest(BaseModel):
    content_type: ContentType
    filename: Annotated[str, StringConstraints(min_length=1, max_length=255)]


class UploadOut(BaseModel):
    key: str
    url: str
    fields: dict[str, str]


router = APIRouter(prefix="/api")


@router.post("/uploads", status_code=status.HTTP_201_CREATED, response_model=UploadOut)
def create_upload(
    body: UploadRequest,
    user: User = Depends(get_current_user),
    storage: PhotoStorage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> UploadOut:

    extension = EXTENSIONS[body.content_type]
    key = f"uploads/{user.id}/{uuid.uuid4().hex}.{extension}"
    presigned_upload = storage.presign_upload(
        key=key, content_type=body.content_type, max_bytes=settings.MAX_UPLOAD_BYTES
    )
    return UploadOut(key=key, url=presigned_upload.url, fields=presigned_upload.fields)
