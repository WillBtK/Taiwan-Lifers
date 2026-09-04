-- 0005: extend sector_monthly reporting_channel CHECK with 'ib_indicators'.
-- Channel carries the monthly FSC-basis series parsed from the Insurance Bureau's
-- 保險市場重要指標 monthly PDFs (表17-1 人身保險業資金運用表), stage2c.
-- Additive only: existing allowed values unchanged.
alter table tlfx.sector_monthly drop constraint sector_monthly_channel;
alter table tlfx.sector_monthly add constraint sector_monthly_channel
  check (reporting_channel = any (array['release'::text, 'briefing_press'::text, 'firm_statements'::text, 'ib_indicators'::text]));
