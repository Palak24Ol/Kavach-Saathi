from __future__ import annotations

from pathlib import Path

import httpx

from kavach_saathi.config import Settings


def _local_path(key: str, settings: Settings) -> Path:
    """Resolve an object key to a local file path.

    Historically the codebase used two different key conventions: full repo-relative
    paths for seeded fixtures (`assets/mock/products/P-001.png`) and plain object keys
    for freshly uploaded files (`uploads/catalogue/<uuid>.png`, written under
    `settings.asset_dir` by the mock-upload endpoint). Both need to resolve locally in
    demo mode since real model calls now actually read the bytes.
    """
    direct = Path(key)
    if direct.exists():
        return direct
    under_asset_dir = settings.asset_dir / key
    if under_asset_dir.exists():
        return under_asset_dir
    raise FileNotFoundError(f"Cannot resolve image key '{key}' to a local file")


async def read_image_bytes(key: str, settings: Settings) -> bytes:
    """Read the raw bytes for an object key, regardless of app_mode."""
    if key.startswith("http://") or key.startswith("https://"):
        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            response = await client.get(key)
            response.raise_for_status()
            return response.content
    if settings.is_live:
        import boto3

        s3_key = key.removeprefix(f"s3://{settings.media_bucket}/")
        body = boto3.client("s3", region_name=settings.aws_region).get_object(
            Bucket=settings.media_bucket, Key=s3_key
        )["Body"].read()
        return body
    return _local_path(key, settings).read_bytes()


def write_generated_image(key: str, content: bytes, settings: Settings, *, content_type: str = "image/png") -> str:
    """Persist a generated image under `key`, returning the object key that was written."""
    if settings.is_live:
        import boto3

        boto3.client("s3", region_name=settings.aws_region).put_object(
            Bucket=settings.media_bucket, Key=key, Body=content, ContentType=content_type
        )
        return key
    destination = settings.asset_dir / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return key
