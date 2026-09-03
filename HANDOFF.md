# TLFX — Stage 1 handoff (2026-09-03)

Stage 1 (FSC sector series) is complete and merged to `main`. Current state lives in
`STATUS.md`, history and rationale in `docs/decisions.md` (entries 1.1–1.8).

## What Stage 1 delivered

- `src/tlfx/fsc_parse.py` + `scripts/stage1_sector_monthly.py` — all 91
  editions of the monthly release (May 2018 – Dec 2025) parsed into
  `tlfx.sector_monthly`, channel `release`, 423/423 checks.
- `config/briefing_press.json` + `scripts/stage1_briefing_press.py` — the
  Insurance Bureau's monthly briefing figures as reported by the press,
  verified against the fetched articles, channel `briefing_press`, basis
  `press_reported`: 2024-12, 2025-08, 2025-10, 2025-12, 2026-01 → 2026-07.
  16/16 identity checks.
- Migrations `0003` (release fields) and `0004` (channel in the key), applied.
- `*.tii.org.tw` TLS fixed at the root cause (missing intermediate; supplied
  from `config/certs/`, verification never disabled).

## The material findings

1. **The release never carried the hedge ratio.** Not in any edition. Series
   4 is press-reported from the briefing for its whole life (2020→), so its
   v1/v2 split is definitional, not a channel break. README §3/§4.1 corrected.
2. **The 2026 channel is fetched, not snippeted.** `money.udn.com`, cnyes and
   CTS/CNA answer directly now; every 2026 month to July is in.
3. **The v2 identity holds** where it can be tested: 15.4兆 × (1 − 50.23%)
   against the Bureau's ≈7.7兆 net exposure, 0.5% apart (old item 2).
4. **Firm statements reconcile to the briefing** at June 2026 (20-firm reserve
   aggregate 6,997.3億 vs 6,997億) but not at December 2025 (6,178.2億 vs
   6,137億). Stage 3 owns that gap.

## What's still open

1. **Briefing backfill 2020-01 → 2025-07 — load-bearing, not optional.**
   The release carries hedging P&L and swap cost but never the hedge
   principal, so the sector-level economic ratio (series 1), net open
   position (series 2) and gross ratio (series 5) for 2020–2025 need
   hedge principal = regulatory ratio × denominator, which only the
   briefing gives (denominator at year-ends only; interpolate or use CBC
   foreign assets less firm FX-policy liabilities, and flag which). It also
   gives the realised sector hedge-cost rate (swap cost ÷ principal) for
   series 7. Without it, pre-2026 sector series 1/2/5 rest on the six-firm
   panel alone. Month-by-month search on `money.udn.com` (the briefing series
   dates from ROC 109); same config-and-verify pattern as the 2026 rows;
   suitable for Haiku 4.5. Do it before Stage 2 derives series 1/2/5.
2. **Firm-level §10 disclosure format** is seen in Cathay's 2Q26 deck (FX
   assets NT$5.54tn, hedging cost 1.21%, FX volatility reserve NT$130.9bn),
   not yet in a statutory statement. Fubon's IR pages under `/en/` do not
   link statements; try the Chinese IR path or MOPS. Both are Stage 3.
3. **Supabase credentials** are not in the environment; SQL is applied via
   the MCP. `--write` (PostgREST) also needs schema `tlfx` exposed.

## Suggested initial prompt for the next session

Read HANDOFF.md, STATUS.md, and docs/decisions.md (Stage 1 entries 1.1–1.8).
Stage 1 is merged to main. First run the briefing backfill (HANDOFF open
item 1) with the config-and-verify pattern in scripts/stage1_briefing_press.py,
then start Stage 2 per README section 7: ingest CBC Financial Statistics Monthly table 8
(`065_EF67_A4L.csv`, index `np-532-1.html`) monthly and the statistics
database (`cpx.cbc.gov.tw`) for history to 2000 into sector_balance_sheet;
derive foreign assets and equity; combine with sector_monthly (channel
`release` to 2025-12, `briefing_press` from 2026) to produce series 1, 2 and 5
at sector level in derived_series. Run README §3 check 2 once CBC foreign
assets exist. Emit SQL as Stage 1 did and apply via the Supabase MCP.
