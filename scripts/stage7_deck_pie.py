#!/usr/bin/env python3
"""The FX hedging pie for every firm that publishes one, on one common base.

WHAT THIS REPLACES
Each of the five listed insurers draws the same picture and none of them draws
it the same way, so until now each was parsed by its own script onto its own
base and the aggregate had to know which was which. This reads all five out of
the MOPS deck corpus and puts them on the base the sell-side workbook uses —
percent of TOTAL foreign investment — so the rows are directly comparable and
the aggregate needs no per-firm arithmetic at all.

  Cathay  pie is a share of the FX-RISK-BEARING portion, and the slide states
          that portion separately: "FX risk exposure 69% / Reserve for FX policy
          31%". So hedged = currency swap & NDF x 69%, and the policy bucket is
          the 31% itself. Three slices: currency swap & NDF, proxy & open,
          FVOCI & FVTPL (overlay).
  KGI     the same construction, labelled differently: currency swap & NDF,
          overseas equity, USD & other currency, over 具外匯風險資產.
  Taiwan  pie is already on foreign investment. No rescaling.
  Life
  Shin    the same, and its slide also prints the base in NT$ (外幣資產總計).
  Kong

WHY THE SLICE ORDER IS ASSERTED AND NOT ASSUMED
Cathay's slide is the dangerous one. The three percentages are drawn in wedge
order and the legend in legend order, and the two orders do not agree — FY23
prints 63/11/26 against a legend reading proxy, swap, FVOCI, while 9M25 prints
60/31/9 against the same legend. Read positionally, 9M25 puts 31% of the book
in an equity overlay that has never exceeded 17%. What IS stable across every
deck from FY17 to 1H26 is that the first number is currency swap & NDF and the
FVOCI overlay is the smaller of the remaining two, and that rule reproduces the
sell-side workbook exactly wherever the two overlap. It is applied as a rule and
the three-slice sum to 100 is the gate.

THE PAGES WITH NO TEXT LAYER
From 1Q24 to 1Q26 Cathay's pie percentages exist only as pixels. Those seven
quarters are transcribed in config/deck_pie_transcribed.tsv with the deck and
page they were read from and the checks that hold on them. Any image-only pie
page WITHOUT a transcription is named in a warning, so the next one cannot go
missing quietly the way 1Q24 did.

Run: python3 scripts/stage7_deck_pie.py
"""
import csv
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "deck_fx_text.json.gz"
SKFH_SRC = ROOT / "data" / "skfh_deck_text.json.gz"
SKFH_MAN = ROOT / "config" / "skfh_decks.tsv"
TRANS = ROOT / "config" / "deck_pie_transcribed.tsv"
OUT = ROOT / "data" / "deck_pie.csv"

NAME = {"cathay_life": "Cathay", "kgi_life": "KGI",
        "taiwan_life": "Taiwan Life", "shinkong_life": "Shin Kong"}

# ---------------------------------------------------------------- Cathay
C_PAGE = re.compile(r"外\s*幣\s*資\s*產\s*避\s*險\s*結\s*構|FX asset hedging "
                    r"structure|Currency hedging structure", re.I)
C_BASE = re.compile(r"外\s*幣\s*資\s*產\s*NT\$\s*([\d.]+)\s*兆元")
C_RISK = re.compile(r"具\s*外\s*匯\s*風\s*險\s*資\s*產\s*(\d{1,2})\s*%")
C_POL = re.compile(r"外\s*幣\s*保\s*單\s*(?:負\s*債)?\s*(\d{1,2})\s*%")
C_PER = re.compile(r"((?:FY|[1-4]Q|[12]H|9M)\s?\d{2})\s*"
                   r"(?:避\s*險\s*成\s*本|外\s*幣\s*資\s*產\s*避\s*險\s*結\s*構)")
C_DATE = re.compile(r"(20\d{2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\s*"
                    r"外\s*幣\s*資\s*產\s*避\s*險\s*結\s*構")
PCT = re.compile(r"(\d{1,3}(?:\.\d)?)\s*%")

# ---------------------------------------------------------------- KGI
K_CS = re.compile(r"Currency\s*swap\s*&\s*NDF\s*(\d{1,3}(?:\.\d)?)\s*%", re.I)
K_EQ = re.compile(r"Overseas\s*equity\s*(\d{1,3}(?:\.\d)?)\s*%", re.I)
K_OP = re.compile(r"USD\s*&\s*other\s*currency\s*(\d{1,3}(?:\.\d)?)\s*%", re.I)
K_RISK = re.compile(r"具\s*外\s*匯\s*風\s*險\s*資\s*產\s*(\d{1,2})\s*%")
K_POL = re.compile(r"外\s*幣\s*保\s*單\s*(\d{1,2})\s*%")
# "3Q 22 避險結構(%)", "2024 避險結構(%)", "1H 26 避險結構(%)"
K_PER = re.compile(r"((?:[1-4]Q|[12]H|9M)\s?\d{2}|20\d{2})\s*避\s*險\s*結\s*構")

# ------------------------------------------------- Taiwan Life / Shin Kong
T_PAT = {
    "fx_policy": re.compile(r"外\s*幣\s*保\s*單\s*(\d{1,3}(?:\.\d)?)\s*%"),
    "hedged": re.compile(r"已\s*避\s*險\s*(\d{1,3}(?:\.\d)?)\s*%"),
    "equity": re.compile(r"Equity\s*-?\s*OCI\s*(\d{1,3}(?:\.\d)?)\s*%"),
    "naked": re.compile(r"未\s*避\s*險\s*(\d{1,3}(?:\.\d)?)\s*%"),
}
# Taiwan Life redrew the slide in 2021. Before that the three shares are on the
# NTD-POLICY-BACKED part of the foreign book only, with the FX-policy share
# shown beside them as a separate 外幣保單 / 台幣保單 split:
#
#   2020-08  外幣保單 40% 台幣保單 60% | 已避險 62% Equity-OCI 14% 未避險 24%
#   2021-05  外幣保單 40% 已避險 36% Equity-OCI 8% 未避險 15%
#
# which is the same disclosure: 62 x 0.60 = 37.2 against the 36 printed two
# quarters later, and the 2021 deck proves the identity by printing BOTH — its
# 台幣保單 sub-pie of 61/13/26 times 60% reproduces its own 36/8/15 exactly.
# Read with the 2021 rule the old slide sums to 138 and is discarded, which is
# why Taiwan Life began in 2021 and not 2018.
TL_OLD_NTD = re.compile(r"台\s*幣\s*保\s*單\s*(\d{1,3})\s*%")
# Shin Kong's four slices, in the order they are DRAWN, which is not the order
# they are labelled: hedged, unhedged, equity & fund, FX policy. That order is
# asserted on four independent proofs rather than read off the legend —
#
#   * the slide states the hedge ratio "including naturally-hedged FX policy
#     position" and it is the FIRST plus the LAST every time: 70.1 + 16.6 =
#     86.7, 65.9 + 17.1 = 83.0, 61.5 + 17.8 = 79.3, 63.6 + 19.0 = 82.7;
#   * from 2026 the same slide also prints the NTD-policy-backed sub-pie, and
#     rescaling it by the complement of the last number reproduces the first
#     three exactly — 54.5 / 43.5 / 2.0 times 69.9% gives 38.1 / 30.4 / 1.4;
#   * the sell-side workbook's two overlapping quarters land on it to the
#     decimal (FY18 63.6 / 19.0 / 12.6 / 4.8, 1Q19 55.1 / 19.8 / 18.7 / 6.4);
#   * the third slice is a bond book's equity sliver, 1.0% to 6.4% across ten
#     years, and no other assignment keeps it that small.
#
# Read the old way — policy second, unhedged last — FX policy jumps from 28.8%
# to 34.4% in one quarter and back, which is what gave the error away.
S_ORDER = ("hedged", "naked", "equity", "fx_policy")
# The pie page names its equity slice, in one of three vocabularies across the
# redraws, and no other page of a results deck does. The gate is needed: a
# income statement's growth column contains runs of four percentages that sum
# to 100 by coincidence, and two of them were read as pies before this.
S_PIE = re.compile(r"股\s*票\s*及\s*基\s*金|股\s*票\s*備\s*供\s*出\s*售\s*部\s*位"
                   r"|Equity\s*&\s*fund", re.I)
S_BASE = re.compile(r"(?:外\s*幣\s*資\s*產\s*)?總\s*計\s*=\s*新\s*台\s*幣\s*"
                    r"([\d,]+(?:\.\d+)?)\s*億\s*元"
                    r"|Total\s*=\s*NT\$\s*([\d,]+(?:\.\d+)?)\s*bn")
S_PER = re.compile(r"(\d)M(\d{2})\s*外幣投資資產|(\d)[QH](\d{2})\s*外幣"
                   r"|(20\d{2})\s*外幣投資資產"
                   r"|新光人壽[^0-9]{0,40}?(\d)[QH](\d{2})")
PROXY = re.compile(r"避\s*險\s*部\s*位\s*包\s*含[^。]{0,40}proxy", re.I)


def qend(period):
    """FY24 / 1Q24 / 1H24 / 9M24 -> the quarter end it reports."""
    m = re.fullmatch(r"(FY|[1-4]Q|[12]H|9M)\s?(\d{2}|\d{4})", period.strip())
    if not m:
        return None
    pre, y = m.group(1), int(m.group(2))
    y = y + 2000 if y < 100 else y
    return {"FY": f"{y}-12-31", "1Q": f"{y}-03-31", "2Q": f"{y}-06-30",
            "3Q": f"{y}-09-30", "4Q": f"{y}-12-31", "1H": f"{y}-06-30",
            "2H": f"{y}-12-31", "9M": f"{y}-09-30"}.get(pre)


def kgi_qend(period):
    p = period.strip().replace(" ", "")
    if re.fullmatch(r"20\d{2}", p):          # a bare year on KGI's slide is FY
        return f"{p}-12-31"
    return qend(p)


def triple(text):
    """The three pie slices, as the first consecutive run summing to 100.

    Deliberately NOT positional beyond the first value. See the module note:
    the wedge order and the legend order disagree, and the only thing stable
    across nine years of these slides is that the run sums to 100 and the FVOCI
    overlay is the smaller of the two that follow currency swap & NDF.
    """
    stripped = C_RISK.sub(" ", C_POL.sub(" ", text))
    vals = [float(v) for v in PCT.findall(stripped)]
    for a, b, c in zip(vals, vals[1:], vals[2:]):
        if not all(1.0 <= v <= 90.0 for v in (a, b, c)):
            continue
        if 98.5 <= a + b + c <= 101.5:
            fvoci, proxy = min(b, c), max(b, c)
            return a, proxy, fvoci
    return None


def quad(text):
    """Shin Kong's four slices: the first consecutive run summing to 100.

    Positional only in the sense that the run's ORDER is fixed (see S_ORDER);
    which four numbers form the run is found, not assumed, because the slide
    has been redrawn three times in ten years and the numbers sit variously
    before the legend, after it, and interleaved with the page number. The
    same page also carries the currency-swap/NDF split and a four-year cost
    series, neither of which sums to 100, and from 2026 an NTD-policy sub-pie
    of three, which is why the first qualifying run is the right one.
    """
    if not S_PIE.search(text):
        return {}
    vals = [float(v) for v in PCT.findall(text)]
    for a, b, c, d in zip(vals, vals[1:], vals[2:], vals[3:]):
        if not all(0.1 <= v <= 90.0 for v in (a, b, c, d)):
            continue
        if 98.5 <= a + b + c + d <= 101.5 and c == min(a, b, c, d):
            return dict(zip(S_ORDER, (a, b, c, d)))
    return {}


def s_base(text):
    """Shin Kong prints the pie's base in NT$. Returns NT$ bn."""
    m = S_BASE.search(text)
    if not m:
        return None
    if m.group(1):                                   # 億元, hundred millions
        return float(m.group(1).replace(",", "")) / 10.0
    return float(m.group(2).replace(",", ""))        # already NT$ bn


def harmonise(cs_ndf, proxy, fvoci, risk):
    """A pie drawn on the FX-risk-bearing base, restated on foreign investment.

    The policy bucket is the complement of the risk-bearing share, which is
    what makes the four add to 100 on the common base.
    """
    f = risk / 100.0
    return {"hedged_pct": round(cs_ndf * f, 2),
            "fx_policy_pct": round(100.0 - risk, 2),
            "naked_pct": round(proxy * f, 2),
            "equity_pct": round(fvoci * f, 2)}


def keep(d):
    tot = sum(d[k] for k in ("hedged_pct", "fx_policy_pct", "naked_pct",
                             "equity_pct"))
    return 98.0 <= tot <= 102.0 and d["equity_pct"] < 20.0


def skfh():
    """Shin Kong Life before the Taishin merger, from the IR-host decks.

    A separate corpus because MOPS has none of it: there are no
    investor-conference filings under code 2888, and 2887's decks describe
    Taishin Life until July 2025 (4.61, 4.67). These fourteen files come from
    the vendor's own file store, enumerated through the archive because the
    index is unreachable (4.70), and they carry the same four-slice pie the
    later decks do — the slide has been redrawn but never renamed.

    The as-of date comes from config/skfh_decks.tsv, not from the page. It
    cannot be read off the filename: "SKFH Company Overview May 2019" carries
    the FY18 pie, and January 2019's carries 9M18. What the page does state is
    the hedging cost for the period it reports, which is the evidence recorded
    beside each date in the manifest.
    """
    if not (SKFH_SRC.exists() and SKFH_MAN.exists()):
        return {}
    when = {}
    for line in SKFH_MAN.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith(("#", "conf_id\t")):
            continue
        cid, _label, as_of, _ev, _url, _ts = line.split("\t")
        if as_of.strip():
            when[int(cid)] = as_of.strip()
    with gzip.open(SKFH_SRC, "rt", encoding="utf-8") as fh:
        store = json.load(fh)
    out = {}
    for name, rec in sorted(store.items(), key=lambda kv: kv[1]["conf_id"]):
        as_of = when.get(rec["conf_id"])
        if not as_of:
            continue
        for page, text in sorted(rec["pages"].items(), key=lambda x: int(x[0])):
            pie = quad(text)
            if len(pie) != 4:
                continue
            base = s_base(text)
            row = {"hedged_pct": pie["hedged"], "fx_policy_pct": pie["fx_policy"],
                   "naked_pct": pie["naked"], "equity_pct": pie["equity"],
                   "basis": "foreign_investment", "cs_ndf_pct_of_risk": None,
                   "fx_risk_pct": None, "foreign_assets_ntd_bn": base,
                   "entity_id": "shinkong_life", "as_of": as_of,
                   "deck": name, "deck_date": as_of, "page": int(page),
                   "source": "ir_host", "includes_proxy": False}
            if keep(row):
                out.setdefault(("shinkong_life", as_of), row)
    return out


def transcribed():
    """Cathay's image-only pies, and the decks they were read from."""
    if not TRANS.exists():
        return {}, set()
    out, decks = {}, set()
    for line in TRANS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith(
                "entity_id\t"):
            continue
        (ent, per, cs, proxy, fvoci, risk, pol, base, deck,
         page) = line.split("\t")
        d = qend(per)
        row = harmonise(float(cs), float(proxy), float(fvoci), float(risk))
        row.update(entity_id=ent, as_of=d, basis="fx_risk_base",
                   cs_ndf_pct_of_risk=float(cs), fx_risk_pct=float(risk),
                   foreign_assets_ntd_bn=float(base) * 1000,
                   deck=deck, deck_date=deck, page=int(page),
                   source="transcribed", includes_proxy=False)
        out[(ent, d)] = row
        decks.add((ent, d))
    return out, decks


def main():
    if not SRC.exists():
        print(f"no harvested decks at {SRC.name}")
        return 1
    with gzip.open(SRC, "rt", encoding="utf-8") as fh:
        decks = json.load(fh)

    rows, blank = {}, []
    for name, rec in sorted(decks.items(), key=lambda kv: kv[1]["date"]):
        ent, ddate = rec["entity_id"], rec["date"]
        if ent not in NAME:
            continue
        for page, text in rec["pages"].items():
            got = None
            if ent == "cathay_life":
                if not C_PAGE.search(text):
                    continue
                risk, pol = C_RISK.search(text), C_POL.search(text)
                if not (risk and pol):
                    continue
                per, dt = C_PER.search(text), C_DATE.search(text)
                as_of = (qend(per.group(1)) if per else
                         (f"{dt.group(1)}-{int(dt.group(2)):02d}-"
                          f"{int(dt.group(3)):02d}" if dt else None))
                if not as_of:
                    continue
                t = triple(text)
                if not t:
                    # the pie is an image; the transcription file covers it
                    blank.append((ent, as_of, name, page))
                    continue
                cs, proxy, fvoci = t
                got = harmonise(cs, proxy, fvoci, float(risk.group(1)))
                b = C_BASE.search(text)
                got.update(basis="fx_risk_base", cs_ndf_pct_of_risk=cs,
                           fx_risk_pct=float(risk.group(1)),
                           foreign_assets_ntd_bn=(float(b.group(1)) * 1000
                                                  if b else None))
            elif ent == "kgi_life":
                cs, eq, op = (K_CS.search(text), K_EQ.search(text),
                              K_OP.search(text))
                risk, per = K_RISK.search(text), K_PER.search(text)
                if not (cs and eq and op and risk and per):
                    continue
                as_of = kgi_qend(per.group(1))
                if not as_of:
                    continue
                cs, eq, op = (float(cs.group(1)), float(eq.group(1)),
                              float(op.group(1)))
                if not 98.5 <= cs + eq + op <= 101.5:
                    continue
                got = harmonise(cs, op, eq, float(risk.group(1)))
                got.update(basis="fx_risk_base", cs_ndf_pct_of_risk=cs,
                           fx_risk_pct=float(risk.group(1)),
                           foreign_assets_ntd_bn=None)
            else:
                pie = {}
                if ent == "taiwan_life":
                    for k, pat in T_PAT.items():
                        m = pat.search(text)
                        if m:
                            pie[k] = float(m.group(1))
                    ntd = TL_OLD_NTD.search(text)
                    if len(pie) == 4 and ntd:
                        # the pre-2021 slide: rescale the three onto the whole
                        # foreign book and take 外幣保單 as the policy slice
                        f = float(ntd.group(1)) / 100.0
                        three = pie["hedged"] + pie["equity"] + pie["naked"]
                        if (abs(three - 100.0) <= 1.5
                                and abs(pie["fx_policy"] + float(ntd.group(1))
                                        - 100.0) <= 1.0):
                            pie = {"hedged": round(pie["hedged"] * f, 1),
                                   "equity": round(pie["equity"] * f, 1),
                                   "naked": round(pie["naked"] * f, 1),
                                   "fx_policy": pie["fx_policy"]}
                        else:
                            pie = {}
                else:
                    pie = quad(text)
                if len(pie) != 4:
                    continue
                # The equity sliver of a bond book is the smallest slice. The
                # SIZE cap is only meaningful for Shin Kong, whose four numbers
                # are read positionally and so could be transposed; Taiwan Life
                # labels each slice, and capping it at 12 there silently dropped
                # 1Q25, where Equity-OCI is exactly 12.
                cap = 12.0 if ent == "shinkong_life" else 20.0
                if pie["equity"] >= cap or pie["equity"] != min(pie.values()):
                    continue
                as_of = period_of(text, ddate)
                got = {"hedged_pct": pie["hedged"],
                       "fx_policy_pct": pie["fx_policy"],
                       "naked_pct": pie["naked"], "equity_pct": pie["equity"],
                       "basis": "foreign_investment",
                       "cs_ndf_pct_of_risk": None, "fx_risk_pct": None,
                       "foreign_assets_ntd_bn": s_base(text)}
            if not got or not keep(got):
                continue
            got.update(entity_id=ent, as_of=as_of, deck=name, deck_date=ddate,
                       page=int(page), source="text",
                       includes_proxy=bool(PROXY.search(text)))
            k = (ent, as_of)
            # One pie per firm-period. The deck that REPORTS that period is
            # preferred over a later deck showing it again on a recap slide,
            # and among equals the newest restatement wins.
            old = rows.get(k)
            if old is None or (ddate[:4] + ddate[5:7]) > (old["deck_date"][:4]
                                                          + old["deck_date"][5:7]):
                rows[k] = got

    tr, _ = transcribed()
    for k, v in tr.items():
        rows.setdefault(k, v)          # text always outranks a transcription
    for k, v in skfh().items():
        rows.setdefault(k, v)          # MOPS outranks the IR host where both

    missing = sorted({(e, d) for e, d, _, _ in blank} - set(rows))
    out = sorted(rows.values(), key=lambda r: (r["entity_id"], r["as_of"]))
    cols = ["entity_id", "as_of", "basis", "hedged_pct", "fx_policy_pct",
            "naked_pct", "equity_pct", "cs_ndf_pct_of_risk", "fx_risk_pct",
            "foreign_assets_ntd_bn", "deck", "deck_date", "page", "source",
            "includes_proxy"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({c: r.get(c) for c in cols})

    print(f"{len(out)} firm-period pies -> {OUT.relative_to(ROOT)}\n")
    print(f"  {'firm':<12}{'as of':<12}{'hedged':>8}{'policy':>8}{'naked':>8}"
          f"{'equity':>8}{'sum':>6}{'FX assets':>11}  src")
    for r in out:
        tot = (r["hedged_pct"] + r["fx_policy_pct"] + r["naked_pct"]
               + r["equity_pct"])
        fa = ("-" if r["foreign_assets_ntd_bn"] is None
              else f"{r['foreign_assets_ntd_bn']:,.0f}")
        print(f"  {NAME[r['entity_id']]:<12}{r['as_of']:<12}"
              f"{r['hedged_pct']:>7.1f}%{r['fx_policy_pct']:>7.1f}%"
              f"{r['naked_pct']:>7.1f}%{r['equity_pct']:>7.1f}%{tot:>6.0f}"
              f"{fa:>11}  {r['source']}")
    per = {}
    for r in out:
        per[r["entity_id"]] = per.get(r["entity_id"], 0) + 1
    print()
    for e, n in sorted(per.items()):
        ds = [r["as_of"] for r in out if r["entity_id"] == e]
        print(f"  {NAME[e]:<12}{n:>3}  {min(ds)} .. {max(ds)}")
    if missing:
        print("\n  IMAGE-ONLY pie pages with no transcription — add them to "
              f"{TRANS.relative_to(ROOT)}:")
        for e, d in missing:
            src = [(f, p) for x, y, f, p in blank if (x, y) == (e, d)]
            print(f"    {NAME[e]:<12}{d}  {src[0][0]} p{src[0][1]}")
    return 0


def period_of(text, deck_date):
    """Taiwan Life / Shin Kong: the pie's own period, else the deck's quarter.

    A deck published in August reports the first half; one published in March
    reports the prior year. Dating a pie by publication puts it a quarter late.
    """
    m = S_PER.search(text)
    if m:
        if m.group(1):
            return _q(m.group(2), m.group(1))
        if m.group(3):
            return _q(m.group(4), m.group(3))
        if m.group(5):
            return f"{m.group(5)}-12-31"
        if m.group(6):
            return _q(m.group(7), m.group(6))
    y, mo = int(deck_date[:4]), int(deck_date[5:7])
    if mo <= 4:
        return f"{y - 1}-12-31"
    if mo <= 7:
        return f"{y}-03-31"
    if mo <= 10:
        return f"{y}-06-30"
    return f"{y}-09-30"


def _q(y, part):
    y = 2000 + int(y) if int(y) < 100 else int(y)
    return {"1": f"{y}-03-31", "3": f"{y}-03-31", "6": f"{y}-06-30",
            "2": f"{y}-06-30", "9": f"{y}-09-30", "4": f"{y}-12-31"}.get(
                str(part))


if __name__ == "__main__":
    sys.exit(main())
