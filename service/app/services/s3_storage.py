"""S3/MinIO compatible object storage helpers."""

from __future__ import annotations

import hashlib
import hmac
import time
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import settings
from app.core.exceptions import BadRequestError


def storage_backend() -> str:
    if settings.ARTIFACT_STORAGE == "s3":
        if not settings.S3_ENDPOINT or not settings.S3_BUCKET:
            raise BadRequestError(
                message="S3 存储未配置完整",
                message_key="errors.autotask.s3_not_configured",
            )
        return "s3"
    return "local"


def full_object_key(storage_key: str) -> str:
    prefix = settings.S3_KEY_PREFIX.strip("/")
    if not prefix:
        return storage_key
    return f"{prefix}/{storage_key}"


@lru_cache(maxsize=1)
def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT or None,
        region_name=settings.S3_REGION or None,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
        config=BotoConfig(signature_version="s3v4"),
    )


def generate_presigned_put_url(storage_key: str, content_type: str | None = None) -> str:
    client = _get_s3_client()
    params: dict = {"Bucket": settings.S3_BUCKET, "Key": full_object_key(storage_key)}
    if content_type:
        params["ContentType"] = content_type
    return client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=settings.S3_PRESIGN_EXPIRES_SECONDS,
    )


def generate_presigned_get_url(storage_key: str) -> str:
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": full_object_key(storage_key)},
        ExpiresIn=settings.S3_PRESIGN_EXPIRES_SECONDS,
    )


def local_artifact_root() -> Path:
    root = Path(settings.ARTIFACT_LOCAL_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _artifact_base_url(configured_url: str) -> str:
    return (configured_url or settings.PUBLIC_BASE_URL).rstrip("/")


def local_upload_url(storage_key: str) -> str:
    base = _artifact_base_url(settings.ARTIFACT_UPLOAD_BASE_URL)
    return f"{base}/api/v1/autotask/artifacts/upload/{storage_key}"


def _sign_download(storage_key: str, expires: int) -> str:
    payload = f"{storage_key}:{expires}"
    return hmac.new(settings.JWT_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def local_download_url(storage_key: str) -> str:
    expires = int(time.time()) + settings.S3_PRESIGN_EXPIRES_SECONDS
    sig = _sign_download(storage_key, expires)
    base = _artifact_base_url(settings.ARTIFACT_DOWNLOAD_BASE_URL)
    return f"{base}/api/v1/autotask/artifacts/download/{storage_key}?expires={expires}&sig={sig}"


def verify_local_download_signature(storage_key: str, expires: int, sig: str) -> bool:
    if expires < int(time.time()):
        return False
    expected = _sign_download(storage_key, expires)
    return hmac.compare_digest(expected, sig)


def create_upload_target(storage_key: str, mime_type: str | None = None) -> str:
    backend = storage_backend()
    if backend == "s3":
        return generate_presigned_put_url(storage_key, mime_type)
    target = local_artifact_root() / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    return local_upload_url(storage_key)


def create_download_target(storage_key: str) -> str:
    backend = storage_backend()
    if backend == "s3":
        return generate_presigned_get_url(storage_key)
    return local_download_url(storage_key)
