#!/usr/bin/env python3
"""The AGGREGATE FX hedge ratio for the Taiwanese life sector, built bottom up.

The construction, and why it works where a naive sum does not:

  ratio_t  =  Σ_i w_i,t · r_i,t  /  Σ_i w_i,t

where r_i is a firm's own traditional-hedge ratio, taken from that firm's
disclosure, and w_i is its share of sector overseas investment.

THE DENOMINATOR PROBLEM, SOLVED WITH SHARES
A per-firm hedge ratio needs that firm's 國外投資. The Insurance Bureau
publishes it monthly, but this project holds only scattered archived snapshots —
three or four dates for most firms. Requiring an exact denominator at every date
left one or two firms per quarter and no aggregate at all.

The way through is that the SECTOR total is held monthly (112 months from
2017-01), and a firm's SHARE of it is a slow, smooth quantity: Fubon runs
14.3-15.3% across six observations spanning six years, Taiwan Life 6.3-7.0%
across ten. So the share is interpolated between observations and the level
comes from the monthly sector series. A firm's own foreign book is then
w_i,t × sector_t, which is accurate enough to divide a notional by and far more
than accurate enough to use as a weight.

WHAT IS AND IS NOT INTERPOLATED
Shares are interpolated; hedge ratios are NOT extrapolated beyond a firm's first
and last observation, and are linearly interpolated between them only where the
gap is at most four quarters. Every point of the aggregate is therefore backed
by real observations on either side for each contributing firm, and the coverage
line says how much of the sector those firms are.

SOURCES, PER FIRM
  Cathay, KGI        the company's own investor-deck FX pie, rescaled from the
                     FX-risk-bearing base onto total overseas investment
  Fubon, Nan Shan    statutory derivatives-note notionals that reconcile to the
                     filing's own printed 合計
Nothing here comes from a sector hedge-ratio series; the sector total is used
only as the scale for the weights.

Run: python3 scripts/stage6_aggregate_hedge_ratio.py
"""
import csv
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTOR = ROOT / "data" / "ib_indicators_monthly.csv"
WAYBACK = ROOT / "data" / "firm_fund_utilisation_wayback.csv"
FUNDS = ROOT / "data" / "ib_firm_funds.csv"
PANEL = ROOT / "data" / "firm_hedge_panel.csv"
STRUCT = ROOT / "data" / "hedging_structure.csv"
CATHAYQ = ROOT / "data" / "cathay_fx_quarterly.csv"
NOTIONAL = ROOT / "data" / "firm_hedge_notional.csv"
FX = ROOT / "data" / "usdtwd_monthly.csv"
DECKFX = ROOT / "data" / "deck_fx_structure.csv"
OUT = ROOT / "data" / "aggregate_hedge_ratio.csv"

# config/firm_uids.tsv only. Nothing inferred: an earlier pass guessed four more
# identifiers and produced hedge ratios of 1,534% and 10,610%.
UID = {"27935073": "fubon_life", "03374707": "cathay_life",
       "11456006": "nanshan_life", "03434016": "kgi_life",
       "03557017": "taiwan_life", "03458902": "shinkong_life"}
# Taiwan Life and Shin Kong enter from their own investor decks, harvested from
# MOPS. Taiwan Life's statutory notionals are still excluded — they do not
# reconcile to the filing's printed total and raw they gave a ratio running 2%
# to 72%, capture changing rather than hedging — but its DECK publishes the same
# four-bucket pie the sell-side tabulates, and reproduces that workbook exactly
# across eight overlapping quarters.
NAME = {"cathay_life": "Cathay", "fubon_life": "Fubon", "kgi_life": "KGI",
        "nanshan_life": "Nan Shan", "taiwan_life": "Taiwan Life",
        "shinkong_life": "Shin Kong"}
MAX_GAP_Q = 4          # quarters a firm's ratio may be interpolated across
MIN_LINK = 0.15        # minimum sector share behind both ends of a chain link


def qend(p):
    """Deck period label to the quarter-end it reports: FY14 -> 2014-12-31."""
    import re as _re
    p = (p or "").strip().upper()
    m = _re.fullmatch(r"(FY|1Q|2Q|3Q|4Q|1H|2H|9M)?(\d{2}|\d{4})", p)
    if not m:
        return None
    pre, y = m.group(1), int(m.group(2))
    y = y + 2000 if y < 100 else y
    return {None: f"{y}-12-31", "FY": f"{y}-12-31", "1Q": f"{y}-03-31",
            "2Q": f"{y}-06-30", "1H": f"{y}-06-30", "3Q": f"{y}-09-30",
            "9M": f"{y}-09-30", "4Q": f"{y}-12-31",
            "2H": f"{y}-12-31"}.get(pre)


def mo(d):
    return int(d[:4]) * 12 + int(d[5:7])


def quarters(a, b):
    out, y, q = [], int(a[:4]), (int(a[5:7]) - 1) // 3
    while True:
        m = q * 3 + 3
        d = f"{y}-{m:02d}-{[31, 30, 30, 31][q]:02d}"
        if mo(d) > mo(b):
            return out
        if mo(d) >= mo(a):
            out.append(d)
        q += 1
        if q == 4:
            q, y = 0, y + 1


def sector_bn():
    """Sector 國外投資, NT$bn. The file states it in NT$ MILLIONS."""
    out = {}
    for r in csv.DictReader(open(SECTOR, newline="", encoding="utf-8")):
        if r.get("foreign_investments"):
            out[r["obs_month"][:7]] = float(r["foreign_investments"]) / 1e3
    return out


def firm_bn():
    fi = collections.defaultdict(dict)
    for r in csv.DictReader(open(WAYBACK, newline="", encoding="utf-8")):
        e = UID.get(r.get("uid"))
        if e and r["item"] == "國外投資":
            fi[e][r["as_of"][:7]] = float(r["amount_ntd_k"]) / 1e6
    for r in csv.DictReader(open(FUNDS, newline="", encoding="utf-8")):
        e = UID.get(r.get("uid"))
        if e and r.get("foreign_investment"):
            fi[e][r["obs_date"][:7]] = float(r["foreign_investment"]) / 1e3
    return fi


def interp(pts, d, max_gap=None):
    """Linear interpolation between observations; never beyond the ends."""
    if not pts:
        return None
    xs = sorted(pts)
    t = mo(d)
    # An EXACT observation is always returned. Without this the gap test below
    # discarded real data points that happened to sit inside a long gap: Cathay
    # discloses at 2025-03 and 2026-06 with nothing between 2023-12 and 2025-03,
    # so both were thrown away and a quarter of the sector vanished from the
    # series in precisely the quarters the ratio was collapsing.
    for k in xs:
        if mo(k + "-01") == t:
            return pts[k]
    if t <= mo(xs[0] + "-01"):
        return pts[xs[0]] if t == mo(xs[0] + "-01") or max_gap is None else None
    if t > mo(xs[-1] + "-01"):
        return pts[xs[-1]] if max_gap is None else None
    for a, b in zip(xs, xs[1:]):
        ta, tb = mo(a + "-01"), mo(b + "-01")
        if ta <= t <= tb:
            if max_gap is not None and (tb - ta) > max_gap * 3:
                return None
            if tb == ta:
                return pts[a]
            f = (t - ta) / (tb - ta)
            return pts[a] + f * (pts[b] - pts[a])
    return None


def main():
    sec = sector_bn()
    fi = firm_bn()
    # share of sector, at each firm's observed dates
    share_obs = {e: {m: v / sec[m] for m, v in d.items() if m in sec}
                 for e, d in fi.items()}

    # The sector series ends 2026-04; hold it one quarter so 2026-06 — the
    # best-covered recent quarter, with three firms reporting — is reachable.
    # A one-quarter carry of a series that moves a few per cent a year.
    last = max(sec)
    ly, lm = int(last[:4]), int(last[5:7])
    for k in range(1, 4):
        m2, y2 = lm + k, ly
        if m2 > 12:
            m2, y2 = m2 - 12, ly + 1
        sec.setdefault(f"{y2}-{m2:02d}", sec[last])
    grid = quarters("2017-03-31", "2026-06-30")

    # a firm's own foreign book on the quarterly grid: share x sector
    def fbook(e, d):
        s = interp(share_obs.get(e, {}), d)
        if s is None:
            return None
        m = d[:7]
        lvl = sec.get(m) or interp({k: v for k, v in sec.items()}, d)
        return None if lvl is None else s * lvl

    # ---- per-firm hedge ratio, at its own observation dates
    obs = collections.defaultdict(dict)

    # CATHAY: the quarterly deck file carries 26 hedge observations back to
    # 1Q15, against the 12 the structure file yielded. The hedge share is quoted
    # on the FX-risk-bearing base, so it is rescaled by that base — which the
    # same file gives at 23 periods and which is strikingly stable, 68-71%
    # throughout and 74% from 2026, so interpolating it costs almost nothing.
    if CATHAYQ.exists():
        cq = list(csv.DictReader(open(CATHAYQ, newline="", encoding="utf-8")))
        risk = {qend(r["period"])[:7]: float(r["fx_risk_exposure_pct"])
                for r in cq if r.get("fx_risk_exposure_pct")
                and qend(r["period"])}
        for r in cq:
            d = qend(r.get("period"))
            if not d or not r.get("hedge_cs_ndf_pct"):
                continue
            b = interp(risk, d)
            if b is None:
                continue
            obs["cathay_life"][d[:7]] = float(r["hedge_cs_ndf_pct"]) / 100 * b / 100

    # Fubon and Nan Shan: statutory notionals from the VERIFIED panel — only
    # rows that reconcile to the filing's own printed total survive into it.
    for r in csv.DictReader(open(PANEL, newline="", encoding="utf-8")):
        e = r["entity_id"]
        if e not in NAME:
            continue
        f = fbook(e, r["as_of"])
        if f:
            obs[e][r["as_of"][:7]] = (float(r["traditional_notional_ntd_k"])
                                      / 1e6 / f)

    # Taiwan Life and Shin Kong: 已避險 as a share of foreign investment,
    # straight off the company's own pie. Already on the right base, so no
    # rescaling — which is why these two are the cleanest inputs in the whole
    # construction.
    if DECKFX.exists():
        for r in csv.DictReader(open(DECKFX, newline="", encoding="utf-8")):
            if r["entity_id"] in NAME:
                obs[r["entity_id"]][r["as_of"][:7]] = \
                    float(r["hedged_pct"]) / 100

    for r in csv.DictReader(open(STRUCT, newline="", encoding="utf-8")):
        # Cathay is taken from its own quarterly file above, which is richer.
        if (r["traditional_hedge_pct"] and r["entity_id"] in NAME
                and r["entity_id"] != "cathay_life"):
            obs[r["entity_id"]][r["as_of"][:7]] = \
                float(r["traditional_hedge_pct"]) / 100

    # A firm ratio outside this band is not a hedge ratio, it is a capture
    # failure. Nothing legitimate sits below 5% or above 95% of a foreign book.
    for e in list(obs):
        bad = {d: v for d, v in obs[e].items() if not 0.05 <= v <= 0.95}
        for d in bad:
            del obs[e][d]
        if bad:
            print(f"  dropped {len(bad)} implausible {e} points: "
                  f"{sorted(bad)[:4]}")

    # ---- the aggregate, CHAIN-LINKED
    #
    # A weighted mean over whichever firms happen to have data is not a time
    # series: this sample runs 8% to 57% of the sector, and the level moved with
    # it — 45.0% on three firms, then 35.4% when only KGI remained, then 46.9%
    # still on KGI alone. Every one of those moves is composition.
    #
    # So the LEVEL is never compared across quarters. For each adjacent pair the
    # ratio is computed twice over the firms present in BOTH, and only their
    # RATIO of ratios is kept; those links are chained into an index and the
    # index is anchored to the direct weighted ratio at the best-covered
    # quarter. A firm entering or leaving then contributes nothing to the level
    # — only its own change, while it is present, moves the series.
    def wr(d, firms=None):
        num = den = 0.0
        got = {}
        for e in (firms if firms is not None else NAME):
            r = interp(obs.get(e, {}), d, MAX_GAP_Q)
            w = interp(share_obs.get(e, {}), d)
            if r is None or w is None:
                continue
            num += w * r
            den += w
            got[e] = (w, r)
        return (num / den if den > 0 else None), den, got

    direct = {}
    for d in grid:
        v, cov, got = wr(d)
        if v is not None:
            direct[d] = (v, cov, got)
    live = [d for d in grid if d in direct]
    # A link is only as good as the sector share standing behind BOTH of its
    # endpoints. At 2024-12 the matched set was KGI alone, 8% of the sector, and
    # its own ratio jumped 35% to 47% in one quarter; chained naively that put a
    # 14-point spike into the sector line on one insurer's deck. So a link needs
    # MIN_LINK coverage, and where the adjacent quarter is too thin the link is
    # taken from the most recent quarter that is thick enough — bridging the
    # thin quarter rather than trusting it or discarding the span.
    links = {}
    for i, b in enumerate(live):
        if i == 0:
            continue
        for a in reversed(live[:i]):
            both = set(direct[a][2]) & set(direct[b][2])
            if not both:
                continue
            _, ca, _ = wr(a, both)
            _, cb, _ = wr(b, both)
            if min(ca, cb) < MIN_LINK:
                continue
            va, _, _ = wr(a, both)
            vb, _, _ = wr(b, both)
            if va and vb:
                links[b] = (a, vb / va)
            break
    # ONE FORWARD WALK, then rescale. The previous version chained forward
    # from an anchor and backward from it, and the backward pass assumed each
    # link joined ADJACENT quarters. Links look back to the most recent quarter
    # thick enough to support them, so they routinely skip one — and the moment
    # they did, the backward walk stopped and took eight quarters of 2022-24
    # with it. Walking forward from the earliest quarter cannot hit that,
    # because a link's reference is always a quarter already visited.
    idx = {}
    for i, d in enumerate(live):
        if i == 0:
            idx[d] = 1.0
            continue
        ref = links.get(d)
        if ref and ref[0] in idx:
            idx[d] = idx[ref[0]] * ref[1]
        # no usable link: the chain cannot cross this gap, so the quarter is
        # left out rather than bridged on an assumption
    anchor = max((d for d in idx), key=lambda d: (direct[d][1], d))
    scale = direct[anchor][0] / idx[anchor]
    idx = {d: v * scale for d, v in idx.items()}

    rows = []
    for d in grid:
        num = den = 0.0
        parts = {}
        for e in NAME:
            r = interp(obs.get(e, {}), d, MAX_GAP_Q)
            w = interp(share_obs.get(e, {}), d)
            if r is None or w is None:
                continue
            num += w * r
            den += w
            parts[e] = (w, r)
        if den <= 0 or d not in idx:
            continue
        rows.append({"as_of": d, "hedge_ratio": round(idx[d], 5),
                     "unchained_ratio": round(num / den, 5),
                     "coverage_share": round(den, 4),
                     "n_firms": len(parts),
                     "anchor": d == anchor,
                     "firms": ";".join(f"{NAME[e]}={r:.3f}@w{w:.3f}"
                                       for e, (w, r) in sorted(parts.items()))})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"AGGREGATE bottom-up FX hedge ratio: {len(rows)} quarters, "
          f"{rows[0]['as_of']} .. {rows[-1]['as_of']}\n")
    print(f"  {'quarter':<13}{'chained':>10}{'unchained':>11}{'coverage':>10}"
          f"{'firms':>7}")
    for r in rows:
        print(f"  {r['as_of']:<13}{r['hedge_ratio']:>9.1%}"
              f"{r['unchained_ratio']:>11.1%}{r['coverage_share']:>10.0%}"
              f"{r['n_firms']:>7}" + ("   <- anchor" if r["anchor"] else ""))
    print(f"\n-> {OUT.relative_to(ROOT)}")
    chart(rows, obs, share_obs)
    return 0


INK, MUTE, GRID = "#1c1c1c", "#6b6b6b", "#e2e0dc"
COL = {"cathay_life": "#4e7d99", "fubon_life": "#c98a8b",
       "kgi_life": "#7aa88f", "nanshan_life": "#bda57e",
       "taiwan_life": "#9b8aa6", "shinkong_life": "#7f8c8d"}
SVG = ROOT / "reports" / "aggregate_hedge_ratio.svg"
PNG = ROOT / "reports" / "aggregate_hedge_ratio.png"


def _t(x, y, s, size=11, fill=INK, anchor="start", weight="normal"):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" '
            f'font-family="Georgia,\'Times New Roman\',serif">{s}</text>')


def chart(rows, obs, share_obs):
    """One picture: the aggregate, the firms behind it, and the coverage."""
    W, H = 1200, 660
    L, R, TOP, BOT = 80, 1092, 118, 470
    STRIP = 566
    m0, m1 = mo(rows[0]["as_of"]), mo(rows[-1]["as_of"])

    def xs(d):
        return L + (mo(d) - m0) / (m1 - m0) * (R - L)

    def ys(v):
        return BOT - v / 0.80 * (BOT - TOP)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" '
         f'fill="#faf9f7"/>']
    a0, a1 = rows[0]["hedge_ratio"], rows[-1]["hedge_ratio"]
    o.append(_t(L, 40, f"Taiwan life sector: the bottom-up FX hedge ratio has "
                       f"more than halved, {a0:.0%} to {a1:.0%}", 19, INK,
                weight="bold"))
    o.append(_t(L, 63, "Traditional hedge notional over overseas investment, "
                       "chain-linked across six insurers. Built firm by firm "
                       "from statutory", 11.5, MUTE))
    o.append(_t(L, 79, "filings and company decks; no sector hedge-ratio "
                       "series is used in the construction. Gross basis, not "
                       "the regulatory denominator.", 11.5, MUTE))

    for g in range(0, 81, 20):
        y = ys(g / 100)
        o.append(f'<line x1="{L}" y1="{y:.1f}" x2="{R}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        o.append(_t(L - 10, y + 4, f"{g}%", 10.5, MUTE, "end"))
    for yr in range(2019, 2027):
        x = xs(f"{yr}-01-01")
        if L <= x <= R:
            o.append(_t(x, BOT + 18, str(yr), 10.5, MUTE, "middle"))
    o.append(f'<line x1="{L}" y1="{BOT}" x2="{R}" y2="{BOT}" stroke="{INK}" '
             f'stroke-width="1"/>')

    # the firms behind it, faint
    taken = []
    for e, col in COL.items():
        pts = [(d, v) for d, v in sorted(obs.get(e, {}).items())]
        if not pts:
            continue
        pp = [(f"{d}-28", v) for d, v in pts if m0 <= mo(d + "-01") <= m1]
        if len(pp) < 2:
            continue
        o.append('<polyline points="'
                 + " ".join(f"{xs(d):.1f},{ys(v):.1f}" for d, v in pp)
                 + f'" fill="none" stroke="{col}" stroke-width="1.1" '
                 f'stroke-dasharray="3 3" opacity="0.85"/>')
        for d, v in pp:
            o.append(f'<circle cx="{xs(d):.1f}" cy="{ys(v):.1f}" r="2.4" '
                     f'fill="{col}" opacity="0.85"/>')
        d, v = pp[-1]
        # Five series converge into a fifteen-point band by 2026; without this
        # the labels sit on top of each other and name the wrong lines.
        y = ys(v) + 3.5
        while any(abs(y - t) < 13 for t in taken):
            y += 13
        taken.append(y)
        o.append(_t(xs(d) + 7, y, NAME[e], 10, col, "start"))

    # the aggregate
    ag = [(r["as_of"], r["hedge_ratio"]) for r in rows]
    o.append('<polyline points="'
             + " ".join(f"{xs(d):.1f},{ys(v):.1f}" for d, v in ag)
             + f'" fill="none" stroke="{INK}" stroke-width="3" '
             f'stroke-linejoin="round"/>')
    for d, v in (ag[0], ag[-1]):
        o.append(f'<circle cx="{xs(d):.1f}" cy="{ys(v):.1f}" r="4.5" '
                 f'fill="{INK}"/>')
    o.append(_t(xs(ag[0][0]) + 10, ys(ag[0][1]) - 12,
                f"{ag[0][1]:.1%}  {ag[0][0]}", 11.5, INK, "start", "bold"))
    o.append(_t(xs(ag[-1][0]) - 12, ys(ag[-1][1]) + 22,
                f"{ag[-1][1]:.1%}", 14, INK, "end", "bold"))
    o.append(_t(xs(ag[-1][0]) - 12, ys(ag[-1][1]) + 37, ag[-1][0], 10, MUTE,
                "end"))
    mid = ag[len(ag) // 2]
    o.append(_t(xs(mid[0]), ys(mid[1]) - 16, "AGGREGATE", 12, INK, "middle",
                "bold"))

    # coverage
    o.append(_t(L, STRIP - 34, "Share of sector overseas investment behind "
                               "each point", 12, INK, weight="bold"))
    o.append(_t(L, STRIP - 18, "The chain-link means a firm entering or leaving "
                               "cannot move the level — but a thin quarter is "
                               "still a noisier one.", 10.5, MUTE))
    for r in rows:
        h = r["coverage_share"] * 62
        o.append(f'<rect x="{xs(r["as_of"]) - 4:.1f}" y="{STRIP - h:.1f}" '
                 f'width="8" height="{h:.1f}" fill="{MUTE}" opacity="0.5"/>')
    for pc in (0.25, 0.50):
        y = STRIP - pc * 62
        o.append(f'<line x1="{L}" y1="{y:.1f}" x2="{R}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-width="1"/>')
        o.append(_t(L - 10, y + 4, f"{pc:.0%}", 10, MUTE, "end"))
    o.append(f'<line x1="{L}" y1="{STRIP}" x2="{R}" y2="{STRIP}" '
             f'stroke="{INK}" stroke-width="1"/>')

    o.append(_t(L, H - 44, "Chain-linked: each quarter-on-quarter change is "
                           "measured only across firms present in BOTH "
                           "quarters, then chained, so composition never "
                           "moves the level.", 10.5, MUTE))
    o.append(_t(L, H - 28, "Cathay, KGI, Taiwan Life and Shin Kong from their "
                           "own investor decks; Fubon and Nan Shan from "
                           "statutory notionals. Weights are each "
                           "firm\u2019s share of sector overseas investment.",
                10.5, MUTE))
    o.append(_t(L, H - 12, "Source: MOPS statutory filings, company investor "
                           "presentations, Insurance Bureau monthly statistics. "
                           "Author\u2019s extraction.", 10.5, MUTE))
    o.append("</svg>")
    SVG.write_text("\n".join(o), encoding="utf-8")
    try:
        import cairosvg
        cairosvg.svg2png(url=str(SVG), write_to=str(PNG), scale=2)
    except Exception as e:                                   # noqa: BLE001
        print(f"(no raster: {e})")
    print(f"-> {SVG.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
