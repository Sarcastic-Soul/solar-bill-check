# Backend (AWS SAM)

One Python 3.14 arm64 Lambda (`ApiFunction`, including the chat assistant) behind a Lambda Function URL. No API Gateway, no NAT,
nothing provisioned, so the idle cost is about zero. Everything runs in **ap-south-1**.

| Resource | What it is |
|---|---|
| `ApiFunction` | Powertools `LambdaFunctionUrlResolver`, 1024 MB, 60 s. Handler `api.handler.lambda_handler` |
| `BillsBucket` | Bill uploads. Public access blocked, SSE-S3, TLS only, CORS for browser POST/PUT, objects expire after 1 day. The API deletes each bill right after reading it |
| `PlansTable` | DynamoDB on-demand, key `planId`, TTL `expiresAt` (30 days). Stores the plan and the inputs with the consumer number masked and no name |
| `ChatsTable` | DynamoDB on-demand, key `sessionId` + `ts` (number, epoch ms), TTL `expiresAt` (7 days). One item per chat turn |

Dev stack: `solar-bill-check-dev`. API URL:
`https://fcz6jcdep5ykiv5st7aq7az3mq0jkjfn.lambda-url.ap-south-1.on.aws/`

## Layout

```
backend/
  template.yaml        SAM template
  samconfig.toml       deploy settings (stack name, region, capabilities)
  pyproject.toml       deps; src/requirements.txt is exported from it for `sam build`
  src/api/             handler.py (routes), upload.py, extract.py, media.py, fields.py,
                       bedrock_client.py, plan.py, speak.py, extract_prompt.py, errors.py, aws.py,
                       chat.py, chat_tools.py, chat_prompt.py (assistant)
  src/engine/          calculation engine (no LLM), shipped in the same zip
  tests/               pytest, no network
  scripts/e2e.sh       curl end-to-end check against a deployed stack
```

`CodeUri` is `src/`, so `api/` and `engine/` are both in the zip.

## API

All bodies are JSON. Errors look like `{"error": "CODE", "message": "plain English"}`.
CORS is set only on the Function URL and the S3 bucket (`AllowedOrigins` parameter: the Amplify site plus localhost ports 5173 and 4173).

| Route | Body | Returns |
|---|---|---|
| `POST /upload-url` | `{contentType}` (or `{filename}`), optional `size` | `{uploadUrl, method: "POST", fields, key, maxBytes, expiresIn}` |
| `POST /extract` | `{key}` | `{fields, confidence, disagreements, warnings, models_used, input, latency_ms}` |
| `POST /plan` | `{fields, pincode, answers: {owns_roof, name_matches_bank, previous_subsidy}, overrides: {roof_area_m2, cost_per_kw, rwa_houses, system_kw, shading_loss_pct}, monthly_units?}` | `{planId, plan, expiresAt, lookups, latency_ms}` |
| `GET /plan/{id}` | | `{planId, createdAt, expiresAt, plan, inputs}` (inputs are masked) |
| `POST /speak` | `{text, lang: "hi" \| "en"}` | `{audio (base64 MP3), contentType: "audio/mpeg", voice, languageCode, chars, truncated}` |
| `POST /chat` | `{sessionId?, planId?, message, lang?}` | `{reply, sessionId}` |
| `GET /health` | | `{ok: true}` |

### Upload (presigned POST)

`/upload-url` returns a presigned **POST**, so S3 itself rejects files over 8 MB and files whose
`Content-Type` doesn't match. Allowed: `image/jpeg`, `image/png`, `image/webp`, `application/pdf`
(HEIC is refused with `HEIC_NOT_SUPPORTED`). From the browser:

```js
const up = await post("/upload-url", { contentType: file.type, size: file.size });
const form = new FormData();
Object.entries(up.fields).forEach(([k, v]) => form.append(k, v));
form.append("file", file); // the file must be the last field
await fetch(up.uploadUrl, { method: "POST", body: form }); // 204 on success
const result = await post("/extract", { key: up.key });
```

### Extraction

- The file type is read from the bytes. Images are rotated by EXIF and cut to 2000 px on the long
  side. PDFs: pages 1 and 2 are rendered with pypdfium2. Password-protected PDFs get `PDF_PASSWORD_PROTECTED`.
- The models in `EXTRACT_MODELS` run in parallel. Default: `moonshotai.kimi-k2.5` (json_text) and
  `mistral.mistral-large-3-675b-instruct` (tool), both in ap-south-1. Change it with the
  `ExtractModels` stack parameter, a JSON list of `{id, region, mode}` (mode `tool`, `tool_auto` or
  `json_text`; optional `max_tokens`, `temperature`). The IAM policy allows the Moonshot and Mistral
  models plus `in.*` inference profiles; other providers need a policy change.
- Confidence per field:
  - `high`: the models agree.
  - `medium`: only one model answered (or one returned null, or a non-key field differs).
  - `check`: the models disagree on a key field, or the value failed a sanity check.
  - `missing`: no value found.
  
  Key fields are `units_billed_kwh`, `consumption_history`, `sanctioned_load_kw`, `bill_amount_rs`,
  `discom`, `state`, `is_residential` and `billing_cycle`. When the models disagree, `fields` keeps
  the first model's value, and `disagreements` lists both candidates.
- Sanity checks (`warnings`, each `{code, field, level: info|check|error, message}`):
  - units between 1 and 20,000
  - load between 0.1 and 100 kW
  - history values in range and no future months
  - units close to the history median
  - Rs/unit between 1 and 30 (when units ≥ 30)
  - billing days match the cycle
  - info flags for estimated readings, existing solar and non-residential connections
- Privacy:
  - The S3 object is deleted in a `finally` right after it is read.
  - Logs only hold model ids, timings, token usage, confidence counts and warning codes.
  - The full consumer number goes back only in the `/extract` response. Stored plans keep the last 4 digits.

### Chat

`POST /chat` runs a [Strands Agents](https://strandsagents.com) agent (`strands-agents` 1.59.0, our own
`@tool`s, no `strands-agents-tools`) on Bedrock in ap-south-1. Strands is imported only on this
route, so the other routes keep their cold start.

- Model: `ChatModelId` stack parameter (env `CHAT_MODEL_ID`), default `moonshotai.kimi-k2.5`;
  `ChatModelRegion` defaults to ap-south-1. Kimi ignores `toolChoice`, but Strands uses auto tool
  choice and Kimi calls the tools reliably. In our test it was the best of the three at answering
  in the user's script (Devanagari, Hinglish, Marathi) and in plain text. Mistral Large 3 is a good
  fallback (as fast, but it mixed scripts and used markdown); Qwen3 VL was slower. The IAM policy
  allows Mistral, Moonshot and Qwen models, so switching needs no policy change.
- First call: send no `sessionId`; keep the one returned and send it back on every later call. Send
  `planId` (from `/plan`) on the first call; later calls reuse the session's plan if it is left out.
  `lang` is the app language (`en`, `hi`, `mr`, ...), used only when the message's language is unclear.
  The reply comes in the language and script of the message (Hindi, Hinglish, English, others).
- The reply is plain text (short sentences or `- ` bullets, no markdown).
- Tools: `get_plan(plan_id)` (saved plan summary), `what_if(plan_id, kw)` (engine re-run at another size
  from the stored inputs plus the saved location and solar yield, no network), `loan_emi(amount,
  rate_pct, years)`, `scheme_facts(topic)` (fixed facts: subsidy, special_category, rwa, dcr, steps,
  loan, net_metering, red_flags, deadline, eligibility, sizing). At most 8 tool calls per message.
- Limits: message up to 1,000 characters (`MESSAGE_TOO_LONG`, 400), 30 turns per session
  (`SESSION_LIMIT`, 429), the last 10 turns are sent to the model. Model failures give
  `CHAT_UNAVAILABLE` (503). Other errors: `EMPTY_MESSAGE`, `BAD_SESSION`, `BAD_PLAN_ID`, `BAD_REQUEST`.
- Privacy: runs of 9+ digits (Aadhaar, bank account, card numbers) are replaced with
  `[number removed]` before the model sees the message and before it is stored. Logs hold only the
  model id, sizes, timings, token counts and tool names, never message text.

```bash
curl -s -X POST $API/chat -H 'content-type: application/json' \
  -d '{"planId":"<planId>","message":"Loan EMI kitna hoga?","lang":"hi"}'
```

## Run tests

```bash
cd backend
uv sync
uv run pytest            # engine, field checks, chat tools/validation (Bedrock stubbed), no network
```

## Build and deploy

`sam build` needs `python3.14` on `PATH` (it cross-downloads the arm64 wheels, so no Docker is needed):

```bash
cd backend
uv tool install aws-sam-cli                     # once; SAM CLI 1.167.0
uv python install 3.14                          # once
export PATH="$(dirname "$(uv python find --system 3.14)"):$PATH"   # --system: not the project .venv (no pip)
export SAM_CLI_TELEMETRY=0

# after changing pyproject.toml deps:
uv export --no-hashes --no-dev --no-emit-project -o src/requirements.txt

sam build
sam deploy               # uses samconfig.toml: stack solar-bill-check-dev, ap-south-1, CAPABILITY_IAM, --resolve-s3
```

First-time equivalent without samconfig:

```bash
sam deploy --region ap-south-1 --stack-name solar-bill-check-dev --capabilities CAPABILITY_IAM \
  --resolve-s3 --no-confirm-changeset
```

Parameters (`--parameter-overrides`):
- `AllowedOrigins`: comma-separated browser origins. Defaults to the Amplify site and local dev.
- `ExtractModels`
- `ChatModelId`, `ChatModelRegion`
- `PlanTtlDays`
- `LogRetentionDays`

Example:

```bash
sam deploy --parameter-overrides AllowedOrigins=https://main.xxxx.amplifyapp.com,http://localhost:5173
```

## End-to-end check

```bash
backend/scripts/e2e.sh eval/bills/delhi-brpl-hindi-clean-01/bill.png 110075
backend/scripts/e2e.sh eval/bills/msedcl-marathi-devanagari-01-photo/bill.jpg 411001
```

It uploads the bill, extracts it, checks the S3 object is gone, builds and fetches a plan, and calls
`/speak` in English and Hindi. Needs `aws`, `curl` and `jq`.

Single calls:

```bash
API=https://fcz6jcdep5ykiv5st7aq7az3mq0jkjfn.lambda-url.ap-south-1.on.aws
curl -s $API/health
curl -s -X POST $API/upload-url -H 'content-type: application/json' -d '{"contentType":"image/png"}'
curl -s $API/plan/<planId>
curl -s -X POST $API/speak -H 'content-type: application/json' -d '{"text":"नमस्ते","lang":"hi"}' | jq -r .audio | base64 -d > hi.mp3
```

Logs: `sam logs --stack-name solar-bill-check-dev --name ApiFunction --region ap-south-1 --tail`
