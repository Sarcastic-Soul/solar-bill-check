"""Download official sample bills published by DISCOMs, turn them into bill images, and write their labels.

The downloads are untrusted data. They go into a fresh empty directory (a new temp dir by default, or
--download-dir, which must be empty or not exist yet). PDFs are rasterised with poppler's `pdftoppm`
into a separate work directory; nothing from the download is ever executed.

Usage:
    uv run --with pillow python -I eval/tools/prepare_official_samples.py [--download-dir DIR] [--reuse DIR]

--reuse DIR skips the download and reads already-downloaded files from DIR (same file names as below).

Labels here were written by hand from the rendered images. If you change a crop or a page, re-check them.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from billkit import BILLS_DIR, fields, save_image, write_label  # noqa: E402

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

SOURCES = {
    "msedcl_lt.pdf": "https://www.mahadiscom.in/wp-content/uploads/2026/09/lt-2026-for-web.pdf",
    "msedcl_solar.pdf": "https://www.mahadiscom.in/wp-content/uploads/2026/09/ltip-solar-2026-for-web.pdf",
    "tpddl.pdf": "https://tatapower-ddl.com/Editor_UploadedDocuments/Content/Customer_Handbook_FY26.pdf",
}


def download(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        sys.exit(f"download dir {dest} is not empty; use a fresh directory")
    for name, url in SOURCES.items():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        if not data.startswith(b"%PDF"):
            sys.exit(f"{url} did not return a PDF")
        (dest / name).write_bytes(data)
        print(f"downloaded {name} ({len(data)} bytes)")


def render_page(pdf: Path, page: int, dpi: int, work: Path):
    from PIL import Image

    prefix = work / f"{pdf.stem}-{page}-{dpi}"
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page), "-singlefile", "-png",
                    str(pdf), str(prefix)], check=True)
    return Image.open(f"{prefix}.png").convert("RGB")


# ------------------------------------------------------------------ MSEDCL LT residential format

def msedcl_lt(dl: Path, work: Path):
    from PIL import ImageDraw

    dpi = 170
    img = render_page(dl / "msedcl_lt.pdf", 1, dpi, work)
    # The published format over-types the name/address with X but the original text is still partly
    # readable. Black it out fully (coordinates measured at 150 dpi), plus the mobile/e-mail field.
    k = dpi / 150
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1 in [(16, 162, 514, 214), (438, 138, 624, 163)]:
        d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=(0, 0, 0))
    bill_id = "msedcl-lt-official-01"
    out = save_image(img, BILLS_DIR / bill_id)
    flds = fields(
        discom="Maharashtra State Electricity Distribution Co. Ltd. (MSEDCL)",
        state="Maharashtra",
        consumer_number=None, consumer_name=None, pincode=None,
        tariff_category="90/LT I Res 1-Phase",
        is_residential=True,
        sanctioned_load_kw=0.26,
        connection_phase="single",
        billing_period_start="2026-07-01",
        billing_period_end="2026-09-02",
        billing_days=63,
        billing_cycle="monthly",
        units_billed_kwh=504,
        bill_amount_rs=6150.00,
        consumption_history=[
            ("2026-09", 504), ("2026-08", 621), ("2026-07", 515), ("2026-06", 627), ("2026-05", 721),
            ("2026-04", 423), ("2026-03", 248), ("2026-02", 233), ("2026-01", 230), ("2025-12", 300),
            ("2025-11", 360), ("2025-09", 395),
        ],
        has_solar_net_meter=False,
        export_units_kwh=None,
        meter_reading_type="actual",
    )
    notes = (
        "Tests: official MSEDCL LT residential bill format (Marathi + English), page 1 of 2. Name, address and "
        "mobile are blacked out by us; consumer number, bill number and meter number are masked with X in the "
        "original, so they are null. Annotations 'Billing Period' and 'Billing History' with red arrows are "
        "added by MSEDCL, not part of a real bill. Reading dates 01-07-2026 to 02-09-2026 give 63 days (not "
        "printed; 'Bill Period: 2.10' months is printed). MSEDCL bills monthly, so billing_cycle is monthly even "
        "though this bill covers about two months. Units 504 = 32828 - 32324. bill_amount_rs is the amount "
        "printed on page 1 (6150.00); page 2 of the PDF (not included) shows an average-bill adjustment and "
        "arrears. History: chart Aug-2026..Nov-2025 plus the comparison box (Sep-2025 395, Sep-2026 504). The "
        "Oct-2025 bar has its value cut off ('ऑक्टोबर-2025...'), so it is left out."
    )
    write_label(bill_id, "official_sample", ["mr", "en"], "clean", flds, notes, source_url=SOURCES["msedcl_lt.pdf"])
    return bill_id, out


# ------------------------------------------------------------------ MSEDCL LT-IP solar (net meter) format

def msedcl_solar(dl: Path, work: Path):
    from PIL import Image

    dpi = 200
    p1 = render_page(dl / "msedcl_solar.pdf", 1, dpi, work)
    p2 = render_page(dl / "msedcl_solar.pdf", 2, dpi, work)
    gap = 24
    h = max(p1.height, p2.height)
    canvas = Image.new("RGB", (p1.width + gap + p2.width, h), "white")
    canvas.paste(p1, (0, 0))
    canvas.paste(p2, (p1.width + gap, 0))
    bill_id = "msedcl-solar-official-01"
    out = save_image(canvas, BILLS_DIR / bill_id)
    flds = fields(
        discom="Maharashtra State Electricity Distribution Co. Ltd. (MSEDCL)",
        state="Maharashtra",
        consumer_number=None, consumer_name=None, pincode=None,
        tariff_category="35 LT-III A Public Water Works",
        is_residential=False,
        sanctioned_load_kw=2.98,
        connection_phase=None,
        billing_period_start="2026-07-31",
        billing_period_end="2026-08-31",
        billing_days=31,
        billing_cycle="monthly",
        units_billed_kwh=384,
        bill_amount_rs=2706.79,
        consumption_history=[
            ("2026-08", 369), ("2026-07", 416), ("2026-06", 471), ("2026-05", 411), ("2026-04", 461),
            ("2026-03", 407), ("2026-02", 362), ("2026-01", 477), ("2025-12", 313), ("2025-11", 442),
            ("2025-10", 359), ("2025-09", 313), ("2025-08", 329),
        ],
        has_solar_net_meter=True,
        export_units_kwh=1,
        meter_reading_type="actual",
    )
    notes = (
        "Tests: official MSEDCL LT-IP solar net-meter bill format (English), pages 1 and 2 side by side; page 3 "
        "of the PDF is blank. Non-residential (public water works, LT-III A). Consumer number, name, address "
        "and pincode are masked with X in the original, so null. Sanctioned load is printed as 4.00 HP; "
        "labelled as 2.98 kW (1 HP = 0.746 kW). No phase printed. Units billed 384 = 385 import - 1 export "
        "(Total Consumption 384.00; 'Billed: 384.00'). bill_amount_rs is TOTAL CURRENT BILL 2706.79; principal "
        "arrears 2054.45 are separate (rounded total 4760.00). History is the 13-month BILLING HISTORY table. "
        "The yellow highlight boxes and the 'Billing History' arrow are MSEDCL annotations."
    )
    write_label(bill_id, "official_sample", ["en"], "clean", flds, notes, source_url=SOURCES["msedcl_solar.pdf"])
    return bill_id, out


# ------------------------------------------------------------------ TPDDL customer handbook sample bill

def tpddl_handbook(dl: Path, work: Path):
    img = render_page(dl / "tpddl.pdf", 9, 300, work)  # handbook page labelled "08"
    img = img.crop((68, 262, 1666, 2205))
    bill_id = "tpddl-handbook-official-01"
    out = save_image(img, BILLS_DIR / bill_id)
    flds = fields(
        discom="Tata Power Delhi Distribution Limited (TPDDL)",
        state="Delhi",
        consumer_number=None, consumer_name=None, pincode=None,
        tariff_category="Domestic Lighting DL",
        is_residential=True,
        sanctioned_load_kw=1.0,
        connection_phase="single",
        billing_period_start="2024-12-27",
        billing_period_end="2025-01-21",
        billing_days=26,
        billing_cycle="monthly",
        units_billed_kwh=100,
        bill_amount_rs=0.0,
        consumption_history=[
            ("2025-01", 100), ("2024-12", 70), ("2024-10", 286), ("2024-09", 283), ("2024-08", 366),
            ("2024-07", 311),
        ],
        has_solar_net_meter=False,
        export_units_kwh=None,
        meter_reading_type="actual",
    )
    notes = (
        "Tests: official TPDDL sample bill from the FY26 customer handbook (page labelled 08), Hindi + English. "
        "Low resolution in the source PDF, and orange 'Step N' stickers cover parts of the bill, hence "
        "difficulty blurry. Name and address are blank; the CA number is cut off ('60...'), so null. Readings "
        "184 - 77 = 107 units consumed; 7 CCT/LED/WiFi units are deducted and energy is charged on 100 units, "
        "so units_billed_kwh = 100. Net current demand 448.56 is fully cancelled by the Delhi subsidy (-448.56); "
        "the pay box says NOT TO PAY, so bill_amount_rs = 0. History is the last-six-bills table on the right "
        "(period end months); the second row's period (27/10/24 to 26/12/24, 70 units) is hard to read."
    )
    write_label(bill_id, "official_sample", ["hi", "en"], "blurry", flds, notes, source_url=SOURCES["tpddl.pdf"],
                extra={"low_confidence_fields": ["consumption_history"]})
    return bill_id, out


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--download-dir", type=Path)
    g.add_argument("--reuse", type=Path)
    a = ap.parse_args()
    if a.reuse:
        dl = a.reuse
    else:
        dl = a.download_dir or Path(tempfile.mkdtemp(prefix="bill-dl-"))
        download(dl)
    with tempfile.TemporaryDirectory(prefix="bill-render-") as w:
        work = Path(w)
        for fn in (msedcl_lt, msedcl_solar, tpddl_handbook):
            bill_id, out = fn(dl, work)
            print(f"{bill_id:<32} {out.name}")


if __name__ == "__main__":
    main()
