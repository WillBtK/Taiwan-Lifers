#!/usr/bin/env python3
"""Probe a candidate press article for Insurance Bureau briefing figures.

    python3 scripts/probe_briefing_article.py <url> [<url> ...]

Prints the byline date and every sentence carrying a briefing keyword and a
number, so the exact printed figure and its reference month can be read off and
pasted into `config/briefing_press.json`. Nothing is written; curation is manual
by design (docs/decisions.md 1.4 — figures go in as printed, verified against
their own article by scripts/stage1_briefing_press.py).

Channel note (decisions 1.10): money.udn.com purges at roughly twelve months,
so for any month older than that use news.cnyes.com, which retains to 2020.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bs4 import BeautifulSoup  # noqa: E402

from tlfx.provenance import fetch  # noqa: E402

KEYS = ("避險比率", "避險比例", "曝險", "國外投資金額", "外匯價格變動準備金", "換匯成本")


def probe(url: str) -> None:
    try:
        fr = fetch(url, source_doc="press article", timeout=45, basis="press_reported")
    except Exception as exc:
        print(f"\n### {url}\n    ERROR {type(exc).__name__}: {exc}")
        return
    soup = BeautifulSoup(fr.content, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for t in soup(["script", "style", "nav", "footer", "header", "aside"]):
        t.decompose()
    text = "\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
    stamp = re.search(r"20\d\d-\d\d-\d\d(?: \d\d:\d\d)?", text)
    print(f"\n### {url}  [{fr.provenance.http_status}]")
    print(f"    title: {title[:90]}")
    print(f"    byline: {stamp.group(0) if stamp else '(none found)'}")
    hits = 0
    for sent in re.split(r"(?<=[。！？])", text):
        if any(k in sent for k in KEYS) and re.search(r"\d", sent):
            print(f"    > {sent.strip()[:260]}")
            hits += 1
    if not hits:
        print("    (no keyed sentence carrying a number — the ratio is probably not in this piece)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for u in sys.argv[1:]:
        probe(u)
