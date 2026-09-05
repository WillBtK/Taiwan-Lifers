#!/usr/bin/env python3
"""What Taiwan actually holds in the US market, by security type — TIC survey.

WHY THIS AND NOT THE BALANCE OF PAYMENTS
----------------------------------------
4.39 built the flow: net acquisition of long-term foreign debt by the sector
the lifers dominate, quarterly, and its turn negative in 2025. But Taiwan's BoP
has no currency dimension and no issuer-type dimension, so it cannot say
"US dollar corporate". The US side can. Treasury's annual TIC survey of foreign
portfolio holdings of US securities reports, by country, the split into
Treasuries, agency debt, agency ABS, corporate debt, corporate ABS and
equities. That is exactly the cut the duration-demand question needs, measured
by the issuing country rather than the holding one, and it is an independent
count of the same exposure.

WHAT IT CANNOT DO, STATED UP FRONT
----------------------------------
TIC is by COUNTRY, not by sector: it does not separate the central bank's
reserves from the life insurers' portfolios. That matters for Treasuries and
agency non-ABS, which the CBC holds in size. It matters much less for the two
lines the question is about — a central bank does not run a USD 175bn
corporate-credit book, and Taiwan's official reserve guidance describes
deposits and sovereign paper. So corporate and agency-ABS holdings are read as
overwhelmingly private, i.e. the lifers, and Treasuries are not attributed at
all. That asymmetry is deliberate and is the whole reason the table is worth
parsing rather than the headline total.

TIC is also custodial: securities held through a custodian in a third country
are attributed to the custodian's country. The direction of that bias for
Taiwan is unknown and is not corrected for.

PARSING
-------
Every vintage carries the same table under three different names and two
different units:

    2013-2018   Table A2  "...long-term securities, by country and type of
                          security"                        millions
    2019        Table A2  "...by Country and Security Type" millions
    2021-2022   Table A6  "...by Country and Security Type" millions
    2023-2024   Table A6  "...by Country and Security"      billions

so the table is found by a loose title predicate, not by its number, and the
units are read off the page. The column block is always the same seven fields
in the same order under the group headers Total / Agency / Corporate, and the
PDF emits one text line per cell, so a country's row is its label followed by
seven numbers. A country name landing mid-column would still yield seven
plausible numbers, so the row is accepted only when the six components sum to
the stated total within rounding. That additivity check is the whole defence.
"""
import csv
import datetime as dt
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "tic"
OUT = ROOT / "data" / "tic_taiwan_holdings.csv"
BASE = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; TLFX/1.0)"}
# the file name alternates between shlNNNNr.pdf and shlaNNNNr.pdf across years
YEARS = [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023,
         2024, 2025]
COUNTRY = "Taiwan"
# seven cells, always in this order, under group headers Total / Agency / Corporate
COLS = ["lt_total", "equities", "treasuries",
        "agency_nonabs", "agency_abs", "corp_nonabs", "corp_abs"]
TITLE = re.compile(r"long-?term securities,\s*by country and", re.I)
# the other table worth having: LT debt by country across eight survey dates.
# It exists in every vintage (A9 in 2013-2019, A3 from 2021) and is the
# independent check on the composition table — the two are compiled from the
# same returns but printed in different units and rounded differently, so
# agreement on every overlapping year is a real, if not fully independent, tie.
TITLE_YRS = re.compile(r"long-?term debt securities,\s*by country", re.I)


def num(s):
    s = s.strip().replace(",", "")
    if s in ("*", "-", "--", ""):      # * means "less than $500 million" / "less than $500,000"
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def fetch(year):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"shl{year}.pdf"
    if p.exists():
        return p
    for name in (f"shl{year}r.pdf", f"shla{year}r.pdf", f"shl{year}.pdf", f"shla{year}.pdf"):
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + name, headers=UA),
                                        timeout=180) as r:
                body = r.read()
        except Exception:
            continue
        if body[:4] == b"%PDF":
            p.write_bytes(body)
            return p
    return None


def parse(path, year, label=COUNTRY):
    """The seven cells for one row label. label='Total' gives the world row,
    which is what turns a level into a market share — the grand total sits on
    the table's last continuation page and has the same seven-cell shape. The
    group header 'Total' is followed by 'Agency', not by numbers, so it cannot
    be mistaken for the total row."""
    import pymupdf
    doc = pymupdf.open(path)
    for page in doc:
        text = page.get_text()
        if not TITLE.search(text):
            continue
        lines = [x.strip() for x in text.splitlines()]
        if label not in lines:
            continue
        # the group-header band must be present: this is a positive check that
        # we are on the seven-column table and not one of the other A-tables
        if not ("Agency" in lines and "Corporate" in lines):
            continue
        scale = 1.0 if "Millions" in text else 1000.0   # report to USD mn
        for j in (i for i, x in enumerate(lines) if x == label):
            vals, k = [], j + 1
            while k < len(lines) and len(vals) < len(COLS):
                v = num(lines[k])
                if v is None:
                    break
                vals.append(v)
                k += 1
            if len(vals) != len(COLS):
                continue
            row = dict(zip(COLS, [v * scale for v in vals]))
            parts = sum(row[c] for c in COLS[1:])
            # rounding slack: billions-unit vintages round each of six cells to 1bn
            tol = max(4 * scale, 0.02 * row["lt_total"])
            if abs(parts - row["lt_total"]) > tol:
                print(f"  {year}: {label} row does not add "
                      f"({parts:,.0f} vs {row['lt_total']:,.0f}) — skipped")
                continue
            row["page"] = page.number + 1
            row["units"] = "millions" if scale == 1.0 else "billions"
            return row
    return None


def parse_years(path):
    """Taiwan's LT debt holdings across the eight survey dates one report lists."""
    import pymupdf
    doc = pymupdf.open(path)
    for page in doc:
        text = page.get_text()
        if not TITLE_YRS.search(text):
            continue
        lines = [x.strip() for x in text.splitlines()]
        if COUNTRY not in lines:
            continue
        years = [int(x) for x in lines if re.fullmatch(r"20\d\d", x)]
        if len(years) != 8:
            continue
        scale = 1.0 if "Millions" in text else 1000.0
        j = lines.index(COUNTRY)
        vals = [num(x) for x in lines[j + 1:j + 9]]
        if any(v is None for v in vals):
            continue
        return {y: v * scale for y, v in zip(years, vals)}
    return {}


SERIES = {"lt_total": "us_lt_securities_holdings",
          "equities": "us_equity_holdings",
          "treasuries": "us_treasury_holdings",
          "agency_nonabs": "us_agency_debt_holdings",
          "agency_abs": "us_agency_abs_holdings",
          "corp_nonabs": "us_corporate_bond_holdings",
          "corp_abs": "us_corporate_abs_holdings"}
TOTAL_KEY = "us_lt_debt_holdings"

NOTE = (
    "US Treasury / Federal Reserve annual survey of foreign portfolio holdings "
    "of US securities (the TIC 'SHL' benchmark), Taiwan's row, as of the last "
    "business day of June in the survey year; obs_date is set to 30 June "
    "throughout and the survey's own as-of date is 28-30 June. Composition "
    "comes from the seven-column table (Table A2 to 2019, Table A6 from 2021) "
    "and is reported in USD mn; the vintages to 2022 publish millions, 2023 "
    "onward publish billions and are rescaled, so those two years carry "
    "billion-level rounding. us_lt_debt_holdings additionally carries "
    "2007-2012 and 2020 from Table A9/A3 (LT debt by country across survey "
    "dates), which is the only source for 2020 because that survey report is "
    "not retrievable from the Treasury document server. MEASURES A COUNTRY, "
    "NOT A SECTOR: Treasuries and agency non-ABS mix the central bank's "
    "reserves with private portfolios and are not attributable to the life "
    "insurers; agency ABS and corporate debt are, since a reserve manager does "
    "not run a corporate-credit book. Custodial bias is uncorrected: paper "
    "held through a custodian outside Taiwan is attributed elsewhere."
)


def emit_sql(rows, yrs, world=()):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    vals = []
    for r in rows:
        d = "%d-06-30" % r["survey_year"]
        for col, key in SERIES.items():
            vals.append((key, d, r[col]))
    for y, v in sorted(yrs.items()):
        vals.append((TOTAL_KEY, "%d-06-30" % y, v))
    # the denominators are stored, not the ratios: a share is then computed in
    # SQL from two auditable primitives instead of being frozen at parse time
    for r in world:
        d = "%d-06-30" % r["survey_year"]
        for col, key in SERIES.items():
            vals.append(("world_" + key, d, r[col]))
    vsql = ",\n  ".join("(%s, %s, %s)" % (sqlq(k), sqlq(d), repr(v)) for k, d, v in vals)
    sql = ("-- stage6-tic: generated by scripts/stage6_tic_holdings.py at " + now
           + ". Idempotent.\nbegin;\n"
           "with vals(series_key, obs_date, value) as (values\n  " + vsql + ")\n"
           "insert into tlfx.derived_series\n"
           "  (series_id, series_key, entity_id, obs_date, freq, value, unit,\n"
           "   definition_version, basis, basis_note, source_url, source_doc,\n"
           "   retrieved_at, vintage)\n"
           "select 10::smallint, series_key, null, obs_date::date, 'A'::tlfx.frequency,\n"
           "  value, 'USD mn', 'tic_shl', 'disclosed',\n  " + sqlq(NOTE) + ",\n  "
           + sqlq(BASE) + ",\n"
           "  'TIC benchmark survey shlNNNNr.pdf, Tables A2/A6 and A3/A9',\n"
           "  " + sqlq(now) + "::timestamptz, current_date\n"
           "from vals\n"
           "on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) "
           "do nothing;\ncommit;\n")
    p = ROOT / "out" / ("stage6_tic_%s.sql" % dt.date.today().strftime("%Y%m%d"))
    p.parent.mkdir(exist_ok=True)
    p.write_text(sql, encoding="utf-8")
    print("\nrows for derived_series: %d" % len(vals))
    for k in sorted({v[0] for v in vals}):
        vs = [v[2] for v in vals if v[0] == k]
        print(f"  {k:<28} n {len(vs):>2}  sum {sum(vs):>16,.1f}")
    print("  sql: %s" % p.relative_to(ROOT))


def sqlq(v):
    return "'" + str(v).replace("'", "''") + "'"


def main():
    rows, yrs, world = [], {}, []
    for year in YEARS:
        p = fetch(year)
        if not p:
            print(f"  {year}: survey not retrievable")
            continue
        row = parse(p, year)
        if not row:
            print(f"  {year}: {COUNTRY} row not parsed")
            continue
        rows.append({"survey_year": year, **row})
        print(f"  {year}: p{row['page']:>4} ({row['units']}) "
              f"LT {row['lt_total']:>10,.0f}")
        yrs.update(parse_years(p))
        w = parse(p, year, "Total")
        if w:
            world.append({"survey_year": year, **w})

    if not rows:
        raise SystemExit("no surveys parsed")
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["survey_year"] + COLS + ["units", "page"])
        w.writeheader()
        w.writerows(rows)

    print("\nTAIWAN: HOLDINGS OF US LONG-TERM SECURITIES, USD bn (TIC survey, end-June)")
    hdr = ("year", "totalLT", "equities", "UST", "agyDebt", "agyABS", "corpBond", "corpABS",
           "debt", "credit", "cr%debt")
    print("  " + "".join(f"{h:>9}" for h in hdr))
    for r in rows:
        debt = r["lt_total"] - r["equities"]
        credit = r["agency_abs"] + r["corp_nonabs"] + r["corp_abs"]
        print(f"  {r['survey_year']:>9}" + "".join(f"{v / 1000:>9,.0f}" for v in
                                                   (r["lt_total"], r["equities"], r["treasuries"],
                                                    r["agency_nonabs"], r["agency_abs"],
                                                    r["corp_nonabs"], r["corp_abs"], debt, credit))
              + f"{100 * credit / debt:>9.0f}")
    print("  debt   = total LT less equities")
    print("  credit = agency ABS + corporate bonds + corporate ABS, i.e. the part")
    print("           a central bank's reserve portfolio does not hold")

    if yrs:
        print("\nCROSS-CHECK against Table A3/A9 (LT debt by country, selected survey dates)")
        bad = 0
        for r in rows:
            y = r["survey_year"]
            if y not in yrs:
                continue
            mine = (r["lt_total"] - r["equities"]) / 1000
            theirs = yrs[y] / 1000
            ok = abs(mine - theirs) <= max(1.0, 0.01 * theirs)
            bad += not ok
            print(f"  {y}  composition {mine:>6,.0f}   A3/A9 {theirs:>6,.0f}   "
                  f"{'ok' if ok else 'MISMATCH'}")
        print(f"  {len(rows) - bad}/{len(rows)} agree")
        gaps = sorted(set(yrs) - {r["survey_year"] for r in rows})
        if gaps:
            print("  years the composition table is missing but A3/A9 covers: "
                  + ", ".join(f"{y} {yrs[y] / 1000:,.0f}" for y in gaps))

    if world:
        # the level says how big Taiwan's book is; the share says whether it
        # matters to the market it buys in, which is the question actually asked
        wx = {r["survey_year"]: r for r in world}
        print("\nTAIWAN AS A SHARE OF ALL FOREIGN HOLDINGS OF US SECURITIES, %")
        print("  " + "".join(f"{h:>12}" for h in
                             ("year", "agency ABS", "corp bonds", "all LT debt")))
        for r in rows:
            w = wx.get(r["survey_year"])
            if not w:
                continue
            td = r["lt_total"] - r["equities"]
            wd = w["lt_total"] - w["equities"]
            print(f"  {r['survey_year']:>12}"
                  + f"{100 * r['agency_abs'] / w['agency_abs']:>12.1f}"
                  + f"{100 * r['corp_nonabs'] / w['corp_nonabs']:>12.1f}"
                  + f"{100 * td / wd:>12.1f}")

    emit_sql(rows, yrs, world)
    print(f"\ncsv: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
