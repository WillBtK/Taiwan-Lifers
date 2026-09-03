# Insurance Bureau briefing — hedge ratio coverage ledger

What has been searched for the sector hedge ratio, what was found, and what is
known not to be findable. Maintained alongside `config/briefing_press.json`,
which holds the rows themselves. Background: `docs/decisions.md` 1.2, 1.9, 1.10.

## The channel picture (measured 2026-09-03)

| Outlet | Retention | Use |
|---|---|---|
| `money.udn.com` | **~12 months.** Cliff measured between story 8947103 (404) and 8974899 (200, dated 2025-08-31) | Current months only |
| `news.cnyes.com` | **Retains to 2020 and earlier.** 15 of 15 sampled ids from 2020→2026 returned 200 | The archive channel for anything older than a year |
| `api.cnyes.com` | 403 at the proxy (policy denial) | Unusable — so cnyes's own site search, which is client-rendered off that API, cannot be driven server-side |

The trap this creates: a web search still returns *cached snippets* of purged
udn articles, so a 2022 story looks findable and 404s when fetched. Two such
snippets (6933086, 6945844) were chased before the retention cliff was measured.
For any month older than about a year, go to cnyes first.

## The search key that works

The Bureau's monthly write-up uses a standard construction:

> 在完全不避險下，壽險業兌換利益為 −3,221 億元，**有 63.07% 避險比率後**，避險部位產生評價利益 2,452 億元…

So `完全不避險` + `避險比率` is the highest-yield query pair, far better than
month-name queries — the search engine largely ignores a year token and returns
recent articles whatever period is asked for.

## Confirmed coverage

Every row below verifies: each figure was located in its own cited article by
`scripts/stage1_briefing_press.py` (0 verification failures, 16/16 checks).

| Month | Ratio | Source | Published | Note |
|---|---|---|---|---|
| 2024-04 | 66% | cnyes 5577871 | 2024-05-28 | whole-percent only — rounded |
| 2024-12 | 66.39% | udn 9292493 | 2026-01-27 | year-end anchor; carries denominator 15.6兆 |
| 2025-04 | 63.07% | cnyes 6000672 | 2025-05-29 | reserve 1,648億 ties exactly to the release |
| 2025-08 | 62.25% | udn 9039413 | 2025-09-30 | reserve ties to release |
| 2025-10 | 58.55% | udn 9167271 | 2025-11-27 | first sub-60%; reserve ties to release |
| 2025-12 | 50.23% | cnyes 6323663 | 2026-01-27 | year-end anchor; denominator 15.4兆 |
| 2026-01 → 2026-07 | 47% → 42.94% | mixed | — | monthly, from Stage 1 |

Added by this pass: **2024-04 and 2025-04**. The other two 2025 finds (62.25%,
58.55%) were recovered independently from cnyes and matched the existing udn
rows exactly — a useful check that the extraction method is sound.

## Searched without result

No contemporaneous monthly article carrying the ratio was found for any month in
**2020-01 → 2024-03**, across `money.udn.com` (purged), `news.cnyes.com`,
`news.cts.com.tw` and unrestricted queries, using both month-name and
`完全不避險` formulations.

One direct negative worth recording: cnyes 4510085 (2020-07-30) is the monthly
FSC write-up for June 2020 and gives 兌換損益, 避險工具損益, 避險工具換匯成本 and
外匯價格變動準備金 — **but no ratio**. That is the release's own field set.

**Inference, not fact.** The ratio appears to have entered the monthly press
write-up somewhere between mid-2020 and early 2024, later than the statistic
itself, which Economic Daily dates to ROC 109. A single 2020 article is weak
evidence; the honest reading is that the *series* starts 2020 but *monthly press
reporting of it* starts later, and the recoverable history is correspondingly
shorter. Pinning that transition month is the next useful piece of work.

## Next queries worth running

1. `完全不避險` restricted to cnyes, paired with each of 2023 / 2024 — to find
   where monthly reporting of the ratio begins.
2. Year-end anchors for 2020, 2021, 2022, 2023 — reported retrospectively, and
   the only months that also carry the denominator.
3. Ratings-agency pieces (中華信評 / Fitch) — 6300469 gives a sector ratio of
   "約 57%" as at late 2025 and 5941594 discusses 2024–25 exposure; these carry
   sector aggregates that may date earlier figures.
