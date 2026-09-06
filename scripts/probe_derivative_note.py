#!/usr/bin/env python3
"""Run the extractors against named filings and report whether they worked.

WHY THIS EXISTS
Both extractors were fixed against ONE filing (Fubon 113Q4). Fubon's layout is
not a standard: the number of columns, the wording of the shock rows and even
whether the sensitivity table is split at all are the filer's choices. A firm
whose table differs yields zero rows, and zero rows is indistinguishable in the
committed CSV from a firm that simply discloses nothing.

So this fetches a handful of filings and, for each, prints what the parsers
actually returned — instrument rows against the printed 合計, sensitivity rows
by table — and dumps the raw flattened text ONLY where extraction failed. That
is the diagnosis needed to write the next fixture, and it costs two requests a
filing instead of a three-hour run.

Usage: probe_derivative_note.py 5846:202602_5846_AI1.pdf 5874:202602_5874_AI1.pdf
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage6_firm_sensitivity import (  # noqa: E402
    BLOCK, FIRMS, INSTR, TRADITIONAL, notionals, pdf, sensitivities)

DEFAULT = ["5846:202602_5846_AI1.pdf", "5874:202602_5874_AI1.pdf",
           "6985:202602_6985_AI1.pdf", "2833:202504_2833_AI1.pdf"]


def report(co, name):
    print(f"\n{'#' * 78}\n# {FIRMS.get(co, co)}  {name}")
    p = pdf(co, name)
    if not p:
        print("  FETCH FAILED")
        return
    import pymupdf
    doc = pymupdf.open(p)
    print(f"# {len(doc)} pages, {p.stat().st_size:,} bytes")

    nots = notionals(p)
    sens = sensitivities(p)
    print(f"\n  notionals : {len(nots):>3} rows")
    by_date = {}
    for r in nots:
        by_date.setdefault((r["as_of"], r["note_kind"]), []).append(r)
    for (d, kind), rs in sorted(by_date.items(), key=lambda kv: str(kv[0])):
        tot = sum(r["notional_ntd_k"] for r in rs)
        trad = sum(r["notional_ntd_k"] for r in rs if r["traditional"])
        printed = next((r.get("total_ntd_k") for r in rs
                        if r.get("total_ntd_k")), None)
        flag = ""
        if printed:
            flag = ("  MATCHES 合計" if abs(tot - printed) <= max(1, 5e-4 * printed)
                    else f"  != 合計 {printed:,.0f}")
        print(f"    {d} {kind:<14} {len(rs):>2} rows  "
              f"all={tot / 1e6:>10,.1f}bn  傳統={trad / 1e6:>10,.1f}bn{flag}")
        for r in sorted(rs, key=lambda r: -r["notional_ntd_k"])[:6]:
            print(f"        {r['instrument']:<12} {r['notional_ntd_k'] / 1e6:>10,.1f}bn"
                  f"  {'傳統' if r['traditional'] else '-'}")

    print(f"\n  sensitivity: {len(sens):>3} rows")
    for r in sorted(sens, key=lambda r: (r["period_end"], r["table"], r["label"]))[:14]:
        print(f"    {r['period_end']} {r['scope']:<8} {r['table']:<7}"
              f"{r['label']:<16} {r['shock']:<6}{r['direction']:<4}"
              f"pnl={r['pnl_ntd_k'] / 1e6:>9,.1f}bn  eq={r['equity_ntd_k'] / 1e6:>9,.1f}bn")

    # Only dump text where a parser found nothing: that is the case that needs
    # a human read, and dumping it unconditionally buries the successes.
    if not nots:
        dump(doc, INSTR, "DERIVATIVES NOTE")
    if not sens:
        dump(doc, BLOCK, "SENSITIVITY TABLE")


def dump(doc, pat, what):
    print(f"\n  ---- {what}: NOTHING EXTRACTED, raw text follows ----")
    shown = 0
    for page in doc:
        raw = unicodedata.normalize("NFKC", page.get_text())
        if not pat.search(raw):
            continue
        digits = len(re.findall(r"\d{1,3}(?:,\d{3})+", raw))
        if digits < 6:                 # prose mentioning it, not the table
            continue
        flat = re.sub(r"\s+", " ", raw)[:3000]
        print(f"\n  PAGE {page.number + 1} ({digits} numbers)\n  {flat}")
        shown += 1
        if shown >= 2:
            return
    if not shown:
        print("  (no page carries it with numbers at all)")


def main():
    for spec in (sys.argv[1:] or DEFAULT):
        co, _, name = spec.partition(":")
        try:
            report(co, name)
        except Exception as e:
            print(f"  ERROR {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
