#!/usr/bin/env python3
"""Taiwan's lifers as a source of duration demand: the stock and the flow.

THE QUESTION THIS SERVES
------------------------
The hedge ratio is a gate, not the object. What matters to a bond market is
that a single domestic sector recycles a current-account surplus above 10% of
GDP into long-dated foreign credit — overwhelmingly USD, overwhelmingly
corporate and agency, with an average duration the firms themselves put beyond
ten years. This builds the two series that size that, and the exposures that
would make it reverse.

THE SERIES, AND WHY THIS PARTICULAR CUT
---------------------------------------
Taiwan's balance of payments splits portfolio-investment debt-security
acquisition by sector AND by tenor. The cut that matters is

    債務證券 - 其他部門 - 其他金融機構 - 長期 - 資產
    debt securities / other sectors / other financial institutions /
    LONG-TERM / assets

quarterly from 1984Q1. "Other financial institutions" is the residual holding
insurers, funds and non-bank financials, and in Taiwan it is dominated by the
life insurers (Setser & S.T.W. 2019 §II.B establish this by comparing the
cumulative flow against the lifers' own foreign-asset series; that comparison
is reproduced here rather than assumed). The long-term leg is the duration
demand proper: short-dated purchases by the same sector are cash management,
not a bid for the long end.

Three things follow that the FX work could not give:
  * the FLOW, quarterly, over four decades — including the two episodes when it
    stopped, which is what a vulnerability case has to be calibrated against;
  * the STOCK, from the IIP, as an independent check on cumulating the flow;
  * the SHARE of all Taiwanese foreign debt buying this one sector accounts
    for, which is what makes it a market participant rather than a curiosity.

SIGN CONVENTION
---------------
BPM6: a positive asset entry is a NET ACQUISITION of foreign assets, i.e. an
outflow and a purchase. Negative means net selling. This is stated because the
whole vulnerability question is about the sign flipping, and a series that is
read upside down would answer it exactly backwards.
"""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOP = ROOT / "cache" / "cbc_db" / "BPP2Q01.json"
IIP = ROOT / "cache" / "cbc_db" / "BPF4Y01.json"
OUT = ROOT / "data" / "duration_demand.csv"
API_BOP = "https://cpx.cbc.gov.tw/API/DataAPI/Get?FileName=BPP2Q01"

# Item labels, resolved by name rather than by index. The BoP has 402 items and
# the CBC has reordered them before; matching on the label fails loudly if the
# structure moves, where an index would silently return a different series.
FLOW = {
    "ca_net":            "經常帳-淨額",
    "debt_all_assets":   "債務證券-資產",
    "debt_ofi_assets":   "債務證券-其他部門-其他金融機構-資產",
    "debt_ofi_lt":       "債務證券-其他部門-其他金融機構-長期-資產",
    "debt_ofi_st":       "債務證券-其他部門-其他金融機構-短期-資產",
    "debt_banks":        "債務證券-存款貨幣機構-資產",
    "debt_govt":         "債務證券-政府-資產",
    "debt_cbc":          "債務證券-中央銀行-資產",
    "reserves":          "準備資產",
}
# Life-insurer foreign assets (國外資產) at year-end, USD mn, from the CBC
# life-insurer balance sheet already loaded in Stage 2, converted at the
# year-end rate. Used only to size the lifers against the whole OFI sector.
LIFER_FA = {"2012": 176029.6, "2013": 207019.2, "2014": 250280.8, "2015": 303218.3,
            "2016": 374137.2, "2017": 453383.8, "2018": 507507.9, "2019": 551754.9,
            "2020": 621029.5, "2021": 687832.9, "2022": 667914.6, "2023": 684751.0,
            "2024": 685507.7, "2025": 700078.5}

STOCK = {"iip_debt_ofi_assets": "證券投資-債務證券-其他部門-其他金融機構-資產",
         "iip_debt_all_assets": "證券投資-債務證券-資產"}


def series(path, wanted):
    d = json.loads(path.read_text(encoding="utf-8"))
    labels = [x["data"] for x in d["data"]["structure"]["Table1"]]
    t2 = [x["data"] for x in d["data"]["structure"].get("Table2", [])] or [""]
    idx = {}
    for key, label in wanted.items():
        if label not in labels:
            raise SystemExit(f"{path.name}: item not found — {label!r}. The "
                             f"source structure has changed; re-map before trusting output.")
        idx[key] = labels.index(label)
    out = {}
    for r in d["data"]["dataSets"]:
        p = r[0]
        row = {}
        for key, i in idx.items():
            v = r[1 + i * len(t2)]
            row[key] = None if v in ("-", "", None) else float(v)
        out[p] = row
    return out


def qkey(p):
    """1984Q1 -> (1984, 1); annual codes pass through as quarter 4."""
    if "Q" in p:
        y, q = p.split("Q")
        return int(y), int(q)
    return int(p), 4


NOTE = (
    "Taiwan balance of payments / international investment position, CBC. "
    "債務證券-其他部門-其他金融機構 (portfolio-investment debt securities, other "
    "sectors, other financial institutions) — the sector that in Taiwan is "
    "dominated by the life insurers: their own 國外資產 runs 90-110% of this "
    "sector's IIP debt stock across 2012-2025, the excess in the early years "
    "being lifer equity and fund holdings that a debt-only stock excludes. "
    "BPM6 sign convention: a POSITIVE asset entry is a net ACQUISITION of "
    "foreign assets, so negative means net SELLING. The long-term leg is the "
    "duration bid proper; the short-term leg is cash management and is kept as "
    "a separate series rather than folded in."
)


def sqlq(v):
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return repr(v)


def emit_sql(rows, stock):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    vals = []
    for r in rows:
        if r["debt_ofi_long_term_usd_mn"] is not None:
            vals.append(("ofi_lt_foreign_debt_purchases", r["obs_quarter"], "Q",
                         r["debt_ofi_long_term_usd_mn"]))
        if r["debt_ofi_assets_usd_mn"] is not None:
            vals.append(("ofi_foreign_debt_purchases", r["obs_quarter"], "Q",
                         r["debt_ofi_assets_usd_mn"]))
    for y in sorted(stock):
        s = stock[y]
        if s["iip_debt_ofi_assets"] is not None:
            vals.append(("ofi_foreign_debt_stock", y + "-12-31", "A",
                         s["iip_debt_ofi_assets"]))
    vsql = ",\n  ".join("(" + ", ".join(sqlq(x) for x in v) + ")" for v in vals)
    sql = (
        "-- stage6-duration: generated by scripts/stage6_duration_demand.py at "
        + now + ". Idempotent.\nbegin;\n"
        "with vals(series_key, obs_date, freq, value) as (values\n  " + vsql + ")\n"
        "insert into tlfx.derived_series\n"
        "  (series_id, series_key, entity_id, obs_date, freq, value, unit,\n"
        "   definition_version, basis, basis_note, source_url, source_doc,\n"
        "   retrieved_at, vintage)\n"
        "select 9::smallint, series_key, null, obs_date::date, freq::tlfx.frequency,\n"
        "  value, 'USD mn', 'bpm6', 'disclosed',\n  " + sqlq(NOTE) + ",\n  "
        + sqlq(API_BOP) + ",\n"
        "  'CBC statistics database, BPP2Q01 (balance of payments) and BPF4Y01 (IIP)',\n"
        "  " + sqlq(now) + "::timestamptz, current_date\n"
        "from vals\n"
        "on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) do nothing;\n"
        "commit;\n")
    out_sql = ROOT / "out" / ("stage6_duration_%s.sql" % dt.date.today().strftime("%Y%m%d"))
    out_sql.parent.mkdir(exist_ok=True)
    out_sql.write_text(sql, encoding="utf-8")
    print("\nrows for derived_series: %d" % len(vals))
    for k in sorted({v[0] for v in vals}):
        vs = [v[3] for v in vals if v[0] == k]
        print("  %-32s n %3d  sum %,.1f".replace(",.1f", ".1f") % (k, len(vs), sum(vs)))
    print("  sql: %s" % out_sql.relative_to(ROOT))
    return out_sql


def main():
    flow = series(BOP, FLOW)
    stock = series(IIP, STOCK)

    rows, cum = [], 0.0
    for p in sorted((k for k in flow if "Q" in k), key=qkey):
        y, q = qkey(p)
        f = flow[p]
        lt = f["debt_ofi_lt"]
        if lt is not None:
            cum += lt
        share = (f["debt_ofi_assets"] / f["debt_all_assets"]
                 if f["debt_ofi_assets"] is not None and f["debt_all_assets"] else None)
        rows.append({
            "obs_quarter": f"{y}-{q*3-2:02d}-01", "period": p,
            "ca_net_usd_mn": f["ca_net"],
            "debt_all_assets_usd_mn": f["debt_all_assets"],
            "debt_ofi_assets_usd_mn": f["debt_ofi_assets"],
            "debt_ofi_long_term_usd_mn": lt,
            "debt_ofi_short_term_usd_mn": f["debt_ofi_st"],
            "debt_banks_usd_mn": f["debt_banks"],
            "debt_cbc_usd_mn": f["debt_cbc"],
            "reserves_usd_mn": f["reserves"],
            "ofi_share_of_debt_buying": None if share is None else round(share, 4),
            "cum_ofi_long_term_usd_mn": round(cum, 1),
        })

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    live = [r for r in rows if r["debt_ofi_long_term_usd_mn"] is not None]
    print(f"BoP quarters: {len(rows)} ({rows[0]['period']} → {rows[-1]['period']}); "
          f"long-term OFI leg populated from {live[0]['period']}")

    print("\nNET ACQUISITION OF FOREIGN LONG-TERM DEBT BY OTHER FINANCIAL "
          "INSTITUTIONS\n  (USD bn a year; positive = buying. This is the lifers' "
          "duration bid.)")
    print(f"  {'year':<6}{'LT debt':>10}{'ST debt':>9}{'all debt':>10}"
          f"{'OFI share':>11}{'CA':>9}{'reserves':>10}")
    by_year = {}
    for r in live:
        by_year.setdefault(r["period"][:4], []).append(r)
    for y in sorted(by_year):
        g = by_year[y]
        if len(g) < 4:
            continue
        s = lambda k: sum(x[k] or 0 for x in g) / 1000
        share = s("debt_ofi_assets_usd_mn") / s("debt_all_assets_usd_mn") if s("debt_all_assets_usd_mn") else 0
        print(f"  {y:<6}{s('debt_ofi_long_term_usd_mn'):>10,.1f}"
              f"{s('debt_ofi_short_term_usd_mn'):>9,.1f}"
              f"{s('debt_all_assets_usd_mn'):>10,.1f}{share:>10.0%}"
              f"{s('ca_net_usd_mn'):>9,.1f}{s('reserves_usd_mn'):>10,.1f}")

    print("\nSTOCK — IIP holdings of foreign debt securities, USD bn")
    print(f"  {'year':<6}{'OFI':>10}{'all sectors':>13}{'OFI share':>11}")
    for p in sorted(stock, key=qkey):
        s = stock[p]
        if s["iip_debt_ofi_assets"] is None:
            continue
        a, b = s["iip_debt_ofi_assets"] / 1000, (s["iip_debt_all_assets"] or 0) / 1000
        print(f"  {p:<6}{a:>10,.1f}{b:>13,.1f}{(a/b if b else 0):>10.0%}")

    # Is "other financial institutions" really the lifers? Setser & S.T.W.
    # assert it; this measures it. The lifers' own foreign-asset series from the
    # CBC's life-insurer balance sheet, converted at the year-end rate, against
    # the IIP holding of the whole OFI sector. A share near 1 means the sector
    # IS the lifers and the flow series can be read as theirs; a share far below
    # would mean funds and other non-banks are doing the buying and the whole
    # reading changes.
    if LIFER_FA:
        print("\nIDENTIFICATION — are 'other financial institutions' the lifers?")
        print(f"  {'year':<6}{'lifer FX assets':>17}{'OFI IIP stock':>15}{'lifer share':>13}")
        for y in sorted(LIFER_FA):
            s = stock.get(y)
            if not s or s["iip_debt_ofi_assets"] is None:
                continue
            lf = LIFER_FA[y] / 1000
            print(f"  {y:<6}{lf:>15,.0f}bn{s['iip_debt_ofi_assets']/1000:>13,.0f}bn"
                  f"{lf/(s['iip_debt_ofi_assets']/1000):>12.0%}")
        print("  (lifer FX assets are the CBC life-insurer balance sheet's 國外資產 at "
              "the year-end\n   rate; the OFI stock also holds funds and other "
              "non-banks, so a share below 1 is expected\n   and its stability is "
              "what licenses reading the flow as the lifers'.)")

    emit_sql(rows, stock)
    print(f"\ncsv: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
