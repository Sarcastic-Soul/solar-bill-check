"""Write eval/bills/INDEX.md from the labels.

Usage:
    python eval/tools/build_index.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from billkit import BILLS_DIR  # noqa: E402

# Short "what this bill tests" text. Anything missing falls back to the first sentence of the notes.
EDGE = {
    "delhi-brpl-hindi-clean-01": "Baseline bilingual Delhi bill, partial subsidy, 6-month history",
    "delhi-bypl-zero-subsidy-01": "Zero bill from the Delhi 200-unit subsidy (amount 0, units still 168)",
    "delhi-tpddl-3phase-7kw-01": "3-phase 7 kW, high summer usage, Indian comma amounts, extra KVAH row",
    "msedcl-marathi-devanagari-01": "Devanagari digits everywhere, name in Devanagari, 12-month bar chart",
    "msedcl-marathi-estimated-01": "Estimated (RNA / average) reading",
    "uppcl-hindi-arrears-01": "Large arrears (Rs 1,12,486) shown apart from current bill; Hindi name",
    "tnpdcl-tamil-bimonthly-01": "Tamil, bi-monthly cycle, slab subsidy, dashed consumer number",
    "cesc-bengali-01": "Bengali, dotted dates, vertical bar-chart history",
    "ugvcl-gujarati-bimonthly-01": "Gujarati, bi-monthly cycle, FPPPA charge, rounded total",
    "tgspdcl-telugu-commercial-01": "Commercial (non-residential), two IDs printed",
    "bescom-kannada-01": "Thermal spot bill, Gruha Jyothi free units, two IDs printed",
    "kseb-malayalam-bimonthly-01": "Thermal spot bill, bi-monthly, load printed in watts",
    "adani-mumbai-solar-english-01": "Rooftop solar net meter (import/export/net)",
    "tatapower-mumbai-nohistory-01": "Current month only, no history (history must be null)",
    "nonbill-water-bill-01": "Not an electricity bill (water bill)",
    "msedcl-lt-official-01": "Official format; masked fields, annotations, about 2-month period",
    "msedcl-solar-official-01": "Official solar net-meter format; non-residential, load in HP, arrears",
    "tpddl-handbook-official-01": "Official handbook sample; low resolution, step stickers, zero bill",
}


def short_discom(d) -> str:
    if d is None:
        return "-"
    if isinstance(d, list):
        d = d[-1]
    m = re.search(r"\(([A-Z]{3,})\)", d)
    if m:
        return m.group(1)
    return "Tata Power (Mumbai)" if "Tata Power Company" in d else d


def main():
    rows = []
    for d in sorted(p for p in BILLS_DIR.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        lab = json.loads((d / "label.json").read_text(encoding="utf-8"))
        bid = lab["id"]
        base = bid[:-6] if bid.endswith("-photo") else bid
        edge = EDGE.get(base) or lab["notes"].removeprefix("Tests: ").split(". ")[0]
        if bid.endswith("-photo"):
            edge = f"Phone-photo copy of `{base}`"
        img = next(d.glob("bill.*")).name
        rows.append((bid, short_discom(lab["fields"]["discom"]), ", ".join(lab["languages"]), lab["difficulty"],
                     lab["source"], img, edge))

    n_off = sum(r[4] == "official_sample" for r in rows)
    n_photo = sum(r[3] == "phone_photo" for r in rows)
    out = [
        "# Eval bills",
        "",
        f"{len(rows)} bills: {n_off} official samples, {len(rows) - n_off - n_photo} clean mocks, "
        f"{n_photo} phone-photo variants. Labels follow `eval/SCHEMA.md`. Mock bills use made-up people, "
        "addresses and numbers and carry a SAMPLE mark; DISCOM names appear as plain text only.",
        "",
        "Regenerate (from the repo root):",
        "",
        "```sh",
        "uv run --with playwright --with jinja2 --with pillow python eval/tools/make_mock_bills.py",
        "uv run --with pillow python -I eval/tools/prepare_official_samples.py   # downloads into a new temp dir",
        "uv run --with opencv-python-headless --with numpy --with pillow python eval/tools/make_photo_variants.py",
        "uv run --with pillow python eval/tools/validate_labels.py",
        "python eval/tools/build_index.py",
        "```",
        "",
        "| id | DISCOM | languages | difficulty | source | file | edge case tested |",
        "|---|---|---|---|---|---|---|",
    ]
    out += [f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |" for r in rows]
    out.append("")
    (BILLS_DIR / "INDEX.md").write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {BILLS_DIR / 'INDEX.md'} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
