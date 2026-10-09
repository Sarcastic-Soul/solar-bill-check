# Solar Bill Check: writeup (draft)

**Track:** Waste and Energy · **Live app:** https://main.d2y09rdd9synq1.amplifyapp.com · **Repo:** https://github.com/Sarcastic-Soul/solar-bill-check

## The problem

India pays households to put solar on their roofs. PM Surya Ghar gives up to ₹78,000 per home, loans at about 6%, and free net metering in most states. The target is 1 crore homes by March 2027. With six months left, about 50 lakh are done.

The money is there. What stops most families is the first question: *is it worth it for my house?* Answering it means knowing your real usage, your DISCOM's slab tariff and free-unit rules, how much sun your roof gets, the subsidy slabs, and the loan maths. Vendors answer it for you, and they are selling. The government portal answers none of it before you sign up.

## What we built

Take a photo of your electricity bill. In about 10 seconds you get an honest answer:

- **The right system size**, capped by your sanctioned load and the 3 kW subsidy sweet spot.
- **Cost, subsidy and what you actually pay**, using the official PM Surya Ghar slabs (and the 10% extra in special-category states).
- **Payback in years and savings over 25 years**, worked out against your own DISCOM's slab tariff and free-unit scheme, with real sunlight data for your pincode (PVGIS).
- **A verdict that can say no.** If your bill is already near zero because of free units, the app tells you solar won't save you much right now.
- **Loan EMI next to your monthly saving**, so you can see if the loan pays for itself.
- **The paperwork, made clear.** We can't apply for you (the portal needs your Aadhaar OTP, and it should). Instead the app checks the things that get applications rejected, like the name on the bill not matching your bank account. It also fills in an application sheet you can copy, and walks you through the 7 real steps from registration to subsidy.
- **A chat assistant** that answers follow-up questions in English, Hindi or Hinglish, using your own plan's numbers. It can also answer "what if I install 3 kW?"
- **Listen** to your plan read aloud in Hindi or English.

It works for bills in any Indian language. Delhi, Maharashtra and UP tariffs are modelled exactly; Karnataka and Tamil Nadu are good estimates; every other DISCOM gets a rough estimate from the bill's own amount, and the app says which level was used.

## How we built it, and where AWS fits

![Architecture](architecture.png)

| Part | AWS service | What it does |
|---|---|---|
| Bill reading | **Amazon Bedrock** (Kimi K2.5 + Mistral Large 3, ap-south-1) | Two models read every bill in parallel. Fields where they agree are trusted. Where they disagree, the user picks the right value. |
| API | **AWS Lambda** (Python 3.14, arm64) with Function URLs, deployed with **AWS SAM** | Upload, extract, plan, saved plans, speech and chat |
| Bill uploads | **Amazon S3** | Presigned upload, size-limited; the image is deleted right after it is read |
| Plans and chat history | **Amazon DynamoDB** | Shareable plan links; chat sessions expire on their own |
| Chat assistant | **Strands Agents SDK** on Bedrock | Tools that read the user's plan, re-run the maths for another size, work out EMI and quote scheme rules |
| Read aloud | **Amazon Polly** (Kajal, neural, hi-IN and en-IN) | Plan summary as audio |
| Website | **AWS Amplify Hosting** | Static React build |

Everything runs in the Mumbai region (ap-south-1), so bill data stays in India.

**We picked the bill-reading models by testing, not by habit.** We built a test set of 24 bills: 3 official DISCOM samples with personal details masked, 15 realistic mock bills in 9 Indian languages, and 6 phone-photo versions. Then we ran 18 Bedrock models against it and scored each field. Kimi K2.5 scored 92/100 at about 3 seconds and $0.005 per bill. Two models scored slightly higher, but one runs only in the US (bills carry personal data) and the other takes 44 seconds. The full results and the harness are in [`eval/`](../eval).

**Privacy.** Bills carry a name, address and consumer number, which is personal data under India's DPDP Act. The image is deleted as soon as it is read. Names are never stored, consumer numbers are masked, and no personal data goes to logs. There is no login.

## What's honest about the limits

- We don't apply on the user's behalf, and never touch Aadhaar or OTPs.
- About 70 DISCOMs exist; 5 have exact tariffs today. More can be added as data.
- Commercial and farm solar (PM-KUSUM) are out of scope.

## AI tools used

- **Claude Code** (Anthropic): planning, research, code, tests and docs.
- **Amazon Bedrock models** inside the product, as listed above.

## Credits

- Official sample bills: MSEDCL and Tata Power-DDL public consumer handbooks, with personal details masked. See [`eval/bills/INDEX.md`](../eval/bills/INDEX.md).
- Sunlight data: PVGIS (European Commission JRC). Pincode lookup: postalpincode.in, OpenStreetMap Nominatim.
- Fonts: Clash Display and Switzer (Fontshare, free licence), Hind (SIL OFL). Icons: Phosphor (MIT).
