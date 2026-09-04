#!/usr/bin/env python3
"""Stage 2b — CBC statistics-database API, table EF67M01 -> sector_balance_sheet history.

The CBC Statistical Database exposes appendix table 8 as JSON:

    https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=EF67M01

monthly from 1987-05 — thirty-seven years further back than the rolling CSV.
**Use the Chinese item code.** The English variant (`EF67M01en`) is served
through a broken chunker: each period needs 31 cells but rows carry 30 plus the
marker, so alignment drifts one period every 31 and the payload ends ~15 months
short of its labels (decisions 2.2). The Chinese payload is exact: 471 rows,
each `[YYYYMMM marker, (amount, annual growth)×15]` in the same line order as
the CSV parser's COLUMNS.

Validation before anything is written:
  - every row is 31 cells with a leading period marker, in month order;
  - the three balance-sheet identities of stage2a hold on every month where the
    inputs exist (the life & investment-contract liabilities line is null in
    the API from 2025-01 — the CSV channel carries those months);
  - every (month, line) present in both this API and the already-ingested CSV
    must agree exactly; one disagreement fails the run.

Overlapping months keep their CSV-sourced rows (same natural key, insert is
`on conflict do nothing`); the API contributes 1987-05 → 2016-11 and the
2017-2024 months the CSV's window has already rolled past.

Writes data/sector_balance_sheet_history.csv, out/stage2b_cbc_api_YYYYMMDD.sql,
reports/stage2b_cbc_api_YYYYMMDD.json. Exit 1 on any failure.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tlfx.emit import render_sql, write_csv, write_report  # noqa: E402
from tlfx.provenance import ReconciliationCheck, RunLog, fetch, utc_now  # noqa: E402

API_URL = "https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=EF67M01"
SOURCE_DOC = "CBC Statistical Database API, item EF67M01 (life insurance companies' assets and liabilities, monthly)"
CACHE = ROOT / "cache" / "cbc"
DATA_CSV = ROOT / "data" / "sector_balance_sheet_history.csv"
EXISTING_CSV = ROOT / "data" / "sector_balance_sheet.csv"
OUT_DIR = ROOT / "out"
REPORT_DIR = ROOT / "reports"

# API line order == the CSV parser's column order (verified against 2026-07).
LINE_CODES = [
    ("foreign_assets",            "國外資產",             "Foreign assets"),
    ("loans",                     "放款",                 "Loans"),
    ("portfolio_nonfin_total",    "對非金融機構證券投資 計", "Portfolio investments in entities excluding financial institutions, subtotal"),
    ("portfolio_nonfin_govt",     "政府機關",             "Government agencies"),
    ("portfolio_nonfin_govt_ent", "公營事業",             "Government enterprises"),
    ("portfolio_nonfin_private",  "民營企業",             "Private enterprises"),
    ("portfolio_fin",             "對金融機構證券投資",     "Portfolio investments in financial institutions"),
    ("real_estate",               "不動產投資",            "Real estate investments"),
    ("claims_on_fin",             "對金融機構債權",         "Claims on financial institutions"),
    ("cash_in_vaults",            "庫存現金",              "Cash in vaults"),
    ("other_assets",              "其他資產",              "Other assets"),
    ("total_assets",              "資產合計",              "Total assets = total liabilities and equity"),
    ("life_and_ic_liabilities",   "人壽保險與投資合約負債",  "Life insurance and investment contract liabilities"),
    ("other_liabilities",         "其他負債",              "Other liabilities"),
    ("equity",                    "權益",                 "Equity"),
]
ASSET_PARTS = [c for c, _, _ in LINE_CODES[:11] if c != "portfolio_nonfin_govt"
               and c != "portfolio_nonfin_govt_ent" and c != "portfolio_nonfin_private"]
NONFIN_PARTS = ("portfolio_nonfin_govt", "portfolio_nonfin_govt_ent", "portfolio_nonfin_private")
LE_PARTS = ("life_and_ic_liabilities", "other_liabilities", "equity")

_MARK = re.compile(r"^(\d{4})M(\d{2})$")


def to_mn(cell) -> Decimal | None:
    s = str(cell).strip()
    if s in ("-", "", "None"):
        return None
    return Decimal(s)


def parse(payload: bytes) -> dict[date, dict[str, Decimal | None]]:
    j = json.loads(payload)
    out: dict[date, dict[str, Decimal | None]] = {}
    prev: date | None = None
    for row in j["data"]["dataSets"]:
        if len(row) != 31 or not (m := _MARK.match(str(row[0]))):
            raise ValueError(f"malformed row: {str(row)[:120]}")
        obs = date(int(m.group(1)), int(m.group(2)), 1)
        if prev and (obs.year, obs.month) <= (prev.year, prev.month):
            raise ValueError(f"months out of order at {obs}")
        prev = obs
        vals = {code: to_mn(row[1 + 2 * k]) for k, (code, _, _) in enumerate(LINE_CODES)}
        out[obs] = vals
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    log = RunLog(stage="stage2b-cbc-api")
    run_id = str(uuid.uuid4())
    retrieved_at = utc_now().isoformat()

    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "EF67M01.json"
    if cached.exists() and not args.refresh:
        payload = cached.read_bytes()
    else:
        fr = fetch(API_URL, source_doc=SOURCE_DOC, timeout=150, basis="disclosed")
        ok = fr.provenance.http_status == 200 and len(fr.content) > 50_000
        log.record_source(fr.provenance, ok=ok, note=None if ok else f"status {fr.provenance.http_status}")
        if not ok:
            print(f"fetch failed: {fr.provenance.http_status}", file=sys.stderr)
            return 1
        payload = fr.content
        cached.write_bytes(payload)

    months = parse(payload)
    vintage = max(months)
    checks: list[ReconciliationCheck] = []

    # identities, where inputs exist
    for obs, v in months.items():
        tag = obs.strftime("%Y-%m")
        if all(v[c] is not None for c in ASSET_PARTS) and v["total_assets"] is not None:
            checks.append(ReconciliationCheck(
                name=f"asset components = total assets ({tag})",
                lhs=float(sum(v[c] for c in ASSET_PARTS)), rhs=float(v["total_assets"]), unit="NT$ mn"))
        if all(v[c] is not None for c in NONFIN_PARTS) and v["portfolio_nonfin_total"] is not None:
            checks.append(ReconciliationCheck(
                name=f"non-financial portfolio parts = subtotal ({tag})",
                lhs=float(sum(v[c] for c in NONFIN_PARTS)), rhs=float(v["portfolio_nonfin_total"]), unit="NT$ mn"))
        if all(v[c] is not None for c in LE_PARTS) and v["total_assets"] is not None:
            checks.append(ReconciliationCheck(
                name=f"liabilities + equity = total assets ({tag})",
                lhs=float(sum(v[c] for c in LE_PARTS)), rhs=float(v["total_assets"]), unit="NT$ mn"))

    # exact agreement with the already-ingested CSV channel on every overlap
    import csv as _csv
    existing: dict[tuple[str, str], Decimal] = {}
    if EXISTING_CSV.exists():
        for r in _csv.DictReader(EXISTING_CSV.open(encoding="utf-8")):
            existing[(r["obs_month"], r["line_code"])] = Decimal(r["value_ntd_mn"])
    overlap = mismatches = 0
    for obs, v in months.items():
        for code, _, _ in LINE_CODES:
            key = (obs.isoformat(), code)
            if key in existing and v[code] is not None:
                overlap += 1
                if existing[key] != v[code]:
                    mismatches += 1
                    checks.append(ReconciliationCheck(
                        name=f"API agrees with CSV channel ({obs:%Y-%m} {code})",
                        lhs=float(v[code]), rhs=float(existing[key]), unit="NT$ mn", tolerance=0.0))
    checks.append(ReconciliationCheck(
        name=f"API/CSV overlap: {overlap} cells compared", lhs=float(mismatches), rhs=0.0,
        unit="mismatches", tolerance=0.0))

    for c in checks:
        log.record_check(c)

    rows: list[dict] = []
    for obs in sorted(months):
        for code, zh, en in LINE_CODES:
            val = months[obs][code]
            if val is None:
                continue
            rows.append({
                "obs_month": obs.isoformat(), "vintage": vintage.isoformat(),
                "line_code": code, "line_label_zh": zh, "line_label_en": en,
                "value_ntd_mn": val, "source_url": API_URL, "source_doc": SOURCE_DOC,
                "retrieved_at": retrieved_at,
            })

    write_csv(DATA_CSV, rows)
    OUT_DIR.mkdir(exist_ok=True)
    sql_path = OUT_DIR / f"stage2b_cbc_api_{date.today():%Y%m%d}.sql"
    sql_path.write_text(render_sql(
        table="tlfx.sector_balance_sheet", conflict=("obs_month", "line_code", "vintage"),
        rows=rows, run_id=run_id, stage="stage2b-cbc-api", log=log, checks=checks,
        generator="scripts/stage2_cbc_history.py"), encoding="utf-8")

    mkeys = sorted(months)
    s = log.summary()
    report = {
        "run_id": run_id, "summary": s, "rows": len(rows), "months": len(mkeys),
        "month_range": [mkeys[0].isoformat(), mkeys[-1].isoformat()],
        "vintage": vintage.isoformat(), "overlap_cells": overlap, "overlap_mismatches": mismatches,
        "failed_checks": log.failed_checks,
        "outputs": {"csv": str(DATA_CSV.relative_to(ROOT)), "sql": str(sql_path.relative_to(ROOT))},
    }
    rpt = REPORT_DIR / f"stage2b_cbc_api_{date.today():%Y%m%d}.json"
    write_report(rpt, report)

    print(f"months: {len(mkeys)} ({mkeys[0]:%Y-%m} → {mkeys[-1]:%Y-%m}); rows: {len(rows)}; "
          f"overlap cells {overlap}, mismatches {mismatches}; "
          f"checks {s['checks_total'] - s['checks_failed']}/{s['checks_total']}")
    for c in log.failed_checks[:10]:
        print(f"  FAIL {c['check_name']}: {c['lhs']:.0f} vs {c['rhs']:.0f}")
    print(f"csv: {DATA_CSV.relative_to(ROOT)}\nsql: {sql_path.relative_to(ROOT)}\nreport: {rpt.relative_to(ROOT)}")
    return 1 if log.failed_checks else 0


if __name__ == "__main__":
    raise SystemExit(main())
