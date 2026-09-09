#!/usr/bin/env python3
"""The four-way FX structure of overseas investment, sourced independently.

WHAT THIS REPRODUCES AND WHY IT IS BUILT RATHER THAN COPIED
A sell-side workbook circulating on this desk decomposes each insurer's
overseas investment into four mutually exclusive buckets, quarterly:

    traditional hedge (CS + NDF) + FX policy + proxy/naked + equity & fund = 100

with the currency-swap and NDF legs split out, and total overseas and total
invested assets alongside. Taking those numbers as data would leave no way to
check them and no way to extend them next quarter. So the construction is
rebuilt here from the primary sources, and the workbook is used only as a
BENCHMARK to measure agreement against (data/benchmark_jpm_hedging_structure.csv).

THE CONSTRUCTION, RECOVERED
Every firm publishes this decomposition as a pie chart in its investor deck,
but each on a DIFFERENT BASE, and the base is what makes the numbers agree or
disagree by tens of percentage points:

  Cathay, KGI   the pie is a share of the FX-RISK-BEARING portion only, and the
                deck separately gives that portion as a share of the whole
                (69/31, 67/33). So a slice on the published base must be
                multiplied by fx_risk before it is comparable.
                  D = cs_ndf x fx_risk,  E = fx_policy,
                  F = naked x fx_risk,   G = equity x fx_risk
  Fubon         the pie EXCLUDES equity and fund, and the deck states that
                base directly as 'FX assets: bonds %'. So
                  G = 100 - bond_share,  (D+E) = cs_ndf_policy x bond_share,
                  F = naked x bond_share
                and Fubon's own pie does NOT separate the traditional hedge
                from the natural one — it prints them as a single slice.

Multiplying by the wrong base, or none, is the same error as the §三(九)
denominator wedge (4.53): a number of the right shape, 30-40% out.

WHAT IS AND IS NOT REPRODUCIBLE
D, E, F, G, H and I come from sources this project already holds and refreshes.
The CURRENCY-SWAP versus NDF split of D does not: no deck prints it, and the
sell-side gets it by asking investor relations. The independent route is the
statutory derivatives note, which names the instruments — but only for the
firms whose note names them, which is not the same set of firms.

Run: python3 scripts/stage6_hedging_structure.py
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATHAY = ROOT / "data" / "cathay_deck_fx.csv"
FUBON = ROOT / "data" / "fubon_deck_fx.csv"
KGI = ROOT / "data" / "kgi_deck_fx.csv"
FUNDS = ROOT / "data" / "ib_firm_funds.csv"
WAYBACK = ROOT / "data" / "firm_fund_utilisation_wayback.csv"
NOTIONALS = ROOT / "data" / "firm_hedge_notional.csv"
BENCH = ROOT / "data" / "benchmark_jpm_hedging_structure.csv"
OUT = ROOT / "data" / "hedging_structure.csv"

# §三(五) counts forwards, FX swaps, CCS and NDFs as 傳統避險. Within that, the
# sell-side split is currency swap against NDF. The statutory note names the
# instrument, so the split IS derivable — with one caveat that must travel with
# the number: 遠期外匯合約 is a deliverable forward and 無本金交割遠期外匯 is an
# NDF, but a firm that prints only the former may be reporting both under it.
SWAP_LEG = {"匯率交換合約", "匯率交換", "換匯換利合約", "換匯換利",
            "換匯合約", "貨幣交換合約"}
FWD_LEG = {"遠期外匯合約", "遠期外匯", "無本金交割遠期外匯",
           "無本金交割遠期外匯合約"}

UID = {"27935073": "fubon_life", "03557017": "taiwan_life",
       "70817744": "transglobe_life", "03374707": "cathay_life",
       "11456006": "nanshan_life", "03434016": "kgi_life",
       "03458902": "shinkong_life"}


def qend(period):
    """A deck's period label to the balance-sheet date it describes.

    '1Q25' -> 2025-03-31, '1H25'/'2Q25' -> 06-30, '9M25'/'3Q25' -> 09-30,
    '25'/'2025'/'4Q25' -> 12-31. A bare year is the FULL year, not its first
    quarter; reading '24' as 2024-03-31 would shift a whole firm's series by
    three quarters against every other source.
    """
    p = (period or "").strip().upper()
    m = re.fullmatch(r"(\d[QH]|9M)?(\d{2}|\d{4})", p)
    if not m:
        return None
    pre, y = m.group(1), int(m.group(2))
    y = y + 2000 if y < 100 else y
    if not pre:
        return f"{y}-12-31"
    return {"1Q": f"{y}-03-31", "2Q": f"{y}-06-30", "1H": f"{y}-06-30",
            "3Q": f"{y}-09-30", "9M": f"{y}-09-30",
            "4Q": f"{y}-12-31", "2H": f"{y}-12-31"}.get(pre)


def deck_date_to_period(d):
    """Cathay labels its decks by publication date, not by period.

    A deck published in March reports the PRIOR year-end; May reports Q1;
    August Q2; November Q3. Attaching a deck to its own publication quarter
    dates every Cathay observation one quarter late.
    """
    y, mo = int(d[:4]), int(d[5:7])
    if mo <= 4:
        return f"{y - 1}-12-31"
    if mo <= 7:
        return f"{y}-03-31"
    if mo <= 10:
        return f"{y}-06-30"
    return f"{y}-09-30"


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fill3(a, b, c):
    """Three slices of a pie: recover whichever one is missing.

    KGI's 4Q24 deck parsed with the naked and equity slices but not the hedge
    slice, and the hedge slice is 100 minus the other two. Dropping the period
    for want of a number the page arithmetically contains is a self-inflicted
    gap.
    """
    got = [x for x in (a, b, c) if x is not None]
    if len(got) == 3 or len(got) < 2:
        return a, b, c
    miss = 100.0 - sum(got)
    return (miss if a is None else a, miss if b is None else b,
            miss if c is None else c)


# ------------------------------------------------------------- deck readers
def cathay_rows():
    """Cathay and KGI share a shape: pie on the FX-risk base, plus that base."""
    out = defaultdict(dict)
    if not CATHAY.exists():
        return out
    for r in csv.DictReader(open(CATHAY, newline="", encoding="utf-8")):
        d = deck_date_to_period(r["deck_date"])
        rec = out[d]
        for src, dst in (("hedge_cs_ndf_pct", "hedge"),
                         ("hedge_proxy_open_pct", "naked"),
                         ("hedge_fvoci_pct", "equity"),
                         ("fx_risk_exposure_pct", "fx_risk"),
                         ("fx_policy_reserve_pct", "fx_policy")):
            v = num(r.get(src))
            if v is not None:
                rec[dst] = v
    return out


def kgi_rows():
    out = defaultdict(dict)
    if not KGI.exists():
        return out
    for r in csv.DictReader(open(KGI, newline="", encoding="utf-8")):
        d = qend(r.get("deck_period"))
        if not d:
            continue
        rec = out[d]
        for src, dst in (("cs_ndf_pct", "hedge"),
                         ("naked_usd_other_pct", "naked"),
                         ("overseas_equity_pct", "equity"),
                         ("fx_risk_pct", "fx_risk"),
                         ("fx_policy_pct", "fx_policy")):
            v = num(r.get(src))
            if v is not None:
                rec[dst] = v
    return out


def fubon_rows():
    """Fubon's pie is on the ex-equity base, and it merges hedge with policy."""
    out = defaultdict(dict)
    if not FUBON.exists():
        return out
    for r in csv.DictReader(open(FUBON, newline="", encoding="utf-8")):
        d = qend(r.get("period"))
        if not d:
            continue
        rec = out[d]
        hp = num(r.get("cs_ndf_policy_pct"))
        nk = num(r.get("naked_usd_other_pct"))
        if nk is None:
            u, o = num(r.get("naked_usd_pct")), num(r.get("naked_other_pct"))
            nk = None if u is None and o is None else (u or 0.0) + (o or 0.0)
        bond = num(r.get("fx_assets_bond_pct"))
        eq = num(r.get("equity_fund_pct"))
        if eq is None:
            fo, fv = num(r.get("fvoci_equity_pct")), num(r.get("fvtpl_equity_pct"))
            eq = None if fo is None and fv is None else (fo or 0.0) + (fv or 0.0)
        for k, v in (("hedge_and_policy", hp), ("naked", nk),
                     ("bond_share", bond), ("equity_direct", eq)):
            if v is not None:
                rec[k] = v
    return out


# ------------------------------------------------------------- other sources
def fund_table():
    """國外投資 and 資金運用總計 per firm-month, NT$bn, from the Bureau table."""
    out = {}
    if FUNDS.exists():
        for r in csv.DictReader(open(FUNDS, newline="", encoding="utf-8")):
            if not r.get("foreign_investment") or not r.get("total"):
                continue
            # The Bureau states this table in 百萬元.
            out[(r["entity_id"], r["obs_date"][:7])] = (
                float(r["foreign_investment"]) / 1e3, float(r["total"]) / 1e3)
    if WAYBACK.exists():
        agg = defaultdict(dict)
        for r in csv.DictReader(open(WAYBACK, newline="", encoding="utf-8")):
            ent = UID.get(r.get("uid"))
            if not ent or r["item"] not in ("國外投資", "資金運用總計"):
                continue
            agg[(ent, r["as_of"][:7])][r["item"]] = float(r["amount_ntd_k"]) / 1e6
        for k, v in agg.items():
            if k not in out and "國外投資" in v and "資金運用總計" in v:
                out[k] = (v["國外投資"], v["資金運用總計"])
    return out


def swap_ndf_split():
    """The CS-versus-NDF split of the traditional hedge, from the filings.

    This is the column no deck prints. Only rows that reconcile to the filing's
    own printed total are used: an unverified instrument mix is worse than none,
    because the split is a RATIO and a missing instrument moves it without
    moving anything that looks wrong.
    """
    out = {}
    if not NOTIONALS.exists():
        return out
    agg = defaultdict(lambda: [0.0, 0.0])
    for r in csv.DictReader(open(NOTIONALS, newline="", encoding="utf-8")):
        if r.get("note_kind") != "currency_risk":
            continue
        if str(r.get("traditional", "")).lower() not in ("true", "1"):
            continue
        if r.get("reconciles") != "yes":
            continue
        v = num(r.get("notional_ntd_k"))
        if not v or v <= 0:
            continue
        k = (r["entity_id"], r["as_of"])
        if r["instrument"] in SWAP_LEG:
            agg[k][0] += v
        elif r["instrument"] in FWD_LEG:
            agg[k][1] += v
    for k, (s, f) in agg.items():
        if s + f > 0:
            out[k] = (s / (s + f), f / (s + f))
    return out


# ------------------------------------------------------------------- build
def build():
    rows = []
    fi = fund_table()
    split = swap_ndf_split()

    def fund(ent, d):
        return fi.get((ent, d[:7])) or (None, None)

    for ent, src in (("cathay_life", cathay_rows()), ("kgi_life", kgi_rows())):
        for d, r in sorted(src.items()):
            h, n, e = fill3(r.get("hedge"), r.get("naked"), r.get("equity"))
            base = r.get("fx_risk")
            if base is None and r.get("fx_policy") is not None:
                base = 100.0 - r["fx_policy"]
            if base is None:
                continue
            pol = r.get("fx_policy", 100.0 - base)
            rows.append(dict(
                entity_id=ent, as_of=d,
                traditional_hedge_pct=None if h is None else h * base / 100,
                fx_policy_pct=pol,
                proxy_naked_pct=None if n is None else n * base / 100,
                equity_fund_pct=None if e is None else e * base / 100,
                basis="deck pie x FX-risk share"))

    for d, r in sorted(fubon_rows().items()):
        bond = r.get("bond_share")
        if bond is None and r.get("equity_direct") is not None:
            bond = 100.0 - r["equity_direct"]
        if bond is None:
            continue
        hp, nk = r.get("hedge_and_policy"), r.get("naked")
        if hp is None and nk is not None:
            hp = 100.0 - nk
        rows.append(dict(
            entity_id="fubon_life", as_of=d,
            traditional_hedge_pct=None,      # deck merges hedge with policy
            hedge_plus_policy_pct=None if hp is None else hp * bond / 100,
            fx_policy_pct=None,
            proxy_naked_pct=None if nk is None else nk * bond / 100,
            equity_fund_pct=100.0 - bond,
            basis="deck pie x ex-equity share; hedge and policy not separated"))

    for r in rows:
        h, t = fund(r["entity_id"], r["as_of"])
        r["overseas_investment_ntd_bn"] = None if h is None else round(h, 1)
        r["total_investment_ntd_bn"] = None if t is None else round(t, 1)
        s = split.get((r["entity_id"], r["as_of"]))
        d = r.get("traditional_hedge_pct")
        r["swap_share_of_hedge"] = None if not s else round(s[0], 4)
        r["currency_swap_pct"] = (None if not s or d is None
                                  else round(d * s[0], 2))
        r["ndf_fwd_pct"] = None if not s or d is None else round(d * s[1], 2)
        for k in ("traditional_hedge_pct", "hedge_plus_policy_pct",
                  "fx_policy_pct", "proxy_naked_pct", "equity_fund_pct"):
            if r.get(k) is not None:
                r[k] = round(r[k], 2)
    return rows


def main():
    rows = build()
    cols = ["entity_id", "as_of", "currency_swap_pct", "ndf_fwd_pct",
            "traditional_hedge_pct", "hedge_plus_policy_pct", "fx_policy_pct",
            "proxy_naked_pct", "equity_fund_pct", "swap_share_of_hedge",
            "overseas_investment_ntd_bn", "total_investment_ntd_bn", "basis"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x["entity_id"], x["as_of"])):
            w.writerow(r)
    print(f"{len(rows)} firm-period rows -> {OUT.relative_to(ROOT)}\n")

    cov = defaultdict(list)
    for r in rows:
        cov[r["entity_id"]].append(r["as_of"])
    print(f"  {'firm':<14}{'periods':>8}  span")
    for e in sorted(cov):
        d = sorted(cov[e])
        print(f"  {e:<14}{len(d):>8}  {d[0]} .. {d[-1]}")
    missing = {"shinkong_life", "taiwan_life", "nanshan_life"} - set(cov)
    if missing:
        print(f"\n  NO deck extraction at all: {', '.join(sorted(missing))}")

    # ------------------------------------------------------- validation
    if not BENCH.exists():
        return 0
    bench = {}
    for r in csv.DictReader(open(BENCH, newline="", encoding="utf-8")):
        bench[(r["entity_id"], r["as_of"])] = r
    mine = {(r["entity_id"], r["as_of"]): r for r in rows}
    pairs = sorted(set(bench) & set(mine))
    print(f"\nAGREEMENT against the sell-side workbook, {len(pairs)} overlapping "
          f"firm-periods")
    print("  percentage points of difference; blank = not comparable\n")
    print(f"  {'firm':<13}{'as of':<12}{'hedge':>8}{'policy':>8}{'naked':>8}"
          f"{'equity':>8}{'overseas':>10}{'total':>9}")
    diffs = defaultdict(list)
    for k in pairs:
        b, m = bench[k], mine[k]
        cells = []
        for bk, mk in (("traditional_hedge_pct", "traditional_hedge_pct"),
                       ("fx_policy_pct", "fx_policy_pct"),
                       ("proxy_naked_pct", "proxy_naked_pct"),
                       ("equity_fund_pct", "equity_fund_pct")):
            bv, mv = num(b.get(bk)), num(m.get(mk))
            if bv is None or mv is None:
                cells.append("")
            else:
                d = mv - bv
                cells.append(f"{d:+.1f}")
                diffs[bk].append(abs(d))
        for bk, mk in (("overseas_investment_ntd_bn",
                        "overseas_investment_ntd_bn"),
                       ("total_investment_ntd_bn", "total_investment_ntd_bn")):
            bv, mv = num(b.get(bk)), num(m.get(mk))
            if bv is None or mv is None:
                cells.append("")
            else:
                d = (mv - bv) / bv * 100
                cells.append(f"{d:+.1f}%")
                diffs[bk].append(abs(d))
        print(f"  {k[0]:<13}{k[1]:<12}{cells[0]:>8}{cells[1]:>8}{cells[2]:>8}"
              f"{cells[3]:>8}{cells[4]:>10}{cells[5]:>9}")
    print(f"\n  {'column':<32}{'n':>4}{'mean |diff|':>13}{'max':>8}")
    for k, v in diffs.items():
        u = "%" if k.endswith("bn") else "pp"
        print(f"  {k:<32}{len(v):>4}{sum(v) / len(v):>11.2f}{u}"
              f"{max(v):>7.1f}{u}")

    # ------------------------------------------- the split no deck prints
    print("\nCURRENCY SWAP share of the traditional hedge, from the FILINGS")
    print("  The sell-side gets this by asking investor relations. This is the\n"
          "  statutory derivatives note instead: instrument-level notionals that\n"
          "  reconcile to the filing's own printed total.\n")
    sp = swap_ndf_split()
    by = defaultdict(list)
    for (e, d), (s, _) in sorted(sp.items()):
        by[e].append((d, s))
    if not by:
        print("  none: no firm-period notional set reconciles.")
    for e in sorted(by):
        ds = sorted(by[e])
        print(f"  {e:<16}{len(ds):>3} periods  {ds[0][0]} .. {ds[-1][0]}"
              f"   swap share {ds[-1][1]:.0%} latest")
    print("\n  Caveat that must travel with these: 遠期外匯合約 is a deliverable\n"
          "  forward and 無本金交割遠期外匯 an NDF, but a firm printing only the\n"
          "  former may be reporting both under it. The split is swap versus\n"
          "  FORWARDS, and equals swap versus NDF only where the firm says so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
