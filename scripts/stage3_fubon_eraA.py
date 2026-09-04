#!/usr/bin/env python3
"""Fubon era-A backfill: the 2006-2010 'Fubon Life - Hedging Cost' tables.

These decks print a rotated table: a period column (2005, 2006, 1Q 2006, ...)
and value columns at fixed x — Hedging Cost NT$bn, 'In basis points', the
TWD/USD 1Y swap points, and 'Implied hedging cost (period-end)'. This pass
extracts the booked cost in bps.

Sign discipline: decks flip convention (ev15 prints costs unsigned, ev21
prints them negative, and the 2009 decks mix signs because hedging genuinely
flipped to a GAIN when swap points inverted). The in-document normaliser is
the implied-cost reference column: it is a market cost by construction, so
its printed sign gives the deck's convention, and every booked value is
flipped to cost-negative accordingly. Cross-deck agreement (post-
normalisation) must then hold on every shared period.

Scope: the simple single-table decks (2006 -> 1Q07 editions) only. The
2008-2010 decks print SIDE-BY-SIDE PANELS per entity (Fubon Life vs the
newly acquired ING Antai book) with several hedging columns each; entity
attribution there needs its own evidence and the analytic value is modest,
so they are out of scope, not guessed.

Emits data/fubon_eraA_cost.csv (period, hedging_cost_bps cost-negative,
implied_cost_bps).
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "fubon"
INDEX = ROOT / "config" / "fubon_conference_decks.json"
OUT_CSV = ROOT / "data" / "fubon_eraA_cost.csv"


def merge_bps(ws):
    """Rotated pages split 'N' and 'bps' vertically; merge by same-x pairs."""
    out, skip = [], set()
    for i, (x0, y0, x1, y1, w) in enumerate(ws):
        if i in skip:
            continue
        if re.fullmatch(r"-?\d{1,3}", w):
            for j, (a0, b0, a1, b1, w2) in enumerate(ws):
                if j != i and w2 in ("bps", "bps)") and abs(a0 - x0) < 12 and 0 < y0 - b1 < 30:
                    out.append((x0, b0, x1, y1, w + "bps"))
                    skip.add(j)
                    break
            else:
                out.append((x0, y0, x1, y1, w))
        else:
            out.append((x0, y0, x1, y1, w))
    return out


def parse_page(page):
    ws = merge_bps([(x0, y0, x1, y1, w) for x0, y0, x1, y1, w, *_ in page.get_text("words")])
    # period rows: quarter tokens pair with the year printed below them
    years = [(x0, (y0 + y1) / 2, w) for x0, y0, x1, y1, w in ws
             if re.fullmatch(r"20\d\d", w) and x0 < 215]
    quarters = [(x0, (y0 + y1) / 2, w) for x0, y0, x1, y1, w in ws
                if re.fullmatch(r"[1-4]Q", w) and x0 < 215]
    used_years = set()
    rows = []  # (ycentre, period)
    for qx, qy, q in quarters:
        cands = sorted((abs(qy - yy - 30), i) for i, (yx, yy, yw) in enumerate(years)
                       if i not in used_years and 5 < qy - yy < 60)
        if cands:
            i = cands[0][1]
            used_years.add(i)
            rows.append(((qy + years[i][1]) / 2, f"{q}{years[i][2][-2:]}"))
    for i, (yx, yy, yw) in enumerate(years):
        if i not in used_years:
            rows.append((yy, yw))
    bps = [(x0, (y0 + y1) / 2, int(m.group(1))) for x0, y0, x1, y1, w in ws
           if (m := re.fullmatch(r"(-?\d{1,3})bps", w))]
    booked = [b for b in bps if 245 < b[0] < 300]
    implied = [b for b in bps if 375 < b[0] < 420]
    if not booked or not implied:
        return {}
    # convention from the implied column: costs printed negative or positive
    neg = sum(1 for _, _, v in implied if v < 0)
    sign = -1 if neg <= len(implied) / 2 else 1  # multiply to get cost-negative
    out = {}
    for ry, p in rows:
        bk = sorted((abs(by - ry), v) for _, by, v in booked if abs(by - ry) < 22)
        im = sorted((abs(by - ry), v) for _, by, v in implied if abs(by - ry) < 22)
        if bk:
            out[p] = {"booked": bk[0][1] * sign,
                      "implied": im[0][1] * sign if im else None}
    return out


def main():
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    agg = defaultdict(lambda: defaultdict(set))
    seen, decks = set(), 0
    for e in idx:
        for fn in CACHE.glob(f"ev{e['event_id']}_{e['lang']}_*"):
            if fn.name in seen:
                continue
            seen.add(fn.name)
            try:
                doc = pymupdf.open(fn)
            except Exception:
                continue
            for page in doc:
                t = page.get_text()
                if "Implied hedging cost" not in t:
                    continue
                got = parse_page(page)
                if got:
                    decks += 1
                    for p, v in got.items():
                        agg[p]["booked"].add(v["booked"])
                        if v["implied"] is not None:
                            agg[p]["implied"].add(v["implied"])
                break
            doc.close()
    rows, problems = [], []
    for p in sorted(agg, key=lambda x: (x[-2:] if not x.startswith("20") else x[2:], x)):
        b, im = agg[p]["booked"], agg[p]["implied"]
        if len(b) > 1:
            problems.append(f"{p}: booked disagrees {sorted(b)}")
            continue
        rows.append({"period": p, "hedging_cost_bps": b.pop(),
                     "implied_cost_bps": im.pop() if len(im) == 1 else None})
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["period", "hedging_cost_bps", "implied_cost_bps"])
        w.writeheader()
        w.writerows(rows)
    print(f"decks parsed: {decks}; periods: {len(rows)}; problems: {len(problems)}")
    for p in problems[:20]:
        print("  PROBLEM", p)
    print(f"csv: {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
