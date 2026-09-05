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
import ssl
import urllib.parse
import urllib.request

from flask import Flask, Response, request

app = Flask(__name__)

ALLOWED_HOSTS = {"ins-info.ib.gov.tw"}
MAX_BYTES = 32 * 1024 * 1024
UA = "Mozilla/5.0 (compatible; TLFX/1.0)"

# Python 3.13 turned on VERIFY_X509_STRICT in create_default_context(), which
# enforces RFC 5280 requirements that many older certificates do not meet.
# ins-info.ib.gov.tw serves one of them and fails with "Missing Subject Key
# Identifier", so a relay running on a current interpreter cannot fetch it.
#
# Clearing that one flag is NOT disabling TLS verification, and the difference
# matters: the certificate chain is still built and verified to a trusted root,
# and the hostname is still checked. What is relaxed is only the strictness
# about optional extensions being present, which is the pre-3.13 default and
# what every browser reaching this site already does. Verification proper
# stays on; if the chain or the hostname were wrong, this would still refuse.
CTX = ssl.create_default_context()
CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT


@app.get("/health")
def health():
    return {"ok": True, "allowed_hosts": sorted(ALLOWED_HOSTS), "post": True}


def _check(target):
    """Shared guard. Returns an error tuple, or None when the target is allowed."""
    expected = os.environ.get("RELAY_TOKEN", "")
    if not expected:
        return {"error": "relay misconfigured: RELAY_TOKEN unset"}, 500
    if request.headers.get("X-Relay-Token", "") != expected:
        return {"error": "forbidden"}, 403
    parts = urllib.parse.urlparse(target)
    if parts.scheme != "https":
        return {"error": f"scheme not allowed: {parts.scheme or '(none)'}"}, 400
    if parts.hostname not in ALLOWED_HOSTS:
        return {"error": f"host not allowed: {parts.hostname}"}, 400
    return None


def _forward(target, data=None, cookie=None):
    """Fetch the target and mirror the bytes back, with the cookie both ways.

    The cookie matters and is the reason this is not a pure byte pipe. The
    portal's report pages are ASP.NET WebForms: a query is a POST carrying
    __VIEWSTATE and __EVENTVALIDATION obtained from a prior GET, and the server
    ties those tokens to the session cookie it set on that GET. Relaying the
    POST without the cookie gets a viewstate-validation failure that looks
    exactly like a malformed request. So Set-Cookie is passed back to the
    caller and Cookie is passed forward, and the caller keeps the session.
    """
    headers = {"User-Agent": UA}
    if cookie:
        headers["Cookie"] = cookie
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(target, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90, context=CTX) as r:
            body = r.read(MAX_BYTES + 1)
            ctype = r.headers.get("Content-Type", "application/octet-stream")
            setc = r.headers.get_all("Set-Cookie") or []
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}, 502
    if len(body) > MAX_BYTES:
        return {"error": "response too large"}, 502
    resp = Response(body, content_type=ctype)
    if setc:
        # one header the caller can hand straight back as Cookie, rather than
        # making every caller reimplement cookie-jar parsing
        resp.headers["X-Relay-Set-Cookie"] = "; ".join(c.split(";", 1)[0] for c in setc)
    return resp


@app.get("/fetch")
def fetch():
    target = request.args.get("url", "")
    bad = _check(target)
    if bad:
        return bad
    return _forward(target, cookie=request.headers.get("X-Relay-Cookie"))


@app.post("/post")
def post():
    """Relay a form POST. Body is the urlencoded form, verbatim.

    Same two guards as /fetch — allowlisted host, shared token — so this widens
    what can be *asked* of the one permitted host, not which hosts can be
    reached. That distinction is the whole security argument for the relay and
    it is unchanged: this is still not an open proxy.
    """
    target = request.args.get("url", "")
    bad = _check(target)
    if bad:
        return bad
    return _forward(target, data=request.get_data(),
                    cookie=request.headers.get("X-Relay-Cookie"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
