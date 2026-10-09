"""Shared AWS clients and settings, created once per Lambda container."""

from __future__ import annotations

import os
from functools import cache

REGION = os.environ.get("AWS_REGION", "ap-south-1")
BILLS_BUCKET = os.environ.get("BILLS_BUCKET", "")
PLANS_TABLE = os.environ.get("PLANS_TABLE", "")
CHATS_TABLE = os.environ.get("CHATS_TABLE", "")
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
PLAN_TTL_DAYS = int(os.environ.get("PLAN_TTL_DAYS", "30"))


@cache
def s3():
    import boto3
    from botocore.config import Config

    # Regional virtual-host endpoint so presigned POSTs never hit a 307 redirect (which breaks CORS).
    return boto3.client("s3", region_name=REGION, endpoint_url=f"https://s3.{REGION}.amazonaws.com",
                        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))


@cache
def dynamodb():
    import boto3

    return boto3.client("dynamodb", region_name=REGION)


@cache
def polly():
    import boto3

    return boto3.client("polly", region_name=REGION)
