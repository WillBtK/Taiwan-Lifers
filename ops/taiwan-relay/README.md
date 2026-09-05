# taiwan-relay

A fetch relay for the one class of source that refuses every egress available
to automation: `ins-info.ib.gov.tw`, the Insurance Bureau's statutory
disclosure portal. Measured 2026-09-05 (decisions 4.13), it refuses the agent
sandbox and a GitHub-hosted runner identically — the TCP connect never
completes — while the same URLs succeed from a Taiwan connection. Everything
else the project needs is reachable from one of the two, so this exists solely
to give continuous integration a Taiwan address.

## What it is not

Not a general proxy. It forwards only to hosts in `ALLOWED_HOSTS` (currently
one), only over https, and only when the caller presents `X-Relay-Token`
matching the `RELAY_TOKEN` environment variable. Widen `ALLOWED_HOSTS`
deliberately, never as a convenience.

## Deploy (Google Cloud Run, region asia-east1 — Changhua, Taiwan)

`asia-east1` is the relevant detail: it is physically in Taiwan, so egress
carries a Taiwan address. Any other provider with a Taiwan region works the
same way.

```
gcloud run deploy taiwan-relay \
  --source ops/taiwan-relay \
  --region asia-east1 \
  --allow-unauthenticated \
  --set-env-vars RELAY_TOKEN="$(openssl rand -hex 24)"
```

`--allow-unauthenticated` puts authentication in the relay's own token rather
than in Google IAM, which is what lets a GitHub runner call it with a single
header and no service-account key. Keep the token secret; it is the only thing
standing between the relay and anyone who finds the URL.

Cloud Run scales to zero and this is called a handful of times a month, so the
cost sits inside the free tier in normal use. Confirm against current pricing
rather than taking that on trust.

## Wire it to CI

Add two repository secrets:

| Secret | Value |
|---|---|
| `TAIWAN_RELAY_URL` | the service URL Cloud Run prints on deploy |
| `TAIWAN_RELAY_TOKEN` | the `RELAY_TOKEN` value used above |

`.github/workflows/fetch-sources.yml` picks them up automatically. Until they
exist, that workflow still runs and still collects every other source; the
relay-bound ones are recorded as unavailable rather than failing the run.

## Verify

```
curl -s "$URL/health"
curl -s -H "X-Relay-Token: $TOKEN" \
  "$URL/fetch?url=https%3A%2F%2Fins-info.ib.gov.tw%2Fopendata%2Fjson-06021011.aspx" | head -c 300
```

The second should return JSON beginning with an insurer record. If it returns
a 502 with a timeout, the region is not giving Taiwan egress and the host is
still refusing; nothing else in the project depends on this, so the fallback
is the manual route it was built to replace.
