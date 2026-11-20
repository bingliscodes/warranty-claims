import logging

from botocore.exceptions import ClientError

from app.config import Settings
from app.storage import PhotoStorage, build_storage

logger = logging.getLogger(__name__)


def ensure_bucket(storage: PhotoStorage, region: str, allowed_origins: list[str]) -> None:
    try:
        storage.client.head_bucket(
            Bucket=storage.bucket,
        )
    except ClientError as err:
        if err.response["Error"]["Code"] != "404":
            raise

        if region == "us-east-1":
            storage.client.create_bucket(
                Bucket=storage.bucket,
            )
        else:
            storage.client.create_bucket(
                Bucket=storage.bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )

    storage.client.put_bucket_lifecycle_configuration(
        Bucket=storage.bucket,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "expire-uploads",
                    "Filter": {"Prefix": "uploads/"},
                    "Status": "Enabled",
                    "Expiration": {"Days": 7},
                }
            ]
        },
    )

    try:
        storage.client.put_bucket_cors(
            Bucket=storage.bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": allowed_origins,
                        "AllowedMethods": ["GET", "POST"],
                        "AllowedHeaders": ["*"],
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 3000,
                    }
                ]
            },
        )
    except ClientError as err:
        if err.response["Error"]["Code"] != "NotImplemented":
            raise
        logger.warning(
            "Bucket (%s) doesn't support per-bucket CORS. "
            "Configure CORS on the store itself, or browser uploads will fail",
            storage.bucket,
        )


def main() -> None:
    settings = Settings()
    ensure_bucket(
        storage=build_storage(settings),
        region=settings.S3_REGION,
        allowed_origins=settings.ALLOWED_ORIGINS,
    )


if __name__ == "__main__":
    main()
