#!/usr/bin/env python3
"""Stage 3 Fubon: extract the hedging page from Fubon FHC results decks.

Corpus: config/fubon_conference_decks.json (fubon.irpro.co conference archive,
2007->2026), files cached under cache/fubon/. Every deck since 2006 carries a
Fubon Life hedging page; this pass targets the eras from 2011 on, where the
page shows a recurring-hedge-cost bar chart with its own period labels and a
hedge-composition pie.

Bindings are in-document only (decisions 3.14 — text order and proximity both
mislead):
  - cost: the page's run of "-?N bps" tokens pairs positionally with the run
    of period tokens (1Q21/2020/1H26...); the deck's own period is the last
    label. Adjacent label-bps pairs ("1Q26 -126bps") are used when present.
  - pie: captions that print as "caption, 12.3%" bind by that comma; the
    2026-era layout (separate wedge labels) instead uses the page note
    ("Naked USD 59.1% + other currencies 1.8%" = the 60.9% wedge) plus the
    sum-to-100 identity.
  - validity: pie must sum to 100 +/- 0.5; every deck for the same period
    must agree with its siblings (CH/EN and conference duplicates).

Emits data/fubon_deck_fx.csv, one row per (period, event, file).
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
OUT_CSV = ROOT / "data" / "fubon_deck_fx.csv"

PERIOD = r"(?:[1-4]Q\d{2}|1H\d{2}|9M\d{2}|20\d{2})"

# canonical pie categories, matched on normalised caption text
PIE_KEYS = [
    ("cs_ndf_policy_pct", ("外匯交換、無本金遠期外匯、外幣保單", "完全避險",
                           "Currency swap, NDF, FX policy", "Fully hedged")),
    ("cs_ndf_pct", ("外匯交換、無本金遠期外匯", "Currency swap, NDF")),
    ("naked_usd_pct", ("美元部位", "Naked USD")),
    ("naked_other_pct", ("其他幣別部位", "其他幣別", "Other currencies")),
    ("naked_usd_other_pct", ("未避險美元及其他幣別", "Naked USD and other currencies")),
    ("equity_fund_pct", ("股票/共同基金", "Equity/mutual fund", "Equity / mutual fund",
                         "Equities & funds")),
    ("fvoci_equity_pct", ("FVOCI股票與基金", "Equities & funds in FVOCI")),
    ("fvtpl_equity_pct", ("FVTPL股票與基金", "Equities & funds in FVTPL")),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def canon_key(caption: str):
    c = norm(caption)
    for key, pats in PIE_KEYS:
        for p in pats:
            if norm(p) in c or c in norm(p):
                return key
    return None


def find_hedge_page(doc):
    best, best_score = None, 0
    for i, page in enumerate(doc):
        t = page.get_text()
        score = 0
        if "避險成本" in t or "Hedging Cost" in t or "Hedging cost" in t:
            score += 2
        if "bps" in t:
            score += 2
        if any(k in t for k in ("避險組合", "避險結構", "Hedging composition",
                                "Hedging portfolio")):
            score += 1
        if "外價金" in t or "FX reserve" in t:
            score += 1
        score += min(3, len(re.findall(r"-?\d{1,3}\s*bps", t)))
        if i < 4:
            score -= 2
        if score > best_score:
            best, best_score = i, score
    return best


def period_rank(p: str):
    """Sortable (year, end_month, cumulative) for tokens like 1Q21/1H26/9M17/2020."""
    if re.fullmatch(r"20\d\d", p):
        return (int(p), 12, 1)
    m = re.fullmatch(r"([1-4])Q(\d\d)", p)
    if m:
        return (2000 + int(m.group(2)), int(m.group(1)) * 3, 0)
    m = re.fullmatch(r"1H(\d\d)", p)
    if m:
        return (2000 + int(m.group(1)), 6, 1)
    m = re.fullmatch(r"9M(\d\d)", p)
    if m:
        return (2000 + int(m.group(1)), 9, 1)
    return (0, 0, 0)


def merged_words(page):
    """Words with split "-N" + "bps" tokens merged into "-Nbps"."""
    ws = [(x0, y0, x1, y1, w) for x0, y0, x1, y1, w, *_ in page.get_text("words")]
    out = []
    skip = set()
    for i, (x0, y0, x1, y1, w) in enumerate(ws):
        if i in skip:
            continue
        if re.fullmatch(r"[+-]?\d{1,3}", w):
            for j, (a0, b0, a1, b1, w2) in enumerate(ws):
                if j != i and w2 in ("bps", "bps)") and abs(a0 - x0) < 30 and abs(b0 - y0) < 30:
                    out.append((x0, y0, x1, y1, w + "bps"))
                    skip.add(j)
                    break
            else:
                out.append((x0, y0, x1, y1, w))
        else:
            out.append((x0, y0, x1, y1, w))
    return out


def cost_by_geometry(page):
    """Bind each bps token to its nearest period label (Euclidean, capped):
    every observed layout prints the label adjacent to its value — above,
    below, or beside. Global greedy assignment by distance; a page whose
    labels sit far from the values (the 2011-13 horizontal multi-column
    tables) binds nothing and is reported, not guessed."""
    ws = merged_words(page)
    bps = [((x0 + x1) / 2, (y0 + y1) / 2, int(m.group(1)))
           for x0, y0, x1, y1, w in ws
           if (m := re.fullmatch(r"([+-]?\d{1,3})bps", w))]
    pers = [((x0 + x1) / 2, (y0 + y1) / 2, w)
            for x0, y0, x1, y1, w in ws if re.fullmatch(PERIOD, w)]
    cands = sorted(
        (((bx - px) ** 2 + (by - py) ** 2) ** 0.5, bi, pi)
        for bi, (bx, by, _) in enumerate(bps)
        for pi, (px, py, _) in enumerate(pers))
    series, coords, ub, up = {}, {}, set(), set()
    for dist, bi, pi in cands:
        if dist > 80 or bi in ub or pi in up:
            continue
        ub.add(bi)
        up.add(pi)
        p = pers[pi][2]
        if p not in series:
            series[p] = bps[bi][2]
            coords[p] = (pers[pi][0], pers[pi][1])
    comps = {}
    nums = [((x0 + x1) / 2, (y0 + y1) / 2, int(w))
            for x0, y0, x1, y1, w in ws
            if re.fullmatch(r"[+-]?\d{1,3}", w) and w not in ("0",)]
    for p, (pcx, pcy) in coords.items():
        # in-bar component labels print in the bar under its period label
        # (PDF y grows downward); keep a bounded band to avoid axis clutter
        col = [v for ncx, ncy, v in nums if abs(ncx - pcx) < 30 and pcy < ncy < pcy + 130]
        comps[p] = col
    multi = len(bps) > len(ub) and bool(series)
    return series, comps, multi


def extract_page(text: str, page=None) -> dict:
    out = {}
    if "Implied hedging cost" in text or "TWD/USD swap points" in text:
        out["era"] = "A_table"
        return out
    series, comps, multi = cost_by_geometry(page) if page is not None else ({}, {}, False)
    if series:
        cur = max(series, key=period_rank)
        out["cost_series"] = series
        out["period"] = cur
        out["total_fx_cost_bps"] = series[cur]
        if multi:
            # some bps tokens stayed unbound: extra series on the page
            out["cost_ambiguous"] = True
        c = comps.get(cur, [])
        # the stacked components of the current bar must sum to the headline
        # (sign conventions vary: some eras print the total unsigned)
        if c and abs(abs(sum(c)) - abs(series[cur])) <= 2:
            out["cost_components"] = sorted(c)
            out["components_ok"] = True
        elif c:
            out["components_ok"] = False

    # --- pie: comma-bound caption/pct pairs (captions may wrap across lines)
    flat = re.sub(r"\s*\n\s*", "", text)
    for m in re.finditer(r"([^,%\d]{2,40})[,，]\s*(\d{1,2}\.\d)%", flat):
        key = canon_key(m.group(1))
        if key:
            out.setdefault("pie", {})[key] = float(m.group(2))

    # --- 2026-era: separate wedge labels; use the note identity
    if "pie" not in out or len(out.get("pie", {})) < 3:
        note = re.search(
            r"美元部位約(\d{1,2}\.\d)%、其他幣別約(\d{1,2}\.\d)%|"
            r"Naked USD account for (\d{1,2}\.\d)% and other currencies account for (\d{1,2}\.\d)%",
            flat)
        if note:
            g = [x for x in note.groups() if x]
            naked = round(float(g[0]) + float(g[1]), 1)
            pcts = [float(x) for x in re.findall(r"(\d{1,2}\.\d)%", text)]
            if naked in pcts:
                pie = {"naked_usd_other_pct": naked}
                # remaining wedges: captions and pcts by canonical presence
                for key, pats in PIE_KEYS:
                    if key == "naked_usd_other_pct":
                        continue
                    for p in pats:
                        if norm(p) in norm(text):
                            pie[key] = None  # present, value bound below
                # bind leftover: 2026 layout prints caption then its pct nearby
                for m2 in re.finditer(r"(FVOCI股票與基金|FVTPL股票與基金|Equities & funds\s*in FVOCI|Equities & funds\s*in FVTPL)\s*\n\s*(\d{1,2}\.\d)%", text):
                    k = canon_key(m2.group(1))
                    if k:
                        pie[k] = float(m2.group(2))
                known = [v for v in pie.values() if v is not None]
                if "cs_ndf_pct" in pie and pie["cs_ndf_pct"] is None and len(known) == len(pie) - 1:
                    pie["cs_ndf_pct"] = round(100 - sum(known), 1)
                out["pie"] = {k: v for k, v in pie.items() if v is not None}
                out["pie_bound_by"] = "note_identity"

    if "pie" in out:
        s = sum(out["pie"].values())
        out["pie_sum_ok"] = abs(s - 100) <= 0.5
    # --- FX-risk asset split (bond vs equity of FX financial assets)
    m = re.search(r"(?:債券部位|Bond and cash)\D{0,20}?(\d{1,2}\.\d)%", flat)
    if m:
        out["fx_assets_bond_pct"] = float(m.group(1))
    # --- FX volatility/price reserve balance, later eras
    m = re.search(r"(?:外價金|外匯準備金)?餘額達?NT\$([\d,]+(?:\.\d)?)(億|bn)|FX reserve accumulated to NT\$([\d,]+\.?\d?)bn", flat)
    if m:
        g = m.groups()
        if g[0]:
            v = float(g[0].replace(",", ""))
            out["fx_reserve_ntd_bn"] = v / 10 if g[1] == "億" else v
        elif g[2]:
            out["fx_reserve_ntd_bn"] = float(g[2].replace(",", ""))
    return out


def main():
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    rows = []
    problems = []
    seen_files = set()
    for e in idx:
        matches = list(CACHE.glob(f"ev{e['event_id']}_{e['lang']}_*"))
        if not matches:
            continue
        if e["year"] <= 2010:
            # era A/B: table layouts and bare-year YTD labels that collide
            # across editions; a later pass handles them explicitly
            continue
        fn = matches[0]
        if fn.name in seen_files:
            continue
        seen_files.add(fn.name)
        try:
            doc = pymupdf.open(fn)
        except Exception as ex:
            problems.append(f"{fn.name}: open failed {ex}")
            continue
        pg = find_hedge_page(doc)
        if pg is None:
            problems.append(f"{fn.name}: no hedge page")
            doc.close()
            continue
        got = extract_page(doc[pg].get_text(), page=doc[pg])
        doc.close()
        if got.get("era") == "A_table":
            problems.append(f"{fn.name}: era-A table layout, out of scope this pass")
            continue
        if "period" not in got:
            problems.append(f"{fn.name}: no cost/period parse (p{pg})")
            continue
        if period_rank(got["period"]) <= (2010, 12, 1):
            continue  # era A/B editions indexed under a later conference year
        row = {"event_id": e["event_id"], "lang": e["lang"], "year": e["year"],
               "url": e["url"], "page": pg + 1, "period": got["period"],
               "total_fx_cost_bps": got.get("total_fx_cost_bps"),
               "cost_ambiguous": got.get("cost_ambiguous"),
               "cost_components": json.dumps(got.get("cost_components", [])),
               "components_ok": got.get("components_ok"),
               "cost_series": json.dumps(got.get("cost_series", {}), ensure_ascii=False),
               "fx_assets_bond_pct": got.get("fx_assets_bond_pct"),
               "fx_reserve_ntd_bn": got.get("fx_reserve_ntd_bn"),
               "pie_sum_ok": got.get("pie_sum_ok"),
               "pie_bound_by": got.get("pie_bound_by", "comma_adjacency"),
               }
        for key, _ in PIE_KEYS:
            row[key] = got.get("pie", {}).get(key)
        rows.append(row)

    # cross-deck series agreement: every deck that prints a period's bar must
    # agree with every other deck on its magnitude (signs are era conventions)
    series_conflicts = 0
    byper = defaultdict(set)
    for r in rows:
        for p, v in json.loads(r["cost_series"]).items():
            byper[p].add(v)
    for p, vals in byper.items():
        if len({abs(v) for v in vals}) > 1:
            series_conflicts += 1
            problems.append(f"period {p}: cost_series magnitudes disagree: {sorted(vals)}")

    # sibling agreement per period
    conflicts = 0
    byp = defaultdict(list)
    for r in rows:
        byp[r["period"]].append(r)
    for period, rs in byp.items():
        for col in ["total_fx_cost_bps"] + [k for k, _ in PIE_KEYS]:
            vals = {r[col] for r in rs if r[col] is not None}
            if len(vals) > 1:
                conflicts += 1
                problems.append(f"period {period}: {col} disagrees across decks: {sorted(vals)}")

    rows.sort(key=lambda r: (r["year"], r["period"], r["event_id"]))
    cols = list(rows[0].keys()) if rows else []
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"rows: {len(rows)} across {len(byp)} periods; conflicts: {conflicts}; "
          f"series conflicts: {series_conflicts}; problems: {len(problems)}")
    for p in problems[:30]:
        print("  PROBLEM", p)
    print(f"csv: {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
