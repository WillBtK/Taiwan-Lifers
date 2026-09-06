#!/usr/bin/env python3
"""Dump the derivatives-note text of ONE statutory filing to stdout.

WHY THIS EXISTS
stage6_firm_sensitivity.notionals() reads a notional as "the first number after
an instrument name". On the filings pulled so far that yields exactly one row
per filing, which cannot be right: a life insurer running a multi-trillion book
discloses forwards, FX swaps, CCS and NDFs separately, each with a notional and
a fair value, for the current period and its comparative.

The fix depends entirely on how the table is actually laid out once the PDF's
one-glyph-per-line CJK is flattened — whether the notional is the first numeric
column or the third, whether buy and sell legs are separate rows, where the
period headers sit. Guessing costs a three-hour run per wrong guess.

So this prints the raw flattened text around every instrument mention and lets
the layout be read directly. It fetches ONE filing, not hundreds: the point is
to look, not to collect.

Text goes to the log rather than a committed file — no binary in the repo, and
no waiting on a commit to see it.
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage6_firm_sensitivity import (INSTR, pdf, FIRMS)  # noqa: E402


def main():
    co = sys.argv[1] if len(sys.argv) > 1 else "5865"      # Fubon Life
    name = sys.argv[2] if len(sys.argv) > 2 else "202404_5865_AI1.pdf"
    print(f"# {FIRMS.get(co, co)}  {name}\n")
    p = pdf(co, name)
    if not p:
        raise SystemExit("could not fetch the filing")
    import pymupdf
    doc = pymupdf.open(p)
    print(f"# {len(doc)} pages, {p.stat().st_size:,} bytes\n")

    shown = 0
    for page in doc:
        raw = unicodedata.normalize("NFKC", page.get_text())
        if not INSTR.search(raw):
            continue
        flat = re.sub(r"\s+", " ", raw)
        print(f"\n{'=' * 78}\nPAGE {page.number + 1}"
              f"   名目={'名目' in raw}  合約金額={'合約金額' in raw}"
              f"  避險活動={'避險活動' in raw}  匯率風險={'匯率風險' in raw}")
        # the whole page, flattened: the layout question is about ordering and
        # column count, and an excerpt around each hit would hide both
        print(flat[:4000])
        shown += 1
        if shown >= 6:
            break

    # ---- where the sensitivity analysis actually is ----
    # The first page mentioning 敏感度 is a cross-reference ("金融商品敏感度分析
    # 請參考附註六(三十二)"), not the table. Stopping there reported the table as
    # present while never seeing it. So: census every page that mentions it,
    # then print the ones that actually carry numbers.
    print(f"\n\n# ---- 敏感度 census ----")
    cands = []
    for page in doc:
        raw = unicodedata.normalize("NFKC", page.get_text())
        if "敏感度" not in raw:
            continue
        digits = len(re.findall(r"\d{1,3}(?:,\d{3})+", raw))
        heads = [h for h in ("利率風險", "匯率風險", "價格風險", "分析表",
                             "基點", "bp", "平移", "升值", "貶值")
                 if h in raw]
        cands.append((page.number + 1, digits, heads, raw))
        print(f"  p{page.number + 1:<4} numbers={digits:<4} {heads}")
    if not cands:
        print("  no page mentions 敏感度 at all")
        return 0
    print(f"\n# ---- the number-bearing ones ----")
    for num, digits, heads, raw in sorted(cands, key=lambda c: -c[1])[:3]:
        flat = re.sub(r"\s+", " ", raw)
        print(f"\n{'=' * 78}\nPAGE {num}  numbers={digits}\n{flat[:3500]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
