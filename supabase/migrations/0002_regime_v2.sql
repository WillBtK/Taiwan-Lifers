-- Migration 0002: IFRS 17 / TW-ICS regime (2026→) — named reserve buckets,
-- notice-defined hedge-ratio fields, press-reported measurement basis.
alter type tlfx.measurement_basis add value if not exists 'press_reported';

alter table tlfx.sector_monthly
  add column if not exists fx_reserve_volatility            numeric,  -- 波動準備金 (liability)
  add column if not exists fx_reserve_fixed                 numeric,  -- 固定準備金 (liability, cap 10% net exposure)
  add column if not exists special_reserve_fx_fixed         numeric,  -- 特別盈餘公積–外匯風險固定準備 (equity)
  add column if not exists special_reserve_fx_strengthening numeric,  -- 特別盈餘公積–外匯風險強化準備 (equity, restricted)
  add column if not exists hedge_ratio_benchmark            numeric,  -- p90 of month-end ratios 2021–2025, notice §(十一)
  add column if not exists hedge_ratio_differential         numeric,  -- notice §(十二)
  add column if not exists net_fx_exposure                  numeric,  -- notice §(二), NT$ mn
  add column if not exists effective_hedge_ratio_memo       numeric,  -- regulator's reserve-inclusive figure; memo only
  add column if not exists reporting_channel                text,     -- 'release' | 'briefing_press' | 'firm_statements'
  add column if not exists basis                            tlfx.measurement_basis not null default 'disclosed';

comment on column tlfx.sector_monthly.fx_reserve_p is 'v1 (to 2025-12) only; v2 uses the four named bucket columns.';
comment on column tlfx.sector_monthly.effective_hedge_ratio_memo is 'Hedged share plus reserve stock over exposure, as quoted by the Insurance Bureau. Memo line, never headline: it mixes a flow hedge with a stock buffer.';

alter table tlfx.firm_quarterly
  add column if not exists fx_reserve_volatility            numeric,
  add column if not exists fx_reserve_fixed                 numeric,
  add column if not exists special_reserve_fx_fixed         numeric,
  add column if not exists special_reserve_fx_strengthening numeric,
  add column if not exists net_fx_exposure                  numeric,
  add column if not exists hedge_ratio_regulatory           numeric,
  add column if not exists unamortised_fx_difference        numeric,
  add column if not exists eps_reported                     numeric,
  add column if not exists eps_ex_reserve_mechanism         numeric;  -- notice §10 mandated disclosure
