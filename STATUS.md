# TLFX — status

Current state only. History lives in `docs/decisions.md`.

**Stage 0 (Scaffold) — complete, 2026-09-03.** Stages 1–7 not started.

## What runs

| Command | Does | State |
|---|---|---|
| `python3 scripts/check_allowlist.py` | Probes one URL per allowlisted host, writes `reports/allowlist_YYYYMMDD.json` | Working. Exit 1 if any tier-1 host is unreachable |
| `python3 scripts/check_allowlist.py --tier 1` | Tier-1 only (fast pre-flight for Stages 1–2) | Working |

`src/tlfx/provenance.py` provides `fetch()`, `Provenance`, `RunLog`,
`ReconciliationCheck`, the two basis enums and the per-host UA policy. Import
via `sys.path.insert(0, 'src')` until the package is installed.

## What is populated

Nothing. All 11 tables in schema `tlfx` exist and are empty.

Project `term-premium-atlas` (`xzhoykybwlkefgvgwnii`), migration
`supabase/migrations/0001_tlfx_schema.sql` applied. RLS enabled on every table,
no permissive policy — ingestion uses the service role.

`entities`, `sector_monthly`, `sector_balance_sheet`, `firm_quarterly`,
`cbc_fx_ops`, `bis_lbs_tw`, `market_daily`, `derived_series`, `run_log`,
`run_source_status`, `run_reconciliation`.

## Network reachability (2026-09-03)

Tier 1 (Stages 1–2 critical path): **6 of 6 reachable.** FSC ch + en, Insurance
Bureau, CBC table-8 CSV, CBC swap page, CBC statistics database.

Tier 2: **15 of 21.** Tier 3: **6 of 8.**

Outstanding failures, with the workaround each needs:

| Host | Symptom | Workaround |
|---|---|---|
| `www.tii.org.tw`, `sv.`, `insdb.`, `law.` | `CONNECT tunnel failed, 502` | Blocked at sandbox egress, not by the source. Needs an environment allowlist entry before Stage 3 |
| `www.ir-cloud.com` | 403 to all agents | Use `www.cathayholdings.com` (reachable) for Cathay |
| `www.irpro.co` | 403 to all agents | Use `www.fubon.com` (reachable) for Fubon |
| `media-ctbc.todayir.com` | 403 to all agents | Reach CTBC PDFs via `ir.ctbcholding.com` (reachable with browser UA) |
| `data.imf.org` | 403 | Optional source (COFER); no action needed |

`www.bis.org/statistics/full_data_sets.htm` is now 404 — BIS bulk downloads have
moved to `data.bis.org/bulkdownload`. Config updated.

## Outstanding before Stage 1

1. **Decision needed from the user:** apply the recommended `--gold` re-step
   (`#8A6A12` light, `#B08C38` dark) to the §2 tokens of
   `docs/artifact_design_system.md`, or keep the current values and accept two
   failing checks. See `docs/decisions.md` 0.3.
2. **Locate the monthly FSC release.** id=96 is confirmed but is the all-FSC
   list; the monthly profit/loss-and-FX release was not on page 1. Stage 1 must
   paginate with a title filter, or use the Insurance Bureau's own page.
   See `docs/decisions.md` 0.10.
3. **TII egress.** Four TII hosts are blocked at the sandbox proxy. Not needed
   until Stage 3, but resolve before starting it.
4. `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` / `FRED_API_KEY` are not set in
   this environment; see `.env.example`.

## Conventions that bind every later stage

- NT$ amounts stored in NT$ million as published; no unit coercion on ingest.
- Every row carries `source_url`, `source_doc`, `retrieved_at`, `vintage`.
  Revisions are kept, never overwritten: `(natural key, vintage)` is unique.
- `accounting_basis` and `measurement_basis` are separate types and must not be
  conflated (`docs/decisions.md` 0.5).
- Unamortised FX differences are a memo column, never a buffer tier.
- Reconciliation tolerance is 3%; a breach fails the run.
- Charts with 4+ series use `dash` as well as hue (`docs/decisions.md` 0.2).
