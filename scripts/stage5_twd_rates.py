#!/usr/bin/env python3
"""TWD per unit of every currency the filings state a notional in.

WHY THIS EXISTS
Four insurers state their derivative notionals in the CONTRACT currency rather
than in NT$ — Shin Kong and Taishin in USD, Taiwan Life across nine currencies,
Mercuries across four, Hontai in USD. The extractor records those faithfully in
`notional_ccy_k` with the currency beside it and leaves `notional_ntd_k` empty,
which is right: a filing that says "USD 19,200,000 仟元" has not stated an NT$
figure and inventing one inside the extractor would bury the assumption.

But a hedge ratio needs one number over another in one unit, so the conversion
has to happen somewhere, and here is where it is visible. 597 notional rows —
two thirds of every row captured, four firms entirely — sit unusable without it,
which is why Mercuries has a hedge notional at 23 dates and appears in no panel.

WHY SPOT, AND WHAT THAT ASSUMES
A currency swap or forward notional of USD 1bn hedges USD 1bn of exposure. The
comparison it goes into is against foreign assets carried in NT$ at the same
date's spot, so translating the notional at that date's spot puts numerator and
denominator on one basis. It is NOT a valuation — the contract rate, which is
not disclosed, would be needed for that, and no mark-to-market is implied.

The rates are the central bank's own monthly spot, mid of the customer bid and
ask, from two matrices this project already caches: EG51M01 for the US dollar,
EG52M01 for the other thirteen. Month-end would be better than a monthly
average for a balance-sheet date; the CBC publishes the average, and at the
scale this feeds — a hedge ratio quoted to a tenth of a point — the difference
is immaterial and is recorded rather than hidden.

Run: python3 scripts/stage5_twd_rates.py
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "cbc_db"
OUT = ROOT / "data" / "twd_rates_monthly.csv"

# EG52M01 columns come in bid/ask pairs, in the order the matrix declares them.
CCY = {"日圓": "JPY", "港幣": "HKD", "澳幣": "AUD", "紐西蘭幣": "NZD",
       "英鎊": "GBP", "瑞典克郎": "SEK", "新加坡幣": "SGD", "泰銖": "THB",
       "加拿大元": "CAD", "歐元": "EUR", "瑞士法郎": "CHF", "南非幣": "ZAR",
       "人民幣": "CNY"}
# The filings write the yuan as RMB and, once, the yen as JPY with the amount
# already in thousands of yen. Both map onto the same CBC column.
ALIAS = {"RMB": "CNY"}


def month(tag):
    """1992M01 -> 1992-01."""
    return f"{tag[:4]}-{tag[5:7]}" if "M" in tag else None


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def usd():
    """TWD per USD, mid of the customer bid and ask."""
    d = json.loads((CACHE / "EG51M01.json").read_text(encoding="utf-8"))
    out = {}
    for row in d["data"]["dataSets"]:
        m = month(row[0])
        bid, ask = num(row[1]), num(row[2])
        if m and bid and ask:
            out[m] = (bid + ask) / 2.0
    return out


def others():
    """TWD per unit for the thirteen currencies of EG52M01."""
    d = json.loads((CACHE / "EG52M01.json").read_text(encoding="utf-8"))
    names = [c["data"] for c in d["data"]["structure"]["Table1"]]
    out = {}
    for row in d["data"]["dataSets"]:
        m = month(row[0])
        if not m:
            continue
        for i, name in enumerate(names):
            code = CCY.get(name)
            if not code:
                continue
            bid, ask = num(row[1 + 2 * i]), num(row[2 + 2 * i])
            if bid and ask:
                out.setdefault(code, {})[m] = (bid + ask) / 2.0
    return out


def load():
    """{currency: {YYYY-MM: TWD per unit}}, aliases resolved."""
    if not (CACHE / "EG51M01.json").exists():
        return {}
    table = others()
    table["USD"] = usd()
    for alias, real in ALIAS.items():
        if real in table:
            table[alias] = table[real]
    return table


def convert(amount_ccy, currency, as_of, table=None):
    """Foreign-currency thousands -> NT$ thousands. None when no rate exists.

    Falls back to the nearest earlier month rather than interpolating, because
    the only gaps are at the start of a currency's history, where there is
    nothing on the other side to interpolate towards.
    """
    table = load() if table is None else table
    pts = table.get((currency or "").upper())
    if not pts or amount_ccy is None:
        return None
    m = as_of[:7]
    if m in pts:
        return amount_ccy * pts[m]
    earlier = [k for k in pts if k <= m]
    return amount_ccy * pts[max(earlier)] if earlier else None


def main():
    table = load()
    if not table:
        print(f"no cached CBC matrices under {CACHE.relative_to(ROOT)}")
        return 1
    rows = [{"obs_month": m, "currency": c, "twd_per_unit": round(v, 6)}
            for c, pts in table.items() for m, v in pts.items()
            if c not in ALIAS]
    rows.sort(key=lambda r: (r["currency"], r["obs_month"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["obs_month", "currency",
                                           "twd_per_unit"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {OUT.relative_to(ROOT)}")
    for c in sorted(table):
        if c in ALIAS:
            continue
        ms = sorted(table[c])
        print(f"  {c}  {len(ms):>4}  {ms[0]} .. {ms[-1]}   "
              f"latest {table[c][ms[-1]]:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
