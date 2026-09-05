-- 0008: firm-level statutory financial indicators from the Insurance
-- Bureau's disclosure portal (ins-info.ib.gov.tw 表06161610 壽險財務業務指標,
-- republished as data.gov.tw dataset 7191). Additive; nothing existing changes.
--
-- Why a separate table: these are the Bureau's own ratios for EVERY life
-- insurer (30 names incl. defunct ones), not the six-firm FX panel, so they
-- are keyed on the published insurer name with entity_id as a nullable link
-- into tlfx.entities. Wide, one row per (insurer, quarter, vintage): the
-- payload is a single record per insurer with 23 positional AMOUNT fields.
--
-- Column order == AMOUNT1..AMOUNT23 == the order of the 23 indicator names in
-- the dataset's catalogue description (decisions 4.10). The catalogue carries
-- no per-field descriptions, so the mapping is positional, corroborated by
-- value ranges on the unambiguous ratios. The verbatim record is kept in
-- raw_record so a re-mapping never needs the source again.
--
-- Units: percent as published (86.13 = 86.13%), except eps_ntd (NT$ per
-- share). 'N/A' and '' in the source both load as NULL; the distinction
-- survives in raw_record.
create table if not exists tlfx.firm_statutory_indicators (
  insurer_name                          text not null,   -- as published
  entity_id                             text references tlfx.entities (entity_id),
  obs_quarter                           date not null,   -- first day of the quarter
  roc_year                              smallint not null,
  quarter                               smallint not null check (quarter between 1 and 4),
  vintage                               date not null,
  basis                                 tlfx.accounting_basis not null,
  liabilities_to_assets_pct             numeric,  -- 1  負債占資產比率
  reserves_to_assets_pct                numeric,  -- 2  各種責任準備金對資產比率
  reserves_change_pct                   numeric,  -- 3  各種責任準備金變動率
  reserves_net_increase_to_premium_pct  numeric,  -- 4  各種責任準備金淨增額對保費收入比率
  affiliate_investment_to_equity_pct    numeric,  -- 5  關係企業投資額對業主權益比率
  first_year_premium_ratio_pct          numeric,  -- 6  初年度保費比率
  renewal_premium_ratio_pct             numeric,  -- 7  續年度保費比率
  new_business_expense_ratio_pct        numeric,  -- 8  新契約費用率
  premium_income_change_pct             numeric,  -- 9  保費收入變動率
  equity_change_pct                     numeric,  -- 10 業主權益變動率
  net_income_change_pct                 numeric,  -- 11 淨利變動率
  funds_utilisation_ratio_pct           numeric,  -- 12 資金運用比率
  persistency_13m_pct                   numeric,  -- 13 繼續率(十三個月)
  persistency_25m_pct                   numeric,  -- 14 繼續率(二十五個月)
  roa_pct                               numeric,  -- 15 資產報酬率
  roe_pct                               numeric,  -- 16 業主權益報酬率
  net_investment_yield_pct              numeric,  -- 17 資金運用淨收益率
  investment_return_pct                 numeric,  -- 18 投資報酬率
  operating_margin_pct                  numeric,  -- 19 營業利益對營業收入比率
  pretax_margin_total_revenue_pct       numeric,  -- 20 稅前純益對總收入比率
  net_margin_pct                        numeric,  -- 21 純益率
  eps_ntd                               numeric,  -- 22 每股盈餘
  real_estate_and_mortgage_to_assets_pct numeric, -- 23 不動產投資與不動產抵押放款對資產比率
  raw_record                            jsonb not null,
  source_url                            text not null,
  source_doc                            text,
  source_note                           text,
  retrieved_at                          timestamptz not null,
  primary key (insurer_name, obs_quarter, vintage)
);

comment on table tlfx.firm_statutory_indicators is
  'Insurance Bureau 壽險財務業務指標 (ins-info 表06161610 / data.gov.tw 7191): '
  'statutory ratios per life insurer. Column order follows AMOUNT1..23 = the '
  'catalogue''s indicator list (decisions 4.10). Percent as published; NULL '
  'for both N/A and blank, distinguished in raw_record.';
comment on column tlfx.firm_statutory_indicators.entity_id is
  'Link into the six-firm panel where the insurer is one of them; NULL for '
  'the other insurers. Both Shin Kong rows (115.1.1合併前 and 原台新人壽) map '
  'to shinkong_life per the README §4.5 continuity convention.';
comment on column tlfx.firm_statutory_indicators.vintage is
  'Date the snapshot was taken (the payload carries no publication stamp and '
  'the catalogue last_update_time predates the quarter it contains).';
comment on column tlfx.firm_statutory_indicators.premium_income_change_pct is
  'AMOUNT9 保費收入變動率 as published. 2026 (IFRS 17) rows cluster near 100 '
  'while the 2025 row is a signed change; definition not yet confirmed from '
  'the portal''s 指標說明 (decisions 4.10).';
comment on column tlfx.firm_statutory_indicators.net_income_change_pct is
  'AMOUNT11 淨利變動率 as published; same definitional caveat as AMOUNT9.';
