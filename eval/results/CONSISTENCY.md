# Bill extraction benchmark

Run `20261009-195146` · prompt `2026-10-09.2` · 24 bills · repeat 3 · total cost $0.802

Scores are out of 100 (weights in eval/SCHEMA.md). Failed calls score 0. "photo" = any difficulty other than clean. "non-Latin" = label languages include an Indian script.

| model | invocation id | mode used | n | mean | clean | photo | non-Latin | JSON valid | errors | p50 s | p95 s | $/bill | score sd (repeats) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| llama4_maverick | `us.meta.llama4-maverick-17b-instruct-v1:0` | tool_auto | 72 | 93.9 | 97.2 | 85.7 | 93.3 | 100% | 0 | 4.0 | 5.0 | 0.0021 | 0.6 |
| kimi_k25 | `moonshotai.kimi-k2.5` | json_text | 72 | 91.9 | 94.8 | 84.7 | 90.8 | 100% | 0 | 4.2 | 6.3 | 0.0051 | 0.9 |
| mistral_large3 | `mistral.mistral-large-3-675b-instruct` | tool_forced | 72 | 87.1 | 90.1 | 79.6 | 86.2 | 100% | 0 | 4.0 | 5.0 | 0.0031 | 4.0 |
| ministral8b | `mistral.ministral-3-8b-instruct` | tool_forced | 72 | 85.4 | 90.0 | 74.2 | 84.2 | 100% | 0 | 2.9 | 4.0 | 0.0008 | 1.9 |

## Per-field accuracy (% of bills where the field was right)

| field | weight | llama4_maverick | kimi_k25 | mistral_large3 | ministral8b |
|---|---|---|---|---|---|
| units_billed_kwh | 20.00 | 100 | 88 | 88 | 89 |
| consumption_history | 20.00 | 91 | 87 | 80 | 71 |
| sanctioned_load_kw | 10.00 | 96 | 93 | 88 | 92 |
| state | 5.00 | 100 | 100 | 99 | 100 |
| discom | 5.00 | 92 | 92 | 93 | 96 |
| is_residential | 5.00 | 97 | 100 | 99 | 99 |
| tariff_category | 5.00 | 93 | 100 | 90 | 83 |
| bill_amount_rs | 10.00 | 88 | 94 | 83 | 78 |
| billing_days | 1.25 | 88 | 92 | 93 | 90 |
| billing_cycle | 1.25 | 96 | 96 | 93 | 99 |
| billing_period_start | 1.25 | 100 | 88 | 78 | 72 |
| billing_period_end | 1.25 | 92 | 92 | 76 | 65 |
| has_solar_net_meter | 1.67 | 100 | 100 | 99 | 99 |
| meter_reading_type | 1.67 | 100 | 100 | 99 | 99 |
| is_electricity_bill | 1.67 | 100 | 100 | 99 | 100 |
| consumer_number | 2.50 | 79 | 78 | 67 | 71 |
| consumer_name | 2.50 | 88 | 90 | 82 | 82 |
| pincode | 2.50 | 90 | 97 | 89 | 100 |
| connection_phase | 2.50 | 83 | 97 | 93 | 88 |
| export_units_kwh | 0.00 | 96 | 100 | 92 | 92 |

## Weakest fields per model (by points lost)

- **llama4_maverick**: consumption_history (91%, -1.8 pts), bill_amount_rs (88%, -1.2 pts), consumer_number (79%, -0.5 pts), discom (92%, -0.4 pts)
- **kimi_k25**: consumption_history (87%, -2.6 pts), units_billed_kwh (88%, -2.5 pts), sanctioned_load_kw (93%, -0.7 pts), bill_amount_rs (94%, -0.6 pts)
- **mistral_large3**: consumption_history (80%, -4.0 pts), units_billed_kwh (88%, -2.5 pts), bill_amount_rs (83%, -1.7 pts), sanctioned_load_kw (88%, -1.2 pts)
- **ministral8b**: consumption_history (71%, -5.8 pts), units_billed_kwh (89%, -2.2 pts), bill_amount_rs (78%, -2.2 pts), sanctioned_load_kw (92%, -0.8 pts)

Raw results: `eval/results/consistency.json`
