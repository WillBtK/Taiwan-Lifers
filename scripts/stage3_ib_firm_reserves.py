#!/usr/bin/env python3
"""Parse the Insurance Bureau's per-company reserve pages.

Two sources, two shapes:

  Info2-5   準備金（包括保險負債、具金融商品性質之保險契約準備及外匯價格變動準備）
  Info2-14  其他負債項下之服務合約負債、特別準備及其他準備

Info2-5 renders in two layouts and which one you get depends on the company's
latest reporting period, not on anything requestable:

  * PRE-2026 (IFRS 4) — ten LABELLED rows across three year columns, including
    外匯價格變動準備 as its own line. This is a firm-level FX-reserve history,
    and it is the only place in the project one exists.
  * 2026 (IFRS 17) — seven rows for one quarter whose 項目 cells are literally
    `&nbsp;` in the source. The page title says the FX reserve is among them,
    but nothing identifies which row, and no row equals any firm's balance
    known from its own filings, so the reserve is bundled rather than merely
    unlabelled. These load POSITIONALLY as item_1..item_6 plus a total, on the
    same principle as the unnamed AMOUNT fields in decisions 4.11: store what
    is published, name only what is pinned, keep the raw row so a later legend
    can rename without refetching.

Guessing names by position across the layout change would be the tempting
move and is exactly wrong: the IFRS 17 statement has a different reserve
decomposition, so position 3 in one is not position 3 in the other.

Every table states a total, checked against the sum of its components.
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ins-info-firm"
OUT_CSV = ROOT / "data" / "ib_firm_reserves.csv"
UIDS = ROOT / "config" / "firm_uids.tsv"

# Labels used by the pre-2026 Info2-5 layout, and by Info2-14.
LABELS = {
    "未滿期保費準備": "unearned_premium",
    "賠款準備": "claims_reserve",
    "責任準備": "policy_reserve",
    "特別準備": "special_reserve_liability",
    "保費不足準備": "premium_deficiency",
    "負債適足準備": "liability_adequacy",
    "其他準備": "other_reserve",
    "具金融商品性質之保險契約準備": "financial_instrument_contract_reserve",
    "外匯價格變動準備": "fx_volatility_reserve",
    "其他負債-服務合約負債": "service_contract_liability",
    "其他負債-特別準備": "special_reserve_liability",
    "其他負債-其他準備": "other_reserve",
}
TOTAL_LABELS = ("各種準備金合計", "合計", "總計")


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def num(s):
    # the portal writes empty cells as the literal entity "&nbsp;", not as the
    # character, so unescaping has to happen before the blank test
    s = (s or "").replace("&nbsp;", "").replace("\xa0", "").replace(",", "").strip()
    if s in ("", "-", "N/A"):
        return None
    return float(s)


def uid_map():
    out = {}
    for line in UIDS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("entity_id\t"):
            continue
        p = (line.split("\t") + ["", "", ""])[:4]
        key = p[0].strip()
        entity = "shinkong_life" if key.startswith("shinkong_life") else key
        out[key] = (entity, p[1].strip())
    return out


def cells(tr):
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]


def periods_from_header(header):
    """Value-column headers -> (obs_date, period_kind), one entry per column.

    Positional, and it must stay positional. The pre-2026 layout prints FOUR
    value columns: a current-year quarter column that is empty, then three
    completed years. Compacting the blank cell away before aligning values to
    columns shifts every figure one year later -- which is silent, survives
    every sum check (the columns still balance among themselves), and was the
    first version of this function. So unreadable columns are kept as None
    placeholders and dropped only after alignment.
    """
    out = []
    for h in header[2:]:
        q = re.search(r"(\d{2,3})年度第(\d)季", h)
        if q:
            y, qq = int(q.group(1)) + 1911, int(q.group(2))
            end = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[qq]
            out.append((f"{y}-{end}", "quarter"))
            continue
        ym = re.search(r"(\d{2,3})年度", h)
        if ym and "第季" not in h:
            out.append((f"{int(ym.group(1)) + 1911}-12-31", "year_end"))
            continue
        # e.g. "115年度第季金額": the current year's quarter is not yet filed,
        # the header is malformed and the cells are blank. It still occupies a
        # column, so it must occupy a slot.
        out.append((None, None))
    return out


def parse_file(path, uids):
    m = re.fullmatch(r"(Info2-\d+)_(.+)_(\d{8})\.html", path.name)
    page, key, stamp = m.group(1), m.group(2), m.group(3)
    entity, uid = uids[key]
    vintage = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
    text = re.sub(r"<script.*?</script>", "",
                  path.read_text(encoding="utf-8", errors="replace"), flags=re.S | re.I)

    md = re.search(r"資料日期：中華民國(\d{2,3})年(\d{1,2})月", text)
    rocy, rocm = (int(md.group(1)), int(md.group(2))) if md else (None, None)

    header, body = None, []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        c = cells(tr)
        if not c or not any(c):
            continue
        if header is None:
            header = c
        else:
            body.append(c)
    if header is None or not body:
        return [], [(f"{page} {entity}: no data (portal says 目前尚無資料)", None)]

    periods = periods_from_header(header)
    if not any(p for p, _ in periods):
        return [], [(f"{page} {entity}: unreadable period header {header}", False)]

    # a row is 列號, 項目, then one value per period (some layouts insert a
    # blank spacer cell between the label and the values)
    rows, checks = [], []
    per_period = {p: {"items": {}, "unnamed": {}, "total": None}
                  for p, _ in periods if p is not None}
    for c in body:
        if not c or not c[0].strip().isdigit():
            continue
        rn = int(c[0].strip())
        label = c[1].strip() if len(c) > 1 else ""
        vals = [num(x) for x in c[2:]]          # positional, blanks kept as None
        for i, (obs, _kind) in enumerate(periods):
            if obs is None:
                continue
            v = vals[i] if i < len(vals) else None
            slot = per_period[obs]
            if label in TOTAL_LABELS:
                slot["total"] = v
            elif label in LABELS:
                slot["items"][LABELS[label]] = v
            elif label:
                slot["unnamed"][f"row_{rn}:{label}"] = v
            else:
                slot["unnamed"][f"item_{rn}"] = v

    for obs, kind in periods:
        if obs is None:
            continue
        slot = per_period[obs]
        named = {k: v for k, v in slot["items"].items() if v is not None}
        unnamed = {k: v for k, v in slot["unnamed"].items() if v is not None}
        total = slot["total"]
        # the last unnamed row of the 2026 layout is its total, stated but
        # not labelled; identify it only by the identity, never by position
        if total is None and unnamed:
            last = max(unnamed, key=lambda k: int(re.search(r"(\d+)", k).group(1)))
            rest = sum(v for k, v in unnamed.items() if k != last)
            if abs(rest - unnamed[last]) <= 1.0:
                total = unnamed.pop(last)
        parts = sum(named.values()) + sum(unnamed.values())
        ok = total is not None and abs(parts - total) <= 1.0
        checks.append((f"{page} {entity} {obs} components sum to total", ok))
        rows.append({
            "entity_id": entity, "uid": uid, "page": page, "obs_date": obs,
            "period_kind": kind, "vintage": vintage,
            "layout": "labelled" if named else "unlabelled",
            "fx_volatility_reserve": named.get("fx_volatility_reserve"),
            "special_reserve_liability": named.get("special_reserve_liability"),
            "other_reserve": named.get("other_reserve"),
            "policy_reserve": named.get("policy_reserve"),
            "items": {k: round(v / 1000, 3) for k, v in named.items()},
            "unnamed_items": {k: round(v / 1000, 3) for k, v in unnamed.items()},
            "total": None if total is None else round(total / 1000, 3),
        })
    return rows, checks


def main():
    uids = uid_map()
    files = sorted(f for pat in ("Info2-5_*.html", "Info2-14_*.html")
                   for f in RAW.glob(pat))
    if not files:
        raise SystemExit("no reserve pages under data/raw/ins-info-firm/")
    rows, checks = [], []
    for f in files:
        r, c = parse_file(f, uids)
        rows += r
        checks += c

    for r in rows:
        for k in ("fx_volatility_reserve", "special_reserve_liability",
                  "other_reserve", "policy_reserve"):
            if r[k] is not None:
                r[k] = round(r[k] / 1000, 3)

    keys = [(r["entity_id"], r["uid"], r["page"], r["obs_date"], r["vintage"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise SystemExit("natural-key collision")

    cols = ["entity_id", "uid", "page", "obs_date", "period_kind", "vintage", "layout",
            "fx_volatility_reserve", "special_reserve_liability", "other_reserve",
            "policy_reserve", "total", "items", "unnamed_items"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            out = dict(r)
            out["items"] = json.dumps(r["items"], ensure_ascii=False)
            out["unnamed_items"] = json.dumps(r["unnamed_items"], ensure_ascii=False)
            w.writerow({c: ("" if out[c] is None else out[c]) for c in cols})

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    sql_cols = cols
    vals = ",\n  ".join(
        "(" + ", ".join(
            sqlv(json.dumps(r[c], ensure_ascii=False) if c in ("items", "unnamed_items") else r[c])
            for c in sql_cols) + ")" for r in rows)
    sql = f"""-- stage3-ib-reserves: generated by scripts/stage3_ib_firm_reserves.py at {now}. Idempotent.
begin;
with vals({', '.join(sql_cols)}) as (values
  {vals})
insert into tlfx.firm_reserves
  ({', '.join(sql_cols)}, source_url, source_doc, source_note, retrieved_at)
select entity_id, uid, page, obs_date::date, period_kind, vintage::date, layout,
  fx_volatility_reserve, special_reserve_liability, other_reserve, policy_reserve,
  total, items::jsonb, unnamed_items::jsonb,
  'https://ins-info.ib.gov.tw/customer/' || page || '.aspx?UID=' || uid,
  '保險業公開資訊觀測站 單一查詢 ' || page,
  'NT$ mn from NT$-thousand as published; components sum to the stated total. '
  'layout=unlabelled means the source prints no item names (2026 Info2-5), so '
  'those figures are positional in unnamed_items and MUST NOT be named by '
  'position across the IFRS-17 layout change (decisions 4.28).',
  '{now}'::timestamptz
from vals
on conflict (entity_id, uid, page, obs_date, vintage) do nothing;
commit;
"""
    tag = dt.date.today().strftime("%Y%m%d")
    out = ROOT / "out" / f"stage3_ib_reserves_{tag}.sql"
    out.write_text(sql, encoding="utf-8")

    real = [c for c in checks if c[1] is not None]
    nok = sum(1 for _, o in real if o)
    print(f"rows: {len(rows)} from {len(files)} files; checks {nok}/{len(real)}")
    for label, o in checks:
        if o is None:
            print("  SKIP", label)
        elif not o:
            print("  FAIL", label)
    fx = [r for r in rows if r["fx_volatility_reserve"] is not None]
    if fx:
        print("\nfirm-level FX volatility reserve, NT$ mn (labelled layout only):")
        for r in sorted(fx, key=lambda x: (x["entity_id"], x["obs_date"])):
            print(f"  {r['entity_id']:<14} {r['obs_date']}  {r['fx_volatility_reserve']:>12,.0f}")
    print(f"\ncsv: {OUT_CSV.relative_to(ROOT)}; sql: {out.relative_to(ROOT)}")
    return 0 if nok == len(real) else 1


if __name__ == "__main__":
    sys.exit(main())
