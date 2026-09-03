"""Locating FSC press releases.

The Chinese press list (`id=96`) is a single reverse-chronological stream of
every FSC release — banking, securities and insurance interleaved — so the
monthly insurance release sits at a different offset each month and cannot be
found by position. The list does, however, expose its own POST search form
(`keyword`, `qptdate`, `qdldate`, `page`, `pagesize`), which is what this
module drives: query by keyword, then filter titles by pattern. No pagination
walking, no positional assumptions.

Release titles carry Republic-of-China years: `114年12月` is December 2025.
`roc_to_date` converts them.

Confirmed working 2026-09-03; see docs/decisions.md 0.10 and 0.11.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import requests

from .provenance import Provenance, ua_for, utc_now

# Both regulators run the same CMS and the same search form, and the monthly
# release is mirrored on both. Querying both and merging on dataserno costs one
# extra request and removes a single point of failure.
CHANNELS: dict[str, tuple[str, str]] = {
    "fsc": ("https://www.fsc.gov.tw/ch/home.jsp", "96"),
    "ib": ("https://www.ib.gov.tw/ch/home.jsp", "239"),
}
DEFAULT_CHANNEL = "fsc"
ITEM_URL = "{base}?id={list_id}&parentpath=0,2&mcustomize=news_view.jsp&dataserno={dataserno}&dtable=News"

# The monthly sector release. Full title, e.g.:
#   114年12月保險業損益、淨值，以及兌換損益、避險損益與外匯價格變動準備金
MONTHLY_TITLE = re.compile(r"(\d{2,3})年(\d{1,2})月保險業損益[、，]?淨值")
MONTHLY_KEYWORD = "損益、淨值"

# Foreign-currency policy sales, e.g.:
#   壽險業115年截至6月底外幣保險商品銷售情形
FX_POLICY_TITLE = re.compile(r"壽險業(\d{2,3})年截至(\d{1,2})月底外幣保險商品銷售")
FX_POLICY_KEYWORD = "外幣保險商品銷售"

_ITEM = re.compile(r"dataserno=(\d+)[^\"]*\"[^>]*>\s*([^<]{6,120}?)\s*</a>")


def roc_to_date(roc_year: int | str, month: int | str) -> date:
    """ROC year + month -> the first day of that month in the Gregorian calendar."""
    return date(int(roc_year) + 1911, int(month), 1)


@dataclass(frozen=True)
class Release:
    dataserno: str
    title: str
    reference_month: date | None   # the month the release reports on
    url: str

    @property
    def published_date(self) -> date:
        """Publication date, encoded in the first 8 digits of dataserno."""
        s = self.dataserno
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def search(keyword: str, *, channel: str = DEFAULT_CHANNEL, pagesize: int = 200,
           page: int = 1, timeout: int = 60) -> tuple[list[tuple[str, str]], Provenance]:
    """POST the list's own search form. Returns [(dataserno, title)] plus provenance."""
    base, list_id = CHANNELS[channel]
    payload = {
        "id": list_id, "contentid": list_id, "parentpath": "0,2",
        "mcustomize": "news_list.jsp", "keyword": keyword,
        "qunit": "", "dateid": "", "qptdate": "", "qdldate": "",
        "page": str(page), "pagesize": str(pagesize),
    }
    resp = requests.post(
        base, data=payload,
        headers={"User-Agent": ua_for(base), "Accept": "*/*"},
        timeout=timeout,
    )
    resp.raise_for_status()
    prov = Provenance(
        source_url=f"{base}?id={list_id} [POST keyword={keyword}]",
        source_doc=f"{channel.upper()} Chinese press-release list",
        retrieved_at=utc_now(),
        http_status=resp.status_code,
    )
    seen: dict[str, str] = {}
    for serno, title in _ITEM.findall(resp.text):
        seen.setdefault(serno, title)
    return list(seen.items()), prov


def _find(keyword: str, pattern: re.Pattern[str], *, channels: tuple[str, ...] = ("fsc", "ib"),
          **kw) -> tuple[list[Release], list[Provenance]]:
    items: dict[str, str] = {}
    provs: list[Provenance] = []
    for channel in channels:
        found, prov = search(keyword, channel=channel, **kw)
        provs.append(prov)
        for serno, title in found:
            items.setdefault(serno, title)
    out = []
    for serno, title in items.items():
        m = pattern.search(title)
        if not m:
            continue
        out.append(
            Release(
                dataserno=serno,
                title=title,
                reference_month=roc_to_date(m.group(1), m.group(2)),
                url=ITEM_URL.format(
                    base=CHANNELS[channels[0]][0],
                    list_id=CHANNELS[channels[0]][1],
                    dataserno=serno,
                ),
            )
        )
    out.sort(key=lambda r: r.reference_month or date.min, reverse=True)
    return out, provs


def find_monthly_releases(**kw) -> tuple[list[Release], list[Provenance]]:
    """Monthly sector release: profit/loss, net value, FX and hedging P&L, FX reserve.

    Newest first. Stage 1's entry point — it never assumes a page position.

    Coverage as measured 2026-09-03: 90 editions, May 2018 to December 2025.
    The series STOPS at the December 2025 edition (published 2026-01-27) on
    both channels; see docs/decisions.md 0.11 before relying on it for 2026.
    """
    return _find(MONTHLY_KEYWORD, MONTHLY_TITLE, **kw)


def find_fx_policy_releases(**kw) -> tuple[list[Release], list[Provenance]]:
    """Foreign-currency policy sales release (README section 4.1)."""
    return _find(FX_POLICY_KEYWORD, FX_POLICY_TITLE, **kw)


def latest_monthly(**kw) -> Release | None:
    releases, _ = find_monthly_releases(**kw)
    return releases[0] if releases else None
