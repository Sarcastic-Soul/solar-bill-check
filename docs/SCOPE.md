# Scope, languages, edge cases and the paperwork

Proposed on 2026-10-09. Decisions marked **(decided)** are settled; the rest wait on the model benchmark or on time.

## 1. Who it's for: all of India, with honest accuracy levels

The parts of the maths that are national work everywhere from day one:

- the central subsidy (one national rule, plus 10% more in special-category states)
- solar yield (PVGIS covers the whole country)
- CO₂ (one national grid factor)
- the application steps (one national portal)

The only part that changes by state is **tariffs and free-unit schemes**, and there are about 70 DISCOMs. We can't model all of them in 2 days, so each DISCOM gets an accuracy level, and the result page shows which level was used.

| Level | DISCOMs | How savings are worked out |
|---|---|---|
| **Exact** | Delhi (BRPL, BYPL, TPDDL), MSEDCL, UPPCL | Real slab tariff + fixed charge + free-unit rules from the regulator's order |
| **Good estimate** | BESCOM, TNPDCL, plus any we add Saturday | Slabs from news reports; flagged as estimate |
| **Rough estimate** | Everyone else | Effective rate = bill amount ÷ units, from their own bill. Free units can't be detected, so we ask: "Does your state give free units?" |

This keeps the app honest for all-India use. More DISCOMs can be added later as data, without code changes. **(decided)**

## 2. Languages

There are three separate problems.

**a) Reading bills in any script.**
- Bills print labels in Hindi, Marathi, Tamil, Kannada, Bengali, Gujarati, Telugu, Malayalam, and sometimes local digits (०१२३).
- This is handled by the vision model, not by us. The benchmark tests 9 scripts plus English, so we pick the model with real numbers.
- Code then turns every number into Western digits and checks it.

**b) The app's UI text.**
- The UI is about 150 short strings, stored in locale JSON files.
- English and Hindi get careful wording. Hindi is checked by reading it, because Hindi is what the demo will show.
- Marathi, Tamil, Bengali, Telugu, Kannada, Gujarati and Malayalam are translated once with Bedrock at build time and committed. Each language pack is loaded only when picked, so the app stays fast.
- The language is guessed from the bill's script and the state (Tamil bill, so Tamil UI), and the user can switch.

**c) Chat answers and audio.**
- The assistant replies in whatever language the user writes in, Hinglish included. No Translate service is needed.
- The "Listen" button only shows where Amazon Polly has a voice: Hindi and Indian English for sure. The full list is being checked.
- Where there is no voice, the button is hidden rather than reading Tamil text in a Hindi voice.

Numbers stay in the Indian format everywhere (₹1,23,456, lakh), using `Intl.NumberFormat('en-IN')`.

## 3. Edge cases

**Bill input**

| Case | What we do |
|---|---|
| Blurry, dark, rotated or cut-off photo | Model returns per-field confidence. Low confidence shows a "retake photo" hint plus editable fields. Never a dead end. |
| Not a bill (receipt, water bill, selfie) | `is_electricity_bill=false`, so we show a friendly "this doesn't look like an electricity bill". |
| Multi-page PDF | Send pages 1–2 (history is often on the back page). |
| Password-protected PDF | Clear error: "remove the password or upload a screenshot". |
| Bi-monthly bill (TN, Kerala) | Detected from billing days or the cycle field; units halved per month. |
| Billing period not 30 days | Units normalised to 30 days. |
| Estimated / average reading | Warning: "this month was estimated, check your units". |
| Only one month shown | Use that month for all 12 and say so; offer to enter more months. |
| Zero bill because of free units | Still use the units; this is exactly the "solar may not save you money" case. |
| Already has a solar net meter | "You already have solar". Show how to check it's performing, or how to add capacity (subsidy only up to 3 kW in total). |
| Commercial / agricultural category | No subsidy under this scheme; say so plainly and point to PM-KUSUM for farms. |
| Arrears or late fee on bill | Use the current charges only. |
| Prepaid smart meter (no bill) | Manual entry: monthly units or recharge amount. |
| Numbers that don't add up | Code checks (units × rate ≈ amount, history in a sane range, load 0.5–50 kW). A failed check flags the field and retries once with a stronger model. |

**The household**

| Case | What we do |
|---|---|
| Tenant, not owner | Not eligible by themselves. Show what to tell the landlord, or the RWA route. |
| Apartment, no own roof | RWA / group housing mode: ₹18k/kW for common areas, plus group or virtual net metering where the DISCOM allows it. |
| Sanctioned load lower than the recommended size | Cap the size, and explain load increase (usually an online request to the DISCOM) to unlock the bigger system. |
| Needs more than 10 kW | Cap at 10 kW (auto-approval limit); a bigger system needs a separate DISCOM study. |
| Very low use (under 100 units a month) | 1 kW minimum; likely a "not worth it now" verdict. |
| Small or shaded roof | Optional roof area; size capped at area ÷ 10 m². A shading question cuts expected output. |
| Special-category state | 10% higher subsidy, set automatically from the state. |
| Wrong pincode, or pincode doesn't match the state on the bill | Ask the user to confirm the state. |

**Trust and privacy**

- Bills carry a name, address and consumer number, which is personal data under India's DPDP Act 2023.
- The bill image is deleted right after it is read (S3 lifecycle as a backup).
- The consumer number is masked in stored results.
- Personal data never goes to logs.
- The app has no login, so nothing is tied to an identity.
- The Bedrock `in.` profile keeps processing inside India.
- One clear line on the upload screen says all this.

## 4. The paperwork

There is no API for the government portal, and it blocks bots. It also requires OTP and Aadhaar login, which we must never handle for the user. So we don't apply on their behalf. Instead the app **removes the confusion and prevents rejections**. That is where people actually give up.

**1. Readiness check before applying.** These are the common reasons applications get stuck or rejected, checked from the bill and a few yes/no questions:
- Is the name on the bill the same as on your bank account? The subsidy goes to a bank account that must match the bill exactly. This is the most common problem.
- Is the bill category residential?
- Do you own the roof?
- Have you had a solar subsidy before?
- Is your sanctioned load at least the system size?

Each "no" comes with the fix (name change on the bill, load increase, and so on).

**2. Your application sheet.**
- Everything the portal form asks for, already filled from the bill: state, district, DISCOM, consumer number, recommended kW.
- The user copies it into pmsuryaghar.gov.in in two minutes.

**3. Step tracker** with the 7 real stages, for each one:
- who acts (you / vendor / DISCOM)
- what's needed
- the usual timeline
- what can go wrong

The stages:
1. Register
2. Feasibility (auto-approved up to 10 kW)
3. Choose a vendor
4. Installation
5. Net meter
6. Inspection
7. Bank details and subsidy (about 15–30 days)

**4. Vendor questions** to ask before signing:
- Are the panels DCR (made in India from Indian cells) with a certificate number? Non-DCR panels lose the whole subsidy.
- Is 5-year maintenance included?
- Who handles the net meter?
- Is the price for DC kW?
- What is the payment schedule? Never pay in full before installation.

**5. Loan path.** Jan Samarth link, the about 6% rate, the 10% margin, and the EMI compared with the monthly saving.

**6. Red flags.** Don't install before feasibility approval. Don't pay anyone who claims to be "from the government". The portal is free.

Saturday stretch goal: if the user's state adds its own subsidy (Delhi, UP), show those extra steps.

## 5. Out of scope (said plainly in the writeup)

- Applying on the user's behalf, or any Aadhaar/OTP handling.
- A vendor marketplace or quotes.
- Commercial and agricultural solar (PM-KUSUM is a different scheme).
- Exact tariffs for all ~70 DISCOMs (the "rough estimate" level covers the rest).
