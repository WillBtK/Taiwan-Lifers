<!-- Supplied by the user 2026-09-05. Verified claim by claim at decisions 4.37.
     ADOPTED: target variables (a)-(e), acceptance test, extraction rules §3.2, order of work §5.
     CORRECTED: §1.2 the FSC statistics API carries none of the six target variables (0/165
       datasets match on any target term); §1.1 checkrpt.aspx is a menu page, not the query;
       §2.2 the CBC keeps no per-month PDF archive (use the Internet Archive, per 4.34).
     OMITTED BY THE DOCUMENT: ins-info and ib.gov.tw are GEO-blocked, not robots-blocked;
       a User-Agent will not help. All three TII hosts are unreachable from this environment. -->

# DATA_SOURCES.md — authoritative source map for the Taiwan lifer FX panel

This file overrides any earlier source guidance in this repo, in chat history, or in the README. If a source is not listed here, do not use it for a series. Read this file at the start of every session that touches ingestion.

## 0. Hard rules

**Do not use, for any series:**
- FSC or Insurance Bureau press releases (新聞稿). They start in 2020, are aggregate-only, and are the reason the last three days were wasted. They are permitted only as a cross-check in a reconciliation step, never as an ingestion target.
- News articles, wire stories, sell-side notes, blogs, Bloomberg/Reuters summaries. Never.
- Investor presentations, until Stage 4. They are supplementary and short-history.
- Any PDF hosted on Scribd or similar re-hosting sites.
- Setser (2019) as a data source. It is methodology only.

**Target panel:** all life insurers licensed by the Insurance Bureau (20 entities in 2026: 國泰, 富邦, 南山, 新光, 凱基, 台灣, 臺銀, 保誠, 三商美邦, 遠雄, 宏泰, 安聯, 中華郵政壽險處, 第一金, 合作金庫, 全球, 元大, 安達, 友邦台灣分公司, 法巴台灣分公司). Priority order within the panel: Cathay, Fubon, Nan Shan, Shin Kong, KGI, Taiwan Life.

**Target variables** (company × quarter): (a) total assets; (b) foreign-currency assets; (c) total liabilities; (d1) FX policy liabilities; (d2) FX financial liabilities by currency; (e) FX derivative notionals by instrument.

**Acceptance test for any source:** it must deliver at least one of (a)–(e) at company level with history before 2020, or at sector level with history before 2010. A source that fails this test is not a series source.

Verification marks: † confirmed by opening the page/resource (Sept 2026); ‡ surfaced in search or linked from a confirmed page, not opened; ? third-party assertion, unverified.

---

## 1. Company-level regulator panel — variables (a), (b), (c)

### 1.1 Insurance Public Information Observation Station (保險業公開資訊觀測站)
Root: `https://ins-info.ib.gov.tw/` †

This is the primary source. Every licensed insurer files standardised quarterly tables here. Use these entry points:

| Entry point | URL | What it gives |
|---|---|---|
| Multi-company aggregation query (彙計表) † | `https://ins-info.ib.gov.tw/customer/checkrpt.aspx` | Select table + period → all companies in one table |
| Statistics query † | `https://ins-info.ib.gov.tw/customer/accountquery.aspx` | Period-by-period query |
| Single-company page † | `https://ins-info.ib.gov.tw/customer/Info2-1.aspx?UID=<統一編號>` | Per-company tables incl. 資金運用表 |
| Announcements † | `https://ins-info.ib.gov.tw/customer/announceinfo.aspx` | Filing announcements |

Tables to pull (IDs confirmed on the 彙計表 page †):
- **表06021011 財務報表摘要** — total assets, total liabilities, equity, by company, by quarter → (a), (c)
- **資金運用表** (per company, single-company page) — fund utilisation with the **國外投資** line → (b)
- **表06161610 壽險財務業務指標** — ratios incl. 資金運用比率, useful for cross-checks
- **表07011010 壽險業務概況** — business overview (premiums by type; may include 外幣保單 premiums — check)

Procedure:
1. Enumerate companies and their 統一編號 (tax IDs) from the IB company list `https://www.ib.gov.tw/ch/home.jsp?id=181&parentpath=0,9,179` †.
2. On 彙計表, walk the period selector backwards until it stops. Record the earliest period per table in `STATUS.md`. Do not assume the depth; establish it.
3. Store every period found, raw, with `source_table`, `period`, `retrieved_at`.
4. For 資金運用表, repeat per company via the single-company page.

Known frictions: the site returns robots-disallowed to a generic fetcher †. Use a browser-like User-Agent, session cookies, and a rate limit of one request per 2–3 seconds. Pages are ASP.NET with ViewState; POST-back is required for selector changes. If the period selector is shallow (e.g. only recent years), the historical backfill moves to §3.

### 1.2 FSC statistics API
- OpenAPI spec: `https://stat.fsc.gov.tw/api/swagger/openapi.json` ‡
- Portal: `https://stat.fsc.gov.tw/` ‡ (金融市場統計資訊系統, Insurance Bureau view `?Beauid=IB`)

Serves the indicator families behind data.gov.tw datasets 7190 (財務報表摘要) ‡ and 7191 (壽險財務業務指標) ‡. Read the spec first; if it exposes historical periods by company, it is the cleaner route to (a) and (c) and should be loaded alongside §1.1 for reconciliation. The data.gov.tw JSON resources for these datasets are current-period snapshots and are not a history source ?.

### 1.3 data.gov.tw (secondary, machine-readable current data)
- 7186 保險公司基本資料 ‡; 7190 財務報表摘要 ‡; 7191 壽險財務業務指標 ‡
- TWSE/MOPS derived: 92000 上市公司綜合損益表(保險業) ‡, 97154 公發公司綜合損益表(保險業) ‡, and the matching balance-sheet datasets (search `https://data.gov.tw/datasets/search?cgl-3=712` ‡)

---

## 2. Sector aggregates — long history, all variables at sector level

### 2.1 CBC table 8 — 人壽保險公司資產負債統計表
- Index: `https://www.cbc.gov.tw/tw/cp-532-104915-d9972-1.html` † (Financial Statistics Monthly contents; appendix table 8 with XLS/CSV/PDF)
- Rolling CSV: `https://www.cbc.gov.tw/public/data/EBOOKXLS/065_EF67_A4L.csv` †
- Open-data mirror: data.gov.tw dataset 10767 / `https://www.cbc.gov.tw/public/data/OpenData/經研處/EF67M01.csv` ?
- Full history database: `https://cpx.cbc.gov.tw/` ‡ (statistics query system; monthly from May 1987 ?)

Gives sector total assets, foreign assets (國外投資), reserves, equity, monthly, back to 1987. This is the reconciliation anchor: quarter-end sums of §1 across all companies must match table 8 within tolerance.

### 2.2 CBC monthly footnote — sector FX hedge outstandings
The monthly life-insurer release carries a footnote stating outstanding FX hedges (the source of "method 2" in Setser and S.T.W. 2019). Footnotes are not in the database. Scrape the monthly PDF versions of table 8 from the index above for every month available; extract the footnote value into `sector_monthly.hedge_notional_cbc`. This is the only aggregate hedge series before 2020.

### 2.3 Taiwan Insurance Institute (保險事業發展中心)
- 保險財務業務統計 index: `https://www.tii.org.tw/tii/information/information1/000001.html` † (XLS/PDF; annual and monthly tables — fund utilisation, foreign investment, premiums)
- Statistics query system: `https://sv.tii.org.tw/` ‡
- Database: `https://insdb.tii.org.tw/` ‡
- Annual 人壽保險業務統計年報 (historical company-level fund utilisation; check for 國外投資 by company) ?

Use TII for (b) by company where the Observation Station history is shallow, and for pre-2000 sector history.

### 2.4 Life Insurance Association (壽險公會)
- 壽險業業績統計 monthly PDFs: `https://www.lia-roc.org.tw/list_article?article_content=36` ‡

Secondary; company-level premiums and assets. Use only if §1 and §2.3 leave gaps.

### 2.5 FSC monthly release (2020–present) — cross-check only
`https://www.fsc.gov.tw/en/home.jsp?id=54&parentpath=0,2` †. Load into `sector_monthly` for the regulatory hedge ratio, hedge cost, FX reserve buckets and FX gains/losses. Never used to construct (a)–(e).

---

## 3. Statutory quarterly financial statements — variables (c), (d2), (e), and (d1) where disclosed

This is the only source for hedge notionals and FX liabilities at company level, and it exists for every insurer, listed or not. The disclosure obligations come from the 保險業財務報告編製準則 (regulation text: `https://law.tii.org.tw/` ‡ or `https://law.fsc.gov.tw/` ?), which require:
- derivative notional principal (名目本金) by instrument in the financial-instruments note;
- foreign-currency monetary assets and liabilities by currency in the note 外幣金融資產及負債之匯率資訊.

### 3.1 Where to get the PDFs
| Firm | Location | Notes |
|---|---|---|
| Cathay Life | `https://www.cathayholdings.com/holdings/` (media library `/-/media/<guid>.pdf?sc_lang=zh-tw`) ?; `https://www.cathaylife.com.tw/` ? | Quarterly reviewed statements back to at least 2021 Q1 online ? |
| Shin Kong Life (TS Financial from 2026) | `https://www.ir-cloud.com/taiwan/2888/financial/` ?; `https://www.irpro.co/2888/financial/` ?; `https://www.tsholdings.com.tw/` ‡ | Notional disclosure confirmed by third party for 2020–2024 ? |
| Fubon Life | `https://www.irpro.co/2881/` ‡; `https://www.fubon.com/financialholdings/` ‡ | |
| KGI Life | `https://www.kgilife.com.tw/` ‡; `https://www.kgi.com/` ‡ | |
| Taiwan Life | `https://ir.ctbcholding.com/` †; PDFs at `https://media-ctbc.todayir.com/` † | `www.ctbcholding.com` is robots-blocked |
| Nan Shan Life | `https://www.nanshanlife.com.tw/` ? | Unlisted; statements on own site and Observation Station |
| All others | Own websites; Observation Station single-company page (check for 財務報告 links) ? | |
| Listed FHC subsidiaries, statutory archive | MOPS `https://mops.twse.com.tw/` ‡ (JS-rendered, rate-limited); legacy `https://mopsov.twse.com.tw/` ‡; English `https://emops.twse.com.tw/` ‡ | Last resort |

### 3.2 Extraction rules (non-negotiable)
1. **Notionals come from the derivatives/financial-instruments note, not from the hedge-accounting table (避險工具).** The hedge-accounting table lists only designated hedges; most economic hedges (FX swaps, NDFs, forwards at FVTPL) are outside it.
2. Store notionals **by instrument**: FX forwards, FX swaps, cross-currency swaps, NDFs, options. Compute `traditional_hedge = forwards + swaps + CCS + NDF` as a derived field, never as the stored value.
3. **(d2) FX financial liabilities** from the currency-risk note, by currency, monetary and non-monetary separately. Do not compute "domestic liabilities = total − (d2)"; insurance contract liabilities are not in that note before 2026.
4. **(d1) FX policy liabilities**: pre-2026, look in the insurance-liabilities/reserves note for 外幣保單 reserves; not every firm discloses it — record `null`, not an estimate. From FY2026, IFRS 17 currency-risk disclosure covers insurance contract liabilities; treat as a format break with a `basis` flag.
5. Every interim report carries comparison columns (prior quarter-end, prior year-end, prior-year same quarter). Use them: one statement per firm per year gives most of the backfill.
6. Pre-2013 statements are ROC GAAP. Notional disclosure exists but labels differ (常見: 遠期外匯合約, 換匯交易, 換匯換利). Extend the panel back as far as PDFs exist; do not stop at 2013 because the labels change.
7. Record page number and note number for every extracted value in `source_doc`.

### 3.3 Third-party reference values (unverified, use as extraction sanity checks only)
- Shin Kong aggregate FX forward + swap notional: NT$1.047tn (Mar 2020), NT$0.999tn (Dec 2020), NT$1.030tn (Mar 2021), NT$1.208tn (Jun 2023), NT$1.369tn (Dec 2023), NT$1.399tn (Jun 2024) ?
- Cathay foreign assets and FX policy liabilities as % of foreign assets: NT$5.11tn/32% (FY22), 5.53/31% (2Q24), 5.60/31% (FY24), 5.42/31% (3Q25), 5.44/26% (1Q26) ?
- Fubon FX policy liabilities 22.4% of foreign financial assets (1Q26) ?

If an extraction disagrees with these by more than 10%, check the extraction before trusting the reference.

---

## 4. Investor presentations — Stage 4 only

Six firms, quarterly, from ~2013. Use only for: FX policy liabilities as % of foreign assets (where §3 gives null), hedge composition (CS/NDF vs proxy vs open), hedging cost in bp, recurring yield pre/post hedge.
- Cathay: `https://www.cathayholdings.com/holdings/eng/ir` ‡ and `https://www.ir-cloud.com/taiwan/2882/` ‡
- Fubon: `https://www.irpro.co/2881/events/` ‡
- TS Financial: `https://www.tsholdings.com.tw/` ‡
- KGI: `https://www.kgi.com/en/` ‡
- CTBC: `https://ir.ctbcholding.com/html/index` †
- Nan Shan: own site ?

---

## 5. Order of work and stop conditions

1. **Observation Station first.** Build the (a), (b), (c) panel for all 20 firms; establish history depth; reconcile quarter-end sums to CBC table 8. Stop and report depth before doing anything else.
2. **CBC table 8 and footnote.** Sector history to 1987; hedge footnote series to the earliest PDF. Stop.
3. **Statements for the six priority firms.** (e) and (d2), then (d1); target 2013 at minimum, earlier where PDFs exist. Stop and report per-firm depth.
4. **Statements for the remaining 14 firms.** Same extraction; accept sparser (d1).
5. **Presentations.** Only now.
6. FSC monthly release loaded as a cross-check series.

If at any point a session finds itself parsing a press release, a news page, or a presentation before step 5, that is the signal that it has drifted; stop and return to this file.

---

## 6. Allowlist entries required for sections 1–4

```
*.ib.gov.tw           # www, ins-info †
*.fsc.gov.tw          # stat (API) ‡, law ?, www (cross-check only) †
*.cbc.gov.tw          # www †, cpx ‡
*.tii.org.tw          # www †, sv ‡, insdb ‡, law ‡
data.gov.tw           # ‡
*.lia-roc.org.tw      # ‡
*.twse.com.tw         # mops, mopsov, emops ‡
*.cathayholdings.com  # ?
*.cathaylife.com.tw   # ?
*.ir-cloud.com        # ?
*.irpro.co            # ‡
*.fubon.com           # ‡
*.tsholdings.com.tw   # ‡
*.kgi.com             # ‡
*.kgilife.com.tw      # ‡
ir.ctbcholding.com    # †
*.todayir.com         # †
*.nanshanlife.com.tw  # ?
```
