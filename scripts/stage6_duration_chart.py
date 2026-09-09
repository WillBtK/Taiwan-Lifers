#!/usr/bin/env python3
"""Two panels on the duration gap, hand-rolled SVG.

LEFT  the disclosed USD asset DV01 for the two firms that break out currency,
      quarterly. This is the only direct measurement in the project of
      Taiwanese life duration demand denominated in dollars.
RIGHT the gap itself at each firm's latest disclosure: the asset column against
      the insurance-liability column, both per basis point of equity.

Every series is labelled at its own line. Colour is not load-bearing: the panel
must read correctly in greyscale and to a reader who cannot separate the hues,
which a legend keyed only to colour does not survive.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENS = ROOT / "data" / "firm_rate_sensitivity.csv"
GAP = ROOT / "data" / "duration_gap_panel.csv"
SVG = ROOT / "reports" / "duration_gap.svg"
PNG = ROOT / "reports" / "duration_gap.png"

INK = "#1c1c1c"
MUTE = "#6b6b6b"
GRID = "#e2e0dc"
SERIES = {"cathay_life": "#1b4965", "fubon_life": "#bc4749"}
ASSET, LIAB = "#bc4749", "#1b4965"
NAME = {"cathay_life": "Cathay", "fubon_life": "Fubon",
        "taiwan_life": "Taiwan Life", "kgi_life": "KGI",
        "nanshan_life": "Nan Shan", "shinkong_life": "Shinkong",
        "transglobe_life": "TransGlobe", "banktaiwan_life": "Bank Taiwan",
        "mercuries_life": "Mercuries", "hontai_life": "Hontai"}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, size=11, fill=INK, anchor="start", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" '
            f'font-family="Georgia,\'Times New Roman\',serif">{esc(s)}</text>')


def main():
    if not SENS.exists() or not GAP.exists():
        print("run stage6_rate_sensitivity.py and stage6_duration_panel.py first")
        return 1
    # ---------------------------------------------------- left panel data
    usd = {}
    for r in csv.DictReader(open(SENS, newline="", encoding="utf-8")):
        if r["currency"] != "USD" or r["measure"] != "equity":
            continue
        if r["subject"] not in ("asset", "total"):
            continue
        usd.setdefault(r["entity_id"], {})[r["as_of"]] = \
            abs(float(r["per_bp_ntd_k"])) / 1e3        # NT$mn per bp
    usd = {k: v for k, v in usd.items() if k in SERIES}

    # ---------------------------------------------------- right panel data
    latest = {}
    for r in csv.DictReader(open(GAP, newline="", encoding="utf-8")):
        if r["currency"] != "all" or not r["liability_dv01_ntd_k"]:
            continue
        # 6985 is Taishin Life before 2026 and the Shin Kong survivor after;
        # the series changes company mid-window (see stage6_duration_panel).
        if r["entity_id"] == "shinkong_life":
            continue
        k = r["entity_id"]
        if k not in latest or r["as_of"] > latest[k]["as_of"]:
            latest[k] = r
    bars = sorted(latest.values(),
                  key=lambda r: -float(r["liability_dv01_ntd_k"]))

    W, H = 1240, 560
    L1, L2 = 62, 640            # panel left edges
    PW1 = 470                   # left panel plot width
    NAMEX = 742                 # right panel: names right-aligned here
    BARW = 340                  # right panel: total bar span in px
    TOP, BOT = 100, 452
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="#faf9f7"/>']

    out.append(txt(L1, 34, "Taiwanese life insurers are short asset duration "
                           "against their liabilities", 17, INK, weight="bold"))
    out.append(txt(L1, 55, "Change in equity per basis point of parallel curve "
                           "rise, from the statutory market-risk note. "
                           "NT$ millions.", 11.5, MUTE))

    # ================================================== LEFT: USD DV01 series
    dates = sorted({d for v in usd.values() for d in v})
    ymax = max(max(v.values()) for v in usd.values()) * 1.12
    x0, x1 = L1, L1 + PW1

    def xs(d):
        return x0 + (dates.index(d) / (len(dates) - 1)) * PW1

    def ys(v):
        return BOT - (v / ymax) * (BOT - TOP)

    for g in range(0, int(ymax) + 1, 500):
        y = ys(g)
        if y < TOP:
            continue
        out.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(txt(x0 - 8, y + 3.5, f"{g:,}", 10, MUTE, "end"))
    for d in dates:
        if d.endswith("-03-31") and d[:4] in ("2018", "2020", "2022", "2024",
                                              "2026"):
            out.append(txt(xs(d), BOT + 18, d[:4], 10, MUTE, "middle"))
    out.append(f'<line x1="{x0}" y1="{BOT}" x2="{x1}" y2="{BOT}" '
               f'stroke="{INK}" stroke-width="1"/>')
    out.append(txt(L1, TOP - 16, "USD asset DV01, the two firms that disclose "
                                 "by currency", 12.5, INK, weight="bold"))
    for ent, ser in usd.items():
        pts = " ".join(f"{xs(d):.1f},{ys(v):.1f}" for d, v in sorted(ser.items()))
        out.append(f'<polyline points="{pts}" fill="none" '
                   f'stroke="{SERIES[ent]}" stroke-width="2.1" '
                   f'stroke-linejoin="round"/>')
        ld, lv = max(sorted(ser.items()))
        out.append(f'<circle cx="{xs(ld):.1f}" cy="{ys(lv):.1f}" r="3.2" '
                   f'fill="{SERIES[ent]}"/>')
        # labelled at the line, not in a legend
        out.append(txt(xs(ld) - 8, ys(lv) - 9, NAME[ent], 11.5, SERIES[ent],
                       "end", "bold"))
    out.append(txt(L1, BOT + 46,
                   "Cathay's USD sensitivity rose 84% in the year to 2026-Q1, "
                   "on the comparison its own", 10.5, MUTE))
    out.append(txt(L1, BOT + 61,
                   "filing prints. Its foreign book did not: the rise is "
                   "duration extension and IFRS 17", 10.5, MUTE))
    out.append(txt(L1, BOT + 76,
                   "reclassification, not new holdings.", 10.5, MUTE))

    # ================================================== RIGHT: the gap
    out.append(txt(L2, TOP - 16, "Assets against insurance liabilities, "
                                 "latest disclosure", 12.5, INK, weight="bold"))
    amax = max(abs(float(r["asset_dv01_ntd_k"])) for r in bars) / 1e3
    lmax = max(float(r["liability_dv01_ntd_k"]) for r in bars) / 1e3
    scale = BARW / (amax + lmax)
    mid = NAMEX + 14 + amax * scale        # the zero line, past the longest
    rowh = (BOT - TOP) / len(bars)         # asset bar and the name gutter
    out.append(f'<line x1="{mid:.1f}" y1="{TOP - 8}" x2="{mid:.1f}" '
               f'y2="{BOT + 6}" stroke="{INK}" stroke-width="1"/>')
    for i, r in enumerate(bars):
        y = TOP + i * rowh + rowh / 2
        a = float(r["asset_dv01_ntd_k"]) / 1e3
        li = float(r["liability_dv01_ntd_k"]) / 1e3
        n = float(r["net_dv01_ntd_k"]) / 1e3
        h = min(rowh * 0.30, 13)
        out.append(f'<rect x="{mid + a * scale:.1f}" y="{y - h - 1.5:.1f}" '
                   f'width="{abs(a) * scale:.1f}" height="{h:.1f}" '
                   f'fill="{ASSET}"/>')
        out.append(f'<rect x="{mid:.1f}" y="{y + 1.5:.1f}" '
                   f'width="{li * scale:.1f}" height="{h:.1f}" fill="{LIAB}"/>')
        # A bar too short to see reads as missing data, and Shinkong's asset
        # column — 1% of invested assets — is the opposite of missing: it is
        # the finding. Say so rather than let the reader infer a gap.
        if abs(a) * scale < 4:
            out.append(txt(mid + a * scale - 6, y - 3, f"{abs(a):,.0f}", 9.5,
                           ASSET, "end"))
        # the name sits in its own gutter, clear of the longest asset bar
        out.append(txt(NAMEX, y + 4, NAME[r["entity_id"]], 11, INK, "end"))
        out.append(txt(mid + li * scale + 9, y + 4, f"net +{n:,.0f}", 10.5,
                       MUTE))
    # one keyed pair, placed under the axis rather than on top of a bar
    out.append(f'<rect x="{mid - 46:.1f}" y="{BOT + 16}" width="38" '
               f'height="9" fill="{ASSET}"/>')
    out.append(txt(mid - 52, BOT + 24, "assets", 10, ASSET, "end", "bold"))
    out.append(f'<rect x="{mid + 8:.1f}" y="{BOT + 16}" width="38" '
               f'height="9" fill="{LIAB}"/>')
    out.append(txt(mid + 52, BOT + 24, "insurance liabilities", 10, LIAB,
                   "start", "bold"))
    out.append(txt(L2, BOT + 46,
                   "Only fair-valued assets reach equity; IFRS 17 marks the "
                   "liability in", 10.5, MUTE))
    out.append(txt(L2, BOT + 61,
                   "full. The gap shown is therefore an upper bound — but "
                   "every firm that", 10.5, MUTE))
    out.append(txt(L2, BOT + 76,
                   "discloses both sides shows the same sign.", 10.5, MUTE))

    out.append(txt(L1, H - 12, "Source: statutory quarterly filings via MOPS, "
                               "notes on market risk. Author's extraction.",
                   10, MUTE))
    out.append("</svg>")
    SVG.parent.mkdir(parents=True, exist_ok=True)
    SVG.write_text("\n".join(out), encoding="utf-8")
    try:
        import cairosvg
        cairosvg.svg2png(url=str(SVG), write_to=str(PNG), scale=2)
        print(f"{SVG.relative_to(ROOT)} and {PNG.relative_to(ROOT)}")
    except Exception as e:                                   # noqa: BLE001
        print(f"{SVG.relative_to(ROOT)} (no raster: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
