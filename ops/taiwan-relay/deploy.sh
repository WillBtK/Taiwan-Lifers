#!/usr/bin/env bash
# Deploy the relay to Cloud Run in asia-east1 (Changhua, Taiwan) and print the
# two values that go into GitHub repository secrets. Safe to re-run: Cloud Run
# deploys are idempotent and the token is only generated when absent.
#
# Easiest path is Google Cloud Shell (console.cloud.google.com, ">_" icon):
# gcloud is installed and already authenticated there, so nothing is needed on
# your own machine.
set -euo pipefail

REGION=asia-east1          # the point of the exercise: physically in Taiwan
SERVICE=taiwan-relay
PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"

if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  echo "No project set. Run:  gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

TOKEN="${RELAY_TOKEN:-$(openssl rand -hex 24)}"
echo "project=$PROJECT region=$REGION service=$SERVICE"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  --project "$PROJECT" --quiet

gcloud run deploy "$SERVICE" \
  --source "$(dirname "$0")" \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "RELAY_TOKEN=$TOKEN" \
  --quiet

URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" \
        --region "$REGION" --format='value(status.url)')

cat <<EOF

Deployed: $URL

Add these two GitHub repository secrets
(Settings -> Secrets and variables -> Actions -> New repository secret):

  TAIWAN_RELAY_URL    $URL
  TAIWAN_RELAY_TOKEN  $TOKEN

Now confirm the origin actually accepts this egress:

  RELAY_URL="$URL" RELAY_TOKEN="$TOKEN" bash $(dirname "$0")/verify.sh
EOF
