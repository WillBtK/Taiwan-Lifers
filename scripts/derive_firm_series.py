#!/usr/bin/env python3
"""Firm-level derived series where the deck STATES its base (README §3).

The composition pies raise a base question that decides series 1 by a factor:
are the instrument shares taken over total FX assets, or only over the
FX-risk-bearing subset (the 74-77% that is not backed by FX policies)?
Getting it wrong moves the headline economic hedge ratio by ~10pp, so this
pass derives only what the documents settle (decisions 4.2):

  Fubon, pre-2026 editions — the big wedge is LABELLED
  「外匯交換、無本金遠期外匯、外幣保單」 / "Currency swap, NDF, FX policy".
  It names FX-policy backing as part of its own contents, so the wedge is
  necessarily over total FX assets (policy-backed assets are excluded from
  the FX-risk subset by construction) and the wedge IS the economic hedge
  ratio — disclosed, not inferred. Its complement (naked USD + other
  currencies) is the net open position as a share of FX assets.

  Hedge cost — Cathay states its base on the page ("Hedging cost is
  calculated based on FX assets"); Fubon's recurring component is colour-
  bound and sum-verified (3.17), in bp of FX assets on the same convention.

Not derived here, and why: Cathay's pie names no policy wedge, and Fubon's
2026 redesign moves the policy split into a separate bar, so for those the
base is inferred rather than stated. decisions 4.2 records the evidence on
both sides and the test that would settle it.

Writes data/derived_series_firm.csv and out/derive_firm_YYYYMMDD.sql.
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Q_START = {3: "01-01", 6: "04-01", 9: "07-01", 12: "10-01"}
Q_END = {3: "03-31", 6: "06-30", 9: "09-30", 12: "12-31"}

FUBON_DECKS = "https://fubon.irpro.co/tw/conference.php"
CATHAY_DECKS = "https://www.cathayholdings.com/holdings/ir/financial_information/quarterly_reports"


def period_parts(p):
    if re.fullmatch(r"20\d\d", p):
        return int(p), 12
    m = re.fullmatch(r"FY(\d\d)", p)   # Cathay labels year-end FY24, Fubon 2024
    if m:
        return 2000 + int(m.group(1)), 12
    m = re.fullmatch(r"([1-4])Q(\d\d)", p)
    if m:
        return 2000 + int(m.group(2)), int(m.group(1)) * 3
    m = re.fullmatch(r"1H(\d\d)", p)
    if m:
        return 2000 + int(m.group(1)), 6
    m = re.fullmatch(r"9M(\d\d)", p)
    if m:
        return 2000 + int(m.group(1)), 9
    raise ValueError(p)


def num(s):
    return None if s in (None, "") else float(s)


def main():
    rows, checks, problems = [], [], []

    def emit(sid, key, entity, obs, freq, value, unit, ver, basis, url, doc,
             note=None, vintage=None):
        if value is None:
            return
        rows.append({"series_id": sid, "series_key": key, "entity_id": entity,
                     "obs_date": obs, "freq": freq, "value": round(value, 6),
                     "unit": unit, "definition_version": ver, "basis": basis,
                     "basis_note": note, "source_url": url, "source_doc": doc,
                     "vintage": vintage})

    # ---------- Fubon: economic hedge ratio + net open share, pre-2026 ----------
    seen = set()
    for r in csv.DictReader(open(ROOT / "data" / "fubon_deck_fx.csv", encoding="utf-8")):
        p = r["period"]
        wedge = num(r["cs_ndf_policy_pct"])
        if wedge is None or p in seen:
            continue
        y, em = period_parts(p)
        if y >= 2026:
            continue  # 2026 redesign moves policy to its own bar: base not stated
        seen.add(p)
        obs = f"{y}-{Q_START[em]}"
        # the pie's own closure is the check. 2014-15 editions carry a fourth
        # wedge (股票/共同基金) alongside the two naked-currency wedges; all of
        # them are outside the hedged wedge, so all count toward the closure
        # and toward the net open position.
        others = sum(num(r[k]) or 0 for k in
                     ("naked_usd_pct", "naked_other_pct", "equity_fund_pct"))
        ok = abs(wedge + others - 100) <= 0.2
        checks.append((f"fubon pie closes ({p})", ok))
        if not ok:
            problems.append(f"fubon {p}: wedge {wedge} + others {others} = {wedge + others}")
            continue
        naked = 100 - wedge  # net open = everything the hedged wedge excludes
        vint = f"{y}-{Q_END[em]}"
        emit(1, "economic_hedge_ratio", "fubon_life", obs, "Q", wedge / 100, "ratio",
             "deck_disclosed", "IFRS17" if y >= 2026 else "IFRS4",
             r["url"], "富邦金控 results deck, Fubon Life hedging page",
             note="the deck's own wedge 外匯交換、無本金遠期外匯、外幣保單 — derivatives "
                  "plus FX-policy backing as a share of FX assets; the wedge names its "
                  "contents, so the base is stated, not inferred (decisions 4.2)",
             vintage=vint)
        emit(2, "net_open_fx_share", "fubon_life", obs, "Q", naked / 100, "share of FX assets",
             "deck_disclosed", "IFRS17" if y >= 2026 else "IFRS4",
             r["url"], "富邦金控 results deck, Fubon Life hedging page",
             note="complement of the economic-hedge wedge: unhedged currency positions, "
                  "plus the separately-drawn equity/mutual-fund wedge in the 2014-15 editions",
             vintage=vint)

    # ---------- hedge cost, bp of FX assets ----------
    for r in csv.DictReader(open(ROOT / "data" / "fubon_recurring_cost.csv", encoding="utf-8")):
        if r["sum_ties_total"] != "True":
            continue
        p = r["period"]
        y, em = period_parts(p)
        emit(7, "hedge_cost_recurring", "fubon_life", f"{y}-{Q_START[em]}", "Q",
             -float(r["recurring_bps"]), "bp of FX assets", "deck_disclosed",
             "IFRS17" if y >= 2026 else "IFRS4", FUBON_DECKS,
             "富邦金控 results deck, 經常性避險成本 (legend-colour bound, sum-verified)",
             note="recurring hedge cost only; the deck's headline bar is the all-in FX "
                  "result (decisions 3.15/3.17). Positive = cost.",
             vintage=f"{y}-{Q_END[em]}")

    for r in csv.DictReader(open(ROOT / "data" / "cathay_fx_quarterly.csv", encoding="utf-8")):
        cost = num(r["hedging_cost_pct"])
        if cost is None:
            continue
        y, em = period_parts(r["period"])
        emit(7, "hedge_cost_recurring", "cathay_life", f"{y}-{Q_START[em]}", "Q",
             cost * 100, "bp of FX assets", "deck_disclosed",
             "IFRS17" if y >= 2026 else "IFRS4", CATHAY_DECKS,
             "國泰金控 results deck, hedging cost",
             note="the page states its base: 'Hedging cost is calculated based on FX assets'. "
                  "Positive = cost.",
             vintage=r["deck_date"])

    # ---------- write ----------
    cols = ["series_id", "series_key", "entity_id", "obs_date", "freq", "value",
            "unit", "definition_version", "basis", "basis_note", "source_url",
            "source_doc", "vintage"]
    csv_path = ROOT / "data" / "derived_series_firm.csv"
    rows.sort(key=lambda r: (r["series_id"], r["entity_id"], r["obs_date"]))
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    now = dt.datetime.now(dt.timezone.utc).isoformat()

    def sqlv(v):
        if v is None:
            return "null"
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
        return str(v)

    vals = ",\n  ".join("(" + ", ".join(sqlv(r[c]) for c in cols) + ")" for r in rows)
    sql = f"""-- derive-firm: generated by scripts/derive_firm_series.py at {now}. Idempotent.
begin;
with vals({', '.join(cols)}) as (values
  {vals})
insert into tlfx.derived_series
  (series_id, series_key, entity_id, obs_date, freq, value, unit,
   definition_version, basis, basis_note, source_url, source_doc,
   retrieved_at, vintage)
select series_id, series_key, entity_id, obs_date::date, freq::tlfx.frequency,
  value, unit, definition_version, basis, basis_note, source_url, source_doc,
  '{now}'::timestamptz, vintage::date
from vals
on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) do nothing;
commit;
"""
    tag = dt.date.today().strftime("%Y%m%d")
    out = ROOT / "out" / f"derive_firm_{tag}.sql"
    out.write_text(sql, encoding="utf-8")

    nok = sum(1 for _, o in checks if o)
    by = {}
    for r in rows:
        by[(r["series_key"], r["entity_id"])] = by.get((r["series_key"], r["entity_id"]), 0) + 1
    print(f"rows: {len(rows)}; checks {nok}/{len(checks)}; problems: {len(problems)}")
    for p in problems:
        print("  PROBLEM", p)
    for k, v in sorted(by.items()):
        print(f"  {k[1]:12} {k[0]:24} {v}")
    print(f"sum(value): {round(sum(r['value'] for r in rows), 4)}")
    print(f"csv: {csv_path.relative_to(ROOT)}\nsql: {out.relative_to(ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
