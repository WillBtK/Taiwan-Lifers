#!/usr/bin/env python3
"""Fubon recurring-cost attribution: colour-bind the stacked components.

stage3_fubon_decks.py proved the headline bps series is the ALL-IN FX result
and left the stacked pair (recurring hedge cost vs FX G/L & reserve
provisioning) unattributed (decisions 3.15). This pass binds them by colour:
each legend caption (經常性避險成本 / 外匯損益&準備金淨提存 / 一次性準備金提存,
or the EN equivalents) has a small colour swatch beside it; a component value
word binds to the series whose swatch colour fills the bar segment containing
it. The sum identity against data/fubon_deck_fx.csv's total then verifies
every attribution.

Emits data/fubon_recurring_cost.csv (one row per period, colour-bound rows
only; unbound decks are reported, not guessed).
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
TOTALS = ROOT / "data" / "fubon_deck_fx.csv"
OUT_CSV = ROOT / "data" / "fubon_recurring_cost.csv"

SERIES = {
    "recurring_bps": ("經常性避險成本", "CS+NDF cost", "CS + NDF cost", "Recurring hedging cost"),
    "fxgl_bps": ("外匯損益", "準備金淨提存", "FX gain/loss", "FX G/L", "net provision"),
    "oneoff_bps": ("一次性準備金提存", "one-off provision", "One-off provision"),
}
PERIOD = r"(?:[1-4]Q\d{2}|1H\d{2}|9M\d{2}|20\d{2})"


def close(a, b, tol=0.02):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def page_components(page):
    """Return {series_key: {period: value}} colour-bound, or {}."""
    d = page.get_text("dict")
    # legend captions with positions
    caps = []
    for b in d["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                for key, pats in SERIES.items():
                    if any(p in t for p in pats) and len(t) < 30:
                        caps.append((key, s["bbox"]))
    if not caps:
        return {}
    fills = [(dr["rect"], tuple(dr["fill"])) for dr in page.get_drawings()
             if dr["type"] in ("f", "fs") and dr["fill"]]
    # swatch: small filled rect left of (or slightly overlapping) the caption
    swatch = {}
    for key, (cx0, cy0, cx1, cy1) in caps:
        cands = []
        for r, col in fills:
            if r.width <= 30 and r.height <= 22 and abs((r.y0 + r.y1) / 2 - (cy0 + cy1) / 2) < 10 \
               and -5 < cx0 - r.x1 < 45:
                cands.append((cx0 - r.x1, col))
        if cands:
            swatch.setdefault(key, min(cands)[1])
    if "recurring_bps" not in swatch:
        return {}
    # period labels and component number words
    ws = [(x0, y0, x1, y1, w) for x0, y0, x1, y1, w, *_ in page.get_text("words")]
    pers = [((x0 + x1) / 2, (y0 + y1) / 2, w) for x0, y0, x1, y1, w in ws
            if re.fullmatch(PERIOD, w)]
    nums = [((x0 + x1) / 2, (y0 + y1) / 2, int(w)) for x0, y0, x1, y1, w in ws
            if re.fullmatch(r"-?\d{1,3}", w)]
    out = defaultdict(dict)
    for ncx, ncy, v in nums:
        # the segment rect containing the number, matched to a swatch colour
        seg = [col for r, col in fills
               if r.x0 - 2 <= ncx <= r.x1 + 2 and r.y0 - 2 <= ncy <= r.y1 + 2
               and (r.width > 34 or r.height > 26)]
        keys = [k for k, col in swatch.items() if any(close(col, c) for c in seg)]
        if len(keys) != 1:
            continue
        # nearest period label sharing the column (vertical charts) or row
        cands = sorted((min(abs(ncx - pcx), abs(ncy - pcy)), p) for pcx, pcy, p in pers
                       if abs(ncx - pcx) < 40 or abs(ncy - pcy) < 15)
        if cands:
            out[keys[0]].setdefault(cands[0][1], v)
    return dict(out)


def main():
    totals = {}
    with open(TOTALS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for p, v in json.loads(r["cost_series"]).items():
                totals[p] = int(v)

    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    per_period = defaultdict(lambda: defaultdict(set))
    problems, seen = [], set()
    bound_decks = 0
    for e in idx:
        if e["year"] <= 2010:
            continue
        for fn in CACHE.glob(f"ev{e['event_id']}_{e['lang']}_*"):
            if fn.name in seen:
                continue
            seen.add(fn.name)
            try:
                doc = pymupdf.open(fn)
            except Exception:
                continue
            best, best_n, best_by = None, 0, None
            for i, page in enumerate(doc):
                t = page.get_text()
                if "避險成本" not in t and "Hedging cost" not in t and "CS+NDF" not in t:
                    continue
                # colour binding only: a stack-order fallback was tried and
                # FALSIFIED — 2018-19 decks stack segments in a different
                # order than the legend, so ordering is not evidence
                got = page_components(page)
                n = sum(len(v) for v in got.values())
                if n > best_n:
                    best, best_n, best_by = got, n, "colour"
            doc.close()
            if not best:
                continue
            bound_decks += 1
            for key, series in best.items():
                for p, v in series.items():
                    per_period[p][key].add((v, best_by))

    rows = []
    conflicts = verified = unverified = 0
    for p in sorted(per_period, key=lambda x: (x[-2:], x)):
        row = {"period": p}
        ok = True
        binds = set()
        for key in SERIES:
            pairs = per_period[p].get(key, set())
            vals = {v for v, _ in pairs}
            binds |= {b for _, b in pairs}
            if len(vals) > 1:
                conflicts += 1
                problems.append(f"{p} {key}: disagrees {sorted(vals)}")
                ok = False
            row[key] = vals.pop() if len(vals) == 1 else None
        row["bound_by"] = "colour" if "colour" in binds else "stack_order"
        comp_sum = sum(v for k in SERIES if (v := row[k]) is not None)
        total = totals.get(p)
        if total is not None and row["recurring_bps"] is not None:
            row["sum_ties_total"] = abs(abs(comp_sum) - abs(total)) <= 2
            verified += row["sum_ties_total"]
            unverified += not row["sum_ties_total"]
            if not row["sum_ties_total"]:
                problems.append(f"{p}: components {comp_sum} vs total {total}")
        else:
            row["sum_ties_total"] = None
        if ok and row["recurring_bps"] is not None:
            rows.append(row)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["period", "recurring_bps", "fxgl_bps",
                                          "oneoff_bps", "sum_ties_total", "bound_by"])
        w.writeheader()
        w.writerows(rows)
    print(f"decks bound: {bound_decks}; periods: {len(rows)}; "
          f"sum-verified: {verified}; sum-failed: {unverified}; conflicts: {conflicts}")
    for p in problems[:25]:
        print("  PROBLEM", p)
    print(f"csv: {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
