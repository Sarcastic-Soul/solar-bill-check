"""POST /extract {key}: read the uploaded bill, delete it, run the extraction models in parallel,
merge their answers and run code sanity checks.

Privacy: the S3 object is deleted right after it is read (the bucket's 1-day lifecycle rule is the
backup). Logs carry model ids, timings, confidence counts and warning codes only, never field values.
"""

from __future__ import annotations

import concurrent.futures as cf
import time
from collections.abc import Callable
from typing import Any

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from . import aws, media
from .bedrock_client import ModelCallError, ModelSpec, converse_extract, models_from_env
from .errors import ApiError
from .fields import clean_fields, merge, sanity_check
from .upload import KEY_RE

logger = Logger(child=True)

# Seconds kept back from the Lambda timeout for merging and returning the response.
RESPONSE_MARGIN_S = 4.0


def read_and_delete(key: str) -> bytes:
    if not KEY_RE.match(key or ""):
        raise ApiError("BAD_KEY", "Unknown upload key.", 400)
    s3 = aws.s3()
    try:
        obj = s3.get_object(Bucket=aws.BILLS_BUCKET, Key=key)
        if obj["ContentLength"] > aws.MAX_UPLOAD_BYTES:  # the presigned POST already enforces this
            raise ApiError("FILE_TOO_LARGE", "The file is too large.", 413)
        return obj["Body"].read()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        # Without s3:ListBucket (not granted on purpose), S3 reports a missing key as AccessDenied.
        if code in ("NoSuchKey", "404", "NotFound", "AccessDenied", "403"):
            logger.info("upload not found", extra={"s3_error": code})
            raise ApiError("UPLOAD_NOT_FOUND", "We couldn't find the upload. It may have expired or was already "
                                               "read; please upload the bill again.", 404) from None
        raise
    finally:
        try:
            s3.delete_object(Bucket=aws.BILLS_BUCKET, Key=key)
        except ClientError:
            logger.warning("bill delete failed; lifecycle rule will remove it", extra={"key_suffix": key[-8:]})


def run_models(specs: list[ModelSpec], blocks: list[dict], deadline: float,
               call: Callable[..., dict] = converse_extract) -> list[dict]:
    """Call every model in parallel. Returns one record per model, in the configured order."""
    records: list[dict] = [{"id": s.id, "region": s.region, "mode": s.mode, "ok": False} for s in specs]
    budget = max(5.0, deadline - time.monotonic())
    ex = cf.ThreadPoolExecutor(max_workers=len(specs))
    futs = {ex.submit(call, s, blocks, read_timeout=int(budget), deadline=deadline): i for i, s in enumerate(specs)}
    try:
        for fut in cf.as_completed(futs, timeout=budget):
            i = futs[fut]
            try:
                out = fut.result()
            except ModelCallError as e:
                records[i]["error"] = e.code
                continue
            except Exception as e:  # noqa: BLE001 - never let one model take the request down
                records[i]["error"] = type(e).__name__
                continue
            records[i].update(ok=True, mode_used=out["mode_used"], latency_ms=out["latency_ms"],
                              attempts=out.get("attempts"), usage=out.get("usage"), prediction=out["prediction"])
    except cf.TimeoutError:
        for r in records:
            if not r["ok"] and "error" not in r:
                r["error"] = "TIMEOUT"
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return records


def extract(key: str, remaining_ms: Callable[[], int] | None = None,
            specs: list[ModelSpec] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    data = read_and_delete(key)
    t_read = time.monotonic()

    blocks, input_info = media.content_blocks(data)
    del data
    t_prep = time.monotonic()

    specs = specs or models_from_env()
    remaining = (remaining_ms() / 1000.0) if remaining_ms else 55.0
    deadline = time.monotonic() + remaining - RESPONSE_MARGIN_S
    records = run_models(specs, blocks, deadline)
    t_models = time.monotonic()

    ok = [r for r in records if r["ok"]]
    if not ok:
        logger.warning("extract failed", extra={"models": [{k: r.get(k) for k in ("id", "error")} for r in records]})
        raise ApiError("EXTRACTION_FAILED", "We couldn't read the bill right now. Try again, or enter your units by "
                                            "hand.", 502, {"models_used": _public(records)})

    merged = merge([clean_fields(r["prediction"]) for r in ok])
    fields, confidence = merged["fields"], merged["confidence"]
    warnings = sanity_check(fields, confidence)
    if len(ok) < len(records):
        warnings.append({"code": "SINGLE_MODEL", "field": None, "level": "info",
                         "message": "Only one reader answered, so fields weren't cross-checked."})

    total_ms = int((time.monotonic() - t0) * 1000)
    latency = {"total": total_ms, "read_s3": int((t_read - t0) * 1000), "prepare": int((t_prep - t_read) * 1000),
               "models": int((t_models - t_prep) * 1000)}
    counts: dict[str, int] = {}
    for c in confidence.values():
        counts[c] = counts.get(c, 0) + 1
    logger.info("extract done", extra={
        "input": {k: v for k, v in input_info.items()},
        "models": [{k: r.get(k) for k in ("id", "ok", "error", "latency_ms", "mode_used", "usage")} for r in records],
        "confidence_counts": counts,
        "disagreement_fields": [d["field"] for d in merged["disagreements"]],
        "warning_codes": [w["code"] for w in warnings],
        "latency_ms": latency,
    })
    return {
        "fields": fields,
        "confidence": confidence,
        "disagreements": merged["disagreements"],
        "warnings": warnings,
        "models_used": _public(records),
        "input": input_info,
        "latency_ms": latency,
    }


def _public(records: list[dict]) -> list[dict]:
    return [{k: r[k] for k in ("id", "region", "mode", "ok", "mode_used", "latency_ms", "error") if k in r}
            for r in records]
