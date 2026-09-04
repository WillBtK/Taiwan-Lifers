-- 0006: firm_quarterly carries deck-disclosed hedge composition as SHARES.
-- Decks (Cathay et al.) disclose hedge structure as percentages of FX assets,
-- never notionals (decisions 3.6); the existing hedge_cs/hedge_ndf/hedge_proxy/
-- open_position notional columns stay for any future statement-derived figures.
-- Additive: new nullable share columns; source_channel discriminates the deck
-- row from the statement row for the same quarter and joins the PK (precedent:
-- 0004 did the same for sector_monthly.reporting_channel).
alter table tlfx.firm_quarterly
  add column if not exists source_channel text not null default 'deck',
  add column if not exists hedge_cs_ndf_share_pct    numeric,  -- CS + NDF, % of FX assets
  add column if not exists hedge_proxy_open_share_pct numeric, -- proxy + open, % of FX assets
  add column if not exists hedge_fvoci_share_pct     numeric,  -- FVOCI overlay wedge, % of FX assets
  add column if not exists fx_risk_share_pct         numeric,  -- share of FX assets carrying FX risk
  add column if not exists fx_policy_share_pct       numeric,  -- share backed by FX-denominated policies
  add column if not exists source_note               text;

alter table tlfx.firm_quarterly
  add constraint firm_quarterly_channel
  check (source_channel = any (array['deck'::text, 'statement'::text]));

alter table tlfx.firm_quarterly drop constraint firm_quarterly_pkey;
alter table tlfx.firm_quarterly
  add primary key (entity_id, obs_quarter, basis, source_channel, vintage);

comment on column tlfx.firm_quarterly.source_channel is
  'deck = IR results presentation (shares, cost, reserve; rounded); '
  'statement = statutory filing (denominator, buffers; NT$-thousand precision). '
  'The two are cross-checked on fx_reserve_balance per decisions 3.6.';
comment on column tlfx.firm_quarterly.hedge_cs_ndf_share_pct is
  'Deck pie wedge: currency swaps + NDF, % of FX assets. Wedge-colour-bound '
  'extraction (decisions 3.4/3.9).';
