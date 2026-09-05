# TLFX — status

Current state only. History lives in `docs/decisions.md`.

**Stage 1 complete (2026-09-03). Stage 2 data complete (2026-09-04):** the
sector balance sheet is loaded monthly from 1987-05, and the monthly FSC-basis
foreign-investment denominator is loaded 2017-01 → 2026-04 (`ib_indicators`
channel); the FSC/CBC basis question is settled — a stable 2.4–4.2%
classification wedge (decisions 2.3/2.4), so series 1/2/5 derivation is
unblocked. **Stage 3 deck side effectively done:** Cathay (both channels),
Fubon (49 periods incl. colour-bound recurring cost and a 2005→1Q07 era-A
backfill) and KGI (20 periods) are extracted, loaded and checksum-verified;
out of scope with reasons on record: Fubon 2008-13 (ING-merger panels,
multi-column era — 3.15/3.19), KGI pre-2023 (no archive), Taiwan Life / Shin
Kong decks (holdco IR hosts proxy-blocked). **Statement side landed:** all six entities carry
statement data — Cathay from the Excel companions (2020→), the other five
from MOPS XBRL, whose derived 2026 FX-reserve balances tie the Fubon and KGI
decks exactly (decisions 4.5). The bulk MOPS crawl is **withdrawn as
impractical** (~12 min/quarter against the WAF, and background processes die
when the session idles — 4.3); a targeted queue with ~7 requests left
replaces it, run in the foreground. **Stage 4 under way:** sector derived
series loaded (8 keys, 2024-04 → 2026-07, 4.1) and firm series loaded (194
rows — Fubon's disclosed economic hedge ratio over 36 quarters plus both
firms' hedge-cost series, split discrete/cumulative after 4.4). The 41億
reserve gap is closed as immaterial (4.8) and the KGI cost definition is
pinned as all-in (4.6). One judgement is open and flagged for the user: the
Cathay composition-pie base (4.2/4.7). **Firm-level statutory ratios
and balance sheets landed by courier** (dataset 7191 → `firm_statutory_indicators`,
4.10; 表06021011 → `firm_statutory_balance`, tying the statement channel exactly
for all six firms, 4.11). The CBC's quarterly life-insurer RBC/ROA/ROE series
is open and cached, queued for a sector-quarterly table with Stage 5 (4.12).
Stages 5–7 not started.

## What runs

| Command | Does | State |
|---|---|---|
| `python3 scripts/check_allowlist.py [--tier 1]` | Probes one URL per allowlisted host, writes `reports/allowlist_YYYYMMDD.json` | Working |
| `python3 scripts/stage1_sector_monthly.py [--offline] [--refresh] [--limit N]` | Locates all editions of the FSC monthly release on both press channels, caches and parses them, runs checks, writes `data/sector_monthly_release.csv`, `out/stage1_release_YYYYMMDD.sql`, `reports/stage1_release_YYYYMMDD.json` | Working: 91 editions, 423/423 checks |
| `python3 scripts/stage2_cbc_balance_sheet.py [--refresh]` | Parses CBC table 8 CSV (Big5, rolling window) into long format, runs the three balance-sheet identities, writes `data/sector_balance_sheet.csv`, `out/stage2_cbc_*.sql`, report | Working: 30 months, 96/96 checks |
| `python3 scripts/stage2_cbc_history.py [--refresh]` | Fetches CBC statistics-database API item EF67M01 (monthly, 1987-05→), validates identities and exact agreement with the CSV channel, writes `data/sector_balance_sheet_history.csv`, `out/stage2b_*.sql`, report | Working: 471 months, 1316/1316 checks |
| `python3 scripts/stage3_cathay_decks.py [--csv] [--limit N]` | Indexes Cathay's 112 results decks, extracts the FX hedging page (wedge-bound pies, tiered validity), writes `data/cathay_deck_fx.csv` | Working: 44 quarters extracted |
| `python3 scripts/stage2c_ib_indicators.py [--refresh] [--limit N]` | Walks the Insurance Bureau's monthly 保險市場重要指標 archive (id=48), parses 表17-1 人身保險業資金運用表 (page selected by value scale — titles print on the preceding page), ties each edition's 資產總額 to CBC table 8, writes `data/ib_indicators_monthly.csv`, `out/stage2c_ib_*.sql`, report | Working: 112 months, 112/112 ties (two named tolerance exceptions: IFRS-17-era 2026, disrupted 2020-03) |
| `python3 scripts/stage3_load_cathay.py` | Maps `data/cathay_fx_quarterly.csv` (merged deck series) into `firm_quarterly` SQL — period → quarter, tn/bn → mn, % → bp, IFRS17 from 2026 | Working: 47 rows |
| `python3 scripts/stage3_cathay_statements.py` | Parses the cached Cathay Life statement Excels (2020→), extracts FX volatility reserve / total assets / equity, derives 2026 reserve via cash-flow net change, joins the deck series, emits CSV + `firm_quarterly` SQL | Working: 26 quarters, 28/28 checks |
| `python3 scripts/stage3_ib_firm_indicators.py` | Maps every couriered `data/raw/ins-info/json-06161610_YYYYMMDD.json` (dataset 7191 payload) into `firm_statutory_indicators` SQL, positional AMOUNT mapping, collision guard, per-column checksums | Working: 30 rows, 1 snapshot |
| `python3 scripts/stage2d_sector_series.py` | Loads the CBC life-insurer soundness series (quarterly ROA/ROE/RBC/assets-GDP) and the guaranty-fund stock/bond holdings (monthly) from `data/raw/`, converts 億元 to NT$ mn, asserts the RBC semi-annual publication pattern | Working: 41 + 40 rows, 4/4 checks |
| `python3 scripts/fetch_sources.py` | Fetches every source the current egress can reach, writes payloads verbatim to `data/raw/<source>/`, dedupes on content hash; run weekly by the `fetch-sources` workflow | Working |
| `python3 scripts/stage3_ib_firm_balance.py` | Maps couriered `json-06021011_YYYYMMDD.json` (表06021011 財務報告彙總) into `firm_statutory_balance` SQL; A=L+E on every record, exact statement ties for the panel firms, checksums | Working: 52 rows, ties 6/6 |
| `python3 scripts/stage1_briefing_press.py [--refresh]` | Fetches the press articles cited in `config/briefing_press.json`, verifies every figure against its article, converts units, runs the v2 identity checks, writes `data/sector_monthly_briefing.csv`, `out/stage1_briefing_YYYYMMDD.sql`, `reports/…json`, `docs/sources/press/briefing_excerpts.md` | Working: 14 months, 16/16 checks |

Write path: the scripts emit idempotent SQL (`insert … on conflict do
nothing` on the natural key); it is applied with the Supabase MCP or psql.
Schema `tlfx` is not exposed through PostgREST, so `--write` (direct POST)
needs that setting changed before it can be used.

Library: `src/tlfx/fsc.py` (locate releases), `fsc_parse.py` (parse one
edition), `emit.py` (CSV / SQL / report), `provenance.py` (`fetch`,
`ca_bundle_for`, `Provenance`, `RunLog`, `ReconciliationCheck`, basis enums).
Import via `sys.path.insert(0, 'src')`.

## What is populated

`tlfx.sector_monthly` — 217 rows in three channels (select on
`reporting_channel`; a month can carry several). `tlfx.
sector_balance_sheet` — **6,967 rows, 471 months, 1987-05 → 2026-07** (CBC
table 8: statistics-database API for history, rolling CSV for the current
window; the two agree exactly on every overlapping cell, and the CSV row wins
the shared key). Loads are checksum-verified server-side against the local CSVs
(row count, total sum, spot values, identities — decisions 2.2).

| Channel | Rows | Months | Basis | Carries |
|---|---|---|---|---|
| `release` | 91 | 2018-05 → 2025-12 (no 2019-03; 2020-03 lacks profit/equity) | `disclosed` | pre-tax profit, equity (life / non-life / total), FX table (FX P&L, hedging P&L — split from 2020-01, reserve net change, total), life FX reserve balance, TWD move YTD, net foreign-investment income (2020-09→) |
| `ib_indicators` | 112 | 2017-01 → 2026-04, complete | `disclosed` | FSC-basis 國外投資 (the regulatory hedge-ratio denominator) and 資產總額, monthly, from 表17-1 of the Bureau's key-indicators PDFs; each month's column label proven by a CBC total-assets tie; vintage = PDF upload date; 2026 figures are IFRS 17 and current-year figures unaudited per the table's own note |
| `briefing_press` | 14 | 2024-04, 2024-12, 2025-04, 2025-08, 2025-09, 2025-10, 2025-12, 2026-01 → 2026-07 | `press_reported` | regulatory hedge ratio; from 2026-02 the P/Q/X/Y buckets, buffer total, net FX exposure, absorbable appreciation, effective-ratio memo; denominators at 2024-12, 2025-09, 2025-10, 2025-12 — hedge principal derivable at the ratio-bearing three: 10.36tn → 8.90tn → 7.74tn NT$ |

Migrations applied: `0001`–`0011`. `0003` adds the release fields, `0004`
puts `reporting_channel` in the primary key, `0005` admits the
`ib_indicators` channel, `0006` adds deck share columns and the
`source_channel` key to `firm_quarterly`, `0007` adds `deck_composition`
and `total_fx_cost_bp`, `0008` adds `firm_statutory_indicators`, `0009` `firm_statutory_balance`, `0010` corrects two indicator
column comments, `0011` adds the sector soundness and holdings tables.
`tlfx.entities` holds the six firms (decisions 3.10). `tlfx.firm_quarterly`
holds three firms' deck series — Cathay 47 quarters, **Fubon 49 (2013-Q4 →
2026-Q2, all-in FX cost + colour-bound recurring cost + composition —
decisions 3.15/3.17/3.18), KGI 20 (2020-Q4 → 2026-Q2, yield, FX-reserve
path, composition; its cost series stays CSV-only pending definition —
3.16)** — plus Cathay in both channels: **deck — 47 quarters, 2013-Q4 → 2026-Q2**
(shares, cost in bp, FX volatility reserve; en/zh cross-confirmed — decisions
3.11) and **statement — 26 quarters, 2020-Q1 → 2026-Q2** (FX volatility
reserve, total assets, equity at NT$-thousand precision from the Excel
statement companions; 2026 reserve derived exactly via the cash-flow net
change and tied to the deck — decisions 3.12). Both loads checksum-verified.
2012–2019 statements are PDF-only, unextracted. The **statement channel also
carries the five non-Cathay firms** — 11 rows from MOPS XBRL (Fubon and Nan
Shan 2025Q4 plus 2026 quarters for all five), whose derived 2026 reserve
balances tie the Fubon and KGI decks exactly (decisions 4.5), so all six
entities are now populated. **`tlfx.firm_statutory_indicators` — 30 rows**, the
Insurance Bureau's 23 statutory ratios per life insurer (ins-info 表06161610 /
data.gov.tw 7191), one snapshot vintage 2026-09-04 couriered by the user,
latest quarter per insurer (active firms 2026-Q2); 7 rows link to the panel
(decisions 4.10). **`tlfx.firm_statutory_balance` — 52 rows**, the Bureau's
財務報告彙總 (表06021011): assets, liabilities, equity, paid-in capital in NT$
thousand for every supervised insurer (30 life, 22 non-life), snapshot
2026-09-05; the six panel firms tie the statement channel exactly to the
NT$ thousand and the pre-merger Shin Kong 2025Q4 anchor is now on record
(decisions 4.11). Other tables remain empty.
`tlfx.derived_series` — **sector 55 rows / 8 keys, 2024-04 → 2026-07**
(reg hedge ratio and the Bureau's effective memo, denominator, net open,
hedge principal, gross hedge ratio, buffer total, absorbable appreciation —
decisions 4.1) and **firm 194 rows** (Fubon economic hedge ratio and net-open
share, 36 quarters 2014 → FY25; Fubon and Cathay recurring hedge cost in bp,
split into discrete-quarter and cumulative series because the decks print
both and they differ materially — decisions 4.4).
No economic hedge ratio is published for Cathay or for Fubon 2026: the
composition pie's base is not stated there (decisions 4.2).
Run logs and check rows are in `tlfx.run_log`, `run_source_status`,
`run_reconciliation`.

## Findings that bind later stages

- **The monthly release never carried the hedge ratio, hedging-cost rate,
  foreign-investment total or reserve buckets** (all 91 editions checked).
  Series 4 is press-reported from the Insurance Bureau's monthly briefing for
  its entire life, 2020 onwards; the release ended at December 2025.
- **Series 4 coverage now:** 2024-04, 2024-12, 2025-04, 2025-08, 2025-10,
  2025-12, and every 2026 month to July (42.89%). The backfill is a press
  search, not a parse, and it is **sparse by nature, not by neglect**: no
  contemporaneous article carrying the ratio was found anywhere in 2020-01 →
  2024-03, and the June 2020 monthly write-up carries the release's field set
  with no ratio at all (`docs/decisions.md` 1.10, ledger in
  `docs/briefing_coverage.md`). Plan pre-2024 sector series 1/2/5 around
  year-end anchors plus the six-firm panel, not a monthly briefing series.
  **Search cnyes, not udn**, for anything older than a year — udn purges.
- **README §3 checks 1–2 need the regulatory denominator**, which only the
  year-end briefing gives. Check 1 holds for 2025-12 within 0.5%; check 2 moves
  to Stages 2–3.
- **Flow items are YTD** as published (`flows_are_ytd`). Monthly flows are a
  derivation for `derived_series`.
- **2026 profit/equity figures are IFRS 17** and not comparable with 2025.
- **The 41億 year-end reserve gap is closed** (decisions 4.8): our two
  sector channels agree exactly at 2025-12 (613,700 NT$ mn), the four firms
  we hold sum to 59.86% of it in line with their asset share, and the gap is
  a 0.67% artefact of a third-party tabulation that no published series
  depends on.
- **Firm statements (v2 clean source):** Cathay's 2Q26 deck shows the FX
  volatility reserve at NT$130.9bn, matching the press tabulation of the Q2
  statements (1,309.3億); the 20-firm aggregate (6,997.3億) matches the June
  briefing. The 2025 year-end aggregate differs from the briefing by 41億 —
  Stage 3 must explain that before substituting the firm aggregate.

## Network reachability (2026-09-03)

**Press retention (measured 2026-09-03).** `money.udn.com` purges at roughly
twelve months — clean cliff between story 8947103 (404) and 8974899 (200, dated
2025-08-31). `news.cnyes.com` retains to 2020 and earlier (15/15 sampled ids).
Search engines still serve cached snippets of purged udn stories, so an old
article can look reachable and 404 on fetch. `api.cnyes.com` is 403 at the
proxy, so cnyes site search (client-rendered off it) is unusable.

Tier 1: 6 of 6. **TII resolved:** all four `*.tii.org.tw` hosts answer once
the TWCA intermediate the server omits is supplied (`config/certs/`,
`provenance.ca_bundle_for`). Media: `money.udn.com`, `news.cnyes.com`,
`news.cts.com.tw` fetch in full with the default UA; `udn.com` apex,
`www.cna.com.tw`, `www.chinatimes.com`, `www.ctee.com.tw`, `taronews.tw` are
403 at the proxy (Economic Daily ids are all served by `money.udn.com`; CNA
copy is carried by CTS). Unchanged from Stage 0: `www.ir-cloud.com`,
`www.irpro.co`, `media-ctbc.todayir.com`, `data.imf.org` blocked, with the
workarounds in `config/allowlist.tsv`. The FSC CMS occasionally resets a
tunnel; `fsc.search` and `fetch` retry transport errors with backoff.

## Outstanding

1. `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` not set in the environment
   (`FRED_API_KEY` is). Writes go through the MCP for now.
1a0. **No reachable open-data host replaces ins-info** (4.14): TII's 139 tables
   are catalogued in `config/tii_tables.tsv`, and its 38 firm-level tables are
   business volume only. Firm financials come from MOPS XBRL or ins-info,
   nowhere else.

1a. **Ingestion is now a weekly workflow** (`fetch-sources`, decisions 4.13),
   covering TIGF, TII and the data.gov.tw catalogue. Only `ins-info` still
   needs a human, because it refuses every egress CI has; deploying
   `ops/taiwan-relay/` to a Taiwan region and setting two repository secrets
   removes that last manual step. The relay is tested and its deployment is
   one command (`ops/taiwan-relay/deploy.sh`, run from Google Cloud Shell),
   but it needs the user's own cloud account, so it is theirs to run (4.15).
   Run `verify.sh` afterwards: Cloud Run's shared egress may not geolocate to
   Taiwan, and the fallback is a small VM in the same region. Until the two
   secrets exist, the courier queue below stands.

1b. **ins-info courier queue (for the user):** `data.gov.tw` is open (4.9);
   `ins-info.ib.gov.tw` is allowlisted but does not route to this egress, so
   its files arrive by courier (4.10). Next asks, in value order: the portal's
   column headers of 表06021011, which would name `amount4..8` (4.11); the
   historical query for either table per firm, which would turn the snapshots
   into panels; one per-company page (`customer/life.aspx?UID=…`) to see what
   else the portal carries; and `www.tigf.org.tw`'s monthly stock/bond
   holdings CSV (data.gov.tw 172653; host is a 403 policy denial — 4.12).
   The 指標說明 page is **no longer needed**: the growth-field functional form
   was settled from the data itself (4.10 revised). Insurer sites (`www.cathaylife.com.tw`, `www.taiwanlife.com`,
   `www.skl.com.tw`, `www.taishinlife.com.tw`, `www.tsfl.com.tw`) remain
   proxy-blocked.
2. Hedge-ratio backfill: the start of the series is now pinned — **2024-04**
   in practice (`docs/decisions.md` 1.11). Before that the press gives spoken
   ranges ("6~7成"), not the regulatory figure, so pre-2024 sector series 1/2/5
   go to the six-firm panel. Remaining: the 2020–2023 year-end anchors, the only
   months that also carry a denominator, and ratings-agency aggregates.
3. FSC/CBC gap settled (decisions 2.3/2.4): a stable 2.4–4.2%
   usage-vs-residence wedge, so ratios pair with the monthly FSC denominator
   in `ib_indicators`, never the CBC series. Remaining tidy-up: a wedge decomposition (FX deposits at domestic
   banks vs bond-ETF look-through) if it ever matters; the two once-unparsed
   editions are fixed and loaded (decisions 2.4).
4. Stage 3 next steps: statement-side extraction into the `statement` channel
   (Cathay Excel companions first — 58 quarters on cathayholdings); then
   Fubon, Nan Shan, KGI, Taiwan Life, Shin Kong (verify the last two firms'
   filing codes before touching any filing system — decisions 3.5). The
   41億 year-end reserve gap remains Stage 3's to explain. The FY22 en/zh
   binding conflict is resolved (wedge colour — decisions 3.9); the Cathay
   deck series is loaded (3.11).

The gold re-step is applied in the spec (all three `:root` blocks, §7/§10);
decisions 0.3's "not applied" was superseded in Stage 0 — see 1.8.

## Conventions that bind every later stage

- NT$ amounts stored in NT$ million as published (the release prints 億;
  ×100 is exact); no other unit coercion on ingest.
- Every row carries `source_url`, `source_doc`, `retrieved_at`, `vintage`.
  `vintage` is the publication date of the edition or article. Revisions are
  kept, never overwritten: `(obs_month, reporting_channel, vintage)` is the key.
- `accounting_basis` and `measurement_basis` are separate types
  (`docs/decisions.md` 0.5); `press_reported` is a measurement basis.
- Unamortised FX differences are a memo column, never a buffer tier.
- Reconciliation tolerance is 3% relative; a breach fails the run. Printed
  rounding (NT$ 1 億) is allowed on identity checks between tiny figures.
- Charts with 4+ series use `dash` as well as hue (`docs/decisions.md` 0.2).
- TLS verification is never disabled; a missing intermediate is supplied
  from `config/certs/` (`docs/decisions.md` 1.5).
