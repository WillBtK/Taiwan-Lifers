-- TLFX — Taiwan Lifer FX Hedge Monitor
-- Migration 0001: schema, enums, provenance contract, core tables.
-- Target project: term-premium-atlas.
--
-- Conventions (README sections 3 and 6):
--   * All NT$ amounts stored in NT$ million, as published. No unit coercion
--     on ingest; conversions happen in derived_series.
--   * Every table carries the four provenance columns. A row without
--     source_url and retrieved_at is not admissible.
--   * vintage is the publisher's reference date for the observation;
--     retrieved_at is when we fetched it. Revisions are kept, never
--     overwritten: (natural key, vintage) is unique, and the latest vintage
--     wins in the reporting views.
--   * basis flags definitional breaks. Two kinds exist and are separate
--     types: accounting_basis (IFRS 4 vs IFRS 17 / TW-ICS, from 2026-01-01)
--     and measurement_basis (CBC disclosed vs our estimate).

create schema if not exists tlfx;

-- ---------------------------------------------------------------- enums
do $$ begin
  create type tlfx.accounting_basis as enum ('IFRS4', 'IFRS17');
exception when duplicate_object then null; end $$;

do $$ begin
  -- 'spliced' marks a series deliberately joined across a break; the
  -- artifact renders those segments dashed, never as a continuous line.
  create type tlfx.measurement_basis as enum ('disclosed', 'estimated', 'spliced');
exception when duplicate_object then null; end $$;

do $$ begin
  create type tlfx.frequency as enum ('D', 'M', 'Q', 'A');
exception when duplicate_object then null; end $$;

do $$ begin
  create type tlfx.hedge_instrument as enum ('CS', 'NDF', 'proxy', 'fx_policy', 'open');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------- entities
create table if not exists tlfx.entities (
  entity_id            text primary key,
  name_en              text not null,
  name_zh              text,
  ticker               text,
  holding_company_en   text,
  holding_company_zh   text,
  is_listed            boolean not null default true,
  valid_from           date not null,
  valid_to             date,
  successor_entity_id  text references tlfx.entities (entity_id),
  break_note           text,
  source_url           text not null,
  source_doc           text,
  retrieved_at         timestamptz not null,
  vintage              date,
  constraint entities_validity check (valid_to is null or valid_to > valid_from)
);

comment on column tlfx.entities.successor_entity_id is
  'Set on the absorbed entity. Taishin Life absorbed Shin Kong Life on '
  '2026-01-01, surviving entity renamed Shin Kong Life under TS Financial '
  'Holding; entity_id of the continuing series is held stable and the '
  'merger recorded as a break (README section 4.5).';

-- ------------------------------------------------------- sector_monthly
-- FSC / Insurance Bureau monthly press release.
create table if not exists tlfx.sector_monthly (
  obs_month                   date not null,          -- first day of month
  vintage                     date not null,
  foreign_investments         numeric,                -- NT$ mn
  regulatory_fx_exposure      numeric,                -- NT$ mn, FSC denominator
  fx_policy_backed_assets     numeric,                -- NT$ mn, derived
  hedge_ratio_regulatory      numeric,                -- fraction, 0-1
  hedge_cost_bp               numeric,                -- annualised, bp
  fx_reserve_total            numeric,                -- NT$ mn
  fx_reserve_p                numeric,
  fx_reserve_q                numeric,
  fx_reserve_x                numeric,
  fx_reserve_y                numeric,
  fx_special_reserve_fixed    numeric,
  fx_gain_loss                numeric,                -- NT$ mn, month
  hedging_gain_loss           numeric,
  owners_equity               numeric,
  unamortised_fx_difference   numeric,                -- memo only: NOT a buffer
  usdtwd_month_end            numeric,
  source_url                  text not null,
  source_doc                  text,
  retrieved_at                timestamptz not null,
  primary key (obs_month, vintage),
  constraint hedge_ratio_regulatory_range
    check (hedge_ratio_regulatory is null
           or hedge_ratio_regulatory between 0 and 2)
);

comment on column tlfx.sector_monthly.unamortised_fx_difference is
  'Cumulative FX difference deferred under the 2026 departure from IAS 21. '
  'Defers recognition; it does not absorb loss. Never counted as a buffer '
  'tier (README section 9).';

-- -------------------------------------------------- sector_balance_sheet
-- CBC Financial Statistics Monthly, appendix table 8.
create table if not exists tlfx.sector_balance_sheet (
  obs_month        date not null,
  vintage          date not null,
  line_code        text not null,
  line_label_zh    text,
  line_label_en    text,
  value_ntd_mn     numeric,
  source_url       text not null,
  source_doc       text,
  retrieved_at     timestamptz not null,
  primary key (obs_month, line_code, vintage)
);

-- -------------------------------------------------------- firm_quarterly
create table if not exists tlfx.firm_quarterly (
  entity_id             text not null references tlfx.entities (entity_id),
  obs_quarter           date not null,   -- first day of quarter
  vintage               date not null,
  basis                 tlfx.accounting_basis not null,
  foreign_assets        numeric,         -- NT$ mn
  fx_policy_liabilities numeric,
  hedge_cs              numeric,
  hedge_ndf             numeric,
  hedge_proxy           numeric,
  open_position         numeric,
  hedge_cost_bp         numeric,
  recurring_yield_pre   numeric,
  recurring_yield_post  numeric,
  fx_reserve_balance    numeric,
  owners_equity         numeric,
  rbc_ratio             numeric,
  ics_ratio             numeric,
  total_assets          numeric,
  source_url            text not null,
  source_doc            text,
  retrieved_at          timestamptz not null,
  primary key (entity_id, obs_quarter, basis, vintage)
);

comment on table tlfx.firm_quarterly is
  'Six-firm panel. Disclosure is heterogeneous: Cathay and Fubon publish '
  'hedge composition and cost, others less, so most columns are nullable by '
  'design. basis is part of the key because firms report both IFRS 4 and '
  'IFRS 17 for the transition quarters.';

-- ------------------------------------------------------------ cbc_fx_ops
create table if not exists tlfx.cbc_fx_ops (
  obs_date          date not null,
  freq              tlfx.frequency not null,
  vintage           date not null,
  basis             tlfx.measurement_basis not null,
  swap_outstanding_usd_mn   numeric,
  fx_call_loans_usd_mn      numeric,
  net_fx_purchases_usd_mn   numeric,
  irfcl_forward_leg_usd_mn  numeric,
  reserves_usd_mn           numeric,
  estimate_ci_low_usd_mn    numeric,
  estimate_ci_high_usd_mn   numeric,
  source_url        text not null,
  source_doc        text,
  retrieved_at      timestamptz not null,
  primary key (obs_date, freq, basis, vintage),
  constraint estimate_ci_only_for_estimates
    check (basis = 'estimated'
           or (estimate_ci_low_usd_mn is null and estimate_ci_high_usd_mn is null))
);

-- ----------------------------------------------------------- bis_lbs_tw
create table if not exists tlfx.bis_lbs_tw (
  obs_quarter    date not null,
  vintage        date not null,
  series_key     text not null,     -- BIS SDMX key, stored verbatim
  measure        text not null,
  currency       text,
  counterparty   text,
  position_type  text,
  value_usd_mn   numeric,
  source_url     text not null,
  source_doc     text,
  retrieved_at   timestamptz not null,
  primary key (obs_quarter, series_key, vintage)
);

-- ---------------------------------------------------------- market_daily
create table if not exists tlfx.market_daily (
  obs_date            date not null,
  vintage             date not null,
  basis               tlfx.measurement_basis not null default 'disclosed',
  usdtwd_spot         numeric,
  fwd_points_1m       numeric,
  fwd_points_3m       numeric,
  fwd_points_12m      numeric,
  ndf_points_3m       numeric,      -- user-supplied Bloomberg windows only
  implied_hedge_cost_3m_bp numeric,
  source_url          text not null,
  source_doc          text,
  retrieved_at        timestamptz not null,
  primary key (obs_date, basis, vintage)
);

comment on column tlfx.market_daily.ndf_points_3m is
  'Offshore NDF points are not free data. Populated only from user-supplied '
  'Bloomberg windows around key dates; source_doc must name the window.';

-- -------------------------------------------------------- derived_series
-- The nine published series. The artifact is built from this table alone,
-- so provenance and basis must survive the derivation step.
create table if not exists tlfx.derived_series (
  series_id           smallint not null,    -- 1-9, README section 3
  series_key          text not null,
  entity_id           text references tlfx.entities (entity_id),  -- null = sector
  obs_date            date not null,
  freq                tlfx.frequency not null,
  value               numeric,
  unit                text not null,
  definition_version  text not null,
  basis               text,                 -- accounting_basis or measurement_basis value
  basis_note          text,
  source_url          text not null,
  source_doc          text,
  retrieved_at        timestamptz not null,
  vintage             date not null,
  run_id              uuid,
  id                  bigint generated always as identity primary key
);

-- entity_id is null for sector-level rows, so the natural key needs a
-- coalesce, which a primary-key constraint cannot express: unique index.
create unique index if not exists derived_series_natural_key
  on tlfx.derived_series (series_key, coalesce(entity_id, ''), obs_date, vintage);

create index if not exists derived_series_lookup
  on tlfx.derived_series (series_id, entity_id, obs_date);

comment on table tlfx.derived_series is
  'Publication layer. Stage 6 exports from here into the artifact #data-blob; '
  'the design spec requires every chart and table to carry a source line with '
  'source and vintage, so those columns are not optional here.';

comment on column tlfx.derived_series.series_id is
  '1 economic hedge ratio, 2 net open FX position, 3 buffer coverage, '
  '4 regulatory hedge ratio, 5 gross hedge ratio, 6 hedge composition, '
  '7 hedge cost, 8 counterparty residual, 9 flow diagnostics.';

comment on column tlfx.derived_series.unit is
  'Series 2 is stored once in NT$ mn; USD, pct_gdp, pct_assets and x_capital '
  'are separate rows of the same series_id, selected in the artifact by a '
  'unit toggle. Never a second y-axis.';

-- ------------------------------------------------------------- run_log
create table if not exists tlfx.run_log (
  run_id        uuid primary key default gen_random_uuid(),
  stage         text not null,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  git_sha       text,
  status        text not null default 'running',
  notes         jsonb,
  constraint run_status check (status in ('running', 'ok', 'fail'))
);

create table if not exists tlfx.run_source_status (
  run_id        uuid not null references tlfx.run_log (run_id) on delete cascade,
  source_url    text not null,
  source_doc    text,
  http_status   integer,
  ok            boolean not null,
  content_sha256 text,
  retrieved_at  timestamptz not null,
  note          text,
  primary key (run_id, source_url)
);

create table if not exists tlfx.run_reconciliation (
  run_id       uuid not null references tlfx.run_log (run_id) on delete cascade,
  check_name   text not null,
  lhs          numeric,
  rhs          numeric,
  tolerance    numeric not null default 0.03,
  rel_error    numeric,
  passed       boolean not null,
  unit         text,
  primary key (run_id, check_name)
);

comment on table tlfx.run_reconciliation is
  'README section 3: a run fails if any check is breached by more than 3%.';

-- --------------------------------------------------------------- RLS
-- Every table in this project runs with RLS enabled and no permissive
-- policy: ingestion uses the service role, which bypasses RLS, and nothing
-- is exposed to anon. Matches the uk_ldi and nl_wtp monitors in the same
-- project.
alter table tlfx.entities            enable row level security;
alter table tlfx.sector_monthly      enable row level security;
alter table tlfx.sector_balance_sheet enable row level security;
alter table tlfx.firm_quarterly      enable row level security;
alter table tlfx.cbc_fx_ops          enable row level security;
alter table tlfx.bis_lbs_tw          enable row level security;
alter table tlfx.market_daily        enable row level security;
alter table tlfx.derived_series      enable row level security;
alter table tlfx.run_log             enable row level security;
alter table tlfx.run_source_status   enable row level security;
alter table tlfx.run_reconciliation  enable row level security;
