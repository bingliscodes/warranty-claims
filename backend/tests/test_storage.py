import pytest
from botocore.exceptions import ClientError

from app.config import Settings
from app.storage import PhotoStorage, build_storage


def test_presigned_urls_use_configured_endpoint():
    s = build_storage(
        Settings(S3_ENDPOINT_URL="http://192.168.1.50:9000", S3_BUCKET="warranty-photos")
    )
    assert s.presign_upload("uploads/1/a.jpg", "image/jpeg", 1000).url.startswith(
        "http://192.168.1.50:9000/warranty-photos"
    )
    assert s.presign_download("claims/1/a.jpg").startswith(
        "http://192.168.1.50:9000/warranty-photos/claims/1/a.jpg"
    )


def test_promote_moves_object(storage):
    storage.client.put_object(
        Bucket="test-bucket", Key="uploads/1/abc.jpg", Body=b"x", ContentType="image/jpeg"
    )
    new_key = storage.promote("uploads/1/abc.jpg", claim_id=7)
    assert new_key == "claims/7/abc.jpg"
    assert storage.head(new_key).content_type == "image/jpeg"
    assert storage.head("uploads/1/abc.jpg") is None


def test_download_url_names_the_file(storage):
    storage.client.put_object(Bucket="test-bucket", Key="claims/7/abc.jpg", Body=b"x")
    url = storage.presign_download(
        "claims/7/abc.jpg", download_name="ASSURANT.KP042788.SMITH.VIN.11.26.jpg"
    )
    assert "response-content-disposition=attachment" in url


def test_head_raises_errors_other_than_missing_object(storage):
    broken = PhotoStorage(storage.client, "no-such-bucket")
    with pytest.raises(ClientError):
        broken.head("claims/7/abc.jpg")
