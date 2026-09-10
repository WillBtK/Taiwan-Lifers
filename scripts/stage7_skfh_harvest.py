#!/usr/bin/env python3
"""Shin Kong Financial's investor decks, via the relay, from skfh.irpro.co.

WHY THIS EXISTS
The pre-2026 Shin Kong Life is roughly a tenth of sector overseas investment
and was absent from the aggregate before 3Q25. MOPS carries no
investor-conference filings for code 2888, and 2887 is Taishin, whose decks
describe Taishin Life until the July 2025 merger — so nothing in the MOPS
corpus covers the entity (4.61, 4.67).

WHERE THEY ARE, WHICH TOOK SOME FINDING
skfh.com.tw/events-conferences is an empty Angular shell. Its content API names
the function but not the URL; the front-end resolves it through a second call,
GET /skfh-portal-api/SystemUrlInfo, which maps funcId to URL:

    conferencelisttw -> https://skfh.irpro.co/tw/event-institutional-investor-
                        conference-list.php

So the index and the decks are on skfh.irpro.co, a host that refuses this
project's sandbox and GitHub's runners alike with a 403 and answers the relay.
The list page is year-filtered and shows only a handful at a time, but the
per-conference page takes a plain integer id — 330 and 331 are 2022, 357 is
2023, 404 is 2024, 415 to 421 are 2025 — so walking the id range finds every
conference without needing the index's pagination at all.

WHAT IS KEPT
The same arrangement as the MOPS deck harvest: only pages matching the
FX-hedging vocabulary, flattened and gzipped, so re-reading the parser costs
seconds instead of re-downloading. The disclosure being sought is one page —
the FY22 deck carries it at page 16, four buckets on total foreign assets with
the base printed in NT$ and, in a footnote, the split between currency swaps
and NDFs.

Run in CI, where the relay token is: python3 scripts/stage7_skfh_harvest.py
"""
import gzip
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "skfh_deck_text.json.gz"
INDEX = ROOT / "reports" / "skfh_deck_index.json"

PAGE = "https://skfh.irpro.co/tw/event-institutional-investor-conference-page.php?id={}"
LIST = "https://skfh.irpro.co/tw/event-institutional-investor-conference-list.php"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
GAP = float((os.environ.get("TLFX_IRPRO_GAP") or "1.5").strip())
# Ids seen in the archive span 330 (2022) to 421 (2025). The window is widened
# either side: below to reach 2018-2021, above so a conference filed after this
# was written is not silently missed.
ID_FROM = int((os.environ.get("TLFX_IRPRO_FROM") or "150").strip())
ID_TO = int((os.environ.get("TLFX_IRPRO_TO") or "460").strip())

FXPAGE = re.compile(
    r"避\s*險|匯\s*率\s*風\s*險|外\s*幣\s*資\s*產|換\s*匯|NDF|"
    r"外匯價格變動準備|currency\s*swap|hedg(?:e|ing)")
PDF = re.compile(r'href="([^"]+\.pdf)"', re.I)
DATE = re.compile(r"(20\d{2})[/.-](\d{1,2})[/.-](\d{1,2})")
_last = [0.0]


def relay(url, binary=False, timeout=120):
    d = GAP - (time.time() - _last[0])
    if d > 0:
        time.sleep(d)
    base = (os.environ.get("TAIWAN_RELAY_URL") or "").strip()
    token = (os.environ.get("TAIWAN_RELAY_TOKEN") or "").strip()
    req = urllib.request.Request(
        base.rstrip("/") + "/fetch?url=" + urllib.parse.quote(url, safe=""),
        headers={"User-Agent": UA})
    if token:
        req.add_header("X-Relay-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
        _last[0] = time.time()
        return body if binary else body.decode("utf-8", "replace")
    except urllib.error.HTTPError:
        _last[0] = time.time()
        return None
    except Exception:                                        # noqa: BLE001
        _last[0] = time.time()
        return None


def deck_pages(raw):
    """The FX-hedging pages of one deck, flattened."""
    import fitz
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception:                                        # noqa: BLE001
        return None
    pages = {}
    for i in range(doc.page_count):
        t = doc[i].get_text()
        if t and FXPAGE.search(t):
            pages[str(i + 1)] = re.sub(
                r"\s+", " ", unicodedata.normalize("NFKC", t))
    return pages


def main():
    if not (os.environ.get("TAIWAN_RELAY_URL") or "").strip():
        print("no TAIWAN_RELAY_URL; this harvest only runs where the relay is")
        return 1
    store = {}
    if OUT.exists():
        with gzip.open(OUT, "rt", encoding="utf-8") as fh:
            store = json.load(fh)
    index, done = [], 0
    print(f"walking conference ids {ID_FROM}..{ID_TO}\n", flush=True)
    for cid in range(ID_FROM, ID_TO + 1):
        html = relay(PAGE.format(cid))
        if not html or "conference" not in html.lower():
            continue
        links = [urllib.parse.urljoin(PAGE.format(cid), u)
                 for u in PDF.findall(html)]
        m = DATE.search(html)
        date = (f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                if m else None)
        if not links:
            continue
        index.append({"id": cid, "date": date, "files": links})
        print(f"  id {cid}  {date or '?':<12} {len(links)} file(s)", flush=True)
        for u in links:
            key = f"{cid}_{u.rsplit('/', 1)[-1]}"
            if key in store:
                continue
            raw = relay(u, binary=True)
            if not raw or raw[:4] != b"%PDF":
                print(f"    ! {key}: not retrieved", flush=True)
                continue
            pages = deck_pages(raw)
            if pages is None:
                continue
            store[key] = {"entity_id": "shinkong_life_pre2026", "conf_id": cid,
                          "date": date, "url": u, "pages": pages}
            done += 1
            print(f"    {key}  {len(pages)} fx pages", flush=True)
            if done % 5 == 0:
                OUT.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(OUT, "wt", encoding="utf-8") as fh:
                    json.dump(store, fh, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    ds = sorted(v["date"] for v in store.values() if v.get("date"))
    print(f"\n{len(store)} decks with FX pages -> {OUT.relative_to(ROOT)}")
    if ds:
        print(f"  {ds[0]} .. {ds[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
