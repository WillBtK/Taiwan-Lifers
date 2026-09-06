#!/usr/bin/env python3
"""Σ傳統避險本金 ÷ §三(九) denominator, per firm and summed, from the filings.

WHY THIS CONSTRUCTION AND NOT THE OTHERS
The FSC's 避險比率 is defined in §三(九) as 傳統避險本金 over 國外投資總額 less
two subtractions. Every other series in this project approximates it:
`fx_pl_offset_ratio_*` infers it from a P&L identity and is not a level series
before 2024 (4.48); the association's 60-70% and the offset ratio's 80-85%
disagree about the pre-2024 level and neither can settle it. This applies the
definition directly to disclosed amounts, which is the only construction that
can (4.50).

THE DENOMINATOR IS NOT 國外投資
Measured at three month-ends where both are published, the regulatory
denominator is about 32% BELOW 國外投資總額 - 15.6兆 against 23.0兆 at 2024-12,
15.2 against 22.3 at 2025-10, 15.4 against 22.8 at 2025-12 (4.53). A ratio
computed on the raw base reads roughly 0.68x the official one: 45% where the
FSC published 66.4%. That is the same order of level error that made the P&L
reconstruction unusable, so the wedge is applied explicitly and its
uncertainty reported, never ignored.

The wedge is a stopgap. It rests on three observations, all post-2024, and the
FX-policy liability book it mostly reflects has grown over time, so assuming it
constant back to 2016 is an assumption and is labelled as one. The proper
denominator is the three §三(九) components read from the same statements as
the numerator; until those parse for every firm, this is the honest interim and
says so in its own output.

CURRENCY
Some firms state notionals in NT$; Taiwan Life states them by currency in
thousands of that currency. USD is 97.7% of its book, and only USD/TWD is
available in this project, so non-USD rows are carried UNCONVERTED and reported
as a residual rather than dropped silently or converted at a guessed rate.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTIONALS = ROOT / "data" / "firm_hedge_notional.csv"
FUND = ROOT / "data" / "firm_fund_utilisation_wayback.csv"
FX = ROOT / "data" / "usdtwd_monthly.csv"
OUT = ROOT / "data" / "bottom_up_hedge_ratio.csv"

# Measured at 2024-12, 2025-10 and 2025-12 (decision 4.53). Range 31.8-32.5%.
WEDGE = 0.320
WEDGE_LO, WEDGE_HI = 0.318, 0.325


def usdtwd():
    if not FX.exists():
        return {}
    with open(FX, newline="", encoding="utf-8") as fh:
        return {r["obs_month"]: float(r["usdtwd"]) for r in csv.DictReader(fh)}


def load_notionals():
    """Traditional-hedge notionals per firm-date, in NT$ thousands.

    Returns (converted, residual_by_currency). The residual is what could not
    be converted for want of a cross rate; it is returned rather than absorbed
    so the caller can report it as a share and decide whether it matters.
    """
    if not NOTIONALS.exists():
        return {}, {}
    rates = usdtwd()
    conv, resid = defaultdict(float), defaultdict(float)
    with open(NOTIONALS, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if str(r.get("traditional", "")).lower() not in ("true", "1"):
                continue
            # 避險活動 lists only DESIGNATED hedges, a small subset of the
            # economic book; summing it with the currency-risk note would
            # double-count part and understate the rest.
            if r.get("note_kind") != "currency_risk":
                continue
            key = (r["entity_id"], r["as_of"])
            if r.get("notional_ntd_k"):
                conv[key] += float(r["notional_ntd_k"])
            elif r.get("notional_ccy_k"):
                ccy, v = r.get("currency"), float(r["notional_ccy_k"])
                if ccy == "USD":
                    rate = rates.get(r["as_of"][:7])
                    if rate:
                        conv[key] += v * rate
                    else:
                        resid[(key, "USD-norate")] += v
                else:
                    resid[(key, ccy)] += v
    return dict(conv), dict(resid)


# The archived fund table identifies firms by 統編 and Chinese name; the
# notionals identify them by entity_id. Joining on the name silently matched
# nothing, so every ratio was skipped and the output looked merely "not ready".
# Keyed on the 統編, which is stable across the renames (國際康健 -> 安達國際).
UID_TO_ENTITY = {"27935073": "fubon_life", "03557017": "taiwan_life",
                 "70817744": "transglobe_life", "03374707": "cathay_life",
                 "11456006": "nanshan_life", "03434016": "kgi_life",
                 "03458902": "shinkong_life"}


def load_foreign_investment():
    """國外投資 per firm-date, NT$ thousands, from the archived fund tables.

    Dates are normalised to the notional's convention: the fund table records
    a year-end as "2024-12" while a filing dates it "2024-12-31". Comparing the
    two forms directly is another way to match nothing.
    """
    if not FUND.exists():
        return {}
    import calendar
    out = {}
    with open(FUND, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["item"] != "國外投資":
                continue
            ent = UID_TO_ENTITY.get(r.get("uid"))
            if not ent:
                continue
            y, mo = (int(x) for x in r["as_of"].split("-")[:2])
            d = f"{y:04d}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"
            out[(ent, d)] = float(r["amount_ntd_k"])
    return out


def main():
    conv, resid = load_notionals()
    if not conv:
        print(f"no traditional-hedge notionals in "
              f"{NOTIONALS.relative_to(ROOT) if NOTIONALS.exists() else NOTIONALS.name}"
              f"; the statement pull has not produced them yet.")
        return 0

    print(f"{len(conv)} firm-period traditional-hedge notionals\n")
    print(f"  {'firm':<18}{'as of':<12}{'傳統避險本金':>18}")
    for (ent, d), v in sorted(conv.items()):
        print(f"  {ent:<18}{d:<12}{v / 1e6:>15,.1f}bn")

    if resid:
        print(f"\n  UNCONVERTED residual (no cross rate available):")
        for (key, ccy), v in sorted(resid.items(), key=lambda kv: str(kv[0])):
            print(f"    {key[0]:<16}{key[1]:<12}{ccy:<12}{v:>16,.0f}k")
        print("    These are excluded from the ratios below, which therefore "
              "understate the numerator slightly.")

    fi = load_foreign_investment()
    rows = []
    print(f"\n  {'firm':<18}{'as of':<12}{'避險本金':>12}{'國外投資':>12}"
          f"{'raw':>8}{'wedge-adj':>11}")
    for (ent, d), v in sorted(conv.items()):
        f = fi.get((ent, d))
        if not f:
            continue
        raw = v / f
        adj = v / (f * (1 - WEDGE))
        lo = v / (f * (1 - WEDGE_LO))
        hi = v / (f * (1 - WEDGE_HI))
        rows.append({"entity_id": ent, "as_of": d,
                     "traditional_notional_ntd_k": round(v, 3),
                     "foreign_investment_ntd_k": round(f, 3),
                     "ratio_on_foreign_investment": round(raw, 5),
                     "ratio_wedge_adjusted": round(adj, 5),
                     "ratio_wedge_lo": round(min(lo, hi), 5),
                     "ratio_wedge_hi": round(max(lo, hi), 5),
                     "basis": "estimated: denominator = 國外投資 x (1 - 0.320); "
                              "the wedge is measured post-2024 only (4.53)"})
        print(f"  {ent:<18}{d:<12}{v / 1e6:>9,.0f}bn{f / 1e6:>11,.0f}bn"
              f"{raw:>8.1%}{adj:>11.1%}")

    if not rows:
        print("\n  no firm-period has BOTH a notional and a 國外投資 figure yet.")
        print("  Notionals come from the statement pull; 國外投資 currently "
              "comes from the archived ins-info tables, which cover only "
              "Taiwan Life and Fubon Life before 2023.")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} rows -> {OUT.relative_to(ROOT)}")
    print("\nNOT the official ratio: the denominator is 國外投資 scaled by a "
          "wedge measured at three post-2024 month-ends, not the three "
          "§三(九) components read from the filings. Comparable in level to "
          "reg_hedge_ratio only to the extent that wedge held.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
