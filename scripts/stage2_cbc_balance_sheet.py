#!/usr/bin/env python3
"""Stage 2a — CBC Financial Statistics Monthly, appendix table 8 -> tlfx.sector_balance_sheet.

"人壽保險公司資產負債統計表" / "Assets and liabilities of life insurance companies".
The published CSV is Big5, bilingual, with a flattened multi-row header and a
carried-forward ROC year in the date column. It is already in NT$ million, which
is the repo's storage unit, so no coercion is applied (README §5 conventions).

The file holds two blocks: year-end rows back to ROC 105 (2016) and a rolling
monthly window. Both are ingested; where a month appears in both, the values are
checked to agree and stored once.

Three identities hold exactly (to NT$ 1 mn) on every row and are run as checks:

    foreign + loans + portfolio(non-fin) + portfolio(fin) + real estate
        + claims on FIs + cash + other          = total assets
    life & investment-contract liabilities + other liabilities + equity
                                                = total assets
    government agencies + government enterprises + private enterprises
                                                = portfolio(non-fin) subtotal

Writes data/sector_balance_sheet.csv, out/stage2_cbc_YYYYMMDD.sql,
reports/stage2_cbc_YYYYMMDD.json. Exit 1 if any check fails.

History before 2016 is a separate job against the statistics database
(`cpx.cbc.gov.tw`), not this file — see HANDOFF.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tlfx.emit import write_csv, render_sql, write_report  # noqa: E402
from tlfx.provenance import ReconciliationCheck, RunLog, fetch, utc_now  # noqa: E402

CSV_URL = "https://www.cbc.gov.tw/public/data/EBOOKXLS/065_EF67_A4L.csv"
SOURCE_DOC = "CBC Financial Statistics Monthly, appendix table 8 (life insurance companies' balance sheet)"
CACHE = ROOT / "cache" / "cbc"
DATA_CSV = ROOT / "data" / "sector_balance_sheet.csv"
OUT_DIR = ROOT / "out"
REPORT_DIR = ROOT / "reports"

# column index -> (line_code, zh, en). Indices 1, 11 and 19 are spacer columns
# the flattened merged header leaves behind; 18 carries the English month label.
COLUMNS: dict[int, tuple[str, str, str]] = {
    2:  ("foreign_assets",            "國外資產",             "Foreign assets"),
    3:  ("loans",                     "放款",                 "Loans"),
    4:  ("portfolio_nonfin_total",    "對非金融機構證券投資 計", "Portfolio investments in entities excluding financial institutions, subtotal"),
    5:  ("portfolio_nonfin_govt",     "政府機關",             "Government agencies"),
    6:  ("portfolio_nonfin_govt_ent", "公營事業",             "Government enterprises"),
    7:  ("portfolio_nonfin_private",  "民營企業",             "Private enterprises"),
    8:  ("portfolio_fin",             "對金融機構證券投資",     "Portfolio investments in financial institutions"),
    9:  ("real_estate",               "不動產投資",            "Real estate investments"),
    10: ("claims_on_fin",             "對金融機構債權",         "Claims on financial institutions"),
    12: ("cash_in_vaults",            "庫存現金",              "Cash in vaults"),
    13: ("other_assets",              "其他資產",              "Other assets"),
    14: ("total_assets",              "資產合計",              "Total assets = total liabilities and equity"),
    15: ("life_and_ic_liabilities",   "人壽保險與投資合約負債",  "Life insurance and investment contract liabilities"),
    16: ("other_liabilities",         "其他負債",              "Other liabilities"),
    17: ("equity",                    "權益",                 "Equity"),
}

ASSET_PARTS = (2, 3, 4, 8, 9, 10, 12, 13)
LIAB_EQUITY_PARTS = (15, 16, 17)
NONFIN_PARTS = (5, 6, 7)

_DATE_FULL = re.compile(r"^(\d{3})\s+(\d{1,2})$")
_DATE_MONTH = re.compile(r"^(\d{1,2})$")


def to_mn(cell: str) -> Decimal | None:
    s = cell.replace(",", "").strip()
    return Decimal(s) if s else None


def parse(text: str) -> list[tuple[date, dict[int, Decimal | None]]]:
    """Rows as (obs_month, {column index: value}). The ROC year is stated on the
    first row of each block and carried forward on the rows beneath it."""
    out: list[tuple[date, dict[int, Decimal | None]]] = []
    roc_year: int | None = None
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 19 or not row[2].strip():
            continue
        c0 = row[0].strip()
        if m := _DATE_FULL.match(c0):
            roc_year, month = int(m.group(1)), int(m.group(2))
        elif (m := _DATE_MONTH.match(c0)) and roc_year is not None:
            month = int(m.group(1))
        else:
            continue
        out.append((date(roc_year + 1911, month, 1), {i: to_mn(row[i]) for i in COLUMNS}))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if cached")
    args = ap.parse_args()

    log = RunLog(stage="stage2-cbc")
    run_id = str(uuid.uuid4())
    retrieved_at = utc_now().isoformat()

    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "065_EF67_A4L.csv"
    if cached.exists() and not args.refresh:
        raw = cached.read_bytes()
        print(f"using cached {cached.relative_to(ROOT)} ({len(raw):,} bytes)")
    else:
        fr = fetch(CSV_URL, source_doc=SOURCE_DOC, timeout=90, basis="disclosed")
        ok = fr.provenance.http_status == 200 and len(fr.content) > 2_000
        log.record_source(fr.provenance, ok=ok, note=None if ok else f"status {fr.provenance.http_status}")
        if not ok:
            print(f"fetch failed: status {fr.provenance.http_status}", file=sys.stderr)
            return 1
        raw = fr.content
        cached.write_bytes(raw)

    parsed = parse(raw.decode("big5", errors="replace"))
    if not parsed:
        print("no data rows parsed", file=sys.stderr)
        return 1

    # The CSV path is stable while its contents roll monthly, and it carries no
    # publication stamp, so the edition is identified by its latest observation
    # month. That is stable across re-runs of the same edition, which matters:
    # the natural key is (obs_month, line_code, vintage), and a retrieval-date
    # vintage would mint a fresh set of rows on every run.
    vintage = max(m for m, _ in parsed)

    checks: list[ReconciliationCheck] = []
    seen: dict[date, dict[int, Decimal | None]] = {}
    duplicate_months: list[str] = []

    for obs, vals in parsed:
        tag = obs.strftime("%Y-%m")
        if all(vals[i] is not None for i in ASSET_PARTS) and vals[14] is not None:
            checks.append(ReconciliationCheck(
                name=f"asset components = total assets ({tag})",
                lhs=float(sum(vals[i] for i in ASSET_PARTS)), rhs=float(vals[14]), unit="NT$ mn"))
        if all(vals[i] is not None for i in LIAB_EQUITY_PARTS) and vals[14] is not None:
            checks.append(ReconciliationCheck(
                name=f"liabilities + equity = total assets ({tag})",
                lhs=float(sum(vals[i] for i in LIAB_EQUITY_PARTS)), rhs=float(vals[14]), unit="NT$ mn"))
        if all(vals[i] is not None for i in NONFIN_PARTS) and vals[4] is not None:
            checks.append(ReconciliationCheck(
                name=f"non-financial portfolio parts = subtotal ({tag})",
                lhs=float(sum(vals[i] for i in NONFIN_PARTS)), rhs=float(vals[4]), unit="NT$ mn"))

        if obs in seen:
            duplicate_months.append(tag)
            if seen[obs] != vals:
                differing = [COLUMNS[i][0] for i in COLUMNS if seen[obs][i] != vals[i]]
                checks.append(ReconciliationCheck(
                    name=f"year-end block agrees with monthly block ({tag}): {', '.join(differing)}",
                    lhs=1.0, rhs=0.0, unit="flag"))
            continue
        seen[obs] = vals

    rows: list[dict] = []
    for obs in sorted(seen):
        for idx, (code, zh, en) in COLUMNS.items():
            v = seen[obs][idx]
            if v is None:
                continue
            rows.append({
                "obs_month": obs.isoformat(), "vintage": vintage.isoformat(),
                "line_code": code, "line_label_zh": zh, "line_label_en": en,
                "value_ntd_mn": v, "source_url": CSV_URL, "source_doc": SOURCE_DOC,
                "retrieved_at": retrieved_at,
            })

    for c in checks:
        log.record_check(c)

    write_csv(DATA_CSV, rows)
    OUT_DIR.mkdir(exist_ok=True)
    sql_path = OUT_DIR / f"stage2_cbc_{date.today():%Y%m%d}.sql"
    sql_path.write_text(render_sql(
        table="tlfx.sector_balance_sheet", conflict=("obs_month", "line_code", "vintage"),
        rows=rows, run_id=run_id, stage="stage2-cbc", log=log, checks=checks,
        generator="scripts/stage2_cbc_balance_sheet.py"), encoding="utf-8")

    months = sorted(seen)
    report = {
        "run_id": run_id, "summary": log.summary(), "rows": len(rows),
        "months": len(months), "month_range": [months[0].isoformat(), months[-1].isoformat()],
        "vintage": vintage.isoformat(), "duplicate_months_deduped": duplicate_months,
        "line_codes": [c for c, _, _ in COLUMNS.values()],
        "failed_checks": log.failed_checks,
        "outputs": {"csv": str(DATA_CSV.relative_to(ROOT)), "sql": str(sql_path.relative_to(ROOT))},
    }
    rpt = REPORT_DIR / f"stage2_cbc_{date.today():%Y%m%d}.json"
    write_report(rpt, report)

    s = log.summary()
    print(f"months: {len(months)} ({months[0]:%Y-%m} → {months[-1]:%Y-%m}); rows: {len(rows)}; "
          f"vintage {vintage:%Y-%m}; checks {s['checks_total'] - s['checks_failed']}/{s['checks_total']}")
    if duplicate_months:
        print(f"  deduped (present in both blocks): {', '.join(duplicate_months)}")
    for c in log.failed_checks:
        print(f"  FAIL {c['check_name']}: {c['lhs']:.0f} vs {c['rhs']:.0f} (rel {c['rel_error']})")
    print(f"csv: {DATA_CSV.relative_to(ROOT)}\nsql: {sql_path.relative_to(ROOT)}\nreport: {rpt.relative_to(ROOT)}")
    return 1 if log.failed_checks else 0


if __name__ == "__main__":
    raise SystemExit(main())
