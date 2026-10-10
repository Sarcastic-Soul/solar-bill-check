# Builder Center post: Solar Bill Check

How to post: copy each field below into the Builder Center editor. In the body, every `>>> IMAGE` line marks where an image goes: delete the two `>>>` lines, upload that file in the same spot and paste the caption under it.

## Title

Is rooftop solar worth it for my home? Answering it from one photo of an electricity bill, on AWS

## Description

I built Solar Bill Check for Environmental Hacks: snap your electricity bill and get an honest rooftop solar plan in 10 seconds, with the PM Surya Ghar subsidy, payback, loan EMI and how to apply. Built on Amazon Bedrock, AWS Lambda, Strands Agents and Amazon Polly, all in the Mumbai region.

Shorter version, if the field has a limit:

Snap your electricity bill, get an honest rooftop solar plan: subsidy, payback, EMI and how to apply. Built on Amazon Bedrock, Lambda and Strands Agents.

## Cover image

Upload `docs/blog/cover.png` (1200 x 675, no text, 45 KB).

## Tags

Pick the ones the editor offers, in this order:

1. Amazon Bedrock
2. AWS Lambda
3. Generative AI
4. Sustainability
5. Strands Agents
6. Amazon DynamoDB
7. Amazon Polly
8. AWS Amplify
9. Serverless
10. Hackathon

If the editor lets you pick a space, post it in the WeMakeDevs space (https://bit.ly/wmd-space). Then put the post link in the hackathon submission form, because the AirPods prize needs it.

## Images

All images are in `docs/blog/`. Each one is under 2 MB.

| File | Where it goes |
|---|---|
| `cover.png` | Cover image field (not in the body) |
| `plan-delhi.png` | IMAGE 1, end of "What Solar Bill Check does" |
| `architecture.png` | IMAGE 2, top of "How it's built on AWS" |
| `check-disagree.png` | IMAGE 3, end of "Two models, and the user settles disagreements" |
| `chat-hinglish.png` | IMAGE 4, end of "A chat assistant that can't make up numbers" |
| `plan-hindi.png` | IMAGE 5, end of "Hindi from the start" |

## Body

Paste everything below this line.

---

*Built for Environmental Hacks (WeMakeDevs × AWS Builder Center), Waste and Energy track.*
*Live app: https://main.d2y09rdd9synq1.amplifyapp.com · Code: https://github.com/Sarcastic-Soul/solar-bill-check · Demo video: https://youtu.be/biS2BCbBY50*

## The money is there. The answer isn't.

India's PM Surya Ghar scheme pays households up to ₹78,000 to put solar panels on their roof. Loans run at about 6%, with no collateral. Net metering is free in most states. The target is 1 crore homes by March 2027, and with six months to go, about half of them have signed up.

So what stops the other half? Most of the time it is the very first question: **is solar actually worth it for my house?**

Answering that honestly is harder than it looks. You need your real monthly usage, your electricity company's slab tariff (every state is different, and some give free units), how much sun your roof gets, the subsidy slabs, and the loan maths. The government portal doesn't answer any of it before you register. Vendors do answer it, but they are selling panels.

I wanted something a family could use in under a minute, in Hindi or English, without trusting a salesperson.

## What Solar Bill Check does

You take a photo of your electricity bill. About 10 seconds later you get:

- **The right system size** for your usage, capped by your sanctioned load.
- **Cost, subsidy and what you actually pay.** For a sample Delhi home: a 2.5 kW system costs about ₹1.6 lakh, the subsidy is ₹69,000, so you pay ₹93,500.
- **Payback and 25-year savings**, worked out against your own electricity company's slab tariff and the real sunlight data for your pincode. That Delhi home pays back in 5.7 years.
- **Loan EMI next to your monthly saving**, so you can see whether the loan pays for itself (₹1,624 EMI against ₹1,367 saved a month).
- **A verdict that can say no.** If free units already keep your bill near zero, the app tells you solar won't save you much right now.
- **The paperwork, made clear.** The app can't apply for you, because the portal needs your Aadhaar OTP, and it should. Instead it checks the things that get applications rejected (like the name on the bill not matching your bank account), fills in an application sheet you can copy, and walks you through the 7 real steps.
- **A chat assistant** that answers follow-up questions in English, Hindi or Hinglish using your own numbers, and a **Listen** button that reads the plan aloud.

>>> IMAGE 1: upload `docs/blog/plan-delhi.png`
>>> Caption: The plan for a Delhi home: 2.5 kW, ₹93,500 after subsidy, pays back in 5.7 years.

## How it's built on AWS

>>> IMAGE 2: upload `docs/blog/architecture.png`
>>> Caption: Everything runs on AWS in the Mumbai region.

Everything runs in the Mumbai region (ap-south-1). Electricity bills carry a name, address and consumer number, so I wanted the data to stay in India.

| Part | AWS service |
|---|---|
| Website | AWS Amplify Hosting (static React build) |
| API | One AWS Lambda function (Python 3.14, arm64) behind a Function URL, deployed with AWS SAM |
| Bill upload | Amazon S3 presigned POST with a size limit; the image is deleted right after it is read |
| Reading the bill | Amazon Bedrock: Kimi K2.5 and Mistral Large 3, called in parallel |
| Chat assistant | Strands Agents SDK, with Kimi K2.5 on Bedrock |
| Read aloud | Amazon Polly (Kajal neural voice, Hindi and Indian English) |
| Shareable plans, chat history | Amazon DynamoDB, with TTL so chats expire on their own |

The whole stack is one SAM template. The upload never passes through Lambda: the browser asks for a presigned POST, sends the image straight to S3, then calls `/extract` with the key. Lambda reads the image, deletes it in a `finally` block, and only then talks to Bedrock. A 1-day lifecycle rule on the bucket is the backup in case a delete ever fails.

### Two models, and the user settles disagreements

A bill-reading app that guesses wrong is worse than no app, because a wrong unit count means a wrong system size and a wrong payback. So every bill is read by two different models at the same time:

```python
ex = cf.ThreadPoolExecutor(max_workers=len(specs))
futs = {ex.submit(call, s, blocks, read_timeout=int(budget), deadline=deadline): i
        for i, s in enumerate(specs)}
for fut in cf.as_completed(futs, timeout=budget):
    ...
```

Then the answers are merged field by field. Where the two models agree, the value is trusted. Where they disagree on a field that changes the result (units, bill amount, sanctioned load, tariff category, and so on), the field is marked "check" and both values are shown to the user, who picks the one that matches their paper bill.

```python
elif k in KEY_FIELDS or k == "is_electricity_bill":
    fields[k], confidence[k] = va, "check"
    disagreements.append({"field": k, "kind": "different", "candidates": [va, vb]})
```

Running them in parallel means the second opinion costs almost no extra time. Code checks run after the merge too: a bill amount that doesn't fit the units, a usage month in the future, or a billing period that doesn't match the number of days also gets flagged.

>>> IMAGE 3: upload `docs/blog/check-disagree.png`
>>> Caption: A blurry phone photo of a Marathi bill. The two models disagreed on the consumer number, the units and the amount, so the user picks the right value for each.

### Picking the models by testing, not by habit

Before writing the app I built a test set of 24 bills: 3 real sample bills from electricity company handbooks (personal details masked), 15 realistic mock bills in 9 Indian languages, and 6 phone-photo versions with blur, angle and glare. Then I ran every vision model I had access to on Bedrock against it, 18 in total, and scored each field.

| Model | Score /100 | Phone photos | Median time | Cost per bill |
|---|---|---|---|---|
| Kimi K3 | 94.4 | 97.4 | 44.3 s | $0.066 |
| Llama 4 Maverick | 94.0 | 85.6 | 3.9 s | $0.002 |
| **Kimi K2.5** | **92.0** | 84.5 | 3.0 s | $0.005 |
| **Mistral Large 3** | **88.3** | 80.9 | 2.7 s | $0.003 |
| Qwen3 VL 235B | 84.5 | 77.9 | 8.4 s | $0.004 |
| Nova Pro | 68.4 | 59.4 | 4.1 s | $0.005 |
| Gemma 3 27B | 66.1 | 58.4 | 6.0 s | $0.001 |

Two models scored a little higher than Kimi K2.5, but Kimi K3 takes 44 seconds per bill, and Llama 4 Maverick is only available through a US inference profile, which would send personal data out of India. Kimi K2.5 plus Mistral Large 3 was the most accurate pair that is fast and stays in ap-south-1. The full benchmark run cost about US$2.70. The harness and all results are in the repo's `eval/` folder, so the choice can be checked and re-run when new models arrive.

### A chat assistant that can't make up numbers

Follow-up questions are where people decide: "What if I put 3 kW instead?", "Loan EMI kitna hoga?" A plain chatbot will happily invent a number. I built the assistant with the **Strands Agents SDK** and gave it four tools that do the real maths using the same plan engine as the main screen:

```python
@tool
def what_if(plan_id: str, kw: float) -> dict:
    """Re-run the user's plan at a different system size and return cost, subsidy,
    savings, payback and EMI for that size, next to the original recommendation."""
```

The others are `get_plan` (the saved plan), `loan_emi` and `scheme_facts` (fixed, sourced rules about the subsidy and loans). The user's plan is loaded into the prompt for each turn, so most answers need no extra tool call and come back in about a second. If a reply contains numbers but no plan was loaded and no tool was called, the agent is asked again to use a tool. The assistant replies in Hinglish when you write in Hinglish, and chat history lives in DynamoDB with a 7-day TTL.

>>> IMAGE 4: upload `docs/blog/chat-hinglish.png` (if that is flagged too, try `docs/blog/chat-loan.png`)
>>> Caption: Asked in Hinglish, the assistant answers in Hinglish with the roof space this plan needs.

The chat route imports Strands only when it is called, so the other routes stay fast on a cold start. Everything still fits in a single Lambda function.

### The plan engine: plain Python, real data

The numbers come from a plain Python engine with 142 tests, not from a model:

- **Tariffs:** exact slab tariffs for Delhi, Maharashtra and Uttar Pradesh (including Delhi's free-unit subsidy), good estimates for Karnataka and Tamil Nadu, and a rough estimate from the bill's own amount everywhere else. The plan says which level it used.
- **Sunlight:** PVGIS data for the pincode's location (from the European Commission's Joint Research Centre).
- **Subsidy:** the official slabs (₹30,000 per kW up to 2 kW, ₹18,000 for the third kW, ₹78,000 max), with 10% extra in special-category states.

Keeping the maths out of the model means the same bill always gives the same answer, and the honest "solar isn't worth it yet" verdict comes from a rule, not a mood.

### Hindi from the start

The app is in English and Hindi (the plan page switches with one tap), and bills in any Indian script are read. Amazon Polly's Kajal voice reads the plan summary in Hindi or Indian English, which helps people who would rather listen than read numbers.

>>> IMAGE 5: upload `docs/blog/plan-hindi.png`
>>> Caption: The same plan in Hindi, on a phone.

## Privacy

There is no login. The bill image is deleted as soon as it is read. Names are never stored, consumer numbers are masked, and no personal data goes into logs. Plans are saved under a random ID so they can be shared with family. Chats expire after 7 days.

## Cost

The app runs inside the AWS free tier, apart from Bedrock. A bill read with two models costs under one US cent, and a chat reply costs a fraction of that.

## What I'd do next

- Add exact tariffs for more of India's roughly 70 electricity companies. Each one is a data file, not new code.
- Let installers see a plan the family chooses to share, so quotes start from real numbers.
- Track the application status alongside the 7-step guide.

## AI tools used

I used Claude Code for planning, research, code, tests and docs. Inside the product, Amazon Bedrock models (Kimi K2.5 and Mistral Large 3) read the bills and power the chat.

Try it with your own bill: **https://main.d2y09rdd9synq1.amplifyapp.com**
