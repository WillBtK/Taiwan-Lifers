# Long-history backfill: variable spec and confirmed sources

Written 2026-09-05 in response to the correct objection that the headline
series is too short. It exists so the backfill happens in ONE pass rather
than several, so the variable list is settled before any parser is written.

## The premise, corrected

The project's data does not start in 2024. What is actually held:

| Series | Coverage |
|---|---|
| Sector balance sheet (CBC EF67M01) incl. 國外資產 | **1987-05 → 2026-07**, 471 months |
| FSC-basis 國外投資 + 資產總額 (Bureau 表17-1) | 2017-01 → 2026-04, 112 months |
| Firm deck series (Cathay, Fubon, KGI) | 2013-10 → 2026-04 |
| FSC monthly release: FX P&L, hedging P&L, FX reserve | 2018-05 → 2025-12, 91 editions |
| Firm hedge cost (Fubon, Cathay) | 2013-10 → 2026-04 |
| **Regulatory hedge ratio** | **2024-04 → 2026-07 only** |

Exactly one series is short, and it is the headline one.

## Why it is short, and why that cannot be fixed by fetching harder

The FSC did not publish the regulatory hedge ratio before 2024; press
mentions earlier than that are spoken ranges at briefings ("6~7成"), not the
figure (decisions 1.11). There is no archive to walk. **A disclosure that did
not exist cannot be back-filled.**

The history therefore has to be *reconstructed* from the counterparty side —
which is the method of Setser and S.T.W. (2019) and Setser and Younger
(2025): foreign assets are known, so if the identified hedge supply (bank
forward/swap books, the central bank's own position, FX-denominated policy
liabilities) can be measured with long history, the hedged share falls out as
an identity rather than a disclosure. That is what Stage 5 was for, and it is
the answer to the objection rather than a detour from it.

## Confirmed reachable, long history (CBC statistics database)

`cpx.cbc.gov.tw/API/DataAPI/Get?FileName=<code>`, SDMX-JSON, no key. The full
catalogue (198 series) is enumerated at `Tree/GetJsonTreeData`; these are the
ones that bear on the question, all fetched and coverage verified:

| Code | Content | Coverage | Why it matters |
|---|---|---|---|
| `EF67M01` | Lifers' balance sheet, incl. **國外資產** | 1987-05 → 2026-07 | The denominator, monthly, 39 years. Held already. |
| `EG47M01` | Daily-average FX turnover **and net FX position**, split 換匯 (swap) / 遠期 (forward) / 即期, customer vs interbank | **1994-01 → 2026-06** | The hedge-supply side. Swap and forward turnover is the closest published proxy for hedging activity, 32 years. |
| `EG55M01` | **USD/TWD forward rates by tenor** (10–180 days), bid and ask | **1991-11 → 2026-07** | With spot, gives the market-implied hedging cost over 35 years — the cost series the project currently has only from decks, 2013→. |
| `EG51M01` | USD spot (customer, interbank, daily average) + forward LC rate | 1992-01 → 2026-07 | Spot leg for the forward premium. |
| `EG49M01` | Taipei FX call-loan market by currency and tenor | 1989-08 → 2026-07 | Dollar funding pressure. |
| `EG01M01` | Banks' FX loans outstanding | 1987-05 → 2026-07 | Bank FX balance-sheet capacity. |
| `BPP2Q01` | Balance of payments, **402 series** | **1984Q1 → 2026Q2** | Portfolio investment outflows: the flow counterpart to the asset stock. |
| `BPF4Y01` | International investment position, 96 series | 2000 → 2025 | Independent cross-check on the national foreign-asset stock. |
| `EG46M01` | Trade FX receipts and payments | 1987-08 → 2026-07 | Corporate FX supply, a competing use of the same hedging capacity. |

## Also long, already reachable

- **TII** (`openapi.tii.org.tw`, catalogue in `config/tii_tables.tsv`):
  `I171` fund utilisation and `I14`/`I15` sector balance sheet and income
  statement, annual **2011 →**; `K46`/`K47` two-year detail.
- **Insurance Bureau monthly archive**: currently walked 2017-01 →; how much
  further back the archive goes is untested and is part of this pass.

## The two genuine gaps

Both are on the user's list and neither is yet located in any source found:

1. **FX-denominated policy liabilities (外幣保單)** — the second research
   question turns on this and the project has only composition *shares* from
   three firms' decks, no NT$ series and no sector total. Candidates to test:
   TII premium tables by currency, the Bureau's business-overview tables
   (`json-07011010`), the FSC's own 外幣保單 statistics.
2. **Currency distribution of lifers' foreign assets** — USD vs other. The
   project assumes overwhelmingly USD (README §1) without a source.
   Candidates: `BPF4Y01` by instrument (national, not lifer-specific), firm
   decks, TII.

If neither turns up, that is a finding to state plainly rather than a gap to
paper over with an assumption.

## What this pass does NOT do

No new infrastructure. Every source above is already reachable by an existing
client; the work is fetching, parsing and loading, then the reconstruction.
