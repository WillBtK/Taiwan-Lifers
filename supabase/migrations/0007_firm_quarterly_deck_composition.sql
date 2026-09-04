-- 0007: carry non-Cathay deck disclosures faithfully.
-- Additive: deck_composition holds each deck's hedge-composition pie under
-- canonical keys (cs_ndf_pct, cs_ndf_policy_pct, naked_usd_pct,
-- naked_other_pct, naked_usd_other_pct, equity_fund_pct, fvoci_equity_pct,
-- fvtpl_equity_pct, fx_risk_pct, fx_policy_pct, ...) without forcing them
-- into the Cathay-shaped share columns when the category semantics differ
-- (Fubon's pre-2026 wedge bundles CS/NDF with FX-policy backing; KGI splits
-- differently). total_fx_cost_bp is the ALL-IN FX result in bp (recurring
-- hedge cost + FX G/L & reserve provisioning; negative = cost) — Fubon's
-- headline series, decisions 3.15 — distinct from hedge_cost_bp, which stays
-- recurring-only and cross-firm comparable.
alter table tlfx.firm_quarterly
  add column if not exists deck_composition jsonb,
  add column if not exists total_fx_cost_bp numeric;

comment on column tlfx.firm_quarterly.deck_composition is
  'Hedge-composition pie exactly as the deck discloses it, canonical keys; '
  'category semantics vary by firm and era, so cross-firm comparisons must '
  'go through the key names, never assume alignment.';
comment on column tlfx.firm_quarterly.total_fx_cost_bp is
  'All-in FX result in bp (recurring hedge cost + FX G/L & reserve '
  'provisioning; negative = cost). Fubon headline series (decisions 3.15). '
  'NOT comparable with hedge_cost_bp (recurring only).';
