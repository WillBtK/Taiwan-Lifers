-- 0012: carry the EQUITY-side reserve buckets, not just the liability-side one.
-- Additive.
--
-- The buffer series (README section 3, series 3) defines four buckets from the
-- February 2026 notice, and only the first pair sits on the liability side in
-- ReserveForForeignExchangeValuation, which is all firm_quarterly held. The
-- other two are appropriations of retained earnings into 特別盈餘公積 and were
-- being ignored entirely. They are not small: at Fubon 2025Q4 the equity-side
-- special reserve is NT$333.9bn against a NT$142.1bn FX reserve, and at Taiwan
-- Life NT$54.1bn against NT$27.9bn. Omitting them understated the loss-
-- absorbing stack by more than half (decisions 4.19).
--
-- IMPORTANT semantics. special_reserve_equity is the WHOLE 特別盈餘公積 line and
-- is therefore an UPPER BOUND on the FX-designated portion: other statutory
-- appropriations (unrealised revaluation, IFRS transition) share it. Splitting
-- out 外匯風險固定準備 and 外匯風險強化準備 needs the notes, not the face of the
-- statements — and the distinction matters, because the 強化 bucket is
-- restricted capital that cannot offset losses at all.
alter table tlfx.firm_quarterly
  add column if not exists special_reserve_equity numeric,
  add column if not exists statutory_reserve numeric,
  add column if not exists special_reserve_appropriated numeric,
  add column if not exists special_reserve_reversal numeric;

comment on column tlfx.firm_quarterly.special_reserve_equity is
  '特別盈餘公積 in NT$ mn, the equity-side special surplus reserve. UPPER BOUND '
  'on the FX-designated buffer: the line also carries non-FX statutory '
  'appropriations. Never add it to fx_reserve_balance and call the total '
  'FX loss-absorbing capacity without saying it is a bound (decisions 4.19).';
comment on column tlfx.firm_quarterly.special_reserve_appropriated is
  'Year-to-date appropriation into 特別盈餘公積 from retained earnings, from the '
  'statement of changes in equity (SpecialReserveMember column). With '
  'special_reserve_reversal it reconciles the year-on-year movement in '
  'special_reserve_equity exactly, which is the check the loader asserts.';
comment on column tlfx.firm_quarterly.statutory_reserve is
  '法定盈餘公積 in NT$ mn. Not FX-designated; carried because it is the other '
  'appropriated-earnings buffer and belongs in the same stack for context.';
