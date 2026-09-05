#!/usr/bin/env python3
"""Stage 3 (statutory channel): load the Insurance Bureau's firm-level
壽險財務業務指標 into tlfx.firm_statutory_indicators.

Source: ins-info.ib.gov.tw/opendata/json-06161610.aspx (表06161610), the
payload behind data.gov.tw dataset 7191. The origin is unreachable from the
sandbox (decisions 4.9), so the file is couriered: fetched by the user and
committed verbatim under data/raw/ins-info/json-06161610_YYYYMMDD.json. The
date in the filename is the snapshot date and becomes the vintage.

Shape: one record per insurer at its latest reported quarter (active firms at
115Q2; defunct firms at their last filing), fields ClaimYear (ROC),
ClaimQuarter, INSURER_Name, AMOUNT1..AMOUNT23. The catalogue gives no
per-field descriptions; AMOUNT_i is mapped positionally to the i-th of the 23
indicators listed in the dataset's `content` string (decisions 4.10).

Emits data/ib_firm_indicators.csv and out/stage3_ib_firm_YYYYMMDD.sql with
per-column checksums to verify server-side after the load.
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ins-info"
OUT_CSV = ROOT / "data" / "ib_firm_indicators.csv"
SRC_URL = "https://ins-info.ib.gov.tw/opendata/json-06161610.aspx"
CAT_URL = "https://data.gov.tw/dataset/7191"
Q_START = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}

# (column, 中文 as listed in the catalogue `content`), in AMOUNT order
INDICATORS = [
    ("liabilities_to_assets_pct", "負債占資產比率"),
    ("reserves_to_assets_pct", "各種責任準備金對資產比率"),
    ("reserves_change_pct", "各種責任準備金變動率"),
    ("reserves_net_increase_to_premium_pct", "各種責任準備金淨增額對保費收入比率"),
    ("affiliate_investment_to_equity_pct", "關係企業投資額對業主權益比率"),
    ("first_year_premium_ratio_pct", "初年度保費比率"),
    ("renewal_premium_ratio_pct", "續年度保費比率"),
    ("new_business_expense_ratio_pct", "新契約費用率"),
    ("premium_income_change_pct", "保費收入變動率"),
    ("equity_change_pct", "業主權益變動率"),
    ("net_income_change_pct", "淨利變動率"),
    ("funds_utilisation_ratio_pct", "資金運用比率"),
    ("persistency_13m_pct", "繼續率(十三個月)"),
    ("persistency_25m_pct", "繼續率(二十五個月)"),
    ("roa_pct", "資產報酬率"),
    ("roe_pct", "業主權益報酬率"),
    ("net_investment_yield_pct", "資金運用淨收益率"),
    ("investment_return_pct", "投資報酬率"),
    ("operating_margin_pct", "營業利益對營業收入比率"),
    ("pretax_margin_total_revenue_pct", "稅前純益對總收入比率"),
    ("net_margin_pct", "純益率"),
    ("eps_ntd", "每股盈餘"),
    ("real_estate_and_mortgage_to_assets_pct", "不動產投資與不動產抵押放款對資產比率"),
]
assert len(INDICATORS) == 23

# published name -> panel entity. Both Shin Kong names map to the one stable
# entity_id (README §4.5): the 115.1.1合併前 row is the old Shin Kong Life's
# last quarter (114Q4), the 原台新人壽 row the surviving entity from 2026.
ENTITY = {
    "國泰人壽保險股份有限公司": "cathay_life",
    "富邦人壽保險股份有限公司": "fubon_life",
    "南山人壽保險股份有限公司": "nanshan_life",
    "凱基人壽保險股份有限公司": "kgi_life",
    "台灣人壽保險股份有限公司": "taiwan_life",
    "新光人壽保險股份有限公司（115.1.1合併前）": "shinkong_life",
    "新光人壽保險股份有限公司（原台新人壽）": "shinkong_life",
}


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def val(s):
    s = (s or "").strip()
    if s in ("", "N/A"):
        return None
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        raise ValueError(f"unexpected value {s!r}")
    return float(s)


def load_file(path):
    m = re.search(r"_(\d{8})\.json$", path.name)
    if not m:
        raise SystemExit(f"{path.name}: filename needs a _YYYYMMDD snapshot stamp")
    vintage = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}"
    recs = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for r in recs:
        extra = set(r) - {"ClaimYear", "ClaimQuarter", "INSURER_Name"} - {f"AMOUNT{i}" for i in range(1, 24)}
        if extra:
            raise SystemExit(f"{path.name}: unexpected fields {sorted(extra)}")
        roc, q = int(r["ClaimYear"]), int(r["ClaimQuarter"])
        y = roc + 1911
        row = {
            "insurer_name": r["INSURER_Name"].strip(),
            "entity_id": ENTITY.get(r["INSURER_Name"].strip()),
            "obs_quarter": f"{y}-{Q_START[q]}",
            "roc_year": roc, "quarter": q, "vintage": vintage,
            "basis": "IFRS17" if y >= 2026 else "IFRS4",
            "raw_record": json.dumps(r, ensure_ascii=False, sort_keys=True),
            "file": path.name,
        }
        for i, (col, _) in enumerate(INDICATORS, 1):
            row[col] = val(r.get(f"AMOUNT{i}"))
        rows.append(row)
    return rows


def main():
    files = sorted(RAW.glob("json-06161610_*.json"))
    if not files:
        raise SystemExit("no couriered payloads under data/raw/ins-info/")
    rows = []
    for f in files:
        rows.extend(load_file(f))

    # natural-key collision guard (decisions 4.4): on conflict do nothing hides these
    keys = {}
    for r in rows:
        k = (r["insurer_name"], r["obs_quarter"], r["vintage"])
        if k in keys:
            raise SystemExit(f"natural-key collision {k} in {r['file']} and {keys[k]}")
        keys[k] = r["file"]

    cols = ["insurer_name", "entity_id", "obs_quarter", "roc_year", "quarter", "vintage",
            "basis"] + [c for c, _ in INDICATORS] + ["raw_record", "file"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r[c] is None else r[c]) for c in cols})

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    ind_cols = [c for c, _ in INDICATORS]
    vals = ",\n  ".join(
        "(" + ", ".join(
            [sqlv(r["insurer_name"]), sqlv(r["entity_id"]), sqlv(r["obs_quarter"]),
             str(r["roc_year"]), str(r["quarter"]), sqlv(r["vintage"]), sqlv(r["basis"])]
            + [sqlv(r[c]) for c in ind_cols]
            + [sqlv(r["raw_record"]), sqlv(r["file"])]) + ")"
        for r in rows)
    sql = f"""-- stage3-ib-firm: generated by scripts/stage3_ib_firm_indicators.py at {now}. Idempotent.
begin;
with vals(insurer_name, entity_id, obs_quarter, roc_year, quarter, vintage, basis,
          {', '.join(ind_cols)}, raw_record, file) as (values
  {vals})
insert into tlfx.firm_statutory_indicators
  (insurer_name, entity_id, obs_quarter, roc_year, quarter, vintage, basis,
   {', '.join(ind_cols)}, raw_record, source_url, source_doc, source_note, retrieved_at)
select insurer_name, entity_id, obs_quarter::date, roc_year, quarter, vintage::date,
  basis::tlfx.accounting_basis, {', '.join(ind_cols)}, raw_record::jsonb,
  '{SRC_URL}',
  '保險業公開資訊觀測站 表06161610 壽險財務業務指標 (data.gov.tw dataset 7191), couriered snapshot ' || file,
  'Latest reported quarter per insurer as of the snapshot; AMOUNT1..23 mapped positionally '
  'to the catalogue indicator list ({CAT_URL}); N/A and blank both NULL, verbatim in '
  'raw_record; vintage = snapshot date (decisions 4.10).',
  '{now}'::timestamptz
from vals
on conflict (insurer_name, obs_quarter, vintage) do nothing;
commit;
"""
    tag = dt.date.today().strftime("%Y%m%d")
    out = ROOT / "out" / f"stage3_ib_firm_{tag}.sql"
    out.write_text(sql, encoding="utf-8")

    print(f"rows: {len(rows)} from {len(files)} file(s); "
          f"panel-linked: {sum(1 for r in rows if r['entity_id'])}")
    print("checksums (sum, non-null count) per column:")
    for c in ind_cols:
        xs = [r[c] for r in rows if r[c] is not None]
        print(f"  {c}: {round(sum(xs), 2)} n={len(xs)}")
    print(f"csv: {OUT_CSV.relative_to(ROOT)}; sql: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
