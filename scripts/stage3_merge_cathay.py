#!/usr/bin/env python3
"""Stage 3a — merge the English and Chinese Cathay deck extractions.

Reads data/cathay_deck_fx.csv (en) and data/cathay_deck_fx_zh.csv (zh) and
writes data/cathay_fx_quarterly.csv, one row per deck date, with per-field
agreement tracking:

  - a field present in both languages must agree (within rounding for tn
    figures); agreement upgrades it to `both`, disagreement blanks the value
    and records the pair in `flags` — a disagreeing cell is not data;
  - a field present in one language is kept with its source (`en`/`zh`);
  - `period` is the reporting period the deck covers, derived from the deck
    month (Mar → FY of the prior year; May → Q1; Aug → 1H; Oct/Nov → 9M) and
    cross-checked against the hedging-cost period label where one was
    extracted — a mismatch there also lands in `flags`.

The zh text layer is the more complete for costs and 2023-era CS & NDF shares;
the en one for the exposure split and the 2026 structure trio. Neither is
authoritative alone; agreement is the standard (decisions 3.8).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "data" / "cathay_deck_fx.csv"
ZH = ROOT / "data" / "cathay_deck_fx_zh.csv"
OUT = ROOT / "data" / "cathay_fx_quarterly.csv"

NUM_FIELDS = ["fx_assets_ntd_tn", "hedge_cs_ndf_pct", "hedge_proxy_open_pct",
              "hedge_fvoci_pct", "fx_risk_exposure_pct", "fx_policy_reserve_pct",
              "hedging_cost_pct", "fx_volatility_reserve_ntd_bn"]

# Conflicts resolved by reading the page geometry by hand (decisions 3.9):
# wedge colours are stable across vintages (dark blue = CS & NDF, yellow =
# proxy & open, green = FVOCI), and on the 2023-03 page values 56/33/12 sit in
# the blue/yellow/green wedges respectively, in both language editions.
MANUAL = {
    ("2023-03-22", "hedge_cs_ndf_pct"): "56",
    ("2023-03-22", "hedge_proxy_open_pct"): "33",
    ("2023-03-22", "hedge_fvoci_pct"): "12",
}


def load(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {r["deck_date"]: r for r in csv.DictReader(path.open(encoding="utf-8"))}


def period_for(deck_date: str) -> str:
    y, m, _ = deck_date.split("-")
    yy = int(y) % 100
    mm = int(m)
    if mm <= 3:
        return f"FY{yy - 1:02d}"
    if mm <= 6:
        return f"1Q{yy:02d}"
    if mm <= 9:
        return f"1H{yy:02d}"
    return f"9M{yy:02d}"


def main() -> int:
    en, zh = load(EN), load(ZH)
    rows = []
    n_agree = n_conflict = 0
    for d in sorted(set(en) | set(zh), reverse=True):
        e, z = en.get(d, {}), zh.get(d, {})
        row: dict = {"deck_date": d, "period": period_for(d)}
        flags = []
        for f in NUM_FIELDS:
            if (d, f) in MANUAL:
                row[f], row[f + "_src"] = MANUAL[(d, f)], "manual_geometry"
                continue
            ev, zv = e.get(f, "").strip(), z.get(f, "").strip()
            if ev and zv:
                if abs(float(ev) - float(zv)) <= (0.05 if f.endswith("_tn") else 0.101):
                    row[f], row[f + "_src"] = ev, "both"
                    n_agree += 1
                else:
                    row[f], row[f + "_src"] = "", "conflict"
                    flags.append(f"{f}: en={ev} zh={zv}")
                    n_conflict += 1
            elif ev or zv:
                row[f], row[f + "_src"] = (ev or zv), ("en" if ev else "zh")
        for f in ("hedging_cost_period", "structure_asof"):
            row[f] = e.get(f, "").strip() or z.get(f, "").strip()
        if row.get("hedging_cost_period") and row["hedging_cost_period"] != row["period"]:
            flags.append(f"cost period label {row['hedging_cost_period']} != derived {row['period']}")
        row["flags"] = "; ".join(flags)
        if any(row.get(f) for f in NUM_FIELDS):
            rows.append(row)

    cols = ["deck_date", "period"] + [c for f in NUM_FIELDS for c in (f, f + "_src")] + \
           ["hedging_cost_period", "structure_asof", "flags"]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"rows: {len(rows)}; field agreements: {n_agree}; conflicts: {n_conflict}")
    for r in rows:
        if r["flags"]:
            print(f"  FLAG {r['deck_date']} ({r['period']}): {r['flags']}")
    print(f"csv: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
