"""Raw copies of fetched records (WO-054). The ONLY code that talks to the raw store (S3); tests
replace it wholesale.

`RAW_STORE=s3` keeps each new record's bytes in the private RAW_BUCKET with the host's IAM role
(no keys), encrypted at rest (SSE-S3); `none` keeps nothing outside the database. The key is
content-addressed, so the same bytes always land under the same name on a given day."""

import asyncio
from datetime import date

from app.core.config import get_settings


def enabled() -> bool:
    return get_settings().raw_store == "s3"


def key_for(source: str, digest: bytes, day: date) -> str:
    """`raw/<source>/<yyyy>/<mm>/<dd>/<sha256 hex>.json` (tech doc §6: fetch, then keep the raw)."""
    return f"raw/{source}/{day:%Y/%m/%d}/{digest.hex()}.json"


def _put(key: str, body: bytes) -> None:
    import boto3  # only the deployed Worker needs it

    s = get_settings()
    boto3.client("s3", region_name=s.aws_region).put_object(
        Bucket=s.raw_bucket, Key=key, Body=body, ContentType="application/json",
        ServerSideEncryption="AES256")


async def put(key: str, body: bytes) -> None:
    """Store the bytes under the key. Raises on any failure; the caller decides what that costs."""
    if not get_settings().raw_bucket:
        raise RuntimeError("RAW_STORE=s3 needs RAW_BUCKET")
    await asyncio.to_thread(_put, key, body)
