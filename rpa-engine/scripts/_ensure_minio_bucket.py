# -*- coding: utf-8 -*-
"""Create MinIO bucket from rpa-engine/.env if missing. Does not print secrets."""
from __future__ import annotations

from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ENV = Path(__file__).resolve().parents[1] / ".env"


def load_minio() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        values[key.strip()] = raw.strip().strip('"').strip("'")
    needed = (
        "MINIO_ENDPOINT_URL",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_BUCKET",
        "MINIO_REGION",
    )
    missing = [k for k in needed if not values.get(k)]
    if missing:
        raise SystemExit(f"missing {missing}")
    return values


def main() -> None:
    cfg = load_minio()
    bucket = cfg["MINIO_BUCKET"]
    client = boto3.client(
        "s3",
        endpoint_url=cfg["MINIO_ENDPOINT_URL"],
        aws_access_key_id=cfg["MINIO_ACCESS_KEY"],
        aws_secret_access_key=cfg["MINIO_SECRET_KEY"],
        region_name=cfg["MINIO_REGION"],
    )
    try:
        client.head_bucket(Bucket=bucket)
        print(f"bucket_exists {bucket}")
        return
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in {"404", "NoSuchBucket", "404 Not Found"}:
            http = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if http not in {404, 403}:
                raise
            if http == 403:
                raise SystemExit(f"bucket {bucket} exists but access denied") from exc
    client.create_bucket(Bucket=bucket)
    print(f"bucket_created {bucket}")


if __name__ == "__main__":
    main()
