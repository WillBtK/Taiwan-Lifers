-- 0014: per-company reserve disclosures from the Insurance Bureau's portal
-- (ins-info Info2-5 準備金, Info2-14 其他負債項下之…特別準備及其他準備). Additive.
--
-- Two layouts, and the distinction is load-bearing rather than cosmetic:
--   labelled   — the pre-2026 (IFRS 4) Info2-5 table, ten named rows across
--                three completed years, 外匯價格變動準備 among them. The only
--                firm-level FX-reserve history that exists in this project.
--   unlabelled — the 2026 (IFRS 17) Info2-5 table. Its 項目 cells are literally
--                empty in the source. The page title says the FX reserve is in
--                there, but no row equals any firm's balance known from its own
--                filings, so it is bundled, not merely unnamed.
--
-- Hence `items` (named) and `unnamed_items` (positional) are separate jsonb
-- columns. Naming the unlabelled rows by position against the labelled layout
-- is forbidden: IFRS 17 restructured the reserve decomposition, so position N
-- in one is not position N in the other (decisions 4.28).
create table if not exists tlfx.firm_reserves (
  entity_id                 text not null references tlfx.entities (entity_id),
  uid                       text not null,
  page                      text not null,          -- Info2-5 | Info2-14
  obs_date                  date not null,
  period_kind               text not null check (period_kind in ('quarter', 'year_end')),
  vintage                   date not null,
  layout                    text not null check (layout in ('labelled', 'unlabelled')),
  fx_volatility_reserve     numeric,
  special_reserve_liability numeric,
  other_reserve             numeric,
  policy_reserve            numeric,
  total                     numeric,
  items                     jsonb,
  unnamed_items             jsonb,
  source_url                text not null,
  source_doc                text,
  source_note               text,
  retrieved_at              timestamptz not null,
  primary key (entity_id, uid, page, obs_date, vintage)
);

comment on table tlfx.firm_reserves is
  'Per-company reserve pages from ins-info (decisions 4.28). NT$ mn. Components '
  'sum to the stated total, asserted per firm per period.';
comment on column tlfx.firm_reserves.fx_volatility_reserve is
  '外匯價格變動準備 in NT$ mn, populated ONLY where layout=labelled. Absent for '
  'every 2026 row because the IFRS-17 page does not break it out.';
comment on column tlfx.firm_reserves.special_reserve_liability is
  '特別準備 on the LIABILITY side. This is NOT 特別盈餘公積, the equity-side '
  'special surplus reserve carried on firm_quarterly (decisions 4.19) and worth '
  'hundreds of billions; this account is zero or near-zero for most firms. The '
  'two are a different account with a similar name, and conflating them would '
  'overstate or understate the buffer stack by orders of magnitude.';
comment on column tlfx.firm_reserves.unnamed_items is
  'Positional rows from a layout that publishes no item names, keyed item_N by '
  'the source''s own 列號. Never rename these by matching position against the '
  'labelled layout.';
