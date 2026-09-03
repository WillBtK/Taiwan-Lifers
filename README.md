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
| 1 | **Economic hedge ratio** (headline) | (derivative hedges + FX-denominated policy liabilities) / foreign-currency assets | sector + firm | M (sector), Q (firm) | 2013 (firm), 2020 (sector) |
| 2 | **Net open FX position** | foreign-currency assets − FX policy liabilities − derivative hedges, stored in NT$ million. USD, % GDP, % assets and × capital are presentations of the same series, selected in the artifact by a unit toggle — never a second y-axis | sector + firm | M / Q | 2020 / 2013 |
| 3 | **Buffer coverage** | tiers as % of net open FX position and as implied absorbable TWD appreciation. v1 (to 2025): (a) FX price-fluctuation reserve; (b) + equity. v2 (2026→, four named buckets of the Feb 2026 notice): (a) 波動準備金 + 固定準備金 (liability side, offset FX losses); (b) + 特別盈餘公積–外匯風險固定準備 (equity); (c) 特別盈餘公積–外匯風險強化準備 shown separately as restricted capital — it cannot offset losses; (d) memo: unamortised FX differences, not loss-absorbing | sector + firm | M / Q | 2020 |
| 4 | **Regulatory hedge ratio** | FSC definition (2026 notice §(九)): traditional hedge principal / (foreign investments − FX-policy liabilities − unhedged non-FVTPL equities and funds). Stated at the Insurance Bureau's monthly press briefing and reported by the press — never printed in the monthly release (Stage 1, decisions 1.2). Press-reported for its whole life; v1/v2 is a definitional break at the Feb 2026 notice, not a channel break | sector | M | 2020 (briefing series; 2024-12 and 2025-08→ ingested so far) |
| 5 | **Gross hedge ratio** | derivative hedges / foreign assets (the figure most sell-side and press quote) | sector + firm | M / Q | 2013 |
| 6 | **Hedge composition** | CS, NDF, proxy, FX policy, open — shares and NT$ | firm | Q | 2013 |
| 7 | **Hedge cost** | reported annualised hedging cost (bp of foreign assets) vs market 3m CS/NDF implied cost | firm + market | Q / M | 2013 |
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

**Briefing channel (series 4 and, from 2026, the reserve buckets).** The Insurance Bureau briefs reporters the day each month's figures are ready — the same day the release used to be posted — and the hedge ratio, buckets and net exposure reach the public through Economic Daily (`money.udn.com`), cnyes and CNA (carried by CTS). This has been the only channel for the hedge ratio since the briefing series began in 2020. Ingested so far (`config/briefing_press.json`, verified against the fetched articles by `scripts/stage1_briefing_press.py`, stored with `basis = 'press_reported'`, `reporting_channel = 'briefing_press'`): 66.39% (Dec 2024), 62.25% (Aug 2025), 58.55% (Oct 2025), 50.23% (Dec 2025), 47% (Jan 2026), 45.1% (Feb), 45.15% (Mar), 44.31% (Apr), 43.66% (May), 42.89% (Jun), 42.94% (Jul); FX reserve + special reserves NT$915.6bn (Feb) → NT$1,083.3bn (Jul); net FX exposure NT$8.61tn (Mar) → NT$9.04tn (Jul). `money.udn.com`, `news.cnyes.com` and `news.cts.com.tw` fetch directly; `udn.com` apex, `www.cna.com.tw` and other outlets are blocked at the sandbox egress. The 2020-01 → 2025-07 monthly backfill is an open task. The Life Insurance Association publishes no hedge or FX data. Firm financial statements carry the mandated disclosures quarterly (notice §10) and are the provenance-clean v2 source (Stage 3).

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

### 4.5 Firm-level (quarterly investor presentations, annual reports)
Six-firm panel: Cathay Life (2882), Fubon Life (2881), Shin Kong Life / TS Financial (2887, formerly 2888), KGI Life (2883), Taiwan Life / CTBC (2891), Nan Shan Life (unlisted; annual report and public disclosures).
- Cathay: `https://www.cathayholdings.com/holdings/eng/ir` (IR hosting also at `https://www.ir-cloud.com/taiwan/2882/`)
- Fubon: `https://www.fubon.com/financialholdings/en/` (monthly PDFs at `https://www.irpro.co/2881/`)
- TS Financial: `https://www.tsholdings.com.tw/`
- KGI Financial: `https://www.kgi.com/en/`; KGI Life: `https://www.kgilife.com.tw/`
- CTBC: `https://ir.ctbcholding.com/html/index` (PDFs at `https://media-ctbc.todayir.com/`); note `www.ctbcholding.com` blocks automated access via robots.txt
- Nan Shan: `https://www.nanshanlife.com.tw/` (unverified — check on first run)
- Filings: MOPS `https://mops.twse.com.tw/` (JavaScript-rendered and rate-limited; legacy `https://mopsov.twse.com.tw/`, English `https://emops.twse.com.tw/`)

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

Wildcards are needed where an organisation serves data from several hosts. † = fetched and confirmed live during scoping (September 2026); ‡ = surfaced in search, not fetched; ? = unverified.

```
# Regulators and official statistics (Taiwan)
*.fsc.gov.tw          # www (en/ch press releases) †
*.ib.gov.tw           # Insurance Bureau ‡
*.cbc.gov.tw          # www (stats, FX ops), cpx (database), law †
*.tii.org.tw          # www, sv, insdb, law †
*.stat.gov.tw         # DGBAS ‡
*.dgbas.gov.tw        # DGBAS alternate host ?
*.tpex.org.tw         # Formosa bonds, bond ETFs ‡
*.twse.com.tw         # mops, mopsov, mopsfin, emops ‡ (JS-rendered; expect blocks)

# Insurers / holding companies
*.cathayholdings.com  # Cathay IR ‡
*.ir-cloud.com        # Cathay IR hosting ‡
*.fubon.com           # Fubon IR ‡
*.irpro.co            # Fubon monthly PDFs ‡
*.tsholdings.com.tw   # TS Financial (Shin Kong Life) ‡
*.kgi.com             # KGI Financial ‡
*.kgilife.com.tw      # KGI Life ‡
ir.ctbcholding.com    # CTBC IR † (www.ctbcholding.com is robots-blocked — deliberately excluded)
*.todayir.com         # CTBC PDFs (media-ctbc.todayir.com) †
*.nanshanlife.com.tw  # Nan Shan ?

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
- `sector_monthly` — FSC monthly: foreign investments, regulatory FX exposure, hedge ratio, hedge cost, FX reserve buckets (p, q, x, y), fixed special reserve, FX gains/losses, hedging gains/losses, equity.
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

**Stage 2 — Sector balance sheet from the CBC.** Ingest table 8 CSV monthly and the statistics database for history to 2000; derive foreign assets and equity; combine with Stage 1 to produce series 1, 2, 5 at sector level. Stop.

**Stage 3 — Firm panel (2013–present).** Scrape quarterly investor presentations for the six firms; hand-code the 2013–2019 history where PDFs are not machine-readable; produce series 1, 2, 5, 6, 7 at firm level; asset-weighted sector cross-check. Handle the Shin Kong merger and the IFRS 17 basis change. Stop.

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
| 1 FSC sector | Sonnet 5 | Bounded parsing against a stable release format |
| 2 CBC balance sheet | Sonnet 5 | Fixed CSV paths, mechanical |
| 3 Firm panel | **Opus 5** for the extraction schema, the Shin Kong merger and the IFRS 17 break; **Sonnet 5** for the per-firm scrapers once one works end-to-end | Six heterogeneous disclosure formats, two structural breaks |
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
- The hedge ratio is strongly carry-sensitive: Cathay ran CS/NDF at ~15% in 2022 and ~69% in Q1 2025 and Q1 2026. Model it as a function of the 3m differential, basis, reserve headroom and regime, not as a slow-moving preference.
- CBC disclosure changed in stages (swap balance from 2020; quarterly IRFCL and intervention from 2026). Do not splice disclosed and estimated series without a `basis` flag.
- Taiwan is not an IMF member; there is no IMF IRFCL page for Taiwan — the template is published by the CBC itself.
- MOPS is JavaScript-rendered and rate-limits scrapers; prefer holding-company IR sites and fall back to MOPS only for statutory statements.

---

## 10. References (Chicago author-date)

- Financial Supervisory Commission. 2025. "FSC announces proposed amendments to the Regulations Governing the Preparation of Financial Reports by Insurance Enterprises as concerns foreign exchange gains and losses." Press release, 23 December 2025.
- Financial Supervisory Commission. 2026. 人身保險業外匯價格變動準備金應注意事項修正規定. Notice, 12 February 2026. Saved as `docs/sources/fsc_2026-02-12_fx_reserve_notice.pdf`.
- Financial Supervisory Commission. 2018–2026. "{ROC year}年{month}月保險業損益、淨值，以及兌換損益、避險損益與外匯價格變動準備金." Monthly press releases, May 2018 – December 2025 (90 editions; the series has no 2026 edition on either the FSC or Insurance Bureau press channel as at 3 September 2026).
- Setser, Brad W. 2026. "Taiwan's Backdoor Currency Manipulation." Follow the Money, Council on Foreign Relations, 26 January 2026.
- Setser, Brad W., and Joshua Younger. 2025. "How Taiwan became a quiet bond market superpower." Financial Times, May 2025.
- Setser, Brad W., and S.T.W. 2019. "Shadow FX Intervention in Taiwan: Solving a USD 100+ bn Enigma." Council on Foreign Relations / Concentrated Ambiguity, October 2019.
- Hsieh, Chang-tai. 2026. "The AI Boom's Hidden Victim: Taiwan's Fragile Insurance Sector." CommonWealth Magazine 844, 17 March 2026.
- Central Bank of the Republic of China (Taiwan) and US Department of the Treasury. 2025. Joint statement on exchange-rate policy, 14 November 2025.
- Bank for International Settlements. Locational Banking Statistics. data.bis.org.
- McGuire, Patrick, and Goetz von Peter. 2009. "The US Dollar Shortage in Global Banking and the International Policy Response." BIS Working Papers 291.
- Borio, Claudio, Robert McCauley, Patrick McGuire, and Vladyslav Sushko. 2016. "Covered Interest Parity Lost: Understanding the Cross-Currency Basis." BIS Quarterly Review, September.
