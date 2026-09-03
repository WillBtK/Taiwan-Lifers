# TLFX — Stage 0 handoff (2026-09-03)

Stage 0 (Scaffold) is complete and merged to `main`. This file is a one-time
handoff note for picking the work back up — current state lives in
`STATUS.md`, history and rationale in `docs/decisions.md`.

## What exists

- Repo layout, `requirements.txt`, `.env.example`.
- `src/tlfx/provenance.py` — fetch with retry/backoff, `Provenance`,
  `RunLog`, `ReconciliationCheck`, the two basis enums, per-host User-Agent
  policy.
- `src/tlfx/fsc.py` — locates FSC/Insurance Bureau releases by keyword
  search across both channels (never by page position).
- `scripts/check_allowlist.py` + `config/allowlist.tsv` — network
  reachability probe, tiered, concurrent, retry-on-transport-error-only.
- `supabase/migrations/0001_tlfx_schema.sql`, `0002_regime_v2.sql` — schema
  `tlfx` in project `term-premium-atlas` (`xzhoykybwlkefgvgwnii`), applied.
  11 tables, RLS on, v2 regime columns added.
- `docs/artifact_design_system.md` — the design spec, amended per its own
  §7/§10 (palette validation recorded and applied) but otherwise verbatim.
- `docs/sources/` — the Feb 2026 FX-reserve notice (PDF + extracted text),
  the primary document for Stage 4.

## The one material finding

The FSC's monthly sector release (series 4, 3(a)) **stopped in December
2025** — no 2026 edition exists on either press channel. The regime changed,
not just the channel: IFRS 17/TW-ICS went live 1 Jan 2026, and a new FX
reserve mechanism (four named buckets, notice-defined hedge ratio and net
exposure) took effect 12 Feb 2026. The 2026 sector hedge ratio (50.23% Dec
2025 → 42.89% Jun 2026) is **press-reported** — from the Insurance Bureau's
monthly briefing, via Economic Daily/cnyes/CNA, not from a citable release.
Firm quarterly statements (notice §10 mandated disclosures) are the
provenance-clean source going forward. Full reasoning: `docs/decisions.md`
0.10–0.12.

## What's still open

1. **`*.tii.org.tw` TLS.** The sandbox proxy now tunnels these hosts (the
   earlier 502 block is gone), but certificate verification fails
   (`unable to get local issuer certificate`) despite an identical issuing
   CA to hosts that work fine. Looks like an unfinished cert-provisioning
   step for a freshly-allowlisted domain, not fixable from inside the repo.
   Retry from a fresh session/container before Stage 3.
2. **Reconciliation check 1** (README §3) is now an *identity* under the
   v2 hedge-ratio definition, not an approximate check — confirm this holds
   once real 2026 firm data is parsed.
3. **Firm-level v2 disclosure format** is not yet seen firsthand (no firm's
   2026 Q1/Q2 statement has been pulled) — the schema's v2 columns are built
   from the notice's requirements, not from an observed filing. Verify
   against Cathay's or Fubon's actual Q2 2026 statement early in Stage 3.

## Suggested initial prompt for the next session

See below — paste as-is to resume.
