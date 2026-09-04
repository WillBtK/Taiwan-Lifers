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
| 2025-09 | — (denominator 15.1兆 only) | cnyes 6260090 | 2025-12-03 | legislator citing FSC data at the Finance Committee |
| 2025-10 | 58.55% | udn 9167271 + udn 9209554 | 2025-11-27 / 12-17 | first sub-60%; reserve ties to release; **carries denominator 15.2兆 and foreign investments 22.3兆** from the FSC's written report to the Legislature — the first non-year-end denominator |
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

### Bisection result (decisions 1.11)

Bisecting 2020-06 → 2024-04 shows a **precision gradient**, not an on/off switch:

| Period | How the ratio appears | Source |
|---|---|---|
| 2020-06 | absent from the monthly write-up | cnyes 4510085 |
| 2021–22 | spoken range, "一般都在 60%～70% 以上" (壽險公會) | cnyes 4900483 |
| 2023–25 | spoken range in commissioned research, "約六至七成" | udn 9297709 |
| 2024-04 | whole percent, "66%", from the Bureau | cnyes 5577871 |
| 2025-04 → | two decimals, 63.07% … 42.94% | cnyes 6000672 etc. |

Only the last two rows are the regulatory series. **Treat 2024-04 as its
practical start.**

The search index does reach cnyes's 2021–23 output (it returns 4748550, 4800682,
4900483, 5116875), so the absence of a monthly ratio write-up there is evidence
rather than a failure to look — but not proof, since cnyes articles are fetchable
by id yet not enumerable while `api.cnyes.com` is blocked. Exact-figure queries
built from the release channel's own reserve balances (2,289億 for 2022-12,
920億 for 2023-12) did not break through either.

## Also closed

`www.ib.gov.tw`, the Insurance Bureau's own site, carries the FSC monthly
release verbatim — a mirror, not a second channel. The two supervisory research
PDFs that would plausibly hold a historical series (`www.tigf.org.tw`,
`www.tpefx.com.tw`) are both 403 at the proxy.

## Year-end anchors 2020–2023: closed as exhausted through press

A second bounded pass (2026-09-04) recovered no pre-2024 year-end value:
retrospective queries on cnyes return the same recent-article set; the
ratings-agency pieces (6300469, 5941594) carry qualitative statements only; the
Finance Committee article (6260090) and the FSC written-report article (9209554)
yielded 2025 monthly denominators instead — a better prize, but not history.
The route to any pre-2024 sector figure, if one exists, is the two blocked
government sources (`ins-info.ib.gov.tw`, `data.gov.tw`) or documents outside
this environment's egress. Do not spend further press searches on it.

## Derivable now

Hedge principal = ratio × denominator at the denominator-bearing months:
2024-12 NT$10.36tn → 2025-10 8.90tn → 2025-12 7.74tn. The traditional hedge
book shrank ~NT$2.6tn in twelve months; 2025-09's denominator (15.1兆) awaits a
ratio for that month.
