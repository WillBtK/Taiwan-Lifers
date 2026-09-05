#!/usr/bin/env bash
# Does the deployed relay actually satisfy the origin's geography filter?
# Cloud Run egress addresses are Google-owned and not always geolocated to the
# region that runs the service, so this has to be measured, not assumed.
set -euo pipefail
: "${RELAY_URL:?set RELAY_URL}"
: "${RELAY_TOKEN:?set RELAY_TOKEN}"

TARGET='https%3A%2F%2Fins-info.ib.gov.tw%2Fopendata%2Fjson-06021011.aspx'
echo "health:"; curl -sS --max-time 20 "$RELAY_URL/health"; echo

code=$(curl -sS --max-time 120 -o /tmp/relay_body -w '%{http_code}' \
        -H "X-Relay-Token: $RELAY_TOKEN" "$RELAY_URL/fetch?url=$TARGET" || echo 000)
echo "fetch: http=$code"
head -c 200 /tmp/relay_body; echo; echo

case "$code" in
  200) echo "PASS - the origin accepts this egress. Add the two secrets and the"
       echo "       weekly workflow will collect these sources from now on." ;;
  502) echo "FAIL - the relay reached the origin and the origin refused or timed"
       echo "       out. Cloud Run's shared egress is not being read as Taiwan."
       echo "       Fallback: a Compute Engine e2-micro in asia-east1 with its own"
       echo "       external address, running the same app, geolocates reliably."
       echo "       That costs roughly USD 7-10/month; check current pricing." ;;
  403) echo "FAIL - token mismatch between RELAY_TOKEN here and the deployed service." ;;
  000) echo "INCONCLUSIVE - no response from the relay at all. Check the URL and"
       echo "       that the service deployed; this says nothing about the origin." ;;
  *)   echo "INCONCLUSIVE - unexpected status $code from the relay, so the origin"
       echo "       was not actually tested. Check 'gcloud run services logs read"
       echo "       taiwan-relay --region asia-east1'." ;;
esac
