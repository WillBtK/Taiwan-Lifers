#!/usr/bin/env python3
"""Parse the CBC's FX-market series, and build the hedging cost back to 1991.

Why this is on the critical path rather than beside it. The reconstruction in
decisions 4.29 shows the sector hedge ratio falling roughly 20pp over six
years. The first candidate for why is price: a lifer hedges when the carry is
bearable and stops when it is not. The project has a hedging-cost series only
from investor decks, three firms, 2013 onwards — too short to say whether the
current cost is unusual, and firm-reported rather than market-observable. The
CBC publishes USD/TWD forwards by tenor from **1991-11** and spot from
**1992-01**, from which the market-implied cost of hedging follows directly,
monthly, for thirty-four years.

THE CONSTRUCTION
----------------
A lifer holding USD assets hedges by SELLING USD forward. It therefore
transacts at the price at which a bank BUYS USD — 買入匯率, the bid — and its
cost is the shortfall of that forward price against what it could sell spot
for today, annualised:

    cost_ann  =  (S_bid − F_bid) / S_bid × 360 / days

Both legs are bank-buys-USD prices (spot 銀行與顧客間交易匯率-買進 against the
forward bid), so the dealer's spread cancels and what is left is the carry.
Pairing a bid forward with a mid or interbank spot would fold half a spread
into the cost and overstate it by roughly 10bp at current levels — small, but
it would be the wrong sign of error to have in a cost series whose whole point
is comparison across decades.

The mid-to-mid version is computed alongside as the market's own quote, since
that is what a rate screen shows and what published comparisons use.

WHAT THE SIGN MEANS
-------------------
Positive = hedging costs money, because USD trades at a forward discount to
TWD, because USD rates exceed TWD rates. Negative = hedging pays, which was
the world before about 1998 and is the fact that makes the long history worth
having: the current regime is not the only one that has existed.

TURNOVER AND THE BANKS' NET POSITION
------------------------------------
EG47M01 gives daily-average turnover split customer/interbank and by
instrument (spot, forward, swap, margin, option, CCS) from 1994, plus the
whole banking system's end-period net FX position. The last of these is the
counterparty question in one number: if banks warehoused the lifers' hedges,
their net position would carry it. It is roughly USD 0.5bn against a lifer
foreign book near USD 700bn, which is the Setser and S.T.W. (2019) point
arithmetically — the banks intermediate, they do not absorb.
"""
import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "cbc_db"
OUT_CSV = ROOT / "data" / "cbc_fx_market.csv"
COST_CSV = ROOT / "data" / "fx_hedge_cost_market.csv"
API = "https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName="

SERIES = ["EG51M01", "EG55M01", "EG47M01"]

# Days per tenor label, for annualising. The CBC labels tenors in days
# already, so this is a parse rather than a convention.
TENOR_DAYS = {"10天": 10, "30天": 30, "60天": 60, "90天": 90,
              "120天": 120, "150天": 150, "180天": 180}


def num(s):
    if s in ("-", "", None):
        return None
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def month(p):
    """CBC period code, e.g. 1991M11. Quarterly and annual codes are skipped."""
    if "M" not in p:
        return None
    y, m = p.split("M")
    return f"{int(y)}-{int(m):02d}-01"


def load(code):
    d = json.loads((CACHE / f"{code}.json").read_text(encoding="utf-8"))
    meta, s = d["meta"], d["data"]["structure"]
    t1 = [x["data"] for x in s["Table1"]]
    t2 = [x["data"] for x in s.get("Table2", [])] or [""]
    # The row is period followed by the cross product of Table1 x Table2, with
    # Table2 varying fastest. Asserting the width rather than trusting it: a
    # silently changed dimension would misalign every column and still parse.
    rows = d["data"]["dataSets"]
    want = 1 + len(t1) * len(t2)
    if len(rows[0]) != want:
        raise SystemExit(f"{code}: row width {len(rows[0])}, expected {want} "
                         f"({len(t1)} items x {len(t2)} sub-items)")
    out = []
    for r in rows:
        m = month(r[0])
        if not m:
            continue
        for i, item in enumerate(t1):
            for j, sub in enumerate(t2):
                v = num(r[1 + i * len(t2) + j])
                if v is not None:
                    out.append({"matrix_code": code, "item": item,
                                "sub_item": sub, "obs_month": m, "value": v})
    return out, meta, t1, t2


def unit_for(code, item, sub):
    """Units are per-row here because the sources mix them within one series."""
    if code == "EG51M01":
        return "pct_pa" if "利率" in item else "TWD per USD"
    if code == "EG55M01":
        return "TWD per USD"
    if code == "EG47M01":
        return "pct_yoy" if sub == "年增率" else "USD mn"
    raise SystemExit(f"no unit rule for {code}")


def months_between(a, b):
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def emit_sql(all_rows, now, per_file=None):
    """Emit the load as one array per series, not one VALUES row per observation.

    The first version wrote 18,405 `VALUES` rows, about 1.9MB, and could not be
    applied: the SQL has to travel as a tool-call argument, so the binding
    constraint is the size of the text, not anything Postgres would object to.
    Chunking row-wise does not fix that — it multiplies the calls without
    reducing the bytes, and 18,405 rows of repeated Chinese labels and dates is
    mostly repetition.

    So each (item, sub_item) travels once, carrying a dense monthly array of
    its values with NULL where the source has none, and Postgres expands it
    with `unnest … with ordinality`. The month is reconstructed by offset from
    the series' first month, which is why the array must stay dense: a gap
    silently shifts every later observation, the same failure class as the
    reserve parser's column compaction (4.28). The `where v is not null` then
    drops the gaps after the dates are fixed, never before.

    That takes the payload from 18,405 labelled rows to 34 arrays.

    HOW MANY ARRAYS PER FILE. Measured, not guessed: a 400KB part could not be
    emitted at all, and a 43KB part was applied once but failed to be emitted
    reliably on a second attempt. Files land dependably at around 12KB, so the
    default is set from a byte budget rather than an array count — the series
    differ in length by a factor of three, so a fixed count gives files that
    vary as much. Override with SERIES_PER_FILE when a different execution path
    can take more.
    """
    if per_file is None:
        per_file = int(os.environ.get("SERIES_PER_FILE", "0")) or None
    keep = [r for r in all_rows if r["sub_item"] != "年增率"]
    groups = {}
    for r in keep:
        groups.setdefault((r["matrix_code"], r["item"], r["sub_item"],
                           r["unit"], r["vintage"]), {})[r["obs_month"]] = r["value"]

    out, files = [], []
    for (code, item, sub, unit, vintage), vals in sorted(groups.items()):
        lo, hi = min(vals), max(vals)
        dense = []
        for i in range(months_between(lo, hi) + 1):
            y, m = divmod((int(lo[:4]) * 12 + int(lo[5:7]) - 1) + i, 12)
            v = vals.get(f"{y}-{m + 1:02d}-01")
            dense.append("NULL" if v is None else repr(v))
        out.append((code, item, sub, lo, unit, vintage, dense))

    # Pack by size, not by count. A part closes once it would exceed the
    # budget, so a single very long series still gets its own file rather than
    # dragging three others past the limit with it.
    BUDGET = 12_000
    parts, cur, cur_len = [], [], 0
    for row in out:
        size = sum(len(x) + 1 for x in row[6]) + 120
        if cur and (cur_len + size > BUDGET or (per_file and len(cur) >= per_file)):
            parts.append(cur)
            cur, cur_len = [], 0
        cur.append(row)
        cur_len += size
    if cur:
        parts.append(cur)

    for n, part in enumerate(parts, start=1):
        rows_sql = ",\n  ".join(
            f"({sqlv(c)}, {sqlv(it)}, {sqlv(sb)}, {sqlv(lo)}, {sqlv(u)}, "
            f"{sqlv(v)}, '{{{','.join(d)}}}'::numeric[])"
            for c, it, sb, lo, u, v, d in part)
        sql = f"""-- stage5-cbc-fx part {n}: generated by scripts/stage5_cbc_fx_market.py at {now}.
-- Idempotent; parts may be applied in any order and re-applied safely.
-- Each row carries one series as a DENSE monthly array from first_month, NULL
-- where the source publishes nothing. The month comes from the array position,
-- so the density is load-bearing: a compacted array would date every later
-- value wrongly and still load cleanly.
begin;
with s(matrix_code, item, sub_item, first_month, unit, vintage, vals) as (values
  {rows_sql})
insert into tlfx.fx_market_monthly
  (matrix_code, item, sub_item, obs_month, value, unit, vintage,
   source_url, source_doc, source_note, retrieved_at)
select s.matrix_code, s.item, s.sub_item,
       (s.first_month::date + ((t.ord - 1) || ' month')::interval)::date,
       t.v, s.unit, s.vintage::date,
       '{API}' || s.matrix_code,
       'CBC statistics database (中央銀行統計資料庫), SDMX-JSON',
       'item and sub_item are the source''s own Table1/Table2 labels, '
       'unmodified. Row width is asserted against items x sub-items on parse, '
       'so a changed dimension fails the run rather than silently misaligning '
       'columns. The published 年增率 (year-on-year) sub-item is NOT stored: '
       'it is an exact transform of the level series in this same table, and '
       'the project''s convention is raw as published on ingest with '
       'conversions in derived_series.',
       '{now}'::timestamptz
from s, unnest(s.vals) with ordinality as t(v, ord)
where t.v is not null
on conflict (matrix_code, item, sub_item, obs_month, vintage) do nothing;
commit;
"""
        p = ROOT / "out" / f"stage5_cbc_fx_{dt.date.today():%Y%m%d}_p{n}.sql"
        p.parent.mkdir(exist_ok=True)
        p.write_text(sql, encoding="utf-8")
        files.append(p)
    return files


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def hedging_cost(rows):
    """Annualised forward cost per tenor, with defective source cells excluded.

    THE EXCLUSION TEST. Two cells in thirty-five years are wrong at source: a
    transposed digit in the 1994-05 120-day ask (27.270 printed as 26.270) and
    an out-of-ladder 2026-01 180-day bid. Both are caught by one test that
    cannot produce a false positive — a bid above its own ask is not a steep
    curve or an unusual month, it is arithmetically impossible in a real quote.
    Where it fires, BOTH sides of that tenor-month are dropped from the derived
    cost rather than adjudicating which half is corrupt: with two cells in
    2,581 there is nothing to gain from guessing.

    THE TEST I TRIED FIRST, AND WHY IT IS A DIAGNOSTIC AND NOT A FILTER. All
    seven tenors price off one interest differential, so the annualised cost
    ought to be near-identical across the ladder, and a tenor that disagrees
    with the month's median looks like a bad cell. Applied as a filter it threw
    out 312 cells. Two reasons, and the second is worth more than the test was:
    annualising a 10-day forward multiplies a 0.001 rounding by 36, so the
    tolerance has to live in price space; and once it does, the largest
    surviving deviations are not defects at all but **2025-06**, where five of
    seven tenors depart from a straight line. That is the month after the TWD
    shock, and it is the curve genuinely going non-linear — the flat-differential
    assumption fails exactly in the stressed months that matter most. Kept as a
    reported diagnostic, because a month where the term structure breaks is a
    finding about the hedging market, not dirt to be swept out of the data.

    The raw values load unchanged either way — the project publishes what is
    published (4.11). It is only the DERIVED cost that drops cells, because a
    transposed digit annualised over 120 days is not a small error.
    """
    by = {}
    for r in rows:
        by.setdefault(r["obs_month"], {})[(r["matrix_code"], r["item"], r["sub_item"])] = r["value"]

    SPOT_BID = ("EG51M01", "美元即期匯率-銀行與顧客間交易匯率-買進", "")
    SPOT_ASK = ("EG51M01", "美元即期匯率-銀行與顧客間交易匯率-賣出", "")

    out = []
    inverted, n_cells, devs = [], 0, []
    for m in sorted(by):
        d = by[m]
        s_bid, s_ask = d.get(SPOT_BID), d.get(SPOT_ASK)
        if s_bid is None:
            continue
        row = {"obs_month": m, "spot_bid": s_bid, "spot_ask": s_ask}
        raw = {}
        for tenor, days in TENOR_DAYS.items():
            f_bid = d.get(("EG55M01", tenor, "買入匯率"))
            f_ask = d.get(("EG55M01", tenor, "賣出匯率"))
            if f_bid is None or f_ask is None:
                continue
            n_cells += 1
            if f_bid > f_ask:
                inverted.append((m, tenor, f_bid, f_ask))
                continue                      # both sides of this cell dropped
            raw[days] = (f_bid, f_ask)
        if not raw:
            continue
        bid_cost = {d_: (s_bid - b) / s_bid * 360 / d_ * 100
                    for d_, (b, _a) in raw.items()}
        med = median(list(bid_cost.values())) if len(raw) >= 3 else None
        for days, (f_bid, f_ask) in sorted(raw.items()):
            row[f"fwd_bid_{days}"] = f_bid
            row[f"cost_ann_pct_{days}"] = round(bid_cost[days], 4)
            row[f"cost_mid_ann_pct_{days}"] = (
                round(((s_bid + s_ask) / 2 - (f_bid + f_ask) / 2)
                      / ((s_bid + s_ask) / 2) * 360 / days * 100, 4)
                if s_ask else None)
            if med is not None:
                # how far this quote sits from a flat-differential curve, in
                # TWD. Reported, never used to reject: see the docstring.
                devs.append((abs(f_bid - s_bid * (1 - med / 100 * days / 360)),
                             m, days))
        row["term_structure_dev_twd"] = (
            round(max(x[0] for x in devs[-len(raw):]), 4) if med is not None else None)
        out.append(row)
    return out, {"cells": n_cells, "inverted": inverted, "devs": devs}


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return repr(v) if isinstance(v, float) else str(v)


def main():
    all_rows, metas = [], {}
    for code in SERIES:
        rows, meta, t1, t2 = load(code)
        for r in rows:
            r["unit"] = unit_for(code, r["item"], r["sub_item"])
            r["vintage"] = meta["last_updated"]
        all_rows += rows
        metas[code] = meta
        ms = sorted({r["obs_month"] for r in rows})
        print(f"{code}  {meta['title'][:44]:<46} {len(rows):>6,} obs  "
              f"{ms[0]} → {ms[-1]}  vintage {meta['last_updated']}")

    keys = [(r["matrix_code"], r["item"], r["sub_item"], r["obs_month"], r["vintage"])
            for r in all_rows]
    if len(keys) != len(set(keys)):
        raise SystemExit("natural-key collision")

    cost, rep = hedging_cost(all_rows)
    print(f"\nforward cells examined: {rep['cells']:,} over 35 years")
    print(f"  bid above its own ask (dropped from the derived cost, both "
          f"sides): {len(rep['inverted'])}")
    for m, tenor, b, a in rep["inverted"]:
        print(f"    {m} {tenor}  bid {b} > ask {a}")
    # A handful of bad cells in a 35-year published series is expected. A
    # systematic problem would show as a rate, not a list, so the run fails on
    # the rate rather than on any single cell.
    bad_rate = len(rep["inverted"]) / max(rep["cells"], 1)
    ok = bad_rate < 0.005
    print(f"  defect rate {bad_rate*100:.3f}%  "
          f"{'(within tolerance)' if ok else 'FAIL — too high to be source noise'}")

    devs = sorted(rep["devs"], reverse=True)
    q = [devs[int(len(devs) * (1 - p))][0] for p in (0.5, 0.9, 0.99)]
    print(f"\n  term-structure diagnostic — distance of each forward from a "
          f"flat-differential\n  curve, TWD: median {q[0]:.4f}, p90 {q[1]:.4f}, "
          f"p99 {q[2]:.4f}. Largest, excluding the\n  defective cells above:")
    seen = set()
    for dv, m, days in devs[:8]:
        print(f"    {m} {days:>3}d  {dv:.3f} TWD")
        seen.add(m)
    if "2025-06-01" in seen:
        print("    ^ 2025-06 appears at several tenors at once: the month "
              "after the TWD shock is\n      the curve genuinely leaving a "
              "straight line, not a data defect.")

    cols = ["matrix_code", "item", "sub_item", "obs_month", "value", "unit", "vintage"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows({c: r[c] for c in cols} for r in all_rows)

    ccols = (["obs_month", "spot_bid", "spot_ask"] + [
        f"{p}{d}" for d in TENOR_DAYS.values()
        for p in ("fwd_bid_", "cost_ann_pct_", "cost_mid_ann_pct_")]
        + ["term_structure_dev_twd"])
    with open(COST_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ccols, extrasaction="ignore")
        w.writeheader()
        for r in cost:
            w.writerow({c: r.get(c, "") for c in ccols})

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    out_sql = emit_sql(all_rows, now)

    # Checksums by unit, not by series: EG47M01 mixes USD mn levels with
    # percentage growth rates, and one total over both is a number that cannot
    # be reproduced from the source or compared against the database. These
    # cover the LOADED set, which excludes the published 年增率 rows — the CSV
    # keeps everything, the table keeps what is not a transform of itself.
    loaded = [r for r in all_rows if r["sub_item"] != "年增率"]
    print(f"\nparsed: {len(all_rows):,} observations; loading {len(loaded):,} "
          f"({len(all_rows) - len(loaded):,} 年增率 rows held in the CSV only)"
          f"\n  checksums of the LOADED set, for server-side verification:")
    for code in SERIES:
        for unit in sorted({r["unit"] for r in loaded if r["matrix_code"] == code}):
            rs = [r for r in loaded
                  if r["matrix_code"] == code and r["unit"] == unit]
            print(f"  {code}  {unit:<14} n {len(rs):>6,}   "
                  f"sum(value) {sum(r['value'] for r in rs):,.4f}")

    print(f"\nMARKET-IMPLIED COST OF HEDGING USD BACK TO TWD, 90-day, "
          f"annualised %\n  (positive = the hedge costs carry; negative = it "
          f"earns it)")
    print(f"  {'year':<6}{'mean':>8}{'min':>8}{'max':>8}   {'months':>7}")
    by_year = {}
    for r in cost:
        v = r.get("cost_ann_pct_90")
        if v is not None:
            by_year.setdefault(r["obs_month"][:4], []).append(v)
    for y in sorted(by_year):
        v = by_year[y]
        print(f"  {y:<6}{sum(v)/len(v):>8.2f}{min(v):>8.2f}{max(v):>8.2f}   {len(v):>7}")

    compare_firms(cost, all_rows)

    print(f"\ncsv: {OUT_CSV.relative_to(ROOT)}, {COST_CSV.relative_to(ROOT)}"
          f"\nsql: {len(out_sql)} parts, "
          f"{out_sql[0].relative_to(ROOT)} … {out_sql[-1].name}")
    return 0 if ok else 1


# Optional stdin payload. A bare list is read as firm_costs, so the older
# invocation still works; a dict adds the hedge principal for the roll check.
STDIN_SQL = """
select json_build_object(
  'firm_costs', (select json_agg(json_build_object(
      'entity_id', entity_id, 'obs_date', obs_date, 'value', value))
    from tlfx.derived_series
    where series_id = 7 and series_key = 'hedge_cost_recurring'),
  'hedge_principal', (select json_agg(json_build_object(
      'obs_date', obs_date, 'value', value))
    from tlfx.derived_series
    where series_key = 'hedge_principal' and unit = 'NT$ mn'));
"""
# No exchange rate is requested: the NT$-to-USD conversion in the roll check
# uses the CBC's own spot from EG51M01, which this script has already parsed.
# Taking it from a second source would let the two legs of one ratio be
# converted at different rates.


def roll_check(cost, principal, rows):
    """Does the observed FX swap market look like the lifers' hedge book rolling?

    The counterparty question, asked as arithmetic rather than as a narrative.
    A hedge book of principal P, rolled at an average tenor of T trading days,
    generates P/T of turnover per day. If the observed customer swap and
    forward turnover is far larger, the lifers are a small part of that market
    and someone else's flow dominates it. If it is far smaller, the hedges are
    not being rolled through the onshore market at all and the counterparty is
    offshore. Neither of those is what the data says.

    The tenor is the assumption, and it is the only one: three months is the
    tenor the firms' own disclosures describe, and the check is reported across
    a range of tenors so a reader can see how much the conclusion depends on it.
    """
    if not principal:
        return
    spot_by_month = {r["obs_month"]: r["spot_bid"] for r in cost}
    swap = {r["obs_month"]: r["value"] for r in rows
            if r["matrix_code"] == "EG47M01"
            and r["item"] == "銀行對顧客市場-換匯" and r["sub_item"] == "原始值"}
    fwd = {r["obs_month"]: r["value"] for r in rows
           if r["matrix_code"] == "EG47M01"
           and r["item"] == "銀行對顧客市場-遠期" and r["sub_item"] == "原始值"}

    print("\nCOUNTERPARTY CHECK — does the onshore swap market look like the "
          "lifers' book rolling?")
    print(f"  {'month':<12}{'principal':>12}{'implied roll, USD bn/day':>26}"
          f"{'observed':>10}{'ratio':>8}")
    print(f"  {'':12}{'USD bn':>12}{'1m':>8}{'3m':>9}{'6m':>9}{'swap+fwd':>10}")
    for p in sorted(principal, key=lambda x: str(x["obs_date"])):
        m = str(p["obs_date"])[:10]
        s = spot_by_month.get(m)
        obs = (swap.get(m) or 0) + (fwd.get(m) or 0)
        if not s or not obs:
            continue
        usd = float(p["value"]) / s / 1000            # NT$ mn -> USD bn
        r1, r3, r6 = (usd / d for d in (21, 63, 126))
        print(f"  {m:<12}{usd:>12,.0f}{r1:>8.1f}{r3:>9.1f}{r6:>9.1f}"
              f"{obs/1000:>10.1f}{obs/1000/r3:>8.2f}")
    print("  ratio = observed turnover / the roll a 3-month book implies. Near "
          "1 means the\n  lifers' hedge rolling would account for essentially "
          "the whole customer swap and\n  forward market; the customer market "
          "also carries corporate and other financial\n  flow, so this is an "
          "upper bound on the lifer share, not a measurement of it.")


def compare_firms(cost, all_rows):
    """Set the market cost against what the firms say they actually paid.

    Optional: pipe the result of FIRM_COST_SQL in as JSON. Without it the run
    still produces the series; with it, it produces the check that makes the
    series worth trusting — and one number that is more interesting than the
    check.

    A firm's reported cost is all-in over its WHOLE foreign book. Only the part
    hedged with currency swaps and NDFs pays the market rate; proxy hedges pay
    less, and the FX-policy-backed and unhedged parts pay nothing. So the
    reported cost should track the market cost in direction and sit BELOW it in
    level, and the ratio between them is a rough read on how much of the book
    is carrying a market-priced hedge. If the reported cost ever exceeded the
    market cost, or moved against it, one of the two series would be wrong.
    """
    if sys.stdin.isatty():
        print("\n(nothing on stdin; skipping the firm comparison and the "
              "counterparty check — pipe in the result of STDIN_SQL to run "
              "them)")
        return
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print("\n(stdin was not valid JSON; skipping the firm comparison)")
        return
    firm = payload if isinstance(payload, list) else (payload.get("firm_costs") or [])
    if isinstance(payload, dict):
        roll_check(cost, payload.get("hedge_principal") or [], all_rows)

    # The firms report per QUARTER; the market series is monthly. Comparing a
    # quarter's reported cost against the market cost in the quarter's first
    # month alone would judge three months of hedging by one of them — and in
    # a quarter like 2022Q3, where the 90-day cost ran 0.9% to 3.4%, the choice
    # of month would move the ratio by a factor of three.
    qtr = {}
    for r in cost:
        v = r.get("cost_ann_pct_90")
        if v is not None:
            q = f"{r['obs_month'][:4]}-{(int(r['obs_month'][5:7]) - 1)//3*3 + 1:02d}-01"
            qtr.setdefault(q, []).append(v)
    mkt = {q: sum(v) / len(v) for q, v in qtr.items() if len(v) == 3}

    print("\nMARKET COST vs WHAT THE FIRMS REPORT PAYING  (bp of FX assets, "
          "quarterly)")
    print(f"  {'quarter':<12}{'firm':<14}{'reported':>9}{'market 90d':>12}"
          f"{'reported/market':>17}")
    ratios = {}
    for r in firm:
        m = str(r["obs_date"])[:10]
        mv = mkt.get(m)
        if mv is None or mv <= 0:
            continue
        rep = float(r["value"])
        ratio = rep / (mv * 100)
        ratios.setdefault(r["entity_id"], []).append(ratio)
        print(f"  {m:<12}{r['entity_id']:<14}{rep:>9.0f}{mv*100:>12.0f}"
              f"{ratio:>17.2f}")
    # An all-in cost over a book that is only partly hedged with market-priced
    # instruments must sit BELOW the market rate. Occasional exceptions are
    # expected — a firm rolls an existing book, so a quarter when the forward
    # curve reprices faster than the book can show a realised cost above the
    # current market one. A firm that is above market REPEATEDLY is reporting
    # something else, and the count is what separates the two cases.
    for ent, rs in sorted(ratios.items()):
        over = sum(1 for x in rs if x > 1)
        verdict = (f"consistent with an all-in cost ({over} of {len(rs)} "
                   "quarters above market)" if over / len(rs) <= 0.15
                   else f"ABOVE MARKET in {over} of {len(rs)} quarters — this "
                        "series is not an all-in ex-ante carry cost and should "
                        "not be pooled with one")
        print(f"  {ent}: n {len(rs)}, mean {sum(rs)/len(rs):.2f}, "
              f"range {min(rs):.2f}–{max(rs):.2f}  →  {verdict}")


if __name__ == "__main__":
    sys.exit(main())
