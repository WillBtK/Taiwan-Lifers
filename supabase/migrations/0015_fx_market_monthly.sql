-- 0015: the FX market side, from the CBC statistics database.
--
-- Everything the project has held so far describes the lifers. This table
-- describes the market they hedge in: what a forward costs, and how much
-- forward and swap business the banking system does. Both matter because the
-- hedge ratio is a price-sensitive choice, not a policy constant — the
-- reconstruction in decisions 4.29 shows it falling roughly 20pp over six
-- years, and the cost of the hedge is the first candidate for why.
--
-- Long format rather than one column per tenor. The three source series have
-- different shapes — forwards are tenor x side, turnover is market segment x
-- (level, YoY) — and a wide table would need re-migrating for each further
-- CBC series added (EG49 call loans, EG01 FX loans, EG46 trade receipts, the
-- balance of payments). item/sub_item carries the source's own two-level
-- structure unchanged, which is also what keeps the labels auditable against
-- the publication.
--
-- Units are NOT normalised here: the rates are TWD per USD, the turnover is
-- USD mn, and forcing them into one column would destroy the distinction.
-- unit is carried per row and is required.

create table if not exists tlfx.fx_market_monthly (
  matrix_code    text not null,          -- CBC series code, e.g. EG55M01
  item           text not null,          -- Table1 label as published (zh)
  sub_item       text not null,          -- Table2 label, or '' where the series has one dimension
  obs_month      date not null,
  value          numeric,
  unit           text not null,
  vintage        date not null,          -- the CBC's own last_updated for the series
  source_url     text not null,
  source_doc     text,
  source_note    text,
  retrieved_at   timestamptz not null,
  primary key (matrix_code, item, sub_item, obs_month, vintage)
);

comment on table tlfx.fx_market_monthly is
  'Monthly FX-market series from the CBC statistics database '
  '(cpx.cbc.gov.tw/API/DataAPI/Get, SDMX-JSON, no key). Long format: item and '
  'sub_item are the source''s own Table1/Table2 labels, unmodified, so a row '
  'can be checked against the published table without a mapping. Values are '
  'as published; ''-'' becomes null, never zero.';

comment on column tlfx.fx_market_monthly.sub_item is
  'Second dimension where the series has one: bid/ask for forward rates '
  '(買入匯率/賣出匯率), level/YoY for turnover (原始值/年增率). Empty string, '
  'not null, for single-dimension series, so it can sit in the primary key.';

comment on column tlfx.fx_market_monthly.vintage is
  'The CBC''s own last_updated date for the series, not the fetch date. The '
  'CBC revises history in place, so a re-fetch after a revision arrives as a '
  'new vintage alongside the old rather than overwriting it.';

comment on column tlfx.fx_market_monthly.unit is
  'Required and per-row: this table mixes TWD-per-USD rates, USD mn turnover '
  'and percentages. A single normalised value column would lose that.';
