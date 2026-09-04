#!/usr/bin/env python3
"""Sector derived series (README §3: series 2, 3, 4, 5) from the loaded data.

Everything here stays inside ONE regulatory scope — the briefing's own
figures — or is explicitly marked estimated where scopes are crossed. The
FSC-basis 國外投資 (ib_indicators) is never paired with the regulatory ratio
(decisions 2.3): the regulatory denominator is ~68% of it.

Two in-document identities carry the derivation (both verified per month):
  net_fx_exposure = denominator × (1 − ratio)   (exact at 2025-12: 15.4tn ×
      0.4977 = 7.66tn ≈ the rounded 7.7tn published)
  buffer_total / net_fx_exposure = absorbable appreciation %   (2026-03:
      911,100/8,607,300 = 10.59% vs published 10.6)

Emitted (sector rows, entity_id null, freq M):
  s4 reg_hedge_ratio            v1/v2 (Feb-2026 notice break), press_reported
  s4 reg_hedge_ratio_effective  the Bureau's own with-buffers memo, v2
  s2 net_open_fx                NT$ mn: published where given; v2 identity
  s2 reg_denominator            NT$ mn: published anchors + v2 identity
  s5 hedge_principal            NT$ mn = denominator − net (or ratio×denom)
  s5 gross_hedge_ratio          hedge_principal / FSC 國外投資 — the ONE
      deliberate cross-scope construct (the sell-side quote), basis estimated
  s3 buffer_total               NT$ mn v2, press_reported
  s3 absorbable_appreciation    % v2, press_reported (checked vs buffer/net)

Writes data/derived_series_sector.csv and out/derive_sector_YYYYMMDD.sql.
"""
import csv
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2_START = "2026-01-01"  # Feb-2026 notice applies to obs from Jan 2026


def num(s):
    return None if s in (None, "") else float(s)


def main():
    briefing = {r["obs_month"]: r for r in
                csv.DictReader(open(ROOT / "data" / "sector_monthly_briefing.csv", encoding="utf-8"))}
    fi = {r["obs_month"]: (int(r["foreign_investments"]), r) for r in
          csv.DictReader(open(ROOT / "data" / "ib_indicators_monthly.csv", encoding="utf-8"))}

    rows, checks, problems = [], [], []

    def emit(sid, key, obs, value, unit, ver, basis, src, note=None, vintage=None):
        if value is None:
            return
        rows.append({"series_id": sid, "series_key": key, "obs_date": obs,
                     "freq": "M", "value": round(value, 6), "unit": unit,
                     "definition_version": ver, "basis": basis,
                     "basis_note": note, "source_url": src["source_url"],
                     "source_doc": src.get("source_doc"),
                     "vintage": vintage or src["vintage"]})

    for obs, r in sorted(briefing.items()):
        ver = "v2" if obs >= V2_START else "v1"
        ratio = num(r["hedge_ratio_regulatory"])
        denom_pub = num(r["regulatory_fx_exposure"])
        net_pub = num(r["net_fx_exposure"])
        buf = num(r["fx_buffer_total"])
        absorb = num(r["buffer_absorbable_appreciation_pct"])
        eff = num(r["effective_hedge_ratio_memo"])

        emit(4, "reg_hedge_ratio", obs, ratio, "ratio", ver, "press_reported", r)
        emit(4, "reg_hedge_ratio_effective", obs, eff, "ratio", ver, "press_reported", r,
             note="Bureau's own effective ratio including buffers (briefing memo)")
        emit(2, "net_open_fx", obs, net_pub, "NT$ mn", ver, "press_reported", r)
        emit(3, "buffer_total", obs, buf, "NT$ mn", ver, "press_reported", r)
        emit(3, "absorbable_appreciation", obs, absorb, "pct", ver, "press_reported", r)

        # identity check: published buffer/net vs published absorbable %
        if buf is not None and net_pub is not None and absorb is not None:
            got = buf / net_pub * 100
            ok = abs(got - absorb) <= 0.25
            checks.append((f"buffer/net ties absorbable% ({obs[:7]})", ok, got, absorb))
            if not ok:
                problems.append(f"{obs[:7]}: buffer/net {got:.2f} vs published {absorb}")

        # denominator: published anchor, else v2 identity net/(1-ratio)
        denom = denom_pub
        dver, dnote = ver, None
        if denom is None and net_pub is not None and ratio is not None:
            denom = net_pub / (1 - ratio)
            dver, dnote = ver + "_identity", "net_fx_exposure / (1 - ratio); both press_reported, same scope"
        emit(2, "reg_denominator", obs, denom, "NT$ mn",
             dver, "press_reported" if denom_pub is not None else "estimated", r, note=dnote)

        # identity check where both published: net = denom * (1 - ratio)
        if denom_pub is not None and net_pub is not None and ratio is not None:
            got = denom_pub * (1 - ratio)
            ok = abs(got - net_pub) / net_pub <= 0.01  # denom rounded to 0.1tn
            checks.append((f"net = denom*(1-ratio) ({obs[:7]})", ok, got, net_pub))
            if not ok:
                problems.append(f"{obs[:7]}: denom*(1-ratio) {got:,.0f} vs net {net_pub:,.0f}")

        # hedge principal, same scope
        principal = None
        if denom is not None and ratio is not None:
            principal = denom * ratio
        elif denom is not None and net_pub is not None:
            principal = denom - net_pub
        emit(5, "hedge_principal", obs, principal, "NT$ mn",
             dver, "estimated", r,
             note="regulatory denominator x ratio (single scope; denominator "
                  + ("published" if denom_pub is not None else "recovered by identity"))

        # gross hedge ratio: principal / FSC-basis FI — deliberate cross-scope
        if principal is not None and obs in fi:
            fival, fir = fi[obs]
            emit(5, "gross_hedge_ratio", obs, principal / fival, "ratio",
                 dver, "estimated", r,
                 note=f"hedge principal (regulatory scope) / FSC 國外投資 {fival:,.0f} "
                      "(ib_indicators) — the cross-scope construct sell-side quotes",
                 vintage=max(r["vintage"], fir["vintage"]))

    # write CSV
    cols = ["series_id", "series_key", "obs_date", "freq", "value", "unit",
            "definition_version", "basis", "basis_note", "source_url",
            "source_doc", "vintage"]
    csv_path = ROOT / "data" / "derived_series_sector.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # SQL
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    def sqlv(v):
        if v is None:
            return "null"
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
        return str(v)

    vals = ",\n  ".join(
        "(" + ", ".join(sqlv(r[c]) for c in cols) + ")" for r in rows)
    sql = f"""-- derive-sector: generated by scripts/derive_sector_series.py at {now}. Idempotent.
begin;
with vals({', '.join(cols)}) as (values
  {vals})
insert into tlfx.derived_series
  (series_id, series_key, entity_id, obs_date, freq, value, unit,
   definition_version, basis, basis_note, source_url, source_doc,
   retrieved_at, vintage)
select series_id, series_key, null, obs_date::date, freq::tlfx.frequency, value,
  unit, definition_version, basis, basis_note, source_url, source_doc,
  '{now}'::timestamptz, vintage::date
from vals
on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) do nothing;
commit;
"""
    tag = dt.date.today().strftime("%Y%m%d")
    out = ROOT / "out" / f"derive_sector_{tag}.sql"
    out.write_text(sql, encoding="utf-8")

    ok = sum(1 for _, o, *_ in checks if o)
    print(f"rows: {len(rows)}; checks {ok}/{len(checks)}; problems: {len(problems)}")
    for p in problems:
        print("  PROBLEM", p)
    by = {}
    for r in rows:
        by[r["series_key"]] = by.get(r["series_key"], 0) + 1
    print("per key:", by)
    print(f"sum(value): {round(sum(r['value'] for r in rows), 4)}")
    print(f"csv: {csv_path.relative_to(ROOT)}\nsql: {out.relative_to(ROOT)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
