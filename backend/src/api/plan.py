"""POST /plan and GET /plan/{id}.

The plan comes from the engine (no LLM). Pincode -> location + solar yield uses the real
fetchers (postalpincode.in, Nominatim/Photon, PVGIS/Global Solar Atlas) with the engine's
fallbacks. The stored copy has the consumer number masked and no consumer name.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from typing import Any

from aws_lambda_powertools import Logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from engine import PlanError, build_plan
from engine.fetchers import Fetchers

from . import aws
from .errors import ApiError
from .fields import clean_fields, redact

logger = Logger(child=True)

PLAN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{12,32}$")
PIN_RE = re.compile(r"^[1-9]\d{5}$")

class _In(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AnswersIn(_In):
    owns_roof: bool | None = None
    name_matches_bank: bool | None = None
    previous_subsidy: bool | None = None


class OverridesIn(_In):
    roof_area_m2: float | None = Field(default=None, gt=0, le=10000)
    cost_per_kw: float | None = Field(default=None, gt=10000, le=300000)
    rwa_houses: int | None = Field(default=None, ge=1, le=10000)
    system_kw: float | None = Field(default=None, gt=0, le=500)
    shading_loss_pct: float | None = Field(default=None, ge=0, le=90)


class PlanRequest(_In):
    fields: dict[str, Any] = Field(default_factory=dict)
    pincode: str | None = None
    answers: AnswersIn = Field(default_factory=AnswersIn)
    overrides: OverridesIn = Field(default_factory=OverridesIn)
    monthly_units: list[float] | float | None = None


def _validation_error(e: ValidationError) -> ApiError:
    # include_input=False: never echo user values back into logs or errors
    errs = [{"loc": ".".join(str(x) for x in err["loc"]), "msg": err["msg"]} for err in e.errors(include_input=False)]
    return ApiError("BAD_REQUEST", "Some fields are invalid.", 400, {"details": errs})


def make_plan(body: dict) -> dict:
    t0 = time.monotonic()
    try:
        req = PlanRequest.model_validate(body)
    except ValidationError as e:
        raise _validation_error(e) from None

    fields = clean_fields(req.fields)
    pin = re.sub(r"\D", "", req.pincode or "") or fields.get("pincode")
    if pin and not PIN_RE.match(pin):
        raise ApiError("BAD_PINCODE", "Enter a 6-digit PIN code.", 400)

    location = solar = None
    fetch_errors: list[str] = []
    if pin:
        f = Fetchers()  # its cache is module-level, so warm invocations reuse lookups
        location, solar = f.resolve(pin)
        fetch_errors = [e.split(":", 1)[0] for e in f.errors]
    t_fetch = time.monotonic()

    options = {k: v for k, v in req.overrides.model_dump().items() if v is not None}
    payload = {
        "bill": fields,
        "monthly_units": req.monthly_units,
        "location": location,
        "solar": solar,
        "answers": {"owns_roof": req.answers.owns_roof, "name_matches_bank": req.answers.name_matches_bank,
                    "previous_solar_subsidy": req.answers.previous_subsidy},
        "options": options,
    }
    try:
        plan = build_plan(payload)
    except PlanError as e:
        raise ApiError(e.code, _PLAN_ERRORS.get(e.code, "We couldn't build a plan from these details."), 422) from None
    except ValidationError as e:
        raise _validation_error(e) from None
    plan_json = plan.model_dump(mode="json")
    t_plan = time.monotonic()

    plan_id = secrets.token_urlsafe(12)
    now = int(time.time())
    stored_inputs = {
        "fields": redact(fields),
        "pincode": pin,
        "answers": req.answers.model_dump(),
        "overrides": options,
        "monthly_units": req.monthly_units,
    }
    aws.dynamodb().put_item(
        TableName=aws.PLANS_TABLE,
        Item={
            "planId": {"S": plan_id},
            "createdAt": {"N": str(now)},
            "expiresAt": {"N": str(now + aws.PLAN_TTL_DAYS * 86400)},
            "engineVersion": {"S": plan_json.get("engine_version", "")},
            "plan": {"S": json.dumps(plan_json, separators=(",", ":"))},
            "inputs": {"S": json.dumps(stored_inputs, separators=(",", ":"), ensure_ascii=False)},
        },
    )
    t_save = time.monotonic()
    latency = {"total": int((t_save - t0) * 1000), "lookups": int((t_fetch - t0) * 1000),
               "engine": int((t_plan - t_fetch) * 1000), "save": int((t_save - t_plan) * 1000)}
    logger.info("plan built", extra={
        "verdict": plan_json["verdict"]["code"], "discom": plan_json["discom"]["code"],
        "accuracy": plan_json["accuracy"], "location_source": location.source if location else None,
        "yield_source": plan_json["solar"]["source"], "fetch_errors": fetch_errors, "latency_ms": latency,
    })
    return {"planId": plan_id, "plan": plan_json, "expiresAt": now + aws.PLAN_TTL_DAYS * 86400,
            "lookups": {"location_source": location.source if location else None,
                        "yield_source": plan_json["solar"]["source"], "errors": fetch_errors},
            "latency_ms": latency}


def get_plan(plan_id: str) -> dict:
    if not PLAN_ID_RE.match(plan_id or ""):
        raise ApiError("PLAN_NOT_FOUND", "This plan link isn't valid.", 404)
    item = aws.dynamodb().get_item(TableName=aws.PLANS_TABLE, Key={"planId": {"S": plan_id}}).get("Item")
    if not item or int(item.get("expiresAt", {}).get("N", "0")) < time.time():
        raise ApiError("PLAN_NOT_FOUND", "This plan has expired or doesn't exist.", 404)
    return {
        "planId": plan_id,
        "createdAt": int(item["createdAt"]["N"]),
        "expiresAt": int(item["expiresAt"]["N"]),
        "plan": json.loads(item["plan"]["S"]),
        "inputs": json.loads(item["inputs"]["S"]),
    }


_PLAN_ERRORS = {
    "NOT_ELECTRICITY_BILL": "This doesn't look like an electricity bill.",
    "NO_CONSUMPTION": "We need your units: from the bill's history, this month's units, or entered by hand.",
}
