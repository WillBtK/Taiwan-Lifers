-- 0010: correct two column comments on firm_statutory_indicators.
-- 0008 recorded the 2026 growth fields as possibly index levels (this period
-- / prior period * 100). The full 30-insurer cross-section falsifies that:
-- AMOUNT9 runs -7.91 to 485.93 and AMOUNT11 reaches -140.36, and an index
-- level cannot be negative. Both are signed percentage changes in both eras
-- (decisions 4.10, revised). No data changes; comments only.
comment on column tlfx.firm_statutory_indicators.premium_income_change_pct is
  'AMOUNT9 保費收入變動率: signed percentage change as published (negative '
  'values occur, so not an index level). Confirmed on the 30-insurer '
  'cross-section, decisions 4.10.';
comment on column tlfx.firm_statutory_indicators.net_income_change_pct is
  'AMOUNT11 淨利變動率: signed percentage change as published (reaches '
  '-140.36). Note the 2026 rows cluster between 86 and 109 for every active '
  'insurer, which is not how net income growth behaves; the sign convention '
  'is settled but the base is not (decisions 4.10).';
comment on column tlfx.firm_statutory_indicators.liabilities_to_assets_pct is
  'AMOUNT1 負債占資產比率. Verified against tlfx.firm_statutory_balance: equals '
  'total_liabilities / total_assets on all 30 records (four large firms show '
  '0.02-0.83pp residuals, scope or refresh unresolved). This identity pins '
  'the positional AMOUNT mapping for the whole table.';
