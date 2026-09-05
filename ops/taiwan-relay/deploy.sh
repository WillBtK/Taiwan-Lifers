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

# Projects created after Google's 2024 change do not give the default Compute
# Engine service account the roles Cloud Build needs; the build then dies on
# "could not resolve source" while uploading. This grant is the documented fix
# and is a no-op where the role is already held.
NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$NUM-compute@developer.gserviceaccount.com" \
  --role=roles/cloudbuild.builds.builder --condition=None --quiet >/dev/null
sleep 20   # IAM changes take a few seconds to reach Cloud Build

gcloud run deploy "$SERVICE" \
  --source "$(dirname "$0")" \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "RELAY_TOKEN=$TOKEN" \
  --quiet

URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" \
        --region "$REGION" --format='value(status.url)' 2>/dev/null)
if [ -z "$URL" ]; then
  echo "Deploy failed - no service URL. Read the error above." >&2
  exit 1
fi

cat <<EOF

Deployed: $URL

Add these two GitHub repository secrets
(Settings -> Secrets and variables -> Actions -> New repository secret):

  TAIWAN_RELAY_URL    $URL
  TAIWAN_RELAY_TOKEN  $TOKEN

Now confirm the origin actually accepts this egress:

  RELAY_URL="$URL" RELAY_TOKEN="$TOKEN" bash $(dirname "$0")/verify.sh
EOF
