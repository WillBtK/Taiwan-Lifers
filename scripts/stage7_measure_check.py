#!/usr/bin/env python3
"""How much does it matter that the aggregate mixes two measures of "hedged"?

The sector series is built from whatever each firm discloses, and that is not
one thing. Four insurers draw a pie with a 已避險 slice; five report a
derivative notional in their statutory accounts and no pie. The aggregate
weights them together as though the two were interchangeable.

For one firm they are. Shin Kong publishes both, and its notional over foreign
assets reproduces its own slide — 35.5 against 34.7, 38.8 against 38.1, 32.3
against 32.2. For the other firm that publishes both they are not: Taiwan
Life's gross notional runs about twice its slide, 78% against 37% at 3Q24, and
its table parses exactly against the page (4.72). One agrees and one does not,
and the five firms that enter on notionals alone publish nothing to check
against.

So this runs the aggregate twice — once as built, once restricted to the
pie-publishing firms — and prints the difference. Neither is "the answer": the
deck-only series is one measure consistently applied over a third of the
sector, the mixed one is seven eighths of the sector on two measures. What the
comparison establishes is how much of the level, and how much of the FALL, is
riding on the assumption that they are the same thing.

Run: python3 scripts/stage7_measure_check.py
"""
import collections
import csv
import importlib.util
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGG = ROOT / "scripts" / "stage6_aggregate_hedge_ratio.py"
NOTIONAL = ROOT / "data" / "firm_hedge_notional.csv"
DECKPIE = ROOT / "data" / "deck_pie.csv"
OUT = ROOT / "data" / "aggregate_hedge_ratio.csv"
DECK_OUT = ROOT / "data" / "aggregate_hedge_ratio_deck_only.csv"
REPORT = ROOT / "reports" / "measure_comparison.txt"


def run(source=None):
    env = dict(os.environ)
    if source:
        env["TLFX_SOURCE"] = source
    else:
        env.pop("TLFX_SOURCE", None)
    r = subprocess.run([sys.executable, str(AGG)], env=env,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"aggregate failed ({source or 'mixed'}):\n{r.stderr}")
    return {row["as_of"]: row for row in
            csv.DictReader(open(OUT, newline="", encoding="utf-8"))}


def paired():
    """Every firm-quarter where BOTH measures exist, side by side.

    Two firms publish a slide and a statutory notional at the same dates, which
    is the only direct evidence there is about whether the two measure the same
    thing. Sixteen comparisons, and the notional is at or above the slide in
    every one of them — by 2% for Shin Kong and by as much as 150% for Taiwan
    Life. A one-sided relationship across sixteen observations is not noise: the
    notional is an UPPER BOUND on the hedge ratio, and the gap is however much
    of a firm's currency-contract book is doing something other than hedging
    the foreign bond portfolio.
    """
    _s = importlib.util.spec_from_file_location("ag", AGG)
    ag = importlib.util.module_from_spec(_s)
    _s.loader.exec_module(ag)
    _f = importlib.util.spec_from_file_location(
        "fx", ROOT / "scripts" / "stage5_twd_rates.py")
    fx = importlib.util.module_from_spec(_f)
    _f.loader.exec_module(fx)
    tbl = fx.load()
    fi, sec = ag.firm_bn(), ag.sector_bn()
    share = {e: {m: v / sec[m] for m, v in d.items() if m in sec}
             for e, d in fi.items()}

    def book(e, d):
        sh = ag.interp(share.get(e, {}), d)
        lvl = sec.get(d[:7]) or ag.interp(sec, d)
        return None if (sh is None or lvl is None) else sh * lvl

    tot = collections.defaultdict(float)
    for r in csv.DictReader(open(NOTIONAL, newline="", encoding="utf-8")):
        if r["traditional"] != "True":
            continue
        v = (float(r["notional_ntd_k"]) if r["notional_ntd_k"] else
             fx.convert(float(r["notional_ccy_k"]), r.get("currency"),
                        r["as_of"], tbl) if r["notional_ccy_k"] else None)
        if v:
            tot[(r["entity_id"], r["as_of"], r["filing"])] += v
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for (e, d, _f2), v in tot.items():
        per[e][d].append(v)
    slide = {(r["entity_id"], r["as_of"]): float(r["hedged_pct"])
             for r in csv.DictReader(open(DECKPIE, newline="",
                                          encoding="utf-8"))}
    out = []
    for e in sorted(per):
        for d in sorted(per[e]):
            sl, bk = slide.get((e, d)), book(e, d)
            if sl is None or not bk:
                continue
            out.append((ag.NAME.get(e, e), d, max(per[e][d]) / 1e6 / bk * 100,
                        sl))
    return out


def num(row, col):
    return float(row[col]) if row and row.get(col) else None


def main():
    deck = run("deck")
    DECK_OUT.write_text(OUT.read_text(encoding="utf-8"), encoding="utf-8")
    mixed = run()                        # last, so the canonical file is the
    lines = []                           # mixed one when this exits

    def say(s=""):
        print(s)
        lines.append(s)

    say("Two measures of 'hedged', weighted together.\n")
    say(f"  {'quarter':<12}{'mixed':>8}{'cov':>6}{'n':>4}"
        f"{'deck-only':>11}{'cov':>6}{'n':>4}{'difference':>12}")
    diffs = []
    for q in sorted(set(mixed) | set(deck)):
        m, d = mixed.get(q), deck.get(q)
        mv, dv = num(m, "hedge_ratio"), num(d, "hedge_ratio")
        mc, dc = num(m, "coverage_share"), num(d, "coverage_share")
        if mv is not None and dv is not None:
            diffs.append(dv - mv)
        say(f"  {q:<12}"
            f"{('-' if mv is None else f'{mv * 100:.1f}%'):>8}"
            f"{('-' if mc is None else f'{mc * 100:.0f}%'):>6}"
            f"{(m or {}).get('n_firms', '-'):>4}"
            f"{('-' if dv is None else f'{dv * 100:.1f}%'):>11}"
            f"{('-' if dc is None else f'{dc * 100:.0f}%'):>6}"
            f"{(d or {}).get('n_firms', '-'):>4}"
            f"{('' if None in (mv, dv) else f'{(dv - mv) * 100:+.1f}pp'):>12}")
    if diffs:
        say()
        say(f"  mean {statistics.mean(diffs) * 100:+.1f}pp over {len(diffs)} "
            f"quarters, from {min(diffs) * 100:+.1f} to "
            f"{max(diffs) * 100:+.1f}")
        qs = sorted(mixed)
        m0, m1 = num(mixed[qs[0]], "hedge_ratio"), num(mixed[qs[-1]],
                                                       "hedge_ratio")
        ds = sorted(deck)
        d0, d1 = num(deck[ds[0]], "hedge_ratio"), num(deck[ds[-1]],
                                                      "hedge_ratio")
        say()
        say(f"  peak to trough, mixed:     {m0 * 100:.1f}% -> {m1 * 100:.1f}%"
            f"   ({(m1 - m0) * 100:+.1f}pp)")
        say(f"  peak to trough, deck-only: {d0 * 100:.1f}% -> {d1 * 100:.1f}%"
            f"   ({(d1 - d0) * 100:+.1f}pp)")
        say()
        say("  The gap is widest where the deck-publishing firms are thinnest.")
        say("  Read the difference as the size of the open question in 4.72,")
        say("  not as an error bar: neither series is known to be the wrong one.")
    rows = paired()
    if rows:
        say()
        say("Every firm-quarter where a company publishes BOTH measures.\n")
        say(f"  {'company':<14}{'quarter':<12}{'from accounts':>14}"
            f"{'from slide':>12}{'ratio':>8}")
        for name, d, a, sl in rows:
            say(f"  {name:<14}{d:<12}{a:>13.1f}%{sl:>11.1f}%{a / sl:>8.2f}")
        n = sum(1 for _n, _d, a, sl in rows if a >= sl)
        say()
        say(f"  The accounts figure is at or above the slide in {n} of "
            f"{len(rows)} comparisons.")
        say("  It is a CEILING on the hedge ratio, not an estimate of it: the")
        say("  gap is whatever part of the currency-contract book is not")
        say("  hedging the foreign bond portfolio. 2% of it for Shin Kong,")
        say("  as much as 150% for Taiwan Life.")
        say()
        say("  So the mixed series is an upper bound wherever accounts-only")
        say("  firms carry weight, and the truth sits between the two lines,")
        say("  nearer the deck one.")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n-> {DECK_OUT.relative_to(ROOT)}")
    print(f"-> {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
