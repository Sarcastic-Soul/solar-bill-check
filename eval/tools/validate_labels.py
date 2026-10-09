"""Check every eval/bills/<id>/label.json against eval/SCHEMA.md and the image limits.

Also scores each label against itself with eval/score.py (taking the first alternative of any list field)
and expects 100.

Usage:
    uv run --with pillow python eval/tools/validate_labels.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from billkit import BILLS_DIR, FIELD_ORDER, MAX_BYTES, MAX_SIDE  # noqa: E402

TOP_KEYS = {"id", "source", "source_url", "languages", "difficulty", "fields", "notes"}
OPTIONAL_TOP = {"low_confidence_fields"}
DIFFICULTY = {"clean", "phone_photo", "blurry", "rotated", "low_light", "cropped"}
STR_FIELDS = {"discom", "state", "consumer_number", "consumer_name", "tariff_category", "pincode"}
BOOL_FIELDS = {"is_electricity_bill", "is_residential", "has_solar_net_meter"}
NUM_FIELDS = {"sanctioned_load_kw", "units_billed_kwh", "bill_amount_rs", "export_units_kwh"}


def check(d: Path) -> list[str]:
    errs = []
    lp = d / "label.json"
    if not lp.exists():
        return ["missing label.json"]
    try:
        lab = json.loads(lp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"bad JSON: {e}"]
    keys = set(lab)
    if TOP_KEYS - keys:
        errs.append(f"missing top keys {TOP_KEYS - keys}")
    if keys - TOP_KEYS - OPTIONAL_TOP:
        errs.append(f"unknown top keys {keys - TOP_KEYS - OPTIONAL_TOP}")
    if lab.get("id") != d.name:
        errs.append(f"id {lab.get('id')} != folder {d.name}")
    if lab.get("source") not in {"mock", "official_sample"}:
        errs.append("bad source")
    if lab.get("source") == "official_sample" and not lab.get("source_url"):
        errs.append("official_sample without source_url")
    if lab.get("difficulty") not in DIFFICULTY:
        errs.append("bad difficulty")
    if d.name.endswith("-photo") and lab.get("difficulty") != "phone_photo":
        errs.append("-photo folder without phone_photo difficulty")
    if not (isinstance(lab.get("languages"), list) and lab["languages"]):
        errs.append("languages must be a non-empty list")

    f = lab.get("fields", {})
    if list(f) != FIELD_ORDER:
        missing, extra = set(FIELD_ORDER) - set(f), set(f) - set(FIELD_ORDER)
        if missing or extra:
            errs.append(f"field keys: missing {missing}, extra {extra}")
    for k in STR_FIELDS:
        v = f.get(k)
        if v is not None and not (isinstance(v, str) or (isinstance(v, list) and v and all(isinstance(x, str) for x in v))):
            errs.append(f"{k} must be string, list of strings, or null")
    for k in BOOL_FIELDS:
        if f.get(k) is not None and not isinstance(f[k], bool):
            errs.append(f"{k} must be bool or null")
    for k in NUM_FIELDS | {"billing_days"}:
        v = f.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
            errs.append(f"{k} must be a number or null")
    if f.get("connection_phase") not in {"single", "three", None}:
        errs.append("bad connection_phase")
    if f.get("billing_cycle") not in {"monthly", "bimonthly", None}:
        errs.append("bad billing_cycle")
    if f.get("meter_reading_type") not in {"actual", "estimated", "unknown", None}:
        errs.append("bad meter_reading_type")
    for k in ("billing_period_start", "billing_period_end"):
        v = f.get(k)
        if v is not None:
            try:
                date.fromisoformat(v)
            except (TypeError, ValueError):
                errs.append(f"{k} not YYYY-MM-DD")
    s, e, days = f.get("billing_period_start"), f.get("billing_period_end"), f.get("billing_days")
    if s and e and days is not None:
        diff = (date.fromisoformat(e) - date.fromisoformat(s)).days
        if abs(diff - days) > 1:
            errs.append(f"billing_days {days} vs dates {diff}")
    if f.get("pincode") is not None and not re.fullmatch(r"\d{6}", str(f["pincode"])):
        errs.append("pincode not 6 digits")
    h = f.get("consumption_history")
    if h is not None:
        months = []
        for item in h:
            if set(item) != {"month", "units_kwh"} or not re.fullmatch(r"\d{4}-\d{2}", str(item["month"])):
                errs.append(f"bad history item {item}")
                break
            if not isinstance(item["units_kwh"], (int, float)) or isinstance(item["units_kwh"], bool):
                errs.append(f"history units not a number: {item}")
            months.append(item["month"])
        if months != sorted(months, reverse=True) or len(set(months)) != len(months):
            errs.append("history not strictly newest-first")
    if f.get("is_electricity_bill") is False:
        others = [k for k in FIELD_ORDER if k != "is_electricity_bill" and f.get(k) is not None]
        if others:
            errs.append(f"non-bill has non-null fields {others}")
    elif f.get("is_electricity_bill") is not True:
        errs.append("is_electricity_bill must be true or false")
    if f.get("has_solar_net_meter") is False and f.get("export_units_kwh") not in (None, 0):
        errs.append("export units without solar")

    imgs = [p for p in d.glob("bill.*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf"}]
    if len(imgs) != 1:
        errs.append(f"expected one bill.* file, found {[p.name for p in imgs]}")
    else:
        p = imgs[0]
        if p.stat().st_size >= MAX_BYTES:
            errs.append(f"{p.name} is {p.stat().st_size} bytes (limit {MAX_BYTES})")
        if p.suffix.lower() != ".pdf":
            with Image.open(p) as im:
                if max(im.size) > MAX_SIDE:
                    errs.append(f"{p.name} is {im.size}, long side > {MAX_SIDE}")
                if im.format not in {"PNG", "JPEG"}:
                    errs.append(f"{p.name} format {im.format}")

    try:
        from score import score
        first = {k: (v[0] if isinstance(v, list) and k != "consumption_history" else v) for k, v in f.items()}
        sc = score(f, first)["score"]
        if sc != 100:
            errs.append(f"self-score {sc} != 100")
    except ImportError:
        pass
    return errs


def main() -> int:
    dirs = sorted(p for p in BILLS_DIR.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))
    bad = 0
    for d in dirs:
        errs = check(d)
        print(f"{'OK  ' if not errs else 'FAIL'} {d.name}")
        for e in errs:
            print(f"       - {e}")
        bad += bool(errs)
    print(f"\n{len(dirs) - bad}/{len(dirs)} labels valid")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
