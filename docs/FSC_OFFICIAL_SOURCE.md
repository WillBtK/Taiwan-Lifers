# FSC Official Monthly Insurance Statistics — Primary Source for Hedge Ratio Data

## Discovery

The Financial Supervisory Commission publishes official monthly press releases with insurance industry statistics, including hedging data. These are more reliable than scattered press articles and cover the full 2020–2025 period.

**URL pattern:** `https://www.fsc.gov.tw/ch/home.jsp?id=96&...&dataserno=YYYYMMDDNNNN&dtable=News`

**Title pattern:** `新聞稿-XXX年M月保險業損益、淨值，以及兌換損益...`

Where XXX is the ROC year:
- 109 = 2020
- 110 = 2021
- 111 = 2022
- 112 = 2023
- 113 = 2024
- 114 = 2025

## Examples found

- 109年6月 (2020-06): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202007300002&dtable=News
- 110年6月 (2021-06): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0&mcustomize=news_view.jsp&dataserno=202107290002&dtable=News
- 111年2月 (2022-02): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202203300002&dtable=News
- 111年7月 (2022-07): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0%2C2&mcustomize=news_view.jsp&dataserno=202208300002&dtable=News
- 111年8月 (2022-08): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0&mcustomize=news_view.jsp&dataserno=202209270007&dtable=News
- 112年3月 (2023-03): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202304250004&dtable=News
- 112年12月 (2023-12): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202402010006&dtable=News
- 113年9月 (2024-09): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202411050003&dtable=News
- 113年11月 (2024-11): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202501020002&dtable=News
- 113年12月 (2024-12): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202502060003&dtable=News
- 114年2月 (2025-02): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202503270005&dtable=News
- 114年3月 (2025-03): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2&mcustomize=news_view.jsp&dataserno=202504290007&dtable=News
- 114年4月 (2025-04): https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0%2C2&mcustomize=news_view.jsp&dataserno=202505290005&dtable=News

## Content

These official releases contain:
- Pre-tax profit/loss by life and property insurance
- Net worth data
- Exchange gains/losses (兌換損益)
- **Hedging gains/losses (避險損益)** — containing the hedge ratio and exposure data
- Foreign exchange price change reserves (外匯價格變動準備金)

## Revised strategy

1. **Fetch FSC official releases** for each month 2020-01 → 2025-07 (67 months)
2. **Parse the structured data** tables from the HTML (likely tables with insurance statistics)
3. **Extract hedge ratio and regulatory exposure** from the tables
4. **Format into config** following the briefing_press.json structure
5. **Verify via stage1_briefing_press.py** that extraction is correct and identity checks pass

This approach is more reliable than parsing scattered press articles because:
- Official source with consistent structure
- Monthly releases cover the full period
- Same organization (FSC) publishes both official data and press articles (alignment guaranteed)
- Structured data is easier to parse than natural-language press articles

## Next step

Systematically collect the FSC release URLs for all 67 months, fetch them, extract the hedge ratio tables, and populate the config.
