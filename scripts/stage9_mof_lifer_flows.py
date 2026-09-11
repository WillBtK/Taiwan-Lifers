#!/usr/bin/env python3
"""Japanese life insurers' net purchases of foreign long-term debt, monthly.

The Ministry of Finance publishes purchases and sales of foreign securities by
resident investor type (designated major investors), monthly from 2005, in
units of 100 million yen. Table monthb3 is long-term debt securities; the
生命保険会社 block gives acquisitions, dispositions and net. This is the
sector-identified flow series for the Japanese half of the Asia page: what
the lifers actually did with their foreign bond book, month by month, against
the stock and hedge series digitised from the BoJ's Financial System Report.

Reads data/raw/mof/monthb3.csv (cp932), fetching it if absent. Writes
data/japan/mof_lifer_foreign_bond_flows_monthly.csv with the net flow in
NT-style units this repo uses elsewhere: yen billions, plus the 12-month
rolling sum.

Run: python3 scripts/stage9_mof_lifer_flows.py
"""
import csv
import io
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "mof" / "monthb3.csv"
OUT = ROOT / "data" / "japan" / "mof_lifer_foreign_bond_flows_monthly.csv"
URL = ("https://www.mof.go.jp/policy/international_policy/reference/"
       "itn_transactions_in_securities/monthb3.csv")
MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def load():
    if not RAW.exists():
        RAW.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (compatible; TLFX/1.0)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            RAW.write_bytes(r.read())
    return list(csv.reader(io.StringIO(RAW.read_bytes().decode("cp932"))))


def main():
    rows = load()
    head = next(r for r in rows[:12] if any("Life Insurance" in c for c in r))
    col = head.index(next(c for c in head if "Life Insurance" in c))
    sub = next(r for r in rows[:12] if "Net" in r)
    assert sub[col + 2] == "Net", sub[col:col + 3]
    vintage = next((c for r in rows[:3] for c in r if "Final Update" in c), "")
    out, year, roll = [], None, []
    for r in rows[11:]:
        if r[0].strip():
            try:
                year = int(r[0])
            except ValueError:
                continue
        if year is None or r[2].strip() not in MON:
            continue
        v = r[col + 2].replace(",", "").strip()
        if v in ("-", ""):
            continue
        net_bn = float(v) / 10.0            # 億円 -> 十億円
        roll.append(net_bn)
        roll = roll[-12:]
        out.append({"obs_month": f"{year}-{MON[r[2].strip()]:02d}", "net_yen_bn": round(net_bn, 1),
                    "rolling12_yen_bn": round(sum(roll), 1) if len(roll) == 12 else "",
                    "source_url": URL, "source_doc": "MOF, Purchases and Sales of Foreign Securities by "
                    "Residents by Types of Investors (Long-term debt securities), 生命保険会社, net",
                    "vintage": vintage.replace("Final Update", "").strip()})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    by = {}
    for o in out:
        by[o["obs_month"][:4]] = by.get(o["obs_month"][:4], 0) + o["net_yen_bn"]
    print(f"-> {OUT.relative_to(ROOT)}  {len(out)} months, {out[0]['obs_month']} to {out[-1]['obs_month']}")
    print("   by year, yen tn: " + "  ".join(f"{y}:{v / 1000:+.1f}" for y, v in sorted(by.items()) if y >= "2016"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
