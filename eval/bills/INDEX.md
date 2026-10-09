# Eval bills

24 bills: 3 official samples, 15 clean mocks, 6 phone-photo variants. Labels follow `eval/SCHEMA.md`. Mock bills use made-up people, addresses and numbers and carry a SAMPLE mark; DISCOM names appear as plain text only.

Regenerate (from the repo root):

```sh
uv run --with playwright --with jinja2 --with pillow python eval/tools/make_mock_bills.py
uv run --with pillow python -I eval/tools/prepare_official_samples.py   # downloads into a new temp dir
uv run --with opencv-python-headless --with numpy --with pillow python eval/tools/make_photo_variants.py
uv run --with pillow python eval/tools/validate_labels.py
python eval/tools/build_index.py
```

| id | DISCOM | languages | difficulty | source | file | edge case tested |
|---|---|---|---|---|---|---|
| `adani-mumbai-solar-english-01` | AEML | en | clean | mock | bill.png | Rooftop solar net meter (import/export/net) |
| `adani-mumbai-solar-english-01-photo` | AEML | en | phone_photo | mock | bill.jpg | Phone-photo copy of `adani-mumbai-solar-english-01` |
| `bescom-kannada-01` | BESCOM | kn, en | clean | mock | bill.png | Thermal spot bill, Gruha Jyothi free units, two IDs printed |
| `bescom-kannada-01-photo` | BESCOM | kn, en | phone_photo | mock | bill.jpg | Phone-photo copy of `bescom-kannada-01` |
| `cesc-bengali-01` | CESC Limited | bn, en | clean | mock | bill.png | Bengali, dotted dates, vertical bar-chart history |
| `delhi-brpl-hindi-clean-01` | BRPL | hi, en | clean | mock | bill.png | Baseline bilingual Delhi bill, partial subsidy, 6-month history |
| `delhi-brpl-hindi-clean-01-photo` | BRPL | hi, en | phone_photo | mock | bill.jpg | Phone-photo copy of `delhi-brpl-hindi-clean-01` |
| `delhi-bypl-zero-subsidy-01` | BYPL | hi, en | clean | mock | bill.png | Zero bill from the Delhi 200-unit subsidy (amount 0, units still 168) |
| `delhi-tpddl-3phase-7kw-01` | TPDDL | hi, en | clean | mock | bill.png | 3-phase 7 kW, high summer usage, Indian comma amounts, extra KVAH row |
| `kseb-malayalam-bimonthly-01` | KSEB | ml, en | clean | mock | bill.png | Thermal spot bill, bi-monthly, load printed in watts |
| `msedcl-lt-official-01` | MSEDCL | mr, en | clean | official_sample | bill.png | Official format; masked fields, annotations, about 2-month period |
| `msedcl-marathi-devanagari-01` | MSEDCL | mr, en | clean | mock | bill.png | Devanagari digits everywhere, name in Devanagari, 12-month bar chart |
| `msedcl-marathi-devanagari-01-photo` | MSEDCL | mr, en | phone_photo | mock | bill.jpg | Phone-photo copy of `msedcl-marathi-devanagari-01` |
| `msedcl-marathi-estimated-01` | MSEDCL | mr, en | clean | mock | bill.png | Estimated (RNA / average) reading |
| `msedcl-solar-official-01` | MSEDCL | en | clean | official_sample | bill.png | Official solar net-meter format; non-residential, load in HP, arrears |
| `nonbill-water-bill-01` | - | mr, en | clean | mock | bill.png | Not an electricity bill (water bill) |
| `tatapower-mumbai-nohistory-01` | Tata Power (Mumbai) | en | clean | mock | bill.png | Current month only, no history (history must be null) |
| `tgspdcl-telugu-commercial-01` | TGSPDCL | te, en | clean | mock | bill.png | Commercial (non-residential), two IDs printed |
| `tnpdcl-tamil-bimonthly-01` | TNPDCL | ta, en | clean | mock | bill.png | Tamil, bi-monthly cycle, slab subsidy, dashed consumer number |
| `tnpdcl-tamil-bimonthly-01-photo` | TNPDCL | ta, en | phone_photo | mock | bill.jpg | Phone-photo copy of `tnpdcl-tamil-bimonthly-01` |
| `tpddl-handbook-official-01` | TPDDL | hi, en | blurry | official_sample | bill.png | Official handbook sample; low resolution, step stickers, zero bill |
| `ugvcl-gujarati-bimonthly-01` | UGVCL | gu, en | clean | mock | bill.png | Gujarati, bi-monthly cycle, FPPPA charge, rounded total |
| `uppcl-hindi-arrears-01` | MVVNL | hi, en | clean | mock | bill.png | Large arrears (Rs 1,12,486) shown apart from current bill; Hindi name |
| `uppcl-hindi-arrears-01-photo` | MVVNL | hi, en | phone_photo | mock | bill.jpg | Phone-photo copy of `uppcl-hindi-arrears-01` |
