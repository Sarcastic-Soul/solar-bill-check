#!/usr/bin/env bash
# Build the frontend and publish it to Amplify Hosting (manual deploy, no Git connection).
# Usage: scripts/deploy-frontend.sh
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
APP_ID="${AMPLIFY_APP_ID:-d2y09rdd9synq1}"
BRANCH="${AMPLIFY_BRANCH:-main}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT/frontend"
npm ci
npm run build

ZIP="$(mktemp -d)/site.zip"
(cd dist && zip -qr "$ZIP" .)

read -r JOB_ID UPLOAD_URL < <(aws amplify create-deployment --region "$REGION" \
  --app-id "$APP_ID" --branch-name "$BRANCH" \
  --query '[jobId, zipUploadUrl]' --output text)

curl -sf -X PUT -H "Content-Type: application/zip" --upload-file "$ZIP" "$UPLOAD_URL"
aws amplify start-deployment --region "$REGION" --app-id "$APP_ID" \
  --branch-name "$BRANCH" --job-id "$JOB_ID" > /dev/null

for _ in $(seq 1 60); do
  STATUS="$(aws amplify get-job --region "$REGION" --app-id "$APP_ID" \
    --branch-name "$BRANCH" --job-id "$JOB_ID" --query job.summary.status --output text)"
  case "$STATUS" in
    SUCCEED) echo "Deployed: https://$BRANCH.$APP_ID.amplifyapp.com"; exit 0 ;;
    FAILED|CANCELLED) echo "Deployment $JOB_ID $STATUS" >&2; exit 1 ;;
  esac
  sleep 5
done
echo "Timed out waiting for deployment $JOB_ID" >&2
exit 1
