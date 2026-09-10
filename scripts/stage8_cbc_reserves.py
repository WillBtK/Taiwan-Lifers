#!/usr/bin/env python3
"""The central bank's foreign-exchange reserves, monthly, in US$ million.

Matrix EF07M01 of the CBC statistical database is the "key financial
indicators (continued 3)" table of the Financial Statistics Monthly; its fourth
column is 外匯存底(百萬美元), the headline reserves figure the CBC announces
each month. It runs from 1987. The quarterly IRFCL template (series 12,
`data/cbc_irfcl.csv`) carries the same stock at quarter-ends with its
securities/deposits split and the forward book; this file is the monthly
series that lets the May 2025 episode be seen month by month.

Reads cache/cbc_db/EF07M01.json, fetching it from the CBC API if the cache is
empty (the cache directory is not committed). Writes
data/cbc_fx_reserves_monthly.csv.

Run: python3 scripts/stage8_cbc_reserves.py
"""
import csv
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "cbc_db" / "EF07M01.json"
OUT = ROOT / "data" / "cbc_fx_reserves_monthly.csv"
API = "https://cpx.cbc.gov.tw/api/DataAPI/Get?FileName=EF07M01"
COLUMN = "外匯存底(百萬美元)"


def load():
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0 (compatible; TLFX/1.0)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            CACHE.write_bytes(r.read())
    return json.loads(CACHE.read_text(encoding="utf-8"))


def main():
    j = load()
    names = [c["data"] for c in j["data"]["structure"]["Table1"]]
    if COLUMN not in names:
        raise SystemExit(f"EF07M01 has no column {COLUMN!r}: {names}")
    i = 1 + names.index(COLUMN)
    vintage = j["meta"]["last_updated"]
    rows = []
    for r in j["data"]["dataSets"]:
        tag, v = r[0], r[i]
        if "M" not in tag or v in ("-", "", None):
            continue
        rows.append({"obs_month": f"{tag[:4]}-{tag[5:7]}", "fx_reserves_usd_mn": float(v),
                     "source_url": API, "source_doc": f"CBC Financial Statistics Monthly, {j['meta']['title']}, {COLUMN}",
                     "vintage": vintage})
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"-> {OUT.relative_to(ROOT)}  {len(rows)} months, {rows[0]['obs_month']} to {rows[-1]['obs_month']}, "
          f"last {rows[-1]['fx_reserves_usd_mn'] / 1e3:,.1f} US$bn (vintage {vintage})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
