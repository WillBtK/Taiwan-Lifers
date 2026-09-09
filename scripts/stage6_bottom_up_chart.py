#!/usr/bin/env python3
"""How far back the bottom-up FX hedge ratio actually goes.

The ratio is 傳統避險本金 over 國外投資, built firm by firm from primary
sources and never from a sector aggregate:

  Fubon, Nan Shan   statutory derivatives note, notionals that reconcile to the
                    filing's own printed 合計, over the Insurance Bureau's
                    國外投資 for the same firm
  Cathay, KGI       the company's own investor-deck FX pie, rescaled onto total
                    overseas investment (the deck states the hedge as a share of
                    the FX-risk-bearing portion only)

Only firms whose 統編 the project has verified are used. An earlier pass mapped
four more firms by guessing the identifier and produced hedge ratios of 1,534%
and 10,610% — a reminder that the denominator, not the numerator, is what
breaks this construction.

WHY THIS IS A PANEL AND NOT YET AN AGGREGATE
At no date do more than three of the ten insurers have a bottom-up ratio, and at
most dates it is one or two. The binding constraint is the DENOMINATOR: the
Bureau publishes 國外投資 per firm monthly, but this project holds it only at
scattered archived snapshots — four dates for Cathay, KGI and Nan Shan. Summing
a numerator across a changing set of firms and dividing by a matching changing
denominator would produce a line whose every move could be composition rather
than hedging. So the firms are drawn separately and the count is drawn beneath
them.

Run: python3 scripts/stage6_bottom_up_chart.py
"""
import csv
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data" / "firm_hedge_panel.csv"
STRUCT = ROOT / "data" / "hedging_structure.csv"
WAYBACK = ROOT / "data" / "firm_fund_utilisation_wayback.csv"
FUNDS = ROOT / "data" / "ib_firm_funds.csv"
OUT = ROOT / "data" / "bottom_up_hedge_ratio_panel.csv"
SVG = ROOT / "reports" / "bottom_up_hedge_ratio.svg"
PNG = ROOT / "reports" / "bottom_up_hedge_ratio.png"

# config/firm_uids.tsv only. Nothing inferred.
UID = {"27935073": "fubon_life", "03374707": "cathay_life",
       "11456006": "nanshan_life", "03434016": "kgi_life",
       "03557017": "taiwan_life"}
NAME = {"cathay_life": "Cathay", "fubon_life": "Fubon", "kgi_life": "KGI",
        "nanshan_life": "Nan Shan"}
COL = {"cathay_life": "#1b4965", "fubon_life": "#bc4749",
       "kgi_life": "#2f6d4f", "nanshan_life": "#8a6d3b"}
SRC = {"cathay_life": "deck", "kgi_life": "deck",
       "fubon_life": "filing", "nanshan_life": "filing"}

INK, MUTE, GRID = "#1c1c1c", "#6b6b6b", "#e2e0dc"


def months(d):
    return int(d[:4]) * 12 + int(d[5:7])


def foreign_investment():
    fi = collections.defaultdict(dict)
    if WAYBACK.exists():
        for r in csv.DictReader(open(WAYBACK, newline="", encoding="utf-8")):
            e = UID.get(r.get("uid"))
            if e and r["item"] == "國外投資":
                fi[e][r["as_of"][:7]] = float(r["amount_ntd_k"]) / 1e6
    if FUNDS.exists():
        for r in csv.DictReader(open(FUNDS, newline="", encoding="utf-8")):
            e = UID.get(r.get("uid"))
            if e and r.get("foreign_investment"):
                # the Bureau states this table in 百萬元
                fi[e][r["obs_date"][:7]] = float(r["foreign_investment"]) / 1e3
    return fi


def build():
    fi = foreign_investment()

    def near(e, d, maxm=6):
        ks = sorted(fi.get(e, {}))
        if not ks:
            return None
        b = min(ks, key=lambda k: abs(months(k + "-01") - months(d)))
        return fi[e][b] if abs(months(b + "-01") - months(d)) <= maxm else None

    ser = collections.defaultdict(dict)
    if PANEL.exists():
        for r in csv.DictReader(open(PANEL, newline="", encoding="utf-8")):
            e = r["entity_id"]
            if e not in UID.values():
                continue
            f = near(e, r["as_of"])
            if f:
                ser[e][r["as_of"]] = (float(r["traditional_notional_ntd_k"])
                                      / 1e6 / f)
    if STRUCT.exists():
        for r in csv.DictReader(open(STRUCT, newline="", encoding="utf-8")):
            if r["traditional_hedge_pct"]:
                ser[r["entity_id"]][r["as_of"]] = \
                    float(r["traditional_hedge_pct"]) / 100
    return {e: v for e, v in ser.items() if e in NAME}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, size=11, fill=INK, anchor="start", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" '
            f'font-family="Georgia,\'Times New Roman\',serif">{esc(s)}</text>')


def main():
    ser = build()
    if not ser:
        print("no bottom-up ratio could be built")
        return 1
    dates = sorted({d for v in ser.values() for d in v})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["entity_id", "as_of", "hedge_ratio", "source"])
        for e in sorted(ser):
            for d in sorted(ser[e]):
                w.writerow([e, d, round(ser[e][d], 5), SRC[e]])
    n_at = {d: sum(1 for e in ser if d in ser[e]) for d in dates}

    W, H = 1180, 650
    L, R, TOP, BOT = 78, 1108, 108, 452
    STRIP = 545                       # firm-count strip baseline
    m0, m1 = months(dates[0]), months(dates[-1])

    def xs(d):
        return L + (months(d) - m0) / (m1 - m0) * (R - L)

    def ys(v):
        return BOT - v / 0.60 * (BOT - TOP)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="#faf9f7"/>']
    o.append(txt(L, 38, "The bottom-up FX hedge ratio begins 2018-12-31",
                 19, INK, weight="bold"))
    o.append(txt(L, 60, "Traditional hedge notional over overseas investment, "
                        "built firm by firm. Two firms from the statutory "
                        "derivatives note,", 11.5, MUTE))
    o.append(txt(L, 76, "two from the company's own investor deck. No sector "
                        "aggregate is used anywhere in the construction.",
                 11.5, MUTE))

    for g in range(0, 61, 10):
        y = ys(g / 100)
        o.append(f'<line x1="{L}" y1="{y:.1f}" x2="{R}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        o.append(txt(L - 10, y + 4, f"{g}%", 10.5, MUTE, "end"))
    for yr in range(2019, 2027):
        x = xs(f"{yr}-01-01")
        if L <= x <= R:
            o.append(txt(x, BOT + 18, str(yr), 10.5, MUTE, "middle"))
    o.append(f'<line x1="{L}" y1="{BOT}" x2="{R}" y2="{BOT}" '
             f'stroke="{INK}" stroke-width="1"/>')

    # Sparse, irregular observations: markers carry the data, the connecting
    # line is thin and dashed so it never reads as a measured path between them.
    taken = []
    for e in sorted(ser, key=lambda k: -max(ser[k].values())):
        pts = sorted(ser[e].items())
        o.append('<polyline points="'
                 + " ".join(f"{xs(d):.1f},{ys(v):.1f}" for d, v in pts)
                 + f'" fill="none" stroke="{COL[e]}" stroke-width="1.4" '
                 f'stroke-dasharray="4 3" opacity="0.75"/>')
        for d, v in pts:
            o.append(f'<circle cx="{xs(d):.1f}" cy="{ys(v):.1f}" r="3.4" '
                     f'fill="{COL[e]}"/>')
        ld, lv = pts[-1]
        y = ys(lv) + 4
        while any(abs(y - t) < 14 for t in taken):
            y += 14                      # Cathay and KGI both end near 27%
        taken.append(y)
        o.append(txt(xs(ld) + 9, y, NAME[e], 11.5, COL[e], "start", "bold"))
    # first observation, called out because it is the answer to the question
    fe = min(ser, key=lambda k: min(ser[k]))
    fd = min(ser[fe])
    o.append(f'<circle cx="{xs(fd):.1f}" cy="{ys(ser[fe][fd]):.1f}" r="7" '
             f'fill="none" stroke="{INK}" stroke-width="1.2"/>')
    o.append(txt(xs(fd) + 12, ys(ser[fe][fd]) - 12,
                 f"first observation  {fd}", 10.5, INK))

    # how many firms stand behind each point
    o.append(txt(L, STRIP - 34, "Firms with a bottom-up ratio at each date",
                 12, INK, weight="bold"))
    o.append(txt(L, STRIP - 18, "Ten insurers make up the sector. The limit is "
                                "the DENOMINATOR — per-firm overseas "
                                "investment is published monthly but held here "
                                "only at archived snapshots.", 10.5, MUTE))
    for d in dates:
        n = n_at[d]
        o.append(f'<rect x="{xs(d) - 3:.1f}" y="{STRIP - n * 11:.1f}" '
                 f'width="6" height="{n * 11}" fill="{MUTE}" opacity="0.55"/>')
    for n in (1, 2, 3):
        o.append(txt(L - 10, STRIP - n * 11 + 4, str(n), 10, MUTE, "end"))
    o.append(f'<line x1="{L}" y1="{STRIP}" x2="{R}" y2="{STRIP}" '
             f'stroke="{INK}" stroke-width="1"/>')

    o.append(txt(L, H - 44, "Never more than three of the ten insurers at any "
                            "one date, and one or two at most dates — so this "
                            "is a panel, not yet a continuous aggregate.",
                 10.5, MUTE))
    o.append(txt(L, H - 30, "Cathay and KGI from investor decks; Fubon and Nan "
                            "Shan from statutory notionals reconciled to the "
                            "filing's own printed total, over the Insurance "
                            "Bureau's overseas-investment table.", 10.5, MUTE))
    o.append(txt(L, H - 14, "Source: MOPS statutory filings, company investor "
                            "presentations, Insurance Bureau fund-utilisation "
                            "table. Author's extraction.", 10.5, MUTE))
    o.append("</svg>")
    SVG.write_text("\n".join(o), encoding="utf-8")
    try:
        import cairosvg
        cairosvg.svg2png(url=str(SVG), write_to=str(PNG), scale=2)
    except Exception as e:                                   # noqa: BLE001
        print(f"(no raster: {e})")
    print(f"first observation {dates[0]}; {len(dates)} dates; "
          f"max firms at any date {max(n_at.values())}")
    print(f"-> {OUT.relative_to(ROOT)}, {SVG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
