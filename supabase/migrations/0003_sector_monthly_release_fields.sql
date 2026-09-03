-- Migration 0003: sector_monthly columns for what the FSC monthly release
-- actually carries (Stage 1, docs/decisions.md 1.1–1.3), plus the fields the
-- 2026 press-reported briefing rows need.
--
-- Measured against all 91 editions (May 2018 – Dec 2025): the release carries
-- pre-tax profit and owners' equity (life / non-life / total), an FX table
-- (FX gain/loss, hedging P&L split into instrument P&L and swap cost from
-- 2020-01, net reserve change, combined effect) and a narrative paragraph
-- (TWD move YTD, life FX reserve balance and its change, net foreign-
-- investment income from 2020-09). It never carries the hedge ratio, the
-- foreign-investment total, the regulatory exposure or the reserve buckets.
--
-- Flow items (profit, FX table) are cumulative year-to-date as published.
-- Monthly flows are a derivation (difference within the calendar year) and
-- belong in derived_series, not here.

alter table tlfx.sector_monthly
  add column if not exists source_id                    text,      -- FSC dataserno, or article id
  add column if not exists pretax_profit_life           numeric,   -- NT$ mn, YTD
  add column if not exists pretax_profit_nonlife        numeric,
  add column if not exists pretax_profit_total          numeric,
  add column if not exists owners_equity_nonlife        numeric,   -- NT$ mn, month-end
  add column if not exists owners_equity_total          numeric,
  add column if not exists hedging_instrument_gain_loss numeric,   -- NT$ mn, YTD, life (2020-01→)
  add column if not exists hedging_swap_cost            numeric,   -- NT$ mn, YTD, life, negative = cost (2020-01→)
  add column if not exists fx_reserve_net_change        numeric,   -- NT$ mn, YTD, life: + release / - provision
  add column if not exists fx_combined_effect           numeric,   -- NT$ mn, YTD, life: fx + hedging + reserve net change
  add column if not exists total_assets                 numeric,   -- NT$ mn, life (2020-01, 2020-02 only)
  add column if not exists fx_reserve_change            numeric,   -- NT$ mn, change in life reserve balance
  add column if not exists fx_reserve_change_basis      text,      -- 'prev_month' (to 2019) | 'prev_year_end' (2020-09→)
  add column if not exists twd_change_ytd_pct           numeric,   -- % vs prior year-end; + = TWD appreciation
  add column if not exists net_foreign_investment_income numeric,  -- NT$ mn, YTD, life (2020-09→)
  add column if not exists one_off_provision            numeric,   -- NT$ mn, memo: one-off transfers into the reserve
  add column if not exists hedging_split_available      boolean,
  add column if not exists flows_are_ytd                boolean not null default true,
  -- press-reported briefing fields (2026→)
  add column if not exists fx_buffer_total              numeric,   -- NT$ mn: FX reserve + special reserves, as quoted
  add column if not exists buffer_absorbable_appreciation_pct numeric, -- regulator's "can absorb x% TWD appreciation"
  add column if not exists hedge_cs_share_note          text,      -- e.g. '>75%' — quoted as a bound, not a figure
  add column if not exists hedge_ndf_share_note         text,
  add column if not exists hedge_cost_cs_annual_pct     numeric,
  add column if not exists hedge_cost_ndf_annual_pct    numeric,
  add column if not exists reported_by                  text,      -- official quoted, for press-reported rows
  add column if not exists source_quote                 text,      -- the sentence carrying the figures
  add column if not exists source_note                  text;

comment on column tlfx.sector_monthly.owners_equity is
  'Life insurers only (壽險業). Non-life and total are separate columns.';
comment on column tlfx.sector_monthly.fx_gain_loss is
  'Life insurers, cumulative year-to-date as published (flows_are_ytd).';
comment on column tlfx.sector_monthly.hedging_gain_loss is
  'Life insurers, YTD. One line to 2019-12; from 2020-01 the sum of '
  'hedging_instrument_gain_loss and hedging_swap_cost (hedging_split_available).';
comment on column tlfx.sector_monthly.fx_reserve_net_change is
  'Life insurers, YTD. Positive = net release (收回較多), negative = net provision.';
comment on column tlfx.sector_monthly.fx_reserve_total is
  'Life insurers'' FX price-fluctuation reserve balance, month-end, NT$ mn. '
  'v1 (release) to 2025-12; v2 (press-reported, then firm statements) is the '
  'sum of the volatility and fixed buckets.';
comment on column tlfx.sector_monthly.vintage is
  'Publication date of the edition or article the row was taken from. '
  'obs_month is the reference month; a re-release of the same month gets a '
  'new vintage and is kept alongside.';
comment on column tlfx.sector_monthly.hedge_ratio_regulatory is
  'Fraction. Never printed in the monthly release; from the Insurance '
  'Bureau briefing (press-reported) for every month it exists.';
