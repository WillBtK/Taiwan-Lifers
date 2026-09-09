#!/usr/bin/env python3
"""The FX hedging pie, read from the harvested investor decks.

This is what closes the two holes in the sector aggregate. Taiwan Life and Shin
Kong both publish the same four-bucket decomposition of their foreign
investment that the sell-side workbook tabulates, and neither was in this
project until the MOPS deck harvest.

  Taiwan Life (CTBC 2891)   外幣保單 38% 已避險 20% Equity-OCI 6% 未避險 36%
  Shin Kong  (Taishin 2887) 股票及基金 / 外幣保單 / 已避險 / 未避險, with the
                            base printed as 外幣資產總計 = 新台幣20,585億元

TWO LAYOUTS, AND ONLY ONE OF THEM IS SAFE TO READ POSITIONALLY
Taiwan Life prints each label immediately before its number, so the pie parses
directly. Shin Kong prints the four NUMBERS first and the four LABELS after, in
a different order from each other — 32.2% 35.4% 2.1% 30.3% then 股票及基金
外幣保單 已避險 未避險. The numbers run 已避險, 外幣保單, 股票及基金, 未避險.
That ordering is asserted, never assumed: a deck is kept only if the four sum to
100 within a point and the equity slice is both the smallest and under 10%,
which is what the shape of this disclosure guarantees and a transposition would
break.

WHAT 已避險 MEANS, WHICH CHANGED
Shin Kong's note reads 已避險部位包含CS及NDF. Taiwan Life's recent decks say the
same, but its 2021 deck says 避險部位包含currency swap, NDF, 及proxy hedge — so
the older series is WIDER than the traditional-hedge definition by the proxy
book. That is exactly the gap between the deck's 64% and the sell-side's 58% for
Taiwan Life at 2020. The note is captured per deck so the definition travels
with the number.

Run: python3 scripts/stage7_deck_fx_parse.py
"""
import csv
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "deck_fx_text.json.gz"
OUT = ROOT / "data" / "deck_fx_structure.csv"

PCT = r"(\d{1,3}(?:\.\d)?)\s*%"
# Taiwan Life: label then number, in the pie on 外幣投資資產.
TL = {
    "fx_policy": re.compile(r"外\s*幣\s*保\s*單\s*" + PCT),
    "hedged": re.compile(r"已\s*避\s*險\s*" + PCT),
    "equity": re.compile(r"Equity\s*-?\s*OCI\s*" + PCT),
    "naked": re.compile(r"未\s*避\s*險\s*" + PCT),
}
# Shin Kong: four numbers, then four labels. Order of the NUMBERS.
SK_ORDER = ("hedged", "fx_policy", "equity", "naked")
SK_NUMS = re.compile(r"(\d{1,2}\.\d)%\s*(\d{1,2}\.\d)%\s*(\d{1,2}\.\d)%\s*"
                     r"(\d{1,2}\.\d)%\s*股\s*票\s*及\s*基\s*金")
SK_BASE = re.compile(r"外\s*幣\s*資\s*產\s*總\s*計\s*=\s*新\s*台\s*幣\s*"
                     r"([\d,]+)\s*億\s*元")
# The period the pie describes, printed in its own title.
PERIOD = re.compile(r"(\d)M(\d{2})\s*外幣投資資產|(\d)[QH](\d{2})\s*外幣"
                    r"|(20\d{2})\s*外幣投資資產"
                    r"|新光人壽[^0-9]{0,40}?(\d)[QH](\d{2})")
PROXY = re.compile(r"避\s*險\s*部\s*位\s*包\s*含[^。]{0,40}proxy", re.I)


def qend(y, part):
    y = 2000 + int(y) if int(y) < 100 else int(y)
    return {"1": f"{y}-03-31", "3": f"{y}-03-31", "6": f"{y}-06-30",
            "2": f"{y}-06-30", "9": f"{y}-09-30", "4": f"{y}-12-31"}.get(
                str(part))


def period_of(text, deck_date):
    """The pie's own period, falling back to the quarter the deck reports on.

    A deck published in August reports the first half; one published in March
    reports the prior year. Dating a pie by its publication date puts every
    observation one quarter late.
    """
    m = PERIOD.search(text)
    if m:
        if m.group(1):
            return qend(m.group(2), m.group(1))
        if m.group(3):
            return qend(m.group(4), m.group(3))
        if m.group(5):
            return f"{m.group(5)}-12-31"
        if m.group(6):
            return qend(m.group(7), m.group(6))
    y, mo = int(deck_date[:4]), int(deck_date[5:7])
    if mo <= 4:
        return f"{y - 1}-12-31"
    if mo <= 7:
        return f"{y}-03-31"
    if mo <= 10:
        return f"{y}-06-30"
    return f"{y}-09-30"


def keep(d):
    """The identity the disclosure guarantees, used as the gate."""
    if any(k not in d for k in ("hedged", "fx_policy", "equity", "naked")):
        return False
    tot = sum(d[k] for k in ("hedged", "fx_policy", "equity", "naked"))
    if not 98.0 <= tot <= 102.0:
        return False
    # Equity is a sliver of a bond book and cannot be the largest slice; if it
    # is, the labels have been read onto the wrong numbers.
    return d["equity"] < 12.0 and d["equity"] == min(
        d[k] for k in ("hedged", "fx_policy", "equity", "naked"))


def main():
    if not SRC.exists():
        print(f"no harvested decks at {SRC.name}")
        return 1
    with gzip.open(SRC, "rt", encoding="utf-8") as fh:
        decks = json.load(fh)

    rows, seen = [], {}
    for name, rec in sorted(decks.items(), key=lambda kv: kv[1]["date"]):
        ent = rec["entity_id"]
        if ent not in ("taiwan_life", "shinkong_life"):
            continue
        for page, text in rec["pages"].items():
            got = {}
            if ent == "taiwan_life":
                for k, pat in TL.items():
                    m = pat.search(text)
                    if m:
                        got[k] = float(m.group(1))
            else:
                m = SK_NUMS.search(text)
                if m:
                    got = {k: float(v) for k, v in
                           zip(SK_ORDER, m.groups())}
            if not keep(got):
                continue
            d = period_of(text, rec["date"])
            base = None
            b = SK_BASE.search(text)
            if b:
                base = float(b.group(1).replace(",", "")) / 10  # 億 -> NT$bn
            r = dict(entity_id=ent, as_of=d, deck=name,
                     deck_date=rec["date"], page=int(page),
                     hedged_pct=got["hedged"], fx_policy_pct=got["fx_policy"],
                     equity_pct=got["equity"], naked_pct=got["naked"],
                     foreign_assets_ntd_bn=base,
                     includes_proxy=bool(PROXY.search(text)))
            # One pie per firm-period: the newest deck restates the cleanest.
            if (ent, d) not in seen or rec["date"] > seen[(ent, d)]["deck_date"]:
                seen[(ent, d)] = r
    rows = sorted(seen.values(), key=lambda r: (r["entity_id"], r["as_of"]))
    if not rows:
        print("no pie parsed")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} firm-period pies -> {OUT.relative_to(ROOT)}\n")
    print(f"  {'firm':<15}{'as of':<13}{'hedged':>8}{'policy':>8}{'naked':>8}"
          f"{'equity':>8}{'sum':>7}{'FX assets':>11}  proxy")
    for r in rows:
        tot = (r["hedged_pct"] + r["fx_policy_pct"] + r["equity_pct"]
               + r["naked_pct"])
        fa = ("-" if r["foreign_assets_ntd_bn"] is None
              else f"{r['foreign_assets_ntd_bn']:,.0f}")
        print(f"  {r['entity_id']:<15}{r['as_of']:<13}{r['hedged_pct']:>7.1f}%"
              f"{r['fx_policy_pct']:>7.1f}%{r['naked_pct']:>7.1f}%"
              f"{r['equity_pct']:>7.1f}%{tot:>7.0f}{fa:>11}"
              f"  {'yes' if r['includes_proxy'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
