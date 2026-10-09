# Bill extraction benchmark

Run `20261009-193424` · prompt `2026-10-09.2` · 24 bills · repeat 1 · total cost $2.688

Scores are out of 100 (weights in eval/SCHEMA.md). Failed calls score 0. "photo" = any difficulty other than clean. "non-Latin" = label languages include an Indian script.

| model | invocation id | mode used | n | mean | clean | photo | non-Latin | JSON valid | errors | p50 s | p95 s | $/bill | score sd (repeats) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kimi_k3 | `in.moonshotai.kimi-k3` | tool->text_fallback, tool_forced | 24 | 94.4 | 93.2 | 97.4 | 98.4 | 96% | 0 | 44.3 | 214.6 | 0.0657 | - |
| llama4_maverick | `us.meta.llama4-maverick-17b-instruct-v1:0` | tool_auto | 24 | 94.0 | 97.5 | 85.6 | 93.5 | 100% | 0 | 3.9 | 5.2 | 0.0021 | - |
| kimi_k25 | `moonshotai.kimi-k2.5` | json_text | 24 | 92.0 | 95.1 | 84.5 | 90.5 | 100% | 0 | 3.0 | 4.7 | 0.0051 | - |
| mistral_large3 | `mistral.mistral-large-3-675b-instruct` | tool_forced | 24 | 88.3 | 91.3 | 80.9 | 87.7 | 100% | 0 | 2.7 | 3.5 | 0.0031 | - |
| ministral8b | `mistral.ministral-3-8b-instruct` | tool_forced | 24 | 86.6 | 91.3 | 75.1 | 85.6 | 100% | 0 | 1.9 | 2.5 | 0.0008 | - |
| qwen3_vl | `qwen.qwen3-vl-235b-a22b` | tool_forced | 24 | 84.5 | 87.3 | 77.9 | 82.5 | 100% | 0 | 8.4 | 13.2 | 0.0041 | - |
| llama4_scout | `us.meta.llama4-scout-17b-instruct-v1:0` | tool_auto | 24 | 84.4 | 88.5 | 74.3 | 83.3 | 100% | 0 | 3.7 | 4.6 | 0.0014 | - |
| ministral14b | `mistral.ministral-3-14b-instruct` | tool_forced | 24 | 84.1 | 88.7 | 72.9 | 82.6 | 100% | 0 | 2.3 | 3.0 | 0.0011 | - |
| magistral_small | `mistral.magistral-small-2509` | json_text | 24 | 80.3 | 87.1 | 63.8 | 79.1 | 100% | 0 | 4.7 | 8.3 | 0.0033 | - |
| pixtral_large | `us.mistral.pixtral-large-2502-v1:0` | json_text | 24 | 76.2 | 79.1 | 69.3 | 74.8 | 100% | 0 | 8.7 | 14.5 | 0.0142 | - |
| ministral3b | `mistral.ministral-3-3b-instruct` | tool->text_fallback, tool_forced | 24 | 74.8 | 82.8 | 55.6 | 73.3 | 100% | 0 | 1.9 | 2.7 | 0.0005 | - |
| nova2_lite | `global.amazon.nova-2-lite-v1:0` | tool_forced | 24 | 71.2 | 77.7 | 55.4 | 68.0 | 100% | 0 | 3.5 | 4.5 | 0.0021 | - |
| nova_pro | `apac.amazon.nova-pro-v1:0` | tool_forced | 24 | 68.4 | 72.1 | 59.4 | 67.8 | 100% | 0 | 4.1 | 5.5 | 0.0052 | - |
| nemotron_vl | `nvidia.nemotron-nano-12b-v2` | json_text | 24 | 66.3 | 69.5 | 58.4 | 63.9 | 96% | 0 | 2.9 | 4.4 | 0.0015 | - |
| gemma3_27b | `google.gemma-3-27b-it` | json_text | 24 | 66.1 | 69.3 | 58.4 | 64.5 | 100% | 0 | 6.0 | 7.2 | 0.0008 | - |
| gemma3_12b | `google.gemma-3-12b-it` | json_text | 24 | 61.0 | 65.5 | 50.1 | 59.3 | 100% | 0 | 4.0 | 6.6 | 0.0004 | - |
| nova_lite | `apac.amazon.nova-lite-v1:0` | tool_forced | 24 | 57.9 | 63.1 | 45.3 | 55.5 | 100% | 0 | 3.1 | 3.6 | 0.0004 | - |
| gemma3_4b | `google.gemma-3-4b-it` | json_text | 24 | 48.3 | 50.7 | 42.7 | 46.4 | 100% | 0 | 2.2 | 2.6 | 0.0002 | - |

## Per-field accuracy (% of bills where the field was right)

| field | weight | kimi_k3 | llama4_maverick | kimi_k25 | mistral_large3 | ministral8b | qwen3_vl | llama4_scout | ministral14b | magistral_small | pixtral_large | ministral3b | nova2_lite | nova_pro | nemotron_vl | gemma3_27b | gemma3_12b | nova_lite | gemma3_4b |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| units_billed_kwh | 20.00 | 96 | 100 | 88 | 88 | 92 | 88 | 92 | 96 | 71 | 75 | 67 | 58 | 67 | 75 | 79 | 62 | 50 | 38 |
| consumption_history | 20.00 | 94 | 92 | 87 | 83 | 72 | 69 | 70 | 56 | 68 | 52 | 59 | 44 | 27 | 28 | 15 | 8 | 31 | 13 |
| sanctioned_load_kw | 10.00 | 96 | 96 | 92 | 92 | 92 | 88 | 88 | 96 | 88 | 88 | 83 | 83 | 88 | 79 | 83 | 83 | 88 | 58 |
| state | 5.00 | 96 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 92 | 100 | 100 | 100 | 100 | 83 | 96 | 100 | 75 | 92 |
| discom | 5.00 | 88 | 92 | 92 | 96 | 96 | 92 | 92 | 96 | 100 | 92 | 96 | 92 | 92 | 79 | 92 | 96 | 83 | 58 |
| is_residential | 5.00 | 96 | 96 | 100 | 100 | 100 | 96 | 83 | 100 | 96 | 96 | 100 | 100 | 96 | 96 | 92 | 92 | 88 | 88 |
| tariff_category | 5.00 | 88 | 92 | 100 | 88 | 83 | 96 | 79 | 88 | 88 | 67 | 79 | 83 | 62 | 71 | 58 | 54 | 58 | 33 |
| bill_amount_rs | 10.00 | 96 | 88 | 96 | 83 | 79 | 79 | 83 | 83 | 79 | 75 | 75 | 75 | 79 | 71 | 71 | 71 | 71 | 62 |
| billing_days | 1.25 | 88 | 88 | 92 | 92 | 88 | 88 | 83 | 71 | 83 | 71 | 88 | 71 | 83 | 71 | 71 | 71 | 29 | 33 |
| billing_cycle | 1.25 | 92 | 96 | 96 | 92 | 100 | 96 | 96 | 92 | 96 | 88 | 79 | 83 | 100 | 71 | 46 | 67 | 92 | 42 |
| billing_period_start | 1.25 | 96 | 100 | 88 | 75 | 79 | 79 | 92 | 79 | 79 | 83 | 67 | 62 | 71 | 33 | 38 | 33 | 67 | 25 |
| billing_period_end | 1.25 | 96 | 92 | 92 | 75 | 67 | 83 | 71 | 67 | 71 | 83 | 46 | 62 | 67 | 46 | 42 | 33 | 46 | 33 |
| has_solar_net_meter | 1.67 | 96 | 100 | 100 | 100 | 100 | 100 | 100 | 96 | 96 | 100 | 100 | 100 | 100 | 92 | 96 | 88 | 96 | 92 |
| meter_reading_type | 1.67 | 96 | 100 | 100 | 100 | 100 | 96 | 96 | 96 | 100 | 92 | 100 | 92 | 96 | 92 | 92 | 92 | 38 | 88 |
| is_electricity_bill | 1.67 | 96 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 96 | 100 | 100 | 92 | 96 |
| consumer_number | 2.50 | 96 | 79 | 79 | 67 | 71 | 62 | 71 | 54 | 67 | 75 | 58 | 58 | 71 | 67 | 62 | 50 | 54 | 42 |
| consumer_name | 2.50 | 96 | 88 | 92 | 83 | 88 | 88 | 83 | 83 | 88 | 71 | 83 | 83 | 62 | 75 | 79 | 71 | 58 | 71 |
| pincode | 2.50 | 96 | 92 | 100 | 92 | 100 | 79 | 96 | 88 | 75 | 83 | 50 | 88 | 38 | 54 | 75 | 79 | 17 | 58 |
| connection_phase | 2.50 | 96 | 83 | 96 | 92 | 88 | 96 | 75 | 96 | 92 | 88 | 71 | 83 | 92 | 75 | 92 | 92 | 33 | 83 |
| export_units_kwh | 0.00 | 96 | 96 | 100 | 92 | 92 | 96 | 96 | 92 | 88 | 92 | 92 | 92 | 62 | 88 | 92 | 88 | 88 | 88 |

## Weakest fields per model (by points lost)

- **kimi_k3**: consumption_history (94%, -1.3 pts), units_billed_kwh (96%, -0.8 pts), tariff_category (88%, -0.6 pts), discom (88%, -0.6 pts)
- **llama4_maverick**: consumption_history (92%, -1.5 pts), bill_amount_rs (88%, -1.2 pts), consumer_number (79%, -0.5 pts), tariff_category (92%, -0.4 pts)
- **kimi_k25**: consumption_history (87%, -2.6 pts), units_billed_kwh (88%, -2.5 pts), sanctioned_load_kw (92%, -0.8 pts), consumer_number (79%, -0.5 pts)
- **mistral_large3**: consumption_history (83%, -3.4 pts), units_billed_kwh (88%, -2.5 pts), bill_amount_rs (83%, -1.7 pts), sanctioned_load_kw (92%, -0.8 pts)
- **ministral8b**: consumption_history (72%, -5.6 pts), bill_amount_rs (79%, -2.1 pts), units_billed_kwh (92%, -1.7 pts), sanctioned_load_kw (92%, -0.8 pts)
- **qwen3_vl**: consumption_history (69%, -6.2 pts), units_billed_kwh (88%, -2.5 pts), bill_amount_rs (79%, -2.1 pts), sanctioned_load_kw (88%, -1.2 pts)
- **llama4_scout**: consumption_history (70%, -6.1 pts), units_billed_kwh (92%, -1.7 pts), bill_amount_rs (83%, -1.7 pts), sanctioned_load_kw (88%, -1.2 pts)
- **ministral14b**: consumption_history (56%, -8.9 pts), bill_amount_rs (83%, -1.7 pts), consumer_number (54%, -1.1 pts), units_billed_kwh (96%, -0.8 pts)
- **magistral_small**: consumption_history (68%, -6.4 pts), units_billed_kwh (71%, -5.8 pts), bill_amount_rs (79%, -2.1 pts), sanctioned_load_kw (88%, -1.2 pts)
- **pixtral_large**: consumption_history (52%, -9.6 pts), units_billed_kwh (75%, -5.0 pts), bill_amount_rs (75%, -2.5 pts), tariff_category (67%, -1.7 pts)
- **ministral3b**: consumption_history (59%, -8.1 pts), units_billed_kwh (67%, -6.7 pts), bill_amount_rs (75%, -2.5 pts), sanctioned_load_kw (83%, -1.7 pts)
- **nova2_lite**: consumption_history (44%, -11.2 pts), units_billed_kwh (58%, -8.3 pts), bill_amount_rs (75%, -2.5 pts), sanctioned_load_kw (83%, -1.7 pts)
- **nova_pro**: consumption_history (27%, -14.6 pts), units_billed_kwh (67%, -6.7 pts), bill_amount_rs (79%, -2.1 pts), tariff_category (62%, -1.9 pts)
- **nemotron_vl**: consumption_history (28%, -14.4 pts), units_billed_kwh (75%, -5.0 pts), bill_amount_rs (71%, -2.9 pts), sanctioned_load_kw (79%, -2.1 pts)
- **gemma3_27b**: consumption_history (15%, -17.0 pts), units_billed_kwh (79%, -4.2 pts), bill_amount_rs (71%, -2.9 pts), tariff_category (58%, -2.1 pts)
- **gemma3_12b**: consumption_history (8%, -18.5 pts), units_billed_kwh (62%, -7.5 pts), bill_amount_rs (71%, -2.9 pts), tariff_category (54%, -2.3 pts)
- **nova_lite**: consumption_history (31%, -13.9 pts), units_billed_kwh (50%, -10.0 pts), bill_amount_rs (71%, -2.9 pts), pincode (17%, -2.1 pts)
- **gemma3_4b**: consumption_history (13%, -17.4 pts), units_billed_kwh (38%, -12.5 pts), sanctioned_load_kw (58%, -4.2 pts), bill_amount_rs (62%, -3.8 pts)

Raw results: `eval/results/full-noclaude.json`
