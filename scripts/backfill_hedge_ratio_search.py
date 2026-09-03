#!/usr/bin/env python3
"""Identify and collect press articles for 2020-01 → 2025-07 Insurance Bureau monthly briefing.

Strategy:
  - Insurance Bureau holds monthly briefings on regulatory hedge ratios and FX exposure.
  - Press reports appear on money.udn.com, news.cnyes.com, CTS/CNA within 1–2 weeks of month-end.
  - Search keywords: 保險局, 避險比率, 國外投資, 曝險金額 (Insurance Bureau, hedge ratio, foreign investments, exposure).
  - For each month 2020-01 → 2025-07, find the primary article (earliest, best-sourced).
  - Extract and verify: hedge_ratio_regulatory, regulatory_fx_exposure, foreign_investments.
  - Output: a candidate config fragment (config/briefing_press_backfill.json) for manual curation.

This script documents the search pattern. Haiku 4.5 can conduct the month-by-month searches
and verify each article's figures against the Insurance Bureau's published statements, then
complete the config. See HANDOFF.md item 1.

Requires: no additional dependencies beyond the main project.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_TEMPLATE = ROOT / "config" / "briefing_press_backfill.json"

# Month-by-month template: each entry needs its article URL(s) filled in.
TEMPLATE = {
    "_doc": [
        "Insurance Bureau monthly briefing — 2020-01 to 2025-07 backfill search candidates.",
        "Each row is one reference month. Search results and URLs are to be filled in.",
        "Searches conducted on money.udn.com for: 保險局 避險比率 (Insurance Bureau hedge ratio)",
        "for the month-end briefing (published early next month).",
        "Primary fields to extract: hedge_ratio_regulatory; secondary: regulatory_fx_exposure,",
        "foreign_investments. See docs/decisions.md 1.2 and HANDOFF.md item 1 for context."
    ],
    "rows": []
}

# Generate template rows for 2020-01 to 2025-07.
start = date(2020, 1, 1)
end = date(2025, 7, 1)
current = start
while current <= end:
    month_str = current.strftime("%Y-%m-%d")
    published_window = f"{current.month+1:02d}" if current.month < 12 else "01"
    year_window = current.year if current.month < 12 else current.year + 1

    TEMPLATE["rows"].append({
        "obs_month": month_str,
        "reported_by": "金管會保險局",
        "sources": [
            {
                "url": "",  # To be filled in: money.udn.com article URL
                "published": f"{year_window}-{published_window}-XX",  # Approx publication window
                "outlet": "經濟日報",
                "fields": {
                    "hedge_ratio_regulatory": ""  # e.g., "50.23%"
                },
                "quote": ""  # Exact quoted text from the article
            }
        ],
        "note": "Backfill 2020-01 → 2025-07: to be searched and verified."
    })

    if current.month == 12:
        current = current.replace(year=current.year + 1, month=1)
    else:
        current = current.replace(month=current.month + 1)

def main():
    CONFIG_TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_TEMPLATE.write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Template written to {CONFIG_TEMPLATE.relative_to(ROOT)}")
    print(f"Months to search: {len(TEMPLATE['rows'])} (2020-01 → 2025-07)")
    print("\nSearch pattern: money.udn.com for '保險局 避險比率' + month-end date")
    print("Fetch articles, verify figures, record exact quotes, and complete config.")
    print("See scripts/stage1_briefing_press.py for config format and verification logic.")

if __name__ == "__main__":
    main()
