#!/usr/bin/env python3
"""Shin Kong Financial's investor decks, one addressed file at a time.

WHY THIS EXISTS
The pre-2026 Shin Kong Life is roughly a tenth of sector overseas investment
and was absent from the aggregate before 3Q25. MOPS carries no
investor-conference filings for code 2888, and 2887 is Taishin, whose decks
describe Taishin Life until the July 2025 merger — so nothing in the MOPS
corpus covers the entity (4.61, 4.67).

WHY IT NO LONGER WALKS AN INDEX
The first version walked conference ids on skfh.irpro.co. That host serves a
certificate which does not cover its own hostname; verification is not being
relaxed for it, and every path on the host whose certificate IS valid returns
404, 403 or the origin's own 500 (4.69, 4.70). The files, meanwhile, are wide
open: every deck URL tried comes back 200 from www.irpro.co and
www.ir-cloud.com alike. So the constraint is not access but ADDRESSING — the
older host names files by title plus a random suffix, the newer by upload
timestamp, and neither is constructible from a date.

What is enumerable is the Wayback Machine's record of the two file stores,
prefix-queried, which yields fourteen decks between 2017 and 2024. They are
listed in config/skfh_decks.tsv and fetched from the live host, with the
archived capture as a fallback so a host outage does not cost the run.

That is roughly annual rather than quarterly. Annual is exactly what the
chain-link tolerates (MAX_GAP_Q = 4), so it carries the firm through the years
it was missing instead of leaving them empty — but it is a floor on what Shin
Kong contributes, not the full history, and the record should say so.

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
MANIFEST = ROOT / "config" / "skfh_decks.tsv"
OUT = ROOT / "data" / "skfh_deck_text.json.gz"
INDEX = ROOT / "reports" / "skfh_deck_index.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
GAP = float((os.environ.get("TLFX_IRPRO_GAP") or "1.5").strip())

FXPAGE = re.compile(
    r"避\s*險|匯\s*率\s*風\s*險|外\s*幣\s*資\s*產|換\s*匯|NDF|"
    r"外匯價格變動準備|currency\s*swap|hedg(?:e|ing)")
_last = [0.0]


def _throttle():
    d = GAP - (time.time() - _last[0])
    if d > 0:
        time.sleep(d)


def relay(url, timeout=120):
    """The live file, through the Taiwan relay. None on any refusal."""
    _throttle()
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
        return body
    except Exception as e:                                   # noqa: BLE001
        print(f"    relay: {type(e).__name__}: {e}", flush=True)
        return None
    finally:
        _last[0] = time.time()


def archived(url, ts, timeout=180):
    """The capture the CDX index says returned this file. Fallback only."""
    if not ts:
        return None
    wb = f"https://web.archive.org/web/{ts}id_/{url}"
    try:
        req = urllib.request.Request(wb, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:                                   # noqa: BLE001
        print(f"    archive: {type(e).__name__}: {e}", flush=True)
        return None


def deck_pages(raw):
    """The FX-hedging pages of one deck, flattened. None if it will not open."""
    import fitz
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception as e:                                   # noqa: BLE001
        print(f"    not a readable pdf: {e}", flush=True)
        return None
    pages, chars = {}, 0
    for i in range(doc.page_count):
        t = doc[i].get_text()
        chars += len(t or "")
        if t and FXPAGE.search(t):
            pages[str(i + 1)] = re.sub(
                r"\s+", " ", unicodedata.normalize("NFKC", t))
    if not pages:
        # The same distinction the note capture had to learn (4.62): a scan
        # and a deck whose vocabulary simply does not match need opposite
        # treatment, and a bare zero cannot tell them apart.
        why = ("no text layer (scan)" if chars < 200 * doc.page_count
               else "text present, no fx page matched")
        print(f"    0 fx pages of {doc.page_count} — {why}", flush=True)
    return pages


def manifest():
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts[0] == "conf_id":
            continue
        rows.append(dict(zip(("conf_id", "label", "url", "wayback_ts"),
                             (p.strip() for p in parts))))
    return rows


def main():
    if not (os.environ.get("TAIWAN_RELAY_URL") or "").strip():
        print("no TAIWAN_RELAY_URL; this harvest only runs where the relay is")
        return 1
    store = {}
    if OUT.exists():
        with gzip.open(OUT, "rt", encoding="utf-8") as fh:
            store = json.load(fh)
    rows = manifest()
    print(f"{len(rows)} decks listed in {MANIFEST.relative_to(ROOT)}\n",
          flush=True)
    index, got = [], 0
    for row in rows:
        key = f"{row['conf_id']}_{row['url'].rsplit('/', 1)[-1]}"
        if key in store:
            print(f"  {row['conf_id']:>4}  {row['label']}: held", flush=True)
            index.append({k: row[k] for k in ("conf_id", "label", "url")}
                         | {"fx_pages": len(store[key]["pages"])})
            continue
        print(f"  {row['conf_id']:>4}  {row['label']}", flush=True)
        raw = relay(row["url"])
        via = "live"
        if not raw or raw[:4] != b"%PDF":
            raw = archived(row["url"], row.get("wayback_ts"))
            via = "archive"
        if not raw or raw[:4] != b"%PDF":
            print("    ! not retrieved from either", flush=True)
            continue
        pages = deck_pages(raw)
        if pages is None:
            continue
        store[key] = {"entity_id": "shinkong_life_pre2026",
                      "conf_id": int(row["conf_id"]), "label": row["label"],
                      "url": row["url"], "via": via, "pages": pages}
        got += 1
        print(f"    {len(raw):,} bytes via {via}, {len(pages)} fx pages",
              flush=True)
        index.append({k: row[k] for k in ("conf_id", "label", "url")}
                     | {"fx_pages": len(pages), "via": via})
        if got % 4 == 0:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(OUT, "wt", encoding="utf-8") as fh:
                json.dump(store, fh, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    with_fx = sum(1 for v in store.values() if v["pages"])
    print(f"\n{len(store)} decks held, {with_fx} with an fx page "
          f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
