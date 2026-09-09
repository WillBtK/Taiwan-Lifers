#!/usr/bin/env python3
"""The duration gap, per firm, from the statutory rate-sensitivity note.

WHAT THIS ANSWERS
Why Taiwanese lifers are a standing bid for long USD duration, and how much of
that bid is structural rather than discretionary. The market-risk note gives
both halves of the answer directly: the change in equity for a parallel curve
move on the INVESTMENT ASSETS, and the same for the INSURANCE CONTRACT
LIABILITIES. Their sum is the accounting duration gap, and its sign says which
way the firm has to trade to close it.

WHAT THE EQUITY MEASURE DOES AND DOES NOT COVER
Only assets carried at fair value reach equity. A bond held at amortised cost
carries duration that never appears in this table, so the asset-side figure is a
floor on asset duration, not a measure of it. Nan Shan makes this explicit by
reporting the two fair-value buckets and nothing else, and says so in the
table's own row labels. The liability side has no such exemption — IFRS 17 discounts
it in full — so the gap this table shows is systematically WIDER than the
economic one. It is an upper bound on the mismatch, and the direction is what
survives the caveat: every firm that discloses both sides shows the same sign.

CURRENCY
Fubon and Cathay disclose the curve shock by currency. Their USD rows are the
only direct measurement in this project of Taiwanese life duration demand
denominated in dollars, and they are reported separately rather than folded
into the aggregate.

Run: python3 scripts/stage6_duration_panel.py
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENS = ROOT / "data" / "firm_rate_sensitivity.csv"
FX = ROOT / "data" / "usdtwd_monthly.csv"
FUNDS = ROOT / "data" / "ib_firm_funds.csv"
OUT = ROOT / "data" / "duration_gap_panel.csv"

# The measure that reaches equity, in preference order. Most firms head the
# column 權益變動; Mercuries and Nan Shan report 其他綜合損益 instead, which is
# the same thing for a book whose rate exposure sits in FVOCI; Hontai states a
# single combined figure and cannot be split.
EQUITY_MEASURES = ("equity", "oci", "pnl_and_oci")
ASSET_SUBJECTS = ("asset", "asset_fvoci", "asset_fvpl", "total")

# MOPS code 6985 is not one company across this window. It is Taishin Life, an
# insurer with about NT$300bn of invested assets, which was renamed Shin Kong
# Life on 2026-01-01 after Taishin absorbed the Shin Kong group. The PRE-2026
# Shin Kong Life — the NT$3.5tn insurer every external series means by
# "Shinkong" — is a different legal entity (統編 03458902) that files under a
# code this project has never indexed.
#
# The consequence is visible in the numbers and is not subtle: the liability
# DV01 read off 6985's filings is +205mn/bp at 2025-03, +191mn at 2025-06 and
# +2,883mn at 2025-12. That is not a firm changing its book, it is the series
# changing companies. Publishing those three points as one insurer's history
# would be wrong in the way that is hardest to catch — a plausible level, a
# plausible trend, and two different balance sheets.
#
# So 6985 is withheld from the headline until its filings are separated by
# reporting entity. The rows stay in the CSV, labelled.
ENTITY_UNRESOLVED = {"shinkong_life"}


def usdtwd():
    with open(FX, newline="", encoding="utf-8") as fh:
        return {r["obs_month"]: float(r["usdtwd"]) for r in csv.DictReader(fh)}


def fund_table():
    """國外投資 and total invested assets per firm, in NT$ BILLIONS.

    The archived fund table states amounts in 百萬元, not the 仟元 every other
    file in this project uses. Reading it as thousands put Cathay's foreign
    book at NT$5.6bn against a true NT$5,555bn, and the coverage ratio came out
    at 39,194%.
    """
    if not FUNDS.exists():
        return {}
    out = {}
    with open(FUNDS, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r.get("foreign_investment") or not r.get("total"):
                continue
            k = r["entity_id"]
            if k not in out or r["obs_date"] > out[k][0]:
                out[k] = (r["obs_date"], float(r["foreign_investment"]) / 1e3,
                          float(r["total"]) / 1e3)
    return out


def load():
    rows = list(csv.DictReader(open(SENS, newline="", encoding="utf-8")))
    # per (firm, period, currency): the asset side, the liability side, the net
    side = defaultdict(dict)
    for r in rows:
        if r["measure"] not in EQUITY_MEASURES:
            continue
        k = (r["entity_id"], r["as_of"], r["currency"])
        v = float(r["per_bp_ntd_k"])
        s = r["subject"]
        if s in ("asset", "asset_fvoci", "asset_fvpl"):
            # Nan Shan splits the asset side into two fair-value buckets; they
            # are additive parts of one book, not alternatives.
            side[k]["asset"] = side[k].get("asset", 0.0) + v
        elif s in ("liability",):
            side[k]["liability"] = v
        elif s == "net":
            side[k]["net"] = v
        elif s == "total":
            side[k]["total"] = v
    return side


def main():
    if not SENS.exists():
        print(f"missing {SENS.name}; run stage6_rate_sensitivity.py first.")
        return 1
    side = load()
    rates = usdtwd()
    fi = fund_table()

    rows = []
    for (ent, d, ccy), v in sorted(side.items()):
        a = v.get("asset")
        li = v.get("liability")
        # A two-column table reports the company as a whole. That is the asset
        # book for Bank Taiwan and Mercuries, whose tables cover financial
        # assets only, and it is stated as such rather than guessed at.
        if a is None and "total" in v:
            a = v["total"]
        net = v.get("net")
        if net is None and a is not None and li is not None:
            net = a + li
        rows.append({"entity_id": ent, "as_of": d, "currency": ccy,
                     "asset_dv01_ntd_k": None if a is None else round(a, 1),
                     "liability_dv01_ntd_k": None if li is None else round(li, 1),
                     "net_dv01_ntd_k": None if net is None else round(net, 1),
                     "usdtwd": rates.get(d[:7])})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} firm-period-currency rows -> {OUT.relative_to(ROOT)}\n")

    # ---- the cross-section, at each firm's latest disclosed period
    latest = {}
    for r in rows:
        if r["currency"] != "all" or r["entity_id"] in ENTITY_UNRESOLVED:
            continue
        k = r["entity_id"]
        if k not in latest or r["as_of"] > latest[k]["as_of"]:
            latest[k] = r
    print("THE DURATION GAP, per basis point, at each firm's latest disclosure")
    print("  NT$mn per bp; positive = a rate RISE increases equity\n")
    print(f"  {'firm':<18}{'as of':<12}{'assets':>10}{'liabilities':>13}"
          f"{'net':>10}   {'net / 100bp':>12}")
    ta = tl = tn = 0.0
    for ent in sorted(latest, key=lambda e: -(latest[e]["net_dv01_ntd_k"] or 0)):
        r = latest[ent]
        a, li, n = (r["asset_dv01_ntd_k"], r["liability_dv01_ntd_k"],
                    r["net_dv01_ntd_k"])
        f = lambda x: "-" if x is None else f"{x / 1e3:,.0f}"
        print(f"  {ent:<18}{r['as_of']:<12}{f(a):>10}{f(li):>13}{f(n):>10}"
              f"   {('-' if n is None else f'{n / 1e6:,.1f}bn'):>12}")
        ta += a or 0.0
        tl += li or 0.0
        tn += n if n is not None else (a or 0.0)
    print(f"  {'SUM':<18}{'':<12}{ta / 1e3:>10,.0f}{tl / 1e3:>13,.0f}"
          f"{tn / 1e3:>10,.0f}   {tn / 1e6:>10,.1f}bn")
    print("\n  The sum is indicative, not a sector total: the periods differ,\n"
          "  and firms that disclose only one side contribute only that side.")
    if ENTITY_UNRESOLVED:
        print(f"  WITHHELD pending entity resolution: "
              f"{', '.join(sorted(ENTITY_UNRESOLVED))} — MOPS code 6985 covers\n"
              f"  Taishin Life and, after the 2026 rename, the Shin Kong "
              f"survivor. Two companies,\n  one series; see the note at the "
              f"head of this file.")

    # ---- what the asset figure implies about the fair-valued bond book
    print("\nIMPLIED FAIR-VALUED BOND BOOK from the asset-side DV01")
    print("  DV01 / 0.0001 = market value x duration. Divided by an assumed\n"
          "  duration, that is the bond book whose price risk reaches equity.\n"
          "  Set against invested assets it says how much of the book is\n"
          "  marked, and by residual how much sits at amortised cost.\n")
    print(f"  {'firm':<18}{'MVxD':>10}{'D=10':>9}{'D=13':>9}{'D=16':>9}"
          f"{'invested':>11}{'國外投資':>11}{'  D=13 share'}")
    for ent in sorted(latest):
        r = latest[ent]
        a = r["asset_dv01_ntd_k"]
        if not a:
            continue
        mvd = abs(a) * 10_000 / 1e6          # NT$bn x duration
        f = fi.get(ent)
        share = f"{mvd / 13 / f[2]:>13.0%}" if f else " " * 13
        print(f"  {ent:<18}{mvd:>10,.0f}{mvd / 10:>9,.0f}{mvd / 13:>9,.0f}"
              f"{mvd / 16:>9,.0f}"
              f"{(f'{f[2]:,.0f}' if f else '-'):>11}"
              f"{(f'{f[1]:,.0f}' if f else '-'):>11}{share}")
    print("\n  NT$bn. The share is against TOTAL invested assets, not the foreign\n"
          "  book, because the all-currency DV01 spans both. It is a floor: a\n"
          "  longer true duration implies a smaller fair-valued book, and only\n"
          "  fair-valued assets appear at all. The residual to 100% is the\n"
          "  amortised-cost book — duration held without touching equity.")

    # ---- the currency split, where disclosed
    print("\nUSD-SPECIFIC ASSET DV01, the two firms that disclose it")
    print(f"  {'firm':<14}{'as of':<12}{'NT$mn/bp':>10}{'USDmn/bp':>10}"
          f"{'MVxD USDbn':>12}{'  D=13 USDbn'}")
    for (ent, d, ccy), v in sorted(side.items()):
        if ccy != "USD" or "asset" not in v and "total" not in v:
            continue
        if d < "2025-01-01":
            continue
        a = v.get("asset", v.get("total"))
        fx = rates.get(d[:7])
        if not fx:
            continue
        um = abs(a) / 1e3 / fx
        print(f"  {ent:<14}{d:<12}{abs(a) / 1e3:>10,.0f}{um:>10,.1f}"
              f"{um * 10:>12,.0f}{um * 10 / 13:>14,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
