"""Parsing the FSC monthly sector release into `sector_monthly` rows.

The release ("{ROC year}年{month}月保險業損益、淨值，以及兌換損益、避險損益與
外匯價格變動準備金情形", earlier "…損益、淨值及匯兌損益情形") is a short HTML
page with three tables and one closing paragraph. Measured against all 91
editions from May 2018 to December 2025 (docs/decisions.md 1.1):

  一  pre-tax profit, YTD, life / non-life / total        (all editions)
  二  owners' equity, month-end, life / non-life / total  (all editions)
  三  FX table, YTD, life / non-life / total:
        兌換損益            FX gain/loss on assets and liabilities
        避險損益            hedging P&L — one row to 2019-12; from 2020-01
                            split into 避險工具損益 (instrument P&L) and
                            避險工具換匯成本 (swap cost)
        外匯價格變動準備淨變動  net change in the FX price-fluctuation
                            reserve; positive = net release, negative =
                            net provision
        合計數              (1)+(2)+(3)
  四  narrative: TWD move YTD vs prior year-end; life insurers' FX reserve
      balance (all editions); change vs prior month (to 2019) or prior
      year-end (2020-09→); net foreign-investment income (2020-09→);
      one-off provisions where they occurred.

What the release does NOT carry, in any edition: the hedge ratio, the
foreign-investment total, the regulatory exposure, a hedge-cost *rate*, or
the reserve buckets. Those come from the Insurance Bureau's monthly
briefing (press-reported) and, from 2026, firm statements — see
docs/decisions.md 1.2.

Units: the release prints NT$ 億 (hundred million). Rows are stored in NT$
million (×100, exact) per the repo convention; no other coercion.

Tables are located by the section header that precedes them and by their
own row labels, never by position — the December 2019 edition has six
<table> elements and the March 2020 edition one.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from bs4 import BeautifulSoup, Tag

from .fsc import roc_to_date

YI_TO_MN = Decimal(100)

# Title, as printed in <div class="subject"><h3>. Two historical wordings.
TITLE_RE = re.compile(r"(\d{2,3})年(\d{1,2})月保險業(?:損益|兌換損益)")

# Row labels in the FX table, checked in this order (the 2020+ layout puts the
# rowspan label 避險損益(2) and the sub-label 避險工具損益 in the same <tr>).
FX_ROW_KEYS: tuple[tuple[str, str], ...] = (
    ("避險工具損益", "hedging_instrument_gain_loss"),
    ("換匯成本", "hedging_swap_cost"),
    ("避險損益", "hedging_gain_loss"),
    ("準備淨變動", "fx_reserve_net_change"),
    ("準備金淨變動", "fx_reserve_net_change"),
    ("兌換損益", "fx_gain_loss"),
    ("合計數", "fx_combined_effect"),
    ("淨影響數", "fx_combined_effect"),
)

_NUMERIC_CELL = re.compile(r"^[（(]?[-－]?[\d,]+(?:\.\d+)?[)）]?$")
_WS = re.compile(r"[\s　\xa0]+")

# Narrative (section 四).
RE_RESERVE_BALANCE = re.compile(
    r"外匯價格變動準備金(?:之)?(?:累積)?餘額(?:達|為|約為|約)?\s*([\d,]+(?:\.\d+)?)\s*億元"
)
RE_RESERVE_CHANGE = re.compile(
    r"餘額[^。]*?較(上月份|上月|1\d\d年底|去年年底|去年底|前一年底)(增加|減少)\s*([\d,]+(?:\.\d+)?)\s*億元"
)
RE_TWD_MOVE = re.compile(
    r"新臺幣兌美元匯率[^。]*?(升值|貶值)幅度(?:為|約為|約)?\s*([\d.]+)\s*[%％]"
)
RE_NET_FOREIGN_INCOME = re.compile(
    r"國外投資淨利益[^為。]*為\s*(負|-|－)?\s*([\d,]+(?:\.\d+)?)\s*億元"
)
RE_COMBINED_NARRATIVE = re.compile(
    r"影響合計數為\s*(負|-|－)?\s*([\d,]+(?:\.\d+)?)\s*億元"
)
RE_ONE_OFF = re.compile(r"一次性提存\s*([\d,]+(?:\.\d+)?)\s*億元")
RE_TOTAL_ASSETS = re.compile(r"壽險業資產\s*([\d,]+(?:\.\d+)?)\s*兆元")
RE_FOREIGN_INV = re.compile(r"國外投資\s*([\d,]+(?:\.\d+)?)\s*兆元")
RE_SWAP_COST_NARRATIVE = re.compile(r"避險交易之換匯成本(?:已)?達\s*([\d,]+(?:\.\d+)?)\s*億元")
ZHAO_TO_MN = Decimal(1_000_000)


def zhao_to_mn(v: Decimal | None) -> Decimal | None:
    return None if v is None else v * ZHAO_TO_MN


class ParseError(ValueError):
    pass


def parse_number(text: str) -> Decimal | None:
    """'1,234' -> 1234; '(1,234)' -> -1234; '負1,518' -> -1518; '-' -> None."""
    s = _WS.sub("", text).replace("，", ",").replace(",", "")
    if s in {"", "-", "－", "—", "--", "─"}:
        return None
    neg = False
    if s[0] in "（(" and s[-1] in "）)":
        neg, s = True, s[1:-1]
    if s and s[0] in "-－負":
        neg, s = True, s[1:]
    try:
        v = Decimal(s)
    except InvalidOperation:
        return None
    return -v if neg else v


def yi_to_mn(v: Decimal | None) -> Decimal | None:
    return None if v is None else v * YI_TO_MN


@dataclass
class SectorRelease:
    """One parsed edition. Amounts in NT$ million; ratios as printed (%)."""

    dataserno: str
    title: str
    published: date
    obs_month: date
    # 一 pre-tax profit, YTD
    pretax_profit_life: Decimal | None = None
    pretax_profit_nonlife: Decimal | None = None
    pretax_profit_total: Decimal | None = None
    # 二 owners' equity, month-end
    owners_equity: Decimal | None = None            # life insurers
    owners_equity_nonlife: Decimal | None = None
    owners_equity_total: Decimal | None = None
    # 三 FX table, life insurers, YTD
    fx_gain_loss: Decimal | None = None
    hedging_gain_loss: Decimal | None = None        # instrument + swap cost
    hedging_instrument_gain_loss: Decimal | None = None
    hedging_swap_cost: Decimal | None = None
    fx_reserve_net_change: Decimal | None = None    # +release / -provision
    fx_combined_effect: Decimal | None = None       # (1)+(2)+(3)
    # 四 narrative
    fx_reserve_total: Decimal | None = None         # life FX reserve balance
    fx_reserve_change: Decimal | None = None
    fx_reserve_change_basis: str | None = None      # 'prev_month' | 'prev_year_end'
    twd_change_ytd_pct: Decimal | None = None       # + = TWD appreciation vs prior year-end
    net_foreign_investment_income: Decimal | None = None
    one_off_provision: Decimal | None = None
    fx_combined_effect_narrative: Decimal | None = None
    total_assets: Decimal | None = None             # 2020-01, 2020-02 only
    foreign_investments: Decimal | None = None      # 2020-01, 2020-02 only
    # bookkeeping
    hedging_split_available: bool = False
    warnings: list[str] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        for k, v in row.items():
            if isinstance(v, Decimal):
                row[k] = decimal_str(v)
            elif isinstance(v, date):
                row[k] = v.isoformat()
        return row


def decimal_str(v: Decimal) -> str:
    """Plain decimal text, never scientific notation: 44700, -0.44, 2.5."""
    s = format(v, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


# ----------------------------------------------------------------- helpers

def _cells(tr: Tag) -> list[str]:
    return [_WS.sub("", td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]


def _numeric_cells(cells: Iterable[str]) -> list[Decimal | None]:
    out: list[Decimal | None] = []
    for c in cells:
        if _NUMERIC_CELL.match(c) or c in {"-", "－", "—"}:
            out.append(parse_number(c))
    return out


def _preceding_text(table: Tag, limit: int = 400) -> str:
    """Text immediately before `table` in document order, nearest first."""
    buf: list[str] = []
    n = 0
    for s in table.find_all_previous(string=True):
        t = _WS.sub("", str(s))
        if not t:
            continue
        buf.append(t)
        n += len(t)
        if n >= limit:
            break
    return "|".join(buf)


def _classify(table: Tag) -> str | None:
    own = _WS.sub("", table.get_text(" ", strip=True))
    if "兌換損益" in own or "匯兌損益" in own or "避險損益" in own:
        return "fx"
    if not ({"壽險業", "產險業"} & set(own.replace("|", "").split())) and "壽險業" not in own:
        return None
    before = _preceding_text(table)
    # nearest header wins: scan the concatenated string for the first
    # keyword occurrence (buf is nearest-first).
    for chunk in before.split("|"):
        if "稅前損益" in chunk:
            return "pretax"
        if "淨值" in chunk or "業主權益" in chunk:
            return "equity"
    return None


def _three_rows(table: Tag) -> dict[str, Decimal | None]:
    out: dict[str, Decimal | None] = {}
    for tr in table.find_all("tr"):
        cells = _cells(tr)
        if not cells:
            continue
        label = next((c for c in cells if c), "")
        key = {"壽險業": "life", "產險業": "nonlife", "合計": "total"}.get(label[:3])
        if key is None:
            continue
        nums = _numeric_cells(cells[1:])
        out[key] = nums[0] if nums else None
    return out


def _fx_rows(table: Tag) -> dict[str, dict[str, Decimal | None]]:
    """{field: {'life':…, 'nonlife':…, 'total':…}}"""
    out: dict[str, dict[str, Decimal | None]] = {}
    for tr in table.find_all("tr"):
        cells = _cells(tr)
        joined = "".join(cells)
        fld = next((f for k, f in FX_ROW_KEYS if k in joined), None)
        if fld is None or fld in out:
            continue
        nums = _numeric_cells(cells)
        if len(nums) < 2:
            continue
        nums = (nums + [None, None, None])[:3]
        out[fld] = {"life": nums[0], "nonlife": nums[1], "total": nums[2]}
    return out


# ------------------------------------------------------------------ parser

def parse_release(html: bytes | str, *, dataserno: str) -> SectorRelease:
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("div", class_="maincontent")
    if main is None:
        raise ParseError(f"{dataserno}: no maincontent div")
    subject = main.find("div", class_="subject")
    title = _WS.sub("", subject.get_text(" ", strip=True)) if subject else ""
    m = TITLE_RE.search(title)
    if not m:
        raise ParseError(f"{dataserno}: title not recognised: {title!r}")
    obs_month = roc_to_date(m.group(1), m.group(2))
    date_div = main.find("div", class_="date")
    published = date.fromisoformat(date_div.get_text(strip=True)) if date_div else \
        date(int(dataserno[:4]), int(dataserno[4:6]), int(dataserno[6:8]))
    body = main.find("div", class_="page-edit") or main
    text = _WS.sub("", body.get_text(" ", strip=True))

    rel = SectorRelease(dataserno=dataserno, title=title, published=published, obs_month=obs_month)

    seen: set[str] = set()
    for table in body.find_all("table"):
        if table.find_parent("table") is not None:
            continue  # nested layout table
        kind = _classify(table)
        if kind is None or kind in seen:
            continue
        # A table only counts once it yields figures: the December 2019
        # edition wraps each section header in its own one-cell <table>, which
        # classifies like the data table that follows it but holds no numbers.
        if kind == "pretax":
            r = _three_rows(table)
            if not r:
                continue
            rel.pretax_profit_life = yi_to_mn(r.get("life"))
            rel.pretax_profit_nonlife = yi_to_mn(r.get("nonlife"))
            rel.pretax_profit_total = yi_to_mn(r.get("total"))
        elif kind == "equity":
            r = _three_rows(table)
            if not r:
                continue
            rel.owners_equity = yi_to_mn(r.get("life"))
            rel.owners_equity_nonlife = yi_to_mn(r.get("nonlife"))
            rel.owners_equity_total = yi_to_mn(r.get("total"))
        else:
            fx = _fx_rows(table)
            if not fx:
                continue
            for fld, vals in fx.items():
                setattr(rel, fld, yi_to_mn(vals["life"]))
            if rel.hedging_instrument_gain_loss is not None and rel.hedging_swap_cost is not None:
                rel.hedging_split_available = True
                rel.hedging_gain_loss = rel.hedging_instrument_gain_loss + rel.hedging_swap_cost
        seen.add(kind)

    if "fx" not in seen:
        raise ParseError(f"{dataserno}: FX table not found")
    if "pretax" not in seen:
        rel.warnings.append("no pre-tax profit table")
    if "equity" not in seen:
        rel.warnings.append("no equity table")

    # ---- narrative
    if (m := RE_RESERVE_BALANCE.search(text)):
        rel.fx_reserve_total = yi_to_mn(parse_number(m.group(1)))
    else:
        rel.warnings.append("reserve balance not found in narrative")
    if (m := RE_RESERVE_CHANGE.search(text)):
        v = parse_number(m.group(3))
        rel.fx_reserve_change = yi_to_mn(-v if m.group(2) == "減少" else v)
        rel.fx_reserve_change_basis = "prev_month" if m.group(1).startswith("上月") else "prev_year_end"
    if (m := RE_TWD_MOVE.search(text)):
        v = Decimal(m.group(2))
        if "相對於上月" in m.group(0):
            # December 2019 quotes the month-on-month move, not the YTD one.
            rel.warnings.append("TWD move quoted month-on-month; YTD left null")
        else:
            rel.twd_change_ytd_pct = v if m.group(1) == "升值" else -v
    else:
        rel.warnings.append("TWD move not found in narrative")
    # January and February 2020 replace the reserve sentence with the balance
    # sheet: "壽險業資產29.8兆元，國外投資17.7兆元". Only these two editions
    # print the foreign-investment total.
    if (m := RE_TOTAL_ASSETS.search(text)):
        rel.total_assets = zhao_to_mn(parse_number(m.group(1)))
    if (m := RE_FOREIGN_INV.search(text)):
        rel.foreign_investments = zhao_to_mn(parse_number(m.group(1)))
    # November and December 2019 give the cumulative swap cost only in prose.
    if rel.hedging_swap_cost is None and (m := RE_SWAP_COST_NARRATIVE.search(text)):
        rel.hedging_swap_cost = -yi_to_mn(parse_number(m.group(1)))  # a cost: stored negative like the table
        rel.warnings.append("swap cost taken from narrative")
    if (m := RE_NET_FOREIGN_INCOME.search(text)):
        v = parse_number(m.group(2))
        rel.net_foreign_investment_income = yi_to_mn(-v if m.group(1) else v)
    if (m := RE_COMBINED_NARRATIVE.search(text)):
        v = parse_number(m.group(2))
        rel.fx_combined_effect_narrative = yi_to_mn(-v if m.group(1) else v)
    if (m := RE_ONE_OFF.search(text)):
        rel.one_off_provision = yi_to_mn(parse_number(m.group(1)))
    return rel


# -------------------------------------------------------------- validation

def internal_checks(rel: SectorRelease, tol_mn: Decimal = Decimal(150)) -> list[tuple[str, bool, str]]:
    """Arithmetic the release must satisfy within rounding (figures are printed
    to NT$ 1 億, so life + non-life can differ from total by up to 1 億 per
    addend: tolerance 1.5 億 = 150 mn)."""
    out: list[tuple[str, bool, str]] = []

    def add(name: str, lhs: Decimal | None, rhs: Decimal | None) -> None:
        if lhs is None or rhs is None:
            return
        ok = abs(lhs - rhs) <= tol_mn
        out.append((name, ok, f"{lhs} vs {rhs}"))

    if rel.pretax_profit_life is not None and rel.pretax_profit_nonlife is not None:
        add("pretax life+nonlife=total", rel.pretax_profit_life + rel.pretax_profit_nonlife, rel.pretax_profit_total)
    if rel.owners_equity is not None and rel.owners_equity_nonlife is not None:
        add("equity life+nonlife=total", rel.owners_equity + rel.owners_equity_nonlife, rel.owners_equity_total)
    parts = [rel.fx_gain_loss, rel.hedging_gain_loss, rel.fx_reserve_net_change]
    if all(p is not None for p in parts):
        add("fx table (1)+(2)+(3)=total", sum(parts), rel.fx_combined_effect)  # type: ignore[arg-type]
    add("fx combined: table vs narrative", rel.fx_combined_effect, rel.fx_combined_effect_narrative)
    return out
