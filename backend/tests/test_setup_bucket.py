import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from app.setup_bucket import ensure_bucket
from app.storage import PhotoStorage

ORIGINS = ["http://192.168.1.50:5173"]


@pytest.fixture
def empty_storage():
    with mock_aws():
        yield PhotoStorage(boto3.client("s3", region_name="us-east-1"), "fresh-bucket")


def test_creates_bucket_with_upload_expiry_and_cors(empty_storage):
    ensure_bucket(empty_storage, "us-east-1", ORIGINS)
    rules = empty_storage.client.get_bucket_lifecycle_configuration(Bucket="fresh-bucket")["Rules"]
    assert [(r["Filter"]["Prefix"], r["Expiration"]["Days"], r["Status"]) for r in rules] == [
        ("uploads/", 7, "Enabled")
    ]
    cors = empty_storage.client.get_bucket_cors(Bucket="fresh-bucket")["CORSRules"]
    assert cors[0]["AllowedOrigins"] == ORIGINS and set(cors[0]["AllowedMethods"]) == {
        "GET",
        "POST",
    }


def test_running_twice_is_safe(empty_storage):
    ensure_bucket(empty_storage, "us-east-1", ORIGINS)
    ensure_bucket(empty_storage, "us-east-1", ORIGINS)
    assert (
        len(empty_storage.client.get_bucket_lifecycle_configuration(Bucket="fresh-bucket")["Rules"])
        == 1
    )


def test_store_without_bucket_cors_still_gets_lifecycle(empty_storage, monkeypatch):
    def not_implemented(**kwargs):
        raise ClientError({"Error": {"Code": "NotImplemented", "Message": "x"}}, "PutBucketCors")

    monkeypatch.setattr(empty_storage.client, "put_bucket_cors", not_implemented)
    ensure_bucket(empty_storage, "us-east-1", ORIGINS)
    assert empty_storage.client.get_bucket_lifecycle_configuration(Bucket="fresh-bucket")["Rules"]


def test_creates_bucket_outside_us_east_1():
    with mock_aws():
        storage = PhotoStorage(boto3.client("s3", region_name="eu-west-1"), "fresh-bucket")
        ensure_bucket(storage, "eu-west-1", ORIGINS)
        location = storage.client.get_bucket_location(Bucket="fresh-bucket")
        assert location["LocationConstraint"] == "eu-west-1"
