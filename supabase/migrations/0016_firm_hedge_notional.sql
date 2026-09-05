-- 0016: per-firm FX hedge notional from the statutory statements.
--
-- 4.36 established that a firm which does NOT apply hedge accounting discloses
-- the notional principal of its economic FX hedges in the currency-risk note of
-- its quarterly statement, and that the disclosure reconciles against the
-- instrument split in the derivatives note at period-end spot. That is the
-- exact per-firm hedge amount this project previously recorded as unpublished.
--
-- Three columns rather than reusing hedge_ndf: 遠期外匯合約 is a deliverable
-- forward and an NDF is not, and the whole point of the FSC's "traditional
-- hedge" definition is that it enumerates instruments. Collapsing a forward
-- into the NDF column would destroy the composition the disclosure exists to
-- give, and the CBC-versus-FSC gap (4.34) turns on precisely that split.

alter table tlfx.firm_quarterly
  add column if not exists hedge_fx_forward     numeric,
  add column if not exists hedge_notional_total numeric;

comment on column tlfx.firm_quarterly.hedge_fx_forward is
  '遠期外匯合約 notional principal, NT$ mn. A DELIVERABLE forward; NDFs belong '
  'in hedge_ndf and currency swaps in hedge_cs. From the derivatives note of '
  'the statutory statement, never the 避險工具 hedge-accounting table, which '
  'lists only designated instruments and is ~1% of the book for firms that do '
  'not apply hedge accounting (decisions 4.36).';

comment on column tlfx.firm_quarterly.hedge_notional_total is
  'Total notional principal of derivatives used to mitigate FX exposure, NT$ mn, '
  'as stated in the currency-risk note (「其名目本金共計新台幣 … 仟元」). Where '
  'the derivatives note also gives the instrument split in USD, the two tie at '
  'the period-end spot rate; that tie is asserted on load, not assumed. NULL '
  'means not disclosed, which is NOT the same as no hedges: a firm applying '
  'hedge accounting reports elsewhere.';
