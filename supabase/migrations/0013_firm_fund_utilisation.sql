-- 0013: fund utilisation per insurer, from the Insurance Bureau's per-company
-- 資金運用表 (ins-info Info2-1). Additive.
--
-- This carries 國外投資 BY FIRM, which is the hedge-ratio denominator at firm
-- level. The project has had that figure for the sector since Stage 2 (表17-1)
-- and for three firms from investor decks, but never published for all six.
-- It is also the freshest series here: the page reports the latest MONTH of
-- the current ROC year, where the statutory filings stop at the quarter.
--
-- Units NT$ mn, converted from the published NT$ thousand. The nine components
-- sum to the printed total, asserted per firm per period by the loader.
create table if not exists tlfx.firm_fund_utilisation (
  entity_id                 text not null references tlfx.entities (entity_id),
  uid                       text not null,   -- 統一編號, the portal's key
  obs_date                  date not null,   -- period END
  period_kind               text not null check (period_kind in ('latest_month', 'year_end')),
  vintage                   date not null,   -- snapshot date
  bank_deposits             numeric,
  securities                numeric,
  real_estate               numeric,
  loans                     numeric,
  project_public_investment numeric,
  foreign_investment        numeric,
  insurance_related         numeric,
  derivatives               numeric,
  other                     numeric,
  total                     numeric,
  source_url                text not null,
  source_doc                text,
  source_note               text,
  retrieved_at              timestamptz not null,
  primary key (entity_id, uid, obs_date, vintage)
);

comment on table tlfx.firm_fund_utilisation is
  'Per-insurer 資金運用表 from ins-info Info2-1 (decisions 4.27). NT$ mn. The '
  'primary key carries uid as well as entity_id because Shin Kong has two '
  'registration numbers either side of the 2026 merger and both report.';
comment on column tlfx.firm_fund_utilisation.foreign_investment is
  '國外投資 in NT$ mn — the hedge-ratio denominator at FIRM level. Note the '
  'scope difference that has bitten before (decisions 4.1): this is the same '
  'definition as 表17-1 國外投資, which is NOT the FSC regulatory hedge-ratio '
  'denominator; that one nets FX-policy liabilities and unhedged non-FVTPL '
  'equities and runs about 68% of this. Never pair a disclosed hedge ratio '
  'with this figure without saying which denominator is meant.';
comment on column tlfx.firm_fund_utilisation.period_kind is
  'latest_month = the current ROC year''s most recent month, dated to that '
  'month end; year_end = a completed year. Mixing them into one series without '
  'the flag would put a mid-year observation on a year-end axis.';
