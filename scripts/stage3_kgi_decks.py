#!/usr/bin/env python3
"""Stage 3 KGI: extract KGI Life investment-performance pages from CDF/KGI
Financial results decks (config/kgi_conference_decks.json, cache/kgi/).

The KGI-era layout (2023->) puts four blocks on one page — pre-hedging
recurring yield (%), hedging cost (%), FX reserve balance (NT$ bn), hedging
structure (pie) — each a small bar chart whose value prints directly above
its period label at the same x. Binding is therefore block-scoped x-pairing:
a chart's values pair with the labels sharing their x within the block's
x-range, never across blocks. Period labels print split ("1H" "26"), merged
before matching.

The deck's own period comes from the title ("1H 2026 Performance Review" /
"FY 2024 營運報告"). Sibling decks (CH/EN, conference duplicates) must agree
on every shared figure. Emits data/kgi_deck_fx.csv.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "kgi"
INDEX = ROOT / "config" / "kgi_conference_decks.json"
OUT_CSV = ROOT / "data" / "kgi_deck_fx.csv"

BLOCKS = {
    "yield_pre_hedge_pct": ("Pre-Hedging Recurring Yield", "避險前經常性收益率"),
    "hedging_cost_pct": ("Hedging Cost", "避險成本"),
    "fx_reserve_ntd_bn": ("FX Reserve Balance", "外匯價格變動準備金", "外匯準備金餘額", "外價金餘額"),
}
PIE_KEYS = [
    ("cs_ndf_pct", ("Currency swap & NDF", "外匯交換及無本金遠期外匯", "換匯及無本金遠期外匯")),
    ("naked_usd_other_pct", ("USD & other currency", "美元及其他幣別")),
    ("overseas_equity_pct", ("Overseas equity", "國外權益", "海外股票")),
    ("fx_risk_pct", ("FX risk exposure", "具外匯風險資產", "具外匯風險")),
    ("fx_policy_pct", ("FX policy", "外幣保單")),
]


def norm(s):
    return re.sub(r"\s+", "", s)


def merged_period_words(ws):
    """Merge split '1H'+'25' / '1H'+'2026' style label pairs."""
    out, skip = [], set()
    for i, (x0, y0, x1, y1, w) in enumerate(ws):
        if i in skip:
            continue
        if w in ("1H", "9M") or re.fullmatch(r"[1-4]Q", w):
            for j, (a0, b0, a1, b1, w2) in enumerate(ws):
                if j != i and re.fullmatch(r"\d\d(\d\d)?", w2) and 0 <= a0 - x1 < 15 and abs(b0 - y0) < 6:
                    out.append((x0, y0, a1, b1, w + w2[-2:]))
                    skip.add(j)
                    break
            else:
                out.append((x0, y0, x1, y1, w))
        else:
            out.append((x0, y0, x1, y1, w))
    return out


def deck_period(doc):
    for i in range(min(4, len(doc))):
        t = doc[i].get_text()
        m = re.search(r"(FY|1H|9M|[1-4]Q)\s?(20\d\d)", t)
        if m:
            tag, y = m.group(1), m.group(2)[-2:]
            return f"{y}" + "" if tag == "FY" else (f"20{y}" if tag == "FY" else f"{tag}{y}")
    return None


def find_page(doc):
    best, score_best = None, 0
    for i, pg in enumerate(doc):
        t = pg.get_text()
        s = 0
        s += 2 * sum(1 for pats in BLOCKS.values() for p in pats if p in t)
        if "Hedging Structure" in t or "避險結構" in t:
            s += 2
        if s > score_best:
            best, score_best = i, s
    return best


def extract(doc, pg):
    page = doc[pg]
    raw = [(x0, y0, x1, y1, w) for x0, y0, x1, y1, w, *_ in page.get_text("words")]
    ws = merged_period_words(raw)
    text = page.get_text()
    out = {}

    # locate block titles as x-anchors: a block owns x within +/-160 of title
    titles = {}
    d = page.get_text("dict")
    for b in d["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                def is_caption(txt, p):
                    # caption = the pattern plus at most a units suffix;
                    # prose that continues ("避險成本為1.53%...") must not anchor
                    t = txt.strip()
                    if not t.startswith(p):
                        return False
                    rest = t[len(p):]
                    return all(c in "()%（）新臺幣十億元bnNT$ .0-9-：:" or c.isdigit() for c in rest)

                for key, pats in BLOCKS.items():
                    if any(is_caption(s["text"], p) for p in pats):
                        x0, y0, x1, y1 = s["bbox"]
                        titles.setdefault(key, (x0, (y0 + y1) / 2))

    labels = [(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2, w) for x0, y0, x1, y1, w in ws
              if re.fullmatch(r"[1-4]Q\d\d|1H\d\d|9M\d\d|20\d\d", w)]
    values = [(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2, float(w)) for x0, y0, x1, y1, w in ws
              if re.fullmatch(r"-?\d{1,3}\.\d{1,2}", w)]

    def nearest_title(cx, cy):
        # captions are left-aligned and each chart hangs BELOW its caption, so
        # a word belongs to the rightmost caption starting left of it and,
        # within that column, to the nearest caption ABOVE it. Splitting the
        # column by absolute vertical distance instead is wrong: the shared
        # period-label row of a 2x2 grid sits closer to the lower caption than
        # to the upper chart it actually labels, which starved the upper block
        # of labels entirely.
        left = [k for k in titles if titles[k][0] <= cx + 20]
        if not left:
            return min(titles, key=lambda k: abs(titles[k][0] - cx)) if titles else None
        best_x = max(titles[k][0] for k in left)
        col = [k for k in left if titles[k][0] == best_x]
        above = [k for k in col if titles[k][1] <= cy]
        return max(above, key=lambda k: titles[k][1]) if above \
            else min(col, key=lambda k: titles[k][1])

    for key, (tx, ty) in titles.items():
        # captions sit above the chart in some vintages, below in others: try
        # both vertical bands; a word belongs to a block only if this title is
        # its NEAREST title horizontally (the grid partitions the page)
        best = {}
        for lo, hi in ((ty, ty + 230),):
            blk_labels = [l for l in labels
                          if lo < l[3] < hi and nearest_title(l[2], l[3]) == key]
            blk_values = [v for v in values
                          if lo < v[3] < hi and nearest_title(v[2], v[3]) == key]
            series = {}
            for lx0, ly0, lcx, lcy, lab in blk_labels:
                cands = sorted((abs(vcx - lcx), v) for _, _, vcx, vcy, v in blk_values
                               if abs(vcx - lcx) < 25 and vcy < lcy)
                if cands:
                    series[lab] = cands[0][1]
            if len(series) > len(best):
                best = series
        if best:
            out[key + "_series"] = best

    # pie: caption spans bound to nearest N% word
    pcts = [(x0, y0, (x0 + x1) / 2, (y0 + y1) / 2, float(w[:-1])) for x0, y0, x1, y1, w in ws
            if re.fullmatch(r"\d{1,2}%", w)]
    for b in d["blocks"]:
        for l in b.get("lines", []):
            span_text = norm("".join(s["text"] for s in l["spans"]))
            for key, pats in PIE_KEYS:
                if any(norm(p) in span_text for p in pats) and key not in out:
                    x0, y0, x1, y1 = l["bbox"]
                    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                    cands = sorted((( (vcx - cx) ** 2 + (vcy - cy) ** 2) ** 0.5, v)
                                   for _, _, vcx, vcy, v in pcts)
                    if cands and cands[0][0] < 120:
                        out[key] = cands[0][1]
    return out


def main():
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    rows, problems, seen = [], [], set()
    for e in idx:
        matches = list(CACHE.glob(f"ev{e['event_id']}_{e['lang']}_*"))
        for fn in matches:
            if fn.name in seen:
                continue
            seen.add(fn.name)
            try:
                doc = pymupdf.open(fn)
            except Exception as ex:
                problems.append(f"{fn.name}: open failed {ex}")
                continue
            pg = find_page(doc)
            if pg is None:
                doc.close()
                continue
            got = extract(doc, pg)
            period = deck_period(doc)
            doc.close()
            if not any(k.endswith("_series") for k in got):
                continue
            row = {"event_id": e["event_id"], "lang": e["lang"], "url": e["url"],
                   "page": pg + 1, "deck_period": period}
            for key in BLOCKS:
                row[key + "_series"] = json.dumps(got.get(key + "_series", {}), ensure_ascii=False)
            for key, _ in PIE_KEYS:
                row[key] = got.get(key)
            rows.append(row)

    # cross-deck series agreement
    conflicts = 0
    for key in BLOCKS:
        agg = defaultdict(set)
        for r in rows:
            for p, v in json.loads(r[key + "_series"]).items():
                agg[p].add(v)
        for p, vals in agg.items():
            if len(vals) > 1:
                conflicts += 1
                problems.append(f"{key} {p}: disagrees {sorted(vals)}")

    rows.sort(key=lambda r: r["event_id"])
    if rows:
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"rows: {len(rows)}; conflicts: {conflicts}; problems: {len(problems)}")
    for p in problems[:25]:
        print("  PROBLEM", p)
    print(f"csv: {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
