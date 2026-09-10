#!/usr/bin/env python3
"""Where is a Shin Kong conference index the relay can actually reach?

The decks are open and the index is not (4.69): every deck URL tried on
www.irpro.co returns 200, while the app that lists them answers only on
skfh.irpro.co, which serves a certificate that does not cover its own
hostname. Verification is not being relaxed for that, so the index has to be
found somewhere else or the decks stay unreachable — their filenames carry a
random suffix and cannot be constructed.

The archive says where else to look. Shin Kong's IR site is built by the same
vendor on an older host, www.ir-cloud.com, whose certificate IS valid and
which serves the same files under /taiwan/2888/. Crawled captures of it show
a document library — downloadlibrary2.php?doctype=2&year=N, 活動訊息, with a
year selector back to 2016 — and, on the pre-2020 skin, per-conference pages
at irwebsite/recent.php?id=N. Either is the index this needs.

So the candidates below split in two. The www.irpro.co ones cost nothing to
try because the host is already permitted; if the same PHP app answers there
under the /2888/ prefix, the problem is solved with no console work at all.
The www.ir-cloud.com ones will be refused by the relay until that host is
added to RELAY_ALLOWED_HOSTS, and are here to say whether asking for that is
worth it.

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

IRPRO = "https://www.irpro.co/2888"           # already permitted
CLOUD = "https://www.ir-cloud.com/taiwan/2888"  # needs RELAY_ALLOWED_HOSTS
TARGETS = [
    # The same app under the file-store prefix, on the host whose certificate
    # is valid. Free to try: nothing has to change for these to answer.
    ("irpro: library, all years",
     f"{IRPRO}/irwebsite_c/downloadlibrary2.php?doctype=2&year=0"),
    ("irpro: library, 2022",
     f"{IRPRO}/irwebsite_c/downloadlibrary2.php?doctype=2&year=2022"),
    ("irpro: library index",
     f"{IRPRO}/irwebsite_c/downloadlibrary.php"),
    ("irpro: old skin event list",
     f"{IRPRO}/irwebsite/event.php"),
    ("irpro: old skin conference 330",
     f"{IRPRO}/irwebsite/recent.php?id=330"),
    ("irpro: known deck, control",
     f"{IRPRO}/events/357/CH/20230321175446-1.pdf"),
    # The host the archive actually crawled these pages on. Refused until it
    # is allow-listed; the control says whether that refusal is the only thing
    # in the way.
    ("ir-cloud: library, all years",
     f"{CLOUD}/irwebsite_c/downloadlibrary2.php?doctype=2&year=0"),
    ("ir-cloud: old skin event list",
     f"{CLOUD}/irwebsite/event.php"),
    ("ir-cloud: known deck, control",
     f"{CLOUD}/events/312/CH/2020Q4%20Chi%20(H)_GAjH2jEBEFqL.pdf"),
]
DUMP = 1200


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
    import re
    text = body.decode("utf-8", "replace")
    pdfs = sorted(set(re.findall(r'[^"\'\s>]+\.pdf', text, re.I)))
    ids = sorted(set(re.findall(r'id=(\d+)', text)), key=int)
    return (f"{len(body):,} bytes | {len(pdfs)} pdf links {pdfs[:4]} | "
            f"ids {ids[:12]}\n      "
            + " ".join(text.split())[:DUMP])


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
        for want in ("www.irpro.co", "www.ir-cloud.com"):
            print(f"  {want} allowed: {want in hosts}")
        print()
    except Exception as e:                                   # noqa: BLE001
        print(f"relay /health failed: {e}\n")

    for label, url in TARGETS:
        code, body = relay(base, token, url)
        print(f"  {label:<38} {str(code):>5}  "
              f"{describe(body) if body else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
