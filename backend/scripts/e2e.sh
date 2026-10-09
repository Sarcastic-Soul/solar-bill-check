#!/usr/bin/env bash
# End-to-end check against a deployed stack, using curl + jq.
#
#   backend/scripts/e2e.sh <bill file> <pincode> [api url]
#   backend/scripts/e2e.sh eval/bills/delhi-brpl-hindi-clean-01/bill.png 110075
#
# Steps: /upload-url -> presigned POST to S3 -> /extract -> check the S3 object is gone ->
# /plan -> GET /plan/{id} -> /speak. Prints trimmed responses and timings.
set -euo pipefail

BILL=${1:?bill file}
PIN=${2:?pincode}
STACK=${STACK:-solar-bill-check-dev}
REGION=${REGION:-ap-south-1}
API=${3:-$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)}
API=${API%/}
BUCKET=${BUCKET:-$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

case "${BILL,,}" in
  *.png) CT=image/png ;; *.jpg|*.jpeg) CT=image/jpeg ;; *.webp) CT=image/webp ;; *.pdf) CT=application/pdf ;;
  *) echo "unknown file type: $BILL" >&2; exit 1 ;;
esac

post() { # path, json body, out file -> prints "<http code> <seconds>"
  curl -sS -o "$3" -w '%{http_code} %{time_total}\n' -X POST "$API$1" -H 'content-type: application/json' -d "$2"
}

echo "== $BILL ($CT) pin $PIN"
read -r code t < <(post /upload-url "{\"contentType\":\"$CT\",\"size\":$(stat -c%s "$BILL")}" "$TMP/up.json")
echo "upload-url: $code ${t}s"
KEY=$(jq -r .key "$TMP/up.json")
URL=$(jq -r .uploadUrl "$TMP/up.json")
FORM=()
while IFS= read -r kv; do FORM+=(-F "$kv"); done < <(jq -r '.fields | to_entries[] | "\(.key)=\(.value)"' "$TMP/up.json")
read -r code t < <(curl -sS -o "$TMP/s3.txt" -w '%{http_code} %{time_total}\n' "${FORM[@]}" -F "file=@$BILL;type=$CT" "$URL")
echo "s3 POST: $code ${t}s  key=$KEY"

read -r code t < <(post /extract "{\"key\":\"$KEY\"}" "$TMP/ex.json")
echo "extract: $code ${t}s"
jq -c '{latency_ms, input, models_used}' "$TMP/ex.json"
jq -c '.fields | {discom, state, units_billed_kwh, bill_amount_rs, sanctioned_load_kw, billing_cycle,
  is_residential, consumer_number, history_months: ((.consumption_history // []) | length)}' "$TMP/ex.json"
jq -c '.confidence' "$TMP/ex.json"
jq -c '{disagreements, warnings: [.warnings[] | "\(.level):\(.code)"]}' "$TMP/ex.json"

if aws s3api head-object --region "$REGION" --bucket "$BUCKET" --key "$KEY" >/dev/null 2>&1; then
  echo "S3 object STILL PRESENT: $KEY"
else
  echo "S3 object deleted after extract: yes"
fi

BODY=$(jq -c --arg pin "$PIN" '{fields: .fields, pincode: $pin,
  answers: {owns_roof: true, name_matches_bank: true, previous_subsidy: false}, overrides: {}}' "$TMP/ex.json")
read -r code t < <(post /plan "$BODY" "$TMP/plan.json")
echo "plan: $code ${t}s"
jq -c '{planId, latency_ms, lookups}' "$TMP/plan.json"
jq -c '.plan | {verdict: .verdict.code, reasons: .verdict.reasons, accuracy, discom: .discom.code,
  yield: .solar.annual_kwh_per_kw, kw: .recommended.kw, net_cost: .recommended.net_cost,
  saving_y1: .recommended.year1_savings, payback: .recommended.payback_years, warnings}' "$TMP/plan.json"
PLAN_ID=$(jq -r .planId "$TMP/plan.json")

read -r code t < <(curl -sS -o "$TMP/get.json" -w '%{http_code} %{time_total}\n' "$API/plan/$PLAN_ID")
echo "GET /plan/$PLAN_ID: $code ${t}s"
jq -c '{planId, verdict: .plan.verdict.code, stored_consumer_number: .inputs.fields.consumer_number,
  has_name: (.inputs.fields | has("consumer_name"))}' "$TMP/get.json"

TEXT=$(jq -r '.plan | "Recommended size \(.recommended.kw) kW. Payback about \(.recommended.payback_years) years."' "$TMP/plan.json")
read -r code t < <(post /speak "$(jq -nc --arg t "$TEXT" '{text: $t, lang: "en"}')" "$TMP/sp.json")
echo "speak (en): $code ${t}s  $(jq -c '{contentType, voice, languageCode, chars, truncated, audio_b64_len: (.audio | length)}' "$TMP/sp.json")"
read -r code t < <(post /speak '{"text":"आपके घर के लिए तीन किलोवाट का सोलर सिस्टम सही रहेगा। सब्सिडी के बाद लागत लगभग एक लाख रुपये है।","lang":"hi"}' "$TMP/sph.json")
echo "speak (hi): $code ${t}s  $(jq -c '{contentType, languageCode, chars, audio_b64_len: (.audio | length)}' "$TMP/sph.json")"
jq -r .audio "$TMP/sph.json" | base64 -d > "$TMP/hi.mp3" && file -b "$TMP/hi.mp3" | cut -c1-60
