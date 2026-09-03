# Hedge-ratio backfill — working brief

Continuing work on the sector hedge ratio in `config/briefing_press.json`.
Coverage ledger: `docs/briefing_coverage.md`. Rationale: `docs/decisions.md`
1.2, 1.9, 1.10.

## Three things that will otherwise cost you a day

1. **The FSC monthly release does not carry the ratio.** It looks like the
   obvious source, it is already fully parsed by Stage 1 (91 editions, 2018-05 →
   2025-12), and it carries hedging P&L and the FX reserve but never the ratio,
   the denominator or the foreign-investment total — verified across the archive
   in decisions 1.9. Do not re-propose it.

2. **`money.udn.com` purges at ~12 months, and search engines hide this.**
   Cached snippets of purged stories still rank, so a 2022 article looks
   reachable and 404s on fetch. For anything older than about a year use
   `news.cnyes.com`, which retains to 2020. Measured cliff: story 8947103 (404)
   / 8974899 (200, 2025-08-31).

3. **The series is sparse, and that is the finding, not a failure.** No
   contemporaneous article carrying the ratio has been found anywhere in
   2020-01 → 2024-03. Record a gap as a gap. Never substitute a narrative
   mention ("避險比率約六至七成", "外匯風險比") for the regulatory figure — those
   are commentary, and one common trap is the LIA's *foreign investment as a
   share of funds* (64.73% in 2020), which is not a hedge ratio at all.

## Method

The Bureau's monthly write-up uses a fixed construction:

> 在完全不避險下，壽險業兌換利益為 −3,221 億元，**有 63.07% 避險比率後**…

Query `完全不避險` + `避險比率`, restricted to `news.cnyes.com`. This beats
month-name queries, which the search engine largely ignores — it returns recent
articles whatever period you ask for.

Then, per candidate:

```bash
python3 scripts/probe_briefing_article.py <url>          # byline date + keyed sentences
```

Read off the exact printed figure and its reference month, add a row to
`config/briefing_press.json` (format: any existing row), and verify:

```bash
python3 scripts/stage1_briefing_press.py                 # must be 0 verification failures
```

Every figure must appear literally in its own cited article or the run fails —
that is the point of the config-and-verify pattern, so write figures exactly as
printed (億 / 兆 / %), not converted.

**Free cross-check:** where a row carries `fx_reserve_total`, it should tie to
the release for the same month. 2025-04, 2025-08 and 2025-10 all tie exactly.
A tie confirms the article is reporting the month you think it is.

## Open pieces, in priority order

1. **Pin where monthly reporting of the ratio begins** — somewhere between
   mid-2020 and early 2024. cnyes 4510085 (2020-07-30, June 2020) carries the
   release field set with no ratio; 5577871 (2024-05-28, April 2024) carries
   66%. Bisect between them.
2. **Year-end anchors for 2020–2023.** Reported retrospectively, and the only
   months that also carry the denominator — so they are worth more per row than
   any ordinary month.
3. **Ratings-agency pieces** (中華信評, Fitch) as a secondary route to sector
   aggregates: cnyes 6300469 gives "約 57%" for late 2025, 5941594 discusses
   2024–25 exposure.

If 1 and 2 come back thin, pre-2024 sector series 1/2/5 should be planned on
year-end anchors plus the six-firm panel (Stage 3), and Stage 2 told to expect
an irregular ratio series with interpolation flagged in the basis.
