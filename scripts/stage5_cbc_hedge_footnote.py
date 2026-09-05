#!/usr/bin/env python3
"""The CBC's own sector hedge amount, from the footnote on table 8, back to 2012.

WHAT THIS IS, AND WHY IT WAS MISSED
-----------------------------------
Appendix 8 of the CBC's Financial Statistics Monthly — the life-insurer balance
sheet this project has parsed since Stage 2 — carries a footnote:

    115年7月底全體人壽保險公司換匯交易等避險交易餘額為52,180億元。
    As of the end of July 2026, outstanding hedge trading by life insurance
    companies, including swap trading, amounted to NT$5,218.0 billion.

That is the sector's hedged amount, monthly, published by the central bank.
Setser and S.T.W. (2019, §II.D) name it as one of their two sources. The Stage
2 parser read the table body and discarded the footnotes, so the number sat in
`cache/cbc/065_EF67_A4L.csv` from 4 September unread. Recorded here because the
lesson is general: a table's notes are part of the table.

WHAT IT MEASURES
----------------
換匯交易等避險交易 — "swap and similar hedging transactions". Against the FSC's
regulatory hedge principal at the same date it runs at about 62% (6.46tn vs
10.36tn at 2024-12), and the press puts currency swaps at "逾7成" of lifers'
hedges with NDFs "低於3成". So this is the ONSHORE, swap-based hedge book, and
excludes offshore non-deliverable forwards — which is exactly the ambiguity
Setser flagged ("it is unclear whether hedges in offshore markets are taken
into account by the CBC") and which the 2024-12 comparison now settles. The
ratio built here therefore sits BELOW the FSC's regulatory ratio by
construction, and the gap between them is the NDF share.

HOW THE HISTORY IS RECOVERED
----------------------------
Each monthly edition overwrites the same file on the CBC's site, so the CBC
keeps no archive. The Internet Archive does: it holds captures of the table's
PDF, XLS and CSV from 2011. Every distinct capture is one edition, and each
edition's footnote is one month's figure. The 2011 editions have no such
footnote, so the series begins between mid-2011 and 2012-03. What comes back is
sparse and irregular — roughly one point a year, denser recently — which is
what Setser described as "a small number of historical values". It is the
sector-level anchor the other constructions are checked against, not a monthly
series in itself.

The ratio pairs the footnote with 國外資產 from the SAME table, taken from the
CBC's API series EF67M01 (already cached and loaded, Stage 2). Same publisher,
same table, same month: no scope wedge to reason about, which is more than can
be said for any other denominator in this project.
"""
import csv
import datetime as dt
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "wayback" / "cbc_table8"
EF67 = ROOT / "cache" / "cbc_db" / "EF67M01.json"
LIVE_CSV = ROOT / "cache" / "cbc" / "065_EF67_A4L.csv"
OUT_CSV = ROOT / "data" / "cbc_hedge_footnote.csv"
RAW_KEEP = ROOT / "data" / "raw" / "cbc-table8-footnote"

TARGETS = ["cbc.gov.tw/public/data/EBOOKXLS/065_EF67_A4L.pdf",
           "cbc.gov.tw/public/data/EBOOKXLS/065_EF67_A4L.csv",
           "cbc.gov.tw/public/data/EBOOKXLS/P065.pdf"]
CDX = "https://web.archive.org/cdx/search/cdx?url={u}&output=json&fl=timestamp,original,digest&collapse=digest"
UA = "Mozilla/5.0 (compatible; TLFX/1.0)"

# 「115年7月底全體人壽保險公司換匯交易等避險交易餘額為52,180億元」
FOOTNOTE = re.compile(r"(\d{2,3})年\s*(\d{1,2})月底全體人壽保險公司換匯交易等避險交易餘額為\s*([\d,]+)\s*億元")


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def captures():
    """Every distinct edition the Internet Archive holds, oldest first."""
    out = []
    for t in TARGETS:
        try:
            rows = json.loads(get(CDX.format(u=urllib.parse.quote(t, safe=""))))
        except Exception as e:
            print(f"  cdx failed for {t}: {e}")
            continue
        out += [(r[0], r[1], r[2]) for r in rows[1:]]
    return sorted(out)


def text_of(path):
    if path.suffix == ".pdf":
        import pymupdf
        return "".join(p.get_text() for p in pymupdf.open(path))
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "big5", "cp950"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("big5", "replace")


def footnote(text):
    # The 2012 PDF encodes several characters as CJK compatibility ideographs
    # (保 as U+F9E0, for instance), which look identical and do not match.
    # NFKC folds them, and fullwidth digits, back to canonical forms.
    text = unicodedata.normalize("NFKC", text)
    m = FOOTNOTE.search(text.replace("\n", ""))
    if not m:
        return None
    y, mth, amt = int(m.group(1)) + 1911, int(m.group(2)), float(m.group(3).replace(",", ""))
    return f"{y}-{mth:02d}-01", amt * 100          # 億元 -> NT$ mn


def foreign_assets():
    """國外資產 by month from the CBC API series, the same table's own line."""
    d = json.loads(EF67.read_text(encoding="utf-8"))
    labels = [x["data"] for x in d["data"]["structure"]["Table1"]]
    col = next(i for i, l in enumerate(labels) if "國外資產" in l)
    out = {}
    for r in d["data"]["dataSets"]:
        if "M" in r[0] and r[1 + col] not in ("-", "", None):
            y, m = r[0].split("M")
            out[f"{int(y)}-{int(m):02d}-01"] = float(r[1 + col])
    return out


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    RAW_KEEP.mkdir(parents=True, exist_ok=True)
    fa = foreign_assets()
    found = {}                                   # obs_month -> record

    def take(obs, amt, src, vintage, path):
        # the same month can appear in several formats of one edition; keep
        # the earliest capture, which is the tightest bound on publication
        if obs in found and found[obs]["vintage"] <= vintage:
            return
        found[obs] = {"obs_month": obs, "hedge_outstanding_ntd_mn": amt,
                      "foreign_assets_ntd_mn": fa.get(obs),
                      "ratio": round(amt / fa[obs], 4) if fa.get(obs) else None,
                      "vintage": vintage, "source": src, "file": path.name}

    print("Internet Archive captures of CBC table 8:")
    for ts, orig, digest in captures():
        ext = orig.rsplit(".", 1)[-1].lower()
        p = CACHE / f"{ts}_{digest[:8]}.{ext}"
        if not p.exists():
            try:
                p.write_bytes(get(f"https://web.archive.org/web/{ts}id_/{orig}"))
            except Exception as e:
                print(f"  {ts} {ext}: fetch failed ({e})")
                continue
        fn = footnote(text_of(p))
        cap = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        if fn:
            obs, amt = fn
            take(obs, amt, f"https://web.archive.org/web/{ts}/{orig}", cap, p)
            print(f"  {cap}  {ext:<3}  edition {obs[:7]}  NT${amt/1000:,.1f}bn")
        else:
            print(f"  {cap}  {ext:<3}  no hedge footnote (pre-2012 layout)")

    # the live edition, fetched by the Stage 2 pipeline
    if LIVE_CSV.exists():
        fn = footnote(text_of(LIVE_CSV))
        if fn:
            obs, amt = fn
            take(obs, amt, "https://www.cbc.gov.tw/public/data/EBOOKXLS/065_EF67_A4L.csv",
                 dt.date.fromtimestamp(LIVE_CSV.stat().st_mtime).isoformat(), LIVE_CSV)
            print(f"  live      csv  edition {obs[:7]}  NT${amt/1000:,.1f}bn")

    rows = [found[k] for k in sorted(found)]
    if not rows:
        raise SystemExit("no footnotes recovered")
    # keep the footnote sentences themselves as provenance, not the PDFs
    (RAW_KEEP / "footnotes.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nTHE CBC SERIES — onshore swap-based hedges, sector, NT$ bn, and "
          f"as a share of the same table's 國外資產")
    print(f"  {'month':<10}{'hedged':>10}{'foreign assets':>16}{'ratio':>8}   captured")
    for r in rows:
        print(f"  {r['obs_month'][:7]:<10}{r['hedge_outstanding_ntd_mn']/1000:>10,.1f}"
              f"{(r['foreign_assets_ntd_mn'] or 0)/1000:>16,.1f}"
              f"{(('%.1f%%' % (r['ratio']*100)) if r['ratio'] else '-'):>8}   {r['vintage']}")

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    vals = []
    for r in rows:
        vals.append(("hedge_outstanding_cbc_footnote", r["obs_month"],
                     r["hedge_outstanding_ntd_mn"], "NT$ mn", "disclosed", r["vintage"], r["source"]))
        if r["ratio"] is not None:
            vals.append(("hedge_ratio_cbc_footnote", r["obs_month"], r["ratio"],
                         "ratio", "estimated", r["vintage"], r["source"]))
    vsql = ",\n  ".join("(" + ", ".join(sqlv(x) for x in v) + ")" for v in vals)
    sql = f"""-- stage5-cbc-footnote: generated by scripts/stage5_cbc_hedge_footnote.py at {now}. Idempotent.
begin;
with vals(series_key, obs_date, value, unit, basis, vintage, source_url) as (values
  {vsql})
insert into tlfx.derived_series
  (series_id, series_key, entity_id, obs_date, freq, value, unit,
   definition_version, basis, basis_note, source_url, source_doc, retrieved_at, vintage)
select 5::smallint, series_key, null, obs_date::date, 'M'::tlfx.frequency, value, unit,
  'cbc_footnote', basis,
  case series_key
    when 'hedge_outstanding_cbc_footnote' then
      'CBC Financial Statistics Monthly, appendix 8 (人壽保險公司資產負債統計表), '
      'footnote: 全體人壽保險公司換匯交易等避險交易餘額. Onshore swap-based hedges; '
      'runs ~62% of the FSC regulatory hedge principal at 2024-12, consistent with '
      'NDFs being excluded. Historical editions recovered from Internet Archive '
      'captures; vintage is the capture date, an upper bound on publication.'
    else
      'hedge_outstanding_cbc_footnote / 國外資產 from the same CBC table (EF67M01). '
      'Same publisher, table and month, so no scope wedge. Sits below the FSC '
      'regulatory ratio by construction: different numerator (no NDF) and '
      'denominator (all foreign assets, not the regulatory net base).'
  end,
  source_url,
  'CBC 金融統計月報 附8 / Financial Statistics Monthly appendix 8',
  '{now}'::timestamptz, vintage::date
from vals
on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) do nothing;
commit;
"""
    out = ROOT / "out" / f"stage5_cbc_footnote_{dt.date.today():%Y%m%d}.sql"
    out.parent.mkdir(exist_ok=True)
    out.write_text(sql, encoding="utf-8")
    amt = [v[2] for v in vals if v[0] == "hedge_outstanding_cbc_footnote"]
    rat = [v[2] for v in vals if v[0] == "hedge_ratio_cbc_footnote"]
    print(f"\nrows for derived_series: {len(vals)}   checksums: amount n {len(amt)} "
          f"sum {sum(amt):,.1f}; ratio n {len(rat)} sum {sum(rat):.4f}")
    print(f"csv: {OUT_CSV.relative_to(ROOT)}   sql: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
