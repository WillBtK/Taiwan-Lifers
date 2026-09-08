#!/usr/bin/env python3
"""Interest-rate sensitivity, all ten insurers, from the captured note text.

WHY THIS AND NOT THE HEDGE NOTIONAL
The notional panel says how much FX hedging the sector runs. It says nothing
about duration, which is the exposure that actually makes these firms a bid for
long USD credit. The statutory market-risk note carries that directly: the
change in pre-tax profit and in equity for a stated parallel move in the yield
curve. Divided by the shock, it is a DV01 on the investment book — the one
disclosed quantity in this project that measures duration rather than currency.

It is also the only firm-level series that includes Cathay. Cathay discloses no
economic hedge notional at all (decision 4.56), so the notional panel structurally
cannot cover the largest insurer; its rate sensitivity is disclosed every period.

WHY THE HEADER IS PARSED AND NOT ASSUMED
Seven layouts, and the column ORDER differs between them in ways no default
survives:

  Fubon        金融資產 | 保險合約負債 | 淨額, each 損益 then 權益
  Taiwan Life  the same three subjects, each 權益 then 損益 — reversed
  KGI/Shinkong/TransGlobe   損益變動 | 權益變動, each 淨保險合約負債 then 投資資產
                            — the nesting itself is inverted, measure outside
  Bank Taiwan  two columns only, 權益 then 損益, and stated in 億元 not 仟元
  Mercuries    稅前利潤 | 其他綜合損益, each split by PERIOD, both periods in
               the same row
  Cathay       the eight-column IFRS 17 split (handled by the existing parser)
  Hontai       no table at all: the figures are in a prose sentence

Assuming any one of these silently transposes the others — an asset DV01 read
off the liability column is the same order of magnitude, the same sign much of
the time, and wrong. So the header is tokenised and the axes recovered from it:
whichever of {subject, period} repeats is the inner axis, and the measures
sit on the other. Where the layout carries a 淨額 column the filing checks
itself — asset + liability must equal net — and a row that fails is dropped
rather than published.

SIGNS
Normalised to a +1bp parallel RISE. A down-shock row is negated. Rates up, bond
prices down, so a long-duration asset book shows a NEGATIVE equity number; a
liability discounted at those rates shows a positive one. Convexity means the
up and down rows are not exact mirrors, which is real and is reported, not
smoothed.

Run: python3 scripts/stage6_rate_sensitivity.py
"""
import csv
import gzip
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTE_TEXT = ROOT / "data" / "mops_note_text.json.gz"
OUT = ROOT / "data" / "firm_rate_sensitivity.csv"

_spec = importlib.util.spec_from_file_location(
    "s6", ROOT / "scripts" / "stage6_firm_sensitivity.py")
s6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s6)


# ---------------------------------------------------------------- numbers
# Decimal-aware, unlike the notional parser's: Bank Taiwan states this table in
# 億元 to two places (74.51), and an integer-only pattern reads that as 74 then
# 51 — two plausible columns out of one number.
NUM = re.compile(r"\(\s*\$?\s*(\d[\d,]*(?:\.\d+)?)\s*\)"
                 r"|\$\s*\(\s*(\d[\d,]*(?:\.\d+)?)\s*\)"
                 r"|\$?\s*(-)(?![\d,.])"
                 r"|\$?\s*(\d[\d,]*(?:\.\d+)?)")


def numbers(seg, n):
    out = []
    for m in NUM.finditer(seg):
        p1, p2, nil, pos = m.groups()
        if nil is not None:
            out.append(0.0)
        elif p1 is not None:
            out.append(-float(p1.replace(",", "")))
        elif p2 is not None:
            out.append(-float(p2.replace(",", "")))
        else:
            out.append(float(pos.replace(",", "")))
        if len(out) == n:
            break
    return out


# ---------------------------------------------------------------- patterns
def sp(s):
    """Allow whitespace between every character.

    The PDF wraps mid-word and flattening leaves '平移上 升1bp'. Permitting \\s*
    only between terms and not inside them is why the Cathay rate row matched
    nothing while its FX row, which happened not to wrap, matched fine.
    """
    return r"\s*".join(re.escape(c) for c in s)


def alt(*words):
    return "(?:" + "|".join(sp(w) for w in words) + ")"


# The risk factor a row belongs to. A shock token alone is not enough: '+1%'
# appears under 權益風險 and 匯率風險 in the same table, and reading those as
# rate rows would put an equity beta in the duration series.
RISK = re.compile("(?P<rate>" + alt("利率風險", "利率敏感度", "利率風險敏感度")
                  + ")|(?P<other>"
                  + alt("匯率風險", "外匯風險", "權益風險", "價格風險",
                        "權益證券價格風險", "證券價格風險", "股票價格風險",
                        "匯率風險敏感度", "保險風險") + ")")

# Two ways a shock is written. Worded: 利率曲線上升 1bp. Signed: +1BP, -0.01%.
CURVE = alt("殖利率曲線", "主要利率曲線", "利率曲線")
UP = alt("上移", "上升", "增加", "上漲")
DOWN = alt("下移", "下跌", "下降", "減少")
UNIT = r"(?:BPS|bps|BP|bp|" + alt("基本點", "基點", "個基點") + r"|%)"
# The currency is inside the row label, not a column: 殖利率曲線(美元)平行上移
# 50BPS. Fubon reports the curve shock separately for 美元, 台幣 and 其他, and
# reading that table without the label collapses three currencies into one
# figure — which is what "total" meant when this parser first ran, and it was
# the USD row. A USD-specific DV01 is the single most useful number here, so it
# is captured rather than aggregated away.
SHOCK_WORDED = re.compile(
    CURVE + r"\s*(?:[（(]\s*(?P<ccy>[^）)0-9]{1,8}?)\s*[）)])?"
    r"[^0-9%（(或及與、]{0,20}?(?P<up>" + UP + r"|" + DOWN
    + r")\s*(?P<mag>\d+(?:\.\d+)?)\s*(?P<unit>" + UNIT + ")")
# An unmapped label must NOT fall through to "all": Cathay's 英鎊 and 港幣 rows
# did, and three different currencies then collided on one key, so the panel
# kept whichever the dedupe saw first and reported a GBP figure as the
# aggregate. Anything unrecognised keeps its own label instead.
CCY = {"美元": "USD", "美金": "USD", "台幣": "TWD", "新台幣": "TWD",
       "新臺幣": "TWD", "歐元": "EUR", "澳幣": "AUD", "澳元": "AUD",
       "日圓": "JPY", "日幣": "JPY", "日元": "JPY", "人民幣": "CNY",
       "英鎊": "GBP", "港幣": "HKD", "加幣": "CAD", "加元": "CAD",
       "紐幣": "NZD", "紐元": "NZD", "新加坡幣": "SGD", "星幣": "SGD",
       "南非幣": "ZAR", "韓圜": "KRW", "韓元": "KRW", "泰銖": "THB",
       "其他": "other", "各幣別": "all", "所有幣別": "all",
       "所有外幣": "all", "全部幣別": "all"}
# 或/及/與 are excluded from the gap deliberately. Mercuries introduces its
# table in a sentence -- "主要利率曲線上升或下降100BPS 對金融資產稅前利潤...
# 之影響" -- and a gap that may contain 或 matches "下降100BPS" inside it. That
# prose sentence then became the table's first data row, consumed the header,
# and cost the firm its entire series.
SHOCK_SIGNED = re.compile(r"(?P<sign>[+\-−])\s*(?P<mag>\d+(?:\.\d+)?)\s*"
                          r"(?P<unit>" + UNIT + ")")

# Column axes.
MEAS = [("pnl", alt("稅前損益變動", "對稅前利潤之影響", "稅前損益", "損益變動",
                    "稅前利潤", "損益")),
        ("equity", alt("稅前權益變動", "稅前權益", "權益變動", "權益")),
        ("oci", alt("其他綜合損益之影響", "其他綜合損益"))]
SUBJ = [("liability", alt("淨保險合約負債", "保險合約負債")),
        ("asset", alt("投資資產", "金融資產")),
        ("net", alt("淨額", "影響淨額"))]
# oci before pnl/equity so 其他綜合損益 is not eaten by the bare 損益 alternative
AXIS = re.compile("|".join(
    [f"(?P<m_{k}>{v})" for k, v in [MEAS[2], MEAS[0], MEAS[1]]]
    + [f"(?P<s_{k}>{v})" for k, v in SUBJ]))
DOT = re.compile(r"\b(9\d|1[0-2]\d)\.(0?[1-9]|1[0-2])\.(0?[1-9]|[12]\d|3[01])\b")
CJK = re.compile(r"(9\d|1[0-2]\d)\s*年\s*(0?[1-9]|1[0-2])\s*月\s*"
                 r"(0?[1-9]|[12]\d|3[01])\s*日")
# An interim table is headed by a RANGE — 115年1月1日至3月31日 — and the balance
# it reports is the one at the END of it. Reading the range's first date put
# every Cathay observation on 1 January of the wrong year: eight quarters that
# looked like a plausible annual series and were each two to six months
# mis-dated, which is worse than a gap because it lines up against nothing.
RANGE = re.compile(r"(9\d|1[0-2]\d)\s*年\s*(?:0?[1-9]|1[0-2])\s*月\s*"
                   r"(?:0?[1-9]|[12]\d|3[01])\s*日\s*至\s*"
                   r"(?:(9\d|1[0-2]\d)\s*年\s*)?"
                   r"(0?[1-9]|1[0-2])\s*月\s*(0?[1-9]|[12]\d|3[01])\s*日")
# 單位:新臺幣億元 sits immediately above the table it governs and overrides the
# note's blanket 仟元. One 億 = 100,000 thousands.
UNITDECL = re.compile(alt("單位") + r"\s*[:：]?\s*" + alt("新臺幣", "新台幣")
                      + r"?\s*(" + alt("億元", "百萬元", "仟元", "千元") + ")")
SCALE = {"億元": 1e5, "百萬元": 1e3, "仟元": 1.0, "千元": 1.0}
# Fubon prints the SAME table twice: once for 本公司 and once for
# 子公司-富邦現代生命保險, its Korean subsidiary, whose book is roughly a
# fortieth the size. The subsidiary's table carries comparative periods the
# parent's page does not, so with no scope test the panel silently took the
# Korean figure for four quarters of 2019-2020 — a 40x understatement that
# looked like nothing more than a quiet period.
SCOPE = re.compile(alt("敏感度分析表") + r"\s*(?:[（(]\s*([^）)]{1,20}?)\s*[）)])?")


def roc(m):
    return f"{1911 + int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def dates_in(seg):
    out, spans = [], []
    for m in RANGE.finditer(seg):
        y = int(m.group(2) or m.group(1))
        out.append((m.start(), f"{1911 + y}-{int(m.group(3)):02d}-"
                               f"{int(m.group(4)):02d}"))
        spans.append((m.start(), m.end()))
    for pat in (DOT, CJK):
        for m in pat.finditer(seg):
            if not any(a <= m.start() < b for a, b in spans):
                out.append((m.start(), roc(m)))
    return sorted(out)


# ---------------------------------------------------------------- schema
def header_of(flat, start, prev_end):
    """The header block governing the row at `start`.

    Two boundaries, and both are load-bearing. The block begins at the LAST date
    marker before the row, because the narrative above the table talks about the
    same things the columns are named after — TransGlobe's introduction says
    "影響損益及權益" and "保險合約負債及對應之投資資產", which tokenises to a
    complete but entirely fictional column schema. And every risk-factor label
    inside the block is blanked, because 權 益 風 險 is a ROW label whose first
    two characters are also a column name; KGI's equity row sitting above its
    rate row added a third measure token and the schema collapsed.

    Returns (block, raw). The date truncation is wrong for the one layout whose
    columns ARE dates — Mercuries prints 115.6.30 114.6.30 115.6.30 114.6.30 as
    the header, and cutting at the last of them leaves one column of four — so
    the untruncated block is returned alongside for that reader.
    """
    lo = max(prev_end, start - 1400)
    raw = RISK.sub(" ", flat[lo:start])
    # The narrative that introduces a table names the same things its columns
    # are named after. Mercuries' lead-in says "對金融資產稅前利潤或其他綜合
    # 損益之影響", which tokenises to one asset and two measures and made the
    # column count disagree with itself. A full stop ends the prose and the
    # header follows it.
    cut = raw.rfind("。")
    if cut >= 0:
        raw = raw[cut + 1:]
    ds = dates_in(raw)
    return (raw[ds[-1][0]:] if ds else raw), raw


def column_schema(header):
    """Recover the column order from the header text.

    Returns a list of (subject, measure) pairs, or None when the header does not
    describe a table this reader understands. The rule is structural rather than
    a lookup: the axis whose labels REPEAT is the inner one, because a table
    prints the outer heading once and the inner headings once per outer column.
    """
    toks = []
    for m in AXIS.finditer(header):
        for k, v in m.groupdict().items():
            if v:
                toks.append(("m" if k.startswith("m_") else "s", k[2:]))
                break
    meas = [t[1] for t in toks if t[0] == "m"]
    subj = [t[1] for t in toks if t[0] == "s"]
    if not meas:
        return None
    # Distinct labels, in the order first seen.
    dm = list(dict.fromkeys(meas))
    ds = list(dict.fromkeys(subj))
    if not ds:
        # Two-column shape: measures only, applying to the company as a whole.
        return [("total", m) for m in dm] if len(dm) == len(meas) else None
    if len(subj) == len(ds) and len(meas) > len(dm):
        # subjects once each, measures repeated -> subject is the outer axis
        inner = meas[:len(meas) // max(len(ds), 1)] or dm
        return [(s, m) for s in ds for m in inner]
    if len(meas) == len(dm) and len(subj) > len(ds):
        # measures once each, subjects repeated -> measure is the outer axis
        inner = subj[:len(subj) // max(len(dm), 1)] or ds
        return [(s, m) for m in dm for s in inner]
    return None


def period_schema(header):
    """Mercuries: the inner axis is TIME, not a balance-sheet subject.

    Its table prints 稅前利潤 and 其他綜合損益, each split into the current and
    the comparative period, so one row carries two dates. Reading it with the
    ordinary reader would attribute the comparative figure to the current
    period — a 4x level error on the OCI column at 2026-06.
    """
    toks = []
    for m in AXIS.finditer(header):
        for k, v in m.groupdict().items():
            if v and k.startswith("m_"):
                toks.append(k[2:])
                break
    dm = list(dict.fromkeys(toks))
    ds = [d for _, d in dates_in(header)]
    dd = list(dict.fromkeys(ds))
    if len(dm) < 2 or len(dd) < 2 or len(toks) != len(dm) or len(ds) <= len(dd):
        return None
    inner = dd[:len(ds) // len(dm)]
    return [(d, m) for m in dm for d in inner]


# ---------------------------------------------------------------- rows
def shocks(flat):
    """Every rate shock on the page, as (position, end, bp, label).

    bp is signed: a +1bp rise is +1, a 50bp fall is -50. Rows whose nearest
    preceding risk label is NOT the rate factor are discarded here — that is
    what keeps 權益風險 +1% out of a duration series.
    """
    labels = [(m.start(), "rate" if m.group("rate") else "other")
              for m in RISK.finditer(flat)]

    def is_rate(pos):
        prev = [k for p, k in labels if p < pos]
        return bool(prev) and prev[-1] == "rate"

    out = []
    for m in SHOCK_WORDED.finditer(flat):
        u = re.sub(r"\s", "", m.group("unit"))
        bp = float(m.group("mag")) * (100.0 if u == "%" else 1.0)
        if re.fullmatch(DOWN, m.group("up")):
            bp = -bp
        c = re.sub(r"\s", "", m.group("ccy") or "")
        out.append((m.start(), m.end(), bp, CCY.get(c, c or "all")))
    taken = [(a, b) for a, b, _, _ in out]
    for m in SHOCK_SIGNED.finditer(flat):
        if any(a <= m.start() < b for a, b in taken):
            continue
        if not is_rate(m.start()):
            continue
        u = re.sub(r"\s", "", m.group("unit"))
        bp = float(m.group("mag")) * (100.0 if u == "%" else 1.0)
        if m.group("sign") in "-−":
            bp = -bp
        out.append((m.start(), m.end(), bp, "all"))
    return sorted(x for x in out if is_rate(x[0]))


def scope_at(flat, pos):
    last = None
    for m in SCOPE.finditer(flat[:pos]):
        last = m.group(1)
    return (last or "本公司").strip()


def unit_scale(flat, pos):
    """The last unit declared before the row governs it."""
    sc = 1.0
    for m in UNITDECL.finditer(flat[:pos]):
        sc = SCALE[re.sub(r"\s", "", m.group(1))]
    return sc


def parse_page(flat):
    """All rate-sensitivity observations on one page, normalised to +1bp."""
    if s6.IFRS17_COLS.search(flat):
        return []                       # Cathay: the eight-column parser owns it
    sh = shocks(flat)
    if not sh:
        return []
    out = []
    for i, (start, end, bp, ccy) in enumerate(sh):
        # The header is whatever sits between the previous shock row and this
        # one; for the first row of a table that is the header block itself.
        header, raw = header_of(flat, start, sh[i - 1][1] if i else 0)
        nxt = sh[i + 1][0] if i + 1 < len(sh) else len(flat)
        seg = flat[end:nxt]
        scale = unit_scale(flat, start)
        scope = scope_at(flat, start)

        cols = None if i else period_schema(raw)
        if cols:                        # period-major (Mercuries)
            vals = numbers(seg, len(cols))
            if len(vals) < len(cols):
                continue
            for (d, meas), v in zip(cols, vals):
                out.append(dict(as_of=d, subject="asset", measure=meas,
                                currency=ccy, scope=scope, shock_bp=bp,
                                value_ntd_k=round(v * scale, 3),
                                per_bp_ntd_k=round(v * scale / bp, 5),
                                layout="period"))
            continue

        cols = column_schema(header)
        if not cols:
            # Carry the previous row's schema: a table prints its header once
            # and then several shock rows under it.
            cols = out and out[-1].get("_cols")
        if not cols:
            continue
        vals = numbers(seg, len(cols))
        if len(vals) < len(cols):
            continue
        d = next((x for p, x in reversed(dates_in(flat[:start]))), None)
        if not d:
            continue
        # 74.51 x 1e5 is 7451000.000000001 in binary floating point, and an
        # exact-equality fixture on a 億元 table fails on that alone.
        rec = {(s, m): round(v * scale, 3) for (s, m), v in zip(cols, vals)}
        # The filing checks itself where it prints a net column.
        subs = {s for s, _ in cols}
        if {"asset", "liability", "net"} <= subs:
            bad = False
            for meas in {m for _, m in cols}:
                a, l, n = (rec.get(("asset", meas)), rec.get(("liability", meas)),
                           rec.get(("net", meas)))
                if None in (a, l, n):
                    continue
                if abs(a + l - n) > max(1.0, 2e-3 * max(abs(n), 1.0)):
                    bad = True
            if bad:
                continue
        for (s, m), v in rec.items():
            out.append(dict(as_of=d, subject=s, measure=m, currency=ccy,
                            scope=scope, shock_bp=bp, value_ntd_k=v,
                            per_bp_ntd_k=v / bp,
                            layout="grid", _cols=cols))
    for r in out:
        r.pop("_cols", None)
    return out


def parse_hontai(flat):
    """Hontai states it in a sentence, not a table.

    '若利率增加/減少30 基點 ... 之稅前損益及稅前其他綜合損益將減少 2,038,323
    仟元/增加 2,164,277 仟元'. One sentence per period, the period named ahead
    of the figures. No table reader will ever find this, and skipping it drops a
    firm from the sector aggregate entirely.
    """
    out = []
    pat = re.compile(
        r"利\s*率\s*增\s*加\s*/\s*減\s*少\s*(\d+)\s*" + alt("基點")
        + r".{0,120}?(9\d|1[0-2]\d)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*至\s*"
        r"(\d{1,2})\s*月\s*(\d{1,2})\s*日.{0,60}?將\s*(增加|減少)\s*"
        r"([\d,]+)\s*" + alt("仟元") + r"\s*/\s*(增加|減少)\s*([\d,]+)")
    for m in pat.finditer(flat):
        bp = float(m.group(1))
        d = (f"{1911 + int(m.group(2))}-{int(m.group(5)):02d}-"
             f"{int(m.group(6)):02d}")
        up = float(m.group(8).replace(",", "")) * (-1 if m.group(7) == "減少" else 1)
        out.append(dict(as_of=d, subject="asset", measure="pnl_and_oci",
                        currency="all", scope="本公司", shock_bp=bp,
                        value_ntd_k=up,
                        per_bp_ntd_k=up / bp, layout="prose"))
    return out


# Nan Shan splits its rate sensitivity by ACCOUNTING BUCKET rather than by
# balance-sheet subject, and that is not a presentational quirk — it is the
# disclosure's scope. Only 透過損益 and 透過其他綜合損益 assets appear. Bonds
# held at amortised cost carry duration and never touch this table, so Nan
# Shan's figure is a floor on its rate exposure, not a measure of it, and must
# not be compared like-for-like with a firm reporting its whole book.
NS_BUCKET = re.compile(alt("透過損益按公允價值衡量之金融資產")
                       + r"|" + alt("透過其他綜合損益按公允價值衡量之金融資產"))
NS_SHOCK = re.compile(r"(" + UP + r"|" + DOWN + r")\s*(\d+(?:\.\d+)?)\s*%")
NS_HEAD = re.compile(alt("變數變動"))


def parse_nanshan(flat):
    """Nan Shan's rate table: bucket rows, trailing marks, dates at the foot.

    The numbers extract right-to-left — '- $ 6,968,522) ($' is nil and
    (6,968,522) — which the existing trailing-mark reader already handles. What
    is specific here is that the table has no period header at all: the dates
    are printed once, after every block, so a block's period comes from its
    ordinal position and not from anything adjacent to it.
    """
    if "利率風險" not in flat or not NS_BUCKET.search(flat):
        return []
    heads = [m.start() for m in NS_HEAD.finditer(flat)]
    if not heads:
        return []
    dates = sorted({d for _, d in dates_in(flat[heads[-1]:])}, reverse=True)
    if len(dates) != len(heads):
        return []
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1] if i + 1 < len(heads) else len(flat)
        seg = flat[h:end]
        for b in NS_BUCKET.finditer(seg):
            sm = NS_SHOCK.search(seg[b.end(): b.end() + 24])
            if not sm:
                continue
            bp = float(sm.group(2)) * 100.0
            if re.fullmatch(DOWN, sm.group(1)):
                bp = -bp
            v = s6.numbers_trailing(seg[b.end() + sm.end():][:90], 2)
            if len(v) < 2:
                continue
            bucket = ("fvoci" if "其他綜合損益" in
                      re.sub(r"\s", "", b.group(0))[:8] else "fvpl")
            for meas, x in (("pnl", v[0]), ("oci", v[1])):
                out.append(dict(as_of=dates[i], subject=f"asset_{bucket}",
                                measure=meas, currency="all", scope="本公司",
                                shock_bp=bp, value_ntd_k=x,
                                per_bp_ntd_k=x / bp, layout="bucket"))
    return out


def parse_cathay(flat):
    """Reuse the eight-column IFRS 17 reader, reshaped to this table's schema.

    Its 金融工具 column is the one comparable to the other firms' asset column;
    the 小計 adds the insurance-contract effect, which the others report as a
    separate liability column. Both are kept, labelled distinctly.
    """
    out = []
    for r in (s6.parse_sensitivity_ifrs17(flat) or []):
        if r.get("table") != "rate":
            continue
        bp = float(re.sub(r"[^\d.]", "", r["shock"]) or 0)
        if not bp:
            continue
        if r.get("direction") in ("下降", "下跌"):
            bp = -bp
        for subj, pk, ek in (("asset", "pnl_instruments_ntd_k",
                              "eq_instruments_ntd_k"),
                             ("liability", "pnl_insurance_ntd_k",
                              "eq_insurance_ntd_k"),
                             ("net", "pnl_ntd_k", "equity_ntd_k")):
            for meas, key in (("pnl", pk), ("equity", ek)):
                v = r.get(key)
                if v is None:
                    continue
                out.append(dict(as_of=r["period_end"], subject=subj,
                                measure=meas, currency="all",
                                scope="本公司", shock_bp=bp,
                                value_ntd_k=v, per_bp_ntd_k=v / bp,
                                layout="ifrs17"))
    return out


def main():
    if not NOTE_TEXT.exists():
        print(f"no captured text at {NOTE_TEXT.name}; run the pull first.")
        return 0
    with gzip.open(NOTE_TEXT, "rt", encoding="utf-8") as fh:
        notes = json.load(fh)

    rows = []
    for filing, rec in sorted(notes.items()):
        for page, flat in rec["pages"].items():
            got = (parse_cathay(flat) or parse_nanshan(flat)
                   or parse_hontai(flat) or parse_page(flat))
            for r in got:
                r.update(entity_id=rec["entity_id"], co_id=rec["co_id"],
                         filing=filing, page=int(page))
                rows.append(r)

    # One observation per firm-period-subject-measure. The same balance sheet is
    # reported in up to three filings (its own and two comparatives) and in both
    # the up and the down row; averaging the two directions would hide convexity,
    # so the RISE is kept and the fall retained separately for comparison.
    best = {}
    for r in rows:
        # A subsidiary's table is a real disclosure and stays in the CSV, but it
        # is not the parent's exposure and must never stand in for it.
        if "子公司" in r.get("scope", ""):
            continue
        k = (r["entity_id"], r["as_of"], r["currency"], r["subject"],
             r["measure"])
        cur = best.get(k)
        # The RISE is preferred, but discarding the fall drops firms entirely:
        # Shinkong and KGI disclose -1bp only, and per_bp already carries the
        # sign (a fall divided by a negative shock IS the rise-equivalent), so
        # the down row is a usable second choice rather than a wrong one.
        # Then the smallest shock, which needs the least linear extrapolation.
        rank = (0 if r["shock_bp"] > 0 else 1, abs(r["shock_bp"]), r["filing"])
        if cur is None or rank < cur[0]:
            best[k] = (rank, r)
    out = [v[1] for _, v in sorted(best.items())]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["entity_id", "co_id", "as_of", "scope", "currency", "subject",
            "measure", "shock_bp", "value_ntd_k", "per_bp_ntd_k", "layout",
            "filing", "page"]
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(out, key=lambda r: (r["entity_id"], r["as_of"],
                                            r["currency"], r["subject"],
                                            r["measure"])):
            r["value_ntd_k"] = round(r["value_ntd_k"], 1)
            r["per_bp_ntd_k"] = round(r["per_bp_ntd_k"], 3)
            w.writerow(r)

    print(f"{len(out)} firm-period-column observations -> "
          f"{OUT.relative_to(ROOT)}\n")
    cov = defaultdict(set)
    lay = defaultdict(set)
    for r in out:
        cov[r["entity_id"]].add(r["as_of"])
        lay[r["entity_id"]].add(r["layout"])
    print(f"  {'firm':<18}{'periods':>8}  {'span':<26}{'layout'}")
    for ent in sorted(cov):
        d = sorted(cov[ent])
        print(f"  {ent:<18}{len(d):>8}  {d[0]} .. {d[-1]}   "
              f"{','.join(sorted(lay[ent]))}")
    missing = {r["entity_id"] for r in rows} ^ set(cov)
    if missing:
        print(f"\n  firms with rows but none surviving: {sorted(missing)}")

    # The number the duration question actually wants: equity change per
    # basis point on the ASSET side, which is the bond book's DV01 as it
    # reaches equity. Reported per firm at its latest period.
    print(f"\n  asset-side equity DV01, latest disclosed period")
    print(f"  {'firm':<18}{'as of':<13}{'NT$k per bp':>14}{'   shock'}")
    tot = 0.0
    for ent in sorted(cov):
        cand = [r for r in out if r["entity_id"] == ent
                and r["subject"] == "asset" and r["measure"] in ("equity", "oci",
                                                                 "pnl_and_oci")]
        if not cand:
            continue
        r = max(cand, key=lambda x: x["as_of"])
        tot += r["per_bp_ntd_k"]
        print(f"  {ent:<18}{r['as_of']:<13}{r['per_bp_ntd_k']:>14,.0f}"
              f"   {r['shock_bp']:.0f}bp")
    print(f"  {'SUM':<18}{'':<13}{tot:>14,.0f}")
    print(f"\n  Not a sector DV01: the periods differ between firms, the "
          f"disclosed measure differs (equity vs OCI vs the two combined), "
          f"and a firm's own shock size is extrapolated linearly to 1bp.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
