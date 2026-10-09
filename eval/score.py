"""Score a model's bill extraction against a label (see eval/SCHEMA.md).

Usage as a script:
    python eval/score.py eval/bills/<id>/label.json prediction.json
"""

from __future__ import annotations

import datetime as dt
import difflib
import json
import re
import sys
import unicodedata

# ---------------------------------------------------------------- weights
# Group weights from SCHEMA.md, split evenly across the fields in a group.
GROUPS: list[tuple[str, float, list[str]]] = [
    ("units", 20, ["units_billed_kwh"]),
    ("history", 20, ["consumption_history"]),
    ("load", 10, ["sanctioned_load_kw"]),
    ("location", 10, ["state", "discom"]),
    ("tariff", 10, ["is_residential", "tariff_category"]),
    ("amount", 10, ["bill_amount_rs"]),
    ("period", 5, ["billing_days", "billing_cycle", "billing_period_start", "billing_period_end"]),
    ("flags", 5, ["has_solar_net_meter", "meter_reading_type", "is_electricity_bill"]),
    ("ids", 10, ["consumer_number", "consumer_name", "pincode", "connection_phase"]),
]
FIELD_WEIGHTS: dict[str, float] = {f: w / len(fs) for _, w, fs in GROUPS for f in fs}
# Tracked for accuracy but not in the 100-point score.
UNWEIGHTED = ["export_units_kwh"]
ALL_FIELDS = list(FIELD_WEIGHTS) + UNWEIGHTED

# ---------------------------------------------------------------- normalizers
_DIGIT_MAP = {}
for _zero in (0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0xFF10):
    for _i in range(10):
        _DIGIT_MAP[_zero + _i] = str(_i)


def western_digits(s: str) -> str:
    """Convert Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam, fullwidth digits."""
    return s.translate(_DIGIT_MAP)


def is_null(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip().lower() in {"", "null", "none", "n/a", "na", "not available", "-"}:
        return True
    if isinstance(v, list) and len(v) == 0:
        return True
    return False


def to_number(v):
    if is_null(v):
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = western_digits(str(v))
    s = re.sub(r"(?i)rs\.?|inr|₹|kwh|kw|kva|units?", "", s)
    s = s.replace(",", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def to_bool(v):
    if is_null(v):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"true", "yes", "y", "1"}:
        return True
    if s in {"false", "no", "n", "0"}:
        return False
    return None


def norm_text(v) -> str:
    s = unicodedata.normalize("NFKC", western_digits(str(v))).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compact(v) -> str:
    return re.sub(r"[\W_]", "", norm_text(v))


_DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y", "%d-%b-%y"]


def to_date(v):
    if is_null(v):
        return None
    s = western_digits(str(v)).strip()
    for f in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, f).date().isoformat()
        except ValueError:
            pass
    return s


def to_month(v):
    if is_null(v):
        return None
    s = western_digits(str(v)).strip()
    m = re.match(r"^(\d{4})[-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    for f in ("%b-%Y", "%b %Y", "%B %Y", "%b-%y", "%m/%Y", "%m-%Y"):
        try:
            return dt.datetime.strptime(s, f).strftime("%Y-%m")
        except ValueError:
            pass
    return s


# ---------------------------------------------------------------- DISCOM / state aliases
# canonical code -> aliases (compared after compact())
DISCOM_ALIASES: dict[str, list[str]] = {
    "MSEDCL": ["msedcl", "mahadiscom", "mahavitaran", "maharashtra state electricity distribution", "महावितरण", "mseb"],
    "BRPL": ["brpl", "bses rajdhani", "rajdhani power"],
    "BYPL": ["bypl", "bses yamuna", "yamuna power"],
    "TPDDL": ["tpddl", "tata power ddl", "tata power delhi", "ndpl", "north delhi power"],
    "NDMC": ["ndmc", "new delhi municipal"],
    "BESCOM": ["bescom", "bangalore electricity supply", "bengaluru electricity supply"],
    "HESCOM": ["hescom", "hubli electricity"],
    "GESCOM": ["gescom", "gulbarga electricity", "kalaburagi electricity"],
    "MESCOM": ["mescom", "mangalore electricity"],
    "CESCOM": ["cescom", "chamundeshwari"],
    "CESC": ["cesc limited", "calcutta electric supply", "cesc ltd"],
    "TNPDCL": ["tnpdcl", "tangedco", "tneb", "tamil nadu power distribution", "tamil nadu generation and distribution", "tamil nadu electricity"],
    "UPPCL": ["uppcl", "uttar pradesh power corporation"],
    "PVVNL": ["pvvnl", "paschimanchal"],
    "MVVNL": ["mvvnl", "madhyanchal"],
    "DVVNL": ["dvvnl", "dakshinanchal"],
    "PUVVNL": ["puvvnl", "purvanchal"],
    "KESCO": ["kesco", "kanpur electricity"],
    "WBSEDCL": ["wbsedcl", "west bengal state electricity"],
    "APEPDCL": ["apepdcl", "eastern power distribution company of andhra"],
    "APSPDCL": ["apspdcl", "southern power distribution company of andhra"],
    "APCPDCL": ["apcpdcl", "central power distribution company of andhra"],
    "TGSPDCL": ["tgspdcl", "tsspdcl", "southern power distribution company of telangana"],
    "TGNPDCL": ["tgnpdcl", "tsnpdcl", "northern power distribution company of telangana"],
    "KSEB": ["kseb", "kerala state electricity"],
    "PSPCL": ["pspcl", "punjab state power"],
    "UHBVN": ["uhbvn", "uttar haryana"],
    "DHBVN": ["dhbvn", "dakshin haryana"],
    "JVVNL": ["jvvnl", "jaipur vidyut"],
    "AVVNL": ["avvnl", "ajmer vidyut"],
    "JDVVNL": ["jdvvnl", "jodhpur vidyut"],
    "MPPKVVCL": ["mppkvvcl", "paschim kshetra"],
    "MPMKVVCL": ["mpmkvvcl", "madhya kshetra"],
    "MPPOKVVCL": ["mppokvvcl", "purv kshetra", "poorv kshetra"],
    "CSPDCL": ["cspdcl", "chhattisgarh state power distribution"],
    "TPCODL": ["tpcodl", "tp central odisha"],
    "TPSODL": ["tpsodl", "tp southern odisha"],
    "TPNODL": ["tpnodl", "tp northern odisha"],
    "TPWODL": ["tpwodl", "tp western odisha"],
    "JBVNL": ["jbvnl", "jharkhand bijli"],
    "NBPDCL": ["nbpdcl", "north bihar power"],
    "SBPDCL": ["sbpdcl", "south bihar power"],
    "APDCL": ["apdcl", "assam power distribution"],
    "TORRENT": ["torrent power"],
    "AEML": ["aeml", "adani electricity mumbai", "adani electricity"],
    "BEST": ["best undertaking", "brihanmumbai electric"],
    "TATAPOWER_MUMBAI": ["tata power company", "tata power mumbai"],
    "DGVCL": ["dgvcl", "dakshin gujarat"],
    "MGVCL": ["mgvcl", "madhya gujarat"],
    "PGVCL": ["pgvcl", "paschim gujarat"],
    "UGVCL": ["ugvcl", "uttar gujarat"],
    "HPSEBL": ["hpsebl", "hpseb", "himachal pradesh state electricity"],
    "UPCL": ["upcl", "uttarakhand power"],
    "GOA_ED": ["goa electricity department", "electricity department goa"],
}
_DISCOM_LOOKUP = sorted(((compact(a), code) for code, al in DISCOM_ALIASES.items() for a in al), key=lambda x: -len(x[0]))

STATE_ALIASES: dict[str, list[str]] = {
    "delhi": ["delhi", "new delhi", "nct of delhi", "nctd", "dl"],
    "maharashtra": ["maharashtra", "mh", "महाराष्ट्र"],
    "karnataka": ["karnataka", "ka"],
    "tamil nadu": ["tamil nadu", "tamilnadu", "tn"],
    "uttar pradesh": ["uttar pradesh", "up"],
    "west bengal": ["west bengal", "wb"],
    "odisha": ["odisha", "orissa", "od"],
    "telangana": ["telangana", "ts", "tg"],
    "andhra pradesh": ["andhra pradesh", "ap"],
    "gujarat": ["gujarat", "gj"],
    "rajasthan": ["rajasthan", "rj"],
    "madhya pradesh": ["madhya pradesh", "mp"],
    "kerala": ["kerala", "kl"],
    "punjab": ["punjab", "pb"],
    "haryana": ["haryana", "hr"],
    "bihar": ["bihar", "br"],
    "jharkhand": ["jharkhand", "jh"],
    "chhattisgarh": ["chhattisgarh", "chattisgarh", "cg"],
    "assam": ["assam", "as"],
    "uttarakhand": ["uttarakhand", "uttaranchal", "uk"],
    "himachal pradesh": ["himachal pradesh", "hp"],
    "goa": ["goa", "ga"],
}
_STATE_LOOKUP = {compact(a): k for k, al in STATE_ALIASES.items() for a in al}


def discom_code(v) -> str | None:
    if is_null(v):
        return None
    c = compact(v)
    # explicit short code in brackets wins, e.g. "... (BRPL)"
    m = re.search(r"\(([A-Za-z]{3,10})\)", str(v))
    if m:
        cc = compact(m.group(1))
        for alias, code in _DISCOM_LOOKUP:
            if cc == alias:
                return code
    for alias, code in _DISCOM_LOOKUP:
        if alias and alias in c:
            return code
    return None


def norm_state(v) -> str | None:
    if is_null(v):
        return None
    c = compact(v)
    return _STATE_LOOKUP.get(c, norm_text(v))


_TITLES = r"\b(mr|mrs|ms|miss|shri|sri|smt|sh|kum|kumari|dr|late|m s|ms|श्री|श्रीमती)\b"


def norm_name(v) -> str:
    s = norm_text(v)
    s = re.sub(_TITLES, " ", s)
    return " ".join(sorted(s.split()))


def norm_phase(v):
    if is_null(v):
        return None
    s = norm_text(v)
    if re.search(r"\b(1|single|one|1ph|1 ph)\b", s) or s.startswith("single") or s.startswith("1"):
        return "single"
    if re.search(r"\b(3|three|poly|3ph)\b", s) or s.startswith("three") or s.startswith("3"):
        return "three"
    return s


def norm_cycle(v):
    if is_null(v):
        return None
    s = compact(v)
    if s.startswith("bi") or "2month" in s or "twomonth" in s:
        return "bimonthly"
    if s.startswith("month"):
        return "monthly"
    return s


def norm_reading(v):
    if is_null(v):
        return None
    s = compact(v)
    if s.startswith("act") or s in {"normal", "ok", "regular"}:
        return "actual"
    if s.startswith("est") or s.startswith("avg") or s.startswith("aver") or s.startswith("assess") or s in {"rna", "locked", "doorlocked", "faulty"}:
        return "estimated"
    if s.startswith("unk"):
        return "unknown"
    return s


# ---------------------------------------------------------------- comparators
def num_close(a, b, rel=0.01) -> bool:
    if a is None or b is None:
        return False
    if a == b:
        return True
    return abs(a - b) <= rel * max(abs(a), abs(b))


def fuzzy(a: str, b: str, thresh=0.8) -> bool:
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= thresh


_TARIFF_WORDS = r"(domestic|residential|resi|res|urban|rural|general|normal|tariff|category|phase|single|three|non|commercial|net|metering|purpose|supply|consumer)"


def latin(v) -> str:
    """compact() but keep only ASCII letters/digits (drops Indian-script words)."""
    return re.sub(r"[^a-z0-9]", "", compact(v))


def tariff_code(v) -> str:
    """Tariff code part only, e.g. 'LT2A(i) Domestic' and 'LT2A(i) ಗೃಹ' -> 'lt2ai'."""
    s = re.sub(r"[^a-z0-9 ]", " ", norm_text(v))
    s = re.sub(rf"\b{_TARIFF_WORDS}\b", " ", s)
    return re.sub(r"\s", "", s)


def history_pairs(v) -> list[tuple[str, float]]:
    if is_null(v) or not isinstance(v, list):
        return []
    out = []
    for item in v:
        if not isinstance(item, dict):
            continue
        m = to_month(item.get("month"))
        u = to_number(item.get("units_kwh", item.get("units")))
        if m and u is not None:
            out.append((m, u))
    return out


def history_f1(label, pred) -> float:
    lp, pp = history_pairs(label), history_pairs(pred)
    if not lp and not pp:
        return 1.0
    if not lp or not pp:
        return 0.0
    used = set()
    tp = 0
    for m, u in lp:
        for j, (pm, pu) in enumerate(pp):
            if j not in used and pm == m and num_close(u, pu):
                used.add(j)
                tp += 1
                break
    if tp == 0:
        return 0.0
    prec, rec = tp / len(pp), tp / len(lp)
    return 2 * prec * rec / (prec + rec)


def field_score(field: str, label_v, pred_v) -> float:
    """Return 0..1 for one field. Null handling: both null = 1, one null = 0.

    Extension to SCHEMA.md: for any non-list field the label may give a list of
    accepted alternatives, e.g. "consumer_name": ["रमेश पाटील", "Ramesh Patil"].
    """
    if field == "consumption_history":
        return history_f1(label_v, pred_v)
    if isinstance(label_v, list):
        return max((_field_score(field, alt, pred_v) for alt in label_v), default=float(is_null(pred_v)))
    return _field_score(field, label_v, pred_v)


def _field_score(field: str, label_v, pred_v) -> float:
    ln, pn = is_null(label_v), is_null(pred_v)
    if ln and pn:
        return 1.0
    if ln or pn:
        return 0.0
    if field in {"units_billed_kwh", "sanctioned_load_kw", "bill_amount_rs", "export_units_kwh"}:
        return float(num_close(to_number(label_v), to_number(pred_v)))
    if field == "billing_days":
        a, b = to_number(label_v), to_number(pred_v)
        return float(a is not None and b is not None and int(a) == int(b))
    if field in {"is_residential", "has_solar_net_meter", "is_electricity_bill"}:
        return float(to_bool(label_v) == to_bool(pred_v) and to_bool(label_v) is not None)
    if field == "discom":
        lc, pc = discom_code(label_v), discom_code(pred_v)
        if lc and pc:
            return float(lc == pc)
        return float(fuzzy(norm_text(label_v), norm_text(pred_v), 0.85))
    if field == "state":
        return float(norm_state(label_v) == norm_state(pred_v))
    if field == "tariff_category":
        lc, pc = tariff_code(label_v), tariff_code(pred_v)
        if lc and pc:
            return float(lc == pc or (min(len(lc), len(pc)) >= 3 and (lc in pc or pc in lc)))
        if lc and not pc:  # label has a code, prediction does not
            return 0.0
        return float(fuzzy(latin(label_v), latin(pred_v), 0.8))
    if field in {"billing_period_start", "billing_period_end"}:
        return float(to_date(label_v) == to_date(pred_v))
    if field == "billing_cycle":
        return float(norm_cycle(label_v) == norm_cycle(pred_v))
    if field == "meter_reading_type":
        return float(norm_reading(label_v) == norm_reading(pred_v))
    if field == "consumer_number":
        a, b = compact(label_v).upper().lstrip("0"), compact(pred_v).upper().lstrip("0")
        return float(a == b)
    if field == "consumer_name":
        return float(norm_name(label_v) == norm_name(pred_v))
    if field == "pincode":
        return float(re.sub(r"\D", "", western_digits(str(label_v))) == re.sub(r"\D", "", western_digits(str(pred_v))))
    if field == "connection_phase":
        return float(norm_phase(label_v) == norm_phase(pred_v))
    return float(norm_text(label_v) == norm_text(pred_v))


def score(label_fields: dict, pred: dict | None) -> dict:
    """Score one prediction. Returns {"score": 0..100, "fields": {field: 0..1}}."""
    pred = pred or {}
    fields = {f: field_score(f, label_fields.get(f), pred.get(f)) for f in ALL_FIELDS}
    total = sum(FIELD_WEIGHTS[f] * fields[f] for f in FIELD_WEIGHTS)
    return {"score": round(total, 2), "fields": fields}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    label = json.load(open(sys.argv[1]))
    pred = json.load(open(sys.argv[2]))
    res = score(label["fields"], pred.get("fields", pred))
    print(f"score: {res['score']}")
    for f, v in res["fields"].items():
        print(f"  {f:24s} {v:.2f}  w={FIELD_WEIGHTS.get(f, 0):.2f}")
