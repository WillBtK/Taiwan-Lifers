#!/usr/bin/env python3
"""Stage 3 (statutory channel): load the Insurance Bureau's 財務報告彙總
(ins-info 表06021011, payload opendata/json-06021011.aspx) into
tlfx.firm_statutory_balance.

Couriered like 表06161610 (decisions 4.10): committed verbatim under
data/raw/ins-info/json-06021011_YYYYMMDD.json, the stamp is the vintage.

Fields: OccurSeason ("115年度第2季"), INSURER_Name, AMOUNT1..3 (assets,
liabilities, equity — pinned by the A = L + E identity on every record and by
exact ties to the six firms' own statements, decisions 4.11), ActualCapital
(paid-in capital), AMOUNT4..8 (unnamed, stored verbatim). NT$ thousand.

Emits data/ib_firm_balance.csv and out/stage3_ib_balance_YYYYMMDD.sql, then
prints checksums and the statement-channel ties for the load verification.
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ins-info"
OUT_CSV = ROOT / "data" / "ib_firm_balance.csv"
SRC_URL = "https://ins-info.ib.gov.tw/opendata/json-06021011.aspx"
Q_START = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}

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


def sector(name):
    # 亞洲保險 (Asia Insurance, HK) is a general insurer that never carried
    # 產物 in its registered name; the only such case in the payload
    if "產物保險" in name or "產險" in name or "漁船" in name or "亞洲保險" in name:
        return "nonlife"
    if "人壽" in name or "郵政" in name:
        return "life"
    raise ValueError(f"cannot classify {name}")


def load_file(path):
    m = re.search(r"_(\d{8})\.json$", path.name)
    if not m:
        raise SystemExit(f"{path.name}: filename needs a _YYYYMMDD snapshot stamp")
    vintage = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}"
    rows = []
    for r in json.loads(path.read_text(encoding="utf-8")):
        extra = set(r) - {"OccurSeason", "INSURER_Name", "ActualCapital"} - {f"AMOUNT{i}" for i in range(1, 9)}
        if extra:
            raise SystemExit(f"{path.name}: unexpected fields {sorted(extra)}")
        mm = re.fullmatch(r"(\d{3})年度第([1-4])季", r["OccurSeason"])
        if not mm:
            raise SystemExit(f"unparsed OccurSeason {r['OccurSeason']!r}")
        roc, q = int(mm.group(1)), int(mm.group(2))
        y = roc + 1911
        a, l, e = val(r["AMOUNT1"]), val(r["AMOUNT2"]), val(r["AMOUNT3"])
        if abs(a - l - e) > 0.01:
            raise SystemExit(f"A=L+E fails for {r['INSURER_Name']}: {a} {l} {e}")
        name = r["INSURER_Name"].strip()
        rows.append({
            "insurer_name": name, "entity_id": ENTITY.get(name), "sector": sector(name),
            "obs_quarter": f"{y}-{Q_START[q]}", "roc_year": roc, "quarter": q,
            "vintage": vintage, "basis": "IFRS17" if y >= 2026 else "IFRS4",
            "total_assets_ntd_k": a, "total_liabilities_ntd_k": l, "owners_equity_ntd_k": e,
            "paid_in_capital_ntd_k": val(r.get("ActualCapital")),
            **{f"amount{i}": val(r.get(f"AMOUNT{i}")) for i in range(4, 9)},
            "raw_record": json.dumps(r, ensure_ascii=False, sort_keys=True),
            "file": path.name,
        })
    return rows


def statement_ties(rows):
    """Exact ties to the statement channel CSVs (NT$ mn) for the panel firms."""
    stmt = {}
    for r in csv.DictReader(open(ROOT / "data" / "mops_statements.csv", encoding="utf-8")):
        stmt[(r["entity_id"], r["obs_quarter"])] = (float(r["assets_mn"]), float(r["equity_mn"]))
    for r in csv.DictReader(open(ROOT / "data" / "cathay_statements_quarterly.csv", encoding="utf-8")):
        if r.get("total_assets_mn"):
            stmt[("cathay_life", r["obs_quarter"])] = (float(r["total_assets_mn"]), float(r["owners_equity_mn"]))
    out = []
    for r in rows:
        if not r["entity_id"]:
            continue
        s = stmt.get((r["entity_id"], r["obs_quarter"]))
        if s is None:
            # no comparator (the pre-merger Shin Kong Life 2025Q4 was never
            # fetched from MOPS: its filing code is unverified, entities seed)
            out.append((r["entity_id"], r["obs_quarter"], "no statement row to tie to (skipped)", None))
            continue
        ok = abs(r["total_assets_ntd_k"] / 1000 - s[0]) <= 0.001 and abs(r["owners_equity_ntd_k"] / 1000 - s[1]) <= 0.001
        out.append((r["entity_id"], r["obs_quarter"],
                    f"assets {r['total_assets_ntd_k']/1000:,.3f} vs {s[0]:,.3f}; equity {r['owners_equity_ntd_k']/1000:,.3f} vs {s[1]:,.3f}", ok))
    return out


def main():
    files = sorted(RAW.glob("json-06021011_*.json"))
    if not files:
        raise SystemExit("no couriered payloads under data/raw/ins-info/")
    rows = []
    for f in files:
        rows.extend(load_file(f))
    keys = {}
    for r in rows:
        k = (r["insurer_name"], r["obs_quarter"], r["vintage"])
        if k in keys:
            raise SystemExit(f"natural-key collision {k} in {r['file']} and {keys[k]}")
        keys[k] = r["file"]

    num_cols = ["total_assets_ntd_k", "total_liabilities_ntd_k", "owners_equity_ntd_k",
                "paid_in_capital_ntd_k"] + [f"amount{i}" for i in range(4, 9)]
    cols = ["insurer_name", "entity_id", "sector", "obs_quarter", "roc_year", "quarter",
            "vintage", "basis"] + num_cols + ["raw_record", "file"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r[c] is None else r[c]) for c in cols})

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    vals = ",\n  ".join(
        "(" + ", ".join(
            [sqlv(r["insurer_name"]), sqlv(r["entity_id"]), sqlv(r["sector"]), sqlv(r["obs_quarter"]),
             str(r["roc_year"]), str(r["quarter"]), sqlv(r["vintage"]), sqlv(r["basis"])]
            + [sqlv(r[c]) for c in num_cols] + [sqlv(r["raw_record"]), sqlv(r["file"])]) + ")"
        for r in rows)
    sql = f"""-- stage3-ib-balance: generated by scripts/stage3_ib_firm_balance.py at {now}. Idempotent.
begin;
with vals(insurer_name, entity_id, sector, obs_quarter, roc_year, quarter, vintage, basis,
          {', '.join(num_cols)}, raw_record, file) as (values
  {vals})
insert into tlfx.firm_statutory_balance
  (insurer_name, entity_id, sector, obs_quarter, roc_year, quarter, vintage, basis,
   {', '.join(num_cols)}, raw_record, source_url, source_doc, source_note, retrieved_at)
select insurer_name, entity_id, sector, obs_quarter::date, roc_year, quarter, vintage::date,
  basis::tlfx.accounting_basis, {', '.join(num_cols)}, raw_record::jsonb,
  '{SRC_URL}',
  '保險業公開資訊觀測站 表06021011 財務報告彙總, couriered snapshot ' || file,
  'Latest reported quarter per insurer as of the snapshot; NT$ thousand as published; '
  'AMOUNT1..3 = assets/liabilities/equity pinned by A=L+E on every record and exact '
  'statement ties for the panel firms; AMOUNT4..8 unnamed, verbatim (decisions 4.11).',
  '{now}'::timestamptz
from vals
on conflict (insurer_name, obs_quarter, vintage) do nothing;
commit;
"""
    tag = dt.date.today().strftime("%Y%m%d")
    out = ROOT / "out" / f"stage3_ib_balance_{tag}.sql"
    out.write_text(sql, encoding="utf-8")

    ties = statement_ties(rows)
    nok = sum(1 for t in ties if t[3])
    ties_total = sum(1 for t in ties if t[3] is not None)
    print(f"rows: {len(rows)} from {len(files)} file(s); life {sum(1 for r in rows if r['sector']=='life')}, "
          f"nonlife {sum(1 for r in rows if r['sector']=='nonlife')}; panel-linked {sum(1 for r in rows if r['entity_id'])}")
    print(f"statement ties: {nok}/{ties_total} (comparators available)")
    for e, q, msg, ok in ties:
        print(f"  {'-- ' if ok is None else 'OK ' if ok else 'BAD'} {e} {q}: {msg}")
    print("checksums (sum, non-null count):")
    for c in num_cols:
        xs = [r[c] for r in rows if r[c] is not None]
        print(f"  {c}: {round(sum(xs), 2)} n={len(xs)}")
    print(f"csv: {OUT_CSV.relative_to(ROOT)}; sql: {out.relative_to(ROOT)}")
    return 0 if nok == ties_total else 1


if __name__ == "__main__":
    sys.exit(main())
