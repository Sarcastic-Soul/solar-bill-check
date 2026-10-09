"""Shared helpers for building eval bills: number formats, slab math, labels, rendering."""

from __future__ import annotations

import io
import json
import math
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BILLS_DIR = ROOT / "eval" / "bills"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

MAX_SIDE = 2000
MAX_BYTES = int(3.75 * 1024 * 1024)

DEV_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "mr": ["जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून", "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर", "डिसेंबर"],
    "ta": ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"],
    "kn": ["ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್", "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"],
    "bn": ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"],
    "gu": ["જાન્યુઆરી", "ફેબ્રુઆરી", "માર્ચ", "એપ્રિલ", "મે", "જૂન", "જુલાઈ", "ઓગસ્ટ", "સપ્ટેમ્બર", "ઓક્ટોબર", "નવેમ્બર", "ડિસેમ્બર"],
    "te": ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జూలై", "ఆగస్టు", "సెప్టెంబర్", "అక్టోబర్", "నవంబర్", "డిసెంబర్"],
    "ml": ["ജനുവരി", "ഫെബ്രുവരി", "മാർച്ച്", "ഏപ്രിൽ", "മേയ്", "ജൂൺ", "ജൂലൈ", "ഓഗസ്റ്റ്", "സെപ്റ്റംബർ", "ഒക്ടോബർ", "നവംബർ", "ഡിസംബർ"],
}


def r2(x: float) -> float:
    return float(f"{x + 1e-9:.2f}") if x >= 0 else -float(f"{-x + 1e-9:.2f}")


def indian_group(intpart: str) -> str:
    if len(intpart) <= 3:
        return intpart
    head, tail = intpart[:-3], intpart[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def num(x, dec=2, indian=False, western_commas=False, dev=False) -> str:
    """Format a number the way a bill prints it."""
    neg = x < 0
    s = f"{abs(x):.{dec}f}"
    ip, _, fp = s.partition(".")
    if indian:
        ip = indian_group(ip)
    elif western_commas:
        ip = f"{int(ip):,}"
    out = ip + ("." + fp if fp else "")
    if neg:
        out = "-" + out
    return out.translate(DEV_DIGITS) if dev else out


def dev(s: str) -> str:
    return str(s).translate(DEV_DIGITS)


def dmy(d: date, sep="-") -> str:
    return d.strftime(f"%d{sep}%m{sep}%Y")


def month_label(ym: str, lang="en", sep="-", short_year=False) -> str:
    y, m = ym.split("-")
    yy = y[2:] if short_year else y
    return f"{MONTHS[lang][int(m) - 1]}{sep}{yy}"


def slab_calc(units: float, bands: list[tuple[float, float]]):
    """Telescopic slab billing. bands = [(upper_limit, rate), ...]. Returns (rows, total)."""
    rows, lo, total = [], 0, 0.0
    for upper, rate in bands:
        if units <= lo:
            break
        u = min(units, upper) - lo
        amt = r2(u * rate)
        rows.append((lo + 1 if lo else 0, upper, u, rate, amt))
        total += amt
        lo = upper
    return rows, r2(total)


def slab_text(lo, hi):
    return f"{lo}-{int(hi)}" if hi != math.inf else f">{lo - 1}"


def bars(items, max_pct=100):
    """items: [(label, value_str, value)] -> [(label, value_str, pct)]"""
    top = max(v for _, _, v in items) or 1
    return [(lab, vs, round(max_pct * v / top, 1)) for lab, vs, v in items]


FIELD_ORDER = [
    "is_electricity_bill", "discom", "state", "consumer_number", "consumer_name", "tariff_category",
    "is_residential", "sanctioned_load_kw", "connection_phase", "billing_period_start", "billing_period_end",
    "billing_days", "billing_cycle", "units_billed_kwh", "bill_amount_rs", "consumption_history",
    "has_solar_net_meter", "export_units_kwh", "meter_reading_type", "pincode",
]


def fields(**kw) -> dict:
    out = {k: None for k in FIELD_ORDER}
    out["is_electricity_bill"] = True  # every bill here is an electricity bill unless told otherwise
    for k, v in kw.items():
        if k not in out:
            raise KeyError(k)
        if isinstance(v, date):
            v = v.isoformat()
        out[k] = v
    if out["consumption_history"] is not None:
        out["consumption_history"] = [{"month": m, "units_kwh": u} for m, u in out["consumption_history"]]
    return out


def write_label(bill_id: str, source: str, languages: list[str], difficulty: str, flds: dict,
                notes: str, source_url: str | None = None, extra: dict | None = None) -> Path:
    d = BILLS_DIR / bill_id
    d.mkdir(parents=True, exist_ok=True)
    label = {
        "id": bill_id,
        "source": source,
        "source_url": source_url,
        "languages": languages,
        "difficulty": difficulty,
        "fields": flds,
        "notes": notes,
    }
    if extra:
        label.update(extra)
    p = d / "label.json"
    p.write_text(json.dumps(label, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def save_image(img, out_dir: Path, prefer="png", jpeg_quality=90) -> Path:
    """Fit to MAX_SIDE, save as bill.png (or bill.jpg), and make sure it is under MAX_BYTES."""
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("bill.*"):
        old.unlink()
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, MAX_SIDE / max(w, h))
    if scale < 1.0:
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    if prefer == "png":
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        if buf.tell() < MAX_BYTES:
            p = out_dir / "bill.png"
            p.write_bytes(buf.getvalue())
            return p
    q = jpeg_quality
    while True:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=q, optimize=True)
        if buf.tell() < MAX_BYTES or q <= 40:
            p = out_dir / "bill.jpg"
            p.write_bytes(buf.getvalue())
            return p
        q -= 5
