#!/usr/bin/env python3
"""Can the relay reach irpro.co, and where is Shin Kong's conference list?

Two questions in one cheap run.

FIRST, whether irpro.co answers the relay at all. It refuses this project's
sandbox and GitHub's runners with a 403 — a bot filter rather than a geography
one, since both are refused identically (4.13). The relay egresses from Taiwan
with a browser user-agent, which may or may not be enough. The test is a file
whose URL is already known to be good: the FY22 Shin Kong deck, recovered from
the Wayback Machine, which carries the four-bucket pie on page 16. If that
comes back as a PDF the route works and nothing else about it is in doubt.

SECOND, where the listing lives. skfh.com.tw/events-conferences is an iframe
onto irpro.co and its content API names the function — systemId "irpro-tw",
funcId "conferencelisttw" — but not the URL, which the front-end builds. The
archive holds irpro files and no index, so the candidates below are guesses
from that naming. One of them answering with HTML mentioning 法人說明會 is the
index this project needs; all of them 404ing means the listing is built from a
POST or a parameterised endpoint and the next step is reading the page's JS.

Nothing is written. This prints and exits.

Run: python3 scripts/probe_irpro.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

# A file the archive proves exists, then the listing guesses.
TARGETS = [
    ("known deck (FY22, event 357)",
     "https://www.irpro.co/2888/events/357/CH/20230321175446-1.pdf"),
    ("known deck (event 404)",
     "https://www.irpro.co/2888/events/404/CH/20240826083438-1.pdf"),
    ("company root", "https://www.irpro.co/2888/"),
    ("conferencelisttw", "https://www.irpro.co/2888/conferencelisttw"),
    ("events index", "https://www.irpro.co/2888/events"),
    ("events index, CH", "https://www.irpro.co/2888/events/CH"),
    ("skfh page (already allowed, control)",
     "https://www.skfh.com.tw/events-conferences/"),
]


def relay(base, token, url, timeout=90):
    req = urllib.request.Request(
        base.rstrip("/") + "/fetch?url=" + urllib.parse.quote(url, safe=""),
        headers={"User-Agent": UA})
    if token:
        req.add_header("X-Relay-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        try:
            body = e.read()[:200]
        except Exception:                                    # noqa: BLE001
            body = b""
        return e.code, body
    except Exception as e:                                   # noqa: BLE001
        return None, str(e).encode()


def describe(body):
    if body[:4] == b"%PDF":
        return f"PDF, {len(body):,} bytes"
    text = body[:4000].decode("utf-8", "replace")
    hit = [w for w in ("法人說明會", "法說會", "conference", "events")
           if w.lower() in text.lower()]
    return (f"{len(body):,} bytes"
            + (f", mentions {'/'.join(hit)}" if hit else "")
            + " | " + " ".join(text.split())[:120])


def main():
    base = (os.environ.get("TAIWAN_RELAY_URL") or "").strip()
    token = (os.environ.get("TAIWAN_RELAY_TOKEN") or "").strip()
    if not base:
        print("no TAIWAN_RELAY_URL; this probe only runs where the relay is "
              "configured")
        return 1
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/health",
                                    timeout=30) as r:
            h = json.load(r)
        print(f"relay /health: {h}")
        hosts = h.get("allowed_hosts", [])
        print(f"  irpro allowed: {'www.irpro.co' in hosts}\n")
    except Exception as e:                                   # noqa: BLE001
        print(f"relay /health failed: {e}\n")

    for label, url in TARGETS:
        code, body = relay(base, token, url)
        print(f"  {label:<38} {str(code):>5}  "
              f"{describe(body) if body else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
