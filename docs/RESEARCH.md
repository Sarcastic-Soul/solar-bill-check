# Research notes

Collected on 2026-10-09. Every number here has a source. Items marked **[UNSURE]** were not confirmed from an official source; treat them as estimates and say so in the UI.

## 1. PM Surya Ghar: Muft Bijli Yojana

Main source: MNRE "Guidelines for PM-Surya Ghar: Muft Bijli Yojana – CFA to Residential Consumers", OM dated 7 Jun 2024 ([mirror PDF](https://jbvnl.co.in/SOLAR/Operational%20Guidelines%20to%20PM%20Suryaghar%207%20June%2024.pdf)). Also the public JS bundle of pmsuryaghar.gov.in (FAQ, how-to-apply, financing text) and the [PIB explainer, 13 Mar 2025](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/mar/doc2025313520001.pdf).

### Subsidy (CFA)

| Segment | General states | Special category states |
|---|---|---|
| First 2 kW | ₹30,000/kW | ₹33,000/kW |
| 3rd kW | ₹18,000/kW | ₹19,800/kW |
| Above 3 kW | nothing extra, cap ₹78,000 | cap ₹85,800 |
| RWA / group housing common areas | ₹18,000/kW | ₹19,800/kW |

- Special category: North-Eastern states incl. Sikkim, Uttarakhand, Himachal Pradesh, J&K, Ladakh, Andaman & Nicobar, Lakshadweep.
- Paid on module DC capacity, not inverter size. Batteries get no subsidy.
- RWA: CFA on the lower of (3 kW × number of houses) and installed kW, max 500 kW.
- Rates unchanged as of Sep 2026. A July 2025 amendment added 5-year mandatory maintenance by vendors.
- Scheme runs to **31 Mar 2027**. Budget raised from ₹17,000 cr (FY26) to ₹22,000 cr (FY27). Talk of a next phase, nothing official.
- Aadhaar authentication became mandatory for CFA in Mar 2026.
- States can add their own top-up:
  - UP: ₹15,000/kW, max ₹30,000. Source: installer and news sites.
  - Delhi: a 2026 scheme adds a matching ₹78,000 (total ₹1.56 L), with zero upfront cost for 3 kW for homes up to 400 units a month. **[UNSURE]** not checked against the official notification.

### Eligibility

- Indian citizen who owns a house with a suitable roof.
- Valid residential electricity connection (consumer number).
- No earlier solar subsidy. Earlier Phase II users get CFA only for the extra capacity, up to 3 kW total.
- Grid-connected only, capex model only. Off-grid is not eligible. Non-residential consumers get no CFA.
- Modules must be DCR, meaning made in India from Indian cells. Any non-DCR module makes the system ineligible.

### Application steps (portal)

1. Register on pmsuryaghar.gov.in with mobile + OTP. Enter State, District, DISCOM, consumer number.
2. Feasibility: systems up to 10 kW are auto-approved for LT residential consumers. Don't start installing before approval.
3. Pick a vendor registered for your DISCOM and agree the price directly. You can change vendor only until the agreement is uploaded; after that the vendor is locked for 45 days.
4. Vendor installs and fills installation details. Consumer checks them and submits to the DISCOM.
5. Net meter installed and agreement signed. 32 states/UTs have dropped the application and net-meter fees.
6. DISCOM inspection, then commissioning certificate. The system needs a performance ratio of at least 75%.
7. Upload a cancelled cheque or passbook (name must match the bill exactly), then redeem the e-token. Subsidy arrives in about 15–30 days (sources differ).

Documents: bank proof (mandatory), Aadhaar authentication, geo-tagged photo of the installation, DCR undertaking, vendor agreement with 5-year maintenance. Electricity bill upload is optional at application.

Vendors: 34,219 registered, 29,469 active (Mercom, Aug 2026). The portal has a "find vendor" page per DISCOM and a rating system.

### Concessional loan (12 public sector banks, apply through [Jan Samarth](https://www.jansamarth.in))

| | Up to ₹2 lakh (about 3 kW) | ₹2–6 lakh (3–10 kW) |
|---|---|---|
| Rate | repo + 0.5%, about 6.00% now | home-loan rate or HL + 1% |
| Margin | 10% | 20% |
| Income proof | none | PAN, income ≥ ₹3 L |

No collateral, up to 10 years, 6-month moratorium, no processing fee. RBI raised repo to 5.50% on 7 Oct 2026, so show "repo + 0.5% (about 6%)".

### Cost per kW

- MNRE benchmark, used only for the subsidy maths: ₹50,000/kW (first 2 kW), ₹45,000 (3rd kW).
- Market price 2026, from installer sites **[UNSURE]**:
  - ₹55,000–85,000/kW, with smaller systems costing more per kW.
  - 3 kW DCR on-grid: about ₹1.6–2.2 L.
- DCR premium: about ₹8,000–12,000 per kW.
- App defaults: ₹70k/kW (1 kW), ₹65k/kW (2 kW), ₹62k/kW (3 kW+). The user can override these.

### Sizing and generation

- MNRE: 1 kW gives 4–5.5 units a day on a sunny day. A 3 kW system gives about 300+ units a month.
- Roof: 10–12 m² of shadow-free area per kW.
- PIB sizing table:

| Monthly units | Size | Subsidy |
|---|---|---|
| 0–150 | 1–2 kW | ₹30k–60k |
| 150–300 | 2–3 kW | ₹60k–78k |
| 300+ | above 3 kW | ₹78k |

- The portal calculator takes state, category and average monthly bill (₹), plus optional roof area, budget, capacity and sanctioned load. Its formula runs on the server and could not be seen.

### Net metering by state

- **Delhi:**
  - Unused credits are paid at year end at the DISCOM's average power purchase cost.
  - A 2026 rule cut net-meter time to 25 days and waived fees up to 10 kW.
  - Delhi Solar Policy 2024 pays a generation incentive of ₹3/unit (1–3 kW) or ₹2/unit (3–10 kW) for 5 years.
- **Maharashtra:** surplus paid at ₹2.82/kWh for FY 2026-27.
- **Karnataka:** new rules from 25 Aug 2026.
  - Subsidised domestic systems get ₹1.96 (1–2 kW), ₹2.14 (2–3 kW) or ₹2.58 (>3 kW) per exported unit.
  - Whether domestic surplus is settled under net or gross metering is **[UNSURE]**.
- **UP:** net metering allowed for domestic users. Year-end surplus rate **[UNSURE]** (₹0.50–2).

### Impact numbers for the pitch

- Over **50 lakh households** benefited, 14.8 GW installed, ₹28,024 cr subsidy paid (MNRE via Mercom, Aug 2026).
- 5.06 lakh households added in July 2026 alone, a record.
- About 19 lakh households have had a zero bill.
- Target is 1 crore homes by Mar 2027, so the scheme is about half-way with 6 months left. **This gap is our pitch.**

## 2. Data sources

### Solar yield per kW (tested live)

| Source | Delhi | Bengaluru | Notes |
|---|---|---|---|
| **PVGIS 5.3** (`mountingplace=building`, optimal tilt) | 1554 | 1459 | Keyless, no CORS (call from the server), 30 calls/s |
| PVWatts v8 | 1443 | 1517 | Free key; host is now `developer.nlr.gov` (old `developer.nrel.gov` no longer resolves) |
| Global Solar Atlas | 1466 | 1577 | Unofficial keyless endpoint, CORS `*` |

All values are kWh per kWp per year.

- **PVGIS call:** `https://re.jrc.ec.europa.eu/api/v5_3/PVcalc?lat=..&lon=..&peakpower=1&loss=14&optimalangles=1&mountingplace=building&outputformat=json`
  - Use `outputs.totals.fixed.E_y` for the yearly total and `outputs.monthly.fixed[].E_m` for months.
  - India only works with the PVGIS-ERA5 database, which is picked automatically.
  - Always pass `optimalangles=1`. Without it the panel is flat and the result is about 12% lower.
- **Global Solar Atlas fallback:** `https://api.globalsolaratlas.info/data/lta?loc=LAT,LON`, using `annual.data.PVOUT_csi`.
- **Last fallback:** 1450.

### Pincode to location

1. `https://api.postalpincode.in/pincode/{pin}` gives state and district but no lat/lon. Check `Status`, because a bad pin still returns HTTP 200.
2. Nominatim `https://nominatim.openstreetmap.org/search?postalcode={pin}&countrycodes=in&format=jsonv2&limit=1` gives lat/lon.
   - Call it from the server, at most 1 request/s, with a real User-Agent.
   - Cache results by pincode and show OSM attribution.
3. Photon `https://photon.komoot.io/api/?q={pin}%20India&limit=1` as a backup. Check that the returned postcode matches.

### Domestic tariffs (hardcode into `tariffs.json`)

| DISCOM | Fixed charge | Energy slabs (₹/kWh) | Confidence |
|---|---|---|---|
| Delhi: BRPL, BYPL, TPDDL | ₹20/kW (≤2 kW), ₹50 (2–5), ₹100 (5–15) | 0–200: 3.00, 201–400: 4.50, 401–800: 6.50, 801–1200: 7.00, >1200: 8.00 | Verified. Plus 8% + 5% surcharges, about 16–18% PPAC, 5% tax |
| MSEDCL (FY 2026-27) | ₹130 (1-phase), ₹435 (3-phase) | 1–100: 5.56, 101–300: 12.40, 301–500: 16.64, >500: 19.13 (wheeling included) | Verified. Plus FAC and duty |
| BESCOM | ₹145–175/kW | flat 5.80 | News reports |
| TNPDCL (bi-monthly) | – | 1–200 free (if ≤500 per 2 months), then 4.70 / 6.30 ... | Medium |
| UPPCL LMV-1 urban | ₹110/kW | 0–150: 5.50, 151–300: 6.00, >300: 6.50 | Verified. Plus about 5% duty |

Free-unit schemes matter a lot:

- **Delhi:**
  - Up to 200 units a month: the bill is zero.
  - 201–400 units: 50% subsidy, capped at ₹800.
  - Above 400 units: no subsidy.
- **Karnataka Gruha Jyothi:** free up to the previous year's average + about 10%, capped at 200 units.
- **Tamil Nadu:** first 100–200 units free (per 2 months).

Compute savings as the bill with the scheme applied, before and after solar. Never as units × average rate.

### CO₂

- Use 0.71 kg/kWh (CEA CO2 Baseline v21.0, FY 2024-25). The scheme itself uses about 0.72.
- Trees: about 21 kg CO₂ per tree per year. State this assumption in the UI.

### Bill formats

- Common fields:
  - consumer number (CA No. / Consumer No. / RR No. / Account No.)
  - sanctioned load (kW)
  - tariff category
  - meter readings and billing period
  - units consumed
  - fixed and energy charges, surcharges, subsidy, net payable
- Consumption history:
  - **MSEDCL:** 12-month bar chart.
  - **Delhi BSES and TPDDL:** last 6 bills.
  - BESCOM, TNPDCL, UPPCL: unknown, so allow manual entry.
- Labels can be in Marathi or Hindi. Textract does not support Devanagari, so use a Bedrock vision model.
- Sample bills:
  - [MSEDCL 2026 format PDF](https://www.mahadiscom.in/wp-content/uploads/2026/09/lt-2026-for-web.pdf)
  - [TPDDL handbook FY26, page 9](https://tatapower-ddl.com/Editor_UploadedDocuments/Content/Customer_Handbook_FY26.pdf)
  - [BSES Know Your Bill JPEG](https://www.bsesdelhi.com/documents/73527/75023/Know+Your+Bill.jpg/aa6e0ae0-56d4-536b-ad56-3a97c7f07d52?t=1522934127978)

## 3. AWS findings

- **Bedrock in ap-south-1** (tested 2026-10-09):
  - `in.anthropic.claude-haiku-4-5-20251001-v1:0` works.
  - `global.anthropic.claude-haiku-5-5` is denied for this account.
  - The Haiku 4.5 model card says retirement "no sooner than Oct 16 2026", so keep the model ID in an env var with `in.anthropic.claude-sonnet-5` as the fallback.
- **Haiku 4.5:**
  - Price is about $1 / $5 per 1M tokens, so about $0.005–0.01 per bill read.
  - The `in.` profile does not support structured outputs, so use forced tool use for JSON.
- **Textract:** no Hindi or Devanagari, and it would still need an LLM afterwards. Skip it.
- **Free tier since Jul 2025:** new accounts get credits (up to $200) instead of the old 12-month offers.
  - Always free: Lambda 1M requests, DynamoDB 25 GB, CloudFront 1 TB.
- **API Gateway HTTP API** has a hard 30 s timeout. Use Lambda Function URLs for slow calls.
- **Strands Agents SDK** (Python v1.59): tools are plain functions with `@tool`. Always pass `region_name`. Keep chat history in DynamoDB, not in the global agent object.
- **AgentCore** is overkill for this project.
- **Polly:** Kajal (neural, hi-IN, bilingual) costs $16 per 1M characters.

### Community notes (dev.to)

- Varun Sharma, "Streaming Bedrock Tokens with AWS Lambda Function URLs" — https://dev.to/sharmavarun/solving-aws-reposts-1-genai-headache-real-time-token-streaming-with-amazon-bedrock-aws-lambda-37kh
- Davide De Sio, "Deploy your first AI agent with Strands Agents SDK" — https://dev.to/aws-builders/deploy-your-first-ai-agent-with-strands-agents-sdk-j85
- Nwosa Emeka Afamefuna, "Deploying a Next.js SSR App to AWS Amplify (the stuff nobody tells you)" — https://dev.to/nwosaemeka/deploying-a-nextjs-ssr-app-to-aws-amplify-the-stuff-nobody-tells-you-4gei
- Taranpreet Kaur, "Why an LLM Alone Cannot Do Invoice Extraction Yet" — https://dev.to/taranpreet_kaur_4b538d878/why-an-llm-alone-cannot-do-invoice-extraction-yet-1oa5 (LLM reads the bill, code checks the numbers, user confirms)
