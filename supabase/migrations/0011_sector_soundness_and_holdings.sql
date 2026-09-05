-- 0011: two sector series that arrived with the automated pipeline (4.13).
-- Both additive; neither fits sector_monthly, which is keyed to the FSC
-- monthly release and its FX table.

-- CBC 金融健全參考指標 – 壽險公司 (data.gov.tw 132163). Quarterly, 2016-03 on.
-- Sector-level solvency and profitability on the central bank's definitions —
-- the first RBC series in the project, and the only one: the Bureau's portal
-- publishes capital adequacy per firm but does not route to CI (4.13).
-- ROA/ROE are annualised percentages as published; rbc_ratio_pct is
-- semi-annual (June and December only), NULL elsewhere because the source
-- prints '-' rather than a value, which is an absence, not a zero.
create table if not exists tlfx.sector_soundness_quarterly (
  obs_quarter                     date not null,   -- first day of the quarter
  vintage                         date not null,
  assets_to_gdp_pct               numeric,
  roa_pct                         numeric,
  roe_pretax_pct                  numeric,
  roe_posttax_pct                 numeric,
  rbc_ratio_pct                   numeric,         -- semi-annual only
  equity_to_investment_assets_pct numeric,
  source_url                      text not null,
  source_doc                      text,
  source_note                     text,
  retrieved_at                    timestamptz not null,
  primary key (obs_quarter, vintage)
);

comment on table tlfx.sector_soundness_quarterly is
  'CBC financial-soundness indicators for life insurers (data.gov.tw 132163). '
  'Sector level. rbc_ratio_pct is published only for June and December.';
comment on column tlfx.sector_soundness_quarterly.assets_to_gdp_pct is
  'Life-insurer assets as a percentage of GDP. Breaks at 2026-Q1 on the IFRS 17 '
  'and TW-ICS transition (131.22 at 2025-12 to 111.19 at 2026-03); that is a '
  'measurement change, not a balance-sheet contraction, so the series must not '
  'be read across the boundary without saying so.';

-- 保險安定基金 insurer holdings of stocks and bonds (data.gov.tw 172653),
-- monthly, from 2024-12. Published in 億元 and stored in NT$ mn (x100, exact
-- on integers) per the project convention; divide by 100 to recover the
-- printed figure. DOMESTIC AND FOREIGN COMBINED — this is not a foreign-asset
-- series and must never be used as one.
create table if not exists tlfx.sector_holdings_monthly (
  obs_month        date not null,      -- first day of the month
  sector           text not null check (sector in ('life', 'nonlife')),
  vintage          date not null,
  stocks_ntd_mn    numeric,
  bonds_ntd_mn     numeric,
  source_url       text not null,
  source_doc       text,
  source_note      text,
  retrieved_at     timestamptz not null,
  primary key (obs_month, sector, vintage)
);

comment on table tlfx.sector_holdings_monthly is
  'Guaranty-fund series of insurers'' stock and bond holdings, domestic and '
  'foreign combined (data.gov.tw 172653). NT$ mn, converted from the published '
  '億元. Monthly, which is its value: it carries the May-2025 shock at monthly '
  'frequency where the statutory tables are quarterly.';
comment on column tlfx.sector_holdings_monthly.stocks_ntd_mn is
  'Total equity holdings, domestic and foreign. Netting the domestic equity '
  'line of TII 表17-1 against this gives an estimate of foreign equity, which '
  'matters because the FSC hedge-ratio denominator excludes unhedged non-FVTPL '
  'equities and funds (decisions 4.16).';
