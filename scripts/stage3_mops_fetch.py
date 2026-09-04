#!/usr/bin/env python3
"""Stage 3 fetch: MOPS t164sb01 XBRL-rendered statements -> cache/mops/.

One request per firm-quarter, heavily paced: mopsov's WAF blocks bursts (two
requests 30s apart triggered it; a lone request succeeds), so the loop sleeps
a randomised 60-100s between fetches and backs off five minutes and doubling
on each WAF page. Every success is written to cache immediately; reruns skip
cached files, so the job resumes cleanly.

t164sb01 params: step=1, CO_ID, SYEAR (western), SSEASON 1-4, REPORT_ID=C
(consolidated). The reply is Big5 HTML carrying the full XBRL-rendered
statements. A '資產總計' hit marks success; the WAF page is ~800 bytes.
"""
import random
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "mops"
URL = "https://mopsov.twse.com.tw/server-java/t164sb01"

FIRMS = {"5865": "fubon_life", "5874": "nanshan_life", "2823": "kgi_life",
         "2833": "taiwan_life", "6985": "shinkong_life"}
# 6985 is the surviving ex-Taishin Life entity: its pre-2026 filings are
# Taishin Life's, not Shin Kong Life's (entities break_note), so skip them.
MIN_YEAR = {"6985": 2026}


def quarters():
    # newest first so the freshest data lands earliest in the run
    out = []
    for y in range(2026, 2012, -1):
        for q in (4, 3, 2, 1):
            if (y, q) >= (2026, 3):
                continue
            out.append((y, q))
    return out


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "zh-TW,zh;q=0.9",
        "Referer": "https://mopsov.twse.com.tw/mops/web/t203sb01",
    })
    backoff = 300
    fetched = skipped = empty = 0
    for y, q in quarters():
        for co in FIRMS:
            if y < MIN_YEAR.get(co, 0):
                continue
            fn = CACHE / f"t164sb01_{co}_{y}_{q}_C.html"
            miss = CACHE / f"t164sb01_{co}_{y}_{q}_C.miss"
            if fn.exists() or miss.exists():
                skipped += 1
                continue
            while True:
                try:
                    r = s.get(URL, params={"step": "1", "CO_ID": co, "SYEAR": str(y),
                                           "SSEASON": str(q), "REPORT_ID": "C"},
                              timeout=90)
                    t = r.content.decode("big5", errors="replace")
                except Exception as ex:
                    print(f"{co} {y}Q{q}: transport {ex}; sleep {backoff}", flush=True)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 3600)
                    continue
                if "資產總計" in t:
                    fn.write_text(t, encoding="utf-8")
                    fetched += 1
                    backoff = 300
                    print(f"{co} {y}Q{q}: ok {len(t)}", flush=True)
                elif "CAN NOT BE ACCESSED" in t or r.status_code == 307:
                    print(f"{co} {y}Q{q}: WAF; sleep {backoff}", flush=True)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 3600)
                    continue
                else:
                    # served page without a balance sheet: treat as no filing
                    miss.write_text(t[:2000], encoding="utf-8")
                    empty += 1
                    backoff = 300
                    print(f"{co} {y}Q{q}: no filing ({len(t)}b)", flush=True)
                break
            time.sleep(random.uniform(60, 100))
    print(f"done: fetched {fetched}, no-filing {empty}, cached-skip {skipped}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
