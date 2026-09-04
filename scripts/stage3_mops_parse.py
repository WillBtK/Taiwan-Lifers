#!/usr/bin/env python3
"""Parse cached MOPS t164sb01 pages (inline XBRL) into a firm-quarter table.

Each cached page is the full XBRL-rendered financial statement: facts are
<ix:nonFraction name="..." contextRef="AsOfYYYYMMDD|FromYYYYMMDDToYYYYMMDD"
sign? scale="3">1,234,567</ix:nonFraction>, so extraction is by concept name
and context date, never by table position. Printed values are NT$ thousand
(scale 3); stored as NT$ mn.

Concepts pulled (per file, at the statement's own period end):
  ifrs-full:Assets / Liabilities / Equity   (AsOf period end)
  *ReserveForForeignExchangeValuation       (AsOf, pre-IFRS17 balance sheets)
  *NetChangeInReserveForForeignExchangeValuation (From Jan-1 To period end;
     recovers the IFRS-17-era balance from the prior year-end, as with
     Cathay — decisions 3.12)

Writes data/mops_statements.csv (one row per firm-quarter-report).
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "mops"
OUT = ROOT / "data" / "mops_statements.csv"

FIRMS = {"5846": "cathay_life", "5865": "fubon_life", "5874": "nanshan_life",
         "2823": "kgi_life", "2833": "taiwan_life", "6985": "shinkong_life"}

FACT = re.compile(
    r'<ix:nonFraction[^>]*?name="([^"]+)"[^>]*?contextRef="([^"]+)"([^>]*)>([^<]*)</ix:nonFraction>')

Q_END = {1: "0331", 2: "0630", 3: "0930", 4: "1231"}


def facts(html: str):
    for m in FACT.finditer(html):
        name, ctx, attrs, raw = m.groups()
        raw = raw.strip().replace(",", "")
        if not raw or not re.fullmatch(r"-?\d+(\.\d+)?", raw):
            continue
        v = float(raw)
        if 'sign="-"' in attrs:
            v = -v
        yield name, ctx, v


def parse_file(path: Path):
    m = re.fullmatch(r"t164sb01_(\d+)_(\d{4})_(\d)_([CA])\.html", path.name)
    assert m, path.name
    co, y, q, rid = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    end = f"{y}{Q_END[q]}"
    ytd = f"From{y}0101To{end}"
    asof = f"AsOf{end}"
    html = path.read_text(encoding="utf-8")
    row = {"co_id": co, "entity_id": FIRMS.get(co, co), "year": y, "q": q,
           "report": rid, "obs_quarter": f"{y}-{q * 3 - 2:02d}-01"}
    for name, ctx, v in facts(html):
        short = name.split(":")[-1]
        if ctx == asof and short in ("Assets", "Liabilities", "Equity"):
            # keep the first occurrence (statement body; later ones are notes)
            row.setdefault(short.lower() + "_mn", round(v / 1000, 3))
        elif ctx == asof and "ReserveForForeignExchangeValuation" in short and "NetChange" not in short:
            row.setdefault("fx_reserve_mn", round(v / 1000, 3))
        elif ctx == ytd and "NetChangeInReserveForForeignExchangeValuation" in short:
            row.setdefault("fx_reserve_net_change_ytd_mn", round(v / 1000, 3))
    return row


def main():
    rows = [parse_file(p) for p in sorted(CACHE.glob("t164sb01_*.html"))]
    problems = []
    for r in rows:
        need = ("assets_mn", "liabilities_mn", "equity_mn")
        if not all(k in r for k in need):
            problems.append(f"{r['co_id']} {r['year']}Q{r['q']}: missing {[k for k in need if k not in r]}")
            continue
        if abs(r["assets_mn"] - r["liabilities_mn"] - r["equity_mn"]) > 0.5:
            problems.append(f"{r['co_id']} {r['year']}Q{r['q']}: A != L+E")
    cols = ["co_id", "entity_id", "year", "q", "report", "obs_quarter",
            "assets_mn", "liabilities_mn", "equity_mn", "fx_reserve_mn",
            "fx_reserve_net_change_ytd_mn"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})
    print(f"rows: {len(rows)}; problems: {len(problems)}")
    for p in problems:
        print("  PROBLEM", p)
    print(f"csv: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
