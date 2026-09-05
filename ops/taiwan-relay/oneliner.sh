mkdir -p ~/tlfx && cd ~/tlfx && cat > main.py <<'PYEOF'
"""Minimal fetch relay with Taiwan egress.

ins-info.ib.gov.tw (the Insurance Bureau's statutory disclosure portal) accepts
connections only from inside Taiwan: it refuses the agent sandbox and GitHub's
runners identically, with the TCP connect never completing (decisions 4.13).
Deployed to a Taiwan region, this service fetches those URLs and returns the
bytes unchanged, so scripts/fetch_sources.py can run anywhere.

It is deliberately not a general proxy. Two constraints keep it from becoming
an open relay someone else can point at arbitrary hosts:
  * the target host must be in ALLOWED_HOSTS (exact match, https only);
  * every request must carry X-Relay-Token matching the RELAY_TOKEN env var.
Requests failing either check are refused without being forwarded.
"""
import os
import urllib.parse
import urllib.request

from flask import Flask, Response, request

app = Flask(__name__)

ALLOWED_HOSTS = {"ins-info.ib.gov.tw"}
MAX_BYTES = 32 * 1024 * 1024
UA = "Mozilla/5.0 (compatible; TLFX/1.0)"


@app.get("/health")
def health():
    return {"ok": True, "allowed_hosts": sorted(ALLOWED_HOSTS)}


@app.get("/fetch")
def fetch():
    expected = os.environ.get("RELAY_TOKEN", "")
    if not expected:
        return {"error": "relay misconfigured: RELAY_TOKEN unset"}, 500
    if request.headers.get("X-Relay-Token", "") != expected:
        return {"error": "forbidden"}, 403

    target = request.args.get("url", "")
    parts = urllib.parse.urlparse(target)
    if parts.scheme != "https":
        return {"error": f"scheme not allowed: {parts.scheme or '(none)'}"}, 400
    if parts.hostname not in ALLOWED_HOSTS:
        return {"error": f"host not allowed: {parts.hostname}"}, 400

    req = urllib.request.Request(target, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read(MAX_BYTES + 1)
            ctype = r.headers.get("Content-Type", "application/octet-stream")
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}, 502
    if len(body) > MAX_BYTES:
        return {"error": "response too large"}, 502
    return Response(body, content_type=ctype)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
PYEOF
printf 'flask==3.0.3\ngunicorn==22.0.0\n' > requirements.txt
printf 'web: gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 120 main:app\n' > Procfile
TOKEN=$(openssl rand -hex 24)
PROJECT=$(gcloud config get-value project 2>/dev/null)
NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
gcloud services enable run.googleapis.com cloudbuild.googleapis.com --quiet
# Projects created after Google's 2024 change do not give the default Compute
# Engine service account the roles Cloud Build needs, and the build then fails
# on "could not resolve source" while uploading. Granting the builder role is
# the documented fix and is a no-op where it is already held.
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$NUM-compute@developer.gserviceaccount.com" \
  --role=roles/cloudbuild.builds.builder --condition=None --quiet >/dev/null
sleep 20   # IAM changes take a few seconds to propagate to Cloud Build
gcloud run deploy taiwan-relay --source . --region asia-east1 --allow-unauthenticated --set-env-vars RELAY_TOKEN=$TOKEN --quiet
URL=$(gcloud run services describe taiwan-relay --region asia-east1 --format='value(status.url)' 2>/dev/null)
# Guard the check on the deploy having produced a service. Running it anyway
# reports a transport failure as an egress verdict, which is a different and
# much more misleading claim.
if [ -z "$URL" ]; then
  echo; echo "DEPLOY FAILED - no service URL. Read the error above; the egress"
  echo "question is untested, not answered."
  exit 1
fi
echo; echo "TAIWAN_RELAY_URL    $URL"; echo "TAIWAN_RELAY_TOKEN  $TOKEN"; echo
echo "--- verifying the origin accepts this egress ---"
code=$(curl -sS --max-time 120 -o /tmp/relay_body -w '%{http_code}' -H "X-Relay-Token: $TOKEN" "$URL/fetch?url=https%3A%2F%2Fins-info.ib.gov.tw%2Fopendata%2Fjson-06021011.aspx" || echo 000)
echo "http=$code"; head -c 200 /tmp/relay_body; echo
case "$code" in
  200) echo "PASS - add the two values above as GitHub secrets." ;;
  502) echo "FAIL - the relay ran and the origin refused it. Cloud Run's shared"
       echo "       egress is not read as Taiwan; the VM fallback is needed." ;;
  *)   echo "INCONCLUSIVE ($code) - the relay itself did not answer properly;"
       echo "       this says nothing about the origin. Check the service logs." ;;
esac
