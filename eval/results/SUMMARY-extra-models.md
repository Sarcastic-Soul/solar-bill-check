# Bill extraction benchmark

Run `20261009-203424` · prompt `2026-10-09.2` · 24 bills · repeat 1 · total cost $0.017

Scores are out of 100 (weights in eval/SCHEMA.md). Failed calls score 0. "photo" = any difficulty other than clean. "non-Latin" = label languages include an Indian script.

| model | invocation id | mode used | n | mean | clean | photo | non-Latin | JSON valid | errors | p50 s | p95 s | $/bill | score sd (repeats) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| palmyra_vision | `writer.palmyra-vision-7b` | json_text | 24 | 17.1 | 13.4 | 26.3 | 17.2 | 79% | 0 | 3.8 | 9.9 | 0.0007 | - |

## Per-field accuracy (% of bills where the field was right)

| field | weight | palmyra_vision |
|---|---|---|
| units_billed_kwh | 20.00 | 8 |
| consumption_history | 20.00 | 0 |
| sanctioned_load_kw | 10.00 | 21 |
| state | 5.00 | 67 |
| discom | 5.00 | 50 |
| is_residential | 5.00 | 67 |
| tariff_category | 5.00 | 0 |
| bill_amount_rs | 10.00 | 21 |
| billing_days | 1.25 | 12 |
| billing_cycle | 1.25 | 25 |
| billing_period_start | 1.25 | 0 |
| billing_period_end | 1.25 | 0 |
| has_solar_net_meter | 1.67 | 42 |
| meter_reading_type | 1.67 | 4 |
| is_electricity_bill | 1.67 | 4 |
| consumer_number | 2.50 | 17 |
| consumer_name | 2.50 | 8 |
| pincode | 2.50 | 8 |
| connection_phase | 2.50 | 0 |
| export_units_kwh | 0.00 | 0 |

## Weakest fields per model (by points lost)

- **palmyra_vision**: consumption_history (0%, -20.0 pts), units_billed_kwh (8%, -18.3 pts), sanctioned_load_kw (21%, -7.9 pts), bill_amount_rs (21%, -7.9 pts)

Raw results: `eval/results/extra-models.json`
