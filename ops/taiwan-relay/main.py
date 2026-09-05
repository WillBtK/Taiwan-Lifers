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
