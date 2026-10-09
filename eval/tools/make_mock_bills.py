"""Generate mock Indian electricity bills (HTML -> PNG) with exact ground-truth labels.

All names, addresses, consumer numbers and meter numbers are made up. DISCOM names are
plain text only (no logos), and each bill carries a SAMPLE mark.

Run from the repo root:
    uv run --with playwright --with jinja2 --with pillow python eval/tools/make_mock_bills.py
Needs Google Chrome installed (uses Playwright's channel="chrome"); set BILL_BROWSER=chromium
to use Playwright's bundled Chromium instead (after `playwright install chromium`).
"""

from __future__ import annotations

import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from billkit import (  # noqa: E402
    BILLS_DIR, TEMPLATES_DIR, bars, dev, dmy, fields, month_label, num, r2, save_image,
    slab_calc, slab_text, write_label,
)

INF = math.inf
BILLS: list[dict] = []  # each: id, template, ctx, languages, fields, notes


def register(fn):
    BILLS.append(fn())
    return fn


def money(x, **kw):
    return "₹ " + num(x, **kw)


# ---------------------------------------------------------------- Delhi (BRPL / BYPL / TPDDL)

def delhi_calc(units, load_kw):
    rows, energy = slab_calc(units, [(200, 3.00), (400, 4.50), (800, 6.50), (1200, 7.00), (INF, 8.00)])
    rate = 20 if load_kw <= 2 else 50 if load_kw <= 5 else 100
    fixed = r2(load_kw * rate)
    base = fixed + energy
    ppac = r2(base * 0.1819)
    sur = r2(base * 0.08)
    pts = r2(base * 0.07)
    sub = r2(base + ppac + sur + pts)
    tax = r2(sub * 0.05)
    gross = r2(sub + tax)
    if units <= 200:
        subsidy = gross
    elif units <= 400:
        subsidy = min(r2(0.5 * energy), 800.0)
    else:
        subsidy = 0.0
    net = r2(gross - subsidy)
    return dict(rows=rows, energy=energy, fixed=fixed, fixed_rate=rate, ppac=ppac, sur=sur, pts=pts,
                tax=tax, gross=gross, subsidy=subsidy, net=net)


def delhi_bill(*, bill_id, org_en, org_hi, short, accent, accent_light, accent_dark, ca, name, address,
               pincode, load, phase, start, end, prev, curr, bill_date, due, meter_no, history,
               indian=False, note=None, notes="", extra_reading_rows=()):
    units = curr - prev
    days = (end - start).days
    c = delhi_calc(units, load)
    m = lambda x: num(x, indian=indian)  # noqa: E731
    hist_rows = []
    for ym, u in history:
        y, mo = map(int, ym.split("-"))
        hist_rows.append([month_label(ym, "en").upper(), m(delhi_calc(u, load)["net"]), u, "Actual"])
    phase_txt = "1 Phase / एकल फेज" if phase == "single" else "3 Phase / तीन फेज"
    ctx = dict(
        html_lang="hi", accent=accent, accent_light=accent_light, accent_dark=accent_dark,
        org_line1=org_en, org_line2=org_hi,
        title="Bill of Supply for Electricity", title2="बिजली आपूर्ति का बिल",
        band=[f"Helpline 19123 (SAMPLE)", f"Bill Month / बिल माह : {end.strftime('%b-%Y').upper()}",
              f"Bill Date / बिल तिथि : {dmy(bill_date)}"],
        info_cols=[
            [("Name / नाम", name), ("Address / पता", address), ("Mobile", "98XXXXXX21"),
             ("Bill Basis / बिल आधार", "Actual / वास्तविक")],
            [("Sanctioned Load / स्वीकृत भार", f"{load:.2f} kW"), ("Supply Type / आपूर्ति", phase_txt),
             ("Tariff Category / श्रेणी", "Domestic (DX) / घरेलू"), ("Power Factor", "1.000")],
            [("CA No. / उपभोक्ता सं.", ca), ("Meter No. / मीटर सं.", meter_no),
             ("Due Date / देय तिथि", dmy(due)), ("Bill No.", f"10{ca[-6:]}0926")],
        ],
        reading_title="Meter and Reading Details / मीटर और रीडिंग का विवरण",
        reading_head=["Unit", "Current Reading Date / वर्तमान रीडिंग तिथि", "Current Reading / वर्तमान रीडिंग",
                      "Previous Reading Date / पिछली रीडिंग तिथि", "Previous Reading / पिछली रीडिंग", "MF",
                      "Days / दिन", "Units Consumed / खपत यूनिट"],
        reading_rows=[["KWH", dmy(end), curr, dmy(start), prev, "1.00", days, units], *extra_reading_rows],
        reading_note=note,
        charges_title="Current Demand Details / वर्तमान शुल्क का विवरण",
        slab_head=["Slab / स्लैब (Units)", "Units / यूनिट", "Rate / दर (₹)", "Amount / राशि (₹)"],
        slab_rows=[[slab_text(lo, hi), u, f"{rate:.2f}", m(a)] for lo, hi, u, rate, a in c["rows"]],
        charges=[
            (f"Fixed Charges / स्थायी शुल्क ({load:g} kW × ₹{c['fixed_rate']})", m(c["fixed"])),
            ("Energy Charges / ऊर्जा शुल्क", m(c["energy"])),
            ("PPAC @ 18.19%", m(c["ppac"])),
            ("Surcharge / अधिभार @ 8%", m(c["sur"])),
            ("Pension Trust Charge @ 7%", m(c["pts"])),
            ("Electricity Tax / विद्युत कर @ 5%", m(c["tax"])),
            ("Gross Amount / सकल राशि", m(c["gross"])),
            ("Govt. Subsidy / सरकारी सब्सिडी", "-" + m(c["subsidy"]) if c["subsidy"] else "0.00"),
            ("Arrears / बकाया", "0.00"),
            ("Net Amount Payable / शुद्ध देय राशि", m(c["net"])),
        ],
        pay_label="Amount Payable / कुल देय राशि (₹)",
        pay_value=money(c["net"], indian=indian),
        pay_rows=[("Due Date / देय तिथि", dmy(due)),
                  ("After due date (LPSC)", m(r2(c["net"] * 1.015)) if c["net"] else "0.00")],
        history_title="Details of Last 6 Bills / पिछले 6 बिलों का विवरण",
        history_head=["Bill Month / बिल माह", "Bill Amount / राशि (₹)", "Units / यूनिट", "Basis / आधार"],
        history_rows=hist_rows,
        footer_title="Important Message / महत्वपूर्ण सूचना",
        footer=["Delhi Govt. subsidy: up to 200 units/month — no charge; 201–400 units — 50% of energy "
                "charges, max ₹800. / 200 यूनिट तक बिल शून्य।",
                "Pay online to avoid queues. Keep your CA No. ready while calling the helpline.",
                "This is a computer generated SAMPLE bill for testing only."],
        stub=[f"<b>{short} — Payment Slip</b>", f"CA No.: {ca}", f"Amount: {money(c['net'], indian=indian)}"],
    )
    flds = fields(
        discom=org_en.split(" (")[0] + f" ({short})", state="Delhi", consumer_number=ca, consumer_name=name,
        tariff_category="Domestic (DX)", is_residential=True, sanctioned_load_kw=load, connection_phase=phase,
        billing_period_start=start, billing_period_end=end, billing_days=days, billing_cycle="monthly",
        units_billed_kwh=units, bill_amount_rs=c["net"], consumption_history=history,
        has_solar_net_meter=False, export_units_kwh=None, meter_reading_type="actual", pincode=pincode,
    )
    return dict(id=bill_id, template="standard.html.j2", ctx=ctx, languages=["hi", "en"], fields=flds,
                notes=notes)


@register
def brpl():
    return delhi_bill(
        bill_id="delhi-brpl-hindi-clean-01", org_en="BSES Rajdhani Power Limited", org_hi="बीएसईएस राजधानी पावर लिमिटेड",
        short="BRPL", accent="#c62828", accent_light="#fde9e7", accent_dark="#8e1c1c",
        ca="152839471", name="SUNITA MALHOTRA",
        address="H.No. 214, Pocket C, Sector 7, Dwarka, New Delhi - 110075", pincode="110075",
        load=3.0, phase="single", start=date(2026, 8, 6), end=date(2026, 9, 5), prev=18452, curr=18794,
        bill_date=date(2026, 9, 8), due=date(2026, 9, 22), meter_no="BR2291847",
        history=[("2026-08", 389), ("2026-07", 412), ("2026-06", 455), ("2026-05", 398), ("2026-04", 251), ("2026-03", 186)],
        notes="Tests: clean bilingual Hindi+English Delhi bill, 201-400 unit band with partial subsidy, 6-bill history "
              "(history excludes the current bill). Amount is the net payable after subsidy.",
    )


@register
def bypl():
    return delhi_bill(
        bill_id="delhi-bypl-zero-subsidy-01", org_en="BSES Yamuna Power Limited", org_hi="बीएसईएस यमुना पावर लिमिटेड",
        short="BYPL", accent="#e65100", accent_light="#fff0e0", accent_dark="#9a3600",
        ca="103746258", name="MOHD. IMRAN QURESHI", address="B-47, Gali No. 3, Jafrabad, Delhi - 110053",
        pincode="110053", load=2.0, phase="single", start=date(2026, 8, 12), end=date(2026, 9, 11),
        prev=9076, curr=9244, bill_date=date(2026, 9, 14), due=date(2026, 9, 28), meter_no="BY1173320",
        history=[("2026-08", 192), ("2026-07", 214), ("2026-06", 231), ("2026-05", 187), ("2026-04", 143), ("2026-03", 121)],
        note="ZERO BILL: consumption up to 200 units — full subsidy by GNCTD. / 200 यूनिट तक खपत — "
             "सरकारी सब्सिडी के कारण इस बिल पर कोई राशि देय नहीं।",
        notes="Tests: zero amount payable because of the Delhi 200-free-units subsidy (bill_amount_rs = 0). "
              "Units (168) must still be read correctly; history has months above and below 200.",
    )


@register
def tpddl():
    return delhi_bill(
        bill_id="delhi-tpddl-3phase-7kw-01", org_en="Tata Power Delhi Distribution Limited",
        org_hi="टाटा पावर दिल्ली डिस्ट्रीब्यूशन लिमिटेड", short="TPDDL", accent="#1b7f3b",
        accent_light="#e6f4ea", accent_dark="#0f5226", ca="60014829375", name="RAJIV KHANNA",
        address="C-112, Ashok Vihar Phase II, Delhi - 110052", pincode="110052", load=7.0, phase="three",
        start=date(2026, 7, 20), end=date(2026, 8, 19), prev=45210, curr=46396,
        bill_date=date(2026, 8, 22), due=date(2026, 9, 5), meter_no="TP75092214", indian=True,
        history=[("2026-07", 1342), ("2026-06", 1408), ("2026-05", 1211), ("2026-04", 768), ("2026-03", 512), ("2026-02", 455)],
        extra_reading_rows=[["KVAH", dmy(date(2026, 8, 19)), 49870, dmy(date(2026, 7, 20)), 48632, "1.00", 30, 1238],
                            ["MDI (KW)", dmy(date(2026, 8, 19)), "6.84", "-", "-", "1.00", "-", "-"]],
        notes="Tests: 3-phase 7 kW connection with high summer usage (1186 kWh), no subsidy, amounts in Indian "
              "comma format. Reading table also has a KVAH row (1238) and MDI row; units billed are the KWH units.",
    )


# ---------------------------------------------------------------- MSEDCL (Marathi)

MS_ENERGY = [(100, 3.96), (300, 10.80), (500, 15.03), (1000, 17.53), (INF, 17.53)]
MS_FAC = [(100, 0.15), (300, 0.30), (500, 0.40), (1000, 0.45), (INF, 0.45)]


def msedcl_calc(units, municipal=True):
    _, energy = slab_calc(units, MS_ENERGY)
    _, fac = slab_calc(units, MS_FAC)
    fixed = 130.0 + (10.0 if municipal else 0.0)
    wheel = r2(units * 1.60)
    duty = r2((fixed + energy + wheel + fac) * 0.16)
    total = r2(fixed + energy + wheel + fac + duty)
    rounded = float(round(total / 10) * 10)
    return dict(fixed=fixed, energy=energy, wheel=wheel, fac=fac, duty=duty, total=total, rounded=rounded)


def msedcl_bill(*, bill_id, consumer, name, address, name_latin=None, pincode, load, start, end, prev, curr_display, units,
                bill_date, due, meter_no, bu, history, devanagari, estimated, notes):
    D = (lambda s: dev(s)) if devanagari else (lambda s: str(s))  # noqa: E731
    n = lambda x, dec=2: num(x, dec=dec, dev=devanagari)  # noqa: E731
    c = msedcl_calc(units)
    days = (end - start).days
    bill_month = bill_date  # MSEDCL names the bill after the month it is issued in
    bm_label = D(month_label(f"{bill_month.year}-{bill_month.month:02d}", "mr"))
    status = ("RNA — रिडिंग उपलब्ध नाही (सरासरी देयक)" if estimated else "सामान्य (Normal)")
    hist_items = [(D(month_label(ym, "mr")), D(u), u) for ym, u in history]
    reading_note = (f"मीटर रिडिंग उपलब्ध नसल्याने हे देयक मागील ३ महिन्यांच्या सरासरी वापरावर ({D(units)} युनिट) "
                    "आधारित आहे. पुढील प्रत्यक्ष रिडिंगनंतर समायोजन केले जाईल." if estimated else None)
    ctx = dict(
        html_lang="mr", accent="#1565c0", accent_light="#e3eefb", accent_dark="#0d3f7a", bar_color="#1e6fe0",
        org_line1="महाराष्ट्र राज्य विद्युत वितरण कंपनी मर्यादित",
        org_line2="Maharashtra State Electricity Distribution Co. Ltd. (MSEDCL)",
        title="वीज पुरवठा देयक", title2=f"BILL OF SUPPLY FOR THE MONTH OF - {bm_label}",
        band=[f"बिलींग युनिट : {D(bu)}", f"देयक दिनांक : {D(dmy(bill_date))}", f"देय दिनांक : {D(dmy(due))}"],
        grid_cols="1.4fr 1fr",
        info_cols=[
            [("ग्राहक क्रमांक", D(consumer)), ("ग्राहकाचे नाव", name), ("पत्ता", address),
             ("दर संकेत", D("90/LT I Res 1-Phase")), ("मिटर क्रमांक", D(meter_no))],
            [("मंजुर भार", f"{n(load)} KW"), ("पुरवठा दिनांक", D("14-06-2004")),
             ("चालु रिडिंग दिनांक", D(dmy(end))), ("मागील रिडिंग दिनांक", D(dmy(start))),
             ("देयक कालावधी (दिवस)", D(days)), ("मीटर स्थिती", status)],
        ],
        reading_title="वीज वापर तपशील",
        reading_head=["चालु रिडिंग", "मागील रिडिंग", "गुणक अवयव", "युनिट", "समा. युनिट", "एकुण वापर"],
        reading_rows=[[curr_display if isinstance(curr_display, str) else D(curr_display), D(prev), D("1.00"),
                       D(units), D(0), D(units)]],
        reading_note=reading_note,
        charges_title="देयकाचा तपशील",
        charges=[("स्थिर आकार", n(c["fixed"])), ("वीज आकार", n(c["energy"])),
                 (f"वहन आकार @ {n(1.60)} रु/यु", n(c["wheel"])), ("इंधन समायोजन आकार", n(c["fac"])),
                 (f"वीज शुल्क {n(16, 2)}%", n(c["duty"])), ("इतर आकार", n(0)),
                 ("चालू वीज देयक (रु.)", n(c["total"])), ("निव्वळ थकबाकी/जमा", n(0)),
                 ("देयकाची निव्वळ रक्कम", n(c["total"])), ("पूर्णांक देयक (रु.)", n(c["rounded"]))],
        pay_label="देयक रक्कम रु.",
        pay_value=n(c["rounded"]),
        pay_rows=[("देय दिनांक", D(dmy(due))), ("या तारखे नंतर भरल्यास", n(c["rounded"] + 20))],
        history_title="वीज वापर इतिहास (Billing History) — युनिट",
        history_style="hbars",
        history_bars=bars(hist_items),
        history_rows=hist_items,
        footer_title="सूचना व अटी :",
        footer=["ऑनलाइन पेमेंट सुविधेचा वापर करा आणि ०.२५% (जास्तीत जास्त रु. ५००) सवलत मिळवा.",
                "महानगरपालिका क्षेत्रातील ग्राहकांना रु. १० प्रती महिना अतिरिक्त स्थिर आकार लागू.",
                "हे केवळ चाचणीसाठी तयार केलेले नमुना (SAMPLE) देयक आहे."],
        stub=[f"स्थळप्रत — ग्राहक क्रमांक : {D(consumer)}", f"अंतिम तारीख : {D(dmy(due))}",
              f"रु. {n(c['rounded'])}"],
    )
    flds = fields(
        discom="Maharashtra State Electricity Distribution Co. Ltd. (MSEDCL)", state="Maharashtra",
        consumer_number=consumer, consumer_name=[name, name_latin] if name_latin else name,
        tariff_category="90/LT I Res 1-Phase", is_residential=True,
        sanctioned_load_kw=load, connection_phase="single", billing_period_start=start, billing_period_end=end,
        billing_days=days, billing_cycle="monthly", units_billed_kwh=units, bill_amount_rs=c["rounded"],
        consumption_history=history, has_solar_net_meter=False, export_units_kwh=None,
        meter_reading_type="estimated" if estimated else "actual", pincode=pincode,
    )
    return dict(id=bill_id, template="standard.html.j2", ctx=ctx, languages=["mr", "en"], fields=flds, notes=notes)


@register
def msedcl_dev():
    return msedcl_bill(
        bill_id="msedcl-marathi-devanagari-01", consumer="170019284563", name="सुरेश बाळकृष्ण जाधव", name_latin="Suresh Balkrishna Jadhav",
        address="फ्लॅट १२, साई कृपा अपार्टमेंट, कर्वे नगर, पुणे ४११०५२", pincode="411052", load=2.5,
        start=date(2026, 8, 1), end=date(2026, 8, 31), prev=45213, curr_display=45500, units=287,
        bill_date=date(2026, 9, 4), due=date(2026, 9, 25), meter_no="05912877", bu="4637",
        history=[("2026-08", 262), ("2026-07", 248), ("2026-06", 301), ("2026-05", 356), ("2026-04", 334),
                 ("2026-03", 279), ("2026-02", 221), ("2026-01", 205), ("2025-12", 214), ("2025-11", 230),
                 ("2025-10", 266), ("2025-09", 251)],
        devanagari=True, estimated=False,
        notes="Tests: Marathi labels with every number printed in Devanagari digits (०-९), including dates, "
              "units and the 12-month bar-chart history. Amount = rounded payable (पूर्णांक देयक); the unrounded "
              "net is within 1%. History months are the bill months printed on the chart. Consumer name is printed "
              "in Devanagari; both the printed form and the Latin transliteration are accepted.",
    )


@register
def msedcl_est():
    return msedcl_bill(
        bill_id="msedcl-marathi-estimated-01", consumer="049012345671", name="ANJALI PRAKASH DESHMUKH",
        address="PLOT 7, GANGAPUR ROAD, NASHIK 422013", pincode="422013", load=1.2,
        start=date(2026, 8, 3), end=date(2026, 9, 2), prev=12890, curr_display="RNA", units=176,
        bill_date=date(2026, 9, 6), due=date(2026, 9, 27), meter_no="07720431", bu="4815",
        history=[("2026-08", 168), ("2026-07", 181), ("2026-06", 179), ("2026-05", 232), ("2026-04", 214),
                 ("2026-03", 177), ("2026-02", 150), ("2026-01", 142), ("2025-12", 149), ("2025-11", 158),
                 ("2025-10", 171), ("2025-09", 183)],
        devanagari=False, estimated=True,
        notes="Tests: estimated/average bill — meter status RNA (reading not available), current reading printed "
              "as 'RNA', units (176) are the 3-month average. meter_reading_type must be 'estimated'.",
    )


# ---------------------------------------------------------------- UPPCL (Hindi, large arrears)

@register
def uppcl():
    units, prev, curr = 312, 23456, 23768
    start, end = date(2026, 7, 31), date(2026, 8, 31)
    rows, energy = slab_calc(units, [(150, 5.50), (300, 6.00), (INF, 6.50)])
    fixed = 220.0
    ed = r2((energy + fixed) * 0.05)
    current = r2(energy + fixed + ed)
    arrears = 112486.00
    total = r2(current + arrears)
    I = lambda x: num(x, indian=True)  # noqa: E731
    history = [("2026-07", 356), ("2026-06", 441), ("2026-05", 398), ("2026-04", 287), ("2026-03", 214), ("2026-02", 198)]
    ctx = dict(
        html_lang="hi", serif=True, accent="#4a148c", accent_light="#f1e8fa", accent_dark="#2e0b5a", th_bg="#ece3f5",
        org_line1="मध्यांचल विद्युत वितरण निगम लिमिटेड", org_line2="Madhyanchal Vidyut Vitran Nigam Ltd. (UPPCL)",
        title="विद्युत बिल", title2="Electricity Bill — LMV-1",
        band=["वितरण खण्ड : अलीगंज", "बिल माह : अगस्त-2026", f"बिल तिथि : {dmy(date(2026, 9, 3))}"],
        info_cols=[
            [("खाता संख्या (Account No.)", "4829173650"), ("नाम", "राम प्रकाश वर्मा"),
             ("पता", "H.No. 45/2, Sector H, Aliganj, Lucknow - 226024"), ("मोबाइल", "94XXXXXX07")],
            [("श्रेणी", "LMV-1 घरेलू (शहरी)"), ("स्वीकृत भार", "2 kW"), ("कनेक्शन", "एकल फेज"),
             ("मीटर संख्या", "UP4471902"), ("बिल आधार", "वास्तविक रीडिंग (OK)")],
            [("बिल अवधि", f"{dmy(start)} से {dmy(end)}"), ("दिन", str((end - start).days)),
             ("देय तिथि", dmy(date(2026, 9, 17))), ("बिल संख्या", "26092481173")],
        ],
        two_cols="1.2fr 1fr",
        reading_title="मीटर रीडिंग विवरण",
        reading_head=["पिछली रीडिंग तिथि", "पिछली रीडिंग", "वर्तमान रीडिंग तिथि", "वर्तमान रीडिंग", "गुणक", "खपत (यूनिट)"],
        reading_rows=[[dmy(start), prev, dmy(end), curr, 1, units]],
        charges_title="बिल गणना",
        slab_head=["स्लैब", "यूनिट", "दर (₹)", "राशि (₹)"],
        slab_rows=[[slab_text(lo, hi), u, f"{r:.2f}", I(a)] for lo, hi, u, r, a in rows],
        charges=[("स्थायी शुल्क (2 kW × ₹110)", I(fixed)), ("ऊर्जा शुल्क", I(energy)),
                 ("विद्युत शुल्क @ 5%", I(ed)), ("वर्तमान बिल राशि", I(current)),
                 ("पिछला बकाया (Arrears)", I(arrears)), ("बकाया पर विलंब अधिभार", "0.00"),
                 ("कुल देय राशि", I(total))],
        pay_label="कुल देय राशि (₹)", pay_value="₹ " + I(total),
        pay_rows=[("वर्तमान बिल राशि", I(current)), ("पिछला बकाया", I(arrears)),
                  ("देय तिथि", dmy(date(2026, 9, 17)))],
        history_side=True,
        history_title="पिछले 6 माह की खपत",
        history_head=["माह", "यूनिट"],
        history_rows=[[month_label(ym, "hi"), u] for ym, u in history],
        footer_title="महत्वपूर्ण सूचना",
        footer=["बकाया राशि ₹ 1,12,486.00 है। एकमुश्त समाधान योजना (OTS) के लिए अपने खण्ड कार्यालय से संपर्क करें।",
                "बकाया का भुगतान न करने पर विद्युत संयोजन विच्छेदित किया जा सकता है।",
                "यह केवल परीक्षण हेतु बनाया गया नमूना (SAMPLE) बिल है।"],
    )
    flds = fields(
        discom="Madhyanchal Vidyut Vitran Nigam Ltd. (MVVNL), UPPCL", state="Uttar Pradesh",
        consumer_number="4829173650", consumer_name=["राम प्रकाश वर्मा", "Ram Prakash Verma"],
        tariff_category=["LMV-1 घरेलू (शहरी)", "LMV-1 Domestic (Urban)"],
        is_residential=True, sanctioned_load_kw=2.0, connection_phase="single", billing_period_start=start,
        billing_period_end=end, billing_days=(end - start).days, billing_cycle="monthly", units_billed_kwh=units,
        bill_amount_rs=current, consumption_history=history, has_solar_net_meter=False, export_units_kwh=None,
        meter_reading_type="actual", pincode="226024",
    )
    return dict(id="uppcl-hindi-arrears-01", template="standard.html.j2", ctx=ctx, languages=["hi", "en"],
                fields=flds, notes="Tests: large arrears shown separately (₹1,12,486.00) — bill_amount_rs is the current "
                "bill only (₹2,124.15), not the total payable (₹1,14,610.15). Mostly Hindi labels, Indian comma format. Name and tariff are printed in "
                "Devanagari; label lists the printed form and an English form.")


# ---------------------------------------------------------------- TNPDCL (Tamil, bi-monthly)

@register
def tnpdcl():
    units, prev, curr = 486, 31540, 32026
    start, end = date(2026, 7, 10), date(2026, 9, 8)
    rows, energy = slab_calc(units, [(100, 0.00), (200, 2.35), (400, 4.70), (500, 6.30), (600, 8.40), (INF, 9.45)])
    subsidy = rows[1][4] if units <= 500 else 0.0
    net = r2(energy - subsidy)
    payable = float(round(net))
    history = [("2026-07", 512), ("2026-05", 598), ("2026-03", 455), ("2026-01", 402), ("2025-11", 438)]
    periods = [("10-05-2026", "09-07-2026"), ("11-03-2026", "09-05-2026"), ("09-01-2026", "10-03-2026"),
               ("10-11-2025", "08-01-2026"), ("11-09-2025", "09-11-2025")]
    ctx = dict(
        html_lang="ta", serif=True, accent="#00695c", accent_light="#e0f2ef", accent_dark="#004d40", bar_color="#26a69a",
        org_line1="தமிழ்நாடு மின் பகிர்மானக் கழகம்", org_line2="Tamil Nadu Power Distribution Corporation Ltd (TNPDCL)",
        title="மின் கட்டண விவரம்", title2="இருமாத கணக்கீடு",
        band=["பிரிவு : வேளச்சேரி", f"கணக்கீட்டு தேதி : {dmy(date(2026, 9, 9))}", "இணையதளம் வழி செலுத்தலாம்"],
        info_cols=[
            [("மின் இணைப்பு எண்", "06-215-004-1234"), ("பெயர்", "K. SELVAKUMAR"),
             ("முகவரி", "No. 18, 3rd Cross Street, Velachery, Chennai - 600042")],
            [("கட்டண வகை", "LA 1A (வீட்டு உபயோகம்)"), ("அனுமதிக்கப்பட்ட மின்பளு", "3 கி.வா (kW)"),
             ("கட்டம் (Phase)", "ஒரு கட்டம் (1)"), ("மீட்டர் எண்", "TN33150892")],
            [("கணக்கீட்டு காலம்", f"{dmy(start)} முதல் {dmy(end)} வரை"), ("நாட்கள்", str((end - start).days)),
             ("செலுத்த கடைசி தேதி", dmy(date(2026, 9, 28))), ("அளவீட்டு நிலை", "சரியான அளவீடு")],
        ],
        reading_title="மீட்டர் அளவீடு",
        reading_head=["முந்தைய அளவீடு", "தற்போதைய அளவீடு", "பெருக்கி", "பயன்படுத்திய அலகுகள்"],
        reading_rows=[[prev, curr, 1, units]],
        charges_title="கட்டணக் கணக்கீடு (இருமாதம்)",
        slab_head=["அலகு வரம்பு", "அலகுகள்", "விலை (₹)", "தொகை (₹)"],
        slab_rows=[[slab_text(lo, hi), u, f"{r:.2f}", num(a)] for lo, hi, u, r, a in rows],
        charges=[("மின் கட்டணம்", num(energy)), ("நிலைக் கட்டணம்", "0.00"),
                 ("அரசு மானியம் (101-200 அலகுகள்)", "-" + num(subsidy)), ("நிலுவைத் தொகை", "0.00"),
                 ("மொத்தம்", num(net)), ("செலுத்த வேண்டிய தொகை (முழு ரூபாய்)", num(payable, dec=0))],
        pay_label="செலுத்த வேண்டிய தொகை", pay_value=f"₹ {num(payable, dec=0)}",
        pay_rows=[("செலுத்த கடைசி தேதி", dmy(date(2026, 9, 28)))],
        history_title="முந்தைய பயன்பாட்டு விவரம் (இருமாதம்)",
        history_head=["காலம் (முதல்)", "காலம் (வரை)", "அலகுகள்"],
        history_rows=[[a, b, u] for (a, b), (_, u) in zip(periods, history)],
        footer_title="குறிப்பு",
        footer=["முதல் 100 அலகுகள் கட்டணமில்லை.", "இது சோதனைக்காக உருவாக்கப்பட்ட மாதிரி (SAMPLE) ரசீது."],
    )
    flds = fields(
        discom="Tamil Nadu Power Distribution Corporation Ltd (TNPDCL)", state="Tamil Nadu",
        consumer_number="06-215-004-1234", consumer_name="K. SELVAKUMAR", tariff_category=["LA 1A (வீட்டு உபயோகம்)", "LA 1A Domestic"],
        is_residential=True, sanctioned_load_kw=3.0, connection_phase="single", billing_period_start=start,
        billing_period_end=end, billing_days=(end - start).days, billing_cycle="bimonthly", units_billed_kwh=units,
        bill_amount_rs=payable, consumption_history=history, has_solar_net_meter=False, export_units_kwh=None,
        meter_reading_type="actual", pincode="600042",
    )
    return dict(id="tnpdcl-tamil-bimonthly-01", template="standard.html.j2", ctx=ctx, languages=["ta", "en"],
                fields=flds, notes="Tests: Tamil-only labels and bi-monthly billing (60 days, 486 units for two "
                "months). History rows are bi-monthly periods; month = end month of each period. Consumer number "
                "is printed with dashes (06-215-004-1234).")


# ---------------------------------------------------------------- CESC (Bengali)

@register
def cesc():
    units, prev, curr = 274, 55102, 55376
    start, end = date(2026, 8, 4), date(2026, 9, 3)
    rows, energy = slab_calc(units, [(25, 5.37), (60, 5.93), (100, 6.49), (150, 7.32), (200, 7.73), (300, 8.33), (INF, 9.27)])
    fixed, meter_rent = 30.0, 15.0
    gross = r2(energy + fixed + meter_rent)
    rebate = r2(energy * 0.01)
    net = r2(gross - rebate)
    history = [("2026-08", 301), ("2026-07", 318), ("2026-06", 336), ("2026-05", 342), ("2026-04", 288), ("2026-03", 196)]
    items = [(month_label(ym, "bn", short_year=True), str(u), u) for ym, u in reversed(history)]
    ctx = dict(
        html_lang="bn", accent="#ad1457", accent_light="#fce4ef", accent_dark="#78002e", bar_color="#d81b60",
        org_line1="CESC Limited", org_line2="সিইএসসি লিমিটেড — কলকাতা",
        title="বিদ্যুৎ বিল / Electricity Bill", title2="গার্হস্থ্য (Domestic)",
        band=[f"বিলের তারিখ / Bill Date: {dmy(date(2026, 9, 5), '.')}", "Bill Month: SEP-2026",
              f"শেষ তারিখ / Due Date: {dmy(date(2026, 9, 20), '.')}"],
        info_cols=[
            [("কনজিউমার আইডি / Consumer ID", "03117452890"), ("নাম / Name", "SUBRATA CHATTERJEE"),
             ("ঠিকানা / Address", "23/1B, Hazra Road, Kolkata - 700026")],
            [("শ্রেণী / Category", "Domestic Urban (LT)"), ("অনুমোদিত লোড / Sanctioned Load", "3.00 kW"),
             ("ফেজ / Phase", "সিঙ্গল ফেজ / Single")],
            [("মিটার নং / Meter No.", "CE0884512"), ("রিডিং-এর ধরন", "প্রকৃত / Actual"),
             ("বিলের সময়কাল", f"{dmy(start, '.')} - {dmy(end, '.')}"), ("দিন / Days", str((end - start).days))],
        ],
        reading_title="মিটার রিডিং / Meter Reading",
        reading_head=["পূর্ববর্তী রিডিং / Previous", "বর্তমান রিডিং / Present", "MF", "ব্যবহৃত ইউনিট / Units"],
        reading_rows=[[prev, curr, 1, units]],
        charges_title="চার্জের বিবরণ / Charges",
        slab_head=["স্ল্যাব", "ইউনিট", "হার (₹)", "টাকা (₹)"],
        slab_rows=[[slab_text(lo, hi), u, f"{r:.2f}", num(a)] for lo, hi, u, r, a in rows],
        charges=[("এনার্জি চার্জ / Energy Charge", num(energy)), ("স্থায়ী চার্জ / Fixed Charge", num(fixed)),
                 ("মিটার ভাড়া / Meter Rent", num(meter_rent)), ("বিদ্যুৎ শুল্ক / Electricity Duty", "0.00"),
                 ("মোট / Gross Amount", num(gross)), ("রিবেট (সময়মতো প্রদানে) / Rebate 1%", "-" + num(rebate)),
                 ("প্রদেয় অর্থ / Net Payable", num(net))],
        pay_label="প্রদেয় অর্থ / Amount Payable", pay_value=f"₹ {num(net)}",
        pay_rows=[("শেষ তারিখ / Due Date", dmy(date(2026, 9, 20), ".")), ("পরে / After due date", num(gross))],
        history_title="বিগত মাসগুলির ব্যবহার (ইউনিট) / Consumption History",
        history_style="vbars", history_bars=bars(items, 85), history_rows=items,
        footer_title="জরুরি তথ্য",
        footer=["সময়মতো বিল জমা দিলে ১% রিবেট পাওয়া যাবে।", "এটি কেবল পরীক্ষার জন্য তৈরি একটি নমুনা (SAMPLE) বিল।"],
    )
    flds = fields(
        discom="CESC Limited", state="West Bengal", consumer_number="03117452890", consumer_name="SUBRATA CHATTERJEE",
        tariff_category="Domestic Urban (LT)", is_residential=True, sanctioned_load_kw=3.0, connection_phase="single",
        billing_period_start=start, billing_period_end=end, billing_days=(end - start).days, billing_cycle="monthly",
        units_billed_kwh=units, bill_amount_rs=net, consumption_history=history, has_solar_net_meter=False,
        export_units_kwh=None, meter_reading_type="actual", pincode="700026",
    )
    return dict(id="cesc-bengali-01", template="standard.html.j2", ctx=ctx, languages=["bn", "en"], fields=flds,
                notes="Tests: Bengali+English labels, dotted dates (DD.MM.YYYY), history as a vertical bar chart "
                "with Bengali month names and 2-digit years (oldest left). Amount = net payable with 1% rebate.")


# ---------------------------------------------------------------- UGVCL (Gujarati, bi-monthly)

@register
def ugvcl():
    units, prev, curr = 634, 40211, 40845
    start, end = date(2026, 7, 5), date(2026, 9, 4)
    rows, energy = slab_calc(units, [(100, 3.05), (200, 3.50), (500, 4.15), (INF, 5.20)])
    fixed = 50.0
    fppa = r2(units * 2.85)
    duty = r2((energy + fixed + fppa) * 0.15)
    total = r2(energy + fixed + fppa + duty)
    payable = float(round(total))
    history = [("2026-07", 788), ("2026-05", 702), ("2026-03", 455), ("2026-01", 398), ("2025-11", 512)]
    ctx = dict(
        html_lang="gu", accent="#2e7d32", accent_light="#e8f5e9", accent_dark="#1b5e20",
        org_line1="ઉત્તર ગુજરાત વીજ કંપની લિમિટેડ", org_line2="Uttar Gujarat Vij Company Ltd. (UGVCL)",
        title="વીજ બિલ", title2="દ્વિમાસિક બિલ (2 મહિના)",
        band=["પેટા વિભાગ : ગાંધીનગર-2", f"બિલ તારીખ : {dmy(date(2026, 9, 6), '/')}",
              f"ભરવાની છેલ્લી તારીખ : {dmy(date(2026, 9, 21), '/')}"],
        info_cols=[
            [("ગ્રાહક નંબર", "29104512678"), ("નામ", "PATEL HITESHBHAI RAMESHBHAI"),
             ("સરનામું", "Plot 512/2, Sector 21, Gandhinagar - 382021")],
            [("ટેરીફ", "RGP (રહેણાંક)"), ("મંજૂર ભાર", "3.00 કિ.વો."), ("ફેઝ", "સિંગલ ફેઝ"),
             ("મીટર નંબર", "GJ60221874")],
            [("બિલ સમયગાળો", f"{dmy(start, '/')} થી {dmy(end, '/')}"), ("દિવસ", str((end - start).days)),
             ("રીડિંગ પ્રકાર", "સામાન્ય (Normal)")],
        ],
        reading_title="મીટર રીડિંગ",
        reading_head=["અગાઉનું રીડિંગ", "હાલનું રીડિંગ", "ગુણક", "વપરાશ (યુનિટ)"],
        reading_rows=[[prev, curr, 1, units]],
        charges_title="બિલની વિગત",
        slab_head=["યુનિટ સ્લેબ", "યુનિટ", "દર (₹)", "રકમ (₹)"],
        slab_rows=[[slab_text(lo, hi), u, f"{r:.2f}", num(a)] for lo, hi, u, r, a in rows],
        charges=[("સ્થિર આકાર", num(fixed)), ("ઊર્જા આકાર", num(energy)),
                 ("FPPPA @ ₹2.85/યુનિટ", num(fppa)), ("વીજ શુલ્ક @ 15%", num(duty)),
                 ("કુલ રકમ", num(total)), ("ભરવાપાત્ર રકમ (રાઉન્ડ)", num(payable))],
        pay_label="ભરવાપાત્ર રકમ", pay_value=f"₹ {num(payable)}",
        pay_rows=[("છેલ્લી તારીખ", dmy(date(2026, 9, 21), "/"))],
        history_side=True,
        history_title="અગાઉનો વપરાશ (દ્વિમાસિક)",
        history_head=["બિલ સમયગાળો (સુધી)", "યુનિટ"],
        history_rows=[[month_label(ym, "gu"), u] for ym, u in history],
        footer_title="સૂચના",
        footer=["બિલ સમયસર ભરો અને વિલંબ ચાર્જથી બચો.", "આ ફક્ત પરીક્ષણ માટેનું નમૂના (SAMPLE) બિલ છે."],
    )
    flds = fields(
        discom="Uttar Gujarat Vij Company Ltd. (UGVCL)", state="Gujarat", consumer_number="29104512678",
        consumer_name="PATEL HITESHBHAI RAMESHBHAI", tariff_category=["RGP (રહેણાંક)", "RGP (Residential)"], is_residential=True,
        sanctioned_load_kw=3.0, connection_phase="single", billing_period_start=start, billing_period_end=end,
        billing_days=(end - start).days, billing_cycle="bimonthly", units_billed_kwh=units, bill_amount_rs=payable,
        consumption_history=history, has_solar_net_meter=False, export_units_kwh=None,
        meter_reading_type="actual", pincode="382021",
    )
    return dict(id="ugvcl-gujarati-bimonthly-01", template="standard.html.j2", ctx=ctx, languages=["gu", "en"],
                fields=flds, notes="Tests: Gujarati labels, bi-monthly billing (61 days), DD/MM/YYYY dates, kW "
                "printed as 'કિ.વો.'. History lists bi-monthly periods by the end month (Gujarati month names).")


# ---------------------------------------------------------------- TGSPDCL (Telugu, commercial)

@register
def tgspdcl():
    units, prev, curr = 642, 70412, 71054
    start, end = date(2026, 8, 10), date(2026, 9, 9)
    rows, energy = slab_calc(units, [(50, 7.00), (100, 8.50), (300, 9.90), (500, 10.40), (INF, 11.00)])
    fixed, cust = 240.0, 65.0
    ed = r2(units * 0.06)
    total = r2(energy + fixed + cust + ed)
    history = [("2026-08", 610), ("2026-07", 588), ("2026-06", 702), ("2026-05", 745), ("2026-04", 690), ("2026-03", 612)]
    items = [(month_label(ym, "te"), str(u), u) for ym, u in history]
    ctx = dict(
        html_lang="te", accent="#bf360c", accent_light="#fbe9e7", accent_dark="#7f2207", bar_color="#e64a19",
        org_line1="తెలంగాణ దక్షిణ ప్రాంత విద్యుత్ పంపిణీ సంస్థ", org_line2="Telangana Southern Power Distribution Company Ltd. (TGSPDCL)",
        title="విద్యుత్ బిల్లు / Electricity Bill", title2="LT-II(A) వాణిజ్య (Non-Domestic)",
        band=["ERO : Kukatpally", f"బిల్లు తేదీ : {dmy(date(2026, 9, 10))}", f"చివరి తేదీ : {dmy(date(2026, 9, 24))}"],
        info_cols=[
            [("యూనిక్ సర్వీస్ నంబర్ (USC No.)", "104582731"), ("సర్వీస్ నంబర్", "B2-114-0451"),
             ("పేరు", "SRI VENKATESWARA TIFFIN CENTRE"), ("చిరునామా", "Shop No 4, Main Road, Kukatpally, Hyderabad - 500072")],
            [("కేటగిరి", "LT-II(A) Non-Domestic/Commercial"), ("కాంట్రాక్ట్ లోడ్", "4 KW"), ("ఫేజ్", "సింగిల్ ఫేజ్ (1Ph)")],
            [("బిల్లు కాలం", f"{dmy(start)} - {dmy(end)}"), ("రోజులు", str((end - start).days)),
             ("మీటర్ నంబర్", "TS9031552"), ("మీటర్ స్థితి", "సాధారణ (01)")],
        ],
        reading_title="మీటర్ రీడింగ్ వివరాలు",
        reading_head=["మునుపటి రీడింగ్", "ప్రస్తుత రీడింగ్", "MF", "వినియోగించిన యూనిట్లు"],
        reading_rows=[[prev, curr, 1, units]],
        charges_title="ఛార్జీల వివరాలు",
        slab_head=["స్లాబ్", "యూనిట్లు", "రేటు (₹)", "మొత్తం (₹)"],
        slab_rows=[[slab_text(lo, hi), u, f"{r:.2f}", num(a)] for lo, hi, u, r, a in rows],
        charges=[("ఎనర్జీ ఛార్జీలు", num(energy)), ("స్థిర ఛార్జీలు (4 KW × ₹60)", num(fixed)),
                 ("కస్టమర్ ఛార్జీలు", num(cust)), ("విద్యుత్ సుంకం", num(ed)), ("బకాయిలు", "0.00"),
                 ("చెల్లించవలసిన మొత్తం", num(total))],
        pay_label="చెల్లించవలసిన మొత్తం", pay_value=f"₹ {num(total)}",
        pay_rows=[("చివరి తేదీ", dmy(date(2026, 9, 24)))],
        history_title="గత నెలల వినియోగం (యూనిట్లు)", history_style="hbars", history_bars=bars(items), history_rows=items,
        footer_title="సూచనలు",
        footer=["బిల్లును ఆన్‌లైన్‌లో చెల్లించండి.", "ఇది పరీక్ష కోసం తయారు చేసిన నమూనా (SAMPLE) బిల్లు."],
    )
    flds = fields(
        discom="Telangana Southern Power Distribution Company Ltd. (TGSPDCL)", state="Telangana",
        consumer_number="104582731", consumer_name="SRI VENKATESWARA TIFFIN CENTRE",
        tariff_category="LT-II(A) Non-Domestic/Commercial", is_residential=False, sanctioned_load_kw=4.0,
        connection_phase="single", billing_period_start=start, billing_period_end=end,
        billing_days=(end - start).days, billing_cycle="monthly", units_billed_kwh=units, bill_amount_rs=total,
        consumption_history=history, has_solar_net_meter=False, export_units_kwh=None,
        meter_reading_type="actual", pincode="500072",
    )
    return dict(id="tgspdcl-telugu-commercial-01", template="standard.html.j2", ctx=ctx, languages=["te", "en"],
                fields=flds, notes="Tests: commercial (non-residential) LT-II(A) category, is_residential=false. Telugu "
                "labels. Two IDs printed: USC No. 104582731 (labelled as consumer_number) and Service No. B2-114-0451.")


# ---------------------------------------------------------------- BESCOM (Kannada thermal slip)

@register
def bescom():
    units, prev, curr, gj = 236, 8812, 9048, 148
    start, end = date(2026, 8, 1), date(2026, 9, 1)
    energy = r2(units * 5.80)
    fixed = 290.0
    tax = r2(energy * 0.09)
    gross = r2(energy + fixed + tax)
    gj_sub = r2(gj * 5.80 + fixed * gj / units + gj * 5.80 * 0.09)
    net = r2(gross - gj_sub)
    history = [("2026-08", 221), ("2026-07", 209), ("2026-06", 248)]
    ctx = dict(
        html_lang="kn",
        head=["ಬೆಂಗಳೂರು ವಿದ್ಯುತ್ ಸರಬರಾಜು ಕಂಪನಿ ನಿಯಮಿತ", "BESCOM — Bangalore Electricity Supply Co. Ltd.",
              "ಉಪವಿಭಾಗ: ವಿಜಯನಗರ (W-4)", "ವಿದ್ಯುತ್ ಬಿಲ್ / SPOT BILL"],
        sections=[
            dict(rows=[("ಬಿಲ್ ದಿನಾಂಕ", dmy(date(2026, 9, 2), "/")), ("ಬಿಲ್ ಸಂಖ್ಯೆ", "W4-0926-118734"),
                       ("ಖಾತೆ ಸಂಖ್ಯೆ (Account ID)", "7854123690"), ("ಆರ್.ಆರ್. ಸಂಖ್ಯೆ", "S7EH-28461"),
                       ("ಹೆಸರು", "LAKSHMI NARAYANA H")]),
            dict(rows=[("ವಿಳಾಸ", ""), ("No 42, 5th Main,", ""), ("Vijayanagar, Bengaluru 560040", "")]),
            dict(rows=[("ಜಕಾತಿ", "LT2A(i) ಗೃಹ"), ("ಮಂಜೂರಾದ ಲೋಡ್", "2.00 KW"), ("ಫೇಸ್", "1"),
                       ("ಮೀಟರ್ ಸಂಖ್ಯೆ", "KA0447812")]),
            dict(title="ರೀಡಿಂಗ್ ವಿವರ", rows=[("ಹಿಂದಿನ ರೀಡಿಂಗ್ ದಿನಾಂಕ", dmy(start, "/")), ("ಪ್ರಸ್ತುತ ರೀಡಿಂಗ್ ದಿನಾಂಕ", dmy(end, "/")),
                                            ("ದಿನಗಳು", str((end - start).days)), ("ಹಿಂದಿನ ರೀಡಿಂಗ್", str(prev)),
                                            ("ಪ್ರಸ್ತುತ ರೀಡಿಂಗ್", str(curr)), ("ಗುಣಕ (MF)", "1"),
                                            ("ಬಳಕೆ (ಯೂನಿಟ್)", str(units)), ("ಮೀಟರ್ ಸ್ಥಿತಿ", "ಸಾಮಾನ್ಯ")]),
            dict(title="ಶುಲ್ಕಗಳು", rows=[("ನಿಗದಿತ ಶುಲ್ಕ 2KW×145", num(fixed)), (f"ವಿದ್ಯುತ್ ಶುಲ್ಕ {units}×5.80", num(energy)),
                                       ("ತೆರಿಗೆ @9%", num(tax)), ("ಒಟ್ಟು", num(gross)),
                                       (f"ಗೃಹಜ್ಯೋತಿ ಅರ್ಹ ಯೂನಿಟ್", str(gj)), ("ಗೃಹಜ್ಯೋತಿ ಸಹಾಯಧನ", "-" + num(gj_sub)),
                                       ("ಬಾಕಿ", "0.00")]),
            dict(title="ಹಿಂದಿನ ತಿಂಗಳುಗಳ ಬಳಕೆ", rows=[(month_label(ym, "kn"), f"{u} ಯೂ") for ym, u in history]),
        ],
        pay_label="ಪಾವತಿಸಬೇಕಾದ ಮೊತ್ತ", pay_value=f"Rs. {num(net)}",
        pay_rows=[("ಕೊನೆಯ ದಿನಾಂಕ", dmy(date(2026, 9, 16), "/"))],
        tail=["ಗೃಹಜ್ಯೋತಿ: ಹಿಂದಿನ ವರ್ಷದ ಸರಾಸರಿ + 10% ವರೆಗೆ ಉಚಿತ", "ನಮೂನೆ (SAMPLE) ಬಿಲ್ — ಪರೀಕ್ಷೆಗೆ ಮಾತ್ರ"],
    )
    flds = fields(
        discom="Bangalore Electricity Supply Company Ltd. (BESCOM)", state="Karnataka", consumer_number="7854123690",
        consumer_name="LAKSHMI NARAYANA H", tariff_category=["LT2A(i) ಗೃಹ", "LT2A(i) Domestic"], is_residential=True,
        sanctioned_load_kw=2.0, connection_phase="single", billing_period_start=start, billing_period_end=end,
        billing_days=(end - start).days, billing_cycle="monthly", units_billed_kwh=units, bill_amount_rs=net,
        consumption_history=history, has_solar_net_meter=False, export_units_kwh=None,
        meter_reading_type="actual", pincode="560040",
    )
    return dict(id="bescom-kannada-01", template="thermal.html.j2", ctx=ctx, languages=["kn", "en"], fields=flds,
                notes="Tests: narrow thermal-printer spot bill with Kannada labels and Gruha Jyothi free-units "
                "subsidy (148 eligible units). Amount = net after subsidy. Two IDs printed: Account ID 7854123690 "
                "(labelled consumer_number) and RR No. S7EH-28461. Only 3 months of history.")


# ---------------------------------------------------------------- KSEB (Malayalam thermal slip, bi-monthly)

@register
def kseb():
    units, prev, curr = 398, 27740, 28138
    start, end = date(2026, 7, 14), date(2026, 9, 12)
    rows, energy = slab_calc(units, [(100, 3.35), (200, 4.25), (300, 5.35), (400, 7.20), (500, 8.50)])
    fixed, meter_rent = 200.0, 12.0
    duty = r2(energy * 0.10)
    fuel = r2(units * 0.10)
    total = r2(energy + fixed + meter_rent + duty + fuel)
    payable = float(round(total))
    history = [("2026-07", 412), ("2026-05", 466), ("2026-03", 371)]
    ctx = dict(
        html_lang="ml",
        head=["കേരള സംസ്ഥാന വൈദ്യുതി ബോർഡ് ലിമിറ്റഡ്", "KSEB Ltd. — Kerala State Electricity Board",
              "സെക്ഷൻ: വഴുതക്കാട്", "ബിൽ / DEMAND CUM DISCONNECTION NOTICE"],
        sections=[
            dict(rows=[("ബിൽ തീയതി", dmy(date(2026, 9, 12))), ("ബിൽ നമ്പർ", "5524-260912-0381"),
                       ("കൺസ്യൂമർ നമ്പർ", "1145678012345"), ("പേര്", "ANNIE GEORGE"),
                       ("വിലാസം", "TC 24/1187,"), ("", "Vazhuthacaud,"), ("", "Thiruvananthapuram 695014")]),
            dict(rows=[("താരിഫ്", "LT-1A"), ("കണക്റ്റഡ് ലോഡ്", "3245 W"), ("ഫേസ്", "1"),
                       ("മീറ്റർ നമ്പർ", "KL8812094"), ("ബിൽ കാലയളവ്", "2 മാസം")]),
            dict(title="റീഡിംഗ്", rows=[("മുൻ റീഡിംഗ് തീയതി", dmy(start)), ("നിലവിലെ റീഡിംഗ് തീയതി", dmy(end)),
                                       ("ദിവസം", str((end - start).days)), ("മുൻ റീഡിംഗ്", str(prev)),
                                       ("നിലവിലെ റീഡിംഗ്", str(curr)), ("ഉപഭോഗം (യൂണിറ്റ്)", str(units)),
                                       ("മീറ്റർ നില", "സാധാരണ")]),
            dict(title="ചാർജുകൾ", rows=[("ഫിക്സഡ് ചാർജ്", num(fixed)), ("എനർജി ചാർജ്", num(energy)),
                                        ("വൈദ്യുതി തീരുവ", num(duty)), ("ഇന്ധന സർചാർജ്", num(fuel)),
                                        ("മീറ്റർ വാടക", num(meter_rent)), ("ആകെ", num(total))]),
            dict(title="മുൻ ഉപഭോഗം (2 മാസം)", rows=[(month_label(ym, "ml"), f"{u} U") for ym, u in history]),
        ],
        pay_label="അടയ്ക്കേണ്ട തുക", pay_value=f"Rs. {num(payable)}",
        pay_rows=[("അവസാന തീയതി", dmy(date(2026, 9, 22))), ("വിച്ഛേദന തീയതി", dmy(date(2026, 9, 27)))],
        tail=["ഓൺലൈനായി അടയ്ക്കുക: wss (SAMPLE)", "മാതൃക (SAMPLE) ബിൽ — പരിശോധനയ്ക്ക് മാത്രം"],
    )
    flds = fields(
        discom="Kerala State Electricity Board Ltd. (KSEB)", state="Kerala", consumer_number="1145678012345",
        consumer_name="ANNIE GEORGE", tariff_category="LT-1A Domestic", is_residential=True, sanctioned_load_kw=3.245,
        connection_phase="single", billing_period_start=start, billing_period_end=end,
        billing_days=(end - start).days, billing_cycle="bimonthly", units_billed_kwh=units, bill_amount_rs=payable,
        consumption_history=history, has_solar_net_meter=False, export_units_kwh=None,
        meter_reading_type="actual", pincode="695014",
    )
    return dict(id="kseb-malayalam-bimonthly-01", template="thermal.html.j2", ctx=ctx, languages=["ml", "en"],
                fields=flds, notes="Tests: Malayalam thermal spot bill, bi-monthly (60 days). Load is printed as "
                "connected load in watts (3245 W -> 3.245 kW). History lists bi-monthly bills by bill month.")


# ---------------------------------------------------------------- Mumbai private DISCOMs (English)

def mumbai_charges(units, bands, fixed, wheel_rate):
    rows, energy = slab_calc(units, bands)
    wheel = r2(units * wheel_rate)
    ed = r2((fixed + energy + wheel) * 0.16)
    tose = r2(units * 0.2604)
    total = r2(fixed + energy + wheel + ed + tose)
    return rows, energy, wheel, ed, tose, total, float(round(total))


@register
def adani_solar():
    imp, exp = 512, 238
    units = imp - exp
    start, end = date(2026, 8, 1), date(2026, 8, 31)
    rows, energy, wheel, ed, tose, total, rounded = mumbai_charges(
        units, [(100, 4.60), (300, 7.60), (500, 10.30), (INF, 11.80)], 105.0, 2.40)
    hist = [("2026-07", 468, 251), ("2026-06", 455, 197), ("2026-05", 622, 284), ("2026-04", 590, 301),
            ("2026-03", 486, 288), ("2026-02", 402, 247)]
    history = [(ym, i - e) for ym, i, e in hist]
    C = lambda x: num(x, western_commas=True)  # noqa: E731
    ctx = dict(
        accent="#5e35b1", accent_light="#efe9fb",
        org_line1="Adani Electricity Mumbai Limited", org_line2="Distribution licensee, Mumbai suburban (AEML)",
        title="Electricity Bill — September 2026",
        doc_lines=["Bill No. 2609-100387462", f"Bill Date: {end.replace(day=1).replace(month=9, day=4).strftime('%d %b %Y')}"],
        summary=[("Account No.", "100387462"), ("Billing Period", f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"),
                 ("Due Date", "18 Sep 2026"), ("Amount Payable", f"₹ {C(rounded)}")],
        left_kv=[
            ("Consumer Details", [("Name", "MEERA KRISHNAN IYER"), ("Address", "Flat 803, Lakeview Towers, Powai, Mumbai 400076"),
                                  ("Tariff", "LT-I(B) Residential — Net Metering"), ("Sanctioned Load", "5.00 kW"),
                                  ("Supply", "Single Phase"), ("Rooftop Solar", "3.00 kWp (Net meter installed 12 Mar 2025)")]),
            ("Billing Details", [("Billing Days", str((end - start).days)), ("Reading Type", "Actual (AMR)"),
                                 ("Meter No.", "AE5521984 (bi-directional)")]),
        ],
        reading_title="Net Meter Readings",
        reading_head=["Register", "Previous (01 Aug)", "Current (31 Aug)", "Units"],
        reading_rows=[["Import (kWh)", "33,120", "33,632", imp], ["Export (kWh)", "9,841", "10,079", exp],
                      ["Net Billed Units (Import − Export)", "", "", units]],
        charges_title="Charges for Net Billed Units",
        charges=[("Fixed Charges", C(105.0)),
                 *[(f"Energy Charge {slab_text(lo, hi)} units ({u} × {r:.2f})", C(a)) for lo, hi, u, r, a in rows],
                 ("Wheeling Charge (274 × 2.40)", C(wheel)), ("Electricity Duty @ 16%", C(ed)),
                 ("Tax on Sale of Electricity (₹0.2604/unit)", C(tose)), ("Current Bill", C(total)),
                 ("Total Amount Payable (Rounded)", C(rounded))],
        history_title="Consumption History (kWh)",
        history_bars=bars([(month_label(ym, "en"), str(n), n) for ym, n in reversed(history)], 85),
        history_head=["Month", "Import", "Export", "Net Billed"],
        history_rows=[[month_label(ym, "en", short_year=True), i, e, i - e] for ym, i, e in hist],
        messages=["Solar export units are adjusted against import units every month; surplus at year end is settled "
                  "as per MERC net metering rules.",
                  "Pay by the due date to get a prompt payment discount.",
                  "This is a SAMPLE bill for testing only. Not a real account."],
    )
    flds = fields(
        discom="Adani Electricity Mumbai Ltd. (AEML)", state="Maharashtra", consumer_number="100387462",
        consumer_name="MEERA KRISHNAN IYER", tariff_category="LT-I(B) Residential — Net Metering", is_residential=True,
        sanctioned_load_kw=5.0, connection_phase="single", billing_period_start=start, billing_period_end=end,
        billing_days=(end - start).days, billing_cycle="monthly", units_billed_kwh=units, bill_amount_rs=rounded,
        consumption_history=history, has_solar_net_meter=True, export_units_kwh=exp,
        meter_reading_type="actual", pincode="400076",
    )
    return dict(id="adani-mumbai-solar-english-01", template="corporate.html.j2", ctx=ctx, languages=["en"],
                fields=flds, notes="Tests: home that already has rooftop solar with a net meter (import 512, export "
                "238, net billed 274). units_billed_kwh = net billed units; history = net billed units per month "
                "(the table also prints import and export columns, which should not be used as history).")


@register
def tata_mumbai():
    units, prev, curr = 218, 61204, 61422
    start, end = date(2026, 8, 8), date(2026, 9, 7)
    rows, energy, wheel, ed, tose, total, rounded = mumbai_charges(
        units, [(100, 4.50), (300, 7.25), (500, 9.80), (INF, 11.20)], 90.0, 1.90)
    C = lambda x: num(x, western_commas=True)  # noqa: E731
    ctx = dict(
        accent="#00508f", accent_light="#e4eef7",
        org_line1="The Tata Power Company Limited", org_line2="Mumbai Distribution — Residential",
        title="Bill of Supply", doc_lines=["Bill No. TPM/2609/558120", "Bill Date: 09 Sep 2026"],
        summary=[("CA Number", "900012345678"), ("Bill Period", f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"),
                 ("Pay By", "23 Sep 2026"), ("Amount Due", f"₹ {C(rounded)}")],
        left_kv=[
            ("Customer", [("Name", "ARJUN MEHTA"), ("Address", "B-1204, Sunshine Heights, Chembur, Mumbai 400071"),
                          ("Tariff Category", "LT-I Residential"), ("Sanctioned Load", "3.00 kW"), ("Phase", "1-Phase")]),
            ("Meter", [("Meter No.", "TPM7740125"), ("Reading Status", "Normal (Actual)"),
                       ("No. of Days", str((end - start).days))]),
        ],
        reading_title="Meter Reading",
        reading_head=["Register", "Previous", "Present", "Units"],
        reading_rows=[["kWh", C(prev), C(curr), units]],
        charges_title="Charges",
        charges=[("Fixed Charge", C(90.0)),
                 *[(f"Energy Charge {slab_text(lo, hi)} ({u} × {r:.2f})", C(a)) for lo, hi, u, r, a in rows],
                 ("Wheeling Charge (218 × 1.90)", C(wheel)), ("Electricity Duty @ 16%", C(ed)),
                 ("Tax on Sale (₹0.2604/unit)", C(tose)), ("Current Month Charges", C(total)),
                 ("Amount Due (Rounded)", C(rounded))],
        history_rows=None,
        messages=["Register for e-bill and save paper.", "This is a SAMPLE bill for testing only. Not a real account."],
    )
    flds = fields(
        discom="The Tata Power Company Ltd. (Mumbai Distribution)", state="Maharashtra", consumer_number="900012345678",
        consumer_name="ARJUN MEHTA", tariff_category="LT-I Residential", is_residential=True, sanctioned_load_kw=3.0,
        connection_phase="single", billing_period_start=start, billing_period_end=end,
        billing_days=(end - start).days, billing_cycle="monthly", units_billed_kwh=units, bill_amount_rs=rounded,
        consumption_history=None, has_solar_net_meter=False, export_units_kwh=None,
        meter_reading_type="actual", pincode="400071",
    )
    return dict(id="tatapower-mumbai-nohistory-01", template="corporate.html.j2", ctx=ctx, languages=["en"],
                fields=flds, notes="Tests: English-only bill with just the current month and no consumption "
                "history; consumption_history must be null (a model should not invent past months).")


# ---------------------------------------------------------------- Non-bill: municipal water bill

@register
def water():
    history = [("Aug-26", "18.4"), ("Jul-26", "17.9"), ("Jun-26", "21.2"), ("May-26", "24.6"), ("Apr-26", "22.0"), ("Mar-26", "19.3")]
    items = [(m, kl, float(kl)) for m, kl in history]
    ctx = dict(
        html_lang="mr", accent="#0277bd", accent_light="#e1f2fb", accent_dark="#01579b",
        org_line1="शिवनगर नगर परिषद — पाणीपुरवठा विभाग", org_line2="Shivnagar Municipal Council — Water Supply Department",
        title="पाणी देयक / Water Bill", title2="Metered domestic water connection",
        band=["Ward: 7 (Ganesh Peth)", "Bill Date: 05-09-2026", "Due Date: 30-09-2026"],
        info_cols=[
            [("Connection No. / जोडणी क्र.", "WS-07-004512"), ("Name / नाव", "VIJAY SHANKAR KULKARNI"),
             ("Address / पत्ता", "House 88, Ganesh Peth, Shivnagar 413512")],
            [("Connection Size", "15 mm (½ inch)"), ("Category", "Domestic / घरगुती"), ("Meter No.", "WM-220917")],
            [("Billing Period", "01-08-2026 to 31-08-2026"), ("Days", "30"), ("Reading Type", "Actual")],
        ],
        reading_title="Water Meter Reading / पाणी मीटर रिडिंग",
        reading_head=["Previous Reading (KL)", "Current Reading (KL)", "Consumption (KL)", "Consumption (Litres)"],
        reading_rows=[["1,204.6", "1,223.0", "18.4", "18,400"]],
        charges_title="Charges / आकार",
        slab_head=["Slab (KL)", "KL", "Rate (₹/KL)", "Amount (₹)"],
        slab_rows=[["0-10", "10.0", "8.00", "80.00"], ["10-20", "8.4", "12.00", "100.80"]],
        charges=[("Water Charges", "180.80"), ("Sewerage Benefit Tax (30%)", "54.24"), ("Meter Rent", "15.00"),
                 ("Service Charge", "25.00"), ("Arrears", "0.00"), ("Total Payable", "275.04")],
        pay_label="Total Payable / एकूण देय", pay_value="₹ 275.04",
        pay_rows=[("Due Date", "30-09-2026"), ("After due date", "290.04")],
        history_title="Water Consumption History (KL) / पाणी वापर", history_style="hbars",
        history_bars=bars(items), history_rows=items,
        footer_title="Notes",
        footer=["Save water. Report leaks to the ward office.", "This is a SAMPLE bill for testing only."],
    )
    keys = dict(is_electricity_bill=False)
    flds = fields(**keys)
    return dict(id="nonbill-water-bill-01", template="standard.html.j2", ctx=ctx, languages=["mr", "en"],
                fields=flds, notes="Tests: not an electricity bill — a municipal water bill that looks like a utility "
                "bill (meter readings, consumption history in KL, amount). is_electricity_bill=false and every other "
                "field null.")


# ---------------------------------------------------------------- render

def render_all(only: set[str] | None = None):
    from jinja2 import Environment, FileSystemLoader
    from PIL import Image
    from playwright.sync_api import sync_playwright

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    browser_kind = os.environ.get("BILL_BROWSER", "chrome")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome") if browser_kind == "chrome" else p.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=2)
        for b in BILLS:
            if only and b["id"] not in only:
                continue
            html = env.get_template(b["template"]).render(b=b["ctx"])
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            png = page.locator("body").screenshot(type="png")
            img = Image.open(__import__("io").BytesIO(png))
            out = save_image(img, BILLS_DIR / b["id"])
            write_label(b["id"], "mock", b["languages"], "clean", b["fields"], b["notes"])
            print(f"{b['id']:<36} {out.name} {Image.open(out).size}")
        browser.close()


if __name__ == "__main__":
    render_all(set(sys.argv[1:]) or None)
