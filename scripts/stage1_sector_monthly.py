#!/usr/bin/env python3
"""Stage 1a — FSC monthly sector release -> tlfx.sector_monthly (v1 channel).

Locates every edition of the monthly release on the FSC and Insurance Bureau
press channels (`tlfx.fsc`), fetches each page into a local cache, parses it
(`tlfx.fsc_parse`), runs the arithmetic and cross-edition reconciliation
checks, and emits:

    data/sector_monthly_release.csv       one row per edition, NT$ mn
    reports/stage1_release_YYYYMMDD.json  run summary, checks, warnings
    out/stage1_release_YYYYMMDD.sql       idempotent INSERTs for
                                          tlfx.sector_monthly, run_log,
                                          run_source_status, run_reconciliation

The SQL is what gets applied to the project (through the Supabase MCP or
psql); with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY set, `--write` posts the
rows to PostgREST directly instead (schema `tlfx` must be exposed in the API
settings for that path; it is not by default, hence the SQL route).

Exit codes: 0 ok; 1 a reconciliation check failed (README section 3: a breach
fails the run); 2 nothing could be located or fetched.

Coverage: 91 editions May 2018 – Dec 2025 (March 2019 missing at source, March
2020 retitled). The series has no 2026 edition; the 2026 rows come from
`stage1_briefing_press.py`. See docs/decisions.md 1.1–1.3.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tlfx.emit import render_sql, write_csv, write_report  # noqa: E402
from tlfx.fsc import Release, find_monthly_releases  # noqa: E402
from tlfx.fsc_parse import SectorRelease, internal_checks, parse_release  # noqa: E402
from tlfx.provenance import Provenance, ReconciliationCheck, RunLog, fetch, utc_now  # noqa: E402

CACHE = ROOT / "cache" / "fsc"
DATA_CSV = ROOT / "data" / "sector_monthly_release.csv"
REPORT_DIR = ROOT / "reports"
OUT_DIR = ROOT / "out"

# SectorRelease field -> sector_monthly column (identity unless listed).
COLUMN_MAP = {
    "dataserno": "source_id",
    "published": "vintage",
}
SKIP_FIELDS = {"title", "warnings", "fx_combined_effect_narrative"}
CONSTANT_COLUMNS = {
    "basis": "disclosed",
    "reporting_channel": "release",
    "flows_are_ytd": True,
}


def load_editions(offline: bool) -> tuple[list[Release], list[Provenance]]:
    if offline:
        rels = []
        for fn in sorted(CACHE.glob("*.html")):
            html = fn.read_bytes()
            try:
                rel = parse_release(html, dataserno=fn.stem)
            except Exception:
                continue
            rels.append(Release(dataserno=fn.stem, title=rel.title, reference_month=rel.obs_month, url=""))
        rels.sort(key=lambda r: r.reference_month, reverse=True)
        return rels, []
    return find_monthly_releases()


def get_html(rel: Release, log: RunLog, *, refresh: bool) -> bytes | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{rel.dataserno}.html"
    if path.exists() and not refresh and path.stat().st_size > 20_000:
        return path.read_bytes()
    if not rel.url:
        return None
    try:
        fr = fetch(rel.url, source_doc=rel.title, vintage=rel.published_date, timeout=60)
    except Exception as exc:  # transport exhausted
        log.record_source(Provenance(source_url=rel.url, source_doc=rel.title, retrieved_at=utc_now()),
                          ok=False, note=f"{type(exc).__name__}: {exc}"[:300])
        return None
    ok = fr.provenance.http_status == 200 and len(fr.content) > 20_000
    log.record_source(fr.provenance, ok=ok, note=None if ok else "unexpected status or short body")
    if ok:
        path.write_bytes(fr.content)
        time.sleep(0.4)  # be polite to a government CMS
        return fr.content
    return None


def cross_edition_checks(parsed: list[SectorRelease]) -> list[ReconciliationCheck]:
    """The narrative's stated change in the reserve balance must tie to the
    balance printed in the edition it compares against. Relative error is
    taken on the balance, so 1 億 print rounding stays far inside 3%."""
    by_month = {p.obs_month: p for p in parsed}
    checks: list[ReconciliationCheck] = []
    for p in sorted(parsed, key=lambda x: x.obs_month):
        if p.fx_reserve_total is None or p.fx_reserve_change is None:
            continue
        if p.fx_reserve_change_basis == "prev_year_end":
            ref = by_month.get(date(p.obs_month.year - 1, 12, 1))
        elif p.fx_reserve_change_basis == "prev_month":
            y, m = p.obs_month.year, p.obs_month.month
            ref = by_month.get(date(y - (m == 1), 12 if m == 1 else m - 1, 1))
        else:
            ref = None
        if ref is None or ref.fx_reserve_total is None:
            continue
        checks.append(ReconciliationCheck(
            name=f"reserve balance ties to {p.fx_reserve_change_basis} ({p.obs_month:%Y-%m})",
            lhs=float(ref.fx_reserve_total + p.fx_reserve_change),
            rhs=float(p.fx_reserve_total),
            unit="NT$ mn",
        ))
    return checks


def to_db_row(p: SectorRelease, retrieved_at: str) -> dict:
    row = {}
    for k, v in p.as_row().items():
        if k in SKIP_FIELDS:
            continue
        row[COLUMN_MAP.get(k, k)] = v
    row.update(CONSTANT_COLUMNS)
    row["source_url"] = (
        "https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp"
        f"&dataserno={p.dataserno}&dtable=News"
    )
    row["source_doc"] = f"FSC press release: {p.title}"
    row["retrieved_at"] = retrieved_at
    if p.warnings:
        row["source_note"] = "; ".join(p.warnings)
    return row


def postgrest_write(rows: list[dict]) -> None:
    import requests

    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/sector_monthly"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    hdrs = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "Content-Profile": "tlfx", "Prefer": "resolution=ignore-duplicates,return=minimal"}
    for i in range(0, len(rows), 50):
        resp = requests.post(url, headers=hdrs, data=json.dumps(rows[i:i + 50]), timeout=60)
        resp.raise_for_status()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="parse the cache only; no network")
    ap.add_argument("--refresh", action="store_true", help="re-fetch cached pages")
    ap.add_argument("--limit", type=int, default=0, help="newest N editions only")
    ap.add_argument("--write", action="store_true", help="POST rows to PostgREST (needs SUPABASE_* env)")
    args = ap.parse_args()

    log = RunLog(stage="stage1-release")
    run_id = str(uuid.uuid4())
    rels, provs = load_editions(args.offline)
    for p in provs:
        log.record_source(p, ok=True)
    if not rels:
        print("no editions located", file=sys.stderr)
        return 2
    if args.limit:
        rels = rels[: args.limit]

    parsed: list[SectorRelease] = []
    for rel in rels:
        html = get_html(rel, log, refresh=args.refresh)
        if html is None:
            continue
        try:
            p = parse_release(html, dataserno=rel.dataserno)
        except Exception as exc:
            log.record_source(Provenance(source_url=rel.url, source_doc=rel.title, retrieved_at=utc_now()),
                              ok=False, note=f"parse: {exc}"[:300])
            continue
        parsed.append(p)
    if not parsed:
        print("nothing parsed", file=sys.stderr)
        return 2
    parsed.sort(key=lambda p: p.obs_month)

    checks: list[ReconciliationCheck] = []
    for p in parsed:
        for name, ok, detail in internal_checks(p):
            lhs, rhs = (float(x) for x in detail.split(" vs "))
            c = ReconciliationCheck(name=f"{name} ({p.obs_month:%Y-%m})", lhs=lhs, rhs=rhs, unit="NT$ mn")
            # rounding to NT$ 1 億 per printed figure: pass if within 150 mn even when tiny
            if not c.passed and abs(lhs - rhs) <= 150:
                c = ReconciliationCheck(name=c.name, lhs=lhs, rhs=rhs, tolerance=1.0, unit="NT$ mn (rounding)")
            checks.append(c)
    checks.extend(cross_edition_checks(parsed))
    for c in checks:
        log.record_check(c)

    retrieved_at = utc_now().isoformat()
    rows = [to_db_row(p, retrieved_at) for p in parsed]

    write_csv(DATA_CSV, rows)

    OUT_DIR.mkdir(exist_ok=True)
    sql_path = OUT_DIR / f"stage1_release_{date.today():%Y%m%d}.sql"
    sql_path.write_text(
        render_sql(table="tlfx.sector_monthly", conflict=("obs_month", "reporting_channel", "vintage"),
                   rows=rows, run_id=run_id, stage="stage1-release", log=log, checks=checks,
                   generator="scripts/stage1_sector_monthly.py"),
        encoding="utf-8",
    )

    if args.write:
        postgrest_write(rows)

    report = {
        "run_id": run_id,
        "summary": log.summary(),
        "editions": len(parsed),
        "first": parsed[0].obs_month.isoformat(),
        "last": parsed[-1].obs_month.isoformat(),
        "warnings": {p.obs_month.isoformat(): p.warnings for p in parsed if p.warnings},
        "failed_checks": log.failed_checks,
        "checks": log.checks,
        "sources_failed": [s for s in log.sources if not s["ok"]],
        "outputs": {"csv": str(DATA_CSV.relative_to(ROOT)), "sql": str(sql_path.relative_to(ROOT))},
    }
    rpt = REPORT_DIR / f"stage1_release_{date.today():%Y%m%d}.json"
    write_report(rpt, report)

    s = log.summary()
    print(f"editions parsed: {len(parsed)}  ({parsed[0].obs_month:%Y-%m} → {parsed[-1].obs_month:%Y-%m})")
    print(f"checks: {s['checks_total'] - s['checks_failed']}/{s['checks_total']} passed; "
          f"sources ok {s['sources_ok']}/{s['sources_total']}")
    for c in log.failed_checks:
        print(f"  FAIL {c['check_name']}: {c['lhs']} vs {c['rhs']} (rel {c['rel_error']})")
    print(f"csv: {DATA_CSV.relative_to(ROOT)}\nsql: {sql_path.relative_to(ROOT)}\nreport: {rpt.relative_to(ROOT)}")
    return 1 if log.failed_checks else 0


if __name__ == "__main__":
    raise SystemExit(main())
