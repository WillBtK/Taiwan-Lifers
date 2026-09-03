# Taiwan Lifer FX Hedge Monitor (TLFX)

Automated tracker of Taiwanese life insurers' foreign-currency exposure, FX hedge ratios and loss-absorption buffers. First leg of a cross-market hedged-FX-exposure series (Taiwan, Japan, Korea); the Japan leg reuses the JLIM Phase 2 definitions so that the economic hedge ratio is comparable across markets.

Conventions follow the existing monitors: DS-Lite architecture, free public data only, full provenance on every observation, data stored in the `term-premium-atlas` Supabase project, one self-contained HTML artifact per release built to `docs/artifact_design_system.md` (copy that file in unchanged from the previous repo).

---

## 1. Questions the monitor answers

1. **USD vulnerability.** How large is the unhedged USD position of Taiwanese lifers (level, share of assets, share of GDP, multiple of capital), what buffers sit against it, and how does that compare with Japanese and Korean lifers?
2. **Structural demand for USD bonds.** How are regulatory and accounting changes (IAS 21 departure, FX volatility reserve mechanism, TW-ICS, FX-policy rules) and cyclical factors (carry, basis) changing the lifers' demand for foreign — overwhelmingly USD — bonds, and the hedging attached to it?

Both questions are answered from the same series stack (section 3). Interpretation notes and references are in section 8.

---

## 2. Background in one paragraph

Setser and S.T.W. (2019) established the accounting: lifers hedged ~USD 250bn of ~USD 465bn foreign assets; banks supplied ~USD 60bn of hedges; the CBC's undisclosed swap book (estimated USD 130bn, 90% CI 60–200bn) filled most of the rest. Since then: (i) foreign assets reached ~USD 700bn; (ii) the CBC began disclosing its USD/TWD swap balance and net FX purchases, and in November 2025 committed with the US Treasury to quarterly IRFCL-template disclosure; (iii) the May 2025 TWD shock produced a record NT$145.4bn monthly FX loss; (iv) the FSC responded with a departure from IAS 21 (amortisation of FX differences on undesignated amortised-cost bonds, effective FY2026) and a restructured four-bucket FX price-fluctuation reserve (February 2026); (v) the regulatory hedge ratio fell from ~60% (2020–24) to 50.2% (Dec 2025) and 42.9% (Jun 2026), with industry guidance of ~40%; (vi) IFRS 17 and TW-ICS went live on 1 January 2026, changing firm-level disclosure formats; (vii) Taishin Life absorbed Shin Kong Life on 1 January 2026 (surviving entity renamed Shin Kong Life, under TS Financial Holding).

---

## 3. Series stack (in publication order)

| # | Series | Definition | Level | Freq. | Start |
|---|--------|------------|-------|-------|-------|
| 1 | **Economic hedge ratio** (headline) | (derivative hedges + FX-denominated policy liabilities) / foreign-currency assets | sector + firm | M (sector), Q (firm) | 2013 (firm), 2020 (sector) |
| 2 | **Net open FX position** | foreign-currency assets − FX policy liabilities − derivative hedges; in NT$, USD, % GDP, % assets, × capital | sector + firm | M / Q | 2020 / 2013 |
| 3 | **Buffer coverage** | three tiers, each as % of net open FX position and as implied absorbable TWD appreciation: (a) FX price-fluctuation reserve + fixed FX special reserve; (b) + equity; (c) memo: accounting deferral (unamortised FX differences, not loss-absorbing) | sector + firm | M / Q | 2020 |
| 4 | **Regulatory hedge ratio** | FSC definition: derivative hedges / (foreign investments − FX-policy-backed assets) | sector | M | 2020 |
| 5 | **Gross hedge ratio** | derivative hedges / foreign assets (the figure most sell-side and press quote) | sector + firm | M / Q | 2013 |
| 6 | **Hedge composition** | CS, NDF, proxy, FX policy, open — shares and NT$ | firm | Q | 2013 |
| 7 | **Hedge cost** | reported annualised hedging cost (bp of foreign assets) vs market 3m CS/NDF implied cost | firm + market | Q / M | 2013 |
| 8 | **Counterparty residual** | lifer hedges − bank supply (BIS LBS + CBC net FX position) − CBC swap book (disclosed) → residual to foreign/other | sector | Q | 2010 |
| 9 | **Flow diagnostics** | net foreign bond purchases (BoP other-sector debt securities), Formosa and bond-ETF holdings, new FX-policy premiums, lifer USD sub-debt issuance | sector | M / Q | 2010 |

Sign and unit conventions: all NT$ series stored in NT$ million as published; USD conversions use the CBC month-end closing rate stored alongside; GDP from DGBAS, annualised four-quarter sum.

Reconciliation checks (fail the run if breached by > 3%):
- FSC net exposure ≈ regulatory denominator × (1 − regulatory ratio).
- FX-policy-backed assets ≈ total foreign investments − regulatory denominator.
- Sector economic ratio from firm panel (asset-weighted, six largest) within 5pp of sector ratio from FSC data.

---

## 4. Data sources

### 4.1 Sector-level (FSC / Insurance Bureau)
Monthly press release "Profit/loss, net value and exchange gains/losses of the insurance industry" — hedge ratio, hedging cost, FX price-fluctuation reserve balance and buckets (P, Q, X, Y), exchange gains/losses, owners' equity. English and Chinese versions; Chinese carries more detail.
- English press list: `https://www.fsc.gov.tw/en/home.jsp?id=54&parentpath=0,2`
- Chinese press list: `https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2` (verify id on first run)
- Insurance Bureau statistics: `https://www.ib.gov.tw/` (Chinese: 保險局 → 統計資料)
- Foreign-currency policy new premiums: monthly Insurance Bureau release.

### 4.2 Sector balance sheet (CBC)
Financial Statistics Monthly, appendix table 8 "Life insurance companies' balance sheet" (人壽保險公司資產負債統計表), CSV/XLS.
- Index page: `https://www.cbc.gov.tw/tw/np-532-1.html`
- Direct CSV (path is stable, contents roll): `https://www.cbc.gov.tw/public/data/EBOOKXLS/065_EF67_A4L.csv`
- Statistics database (for history): `https://cpx.cbc.gov.tw/Tree/TreeSelect`
- Annual "Financial institutions business overview" (life insurers, tables 7.1–7.2): `https://www.cbc.gov.tw/tw/cp-977-169739-a8c52-1.html`

### 4.3 CBC FX operations and reserves
- USD/TWD FX swap outstanding and FX call-loan balance (the disclosed swap book): `https://www.cbc.gov.tw/tw/lp-4197-1.html`
- Net FX purchases/sales (buyback intervention series): `https://www.cbc.gov.tw/tw/lp-6305-1.html`
- International reserves and foreign-currency liquidity (IRFCL template, quarterly from 2026): `https://www.cbc.gov.tw/tw/lp-6294-1.html`
- CBC balance sheet (for the 2019 PnL-regression backfill): `https://www.cbc.gov.tw/public/data/EBOOKXLS/025_EF23_A4L.csv`
- Banks' net FX position and daily turnover: `https://www.cbc.gov.tw/public/data/EBOOKXLS/155_EG47_A4L.csv`
- USD/TWD forward rates (onshore): `https://www.cbc.gov.tw/public/data/EBOOKXLS/163_EG55_A4L.csv`
- Balance of payments / IIP: `https://www.cbc.gov.tw/tw/lp-538-1.html`, `https://www.cbc.gov.tw/tw/lp-539-1.html`
- English site root: `https://www.cbc.gov.tw/en/mp-2.html`

### 4.4 Taiwan Insurance Institute (TII)
Life insurance statistics (fund utilisation, foreign investment share, monthly premium tables).
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
- Nan Shan: `https://www.nanshanlife.com.tw/` (not yet validated — check on first run)
- Filings: MOPS `https://mops.twse.com.tw/` (JavaScript-rendered and rate-limited; legacy `https://mopsov.twse.com.tw/`, English `https://emops.twse.com.tw/`)

Panel-continuity notes: (i) Shin Kong pre-2026 series continues under the merged entity — keep `entity_id` stable and record the merger as a break; (ii) IFRS 17 / TW-ICS change the presentation of investments and equity from Q1 2026 — store both old and new bases where firms provide them; (iii) Cathay and Fubon disclose hedge composition (CS/NDF/proxy) and hedging cost; others disclose less — schema must tolerate missing fields.

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

Wildcards are needed where an organisation serves data from several hosts. Entries marked † were confirmed live during scoping (September 2026); entries marked ‡ were surfaced in search but not fetched; entries marked ? are unverified.

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
*.ctbcholding.com     # ir.ctbcholding.com † (www.ctbcholding.com robots-blocked)
*.todayir.com         # CTBC PDFs (media-ctbc.todayir.com) †
*.nanshanlife.com.tw  # Nan Shan ?

# International data
*.bis.org             # www, data, stats ‡
home.treasury.gov     # FX reports ‡
*.stlouisfed.org      # fred, api ‡
*.imf.org             # data.imf.org (optional) ?

# Storage
*.supabase.co
api.supabase.com

# Reference (read-only, not ingested)
www.cfr.org
concentratedambiguity.wordpress.com
```

Apex vs www: every Taiwanese official site redirects apex to `www`; the insurer sites are mixed. Use wildcards rather than enumerating hosts. `home.treasury.gov` is a single host and needs no wildcard. If the sandbox cannot express wildcards, enumerate: `www.`, `cpx.`, `law.` for cbc; `www.`, `sv.`, `insdb.`, `law.` for tii; `data.`, `stats.`, `www.` for bis; `mops.`, `mopsov.`, `mopsfin.`, `emops.` for twse; `ir.` and `www.` for ctbcholding; `media-ctbc.` for todayir.

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
- `derived_series` — the nine published series with `definition_version`.
- `run_log` — per-run source status, reconciliation check results.

---

## 7. Build stages and stopping points

Each stage ends with a runnable script, a populated table, a reconciliation report, and a short `STATUS.md` note. Stop and switch model/review at the end of each stage.

**Stage 0 — Scaffold.** Repo layout, allowlist test (`scripts/check_allowlist.py` fetches one URL per host and records status), Supabase schema migration, provenance helpers. Stop.

**Stage 1 — Sector series from the FSC (2020–present).** Parse the monthly press release (Chinese primary, English fallback) into `sector_monthly`; build series 4, 3(a), and the FX-policy-backed asset figure; reconciliation checks. Backfill from the FSC press archive. Stop.

**Stage 2 — Sector balance sheet from the CBC.** Ingest table 8 CSV monthly and the statistics database for history to 2000; derive foreign assets and equity; combine with Stage 1 to produce series 1, 2, 5 at sector level. Stop.

**Stage 3 — Firm panel (2013–present).** Scrape quarterly investor presentations for the six firms; hand-code the 2013–2019 history where PDFs are not machine-readable; produce series 1, 2, 5, 6, 7 at firm level; asset-weighted sector cross-check. Handle the Shin Kong merger and the IFRS 17 basis change. Stop.

**Stage 4 — Buffers.** Add reserve buckets and equity tiers; produce series 3 fully; implied absorbable appreciation. Stop.

**Stage 5 — Counterparty leg.** CBC swap and net-purchase series, IRFCL forward leg, BIS LBS Taiwan by currency, CBC bank net FX position; produce series 8; optionally re-run the 2019 PnL regression on the CBC balance sheet as a pre-2020 backfill and cross-check. Stop.

**Stage 6 — Flows and artifact.** Series 9; monthly artifact per `docs/artifact_design_system.md`; scheduled run (monthly after FSC release, ~last week of month; quarterly after firm results). Stop.

**Stage 7 — Cross-market hooks.** Export `derived_series` in the common schema used by JLIM Phase 2 so the Taiwan, Japan and Korea economic hedge ratios can be joined.

---

## 8. Interpretation notes and known pitfalls

- The regulatory ratio's denominator excludes FX-policy-backed assets; the gross ratio does not. With FX-policy sales growing 30–50% y/y, the gross ratio falls mechanically. Publish all three ratios; headline the economic ratio.
- FX policies are a balance-sheet match, not a behavioural one: surrender periods and charges are short, so a sharp TWD rally could see policyholders redenominate. Carry a stressed variant that haircuts the policy match.
- The 2026 amortisation rule applies only to amortised-cost bonds with no designated FX hedge. It defers recognition; it does not absorb losses. Never count unamortised FX differences as a buffer.
- Remaining hedges are mostly short-dated and marked to market while the hedged assets are not; this creates an incentive to reduce hedging further (Setser 2026, fn.).
- Hedge ratio is strongly carry-sensitive: Cathay ran CS/NDF at ~15% in 2022 and ~69% in Q1 2025 / Q1 2026. Model the ratio as a function of the 3m differential, basis, reserve headroom and regime, not as a slow-moving preference.
- CBC disclosure changed in stages (swap balance from 2020; quarterly IRFCL and intervention from 2026). Do not splice disclosed and estimated series without a `basis` flag.
- Taiwan is not an IMF member; there is no IMF IRFCL page for Taiwan — the template is published by the CBC itself.
- MOPS is JavaScript-rendered and rate-limits scrapers; prefer holding-company IR sites and only fall back to MOPS for statutory statements.

---

## 9. References (Chicago author-date)

- Financial Supervisory Commission. 2025. "FSC announces proposed amendments to the Regulations Governing the Preparation of Financial Reports by Insurance Enterprises as concerns foreign exchange gains and losses." Press release, 23 December 2025.
- Financial Supervisory Commission. 2026. Monthly press releases on insurance-industry profit/loss, net value and exchange gains/losses, January–July 2026.
- Setser, Brad W. 2026. "Taiwan's Backdoor Currency Manipulation." Follow the Money, Council on Foreign Relations, 26 January 2026.
- Setser, Brad W., and Joshua Younger. 2025. "How Taiwan became a quiet bond market superpower." Financial Times, May 2025.
- Setser, Brad W., and S.T.W. 2019. "Shadow FX Intervention in Taiwan: Solving a USD 100+ bn Enigma." Council on Foreign Relations / Concentrated Ambiguity, October 2019.
- Hsieh, Chang-tai. 2026. "The AI Boom's Hidden Victim: Taiwan's Fragile Insurance Sector." CommonWealth Magazine 844, 17 March 2026.
- Central Bank of the Republic of China (Taiwan) and US Department of the Treasury. 2025. Joint statement on exchange-rate policy, 14 November 2025.
- Bank for International Settlements. Locational Banking Statistics. data.bis.org.
- McGuire, Patrick, and Goetz von Peter. 2009. "The US Dollar Shortage in Global Banking and the International Policy Response." BIS Working Papers 291.
- Borio, Claudio, Robert McCauley, Patrick McGuire, and Vladyslav Sushko. 2016. "Covered Interest Parity Lost: Understanding the Cross-Currency Basis." BIS Quarterly Review, September.
