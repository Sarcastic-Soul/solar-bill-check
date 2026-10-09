# Demo video script (target 2:45, hard limit 3:00)

Recorded as screen captures of the live app on a phone-sized window and a desktop window, plus the AWS console. Voiceover is about 130 words a minute.

| Time | On screen | Voiceover |
|---|---|---|
| 0:00–0:15 | A paper electricity bill on a table. Title card: "Is solar worth it for my home?" | India will pay up to ₹78,000 to put solar on your roof. Half of the 1 crore homes the scheme is aiming for still haven't signed up. The first question stops most families: is it actually worth it for my house? |
| 0:15–0:30 | Home screen on phone. Tap "Snap your bill", pick the Delhi Hindi bill. | Solar Bill Check answers that from one photo of your electricity bill. Any state, any language. |
| 0:30–0:50 | Reading screen, then the Check screen. Zoom on a field where the two models disagree; tap the right value. | Two AI models on Amazon Bedrock read the bill at the same time. Where they agree, we trust the number. Where they don't, like this amount, you pick the right one from your paper bill. No silent guessing. |
| 0:50–1:25 | Plan screen. Scroll slowly: verdict, 5.7 years, the cost strip, the monthly chart, the EMI line. | For this Delhi home: a 2.5 kW system. ₹1.6 lakh, minus ₹69,000 subsidy, so ₹93,500. It wipes out the bill and pays for itself in under six years. The maths uses this DISCOM's real slab tariff, Delhi's free units, and sunlight data for this pincode. And if your bill is already near zero, it will tell you solar isn't worth it yet. |
| 1:25–1:45 | "Before you apply" checklist, application sheet with Copy, the 7-step tracker. | We can't apply for you, because the portal needs your Aadhaar OTP. So we fix what gets applications rejected, like the name on the bill not matching your bank account. Then we hand you a filled-in sheet and the seven real steps. |
| 1:45–2:05 | Chat: type "Loan EMI kitna hoga?" then "What if I install 3 kW?". Tap "Listen" (Hindi audio plays). | Questions? Ask in Hindi, English or Hinglish. The assistant is built with Strands Agents on Bedrock and uses your own plan's numbers. Polly reads the plan aloud. |
| 2:05–2:35 | Architecture diagram, then quick cuts: Lambda function, S3 bucket (empty), DynamoDB plans table, Bedrock model access page, Amplify app. | It runs on AWS in Mumbai, so bill data stays in India. Amplify hosts the site. Lambda runs the API, deployed with SAM. S3 takes the upload and the photo is deleted right after reading. DynamoDB keeps shareable plans. Bedrock reads the bills and powers the chat. |
| 2:35–2:50 | Benchmark table from eval/results. | We didn't just pick a model. We tested 18 Bedrock models on 24 bills in 9 languages and picked the most accurate one that is fast and stays in India. |
| 2:50–3:00 | Home screen with the URL. | Solar Bill Check. One photo, one honest answer. |

## Recording checklist

- Use the live Amplify URL, not localhost.
- Clear the browser first so the language starts in English; switch to Hindi once on the plan screen.
- Prepare one Bedrock disagreement: use the MSEDCL phone-photo bill if the Delhi bill reads perfectly.
- AWS console in ap-south-1 and already logged in; hide the account ID.
- Upload to YouTube as unlisted, and check the link in a signed-out browser.
