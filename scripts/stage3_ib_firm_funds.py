#!/usr/bin/env python3
"""Parse the Insurance Bureau's per-company 資金運用表 into firm fund utilisation.

Source: data/raw/ins-info-firm/Info2-1_<entity>_YYYYMMDD.html, fetched weekly
through the Taiwan relay (decisions 4.26). Each page is one insurer's fund
utilisation at four periods: the latest month of the current ROC year, then
the three preceding year-ends.

Why this matters more than its size suggests. 國外投資 by firm is the
hedge-ratio denominator at firm level. The project has had it for the sector
(表17-1) since Stage 2 and for three firms from investor decks, but never as a
published figure for all six, and never monthly. The page is also fresher than
anything else here: it carries the latest month, where the statutory filings
stop at the quarter.

Units are NT$ thousand as published and are stored in NT$ mn per the project
convention. The nine components must sum to the printed total; that identity
is asserted per firm per period rather than assumed, because a mis-parsed row
would otherwise pass silently into a denominator.
"""
import csv
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ins-info-firm"
OUT_CSV = ROOT / "data" / "ib_firm_funds.csv"
UIDS = ROOT / "config" / "firm_uids.tsv"

# 列號 -> column. Row 10 is the printed total, checked against rows 1-9.
ITEMS = {
    1: "bank_deposits", 2: "securities", 3: "real_estate", 4: "loans",
    5: "project_public_investment", 6: "foreign_investment",
    7: "insurance_related", 8: "derivatives", 9: "other",
}
TOTAL_ROW = 10
COLS = list(ITEMS.values())


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def num(s):
    s = (s or "").replace(",", "").strip()
    if s in ("", "-", "N/A"):
        return None
    return float(s)


def uid_map():
    """entity as filed -> (entity_id for the panel, uid, note)."""
    out = {}
    for line in UIDS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("entity_id\t"):
            continue
        p = (line.split("\t") + ["", "", ""])[:4]
        key = p[0].strip()
        # the pre-merger Shin Kong company is the same panel series (README 4.5)
        entity = "shinkong_life" if key.startswith("shinkong_life") else key
        out[key] = (entity, p[1].strip(), p[3].strip())
    return out


def cells(tr):
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]


def parse_file(path, uids):
    m = re.fullmatch(r"Info2-1_(.+)_(\d{8})\.html", path.name)
    if not m:
        raise SystemExit(f"{path.name}: unexpected name")
    key, stamp = m.group(1), m.group(2)
    if key not in uids:
        raise SystemExit(f"{path.name}: {key} not in {UIDS.name}")
    entity, uid, note = uids[key]
    vintage = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)

    rocy = rocm = None
    md = re.search(r"資料日期：中華民國(\d{2,3})年(\d{1,2})月", text)
    if md:
        rocy, rocm = int(md.group(1)), int(md.group(2))
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I)
    header = None
    data = {}
    for tr in trs:
        c = cells(tr)
        if not c:
            continue
        if header is None and any("年度" in x for x in c) and "項目" in " ".join(c):
            header = c
            continue
        if header and c[0].isdigit():
            data[int(c[0])] = c
    if header is None or not data:
        raise SystemExit(f"{path.name}: no table found")

    # period columns: "115年度最新一期金額" then "114年度金額" and so on
    periods = []
    for h in header:
        hm = re.search(r"(\d{2,3})年度(最新一期)?", h)
        if hm:
            y = int(hm.group(1)) + 1911
            latest = bool(hm.group(2))
            if latest and rocm:
                # the latest column is a MONTH, not a year end; using the year
                # end would silently date an August figure to December
                end = dt.date(y, rocm, 1)
                nxt = dt.date(y + (rocm == 12), (rocm % 12) + 1, 1)
                periods.append(((nxt - dt.timedelta(days=1)).isoformat(), "latest_month"))
            else:
                periods.append((f"{y}-12-31", "year_end"))
    if len(periods) < 2:
        raise SystemExit(f"{path.name}: could not read period columns from {header}")

    rows, checks = [], []
    for idx, (obs, kind) in enumerate(periods):
        vals = {}
        for rn, col in ITEMS.items():
            c = data.get(rn)
            vals[col] = num(c[idx + 2]) if c and len(c) > idx + 2 else None
        tot_cells = data.get(TOTAL_ROW)
        total = num(tot_cells[idx + 2]) if tot_cells and len(tot_cells) > idx + 2 else None
        parts = sum(v for v in vals.values() if v is not None)
        ok = total is not None and abs(parts - total) <= 1.0   # NT$ thousand
        checks.append((f"{entity} {obs} components sum to total", ok))
        rows.append({
            "entity_id": entity, "uid": uid, "obs_date": obs, "period_kind": kind,
            "vintage": vintage, "file": path.name, "note": note,
            **{c: (None if vals[c] is None else round(vals[c] / 1000, 3)) for c in COLS},
            "total": None if total is None else round(total / 1000, 3),
        })
    return rows, checks


def main():
    uids = uid_map()
    files = sorted(RAW.glob("Info2-1_*.html"))
    if not files:
        raise SystemExit("no Info2-1 pages under data/raw/ins-info-firm/")
    rows, checks = [], []
    for f in files:
        r, c = parse_file(f, uids)
        rows += r
        checks += c

    keys = [(r["entity_id"], r["uid"], r["obs_date"], r["vintage"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise SystemExit("natural-key collision")

    cols = ["entity_id", "uid", "obs_date", "period_kind", "vintage"] + COLS + ["total", "file", "note"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r[c] is None else r[c]) for c in cols})

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    sql_cols = ["entity_id", "uid", "obs_date", "period_kind", "vintage"] + COLS + ["total"]
    vals = ",\n  ".join("(" + ", ".join(sqlv(r[c]) for c in sql_cols) + ")" for r in rows)
    sql = f"""-- stage3-ib-funds: generated by scripts/stage3_ib_firm_funds.py at {now}. Idempotent.
begin;
with vals({', '.join(sql_cols)}) as (values
  {vals})
insert into tlfx.firm_fund_utilisation
  ({', '.join(sql_cols)}, source_url, source_doc, source_note, retrieved_at)
select entity_id, uid, obs_date::date, period_kind, vintage::date,
  {', '.join(COLS)}, total,
  'https://ins-info.ib.gov.tw/customer/Info2-1.aspx?UID=' || uid,
  '保險業公開資訊觀測站 單一查詢 資金運用表 (Info2-1)',
  'NT$ mn from NT$-thousand as published; components sum to the printed total '
  '(asserted per firm per period). The latest-period column is a MONTH, dated '
  'to that month end, not a year end (decisions 4.27).',
  '{now}'::timestamptz
from vals
on conflict (entity_id, uid, obs_date, vintage) do nothing;
commit;
"""
    tag = dt.date.today().strftime("%Y%m%d")
    out = ROOT / "out" / f"stage3_ib_funds_{tag}.sql"
    out.write_text(sql, encoding="utf-8")

    nok = sum(1 for _, o in checks if o)
    print(f"rows: {len(rows)} from {len(files)} files; checks {nok}/{len(checks)}")
    for label, o in checks:
        if not o:
            print("  FAIL", label)
    print("\nforeign investment, NT$ mn:")
    by = {}
    for r in rows:
        by.setdefault(r["obs_date"], []).append((r["entity_id"], r["foreign_investment"]))
    for obs in sorted(by, reverse=True):
        ents = [e for e, _ in by[obs]]
        tot = sum(v for _, v in by[obs] if v)
        # Shin Kong reports under two registration numbers, so a plain sum at a
        # shared year-end double-counts it; say so rather than printing a
        # number that looks like a panel total and is not one
        dup = len(ents) != len(set(ents))
        flag = "  <- DOUBLE-COUNTS shinkong (two uids); not a panel total" if dup else ""
        print(f"  {obs}  n={len(by[obs])}  sum {tot:>14,.0f}{flag}")
    print(f"\nchecksums: sum foreign_investment {round(sum(r['foreign_investment'] or 0 for r in rows), 3)}; "
          f"sum total {round(sum(r['total'] or 0 for r in rows), 3)}")
    print(f"csv: {OUT_CSV.relative_to(ROOT)}; sql: {out.relative_to(ROOT)}")
    return 0 if nok == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
