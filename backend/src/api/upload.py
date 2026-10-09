"""POST /upload-url: a presigned S3 POST for one bill file.

A presigned POST (not PUT) lets S3 itself enforce the size limit (content-length-range)
and the content type. The browser sends multipart/form-data with `fields` + the file last.
"""

from __future__ import annotations

import re
import uuid

from . import aws
from .errors import ApiError

ALLOWED = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}
EXT_TO_TYPE = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "pdf": "application/pdf"}
KEY_RE = re.compile(r"^bills/[0-9a-f]{32}\.(jpg|png|webp|pdf)$")
EXPIRES_S = 300


def content_type_from(body: dict) -> str:
    ct = str(body.get("contentType") or "").split(";")[0].strip().lower()
    if not ct and body.get("filename"):
        ext = str(body["filename"]).rsplit(".", 1)[-1].lower()
        ct = EXT_TO_TYPE.get(ext, "")
    if ct in ("image/heic", "image/heif"):
        raise ApiError("HEIC_NOT_SUPPORTED", "iPhone HEIC photos aren't supported. Upload a JPEG/PNG or a screenshot.",
                       415)
    if ct not in ALLOWED:
        raise ApiError("UNSUPPORTED_TYPE", "Upload a JPEG, PNG or WebP photo, or a PDF of the bill.", 415,
                       {"allowed": sorted(ALLOWED)})
    return ct


def create_upload(body: dict) -> dict:
    ct = content_type_from(body)
    size = body.get("size")
    if isinstance(size, (int, float)) and size > aws.MAX_UPLOAD_BYTES:
        raise ApiError("FILE_TOO_LARGE", f"The file is over {aws.MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
                                         "Try a smaller photo or a screenshot.", 413)
    key = f"bills/{uuid.uuid4().hex}.{ALLOWED[ct]}"
    post = aws.s3().generate_presigned_post(
        Bucket=aws.BILLS_BUCKET,
        Key=key,
        Fields={"Content-Type": ct},
        Conditions=[{"Content-Type": ct}, ["content-length-range", 1, aws.MAX_UPLOAD_BYTES]],
        ExpiresIn=EXPIRES_S,
    )
    return {"uploadUrl": post["url"], "method": "POST", "fields": post["fields"], "key": key,
            "maxBytes": aws.MAX_UPLOAD_BYTES, "expiresIn": EXPIRES_S}
