# TLFX — status

Current state only. History lives in `docs/decisions.md`.

**Stage 1 (FSC sector series) — complete, 2026-09-03.** Stage 0 complete.
Stages 2–7 not started.

## What runs

| Command | Does | State |
|---|---|---|
| `python3 scripts/check_allowlist.py [--tier 1]` | Probes one URL per allowlisted host, writes `reports/allowlist_YYYYMMDD.json` | Working |
| `python3 scripts/stage1_sector_monthly.py [--offline] [--refresh] [--limit N]` | Locates all editions of the FSC monthly release on both press channels, caches and parses them, runs checks, writes `data/sector_monthly_release.csv`, `out/stage1_release_YYYYMMDD.sql`, `reports/stage1_release_YYYYMMDD.json` | Working: 91 editions, 423/423 checks |
| `python3 scripts/stage1_briefing_press.py [--refresh]` | Fetches the press articles cited in `config/briefing_press.json`, verifies every figure against its article, converts units, runs the v2 identity checks, writes `data/sector_monthly_briefing.csv`, `out/stage1_briefing_YYYYMMDD.sql`, `reports/…json`, `docs/sources/press/briefing_excerpts.md` | Working: 13 months, 16/16 checks |

Write path: the scripts emit idempotent SQL (`insert … on conflict do
nothing` on the natural key); it is applied with the Supabase MCP or psql.
Schema `tlfx` is not exposed through PostgREST, so `--write` (direct POST)
needs that setting changed before it can be used.

Library: `src/tlfx/fsc.py` (locate releases), `fsc_parse.py` (parse one
edition), `emit.py` (CSV / SQL / report), `provenance.py` (`fetch`,
`ca_bundle_for`, `Provenance`, `RunLog`, `ReconciliationCheck`, basis enums).
Import via `sys.path.insert(0, 'src')`.

## What is populated

`tlfx.sector_monthly` — 104 rows in two channels (select on
`reporting_channel`; from 2024-04 a month can carry both):

| Channel | Rows | Months | Basis | Carries |
|---|---|---|---|---|
| `release` | 91 | 2018-05 → 2025-12 (no 2019-03; 2020-03 lacks profit/equity) | `disclosed` | pre-tax profit, equity (life / non-life / total), FX table (FX P&L, hedging P&L — split from 2020-01, reserve net change, total), life FX reserve balance, TWD move YTD, net foreign-investment income (2020-09→) |
| `briefing_press` | 13 | 2024-04, 2024-12, 2025-04, 2025-08, 2025-10, 2025-12, 2026-01 → 2026-07 | `press_reported` | regulatory hedge ratio; from 2026-02 the P/Q/X/Y buckets, buffer total, net FX exposure, absorbable appreciation, effective-ratio memo; year-end denominators for 2024 and 2025 |

Migrations applied: `0001`–`0004`. `0003` adds the release fields, `0004`
puts `reporting_channel` in the primary key. All other tables remain empty.
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
2. Hedge-ratio backfill: continue on cnyes with the `完全不避險` search key.
   Open pieces — pin the month monthly press reporting of the ratio begins
   (somewhere mid-2020 → early 2024), and recover the 2020–2023 year-end
   anchors, which are the only months also carrying the denominator.
3. Stage 2 (CBC table 8) next; Stage 3 should verify the §10 disclosures
   against Cathay's and Fubon's statutory Q2 2026 statements (deck seen, not
   the statement) and resolve the 41億 year-end gap above.

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
