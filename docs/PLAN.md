# Build plan: Solar Bill Check (working name)

Track: **Waste and Energy**. Deadline: **Sun Oct 11, 20:00 IST** (we aim to submit by 17:00).
Research behind every number: [RESEARCH.md](RESEARCH.md).

## The pitch in one line

Snap your electricity bill, and in 30 seconds learn if rooftop solar is worth it for *your* home: what size, what it costs after the PM Surya Ghar subsidy, when it pays back, and exactly how to apply.

## Why this can win

- **Real gap:** the scheme has reached about 50 lakh homes, but the target is 1 crore by Mar 2027. That leaves 6 months to reach the other half. The portal calculator asks for your "average monthly bill in ₹" and gives a generic answer. It ignores your actual usage history, your DISCOM's slab tariff and your state's free-units scheme.
- **Honest answer, not a sales pitch:**
  - A Delhi home using 180 units a month already pays ₹0, so solar saves it almost nothing. We say that.
  - A Mumbai home on MSEDCL paying ₹12–19 per unit gets paid back in about 3 years. We say that too.
  - Most calculators skip this. Judges will notice.
- **One-photo demo moment:** bill photo in, personal answer out. Easy to show in a 3-minute video.
- **AWS is part of how it works,** not just mentioned:
  - Bedrock reads the bill.
  - A Strands agent answers questions.
  - Polly speaks Hindi.
  - Lambda, S3, DynamoDB and Amplify run the app.

## User flow

1. **Upload:** photo or PDF of the bill. Or "no bill handy? enter your monthly units".
2. **Confirm:** we show what we read (DISCOM, consumer category, sanctioned load, units for each month we found). Every field can be edited. Low-confidence fields are highlighted.
3. **Pincode:** we look up the state, district and solar yield for that location.
4. **Result:**
   - A verdict: **Worth it / Worth it with a loan / Not worth it right now**, with the reason.
   - Recommended size (kW), which is capped by the sanctioned load and the roof area if given.
   - Gross cost, central subsidy plus any state top-up, net cost.
   - Monthly bill before and after solar, using the real slab tariff and free units.
   - Payback years, 25-year savings, CO₂ avoided per year, tree equivalent, roof area needed.
   - Loan view: EMI at about 6% for 10 years next to the monthly saving ("pays for itself from month 1").
5. **Apply checklist:**
   - Personal steps: register on pmsuryaghar.gov.in with *your* DISCOM and consumer number, check vendors on the portal's find-vendor page, apply for the loan on Jan Samarth.
   - The document list.
   - Red flags: non-DCR panels lose the subsidy, and never pay before the agreement.
6. **Ask:** a chat assistant in English or Hindi ("what if I install 2 kW instead?", "what happens to extra units?"). A **Listen** button reads the answer aloud in Hindi.

## Scope

**Must have (done by Sat 14:00):**
- Upload, Bedrock extraction, the confirm screen, pincode lookup to PVGIS, the calculation engine, the result screen, the checklist.
- Deployed on AWS with a public URL.

**Should have (Sat evening):**
- Chat assistant (Strands).
- Hindi toggle and Polly "Listen".
- Loan/EMI view.
- Shareable result link.

**Stretch (only if everything above is solid):**
- Voice question in Hindi (Transcribe).
- RWA / apartment mode.
- PDF of the result to hand to a vendor.

**Out of scope:** login, a vendor marketplace, scraping the government portal.

## Calculation engine (plain Python, unit tested, no LLM)

The LLM only reads the bill and explains results. All numbers come from code, so they are the same every time and can be checked.

1. **Monthly units:**
   - Use the history from the bill (MSEDCL has 12 months, Delhi bills have 6).
   - If only one month is available, use it for all 12 and say so.
   - TN bills cover 2 months, so halve them.
2. **Yield:**
   - PVGIS `E_y` and monthly `E_m` for the lat/lon (`optimalangles=1`, `mountingplace=building`).
   - Fallback: Global Solar Atlas, then 1450 kWh/kW/yr.
3. **Size:**
   - Annual units ÷ yield, rounded to the nearest 0.5 kW, minimum 1 kW.
   - Capped at the sanctioned load, and at roof area ÷ 10 m² if a roof area is given.
   - Also show the 3 kW option, since it gets the full subsidy.
4. **Subsidy:** `min(kW,2)×30000 + min(max(kW−2,0),1)×18000`, ×1.1 for special-category states. Add the state top-up where known (UP ₹15k/kW up to ₹30k; the Delhi one is flagged as unconfirmed).
5. **Cost:** ₹70k/kW (1 kW), ₹65k/kW (2 kW), ₹62k/kW (3 kW+). The user can edit this.
6. **Savings, month by month:**
   - Compute `bill(units)` minus `bill(max(0, units − solar_month))`, using `tariffs.json` slabs, fixed charges and the free-unit rules.
   - Surplus units go into a yearly bank (net metering) and are paid at the state export rate (MH ₹2.82; others use a conservative default of ₹2).
   - Unknown DISCOM: use an effective rate of bill amount ÷ units.
7. **Payback:** net cost ÷ yearly savings.
   - 25-year savings: assume 0.5% panel loss per year and a 3% tariff rise per year. Show both assumptions.
8. **CO₂:** kWh × 0.71 kg. Trees = kg ÷ 21.
9. **Verdict:**
   - Payback ≤ 6 years: worth it.
   - 6–10 years, or the EMI is below the saving: worth it with a loan.
   - Over 10 years, or the home is in a free-units band: not worth it right now (explain why, and what would change it).

**Tariff coverage:**
- Full: Delhi (BRPL, BYPL, TPDDL), MSEDCL, UPPCL. These are verified.
- Marked as estimate: BESCOM, TNPDCL.
- Everything else: the effective-rate fallback.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Vite + React + TypeScript, static build, Phosphor icons | Simple static site, no server-side rendering gotchas |
| Hosting | **AWS Amplify Hosting** (ap-south-1) | HTTPS URL for judges, clearly AWS |
| Backend | **AWS SAM**, Python 3.14 arm64 Lambdas with **Function URLs** | One `template.yaml`, one deploy; Function URLs avoid API Gateway's 30 s limit |
| Bill reading | **Amazon Bedrock**, Kimi K2.5 and Mistral Large 3 run side by side in ap-south-1, forced tool use for JSON, code checks | Picked by benchmark (`eval/`). Fields where the two models disagree are flagged for the user to check. Reads Hindi/Marathi labels and tables; Textract can't. Data stays in India |
| Assistant | **Strands Agents SDK** (AWS open source) with tools `calculate_plan`, `get_solar_yield`, `scheme_facts` | Counts for the open-source rule too; simple Python tools |
| Voice | **Amazon Polly**, Kajal neural hi-IN | "Listen in Hindi" button, cheap |
| Storage | **S3** (bill uploads by presigned URL, deleted right after reading, 1-day expiry as backup), **DynamoDB** (results, chat history) | Always-free DynamoDB; bills not kept long (privacy) |
| Ops | CloudWatch logs, **AWS Budgets** alarm at $30 | Cost safety |
| External | PVGIS, postalpincode.in, Nominatim (cached) | Free, no keys |

All AWS resources go in **ap-south-1 (Mumbai)**. The extraction model IDs are set by the `ExtractModels` stack parameter, so they can change without code edits. Claude models get benchmarked once Anthropic model access is approved.

## Architecture

```
Browser (Amplify Hosting, static React)
   |
   |-- POST /upload-url ------> ApiFunction (Lambda, Function URL)
   |                              returns S3 presigned PUT
   |-- PUT bill -------------> S3 bills bucket (deleted after read)
   |-- POST /extract ---------> ApiFunction -> Bedrock Kimi K2.5 + Mistral Large 3 (read bill)
   |                              -> Pydantic checks -> fields + confidence
   |-- POST /plan ------------> ApiFunction -> postalpincode + Nominatim + PVGIS
   |                              -> engine -> DynamoDB (results) -> plan JSON
   |-- POST /speak -----------> ApiFunction -> Polly (Kajal) -> mp3
   |-- POST /chat ------------> ChatFunction (Strands agent, Bedrock)
                                  tools call the same engine; history in DynamoDB
```

Two Lambdas, because Strands is heavy and should not slow down the main API's cold start.

## Repo layout

```
backend/
  template.yaml          SAM: 2 functions, S3 bucket, DynamoDB tables
  src/api/               handler.py (small router), extract.py, plan.py, speak.py
  src/chat/              handler.py (Strands agent + tools)
  src/engine/            sizing.py, tariffs.py, subsidy.py, data/tariffs.json, constants.py
  tests/                 engine unit tests, sample bill fixtures
frontend/                Vite React app
docs/                    PLAN.md, RESEARCH.md, architecture diagram
```

## Cost estimate

Assuming 500 bill reads and 2,000 chat messages:

- Bedrock bill reading: about $0.01 per bill for both models, so about $5. Chat model cost comes on top.
- Lambda, DynamoDB and CloudWatch: about $0.
- Polly: a few dollars.
- Amplify: about $0–2.

This fits in the account credits. Keep `max_tokens` capped and trim chat history to the last 10 turns.

## Timeline

### Fri Oct 9 (today)
- [ ] `git init`, public GitHub repo, `.gitignore` (add `.playwright-mcp/`)
- [ ] Install SAM CLI. Create the AWS Budget alarm. Check whether the account is on the Free or Paid plan.
- [ ] Engine module + `tariffs.json` + unit tests (Delhi 180 / 450 units, MSEDCL 350 units, UPPCL 300 units)
- [ ] Extraction prompt + tool schema, tested on 3 sample bills (MSEDCL PDF, TPDDL page, BSES JPEG) + **your own real bill**
- [ ] SAM skeleton deployed to ap-south-1 (upload-url + extract working)

### Sat Oct 10
- [ ] 09–13: `/plan` end to end (pincode, PVGIS, engine, DynamoDB). Frontend upload → confirm → result.
- [ ] 13–14: deploy frontend to Amplify. **Must-have scope done and live.**
- [ ] 14–19: checklist screen, loan view, chat (Strands), Hindi + Polly
- [ ] 19–22: design pass (design-guardrails), mobile check, error states
- [ ] 22:00: scope freeze. Only bug fixes after this.

### Sun Oct 11
- [ ] 08–11: fixes, README, architecture diagram, test on 5 bills
- [ ] 11–12: record the demo flow; feature freeze at 12:00
- [ ] 12–15: demo video (under 3 min) with the `demo-video` skill, upload to YouTube as unlisted, check it in a signed-out browser
- [ ] 15–16: writeup (problem, build, where AWS fits, AI tools used)
- [ ] 16–17: AWS Builder Center blog post, link it in the submission
- [ ] **17:00 submit.** The 3 hours before the deadline are buffer.

## Demo video outline (under 3 min)

- **0:00–0:20:** problem.
  - "50 lakh homes have solar under PM Surya Ghar. The target is 1 crore by March. Most people never start, because nobody tells them what it means for *their* bill."
- **0:20–1:50:** one full run.
  - Photo of a real MSEDCL bill, confirm screen, result with the verdict, loan view, checklist.
  - Then a quick second case: a Delhi 180-unit home, where the honest verdict is "not worth it right now".
- **1:50–2:20:** ask in Hindi, then Listen.
- **2:20–2:45:** architecture slide, plus 5 s of the AWS console (Lambda, Bedrock, DynamoDB).
- **2:45–3:00:** impact line and URL.

## Risks and fallbacks

| Risk | Fallback |
|---|---|
| Bedrock misreads a bill | Confirm screen with editable fields; two-model agreement check; manual units entry |
| A Bedrock model is slow or unavailable | Model IDs in the `ExtractModels` parameter; one model alone still works, with medium confidence |
| PVGIS down or slow | Global Solar Atlas, then 1450 constant |
| Nominatim blocks us | Cache by pincode; Photon; state-capital coordinates |
| Tariff for an unknown DISCOM | Effective rate from the bill (amount ÷ units), labelled as an estimate |
| Run out of time | Cut chat and Polly first; the must-have flow alone is a complete product |

## Open decisions for you

1. Product name (Solar Bill Check is a placeholder).
2. Solo or team? If team, split frontend and backend now.
3. Create the public GitHub repo under Sarcastic-Soul now?
