#!/usr/bin/env python3
"""The Formosa bond register: the USD duration the TIC survey cannot see.

WHY
---
4.40 measured Taiwan's holdings of US-ISSUED securities and found the gap that
matters: from 2019 the lifers' own foreign debt stock (OFI IIP, USD 749bn at
end-2024) EXCEEDS Taiwan's entire country-wide holding of US long-term debt
(632bn, June 2024) — before setting aside whatever part of that is the CBC's
reserves. So a large part of the lifers' USD book is not US-issued and the TIC
survey never sees it.

國際板債券 — Formosa bonds — are the obvious candidate and this quantifies them.
They are foreign-issuer paper listed on the Taipei Exchange, overwhelmingly
USD-denominated, sold to professional investors. They are USD credit risk and
USD duration; they are not US securities, so they appear in no TIC table.

WHAT THIS FILE IS AND IS NOT
----------------------------
TPEx publishes the register of CURRENTLY LISTED international bonds. Three
consequences, all of which bound what may be claimed:

  * It is a SNAPSHOT, not a history. Bonds that matured or were called are
    gone from it. The by-issue-year totals below are therefore "issued then and
    still listed now" — heavily survivorship-biased, since the 2020-21 rate
    rally saw callable issues redeemed en masse. They are NOT an issuance
    history and must not be read as one.
  * AmountOfIssuance is the size at issue, not the amount outstanding today;
    partial redemptions do not show. It is an upper bound on outstanding for
    each live line.
  * It says what EXISTS, not who OWNS it. The register carries no holder
    information. Attributing the bulk of it to the life insurers rests on the
    regulatory history and on supervisors' statements, not on this file, and is
    kept out of the loaded data — the rows here are market size, not lifer
    holdings.

WHAT IT DOES SETTLE
-------------------
The shape of the paper: currency, original tenor, remaining maturity, and
whether the investor is short a call. That is the duration-demand question in
its most direct form, and none of it depends on the caveats above, because it
is measured across the live book rather than across time.
"""
import collections
import csv
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "formosa_register.csv"
API = "https://www.tpex.org.tw/openapi/v1/"
# two registers, same schema: bonds sold to professional investors only (the
# market proper) and the small retail-eligible tranche. Both are 國際債券.
ENDPOINTS = ["tpex_international_bond_issue_org",
             "tpex_international_bond_issue_investor"]
UA = {"User-Agent": "Mozilla/5.0 (compatible; TLFX/1.0)"}
TODAY = dt.date.today()


def fetch(name):
    req = urllib.request.Request(API + name, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def amt(r):
    try:
        return float(r["AmountOfIssuance"] or 0)
    except (TypeError, ValueError):
        return 0.0


def date(s):
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except (TypeError, ValueError):
        return None


def perpetual(r):
    """TPEx codes a perpetual as tenor 99.9 maturing 2910-12-31. Left in the
    tenor average it would add half a year to it, and left in the maturity
    ladder it would print a bucket in the thirtieth century."""
    return r["Tenor"].strip() == "99.9" or r["MaturityDate"].startswith("2910")


def domestic(r):
    """Issuer names in Chinese characters are the Taiwanese issuers — TSMC, the
    banks, and the lifers' own USD sub-debt. They are Formosa listings but not
    foreign credit, so they are reported separately rather than netted out."""
    return any("一" <= ch <= "鿿" for ch in r["Issuer"])


def main():
    rows = []
    for e in ENDPOINTS:
        d = fetch(e)
        print(f"  {e}: {len(d)} issues")
        rows += d
    if not rows:
        raise SystemExit("register empty")

    cur = collections.Counter()
    n = collections.Counter()
    for r in rows:
        c = r["CurrencyDenomination"].strip()
        cur[c] += amt(r)
        n[c] += 1
    total = sum(cur.values())
    print(f"\nLISTED INTERNATIONAL (FORMOSA) BONDS, {TODAY}: "
          f"{len(rows)} issues, USD-equivalent face at issue")
    for c, v in cur.most_common():
        print(f"  {c:>5}  n {n[c]:>4}  {v / 1e9:>8,.1f} bn  {100 * v / total:>5.1f}%")

    us = [r for r in rows if r["CurrencyDenomination"].strip() == "USD"]
    T = sum(amt(r) for r in us)

    dom = sum(amt(r) for r in us if domestic(r))
    perp = sum(amt(r) for r in us if perpetual(r))
    dated = [r for r in us if not perpetual(r)]
    Td = sum(amt(r) for r in dated)

    # original tenor, amount-weighted: the single number that says whether this
    # market is a duration bid or a money-market product
    wt = sum(amt(r) * float(r["Tenor"] or 0) for r in dated if r["Tenor"]) / Td
    print(f"\nUSD book: {T / 1e9:,.1f} bn across {len(us)} issues")
    print(f"  of which Taiwanese issuers: {dom / 1e9:,.1f} bn "
          f"({100 * dom / T:.1f}%) — TSMC, the banks, and lifer USD sub-debt")
    print(f"  of which perpetual: {perp / 1e9:,.1f} bn, excluded from the "
          f"tenor figures below")
    print(f"  amount-weighted ORIGINAL tenor: {wt:,.1f} years")

    tenor = collections.Counter()
    for r in dated:
        t = float(r["Tenor"] or 0)
        tenor["<=10" if t <= 10 else "11-20" if t <= 20 else
              "21-30" if t <= 30 else ">30"] += amt(r)
    for k in ("<=10", "11-20", "21-30", ">30"):
        print(f"    original tenor {k:>6}: {tenor[k] / 1e9:>8,.1f} bn "
              f"{100 * tenor[k] / Td:>5.1f}%")

    rem = collections.Counter()
    ladder = collections.Counter()
    for r in dated:
        m = date(r["MaturityDate"])
        if not m:
            continue
        y = (m - TODAY).days / 365.25
        rem["<1" if y < 1 else "1-3" if y < 3 else "3-5" if y < 5 else
            "5-10" if y < 10 else "10-20" if y < 20 else "20+"] += amt(r)
        ladder[m.year] += amt(r)
    print("  remaining maturity:")
    for k in ("<1", "1-3", "3-5", "5-10", "10-20", "20+"):
        print(f"    {k:>6}: {rem[k] / 1e9:>8,.1f} bn {100 * rem[k] / Td:>5.1f}%")

    # the convexity point: a callable long bond is not a long bond in a rally
    # and is worse than one in a sell-off
    call = sum(amt(r) for r in us
               if r["EarlyRedemption"].strip() not in ("Not Applicable", ""))
    print(f"  issuer-callable: {call / 1e9:,.1f} bn = {100 * call / T:.1f}% of the USD book")
    struct = collections.Counter(r["NonCallPeriodYearxCallFrequencyYear"].strip()
                                 for r in us)
    print("  most common non-call x call-frequency structures:")
    for k, v in struct.most_common(5):
        print(f"    {k:<20} {v:>4} issues")

    iss = collections.Counter()
    for r in us:
        iss[r["Issuer"].strip().replace("&amp;", "&")] += amt(r)
    print("  largest issuers, USD bn:")
    for k, v in iss.most_common(10):
        print(f"    {v / 1e9:>6,.1f}  {k[:55]}")

    vintage = collections.Counter()
    for r in us:
        d0 = date(r["IssuingDate"])
        if d0:
            vintage[d0.year] += amt(r)
    print("  issued in year and STILL LISTED (survivorship-biased, not issuance):")
    print("    " + "  ".join(f"{y}:{vintage[y] / 1e9:,.0f}" for y in sorted(vintage)))

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\ncsv: {OUT.relative_to(ROOT)}  ({len(rows)} issues)")

    emit_sql(cur, T, wt, tenor, rem, ladder, call, len(us), dom, perp)
    return 0


NOTE = (
    "Taipei Exchange register of CURRENTLY LISTED 國際債券 (Formosa bonds): "
    "foreign-issuer paper listed in Taipei, sold mainly to professional "
    "investors. This is USD credit and USD duration that the US TIC survey "
    "cannot see, because the issuers are not US residents — it is the missing "
    "piece between the lifers' foreign debt stock and Taiwan's measured "
    "holdings of US securities. THREE LIMITS. (1) Snapshot, not history: "
    "matured and called issues are absent, so amounts by issue year are "
    "'issued then and still listed now' and are NOT an issuance series. "
    "(2) Amounts are face at issue, not amount outstanding: partial "
    "redemptions do not show, so each line is an upper bound. (3) The register "
    "carries NO holder information — these rows are market size, not life "
    "insurer holdings, and nothing here attributes them to the lifers."
)


def sqlq(v):
    return "'" + str(v).replace("'", "''") + "'"


def emit_sql(cur, T, wt, tenor, rem, ladder, call, n_us, dom, perp):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    d = TODAY.isoformat()
    vals = [("formosa_listed_face_all_ccy", d, sum(cur.values()) / 1e6, "USD mn"),
            ("formosa_usd_listed_face", d, T / 1e6, "USD mn"),
            ("formosa_usd_issue_count", d, float(n_us), "count"),
            ("formosa_usd_wavg_original_tenor", d, round(wt, 2), "years"),
            ("formosa_usd_callable_face", d, call / 1e6, "USD mn"),
            ("formosa_usd_face_domestic_issuer", d, dom / 1e6, "USD mn"),
            ("formosa_usd_face_perpetual", d, perp / 1e6, "USD mn")]
    for k, v in tenor.items():
        vals.append(("formosa_usd_face_original_tenor_" + k.replace("<=", "le")
                     .replace(">", "gt").replace("-", "_"), d, v / 1e6, "USD mn"))
    for k, v in rem.items():
        vals.append(("formosa_usd_face_remaining_" + k.replace("<", "lt")
                     .replace("+", "plus").replace("-", "_"), d, v / 1e6, "USD mn"))
    # the roll-off schedule: dated to the maturity year, so it reads as a
    # forward ladder rather than as a snapshot attribute
    for y, v in sorted(ladder.items()):
        vals.append(("formosa_usd_face_maturing", f"{y}-12-31", v / 1e6, "USD mn"))
    vsql = ",\n  ".join("(%s, %s, %s, %s)" % (sqlq(k), sqlq(dd), repr(v), sqlq(u))
                        for k, dd, v, u in vals)
    sql = ("-- stage6-formosa: generated by scripts/stage6_formosa_register.py at "
           + now + ". Idempotent.\nbegin;\n"
           "with vals(series_key, obs_date, value, unit) as (values\n  " + vsql + ")\n"
           "insert into tlfx.derived_series\n"
           "  (series_id, series_key, entity_id, obs_date, freq, value, unit,\n"
           "   definition_version, basis, basis_note, source_url, source_doc,\n"
           "   retrieved_at, vintage)\n"
           "select 11::smallint, series_key, null, obs_date::date, 'A'::tlfx.frequency,\n"
           "  value, unit, 'tpex_register', 'disclosed',\n  " + sqlq(NOTE) + ",\n  "
           + sqlq(API + ENDPOINTS[0]) + ",\n"
           "  'TPEx OpenAPI tpex_international_bond_issue_org and _investor',\n"
           "  " + sqlq(now) + "::timestamptz, " + sqlq(d) + "::date\n"
           "from vals\n"
           "on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) "
           "do nothing;\ncommit;\n")
    p = ROOT / "out" / ("stage6_formosa_%s.sql" % TODAY.strftime("%Y%m%d"))
    p.parent.mkdir(exist_ok=True)
    p.write_text(sql, encoding="utf-8")
    print(f"\nrows for derived_series: {len(vals)}  "
          f"sum(USD mn rows) {sum(v for _, _, v, u in vals if u == 'USD mn'):,.3f}")
    print(f"  sql: {p.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
