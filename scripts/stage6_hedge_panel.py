#!/usr/bin/env python3
"""One defensible 傳統避險本金 panel from the extracted notionals.

WHY AN AGGREGATOR AND NOT A GROUP-BY
A period appears in several filings: its own, and as the comparative column of
the next one or two. Those are not independent observations to be summed — they
are the same balance sheet reported twice — but they arrive as separate rows
because they come from different pages. Summing them doubled Nan Shan's
2020-06-30 to NT$3,616bn against a true ~NT$1,800bn.

So exactly one filing is chosen per firm-period: the one for which that period
is its OWN reporting date, falling back to the nearest later filing. A
comparative column is used only when the primary filing was never captured.

WHAT THIS IS NOT
Not a sector total. Cathay Life — the largest insurer, roughly a quarter of the
sector's foreign investment — does not disclose an economic hedge notional in
its statements at all (decision 4.56), so no bottom-up sum over the disclosing
firms can be scaled to the sector without assuming Cathay behaves like the
others. The panel is per firm, and the coverage it achieves against the
published sector numerator is reported rather than hidden.
"""
import csv
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "firm_hedge_notional.csv"
OUT = ROOT / "data" / "firm_hedge_panel.csv"

# quarter end months, to turn a MOPS filename (202404_5865_AI1.pdf) into the
# reporting date the filing is primarily about
QEND = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


def filing_period(name):
    m = re.match(r"(\d{4})(\d{2})_", name or "")
    if not m:
        return None
    y, q = int(m.group(1)), int(m.group(2))
    return f"{y}-{QEND.get(q, '12-31')}" if q in QEND else None


def main():
    if not SRC.exists():
        print(f"missing {SRC.relative_to(ROOT)}")
        return 1
    rows = [r for r in csv.DictReader(open(SRC, newline="", encoding="utf-8"))
            if r.get("traditional") == "True" and r.get("notional_ntd_k")]

    # Candidate filings per firm-period. Reconciliation outranks recency:
    # preferring the filing for which the period is primary put Fubon's
    # 2020-12-31 at NT$16bn against ~1,400bn either side, because that
    # filing's table parsed badly while the comparative column of a later
    # filing parsed correctly and reconciled to its printed 合計.
    cand = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in rows:
        cand[(r["entity_id"], r["as_of"])][r["filing"]].add(
            r.get("reconciles", "no_total"))

    chosen = {}
    for key, filings in cand.items():
        _, as_of = key
        chosen[key] = min(
            filings,
            key=lambda f: ("yes" not in filings[f],          # reconciles first
                           filing_period(f) != as_of,        # then primary
                           f))
    # A quality gate, not a best-effort fill. Where NO filing reconciles for a
    # period, the surviving value is simply the least-bad parse — Fubon's
    # 2020-12-31 came out at NT$16bn between quarters of ~1,400bn. Emitting
    # that is worse than emitting nothing: a gap is visible, a wrong level is
    # not. Nan Shan is admitted on a different warrant — its parser sums to the
    # filing's own printed asset and liability subtotals, which is checked by
    # fixture — so it is labelled distinctly rather than silently pooled.
    SUBTOTAL_VALIDATED = {"nanshan_life"}
    agg = collections.defaultdict(float)
    parts = collections.defaultdict(dict)
    quality = {}
    dropped = collections.Counter()
    for r in rows:
        key = (r["entity_id"], r["as_of"])
        if r["filing"] != chosen[key]:
            continue
        if r.get("reconciles") == "yes":
            q = "reconciled"
        elif r["entity_id"] in SUBTOTAL_VALIDATED:
            q = "subtotal_validated"
        else:
            dropped[r["entity_id"]] += 1
            continue
        v = float(r["notional_ntd_k"])
        if v <= 0:
            continue
        quality[key] = q
        agg[key] += v
        parts[key][r["instrument"]] = parts[key].get(r["instrument"], 0.0) + v

    out = []
    for (ent, as_of), v in sorted(agg.items()):
        # A period whose instruments all parsed to zero is a failed read, not
        # a firm that closed its whole hedge book overnight.
        if v <= 0:
            continue
        out.append({"entity_id": ent, "as_of": as_of,
                    "traditional_notional_ntd_k": round(v, 3),
                    "source_filing": chosen[(ent, as_of)],
                    "primary": filing_period(chosen[(ent, as_of)]) == as_of,
                    "quality": quality[(ent, as_of)],
                    "instruments": "; ".join(
                        f"{k}={x / 1e6:,.1f}bn" for k, x in
                        sorted(parts[(ent, as_of)].items(), key=lambda kv: -kv[1]))})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    byfirm = collections.defaultdict(dict)
    for r in out:
        byfirm[r["entity_id"]][r["as_of"]] = r["traditional_notional_ntd_k"]
    print(f"{len(out)} firm-period observations -> {OUT.relative_to(ROOT)}")
    if dropped:
        print("  dropped as unverifiable (no filing reconciled): "
              + ", ".join(f"{k} {v}" for k, v in sorted(dropped.items())))
    print()
    for ent in sorted(byfirm, key=lambda e: -max(byfirm[e].values())):
        ds = sorted(byfirm[ent])
        peak = max(byfirm[ent].values()) / 1e6
        print(f"  {ent:<18}{len(ds):>3} periods  {ds[0]} .. {ds[-1]}"
              f"   peak {peak:>8,.0f}bn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
