#!/usr/bin/env python3
"""Cell by cell against the sell-side workbook: what is missing, and what differs.

stage7_benchmark_check.py answers "where the two overlap, do they agree". This
answers the prior question — WHERE DO THEY NOT OVERLAP — because a mean
absolute difference computed over the cells that happen to exist says nothing
about the cells that do not, and the workbook is a 55-cell rectangle: five
firms, eleven quarters, no holes.

Eight columns are compared, and they are not equally hard. The four structure
shares come off a slide. The swap/NDF split is published by some firms and not
others. The two denominators are not a disclosure at all for most firms at most
dates — they are interpolated from a handful of Bureau observations — so this
distinguishes an OBSERVED denominator from an ESTIMATED one and reports the
estimate's error separately. Reporting an interpolated figure as though it were
a match would be the more flattering answer and the wrong one.

Sources are the independent ones only. Nothing here is read from the workbook.

Run: python3 scripts/stage7_benchmark_gaps.py
"""
import collections
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "data" / "benchmark_jpm_hedging_structure.csv"
DECKPIE = ROOT / "data" / "deck_pie.csv"
STRUCT = ROOT / "data" / "hedging_structure.csv"
WAYBACK = ROOT / "data" / "firm_fund_utilisation_wayback.csv"
FUNDS = ROOT / "data" / "ib_firm_funds.csv"
SECTOR = ROOT / "data" / "ib_indicators_monthly.csv"
SKFH = ROOT / "data" / "skfh_deck_text.json.gz"
SKFH_MAN = ROOT / "config" / "skfh_decks.tsv"

NAME = {"cathay_life": "Cathay", "fubon_life": "Fubon", "kgi_life": "KGI",
        "shinkong_life": "Shin Kong", "taiwan_life": "Taiwan Life"}
# The same tax ids stage6 uses; Shin Kong has two because the Bureau's page
# changed the registrant at the Taishin merger.
UID = {"03374707": "cathay_life", "27935073": "fubon_life",
       "03434016": "kgi_life", "03458902": "shinkong_life",
       "70789634": "shinkong_life", "03557017": "taiwan_life"}
# The four structure shares, then the two instrument shares, then the two
# denominators. Named as the workbook names them.
SHARES = ("traditional_hedge_pct", "fx_policy_pct", "proxy_naked_pct",
          "equity_fund_pct")
SPLIT = ("currency_swap_pct", "ndf_pct")
DENOM = ("overseas_investment_ntd_bn", "total_investment_ntd_bn")
TOL = 0.5          # pp, within which a share is called a match
DTOL = 2.0         # %, within which a denominator is called a match


def bench():
    rows = {}
    for r in csv.DictReader(open(BENCH, newline="", encoding="utf-8")):
        rows[(r["entity_id"], r["as_of"])] = r
    return rows


def ours():
    """Our own structure shares, by firm-quarter, from the strongest source."""
    out = collections.defaultdict(dict)
    # The superseded table first, so deck_pie overwrites it. It is kept only
    # because it still holds Fubon, whose deck merges traditional and natural
    # hedge into one wedge and so cannot fill traditional_hedge_pct at all.
    if STRUCT.exists():
        for r in csv.DictReader(open(STRUCT, newline="", encoding="utf-8")):
            k = (r["entity_id"], r["as_of"])
            for a, b in (("traditional_hedge_pct", "traditional_hedge_pct"),
                         ("fx_policy_pct", "fx_policy_pct"),
                         ("proxy_naked_pct", "proxy_naked_pct"),
                         ("equity_fund_pct", "equity_fund_pct")):
                if r.get(b):
                    out[k][a] = float(r[b])
            out[k]["_src"] = "structure"
    for r in csv.DictReader(open(DECKPIE, newline="", encoding="utf-8")):
        k = (r["entity_id"], r["as_of"])
        out[k].update({"traditional_hedge_pct": float(r["hedged_pct"]),
                       "fx_policy_pct": float(r["fx_policy_pct"]),
                       "proxy_naked_pct": float(r["naked_pct"]),
                       "equity_fund_pct": float(r["equity_pct"]),
                       "_src": r["source"]})
    return out


def swap_split():
    """currency_swap_pct / ndf_pct, where a firm publishes the split.

    Shin Kong prints it in a footnote on the same slide as the pie — "Currency
    swaps and non-delivery forwards accounted for 51% and 49%" — as shares OF
    the traditional hedge, so the workbook's basis is that share times the
    traditional hedge. No other firm in the workbook prints it.
    """
    import gzip
    import json
    import re
    if not (SKFH.exists() and SKFH_MAN.exists()):
        return {}
    when = {}
    for line in SKFH_MAN.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith(("#", "conf_id\t")):
            continue
        cid, _l, as_of, _e, _u, _t = line.split("\t")
        if as_of.strip():
            when[int(cid)] = as_of.strip()
    pat = re.compile(r"比\s*重\s*分\s*別\s*為\s*(\d{1,3})\s*%\s*及\s*(\d{1,3})\s*%"
                     r"|accounted\s+for\s+(\d{1,3})%\s+and\s+(\d{1,3})%"
                     r"|分\s*別\s*為\s*(\d{1,3})\s*%\s*與\s*(\d{1,3})\s*%", re.I)
    out = {}
    with gzip.open(SKFH, "rt", encoding="utf-8") as fh:
        store = json.load(fh)
    for rec in store.values():
        as_of = when.get(rec["conf_id"])
        if not as_of:
            continue
        for text in rec["pages"].values():
            m = pat.search(text)
            if m:
                g = [x for x in m.groups() if x]
                out.setdefault(("shinkong_life", as_of), (float(g[0]),
                                                          float(g[1])))
    return out


def firm_bn():
    """A firm's own 國外投資 and total invested funds, NT$bn, where DISCLOSED."""
    fi = collections.defaultdict(dict)
    tot = collections.defaultdict(dict)
    for r in csv.DictReader(open(WAYBACK, newline="", encoding="utf-8")):
        e = UID.get(r.get("uid"))
        if not e:
            continue
        if r["item"] == "國外投資":
            fi[e][r["as_of"][:7]] = float(r["amount_ntd_k"]) / 1e6
        elif r["item"] == "資金運用總計":
            tot[e][r["as_of"][:7]] = float(r["amount_ntd_k"]) / 1e6
    for r in csv.DictReader(open(FUNDS, newline="", encoding="utf-8")):
        e = UID.get(r.get("uid"))
        if not e:
            continue
        if r.get("foreign_investment"):
            fi[e][r["obs_date"][:7]] = float(r["foreign_investment"]) / 1e3
        if r.get("total"):
            tot[e][r["obs_date"][:7]] = float(r["total"]) / 1e3
    for r in csv.DictReader(open(DECKPIE, newline="", encoding="utf-8")):
        if r["entity_id"] in NAME and r.get("foreign_assets_ntd_bn"):
            fi[r["entity_id"]][r["as_of"][:7]] = float(
                r["foreign_assets_ntd_bn"])
    return fi, tot


def sector_bn():
    """Sector 國外投資, NT$bn, monthly and observed."""
    out = {}
    for r in csv.DictReader(open(SECTOR, newline="", encoding="utf-8")):
        if r.get("foreign_investments"):
            out[r["obs_month"][:7]] = float(r["foreign_investments"]) / 1e3
    return out


def main():
    B, O = bench(), ours()
    SP = swap_split()
    FI, TOT = firm_bn()
    dates = sorted({d for _, d in B})
    firms = sorted({e for e, _ in B}, key=lambda e: NAME[e])

    print(f"Against {len(B)} workbook cells: {len(firms)} firms x "
          f"{len(dates)} quarters, no holes.\n")

    # ---------------------------------------------------- structure shares
    print("THE FOUR STRUCTURE SHARES")
    print("  h = hedge, p = policy, n = naked, e = equity. "
          f". means we have no value; a digit is |difference| in pp, "
          f"rounded; * is over {TOL}pp.\n")
    print("  " + "firm".ljust(13) + "".join(d[2:7].replace("-", "").rjust(7)
                                            for d in dates))
    missing = collections.Counter()
    diffs = collections.defaultdict(list)
    for e in firms:
        cells = []
        for d in dates:
            b, o = B[(e, d)], O.get((e, d), {})
            s = ""
            for c, ch in zip(SHARES, "hpne"):
                if not o.get(c):
                    s += "."
                    missing[(e, c)] += 1
                    continue
                dv = abs(float(b[c]) - o[c])
                diffs[c].append((dv, e, d))
                s += ("0" if dv <= 0.05 else
                      f"{min(9, round(dv))}" if dv <= TOL else "*")
            cells.append(s)
        print("  " + NAME[e].ljust(13) + "".join(c.rjust(7) for c in cells))

    print("\n  cells we cannot fill, by firm and column:")
    for (e, c), n in sorted(missing.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {NAME[e]:<13}{c:<24}{n:>3} of {len(dates)}")
    if not missing:
        print("    none")

    print(f"\n  differences over {TOL}pp where we DO have the value:")
    worst = sorted((x for v in diffs.values() for x in v), reverse=True)
    shown = [x for x in worst if x[0] > TOL]
    for dv, e, d in shown:
        cols = [c for c in SHARES if any(
            (dv, e, d) == t for t in diffs[c])]
        b, o = B[(e, d)], O[(e, d)]
        for c in cols:
            print(f"    {NAME[e]:<13}{d}  {c:<24}"
                  f"workbook {float(b[c]):>6.1f}   ours {o[c]:>6.1f}"
                  f"   {o[c] - float(b[c]):+5.1f}")
    if not shown:
        print("    none")

    # ---------------------------------------------------- swap / NDF split
    print("\n\nTHE CURRENCY-SWAP / NDF SPLIT")
    have = miss = 0
    lines = []
    for e in firms:
        for d in dates:
            b = B[(e, d)]
            if not b.get("currency_swap_pct"):
                continue                      # the workbook has none either
            o = O.get((e, d), {})
            sp = SP.get((e, d))
            if sp and o.get("traditional_hedge_pct"):
                cs = o["traditional_hedge_pct"] * sp[0] / 100.0
                nd = o["traditional_hedge_pct"] * sp[1] / 100.0
                lines.append(f"    {NAME[e]:<13}{d}  workbook "
                             f"{float(b['currency_swap_pct']):>5.1f}/"
                             f"{float(b['ndf_pct']):<5.1f} ours "
                             f"{cs:>5.1f}/{nd:<5.1f}")
                have += 1
            else:
                miss += 1
    n_b = sum(1 for k in B if B[k].get("currency_swap_pct"))
    print(f"  the workbook publishes it for {n_b} of {len(B)} cells; "
          f"we can fill {have} of those {n_b}.")
    for ln in lines:
        print(ln)
    print("  Only Shin Kong prints the split, in a footnote on the pie slide,\n"
          "  and it does so on these dates:")
    held = sorted({d for _, d in SP})
    print("    " + ", ".join(held) if held else "    none")
    print("  None of them is a workbook date except 2018-12-31, where the\n"
          "  workbook itself leaves the split blank. Cathay, Fubon, KGI and\n"
          "  Taiwan Life do not publish it at all, so those cells are not a\n"
          "  parsing gap — the number is not disclosed by the firm.")

    # ---------------------------------------------------- denominators
    print("\n\nTHE TWO DENOMINATORS")
    print("  obs = the firm's own figure at that month, from the Bureau's page\n"
          "  or printed on the slide. est = the aggregate's own estimate: the\n"
          "  firm's SHARE of the sector interpolated, times the sector total,\n"
          "  which is monthly and observed. Error is ours against theirs.\n")
    SEC = sector_bn()
    for col, src, unit in (("overseas_investment_ntd_bn", FI, "國外投資"),
                           ("total_investment_ntd_bn", TOT, "資金運用總計")):
        print(f"  {col}  ({unit})")
        n_obs = n_est = n_none = 0
        errs = []
        for e in firms:
            for d in dates:
                pts = src.get(e, {})
                b = float(B[(e, d)][col])
                if d[:7] in pts:
                    v, kind = pts[d[:7]], "obs"
                    n_obs += 1
                else:
                    # The aggregate does NOT interpolate the level. It
                    # interpolates the firm's SHARE of the sector and
                    # multiplies by the sector total, which is monthly and
                    # observed — a firm's share moves slowly where its level
                    # moves with the whole market. Measuring the level
                    # interpolation instead overstates the error the series
                    # actually carries, which is the wrong direction to be
                    # wrong about your own precision.
                    v = None
                    if col.startswith("overseas") and SEC:
                        sh = _interp({m: x / SEC[m] for m, x in pts.items()
                                      if m in SEC}, d)
                        lvl = SEC.get(d[:7]) or _interp(SEC, d)
                        v = None if (sh is None or lvl is None) else sh * lvl
                    if v is None:
                        v = _interp(pts, d)
                    kind = "est"
                    if v is None:
                        n_none += 1
                        continue
                    n_est += 1
                errs.append((abs(v - b) / b * 100.0, kind, e, d, v, b))
        print(f"    observed {n_obs}, estimated {n_est}, unavailable {n_none}"
              f"  of {len(B)}")
        for kind in ("obs", "est"):
            g = [x for x in errs if x[1] == kind]
            if not g:
                continue
            m = sum(x[0] for x in g) / len(g)
            w = max(g)
            print(f"    {kind}: mean |error| {m:5.2f}%   worst {w[0]:5.1f}% "
                  f"({NAME[w[2]]} {w[3]}: ours {w[4]:,.0f} vs {w[5]:,.0f})")
        bad = sorted((x for x in errs if x[0] > DTOL), reverse=True)
        if bad:
            print(f"    over {DTOL}% ({len(bad)} cells):")
            for pc, kind, e, d, v, b in bad[:12]:
                print(f"      {NAME[e]:<13}{d}  {kind}  ours {v:>8,.0f}"
                      f"   workbook {b:>8,.0f}   {(v - b) / b * 100:+6.1f}%")
        print()
    return 0


def _mo(d):
    return int(d[:4]) * 12 + int(d[5:7])


def _interp(pts, d):
    if not pts:
        return None
    xs = sorted(pts)
    t = _mo(d)
    if t < _mo(xs[0] + "-01") or t > _mo(xs[-1] + "-01"):
        return None
    for a, b in zip(xs, xs[1:]):
        ta, tb = _mo(a + "-01"), _mo(b + "-01")
        if ta <= t <= tb:
            if tb == ta:
                return pts[a]
            return pts[a] + (t - ta) / (tb - ta) * (pts[b] - pts[a])
    return None


if __name__ == "__main__":
    sys.exit(main())
