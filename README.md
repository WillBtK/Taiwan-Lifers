# Taiwan Lifer FX Hedge Monitor (TLFX)

Automated tracker of Taiwanese life insurers' foreign-currency exposure, FX hedge ratios and loss-absorption buffers. First leg of a cross-market hedged-FX-exposure series (Taiwan, Japan, Korea); the Japan leg reuses the JLIM Phase 2 definitions so that the economic hedge ratio is comparable across markets.

Conventions follow the existing monitors: DS-Lite architecture, free public data only, full provenance on every observation, data stored in the `term-premium-atlas` Supabase project, and one self-contained HTML artifact per release built to the design system in `docs/artifact_design_system.md`.

`docs/artifact_design_system.md` is a project-agnostic replication spec supplied by the user and copied into this repo unchanged. It is authoritative and byte-literal: CSS tokens, component classes and JS helpers are pasted verbatim, charts are hand-built inline SVG with no charting library, no external fonts or stylesheets, no runtime network calls, and all content is generated from a single embedded JSON blob. Only the content of the artifact — sections, series, copy — is authored here. Do not restyle, rename classes, or substitute a chart library.

**Start here:** read section 7 (build stages) and section 8 (model routing) before running anything. Stage 0 runs on Opus 5.

---

## 1. Questions the monitor answers

1. **USD vulnerability.** How large is the unhedged USD position of Taiwanese lifers (level, share of assets, share of GDP, multiple of capital), what buffers sit against it, and how does that compare with Japanese and Korean lifers?
2. **Structural demand for USD bonds.** How are regulatory and accounting changes (IAS 21 departure, FX volatility reserve mechanism, TW-ICS, FX-policy rules) and cyclical factors (carry, basis) changing the lifers' demand for foreign — overwhelmingly USD — bonds, and the hedging attached to it?

Both questions are answered from the same series stack (section 3). Interpretation notes and references are in sections 9 and 10.

---

## 2. Background in one paragraph

Setser and S.T.W. (2019) established the accounting: lifers hedged ~USD 250bn of ~USD 465bn foreign assets; banks supplied ~USD 60bn of hedges; the CBC's undisclosed swap book (estimated USD 130bn, 90% CI 60–200bn) filled most of the rest. Since then: (i) foreign assets reached ~USD 700bn; (ii) the CBC began disclosing its USD/TWD swap balance and net FX purchases, and in November 2025 committed with the US Treasury to quarterly IRFCL-template disclosure; (iii) the May 2025 TWD shock produced a record NT$145.4bn monthly FX loss; (iv) the FSC responded with a departure from IAS 21 (amortisation of FX differences on undesignated amortised-cost bonds, effective FY2026) and a restructured four-bucket FX price-fluctuation reserve (February 2026); (v) the regulatory hedge ratio fell from ~60% (2020–24) to 50.2% (Dec 2025) and 42.9% (Jun 2026), with industry guidance of ~40%; (vi) IFRS 17 and TW-ICS went live on 1 January 2026, changing firm-level disclosure formats; (vii) Taishin Life absorbed Shin Kong Life on 1 January 2026 (surviving entity renamed Shin Kong Life, under TS Financial Holding).

---

## 3. Series stack (in publication order)

| # | Series | Definition | Level | Freq. | Start |
|---|--------|------------|-------|-------|-------|
| 1 | **Economic hedge ratio** (headline) | (derivative hedges + FX-denominated policy liabilities) / foreign-currency assets | sector + firm | M (sector), Q (firm) | 2011 (firm); sector 2024-04, gated by the ratio — see §4.1 |
| 2 | **Net open FX position** | foreign-currency assets − FX policy liabilities − derivative hedges, stored in NT$ million. USD, % GDP, % assets and × capital are presentations of the same series, selected in the artifact by a unit toggle — never a second y-axis | sector + firm | M / Q | sector 2024-04 / firm 2011 |
| 3 | **Buffer coverage** | tiers as % of net open FX position and as implied absorbable TWD appreciation. v1 (to 2025): (a) FX price-fluctuation reserve; (b) + equity. v2 (2026→, four named buckets of the Feb 2026 notice): (a) 波動準備金 + 固定準備金 (liability side, offset FX losses); (b) + 特別盈餘公積–外匯風險固定準備 (equity); (c) 特別盈餘公積–外匯風險強化準備 shown separately as restricted capital — it cannot offset losses; (d) memo: unamortised FX differences, not loss-absorbing | sector + firm | M / Q | 2020 |
| 4 | **Regulatory hedge ratio** | FSC definition (2026 notice §(九)): traditional hedge principal / (foreign investments − FX-policy liabilities − unhedged non-FVTPL equities and funds). Never printed in the monthly release (decisions 1.2); the Bureau's own portal is the source of record, the press briefing the current fallback. v1/v2 is a definitional break at the Feb 2026 notice, not a channel break | sector | M | published **2024-04** — earlier press mentions are spoken ranges, not the figure (decisions 1.11). Reconstructed from the release's own P&L lines back to **2019-05** as `reg_hedge_ratio_pl_implied`, `basis = estimated`, validated against the published anchors at 4.4pp MAE (decisions 4.29) |
| 5 | **Gross hedge ratio** | derivative hedges / foreign assets (the figure most sell-side and press quote) | sector + firm | M / Q | firm 2011; sector gated as series 1 |
| 6 | **Hedge composition** | CS, NDF, proxy, FX policy, open — shares and NT$ | firm | Q | 2011 |
| 7 | **Hedge cost** | reported annualised hedging cost (bp of foreign assets) vs market implied cost from CBC USD/TWD forwards by tenor. **The two firm series are not on one definition** — Fubon's behaves as an all-in ex-ante carry (0.51x market over 26 quarters), Cathay's exceeds the market cost in 3 of 11 quarters and cannot; do not draw them as one line (decisions 4.30) | firm + market | Q / M | firm 2011; **market 1992-01** |
| 8 | **Counterparty residual** | lifer hedges − bank supply (BIS LBS + CBC net FX position) − CBC swap book (disclosed) → residual to foreign/other | sector | Q | 2010 |
| 9 | **Flow diagnostics** | net foreign bond purchases (BoP other-sector debt securities), Formosa and bond-ETF holdings, new FX-policy premiums, lifer USD sub-debt issuance | sector | M / Q | 2010 |

Sign and unit conventions: all NT$ series stored in NT$ million as published; USD conversions use the CBC month-end closing rate stored alongside; GDP from DGBAS, annualised four-quarter sum.

Reconciliation checks (fail the run if breached by > 3%):
- FSC net exposure ≈ regulatory denominator × (1 − regulatory ratio). The denominator is only given at year-end briefings; holds for 2025-12 within 0.5% (decisions 1.2).
- FX-policy-backed assets ≈ total foreign investments − regulatory denominator. Needs Stage 2/3 inputs; not runnable from sector data alone.
- Sector economic ratio from firm panel (asset-weighted, six largest) within 5pp of sector ratio from FSC data.
- Stage 1 additionally checks every release edition's arithmetic, the cross-edition reserve-balance ties, and the Feb 2026 notice's bucket identities on the press-reported rows (decisions 1.7).

---

## 4. Data sources

**Sourcing hierarchy — work down it, and record why when you stop short.**

1. **Structured open data** published by the agency (`data.gov.tw`, agency CSV/XBRL endpoints).
2. **The regulator's own disclosure portal** — for insurers this is
   保險業公開資訊觀測站 (`ins-info.ib.gov.tw`), the Insurance Bureau's statutory
   platform, and for listed entities the legacy MOPS (`mopsov.twse.com.tw`).
3. **Statutory filings** on the filer's own site (financial statements, published
   under 人身保險業辦理資訊公開管理辦法).
4. **Investor-relations material** — decks and presentations.
5. **Press reporting** of a briefing.

Tiers 4 and 5 are presentation layers: a deck states a rounded chart label where
the filing states an audited amount, and a newspaper states what a journalist
heard. Use them where the higher tiers genuinely do not carry the figure, say so
explicitly in `docs/decisions.md`, and prefer the highest tier that does.

This was learned the expensive way. Stage 1 built the hedge-ratio series off
press articles without first checking the regulator's own disclosure portal;
`money.udn.com` then turned out to purge at twelve months, and the recoverable
press series began in 2024 rather than 2020 (decisions 1.9–1.11, 3.2–3.4). An
unreachable higher-tier source is a finding to record and escalate, not a reason
to silently drop a tier.

### 4.1 Sector-level (FSC / Insurance Bureau)
Monthly press release "Profit/loss, net value and exchange gains/losses of the insurance industry". **Measured at Stage 1 across all 91 editions:** it carries pre-tax profit and owners' equity (life / non-life / total), FX gains/losses, hedging P&L (instrument P&L and swap cost, split from 2020-01), the reserve's net change, the life insurers' FX price-fluctuation reserve balance, the TWD move YTD and (2020-09→) net foreign-investment income. It does **not** carry the hedge ratio, a hedging-cost rate, the foreign-investment total, the regulatory exposure or the reserve buckets — those are stated at the Insurance Bureau's monthly briefing and reach the public through the press (see "Briefing channel" below). English and Chinese versions; Chinese carries more detail. Parser: `src/tlfx/fsc_parse.py`; ingestion: `scripts/stage1_sector_monthly.py`.
- English press list: `https://www.fsc.gov.tw/en/home.jsp?id=54&parentpath=0,2`
- Chinese press list: `https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2` — **confirmed 2026-09-03**
- Insurance Bureau press list (mirrors the same releases): `https://www.ib.gov.tw/ch/home.jsp?id=239&parentpath=0,2`
- Insurance Bureau statistics: `https://www.ib.gov.tw/ch/home.jsp?id=48&parentpath=0,4`; official statistical returns `id=385`
- Foreign-currency policy new premiums: monthly Insurance Bureau release, title `壽險業{ROC year}年截至{month}月底外幣保險商品銷售情形`.

Both press lists are the same CMS and expose a POST search form (`keyword`,
`qptdate`, `qdldate`, `page`, `pagesize`). Query it by keyword and filter on
title — never by page position, since the list interleaves banking, securities
and insurance releases. `src/tlfx/fsc.py` implements this against both channels.

**The Insurance Bureau's own disclosure portal — try this before the press.**
保險業公開資訊觀測站, `https://ins-info.ib.gov.tw/`, is the statutory disclosure
platform for insurers: per-company pages (`customer/life.aspx?UID=…`,
`Info2-2.aspx`, `Info2-3.aspx`) and aggregate tables, among them 表06021011
財務報告彙總 and 表06161610 壽險財務業務指標. Every insurer publishes there under
人身保險業辦理資訊公開管理辦法. The same indicators are also on `data.gov.tw`
(dataset 7191, 壽險財務業務指標) as structured open data.

**Reachability, measured (2026-09-05, decisions 4.13).** Ingestion is split by
egress, not by source type, because three sources were "unreachable" for three
different reasons and only one was real.

| Source | Sandbox | GitHub runner | Cause |
|---|---|---|---|
| `ins-info.ib.gov.tw` | times out | times out | origin refuses non-Taiwan egress |
| `www.tigf.org.tw` | 403 | 200 | our proxy's policy only |
| `openapi.tii.org.tw` | 200 | 200 with the repo's TWCA cert | missing intermediate |
| `data.gov.tw` | 200 | 200 | open |

`scripts/fetch_sources.py` fetches all of them, writes each payload verbatim to
`data/raw/<source>/<name>_YYYYMMDD.<ext>` and deduplicates on content hash;
`.github/workflows/fetch-sources.yml` runs it weekly and commits what is new.
ins-info needs Taiwan egress, so it goes through an optional relay
(`ops/taiwan-relay/`); when the relay is unconfigured those sources are
recorded unavailable and the run still succeeds. The manual courier route
(decisions 4.10) produces byte-identical files and remains a valid fallback.

**Briefing channel (fallback for series 4 and, from 2026, the reserve buckets).**
The Insurance Bureau briefs reporters the day each month's figures are ready and
the hedge ratio, buckets and net exposure reach the public through Economic Daily
(`money.udn.com`), cnyes and CNA (carried by CTS). Ingested
(`config/briefing_press.json`, verified against the fetched articles by
`scripts/stage1_briefing_press.py`, `basis = 'press_reported'`,
`reporting_channel = 'briefing_press'`): 66% (Apr 2024), 66.39% (Dec 2024),
63.07% (Apr 2025), 62.25% (Aug 2025), 58.55% (Oct 2025), 50.23% (Dec 2025), 47%
(Jan 2026), 45.1% (Feb), 45.15% (Mar), 44.31% (Apr), 43.66% (May), 42.89% (Jun),
42.94% (Jul); FX reserve + special reserves NT$915.6bn (Feb) → NT$1,083.3bn
(Jul); net FX exposure NT$8.61tn (Mar) → NT$9.04tn (Jul).

Two measured properties of this channel that bound what it can deliver
(decisions 1.10–1.11, ledger in `docs/briefing_coverage.md`):

- **`money.udn.com` purges at about twelve months.** Search engines still serve
  cached snippets of purged stories, so an old article looks reachable and 404s
  on fetch. `news.cnyes.com` retains to 2020 and is the archive channel.
- **The ratio series effectively starts 2024-04.** Before that the press gives
  spoken ranges ("約六至七成"), which are commentary and must never be stored as
  the regulatory figure. A pre-2024 sector ratio therefore does not exist in this
  channel at all, whatever the briefing series' own start date.

The Life Insurance Association publishes no hedge or FX data. Firm financial
statements carry the mandated disclosures quarterly (notice §10) and are the
provenance-clean source (§4.5).

**Coverage, measured 2026-09-03.** The monthly release
(`{ROC year}年{month}月保險業損益、淨值，以及兌換損益、避險損益與外匯價格變動準備金`)
runs to 91 editions from May 2018 to December 2025: March 2019 has no edition
under any title on either channel, and March 2020 is retitled
(`…兌換損益、避險損益與外匯價格變動準備金情形`, without the profit and equity
sections). **It stops there.** No 2026 edition exists on either channel; the
series ended at the IFRS 17 / TW-ICS transition on 1 January 2026, and the
briefing channel above carries the sector figures from then on — see
`docs/decisions.md` 0.11 and 1.1–1.4.

### 4.2 Sector balance sheet (CBC)
Financial Statistics Monthly, appendix table 8 "Life insurance companies' balance sheet" (人壽保險公司資產負債統計表), CSV/XLS.
- Index page: `https://www.cbc.gov.tw/tw/np-532-1.html`
- Direct CSV (path stable, contents roll monthly): `https://www.cbc.gov.tw/public/data/EBOOKXLS/065_EF67_A4L.csv`
- Statistics database (for history): `https://cpx.cbc.gov.tw/Tree/TreeSelect`
- Annual "Financial institutions business overview" (life insurers, tables 7.1–7.2): `https://www.cbc.gov.tw/tw/cp-977-169739-a8c52-1.html`

### 4.3 CBC FX operations and reserves
- USD/TWD FX swap outstanding and FX call-loan balance (the disclosed swap book): `https://www.cbc.gov.tw/tw/lp-4197-1.html`
- Net FX purchases/sales (intervention series): `https://www.cbc.gov.tw/tw/lp-6305-1.html`
- International reserves and foreign-currency liquidity (IRFCL template, quarterly from 2026): `https://www.cbc.gov.tw/tw/lp-6294-1.html`
- CBC balance sheet (for the 2019 PnL-regression backfill): `https://www.cbc.gov.tw/public/data/EBOOKXLS/025_EF23_A4L.csv`
- Banks' net FX position and daily turnover: `https://www.cbc.gov.tw/public/data/EBOOKXLS/155_EG47_A4L.csv`
- USD/TWD forward rates (onshore): `https://www.cbc.gov.tw/public/data/EBOOKXLS/163_EG55_A4L.csv`
- Balance of payments / IIP: `https://www.cbc.gov.tw/tw/lp-538-1.html`, `https://www.cbc.gov.tw/tw/lp-539-1.html`
- English site root: `https://www.cbc.gov.tw/en/mp-2.html`

### 4.4 Taiwan Insurance Institute (TII)
Life insurance statistics (fund utilisation, foreign investment share, monthly premium tables). The servers omit their TWCA intermediate certificate; `tlfx.provenance.fetch` supplies it from `config/certs/` (decisions 1.5) — use `fetch`, or pass `verify=ca_bundle_for(url)`, for these hosts.
- Statistics index: `https://www.tii.org.tw/tii/information/information1/000001.html`
- Actuarial/statistics query system: `https://sv.tii.org.tw/`
- Database service: `https://insdb.tii.org.tw/`
- Regulations database: `https://law.tii.org.tw/`

### 4.5 Firm-level (statutory filings first, IR decks second)

**Use the life company's own filing code, not its holding company's.** The
holdco financials consolidate banking and securities and are not the insurer.
The two were conflated in an earlier draft of this section.

| Life company | Filing code | Holding company | Holdco code |
|---|---|---|---|
| 國泰人壽 Cathay Life | **5846** | Cathay FHC | 2882 |
| 富邦人壽 Fubon Life | **5865** | Fubon FHC | 2881 |
| 南山人壽 Nan Shan Life | **5874** | — (unlisted) | — |
| 凱基人壽 KGI Life (ex-China Life) | **2823** | KGI FHC | 2883 |
| 新光人壽 Shin Kong Life | **6985** (2026-on only) | TS Financial (merged) | 2887, formerly 2888 |
| 台灣人壽 Taiwan Life | **2833** | CTBC FHC | 2891 |

2823 was verified directly against MOPS; 5846, 5865 and 5874 appear on the
companies' own filed documents; 2833 and 6985 come from the TWSE open-data
registry of public companies (`openapi.twse.com.tw/v1/opendata/t187ap03_P`,
decisions 3.13). **6985 is the surviving ex-Taishin Life entity's code**: its
pre-2026 filings are Taishin Life's, not Shin Kong Life's, so pre-merger
Shin Kong statements need the old code, which is not yet verified.

**Statutory statements.** Reach them through the legacy MOPS, which serves plain
HTML and accepts POST — the new `mops.twse.com.tw` returns an 800-byte JS shell,
and an earlier note dismissing "MOPS" wholesale as JS-rendered was wrong about
the legacy host and closed off this route for a whole stage. The sequence, and
the download gate that still blocks the last step, are in decisions 3.3.
Insurers also publish the same statements on their own sites under
人身保險業辦理資訊公開管理辦法, which avoids MOPS entirely and is usually easier.

- Legacy MOPS: `https://mopsov.twse.com.tw/` (English `https://emops.twse.com.tw/`)
- Statement documents: `https://doc.twse.com.tw/server-java/t57sb01` (index reachable by GET; file download gated)

**What a statement actually carries** — check before designing around it. The one
Cathay Life statement parsed so far gives derivative **fair values** by
instrument family and discloses 名目本金 only for related-party trades, not the
total book. A fair value is not a hedge notional, so that vintage cannot yield a
hedge ratio on its own. Whether current filings can, under IFRS 9 hedge
accounting and notice §10, is unresolved and is the first thing to test.

**IR decks.** A presentation layer, but the only place a firm-level hedge *ratio*
is currently known to be stated. Cathay's "FX hedging strategy" page carries the
FX asset base, the hedging structure split, the FX-policy split, a hedging-cost
strip and an FX volatility reserve strip. 112 decks back to 2011 Q4, and **all
sampled vintages are machine-readable text**. Values are rounded chart labels and
must be bound to their captions through the pie wedge, not by proximity
(decisions 3.1).

- Cathay: `https://www.cathayholdings.com/holdings/ir/financial_information/results_presentation` (also hosts Cathay Life statutory statements; `www.cathaylife.com.tw` is 403 at the sandbox egress, `www.ir-cloud.com` blocks automated clients)
- Fubon: `https://www.fubon.com/life/Investors/public-info/` (structured 財務概況 disclosure section); `https://www.irpro.co/2881/` blocks automated clients
- Nan Shan: `https://www.nanshanlife.com.tw/` — quarterly 財務概況 PDFs at `portal-api/File/{id}`
- KGI Life: `https://www.kgilife.com.tw/`
- TS Financial: `https://www.tsholdings.com.tw/`
- CTBC: `https://ir.ctbcholding.com/html/index`; `media-ctbc.todayir.com` and `www.ctbcholding.com` block automated access

Panel-continuity notes: (i) Shin Kong pre-2026 series continues under the merged entity — keep `entity_id` stable and record the merger as a break; (ii) IFRS 17 / TW-ICS change the presentation of investments and equity from Q1 2026 — store both bases where firms provide them; (iii) Cathay and Fubon disclose hedge composition (CS/NDF/proxy) and hedging cost; others disclose less — schema must tolerate missing fields.

### 4.6 Counterparty leg
- BIS locational banking statistics (Taiwan by residence, currency breakdown): portal `https://data.bis.org/topics/LBS/data`; SDMX API `https://stats.bis.org/api/v2/` (docs `https://stats.bis.org/api-doc/v1/`); bulk `https://www.bis.org/statistics/full_data_sets.htm`
- US Treasury FX report (semi-annual; Taiwan intervention estimates): `https://home.treasury.gov/policy-issues/international/macroeconomic-and-foreign-exchange-policies-of-major-trading-partners-of-the-united-states`

### 4.7 Market and macro
- USD/TWD daily (FRED DEXTAUS): `https://fred.stlouisfed.org/series/DEXTAUS`, API `https://api.stlouisfed.org/`
- GDP: DGBAS `https://www.stat.gov.tw/` (and `https://www.dgbas.gov.tw/`)
- Formosa bonds and bond ETFs: TPEx `https://www.tpex.org.tw/`
- IMF COFER (for the 2019-style other-currency adjustment, optional): `https://data.imf.org/`
- Offshore NDF points: not free; user-supplied Bloomberg windows around key dates, as in the NL-WTP repo.

---

## 5. Network allowlist

Wildcards are needed where an organisation serves data from several hosts. † = fetched and confirmed live; ‡ = surfaced in search, not fetched; ? = unverified. **`config/allowlist.tsv` is the operational source of truth** — it carries one probe URL per host with a measured status, and `scripts/check_allowlist.py` re-probes it. Its columns are `host / tier / probe_url / expect / note`, where `expect` is blank or an integer status code; status words belong in the note.

```
# Regulators and official statistics (Taiwan)
*.fsc.gov.tw          # www (en/ch press releases) †
*.ib.gov.tw           # Insurance Bureau † — BUT ins-info.ib.gov.tw (the statutory
                      #   disclosure portal, tier 2 of the §4 hierarchy) does not route to
                      #   this egress even when allowlisted (4.9); files come by courier (4.10)
data.gov.tw           # open data, reachable since 2026-09-04 (front-end API, no key; 4.9).
                      #   Highest tier of the §4 hierarchy; dataset 7191 = 壽險財務業務指標
*.cbc.gov.tw          # www (stats, FX ops), cpx (database), law †
*.tii.org.tw          # www, sv, insdb, law † (insdb needs a member login)
*.stat.gov.tw         # DGBAS ‡
*.dgbas.gov.tw        # DGBAS alternate host ?
*.tpex.org.tw         # Formosa bonds, bond ETFs ‡
*.twse.com.tw         # mopsov † serves PLAIN HTML and accepts POST — use it.
                      #   mops (new) is an 800-byte JS shell; doc.twse.com.tw serves the
                      #   statement index by GET but gates the file download. Rate-limited

# Insurers / holding companies
*.cathayholdings.com  # Cathay IR † — also hosts Cathay Life statutory statements
*.cathaylife.com.tw   # Cathay Life own site — 403 at the sandbox egress; use cathayholdings
*.ir-cloud.com        # Cathay IR hosting — 403 to automated clients
*.fubon.com           # Fubon IR † (life 財務概況 under /life/Investors/public-info/)
*.irpro.co            # Fubon monthly PDFs — 403 to automated clients
*.tsholdings.com.tw   # TS Financial (Shin Kong Life) ‡
*.kgi.com             # KGI Financial ‡
*.kgilife.com.tw      # KGI Life †
ir.ctbcholding.com    # CTBC IR † (www.ctbcholding.com is robots-blocked — deliberately excluded)
*.todayir.com         # CTBC PDFs (media-ctbc.todayir.com) — 403 to automated clients
*.nanshanlife.com.tw  # Nan Shan † — quarterly 財務概況 at portal-api/File/{id}

# Press (fallback tier only — see the §4 hierarchy)
money.udn.com         # Economic Daily † — PURGES AT ~12 MONTHS; search still serves
                      #   cached snippets of purged stories, which 404 on fetch
news.cnyes.com        # cnyes † — retains to 2020; the archive channel. api.cnyes.com is
                      #   403, so cnyes site search cannot be driven server-side
news.cts.com.tw       # CNA via CTS † (www.cna.com.tw and udn.com apex are 403)

# International data
*.bis.org             # www, data, stats ‡
home.treasury.gov     # FX reports ‡ (single host, no wildcard needed)
*.stlouisfed.org      # fred, api ‡
*.imf.org             # data.imf.org (optional) ?

# Storage
*.supabase.co
api.supabase.com

# Reference (read-only, not ingested)
www.cfr.org
concentratedambiguity.wordpress.com
```

Apex vs www: every Taiwanese official site redirects apex to `www`; the insurer sites are mixed. Use wildcards rather than enumerating hosts. If the sandbox cannot express wildcards, enumerate: `www.`, `cpx.`, `law.` for cbc; `www.`, `sv.`, `insdb.`, `law.` for tii; `data.`, `stats.`, `www.` for bis; `mops.`, `mopsov.`, `mopsfin.`, `emops.` for twse; `media-ctbc.` for todayir.

---

## 6. Supabase schema (sketch)

Schema `tlfx`, all tables with `source_url`, `source_doc`, `retrieved_at`, `vintage` columns for provenance.

- `entities` — `entity_id`, name (en/zh), ticker, holding company, `valid_from`, `valid_to`, `successor_entity_id`.
- `sector_monthly` — FSC monthly: foreign investments, regulatory FX exposure, hedge ratio, hedge cost, FX reserve buckets (p, q, x, y), fixed special reserve, FX gains/losses, hedging gains/losses, equity. `reporting_channel` is part of the natural key alongside `(obs_month, vintage)` — one month can carry both a `release` and a `briefing_press` row, on different bases (migration 0004, decisions 1.3).
- `sector_balance_sheet` — CBC table 8 line items, monthly.
- `firm_quarterly` — foreign assets, FX policy liabilities (or reserves), traditional hedge (CS, NDF), proxy hedge, open position, hedge cost bp, recurring yield pre/post hedge, FX reserve balance, equity, RBC/ICS ratio; `basis` column (IFRS4 / IFRS17).
- `cbc_fx_ops` — swap balance, FX call loans, net FX purchases, IRFCL forward leg, reserves.
- `bis_lbs_tw` — cross-border and local positions by currency.
- `market_daily` — USD/TWD spot, onshore forward points (CBC), user-supplied NDF windows.
- `derived_series` — the nine published series with `definition_version`, plus `source_url`, `source_doc`, `retrieved_at`, `vintage` and `basis` carried through from the upstream tables. The artifact is built from this table alone, so provenance must survive the derivation step; otherwise Stage 6 cannot write its source lines without re-querying upstream.
- `run_log` — per-run source status, reconciliation check results.

---

## 7. Build stages and stopping points

Each stage ends with: a runnable script, a populated table, a reconciliation report, an updated `STATUS.md`, and any new conventions appended to `docs/decisions.md`. Stop at the end of every stage; switch model per section 8.

**Stage 0 — Scaffold.** Repo layout, allowlist test (`scripts/check_allowlist.py` fetches one URL per host and records status), Supabase schema migration, provenance helpers, `docs/decisions.md` created. Place the user-supplied `artifact_design_system.md` in `docs/` unchanged — do not summarise it, and do not read it into context at this stage. The only edits ever permitted to it are the amendments the spec itself mandates in its §7 (record a palette-validation outcome) and §10 (carry a discovered gap forward), each logged in `docs/decisions.md`. Confirm the Chinese FSC press-list `id` here. Validate the six-hue categorical palette (`--blue`, `--orange`, `--teal`, `--purple`, `--gold`, `--rose`) for colour-vision-deficiency safety against both the light (`#FFFFFF`) and dark (`#1A1E24`) surfaces, record the outcome as an amendment in `docs/artifact_design_system.md` §7 as that spec directs, and log the dash-encoding convention in `docs/decisions.md` — series 6 needs five hues, so the provisional `--gold`/`--rose` extension is on the critical path and should not be discovered at Stage 6. Stop.

**Stage 1 — Sector series from the FSC (2020–present).** Parse the monthly press release (Chinese primary, English fallback) into `sector_monthly`; build series 4, 3(a), and the FX-policy-backed asset figure; reconciliation checks. Backfill from the FSC press archive. Stop.

**Stage 2 — Sector balance sheet from the CBC.** Ingest table 8 CSV monthly and the statistics database for history to 2000; derive foreign assets and equity. Table 8 is done (`scripts/stage2_cbc_balance_sheet.py`; 2016-12 year-ends, monthly 2024-10→, three identities exact on every row); `cpx.cbc.gov.tw` history is outstanding. Stop.

**Stage 2/3 ordering — inverted in practice, and the reason matters.** Sector
series 1, 2 and 5 were to be derived here by combining Stage 1's ratio with a
CBC denominator. That does not work: the ratio only exists from 2024-04
(decisions 1.11), and CBC 國外資產 differs from the FSC 國外投資 the regulatory
ratio is defined against by 2.3% at 2024-12 widening to 3.47% at 2025-12 — past
the 3% tolerance, and definitional rather than coverage, since CBC and FSC equity
tie to 0.00–0.03% across all 23 overlapping months (decisions 2.1). Pairing the
two mixes bases. **Run Stage 3 before deriving sector series 1/2/5**, and resolve
the foreign-asset gap first.

**Stage 3 — Firm panel (2011–present).** Statutory filings first, IR decks second
(§4.5). Produce series 1, 2, 5, 6, 7 at firm level; asset-weighted sector
cross-check. Handle the Shin Kong merger and the IFRS 17 basis change. **Do not
budget for hand-coding**: an earlier draft assumed 2013–2019 PDFs would not be
machine-readable, and every deck vintage sampled from 2014 to 2026 extracts as
text (19k–38k characters). What does need work is layout variance across
vintages, not OCR. Stop.

**Stage 4 — Buffers.** Add reserve buckets and equity tiers; produce series 3 fully; implied absorbable appreciation. Requires the February 2026 four-bucket guidelines to define P/Q/X/Y precisely. Stop.

**Stage 5 — Counterparty leg.** CBC swap and net-purchase series, IRFCL forward leg, BIS LBS Taiwan by currency, CBC bank net FX position; produce series 8; optionally re-run the 2019 PnL regression on the CBC balance sheet as a pre-2020 backfill and cross-check. Stop.

**Stage 6 — Flows and artifact.** Series 9; then the monthly artifact. Read `docs/artifact_design_system.md` in full at the start of this stage (it is ~48kB and is the single largest context cost in the build — read it once, here, and nowhere else). Paste the CSS tokens and JS helpers verbatim, export the published series from `derived_series` into the `#data-blob` JSON payload, and author only the sections, chart series and copy. Inverted-pyramid structure: headline economic hedge ratio and net open position first, then buffers, then composition and cost, then the counterparty residual. Series carrying a `basis` break — disclosed versus estimated CBC series, IFRS 4 versus IFRS 17 firm series — render the affected segment dashed with a `.chip` marking the break, never as a continuous line. Scheduled run: monthly after the FSC release (~last week of month), quarterly after firm results. Stop.

**Stage 7 — Cross-market hooks.** Export `derived_series` in the common schema used by JLIM Phase 2 so the Taiwan, Japan and Korea economic hedge ratios can be joined.

---

## 8. Model routing

Stage 0 runs on Opus 5: the schema, the provenance and `basis`-flag conventions, and the allowlist script shape everything downstream, and a schema error surfacing at Stage 3 is expensive to unwind. The stage is short, so the absolute token cost is small.

| Stage | Model | Rationale |
|---|---|---|
| 0 Scaffold | **Opus 5** | Schema and conventions are load-bearing |
| 1 FSC sector | **Opus 5** | Rated Sonnet on the assumption of bounded parsing. It was not: establishing which fields the release does *not* carry, and that the press ratio series starts 2024 not 2020, was the substance of the stage |
| 2 CBC balance sheet | Sonnet 5 for table 8; **Opus 5** for the basis question | Table 8 is mechanical. Deciding whether CBC 國外資產 may stand in for FSC 國外投資 is not, and it gates series 1/2/5 |
| 3 Firm panel | **Opus 5** for the extraction schema, the Shin Kong merger and the IFRS 17 break; **Sonnet 5** for the per-firm scrapers once one works end-to-end | Six heterogeneous disclosure formats, two structural breaks. No OCR budget needed — see Stage 3 |
| 4 Buffers | **Opus 5** | Judgement on which buckets are loss-absorbing on a going-concern basis |
| 5 Counterparty leg | **Opus 5** | BIS dimension selection; splicing disclosed against estimated CBC series |
| 6 Flows + artifact | **Opus 5** for artifact structure and copy; **Sonnet 5** for the verbatim chrome and the `#data-blob` export | The spec fixes the chrome but leaves section order, chart-type selection and all prose to the author (spec §§8–9) — the editorial half is a judgement task |
| 7 Cross-market export | Sonnet 5 | Mapping to an existing schema |

Use **Haiku 4.5** inside stages for repetitive work — re-running a proven scraper across months, bulk downloads, reconciliation reruns — not as a stage owner.

**Design spec handling.** `docs/artifact_design_system.md` is ~48kB and is read in full exactly once, in Stage 6. It is not needed in Stages 0–5 and must not be pulled into context there; Stage 0 only copies the file into place. The chrome — CSS tokens, component classes, JS helpers — is pasted verbatim and needs no judgement; the content is not. Spec §9 leaves section order, chart-type selection, the series driving each chart and all copy to the author, and spec §8 imposes a decision-document register: inverted pyramid at page and panel level, a lede carrying a number, counterarguments in the body rather than an appendix. Route that half to Opus 5. The file must be read whole in one pass, so do not split the artifact build across sessions if it can be avoided.

**Decisions log convention.** The efficiency gain that matters more than model choice is not re-deriving context. At the end of every stage, append to `docs/decisions.md`: the decision, the reason, the alternative rejected, and the files affected. `STATUS.md` holds current state only (what runs, what is populated, what is outstanding). A Sonnet or Haiku stage should be able to start from these two files plus this README, without re-reading the repo.

---

## 9. Interpretation notes and known pitfalls

- The regulator now also quotes an "effective hedge ratio" that adds the reserve stock to the hedged share (55% at June 2026 against 42.89% nominal). Publish it as a memo line with its construction stated; do not headline it — it mixes a flow hedge with a stock buffer.
- The regulatory ratio's denominator excludes FX-policy-backed assets and unhedged non-FVTPL equities and funds; the gross ratio excludes neither. With FX-policy sales growing 30–50% y/y, the gross ratio falls mechanically. Publish all three ratios; headline the economic ratio.
- FX policies are a balance-sheet match, not a behavioural one: surrender periods and charges are short, so a sharp TWD rally could see policyholders redenominate. Carry a stressed variant that haircuts the policy match.
- The 2026 amortisation rule applies only to amortised-cost bonds with no designated FX hedge. It defers recognition; it does not absorb losses. Never count unamortised FX differences as a buffer.
- Remaining hedges are mostly short-dated and marked to market while the hedged assets are not; this creates a further incentive to reduce hedging (Setser 2026, fn.).
- **The hedge ratio is NOT carry-sensitive, on this project's own measurements.** This line previously asserted that it was, inherited from sell-side commentary and never tested. Tested at decisions 4.31 against the reconstructed ratio (4.29) and the market cost series (4.30): cost explains R² 0.23 alone but a plain time trend explains 0.47, and cost retains nothing once the trend is removed (t = −0.51). One observation settles it without any regression — between 2024-08 and 2025-11 the 24-month mean carry **fell** from 4.27% to 3.28% while the hedge ratio fell from 75.9% to 59.2%, its steepest decline in the sample. The decline is a steady structural trend of about 2.6pp a year, sustained across regimes in which carry was 0.3% and 4.3%, which points at the reserve regime, the FX-policy push and IFRS 17 rather than at price. Model the composition from the measured series in `data/cathay_fx_quarterly.csv`, not from this section's earlier anecdotes. **Two claims previously here failed verification against the decks themselves** (decisions 3.9): "CS/NDF ~15% in 2022" — the deck series runs 59% (9M21) → 65% (1Q22) → 64% (1H22, 9M22) → 56% (FY22), nowhere near 15; and "~69% in Q1 2026" sits against a page-verified 36% at 1H26, where the 1M26 reclassification into AC (proxy & open 60%) is the likelier story. What the measured series does show: the share collapsed from ~63% (FY24) to 36% (1H26), and FY22's *cost* collapsed to 0.14% on TWD depreciation while the share stayed 56% — carry moves the cost faster than the book.
- CBC disclosure changed in stages (swap balance from 2020; quarterly IRFCL and intervention from 2026). Do not splice disclosed and estimated series without a `basis` flag.
- Taiwan is not an IMF member; there is no IMF IRFCL page for Taiwan — the template is published by the CBC itself.
- **Legacy MOPS (`mopsov.twse.com.tw`) serves plain HTML and accepts POST;** only the new `mops.twse.com.tw` is JS-rendered. An earlier blanket note here said otherwise and pushed the project onto IR decks for a whole stage. MOPS does rate-limit (a 307 to a security page), so pace requests. Prefer, in order: the Insurance Bureau's own portal, the insurer's own statutory publication, legacy MOPS, then IR material.

---

## 10. References (Chicago author-date)

- Financial Supervisory Commission. 2025. "FSC announces proposed amendments to the Regulations Governing the Preparation of Financial Reports by Insurance Enterprises as concerns foreign exchange gains and losses." Press release, 23 December 2025.
- Financial Supervisory Commission. 2026. 人身保險業外匯價格變動準備金應注意事項修正規定. Notice, 12 February 2026. Saved as `docs/sources/fsc_2026-02-12_fx_reserve_notice.pdf`.
- Financial Supervisory Commission. 2018–2026. "{ROC year}年{month}月保險業損益、淨值，以及兌換損益、避險損益與外匯價格變動準備金." Monthly press releases, May 2018 – December 2025 (91 editions; the series has no 2026 edition on either the FSC or Insurance Bureau press channel as at 3 September 2026).
- Setser, Brad W. 2026. "Taiwan's Backdoor Currency Manipulation." Follow the Money, Council on Foreign Relations, 26 January 2026.
- Setser, Brad W., and Joshua Younger. 2025. "How Taiwan became a quiet bond market superpower." Financial Times, May 2025.
- Setser, Brad W., and S.T.W. 2019. "Shadow FX Intervention in Taiwan: Solving a USD 100+ bn Enigma." Council on Foreign Relations / Concentrated Ambiguity, October 2019.
- Hsieh, Chang-tai. 2026. "The AI Boom's Hidden Victim: Taiwan's Fragile Insurance Sector." CommonWealth Magazine 844, 17 March 2026.
- Central Bank of the Republic of China (Taiwan) and US Department of the Treasury. 2025. Joint statement on exchange-rate policy, 14 November 2025.
- Bank for International Settlements. Locational Banking Statistics. data.bis.org.
- McGuire, Patrick, and Goetz von Peter. 2009. "The US Dollar Shortage in Global Banking and the International Policy Response." BIS Working Papers 291.
- Borio, Claudio, Robert McCauley, Patrick McGuire, and Vladyslav Sushko. 2016. "Covered Interest Parity Lost: Understanding the Cross-Currency Basis." BIS Quarterly Review, September.
