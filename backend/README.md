# Backend (AWS SAM)

One Python 3.14 arm64 Lambda (`ApiFunction`) behind a Lambda Function URL. No API Gateway, no NAT,
nothing provisioned, so the idle cost is about zero. Everything runs in **ap-south-1**.

| Resource | What it is |
|---|---|
| `ApiFunction` | Powertools `LambdaFunctionUrlResolver`, 1024 MB, 60 s. Handler `api.handler.lambda_handler` |
| `BillsBucket` | Bill uploads. Public access blocked, SSE-S3, TLS only, CORS for browser POST/PUT, objects expire after 1 day. The API deletes each bill right after reading it |
| `PlansTable` | DynamoDB on-demand, key `planId`, TTL `expiresAt` (30 days). Stores the plan and the inputs with the consumer number masked and no name |
| `ChatsTable` | DynamoDB on-demand, key `sessionId` + `ts` (number, epoch ms), TTL `expiresAt`. For the chat function (not built yet; a commented-out stub is in `template.yaml`) |

Dev stack: `solar-bill-check-dev`. API URL:
`https://fcz6jcdep5ykiv5st7aq7az3mq0jkjfn.lambda-url.ap-south-1.on.aws/`

## Layout

```
backend/
  template.yaml        SAM template
  samconfig.toml       deploy settings (stack name, region, capabilities)
  pyproject.toml       deps; src/requirements.txt is exported from it for `sam build`
  src/api/             handler.py (routes), upload.py, extract.py, media.py, fields.py,
                       bedrock_client.py, plan.py, speak.py, extract_prompt.py, errors.py, aws.py
  src/engine/          calculation engine (no LLM), shipped in the same zip
  tests/               pytest, no network
  scripts/e2e.sh       curl end-to-end check against a deployed stack
```

`CodeUri` is `src/`, so `api/` and `engine/` are both in the zip.

## API

All bodies are JSON. Errors look like `{"error": "CODE", "message": "plain English"}`.
CORS is set only on the Function URL (`AllowedOrigin` parameter, default `*`).

| Route | Body | Returns |
|---|---|---|
| `POST /upload-url` | `{contentType}` (or `{filename}`), optional `size` | `{uploadUrl, method: "POST", fields, key, maxBytes, expiresIn}` |
| `POST /extract` | `{key}` | `{fields, confidence, disagreements, warnings, models_used, input, latency_ms}` |
| `POST /plan` | `{fields, pincode, answers: {owns_roof, name_matches_bank, previous_subsidy}, overrides: {roof_area_m2, cost_per_kw, rwa_houses, system_kw, shading_loss_pct}, monthly_units?}` | `{planId, plan, expiresAt, lookups, latency_ms}` |
| `GET /plan/{id}` | | `{planId, createdAt, expiresAt, plan, inputs}` (inputs are masked) |
| `POST /speak` | `{text, lang: "hi" \| "en"}` | `{audio (base64 MP3), contentType: "audio/mpeg", voice, languageCode, chars, truncated}` |
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

## Run tests

```bash
cd backend
uv sync
uv run pytest            # engine + field agreement / sanity checks, no network
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
- `AllowedOrigin`: set to the Amplify domain later.
- `ExtractModels`
- `PlanTtlDays`
- `LogRetentionDays`

Example:

```bash
sam deploy --parameter-overrides AllowedOrigin=https://main.xxxx.amplifyapp.com
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
