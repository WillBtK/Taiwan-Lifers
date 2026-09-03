#!/usr/bin/env python3
"""Stage 1b — Insurance Bureau monthly briefing, press-reported -> tlfx.sector_monthly.

The sector hedge ratio, the reserve buckets and the net FX exposure are stated
orally at the Insurance Bureau's monthly briefing and never printed in the
monthly release (docs/decisions.md 1.2). `config/briefing_press.json` holds
the figures exactly as printed by the cited article; this script

  1. fetches every cited article (cache/press/), extracts its paragraph text;
  2. verifies each configured value string occurs in that text — a value that
     cannot be found in its own citation fails the run;
  3. converts units (億, 兆, %) to NT$ mn / fractions;
  4. runs the identity check the v2 definitions imply where the inputs exist:
        net exposure ≈ regulatory exposure × (1 − hedge ratio)
     and the bucket sum check  P + Q ≈ reserve total,  reserve + X + Y ≈ buffer;
  5. emits data/sector_monthly_briefing.csv, out/stage1_briefing_YYYYMMDD.sql,
     reports/stage1_briefing_YYYYMMDD.json and
     docs/sources/press/briefing_excerpts.md (URL, date, quoted sentence per row).

Rows carry basis = 'press_reported', reporting_channel = 'briefing_press',
vintage = publication date of the primary article. Exit 1 if verification or a
reconciliation check fails.
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

from bs4 import BeautifulSoup  # noqa: E402

from tlfx.emit import decimal_str, render_sql, write_csv, write_report  # noqa: E402
from tlfx.provenance import Provenance, ReconciliationCheck, RunLog, fetch, utc_now  # noqa: E402

CONFIG = ROOT / "config" / "briefing_press.json"
CACHE = ROOT / "cache" / "press"
DATA_CSV = ROOT / "data" / "sector_monthly_briefing.csv"
EXCERPTS = ROOT / "docs" / "sources" / "press" / "briefing_excerpts.md"
OUT_DIR = ROOT / "out"
REPORT_DIR = ROOT / "reports"

# Measured 2026-09-03: money.udn.com, news.cnyes.com and news.cts.com.tw all
# answer the default descriptive UA with 200 (no override needed).
FRACTION_FIELDS = {"hedge_ratio_regulatory", "effective_hedge_ratio_memo"}
PCT_FIELDS = {"buffer_absorbable_appreciation_pct", "hedge_cost_cs_annual_pct", "hedge_cost_ndf_annual_pct"}
TEXT_FIELDS = {"hedge_cs_share_note", "hedge_ndf_share_note"}
PLAIN_FIELDS = {"usdtwd_month_end"}

_NUM = re.compile(r"^(-?)([\d,]+(?:\.\d+)?)\s*(兆|億|%|％|元)?(?:元)?$")


def to_value(field: str, printed: str):
    if field in TEXT_FIELDS:
        return printed
    s = printed.replace(" ", "")
    # "8兆6073億元" / "1兆648億元" / "3兆9103億元"
    m = re.match(r"^(-?)(\d+(?:\.\d+)?)兆(\d+(?:,\d+)?(?:\.\d+)?)?億?元?$", s)
    if m:
        v = Decimal(m.group(2)) * Decimal(1_000_000)
        if m.group(3):
            v += Decimal(m.group(3).replace(",", "")) * 100
        return -v if m.group(1) else v
    m = _NUM.match(s)
    if not m:
        raise ValueError(f"{field}: cannot parse {printed!r}")
    v = Decimal(m.group(2).replace(",", ""))
    unit = m.group(3)
    if m.group(1):
        v = -v
    if unit == "兆":
        return v * Decimal(1_000_000)
    if unit == "億":
        return v * 100
    if unit in ("%", "％"):
        return v / 100 if field in FRACTION_FIELDS else v
    if field in PLAIN_FIELDS or unit in (None, "元"):
        return v
    raise ValueError(f"{field}: unhandled unit in {printed!r}")


def article_text(html: bytes) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for t in soup(["script", "style", "nav", "footer", "header", "aside"]):
        t.decompose()
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return title, "\n".join(paras)


def norm(s: str) -> str:
    return re.sub(r"[\s,，]", "", s).replace("％", "%")


def value_in_text(printed: str, text: str) -> bool:
    """The digits as printed (commas/spaces ignored) must occur in the article.
    Bounds like '>75%' are checked on their number only."""
    core = re.sub(r"^[<>≈約\-–—]+", "", printed.replace("–", "-"))
    core = re.sub(r"元$", "", core)
    core = core.replace("-", "")  # sign is ours, e.g. "-682億"
    if core in ("0",):
        return "0" in text
    return norm(core) in norm(text) or norm(core.replace("億", "")) in norm(text)


def get_article(url: str, log: RunLog, refresh: bool) -> tuple[bytes | None, str | None]:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9]+", "_", url.split("//", 1)[1])[:120]
    path = CACHE / f"{key}.html"
    if path.exists() and not refresh:
        return path.read_bytes(), None
    try:
        fr = fetch(url, source_doc="press article", timeout=45, basis="press_reported")
    except Exception as exc:
        log.record_source(Provenance(source_url=url, source_doc="press article", retrieved_at=utc_now()),
                          ok=False, note=f"{type(exc).__name__}: {exc}"[:300])
        return None, f"{type(exc).__name__}"
    ok = fr.provenance.http_status == 200 and len(fr.content) > 5_000
    log.record_source(fr.provenance, ok=ok, note=None if ok else f"status {fr.provenance.http_status}")
    if ok:
        path.write_bytes(fr.content)
        return fr.content, None
    return None, f"status {fr.provenance.http_status}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    log = RunLog(stage="stage1-briefing")
    run_id = str(uuid.uuid4())
    retrieved_at = utc_now().isoformat()
    rows: list[dict] = []
    verify_failures: list[str] = []
    excerpts: list[str] = ["# Insurance Bureau monthly briefing — press excerpts\n",
                           "Generated by `scripts/stage1_briefing_press.py`. One block per reference month: "
                           "the cited article(s), publication date, and the sentence(s) carrying the figures. "
                           "Full articles are cached locally (`cache/press/`, not committed).\n"]
    checks: list[ReconciliationCheck] = []

    for item in cfg["rows"]:
        obs = item["obs_month"]
        row: dict = {
            "obs_month": obs, "basis": "press_reported", "reporting_channel": "briefing_press",
            "flows_are_ytd": True, "retrieved_at": retrieved_at, "reported_by": item.get("reported_by"),
        }
        quotes, notes, secondary = [], [], []
        if item.get("note"):
            notes.append(item["note"])
        for i, src in enumerate(item["sources"]):
            html, err = get_article(src["url"], log, args.refresh)
            title, text = article_text(html) if html else ("", "")
            if i == 0:
                row["vintage"] = src["published"]
                row["source_url"] = src["url"]
                row["source_doc"] = f"{src['outlet']}: {title or '(not fetched)'}"
                row["source_id"] = src["url"].rstrip("/").rsplit("/", 1)[-1].split(".")[0]
            else:
                secondary.append(f"{src['url']} ({src['published']})")
            for field, printed in src["fields"].items():
                if html is None:
                    verify_failures.append(f"{obs} {field}: article not fetched ({err})")
                elif field not in TEXT_FIELDS and not value_in_text(printed, text):
                    # note fields ('>75%') transcribe a spoken bound ("高於7成"),
                    # not a printed figure, so they are not checked literally
                    verify_failures.append(f"{obs} {field}: {printed!r} not found in {src['url']}")
                row[field] = to_value(field, printed)
            quotes.append(src["quote"])
            if i == 0:
                excerpts.append(f"## {obs[:7]}\n")
            excerpts.append(f"- {src['url']} — {src['outlet']}, {src['published']}"
                            f"{' (primary)' if i == 0 else ''}\n  > {src['quote']}\n")
        if "fx_reserve_change" in row:
            row["fx_reserve_change_basis"] = "prev_month"
        row["source_quote"] = " ‖ ".join(quotes)
        if secondary:
            notes.append("Also: " + "; ".join(secondary))
        if notes:
            row["source_note"] = " ".join(notes)
        rows.append(row)

        # identities implied by the notice's definitions (docs/decisions.md 1.4)
        if all(k in row for k in ("regulatory_fx_exposure", "hedge_ratio_regulatory", "net_fx_exposure")):
            checks.append(ReconciliationCheck(
                name=f"net exposure = denominator × (1 − ratio) ({obs[:7]})",
                lhs=float(row["regulatory_fx_exposure"] * (1 - row["hedge_ratio_regulatory"])),
                rhs=float(row["net_fx_exposure"]), unit="NT$ mn"))
        if all(k in row for k in ("fx_reserve_volatility", "fx_reserve_fixed", "fx_reserve_total")):
            checks.append(ReconciliationCheck(
                name=f"P + Q = reserve total ({obs[:7]})",
                lhs=float(row["fx_reserve_volatility"] + row["fx_reserve_fixed"]),
                rhs=float(row["fx_reserve_total"]), unit="NT$ mn"))
        if all(k in row for k in ("fx_reserve_total", "special_reserve_fx_fixed", "fx_buffer_total")):
            y = row.get("special_reserve_fx_strengthening", Decimal(0))
            checks.append(ReconciliationCheck(
                name=f"reserve + X + Y = buffer total ({obs[:7]})",
                lhs=float(row["fx_reserve_total"] + row["special_reserve_fx_fixed"] + y),
                rhs=float(row["fx_buffer_total"]), unit="NT$ mn"))
        if all(k in row for k in ("fx_buffer_total", "net_fx_exposure", "buffer_absorbable_appreciation_pct")):
            checks.append(ReconciliationCheck(
                name=f"buffer / net exposure = absorbable appreciation ({obs[:7]})",
                lhs=float(row["fx_buffer_total"] / row["net_fx_exposure"] * 100),
                rhs=float(row["buffer_absorbable_appreciation_pct"]), unit="pct", tolerance=0.05))
    for c in checks:
        log.record_check(c)

    write_csv(DATA_CSV, rows)
    OUT_DIR.mkdir(exist_ok=True)
    sql_path = OUT_DIR / f"stage1_briefing_{date.today():%Y%m%d}.sql"
    sql_path.write_text(render_sql(table="tlfx.sector_monthly", conflict=("obs_month", "reporting_channel", "vintage"),
                                   rows=rows, run_id=run_id, stage="stage1-briefing", log=log, checks=checks,
                                   generator="scripts/stage1_briefing_press.py"), encoding="utf-8")
    EXCERPTS.parent.mkdir(parents=True, exist_ok=True)
    EXCERPTS.write_text("\n".join(excerpts), encoding="utf-8")

    report = {
        "run_id": run_id, "summary": log.summary(), "rows": len(rows),
        "months": [r["obs_month"] for r in rows],
        "verification_failures": verify_failures, "failed_checks": log.failed_checks, "checks": log.checks,
        "sources_failed": [s for s in log.sources if not s["ok"]],
        "outputs": {"csv": str(DATA_CSV.relative_to(ROOT)), "sql": str(sql_path.relative_to(ROOT)),
                    "excerpts": str(EXCERPTS.relative_to(ROOT))},
    }
    rpt = REPORT_DIR / f"stage1_briefing_{date.today():%Y%m%d}.json"
    write_report(rpt, report)

    s = log.summary()
    print(f"rows: {len(rows)} ({rows[0]['obs_month'][:7]} → {rows[-1]['obs_month'][:7]}); "
          f"verification failures: {len(verify_failures)}; checks {s['checks_total'] - s['checks_failed']}/{s['checks_total']}")
    for v in verify_failures:
        print("  VERIFY", v)
    for c in log.failed_checks:
        print(f"  FAIL {c['check_name']}: {c['lhs']:.0f} vs {c['rhs']:.0f} (rel {c['rel_error']})")
    for c in log.checks:
        if c["passed"]:
            print(f"  ok   {c['check_name']}: rel {c['rel_error']}")
    print(f"csv: {DATA_CSV.relative_to(ROOT)}\nsql: {sql_path.relative_to(ROOT)}\nreport: {rpt.relative_to(ROOT)}")
    return 1 if (verify_failures or log.failed_checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
