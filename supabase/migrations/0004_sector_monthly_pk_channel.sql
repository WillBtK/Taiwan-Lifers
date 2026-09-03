-- Migration 0004: sector_monthly natural key includes the reporting channel.
--
-- The Insurance Bureau briefs the press on the same day the monthly release
-- is posted (measured: 2025-08 release 2025-09-30 / Economic Daily 2025-09-30;
-- 2025-10 2025-11-27 / 2025-11-27; 2025-12 2026-01-27 / 2026-01-27). The
-- release row and the press-reported row for one month therefore share
-- (obs_month, vintage) and the Stage 0 key cannot hold both. The channel is
-- part of the observation's identity, so it joins the key. Table is empty at
-- this point (Stage 0 populated nothing).
alter table tlfx.sector_monthly
  alter column reporting_channel set default 'release';
update tlfx.sector_monthly set reporting_channel = 'release' where reporting_channel is null;
alter table tlfx.sector_monthly
  alter column reporting_channel set not null,
  drop constraint sector_monthly_pkey,
  add primary key (obs_month, reporting_channel, vintage),
  add constraint sector_monthly_channel
    check (reporting_channel in ('release', 'briefing_press', 'firm_statements'));

comment on column tlfx.sector_monthly.reporting_channel is
  'release = FSC/IB monthly press release (to 2025-12); briefing_press = '
  'Insurance Bureau monthly briefing as reported by the press (basis '
  'press_reported); firm_statements = aggregate built from firm quarterly '
  'statements (Stage 3). Consumers must select a channel; months from 2025-08 '
  'carry more than one.';
