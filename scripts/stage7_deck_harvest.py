#!/usr/bin/env python3
"""Harvest investor-conference decks from MOPS, for the FX-hedging disclosure.

WHY THIS EXISTS
The sector hedge ratio has to be built from the companies' own numbers, and the
companies publish them in their quarterly investor decks. Until now this project
held a partial deck corpus assembled per firm from company IR sites — good for
Cathay, Fubon and KGI, nothing at all for Shin Kong or Taiwan Life, which is
roughly 18% of sector overseas investment missing from every aggregate.

MOPS is the channel that covers all of them at once. Every listed company must
file its 法人說明會 materials there, and the listing gives a deterministic
filename:

  listing   POST /mops/web/ajax_t100sb02_1
            encodeURIComponent=1 step=1 firstin=1 off=1 TYPEK=sii
            year=<ROC> month=<MM or blank> co_id=<id>
            -> a table with 召開法人說明會日期 and the deck filenames,
               e.g. 288120230316M001.pdf (Chinese) / ...E001.pdf (English)

  download  POST /server-java/FileDownLoad
            step=9 filePath=/home/html/nas/STR/ fileName=<name>
            functionName=t100sb02_1

The insurers are subsidiaries, so the deck is the HOLDING company's:
  2882 Cathay -> Cathay Life      2881 Fubon  -> Fubon Life
  2888 Shin Kong -> Shin Kong Life 2891 CTBC  -> Taiwan Life
  2883 KGI -> KGI Life            2823 China Life, its own listing pre-rebrand
  2833 Taiwan Life, its own listing before the CTBC merger

WHAT IS STORED, AND WHY ONLY THE TEXT
Decks are large and disposable; the FX-hedging disclosure is one or two pages.
Only the text of pages matching the hedging vocabulary is kept, gzipped, and
committed — so writing and rewriting the parsers costs seconds instead of
re-downloading hundreds of megabytes. This is the same arrangement that made the
statutory note parsers tractable.

WHY IT RUNS IN CI
The listing query answers fine from anywhere, but the FILE DOWNLOAD returns the
"FOR SECURITY REASONS" WAF page to this project's sandbox. A runner has a
different address.

Run: python3 scripts/stage7_deck_harvest.py [roc_year ...]
"""
import gzip
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "deck_list"
OUT = ROOT / "data" / "deck_fx_text.json.gz"
INDEX = ROOT / "reports" / "deck_index.json"

LIST_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1"
FILE_URL = "https://mopsov.twse.com.tw/server-java/FileDownLoad"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
BLOCKED = "FOR SECURITY REASONS"

# holding company -> the life insurer whose disclosure the deck carries
ISSUERS = {"2882": "cathay_life", "2881": "fubon_life",
           "2888": "shinkong_pre2026", "2891": "taiwan_life",
           "2883": "kgi_life", "2823": "kgi_life", "2833": "taiwan_life",
           "2887": "shinkong_life"}


def _f(name, default):
    return float((os.environ.get(name) or "").strip() or default)


GAP = _f("TLFX_MOPS_GAP", 8)
BLOCK_WAIT = _f("TLFX_MOPS_BLOCK_WAIT", 120)
_last = [0.0]

# The page worth keeping. A deck is 40+ pages of earnings; the FX-hedging
# disclosure is one or two and always speaks this vocabulary.
FXPAGE = re.compile(
    r"避\s*險|匯\s*率\s*風\s*險|外\s*幣\s*資\s*產|換\s*匯|NDF|"
    r"外匯價格變動準備|FX\s*(?:hedg|polic|reserve)|hedg(?:e|ing)\s*ratio|"
    r"currency\s*swap|natural\s*hedge")


def _sleep():
    d = GAP - (time.time() - _last[0])
    if d > 0:
        time.sleep(d)


def _post(url, form, referer, binary=False):
    _sleep()
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(form).encode(),
        headers={"User-Agent": UA, "Referer": referer,
                 "Content-Type": "application/x-www-form-urlencoded"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read()
            _last[0] = time.time()
            if body[:6] == b"<html>" and BLOCKED.encode() in body[:900]:
                print(f"    ~ WAF, pausing {BLOCK_WAIT:.0f}s", flush=True)
                time.sleep(BLOCK_WAIT)
                _last[0] = time.time()
                continue
            return body if binary else body.decode("utf-8", "replace")
        except Exception as e:                               # noqa: BLE001
            _last[0] = time.time()
            if attempt == 3:
                return None
            time.sleep(5 * (attempt + 1))
    return None


ROW = re.compile(r"<tr[^>]*data-type='body'[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
PDF = re.compile(r"([0-9]{4}\d{8}[ME]\d{3}\.pdf)")
DATE = re.compile(r"(\d{2,3})/(\d{1,2})/(\d{1,2})")


# MONTH IS REQUIRED. A blank month returns 查無資料 rather than the year, which
# read as "this company files no investor conferences" and silently produced an
# empty harvest for every issuer. Conferences cluster in the months after each
# reporting date, so those are queried rather than all twelve.
MONTHS = (3, 4, 5, 6, 8, 9, 11, 12)


def listing(co_id, roc_year):
    """Every investor conference that company filed that year."""
    parts = []
    for m in MONTHS:
        key = CACHE / f"{co_id}_{roc_year}_{m:02d}.html"
        if key.exists():
            parts.append(key.read_text(encoding="utf-8", errors="replace"))
            continue
        t = _post(LIST_URL, {"encodeURIComponent": "1", "step": "1",
                             "firstin": "1", "off": "1", "TYPEK": "sii",
                             "year": str(roc_year), "month": f"{m:02d}",
                             "co_id": co_id},
                  "https://mopsov.twse.com.tw/mops/web/t100sb02_1")
        if t is None:
            continue
        CACHE.mkdir(parents=True, exist_ok=True)
        key.write_text(t, encoding="utf-8")
        parts.append(t)
    t = "\n".join(parts)
    # The DATE COMES FROM THE FILENAME, not from the row. A row carries links to
    # other conferences under 歷年法人說明會, so pairing the row's first date
    # with the row's first PDF attached 2021-03-09 to a file stamped 20201123
    # and gave three different dates the same file. 289120210325M001.pdf is
    # co_id + YYYYMMDD + M001 and cannot disagree with itself.
    out, seen = [], set()
    for name in PDF.findall(t):
        if "M" not in name[-8:]:      # E001 is the English deck, same content
            continue
        if name in seen:
            continue
        seen.add(name)
        y, m, d = name[4:8], name[8:10], name[10:12]
        out.append({"co_id": co_id, "roc_year": roc_year,
                    "date": f"{y}-{m}-{d}", "file": name})
    return out


def deck_text(name):
    """The FX-hedging pages of one deck, flattened."""
    raw = _post(FILE_URL, {"step": "9", "filePath": "/home/html/nas/STR/",
                           "fileName": name, "functionName": "t100sb02_1"},
                "https://mopsov.twse.com.tw/mops/web/t100sb02_1", binary=True)
    if not raw or raw[:4] != b"%PDF":
        return None
    try:
        import fitz
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception:                                        # noqa: BLE001
        return None
    pages = {}
    for i in range(doc.page_count):
        t = doc[i].get_text()
        if not t or not FXPAGE.search(t):
            continue
        pages[str(i + 1)] = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t))
    return pages


def main():
    years = [int(x) for x in sys.argv[1:]] or list(range(115, 106, -1))
    store = {}
    if OUT.exists():
        with gzip.open(OUT, "rt", encoding="utf-8") as fh:
            store = json.load(fh)
    index = []
    print(f"harvesting {len(ISSUERS)} issuers over ROC {years}\n", flush=True)
    for co_id, ent in ISSUERS.items():
        for y in years:
            rows = listing(co_id, y)
            if rows:
                print(f"  {co_id} {ent:<18} ROC{y}: {len(rows)} conferences",
                      flush=True)
            index += rows
    print(f"\n{len(index)} conferences listed", flush=True)

    # MISSING FIRMS FIRST. Sorted by date, run 1 spent three hours on Cathay
    # and Fubon decks from 2021-22 — firms this project already covers — and
    # had not reached Shin Kong or Taiwan Life, the two it was built for. A run
    # that is cut short must still have delivered the thing it was for.
    PRIORITY = {"2888": 0, "2891": 1, "2833": 2, "2823": 3, "2887": 4}
    done = 0
    for r in sorted(index, key=lambda x: (PRIORITY.get(x["co_id"], 9),
                                          x["date"])):
        if r["file"] in store:
            continue
        pages = deck_text(r["file"])
        if pages is None:
            print(f"    ! {r['file']}: not retrieved", flush=True)
            continue
        store[r["file"]] = {"entity_id": ISSUERS[r["co_id"]],
                            "co_id": r["co_id"], "date": r["date"],
                            "pages": pages}
        done += 1
        print(f"    {r['file']}  {r['date']}  {len(pages)} fx pages",
              flush=True)
        if done % 10 == 0:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(OUT, "wt", encoding="utf-8") as fh:
                json.dump(store, fh, ensure_ascii=False)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    per = {}
    for v in store.values():
        per[v["entity_id"]] = per.get(v["entity_id"], 0) + 1
    print(f"\n{len(store)} decks with FX pages -> {OUT.relative_to(ROOT)}")
    for k, v in sorted(per.items()):
        print(f"  {k:<18}{v:>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
