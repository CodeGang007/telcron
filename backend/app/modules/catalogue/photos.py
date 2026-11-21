"""Product photos (WO-014). The ONLY code that talks to the photo store (S3) and to the image
reader (Amazon Rekognition); both are replaced wholesale in tests.

`MEDIA_STORE=s3` keeps photos in the private media bucket with the host's IAM role (no keys);
`none` keeps nothing. `IMAGE_READER=rekognition` reads the printed text and the kind of object
before the vision model looks, so the model is told what the pack actually says."""

import asyncio
import base64
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings

DATA_URL = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,(.+)$", re.S)
LINK_SECONDS = 300


class PhotoUnreadable(Exception):
    pass


@dataclass
class Reading:
    lines: list[str] = field(default_factory=list)       # printed text, most confident first
    labels: list[tuple[str, float]] = field(default_factory=list)  # (what it is, confidence 0-1)
    error: str | None = None


def decode(data_url: str) -> tuple[str, bytes]:
    match = DATA_URL.match(data_url)
    if not match:
        raise PhotoUnreadable("not a JPEG, PNG or WebP data URL")
    try:
        return match.group(1), base64.b64decode(match.group(2), validate=True)
    except ValueError as exc:
        raise PhotoUnreadable("bad base64") from exc


def _client(service: str):
    import boto3  # only the deployed API needs it
    return boto3.client(service, region_name=get_settings().aws_region)


async def store(key: str, mime: str, body: bytes) -> None:
    s = get_settings()
    await asyncio.to_thread(_client("s3").put_object, Bucket=s.media_bucket, Key=key, Body=body,
                            ContentType=mime)


def link(key: str) -> str:
    """A short-lived link to a stored photo (the bucket is private)."""
    s = get_settings()
    return _client("s3").generate_presigned_url(
        "get_object", Params={"Bucket": s.media_bucket, "Key": key}, ExpiresIn=LINK_SECONDS)


def _read(body: bytes) -> Reading:
    rek = _client("rekognition")
    text = rek.detect_text(Image={"Bytes": body})
    labels = rek.detect_labels(Image={"Bytes": body}, MaxLabels=10, MinConfidence=70)
    lines = [d["DetectedText"] for d in sorted(
        (d for d in text.get("TextDetections", []) if d.get("Type") == "LINE"),
        key=lambda d: -d.get("Confidence", 0))][:25]
    return Reading(lines, [(lbl["Name"], round(lbl["Confidence"] / 100, 3))
                           for lbl in labels.get("Labels", [])])


async def read(body: bytes) -> Reading:
    if get_settings().image_reader != "rekognition":
        return Reading()
    try:
        return await asyncio.to_thread(_read, body)
    except Exception as exc:  # the reader is a help, not a requirement: say why and go on
        return Reading(error=f"{type(exc).__name__}: {exc}"[:300])


def hints(reading: Reading) -> dict[str, Any]:
    return {"printed_text": reading.lines, "looks_like": [n for n, _ in reading.labels]}
