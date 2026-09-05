#!/usr/bin/env python3
"""The CBC's own balance sheet: the IRFCL template, quarterly.

WHY THIS EXISTS — IT IS A CORRECTION
------------------------------------
4.40 and 4.42 used the TIC survey's Taiwan row and attributed its agency-ABS
and corporate-bond lines to the life insurers, on the argument that a reserve
manager does not run a corporate-credit book. The user objected that TIC is a
COUNTRY, that it therefore contains the central bank, and that none of it can
be attributed without knowing the CBC's balance sheet. That objection is
correct, and two pieces of evidence settle it against the earlier reading:

  * TIC publishes NO official/private split by country. The annual survey gives
    one global "of which: holdings of FOI" line; the monthly SLT tables
    (slt1d_globl.csv) carry no official column at all; Major Foreign Holders
    covers Treasuries only and does not split by holder type either. So the
    question cannot be answered from TIC at any frequency.
  * The global FOI line refutes the specific argument that was used. At June
    2025 foreign OFFICIAL institutions held USD 524bn of US agency paper
    against USD 829bn held by foreign private holders — official money is 39%
    of the foreign-held agency stock. "Central banks do not buy agency MBS" is
    simply false.

So this script goes and gets the central bank's balance sheet. The CBC
publishes the IMF/BIS Data Template on International Reserves and Foreign
Currency Liquidity quarterly, in USD millions. It gives what is needed:

  Section I    reserve assets split into SECURITIES and currency/deposits, plus
               gold, plus other foreign currency assets held outside reserves.
  Section II   the aggregate short and long positions in FX forwards and
               futures against the domestic currency, INCLUDING THE FORWARD LEG
               OF CURRENCY SWAPS, by residual maturity. That is the CBC swap
               book Setser & S.T.W. (2019) could only estimate at USD 130bn
               with a 60-200bn interval. It is now a published number.

WHAT IT DOES AND DOES NOT SETTLE
--------------------------------
It gives securities versus deposits, not security type and not currency. So it
bounds how much of Taiwan's TIC row could be the CBC; it does not decompose it.
At 30 June 2025 the CBC held USD 554.7bn of securities against a TIC-measured
Taiwanese holding of USD 677bn of US long-term debt. The central bank is
therefore capable of accounting for most of that row, and the residual left for
private holders cannot be pinned down. The conclusion is that TIC's Taiwan row
is a statement about the COUNTRY and must not be read as a lifer series. The
sector-identified evidence is the IIP/BoP series (series 9), where reserve
assets are a separate line by construction, and the Formosa register (11).
"""
import datetime as dt
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "cbc_irfcl"
OUT = ROOT / "data" / "cbc_irfcl.csv"
INDEX = "https://www.cbc.gov.tw/tw/lp-6294-1.html"
UA = {"User-Agent": "Mozilla/5.0 (compatible; TLFX/1.0)"}

# Anchors are the English template labels, which are stable across editions;
# the Chinese gloss sits on the following line and the number on the line
# before the English label or just after it, depending on the vintage — so the
# value is taken as the nearest number within a small window and the result is
# checked against the template's own identities rather than trusted.
FIELDS = {
    "reserve_assets_total": r"A\.\s*Official reserve assets",
    "fx_reserves": r"\(1\)\s*Foreign currency reserves",
    "reserve_securities": r"\(a\)\s*Securities",
    "reserve_deposits": r"\(b\)\s*total currency and deposits",
    "gold": r"\(4\)\s*gold",
    "other_fx_assets": r"B\.\s*Other foreign currency assets",
}


def links():
    with urllib.request.urlopen(urllib.request.Request(INDEX, headers=UA),
                                timeout=120) as r:
        html = r.read().decode("utf-8", "replace")
    out = []
    for m in re.finditer(r'href="(/tw/dl-[^"]+)"\s+title="國際準備與外幣流動性'
                         r'([0-9]{4})\.([0-9]{2})\.([0-9]{2})', html):
        out.append((f"{m.group(2)}-{m.group(3)}-{m.group(4)}",
                    "https://www.cbc.gov.tw" + m.group(1)))
    return sorted(set(out))


def fetch(date, url):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"irfcl_{date}.pdf"
    if p.exists() and p.stat().st_size > 10000:
        return p
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                timeout=240) as r:
        body = r.read()
    if body[:4] != b"%PDF":
        return None
    p.write_bytes(body)
    return p


def nums(seg):
    return [float(x.replace(",", "")) for x in re.findall(r"-?[\d,]{1,15}\.?\d*", seg)
            if re.search(r"\d", x)]


def parse(path):
    import pymupdf
    doc = pymupdf.open(path)
    text = unicodedata.normalize("NFKC", "\n".join(p.get_text() for p in doc))
    lines = [x.strip() for x in text.splitlines()]
    got = {}
    for key, pat in FIELDS.items():
        rx = re.compile(pat, re.I)
        for i, ln in enumerate(lines):
            if not rx.search(ln):
                continue
            # the number sits on its own line, before or just after the label
            for j in (i - 1, i + 1, i + 2, i - 2, i + 3):
                if 0 <= j < len(lines) and re.fullmatch(r"[\d,]+(\.\d+)?", lines[j]):
                    got[key] = float(lines[j].replace(",", ""))
                    break
            if key in got:
                break
    # Section II: the swap book. The short-position line is followed by the
    # total and its three maturity buckets, and the long line repeats the shape.
    for i, ln in enumerate(lines):
        if not re.search(r"\(a\)\s*Short positions", ln, re.I):
            continue
        # the template prints the row as total then three residual-maturity
        # buckets. Rather than assume which numbers near the label belong to it,
        # look for a run of four consecutive numbers where the first is the sum
        # of the other three — that pattern identifies the row unambiguously and
        # is the validation at the same time.
        v = []
        for j in range(max(0, i - 8), min(len(lines), i + 8)):
            if re.fullmatch(r"[\d,]+(\.\d+)?", lines[j]):
                v.append(float(lines[j].replace(",", "")))
        run = next((v[k] for k in range(len(v) - 3)
                    if v[k] > 0 and abs(v[k] - sum(v[k + 1:k + 4]))
                    <= max(1.0, 0.005 * v[k])), None)
        if run is not None:
            got["fx_forward_short_total"] = run
            got["_swap_buckets_add"] = True
        elif v:
            got["fx_forward_short_total"] = max(v)
            got["_swap_buckets_add"] = False
        break
    return got


def main():
    rows = []
    for date, url in links():
        try:
            p = fetch(date, url)
        except Exception as e:
            print(f"  {date}: fetch failed ({type(e).__name__})")
            continue
        if not p:
            print(f"  {date}: not a PDF")
            continue
        g = parse(p)
        # the template's own identity: reserves = fx reserves + gold (+ IMF
        # position and SDRs, which Taiwan does not report). A row that fails it
        # has been mis-picked and is dropped rather than reported.
        a, f, gd = (g.get("reserve_assets_total"), g.get("fx_reserves"),
                    g.get("gold", 0.0))
        ok = a and f and abs(a - (f + gd)) <= max(2.0, 0.005 * a)
        s, dep = g.get("reserve_securities"), g.get("reserve_deposits")
        ok2 = s and dep and abs(f - (s + dep)) <= max(2.0, 0.005 * f)
        if not (ok and ok2):
            print(f"  {date}: identity check failed {g} — skipped")
            continue
        swap_ok = g.pop("_swap_buckets_add", None)
        if swap_ok is False:                 # keep the reserve rows, drop the swap
            g.pop("fx_forward_short_total", None)
        rows.append({"obs_date": date, **g})
        print(f"  {date}  reserves {a:>9,.0f}  securities {s:>9,.0f} "
              f"({100 * s / a:>4.1f}%)  deposits {dep:>7,.0f}  "
              f"fwd/swap short {g.get('fx_forward_short_total', float('nan')):>8,.0f}"
              f"  {'buckets add' if swap_ok else 'BUCKETS DO NOT ADD'}")

    if not rows:
        raise SystemExit("nothing parsed")
    import csv
    OUT.parent.mkdir(exist_ok=True)
    cols = ["obs_date"] + [c for c in rows[-1] if c != "obs_date"]
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} quarters -> {OUT.relative_to(ROOT)}")
    emit_sql(rows, cols)
    return 0


NOTE = (
    "Central Bank of the Republic of China (Taiwan), IMF/BIS Data Template on "
    "International Reserves and Foreign Currency Liquidity, quarterly, USD mn "
    "as published. Loaded because the TIC survey's Taiwan row mixes the central "
    "bank with private holders and TIC publishes NO official/private split by "
    "country at any frequency — so the CBC's own balance sheet is the only way "
    "to bound how much of Taiwan's measured US holdings is official money. "
    "reserve_securities is Section I(1)(a) and is SECURITIES OF ALL KINDS IN "
    "ALL CURRENCIES: the template gives no security-type and no currency "
    "breakdown, so it bounds the official share of Taiwan's TIC row without "
    "decomposing it. fx_forward_short_total is Section II.2(a), the aggregate "
    "SHORT position in FX forwards and futures against the domestic currency "
    "INCLUDING THE FORWARD LEG OF CURRENCY SWAPS — the CBC swap book that "
    "Setser and S.T.W. (2019) could only estimate."
)


def sqlq(v):
    return "'" + str(v).replace("'", "''") + "'"


def emit_sql(rows, cols):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    keys = {"reserve_assets_total": "cbc_reserve_assets",
            "fx_reserves": "cbc_fx_reserves",
            "reserve_securities": "cbc_reserve_securities",
            "reserve_deposits": "cbc_reserve_deposits",
            "gold": "cbc_reserve_gold",
            "other_fx_assets": "cbc_other_fx_assets",
            "fx_forward_short_total": "cbc_fx_forward_short_position"}
    vals = [(keys[c], r["obs_date"], r[c])
            for r in rows for c in cols if c in keys and r.get(c) is not None]
    vsql = ",\n  ".join("(%s, %s, %s)" % (sqlq(k), sqlq(d), repr(v))
                        for k, d, v in vals)
    sql = ("-- stage6-irfcl: generated by scripts/stage6_cbc_irfcl.py at " + now
           + ". Idempotent.\nbegin;\n"
           "with vals(series_key, obs_date, value) as (values\n  " + vsql + ")\n"
           "insert into tlfx.derived_series\n"
           "  (series_id, series_key, entity_id, obs_date, freq, value, unit,\n"
           "   definition_version, basis, basis_note, source_url, source_doc,\n"
           "   retrieved_at, vintage)\n"
           "select 12::smallint, series_key, null, obs_date::date, 'Q'::tlfx.frequency,\n"
           "  value, 'USD mn', 'irfcl', 'disclosed',\n  " + sqlq(NOTE) + ",\n  "
           + sqlq(INDEX) + ",\n"
           "  'CBC 國際準備與外幣流動性 (IRFCL data template), quarterly PDF',\n"
           "  " + sqlq(now) + "::timestamptz, current_date\n"
           "from vals\n"
           "on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) "
           "do nothing;\ncommit;\n")
    p = ROOT / "out" / ("stage6_irfcl_%s.sql" % dt.date.today().strftime("%Y%m%d"))
    p.parent.mkdir(exist_ok=True)
    p.write_text(sql, encoding="utf-8")
    print(f"rows for derived_series: {len(vals)}  sum {sum(v for _, _, v in vals):,.1f}")
    print(f"  sql: {p.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
