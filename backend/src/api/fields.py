"""Pure logic for extracted bill fields: clean up, compare two models, sanity checks, masking.

No network and no AWS here, so it is unit tested directly (backend/tests/test_fields.py).

Confidence per field:
  high     both models agree (key fields), or agree on a non-key field
  medium   only one model answered, or one model returned null, or a non-key field differs
  check    key field where the two models disagree, or a value failed a sanity check
  missing  no model found a value
"""

from __future__ import annotations

import datetime as dt
import re
import statistics
import unicodedata
from typing import Any

from engine.tariffs import normalize_state, resolve_discom

from .extract_prompt import FIELD_ORDER

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

KEY_FIELDS = [
    "units_billed_kwh",
    "consumption_history",
    "sanctioned_load_kw",
    "bill_amount_rs",
    "discom",
    "state",
    "is_residential",
    "billing_cycle",
    "consumer_number",
]

NUMBER_FIELDS = {"units_billed_kwh", "sanctioned_load_kw", "bill_amount_rs", "export_units_kwh"}
INT_FIELDS = {"billing_days"}
BOOL_FIELDS = {"is_electricity_bill", "is_residential", "has_solar_net_meter"}
DATE_FIELDS = {"billing_period_start", "billing_period_end"}
ENUMS = {
    "connection_phase": {"single", "three"},
    "billing_cycle": {"monthly", "bimonthly"},
    "meter_reading_type": {"actual", "estimated", "unknown"},
}
# Fields that must never reach logs or storage in full.
PERSONAL_FIELDS = {"consumer_name", "consumer_number"}

# Agreement tolerance per numeric field: (absolute, relative)
TOLERANCE = {
    "units_billed_kwh": (0.5, 0.0),
    "sanctioned_load_kw": (0.01, 0.0),
    "bill_amount_rs": (1.0, 0.002),
    "export_units_kwh": (0.5, 0.0),
    "history": (0.5, 0.0),
}

LIMITS = {
    "units_billed_kwh": (1, 20000),
    "sanctioned_load_kw": (0.1, 100),
    "history_units": (0, 20000),
    "bill_amount_rs": (0, 1_000_000),
    "rate_rs_per_kwh": (1.0, 30.0),  # bill amount / units, checked only when units >= 30
}


# ---------------------------------------------------------------- digits and values


def normalize_digits(s: str) -> str:
    """Turn any Unicode decimal digit (Devanagari ४, Bengali ৪, Tamil ௪, ...) into 0-9."""
    out = []
    for ch in s:
        if ch.isdigit() and not ("0" <= ch <= "9"):
            try:
                out.append(str(unicodedata.decimal(ch)))
                continue
            except (TypeError, ValueError):
                pass
        out.append(ch)
    return "".join(out)


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def to_number(v: Any) -> float | None:
    """Parse '1,323.01', '₹ 1323', '३४२', '3 kW', 1323 -> float. None for anything else."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = normalize_digits(v).replace(",", "").replace("٫", ".").strip()
        m = _NUM_RE.search(s)
        if m:
            return float(m.group(0))
    return None


def to_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "y", "1"):
            return True
        if s in ("false", "no", "n", "0"):
            return False
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    return None


def _to_date(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = normalize_digits(v).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})", s)  # Indian day-first
        if not m:
            return None
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def _to_month(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = normalize_digits(v).strip()
    m = re.match(r"(\d{4})-(\d{1,2})", s)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return f"{y:04d}-{mo:02d}" if 1 <= mo <= 12 and 1990 <= y <= 2100 else None


def _to_enum(field: str, v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = v.strip().lower()
    if field == "connection_phase":
        if s.startswith(("single", "1", "one")):
            return "single"
        if s.startswith(("three", "3", "poly")):
            return "three"
    if field == "billing_cycle":
        s = s.replace("-", "").replace(" ", "")
        if s in ("bimonthly", "twomonthly"):
            return "bimonthly"
    return s if s in ENUMS[field] else None


def _clean_history(v: Any) -> list[dict] | None:
    if not isinstance(v, list):
        return None
    seen: dict[str, float] = {}
    for item in v:
        if not isinstance(item, dict):
            continue
        month = _to_month(item.get("month"))
        units = to_number(item.get("units_kwh", item.get("units")))
        if month is None or units is None or month in seen:
            continue
        seen[month] = units
    if not seen:
        return None
    return [{"month": m, "units_kwh": u} for m, u in sorted(seen.items(), reverse=True)]


def clean_fields(raw: dict | None) -> dict:
    """Normalise one model's output into the schema's shape: Western digits, numbers as numbers,
    enums lower-case, dates YYYY-MM-DD, history newest first. Unknown keys are dropped."""
    raw = raw or {}
    out: dict[str, Any] = {}
    for k in FIELD_ORDER:
        v = raw.get(k)
        if k in NUMBER_FIELDS:
            out[k] = to_number(v)
        elif k in INT_FIELDS:
            n = to_number(v)
            out[k] = round(n) if n is not None else None
        elif k in BOOL_FIELDS:
            out[k] = to_bool(v)
        elif k in DATE_FIELDS:
            out[k] = _to_date(v)
        elif k in ENUMS:
            out[k] = _to_enum(k, v)
        elif k == "consumption_history":
            out[k] = _clean_history(v)
        elif k == "consumer_number":
            s = normalize_digits(str(v)).strip() if v not in (None, "") else None
            out[k] = re.sub(r"\s+", "", s) if s else None
        elif k == "pincode":
            digits = re.sub(r"\D", "", normalize_digits(str(v))) if v is not None else ""
            out[k] = digits if re.fullmatch(r"[1-9]\d{5}", digits) else None
        elif k == "state":
            out[k] = normalize_state(v) if isinstance(v, str) and v.strip() else None
        else:
            out[k] = normalize_digits(v).strip() or None if isinstance(v, str) else None
    if out.get("is_electricity_bill") is None and any(out[k] is not None for k in FIELD_ORDER):
        out["is_electricity_bill"] = True
    return out


# ---------------------------------------------------------------- agreement


def _close(field: str, a: float, b: float) -> bool:
    abs_tol, rel_tol = TOLERANCE.get(field, (1e-6, 0.0))
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))


def _norm_text(s: str) -> str:
    return re.sub(r"[^0-9a-zऀ-෿]", "", s.lower())


def same_value(field: str, a: Any, b: Any, state: str | None = None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if field in NUMBER_FIELDS:
        return _close(field, float(a), float(b))
    if field == "consumption_history":
        ma = {h["month"]: h["units_kwh"] for h in a}
        mb = {h["month"]: h["units_kwh"] for h in b}
        return ma.keys() == mb.keys() and all(_close("history", ma[m], mb[m]) for m in ma)
    if field == "discom":
        ca, _ = resolve_discom(a, state)
        cb, _ = resolve_discom(b, state)
        if ca and cb:
            return ca == cb
        na, nb = _norm_text(a), _norm_text(b)
        return bool(na and nb) and (na == nb or na in nb or nb in na)
    if isinstance(a, str) and isinstance(b, str):
        return _norm_text(a) == _norm_text(b)
    return a == b


def merge(results: list[dict]) -> dict:
    """Combine cleaned outputs from 1+ models (first = primary).

    Returns {fields, confidence, disagreements}. Key fields where two models differ get
    confidence "check" and both candidate values; the primary model's value is kept as the
    default so the user only has to confirm or switch.
    """
    results = [r for r in results if r is not None]
    if not results:
        raise ValueError("no results to merge")
    fields: dict[str, Any] = {}
    confidence: dict[str, str] = {}
    disagreements: list[dict] = []

    if len(results) == 1:
        only = results[0]
        for k in FIELD_ORDER:
            fields[k] = only.get(k)
            confidence[k] = "missing" if fields[k] is None else "medium"
        return {"fields": fields, "confidence": confidence, "disagreements": disagreements}

    a, b = results[0], results[1]
    state_hint = a.get("state") or b.get("state")
    for k in FIELD_ORDER:
        va, vb = a.get(k), b.get(k)
        if va is None and vb is None:
            fields[k], confidence[k] = None, "missing"
        elif same_value(k, va, vb, state_hint):
            fields[k], confidence[k] = va, "high"
        elif va is None or vb is None:
            fields[k] = va if va is not None else vb
            confidence[k] = "medium"
            if k in KEY_FIELDS:
                disagreements.append({"field": k, "kind": "one_missing", "candidates": [va, vb]})
        elif k in KEY_FIELDS or k == "is_electricity_bill":
            fields[k], confidence[k] = va, "check"
            disagreements.append({"field": k, "kind": "different", "candidates": [va, vb]})
        else:
            fields[k], confidence[k] = va, "medium"
    return {"fields": fields, "confidence": confidence, "disagreements": disagreements}


# ---------------------------------------------------------------- sanity checks


def _warn(code: str, field: str | None, level: str, message: str) -> dict:
    return {"code": code, "field": field, "level": level, "message": message}


def sanity_check(fields: dict, confidence: dict | None = None, today: dt.date | None = None) -> list[dict]:
    """Code checks on the merged fields. Fields that fail are set to confidence "check"
    (in place, if `confidence` is given). Returns warnings: {code, field, level, message}."""
    conf = confidence if confidence is not None else {}
    today = today or dt.datetime.now(IST).date()
    warnings: list[dict] = []

    def flag(code: str, field: str | None, message: str, level: str = "check"):
        warnings.append(_warn(code, field, level, message))
        if field and level == "check" and fields.get(field) is not None:
            conf[field] = "check"

    if fields.get("is_electricity_bill") is False:
        warnings.append(_warn("NOT_ELECTRICITY_BILL", "is_electricity_bill", "error",
                              "This doesn't look like an electricity bill."))
        return warnings

    units = fields.get("units_billed_kwh")
    lo, hi = LIMITS["units_billed_kwh"]
    if units is not None and not lo <= units <= hi:
        flag("UNITS_OUT_OF_RANGE", "units_billed_kwh", f"Units billed ({units:g}) look wrong; expected {lo}-{hi}.")

    load = fields.get("sanctioned_load_kw")
    lo, hi = LIMITS["sanctioned_load_kw"]
    if load is not None and not lo <= load <= hi:
        flag("LOAD_OUT_OF_RANGE", "sanctioned_load_kw", f"Sanctioned load ({load:g} kW) looks wrong; expected {lo}-{hi} kW.")

    amount = fields.get("bill_amount_rs")
    lo, hi = LIMITS["bill_amount_rs"]
    if amount is not None and not lo <= amount <= hi:
        flag("AMOUNT_OUT_OF_RANGE", "bill_amount_rs", f"Bill amount (Rs {amount:g}) looks wrong.")
    elif amount and units and units >= 30:
        rate = amount / units
        rlo, rhi = LIMITS["rate_rs_per_kwh"]
        if rate > rhi:
            flag("AMOUNT_HIGH_FOR_UNITS", "bill_amount_rs",
                 f"Rs {amount:g} for {units:g} units is Rs {rate:.1f}/unit, which is unusually high. Check the amount "
                 "(arrears included?) and the units.")
        elif rate < rlo:
            flag("AMOUNT_LOW_FOR_UNITS", "bill_amount_rs",
                 f"Rs {amount:g} for {units:g} units is Rs {rate:.2f}/unit, which is unusually low. Check both.")

    history = fields.get("consumption_history") or []
    if history:
        lo, hi = LIMITS["history_units"]
        bad = [h for h in history if not lo <= h["units_kwh"] <= hi]
        if bad:
            flag("HISTORY_VALUE_OUT_OF_RANGE", "consumption_history",
                 f"{len(bad)} month(s) in the usage history look wrong (outside {lo}-{hi} units).")
        limit = f"{today.year + (today.month == 12):04d}-{today.month % 12 + 1:02d}"
        if any(h["month"] > limit for h in history):
            flag("HISTORY_MONTH_IN_FUTURE", "consumption_history", "The usage history has a month in the future.")
        vals = [h["units_kwh"] for h in history if h["units_kwh"] > 0]
        if units and units >= 10 and len(vals) >= 3:
            med = statistics.median(vals)
            if med > 0 and not (med / 4 <= units <= med * 4):
                flag("UNITS_VS_HISTORY", "units_billed_kwh",
                     f"Units billed ({units:g}) are far from the usual month in the history ({med:g}). Check both.")
        if len(history) == 1:
            warnings.append(_warn("HISTORY_SINGLE_MONTH", "consumption_history", "info",
                                  "Only one month of history was found; you can add more months."))
    elif units is not None:
        warnings.append(_warn("NO_HISTORY", "consumption_history", "info",
                              "No usage history found on the bill; this month's units will be used for every month."))

    days, cycle = fields.get("billing_days"), fields.get("billing_cycle")
    if days is not None and ((cycle == "bimonthly" and days < 45) or (cycle == "monthly" and days > 45)):
        flag("BILLING_CYCLE_VS_DAYS", "billing_cycle", f"{days} billing days doesn't match a {cycle} bill.")

    start, end = fields.get("billing_period_start"), fields.get("billing_period_end")
    if start and end and start >= end:
        flag("BILLING_DATES_ORDER", "billing_period_start", "The billing start date is not before the end date.")

    if fields.get("meter_reading_type") == "estimated":
        warnings.append(_warn("ESTIMATED_READING", "meter_reading_type", "info",
                              "This bill used an estimated reading; check the units against your meter."))
    if fields.get("has_solar_net_meter"):
        warnings.append(_warn("ALREADY_HAS_SOLAR", "has_solar_net_meter", "info",
                              "This bill shows a solar net meter."))
    if fields.get("is_residential") is False:
        warnings.append(_warn("NON_RESIDENTIAL", "is_residential", "info",
                              "This looks like a non-domestic connection; PM Surya Ghar covers homes only."))
    if units is None and not history:
        warnings.append(_warn("NO_UNITS", "units_billed_kwh", "check", "No units found; please enter them."))
    return warnings


# ---------------------------------------------------------------- privacy


def mask_consumer_number(v: str | None) -> str | None:
    """'152839471' -> 'XXXXX9471'. Keeps the last 4 (last 2 if the number is short)."""
    if not v:
        return v
    s = str(v)
    keep = 4 if len(s) > 6 else 2 if len(s) > 2 else 0
    return "X" * (len(s) - keep) + s[len(s) - keep:]


def redact(fields: dict) -> dict:
    """Copy safe to store: consumer number masked, consumer name dropped."""
    out = dict(fields)
    out.pop("consumer_name", None)
    if out.get("consumer_number"):
        out["consumer_number"] = mask_consumer_number(out["consumer_number"])
    return out
