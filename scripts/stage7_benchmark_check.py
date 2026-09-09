#!/usr/bin/env python3
"""How closely the independently-sourced pie reproduces the sell-side workbook.

The workbook is a BENCHMARK and never an input: nothing in this project reads
data/benchmark_jpm_hedging_structure.csv into a series. Its only use is this —
to say, cell by cell, whether reading the companies' own disclosures gets the
same answer as a desk that rings the IR teams and asks.

Four columns are comparable, because they are the four the pie decomposes into:
traditional hedge, FX policy, proxy/naked and equity & fund, each as a percent
of total overseas investment. The currency-swap versus NDF split inside the
first is NOT comparable and never will be from public disclosure — no company
publishes it; the sell-side gets it by asking.

Run: python3 scripts/stage7_benchmark_check.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MINE = ROOT / "data" / "deck_pie.csv"
THEIRS = ROOT / "data" / "benchmark_jpm_hedging_structure.csv"

PAIRS = [("traditional_hedge_pct", "hedged_pct", "hedge"),
         ("fx_policy_pct", "fx_policy_pct", "policy"),
         ("proxy_naked_pct", "naked_pct", "naked"),
         ("equity_fund_pct", "equity_pct", "equity")]
NAME = {"cathay_life": "Cathay", "kgi_life": "KGI",
        "taiwan_life": "Taiwan Life", "shinkong_life": "Shin Kong",
        "fubon_life": "Fubon"}


def main():
    if not (MINE.exists() and THEIRS.exists()):
        print("need both data/deck_pie.csv and the benchmark")
        return 1
    mine = {(r["entity_id"], r["as_of"]): r
            for r in csv.DictReader(open(MINE, newline="", encoding="utf-8"))}
    theirs = [r for r in csv.DictReader(open(THEIRS, newline="",
                                             encoding="utf-8"))]
    diffs = {k: [] for _, _, k in PAIRS}
    rows, missing = [], []
    for t in theirs:
        m = mine.get((t["entity_id"], t["as_of"]))
        if not m:
            missing.append((t["entity_id"], t["as_of"]))
            continue
        d = {}
        for tk, mk, label in PAIRS:
            if not t.get(tk) or m.get(mk) in (None, ""):
                continue
            gap = float(m[mk]) - float(t[tk])
            d[label] = gap
            diffs[label].append(abs(gap))
        rows.append((t["entity_id"], t["as_of"], d, m["source"]))

    print(f"{len(rows)} overlapping firm-quarters, "
          f"{len(missing)} of theirs not covered here\n")
    print(f"  {'firm':<12}{'as of':<12}{'hedge':>8}{'policy':>8}{'naked':>8}"
          f"{'equity':>8}   source")
    for e, d, gaps, src in sorted(rows, key=lambda r: (r[0], r[1])):
        cells = "".join(f"{gaps[k]:>+8.1f}" if k in gaps else f"{'-':>8}"
                        for _, _, k in PAIRS)
        print(f"  {NAME.get(e, e):<12}{d:<12}{cells}   {src}")
    print(f"\n  mean absolute difference, percentage points")
    for _, _, k in PAIRS:
        v = diffs[k]
        if v:
            print(f"    {k:<8}{sum(v) / len(v):>6.2f}  over {len(v)} cells, "
                  f"worst {max(v):.1f}")
    if missing:
        print("\n  in the workbook, not reproduced here:")
        for e, d in sorted(missing):
            print(f"    {NAME.get(e, e):<12}{d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
