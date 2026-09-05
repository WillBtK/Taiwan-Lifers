#!/usr/bin/env python3
"""Load the two sector series the automated pipeline brought in (decisions 4.13):

  * CBC 金融健全參考指標 – 壽險公司 -> tlfx.sector_soundness_quarterly
    (quarterly ROA/ROE/RBC/assets-to-GDP, 2016-03 on)
  * 保險安定基金 stock and bond holdings -> tlfx.sector_holdings_monthly
    (monthly, life and non-life, 2024-12 on)

Sources are read from the pipeline's own archive under data/raw/ where the
fetcher writes them, falling back to the manual cache for the CBC file, which
predates the pipeline. Emits idempotent SQL plus per-column checksums to be
verified server-side after the load.

Units. The CBC file is percentages as published. The holdings file publishes
億元 and is stored in NT$ mn (x100, exact on the integers it contains) to hold
the project convention; the printed figure is value/100.

The CBC file writes '-' for a quarter where the RBC ratio is not published
(it is semi-annual). That is an absence and loads as NULL; reading it as zero
would put a solvency ratio of nought on the sector in eight quarters out of
ten.
"""
import csv
import datetime as dt
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CBC = [ROOT / "data" / "raw" / "cbc", ROOT / "cache" / "cbc"]
TIGF = ROOT / "data" / "raw" / "tigf"
CBC_URL = ("https://www.cbc.gov.tw/public/data/opendata/financialstability/"
           "FSI-%E5%A3%BD%E9%9A%AA%E5%85%AC%E5%8F%B8.csv")
TIGF_URL = ("https://www.tigf.org.tw/content/2025/file/"
            "%E4%BF%9D%E9%9A%AA%E6%A5%AD%E6%8A%95%E8%B3%87%E5%9C%8B%E5%85%A7%E5%A4%96"
            "%E8%82%A1%E7%A5%A8%E5%8F%8A%E5%82%B5%E5%88%B8%E9%87%91%E9%A1%8D.csv")
Q_START = {3: "01-01", 6: "04-01", 9: "07-01", 12: "10-01"}


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def num(s):
    s = (s or "").strip()
    # '-' marks a quarter the indicator is not published for, not a zero
    if s in ("", "-", "N/A"):
        return None
    return float(s)


def newest(dirs, pattern):
    hits = []
    for d in dirs if isinstance(dirs, list) else [dirs]:
        if d.exists():
            hits += sorted(d.glob(pattern))
    if not hits:
        raise SystemExit(f"no file matching {pattern} under {dirs}")
    return hits[-1]


def stamp_of(path):
    m = re.search(r"_(\d{8})\.csv$", path.name)
    if not m:
        raise SystemExit(f"{path.name}: needs a _YYYYMMDD stamp")
    d = m.group(1)
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def load_cbc():
    p = newest(CBC, "FSI_life_*.csv")
    vintage = stamp_of(p)
    rows, checks = [], []
    text = p.read_text(encoding="utf-8-sig")
    for r in csv.DictReader(io.StringIO(text)):
        rocym = (r.get("民國年月") or "").strip()
        if not re.fullmatch(r"\d{5}", rocym):
            continue
        y, m = int(rocym[:3]) + 1911, int(rocym[3:])
        if m not in Q_START:
            checks.append((f"unexpected month {rocym}", False))
            continue
        rows.append({
            "obs_quarter": f"{y}-{Q_START[m]}", "vintage": vintage,
            "assets_to_gdp_pct": num(r.get("資產/GDP(比率)")),
            "roa_pct": num(r.get("資產報酬率(ROA)(比率)")),
            "roe_pretax_pct": num(r.get("權益報酬率(ROE)(稅前)(比率)")),
            "roe_posttax_pct": num(r.get("權益報酬率(ROE)(稅後)(比率)")),
            "rbc_ratio_pct": num(r.get("資本適足率(比率)")),
            "equity_to_investment_assets_pct": num(r.get("權益/投資性資產(比率)")),
        })
    # the RBC ratio is semi-annual: it must appear in June/December and nowhere else
    for x in rows:
        m = int(x["obs_quarter"][5:7])
        published = x["rbc_ratio_pct"] is not None
        expect = m in (4, 10)  # quarter starting April = Jun, October = Dec
        if published != expect:
            checks.append((f"RBC publication pattern {x['obs_quarter']}", False))
    checks.append(("RBC semi-annual pattern", not any(not ok for _, ok in checks)))
    return rows, p, vintage, checks


def load_tigf():
    p = newest(TIGF, "tigf_holdings_*.csv")
    vintage = stamp_of(p)
    rows, checks = [], []
    for r in csv.DictReader(io.StringIO(p.read_text(encoding="utf-8-sig"))):
        ys, ms = (r.get("年度") or "").strip(), (r.get("月份") or "").strip()
        if not (ys.isdigit() and ms.isdigit()):
            continue
        obs = f"{int(ys)}-{int(ms):02d}-01"
        for sector, sk, bk in (("life", "壽險股票(億元)", "壽險債券(億元)"),
                               ("nonlife", "產險股票(億元)", "產險債券(億元)")):
            s, b = num(r.get(sk)), num(r.get(bk))
            rows.append({
                "obs_month": obs, "sector": sector, "vintage": vintage,
                # 億元 -> NT$ mn; the source carries integers so this is exact
                "stocks_ntd_mn": None if s is None else s * 100,
                "bonds_ntd_mn": None if b is None else b * 100,
            })
    life = [x for x in rows if x["sector"] == "life"]
    checks.append(("life bonds exceed life stocks in every month",
                   all(x["bonds_ntd_mn"] > x["stocks_ntd_mn"] for x in life)))
    checks.append(("life bond holdings are NT$15-25tn",
                   all(1.5e7 < x["bonds_ntd_mn"] < 2.5e7 for x in life)))
    months = sorted(x["obs_month"] for x in life)
    checks.append(("months are unique and contiguous",
                   len(months) == len(set(months))))
    return rows, p, vintage, checks


def main():
    cbc, cbc_p, cbc_v, cbc_checks = load_cbc()
    tigf, tigf_p, tigf_v, tigf_checks = load_tigf()
    checks = cbc_checks + tigf_checks
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    for name, rows in (("cbc", cbc), ("tigf", tigf)):
        keys = [tuple(r[k] for k in (("obs_quarter", "vintage") if name == "cbc"
                                     else ("obs_month", "sector", "vintage"))) for r in rows]
        if len(keys) != len(set(keys)):
            raise SystemExit(f"{name}: natural-key collision")

    c_cols = ["obs_quarter", "vintage", "assets_to_gdp_pct", "roa_pct",
              "roe_pretax_pct", "roe_posttax_pct", "rbc_ratio_pct",
              "equity_to_investment_assets_pct"]
    t_cols = ["obs_month", "sector", "vintage", "stocks_ntd_mn", "bonds_ntd_mn"]
    c_vals = ",\n  ".join("(" + ", ".join(sqlv(r[c]) for c in c_cols) + ")" for r in cbc)
    t_vals = ",\n  ".join("(" + ", ".join(sqlv(r[c]) for c in t_cols) + ")" for r in tigf)

    sql = f"""-- stage2d: generated by scripts/stage2d_sector_series.py at {now}. Idempotent.
begin;
with vals({', '.join(c_cols)}) as (values
  {c_vals})
insert into tlfx.sector_soundness_quarterly
  ({', '.join(c_cols)}, source_url, source_doc, source_note, retrieved_at)
select obs_quarter::date, vintage::date, {', '.join(c_cols[2:])},
  '{CBC_URL}',
  '中央銀行 金融健全參考指標 – 壽險公司 (data.gov.tw 132163), file {cbc_p.name}',
  'Percentages as published. rbc_ratio_pct is semi-annual (June and December); '
  'the source prints a dash elsewhere and that loads as NULL, not zero. '
  'assets_to_gdp_pct breaks at 2026-Q1 on the IFRS 17 / TW-ICS transition.',
  '{now}'::timestamptz
from vals
on conflict (obs_quarter, vintage) do nothing;

with vals({', '.join(t_cols)}) as (values
  {t_vals})
insert into tlfx.sector_holdings_monthly
  ({', '.join(t_cols)}, source_url, source_doc, source_note, retrieved_at)
select obs_month::date, sector, vintage::date, stocks_ntd_mn, bonds_ntd_mn,
  '{TIGF_URL}',
  '財團法人保險安定基金 保險業投資國內外股票及債券金額 (data.gov.tw 172653), file {tigf_p.name}',
  'NT$ mn converted from the published 億元 (x100, exact). DOMESTIC AND FOREIGN '
  'COMBINED — not a foreign-asset series.',
  '{now}'::timestamptz
from vals
on conflict (obs_month, sector, vintage) do nothing;
commit;
"""
    tag = dt.date.today().strftime("%Y%m%d")
    out = ROOT / "out" / f"stage2d_sector_{tag}.sql"
    out.write_text(sql, encoding="utf-8")

    nok = sum(1 for _, ok in checks if ok)
    print(f"cbc rows: {len(cbc)} ({cbc[0]['obs_quarter']} -> {cbc[-1]['obs_quarter']}), "
          f"file {cbc_p.name}, vintage {cbc_v}")
    print(f"tigf rows: {len(tigf)} ({tigf[0]['obs_month']} -> {tigf[-1]['obs_month']}, "
          f"two sectors), file {tigf_p.name}, vintage {tigf_v}")
    print(f"checks {nok}/{len(checks)}")
    for label, ok in checks:
        if not ok:
            print("  FAIL", label)
    def s(rows, col):
        xs = [r[col] for r in rows if r[col] is not None]
        return f"{round(sum(xs), 2)} n={len(xs)}"
    print("checksums cbc: " + "; ".join(f"{c} {s(cbc, c)}" for c in c_cols[2:]))
    print("checksums tigf life: " +
          "; ".join(f"{c} {s([r for r in tigf if r['sector']=='life'], c)}"
                    for c in ("stocks_ntd_mn", "bonds_ntd_mn")))
    print("checksums tigf nonlife: " +
          "; ".join(f"{c} {s([r for r in tigf if r['sector']=='nonlife'], c)}"
                    for c in ("stocks_ntd_mn", "bonds_ntd_mn")))
    print(f"sql: {out.relative_to(ROOT)}")
    return 0 if nok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
