import posixpath
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import Request

from app.config import Settings


@dataclass
class PresignedUpload:
    url: str
    fields: dict[str, str]


@dataclass
class ObjectInfo:
    content_type: str
    size: int


class PhotoStorage:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def presign_upload(
        self, key: str, content_type: str, max_bytes: int, expires_in: int = 900
    ) -> PresignedUpload:
        result = self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
            ExpiresIn=expires_in,
        )
        return PresignedUpload(url=result["url"], fields=result["fields"])

    def presign_download(
        self, key: str, download_name: str | None = None, expires_in: int = 900
    ) -> str:
        params = {"Bucket": self.bucket, "Key": key}
        if download_name is not None:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'

        return self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)

    def head(self, key: str) -> ObjectInfo | None:
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as err:
            if err.response["Error"]["Code"] == "404":
                return None
            raise
        return ObjectInfo(content_type=response["ContentType"], size=response["ContentLength"])

    def promote(self, upload_key: str, claim_id: int) -> str:
        new_key = f"claims/{claim_id}/{posixpath.basename(upload_key)}"
        self.client.copy_object(
            Bucket=self.bucket, Key=new_key, CopySource={"Bucket": self.bucket, "Key": upload_key}
        )
        self.client.delete_object(Bucket=self.bucket, Key=upload_key)
        return new_key


def build_storage(settings: Settings) -> PhotoStorage:
    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    return PhotoStorage(client=client, bucket=settings.S3_BUCKET)


def get_storage(request: Request) -> PhotoStorage:
    """FastAPI dependency: the PhotoStorage that create_app() was given."""
    return request.app.state.storage
