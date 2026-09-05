-- 0009: firm-level statutory balance-sheet summary from the Insurance
-- Bureau's disclosure portal (ins-info.ib.gov.tw 表06021011 財務報告彙總,
-- payload opendata/json-06021011.aspx). Additive.
--
-- Covers every insurer the Bureau supervises — life AND non-life, active and
-- defunct — one record per insurer at its latest reported quarter, so the
-- published name is the key and entity_id links the six panel firms.
--
-- Named columns are the ones the data itself pins: AMOUNT1 - AMOUNT2 =
-- AMOUNT3 holds to the NT$ thousand on all 52 records, and AMOUNT1..3 tie
-- exactly to the six firms' own MOPS / Excel statements in firm_quarterly
-- (decisions 4.11), so they are total assets, total liabilities and owners'
-- equity in NT$ THOUSAND as published (note: NOT the project's NT$ mn
-- convention — kept as published because the source is a regulator table,
-- conversion happens in queries). ActualCapital is paid-in capital, the
-- field's own name. AMOUNT4..8 are NOT named: the catalogue carries no
-- field list for this table and no in-data identity pins them; they are
-- stored verbatim under their source names until the portal's column
-- headers are couriered.
create table if not exists tlfx.firm_statutory_balance (
  insurer_name          text not null,     -- as published
  entity_id             text references tlfx.entities (entity_id),
  sector                text not null check (sector in ('life', 'nonlife')),
  obs_quarter           date not null,     -- first day of the quarter
  roc_year              smallint not null,
  quarter               smallint not null check (quarter between 1 and 4),
  vintage               date not null,     -- snapshot date (courier stamp)
  basis                 tlfx.accounting_basis not null,
  total_assets_ntd_k    numeric not null,  -- AMOUNT1, NT$ thousand
  total_liabilities_ntd_k numeric not null, -- AMOUNT2
  owners_equity_ntd_k   numeric not null,  -- AMOUNT3
  paid_in_capital_ntd_k numeric,           -- ActualCapital
  amount4               numeric,           -- unnamed, see above
  amount5               numeric,
  amount6               numeric,
  amount7               numeric,
  amount8               numeric,
  raw_record            jsonb not null,
  source_url            text not null,
  source_doc            text,
  source_note           text,
  retrieved_at          timestamptz not null,
  primary key (insurer_name, obs_quarter, vintage),
  constraint firm_statutory_balance_identity
    check (abs(total_assets_ntd_k - total_liabilities_ntd_k - owners_equity_ntd_k) <= 0.01)
);

comment on table tlfx.firm_statutory_balance is
  'Insurance Bureau 財務報告彙總 (ins-info 表06021011): total assets, liabilities, '
  'equity and paid-in capital per insurer in NT$ THOUSAND as published, latest '
  'quarter per insurer per snapshot. AMOUNT4..8 unnamed pending the portal '
  'headers (decisions 4.11).';
comment on column tlfx.firm_statutory_balance.sector is
  'life / nonlife from the published name (產物保險 / 產險 → nonlife; the '
  'fishing-vessel cooperative is nonlife); 中華郵政 is life (postal life insurance).';
