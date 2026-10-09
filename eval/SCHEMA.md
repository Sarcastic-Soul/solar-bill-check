# Bill extraction eval: label schema

Each test bill lives in `eval/bills/<id>/`:

- `bill.png`, `bill.jpg` or `bill.pdf`: the input.
- `label.json`: the ground truth, in the shape below.

```json
{
  "id": "msedcl-marathi-clean-01",
  "source": "mock | official_sample",
  "source_url": "where it came from, if official_sample",
  "languages": ["mr", "en"],
  "difficulty": "clean | phone_photo | blurry | rotated | low_light | cropped",
  "fields": {
    "is_electricity_bill": true,
    "discom": "Maharashtra State Electricity Distribution Co. Ltd. (MSEDCL)",
    "state": "Maharashtra",
    "consumer_number": "170012345678",
    "consumer_name": "Ramesh Patil",
    "tariff_category": "LT I(B) Residential",
    "is_residential": true,
    "sanctioned_load_kw": 2.0,
    "connection_phase": "single | three | null",
    "billing_period_start": "2026-08-01",
    "billing_period_end": "2026-08-31",
    "billing_days": 31,
    "billing_cycle": "monthly | bimonthly",
    "units_billed_kwh": 312,
    "bill_amount_rs": 3456.78,
    "consumption_history": [
      { "month": "2026-07", "units_kwh": 290 },
      { "month": "2026-06", "units_kwh": 344 }
    ],
    "has_solar_net_meter": false,
    "export_units_kwh": null,
    "meter_reading_type": "actual | estimated | unknown",
    "pincode": "411001"
  },
  "notes": "anything odd about this bill"
}
```

Rules:

- `null` means the field is not on the bill. A model should also return `null` there; guessing a value counts as wrong.
- `bill_amount_rs` is the current bill's net amount payable, not including arrears, if the bill shows them separately.
- `consumption_history` lists every month shown on the bill, newest first. For bi-monthly bills, use the end month of each period and the units for the whole period.
- `month` is `YYYY-MM`. Dates are `YYYY-MM-DD`.
- Numbers are plain numbers: no commas, no currency signs, Western digits even if the bill prints Devanagari or other digits.

## Scoring

| Field group | Weight | Match rule |
|---|---|---|
| `units_billed_kwh` | 20 | exact, or within 1% |
| `consumption_history` | 20 | F1 over (month, units) pairs, units within 1% |
| `sanctioned_load_kw` | 10 | within 1% |
| `state`, `discom` | 10 | normalized fuzzy match (DISCOM short code or full name) |
| `is_residential`, `tariff_category` | 10 | boolean exact; category fuzzy |
| `bill_amount_rs` | 10 | within 1% |
| `billing_days`, `billing_cycle`, period dates | 5 | exact |
| `has_solar_net_meter`, `meter_reading_type`, `is_electricity_bill` | 5 | exact |
| `consumer_number`, `consumer_name`, `pincode`, `connection_phase` | 10 | normalized exact |

The total is 100 per bill. We also record latency (seconds), input and output tokens, cost (USD), and whether the output was valid JSON.
