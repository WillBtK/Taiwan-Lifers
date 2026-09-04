# Decisions log

Append-only. One entry per decision: what was decided, why, what was rejected,
and which files it touches. A later stage should be able to start from this
file plus `STATUS.md` and the README, without re-reading the repo.

---

## Stage 0 — Scaffold (2026-09-03)

### 0.1 Design spec placed verbatim, then amended only where the spec requires

**Decision.** `docs/artifact_design_system.md` is the user-supplied replication
spec, copied byte-for-byte (47,758 bytes, md5 `79d78825ae54e782f0639c589cf0eb85`).
It was subsequently amended in §5b, §6, §7 and §10 only — to record the palette
validation outcome that §7 itself instructs the first project needing `--gold`
and `--rose` to record.

**Reason.** The README's "unchanged" instruction and the spec's own §7/§10
("record the outcome here", "amend THIS file… rather than patching around it in
page-building code") pull in opposite directions. The spec's instruction is the
more specific one and is the one that prevents the next project repeating the
work, so it wins. README Stage 0 has been reworded to say so.

**Rejected.** Leaving the spec untouched and putting the validation result only
in this log — it would be invisible to the next repo, which copies the spec but
not this file.

**Files.** `docs/artifact_design_system.md`, `README.md`.

### 0.2 Palette: dash encoding is mandatory from four series, not five

**Decision.** Any chart with 4+ series encodes each series by line style as well
as hue. Recorded in spec §5b, §6, §7, §10.

**Reason.** Measured, not judged. `dataviz/scripts/validate_palette.js` against
the spec's own surfaces:

| Set | Mode | Adjacent pairs | All pairs |
|---|---|---|---|
| 4-hue | light `#FFFFFF` | pass | **fail** — blue↔purple ΔE 1.0 protan, 9.9 normal |
| 4-hue | dark `#1A1E24` | pass | **fail** — blue↔purple ΔE 5.1 deutan, 11.5 normal |
| 6-hue | light `#FFFFFF` | fail (gold chroma 0.098 < 0.100) | fail — as above |
| 6-hue | dark `#1A1E24` | fail (gold L 0.721 > 0.67 band) | fail — as above |

A normal-vision ΔE below 15 is a hard fail: full-colour readers cannot separate
the pair. Purple is slot 4, so the failing pair is present in every four-series
chart — which is the commonest form in this system. The spec's existing 5-series
threshold was therefore one slot too late.

**Rejected.** (i) Reordering the fixed hue sequence to separate blue and purple
— it would repaint every chart in every project built on the spec, for a problem
that secondary encoding solves; (ii) dropping purple to a three-hue working set
— too restrictive for series 6, which has five categories.

**Files.** `docs/artifact_design_system.md` (§5b, §6, §7, §10).

### 0.3 Gold re-step recommended, not applied

**Decision.** `--gold` fails two checks as specified: chroma 0.098 against a
0.100 floor (light), lightness 0.721 against a 0.48–0.67 band (dark).
Re-stepping to `#8A6A12` (light) and `#B08C38` (dark) returns ALL CHECKS PASS
for the full six-hue set in both modes. Recorded in spec §7; **not** applied to
the §2 tokens.

**Reason.** A token change propagates to every page built from this spec,
including the sibling monitors. That is the user's call, not Stage 0's.

**Rejected.** Silently editing the tokens; or leaving the failure unrecorded.

**Files.** `docs/artifact_design_system.md` (§7) — pending, on approval:
the three `:root` blocks in §2.

### 0.4 Schema `tlfx`, not prefixed tables in `public`

**Decision.** All tables live in schema `tlfx` (README §6), applied to project
`term-premium-atlas` (`xzhoykybwlkefgvgwnii`) as migration
`supabase/migrations/0001_tlfx_schema.sql`. RLS enabled on all 11 tables with no
permissive policy; ingestion uses the service role.

**Reason.** The README specifies schema `tlfx`. The sibling monitors in the same
project (`uk_ldi_*`, `nl_wtp_*`) use prefixed tables in `public`; a separate
schema keeps the fourth monitor from crowding that namespace further. RLS-on
matches every existing table in the project.

**Rejected.** `public.tlfx_*` for consistency with the siblings — consistency
with the README matters more, and the schema boundary makes the Stage 7
cross-market export cleaner.

**Files.** `supabase/migrations/0001_tlfx_schema.sql`.

### 0.5 Two separate basis types, not one

**Decision.** `tlfx.accounting_basis` (`IFRS4`, `IFRS17`) and
`tlfx.measurement_basis` (`disclosed`, `estimated`, `spliced`) are distinct
Postgres enums. `firm_quarterly.basis` is part of the primary key.

**Reason.** README §9 forbids splicing disclosed and estimated CBC series
without a flag, and separately requires both IFRS bases where firms publish
them. These are different failure modes: one is a measurement provenance
question, the other a definitional break in the reporting entity. A single
free-text column invites conflating them at Stage 3, which is exactly where it
would be expensive to unwind.

**Rejected.** One `basis text` column with a check constraint.

**Files.** `supabase/migrations/0001_tlfx_schema.sql`, `src/tlfx/provenance.py`.

### 0.6 `derived_series` carries provenance, not just values

**Decision.** `derived_series` holds `source_url`, `source_doc`, `retrieved_at`,
`vintage`, `basis`, `basis_note` alongside `definition_version`. Natural key
enforced by a unique index on `(series_key, coalesce(entity_id,''), obs_date,
vintage)` — a primary key cannot hold a `coalesce`, and `entity_id` is null for
sector rows.

**Reason.** The spec requires every chart and table in the artifact to carry a
source line naming source and vintage. Stage 6 builds the artifact from
`derived_series` alone; without these columns it would have to re-query upstream
tables to write its captions.

**Rejected.** Deriving source lines at Stage 6 by joining back to source tables —
it breaks the single-blob export and re-introduces a runtime dependency.

**Files.** `supabase/migrations/0001_tlfx_schema.sql`, `README.md` §6.

### 0.7 Net open FX position stored once, presented many ways

**Decision.** Series 2 is stored in NT$ mn. USD, % GDP, % assets and × capital
are separate rows of the same `series_id` under different `unit` values, selected
in the artifact by a `.seg` unit toggle.

**Reason.** The spec bans dual-axis charts outright, so the five units the README
lists cannot be one chart. Storing the presentations as rows keeps the toggle a
pure lookup and keeps each presentation independently traceable.

**Rejected.** Computing presentations client-side in the artifact — it would put
GDP and capital denominators into the page without provenance.

**Files.** `supabase/migrations/0001_tlfx_schema.sql`, `README.md` §3.

### 0.8 User-Agent is per-host, with measured reasons

**Decision.** Default UA is the descriptive `TLFX-monitor/0.1`. Two overrides,
each recorded with the measurement that justifies it, in
`src/tlfx/provenance.py`.

**Reason.** No single string works. Measured 2026-09-03:
`fred.stlouisfed.org` answers `curl/8.5.0`, `python-requests/2.32` and
`Wget/1.21` in under 1.5s but read-times-out (>18s) on both the descriptive
string and a Chrome string — its edge tarpits agents it does not recognise.
Conversely `ir.ctbcholding.com` returns 403 to everything except a browser
string. An initial reading that attributed FRED's behaviour to browser-like
agents was wrong and is corrected in the code comment.

**Rejected.** A single browser UA everywhere (breaks FRED); a single honest UA
everywhere (breaks CTBC).

**Files.** `src/tlfx/provenance.py`, `scripts/check_allowlist.py`.

### 0.9 Allowlist probes retry transport errors but never status codes

**Decision.** `scripts/check_allowlist.py` retries connection resets, closed
tunnels and read timeouts twice with backoff, at 4-way concurrency; HTTP status
codes are never retried. An optional `expect` column marks endpoints that are
reachable but answer non-2xx by design.

**Reason.** At 8-way concurrency the sandbox proxy produced false failures that
did not reproduce — FSC-English and FRED both flipped between runs. A single
attempt cannot distinguish a blocked host from a flaky egress path, and a
Stage-0 report that cries wolf is worse than none. A 403 is an answer, not a
transient fault, so it is recorded as-is. The FRED API returns 400 without a key,
which is proof of reachability, hence `expect`.

**Rejected.** Single-attempt probing (the script's first draft); retrying 5xx and
403 (would mask real source changes).

**Files.** `scripts/check_allowlist.py`, `config/allowlist.tsv`.

### 0.10 Chinese FSC press-list id confirmed as 96

**Decision.** `https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2` is the
correct Chinese press-release list; the README's "unconfirmed" note is resolved.
Individual releases sit at
`…&mcustomize=news_view.jsp&dataserno=YYYYMMDDNNNN&dtable=News`.

**Reason.** Fetched 2026-09-03: page title `新聞稿`, carrying insurance items
including `壽險業115年截至6月底外幣保險商品銷售情形` dated 2026-08-25 (the
foreign-currency policy premium release of README §4.1). Dates are ROC calendar
(115年 = 2026).

**Caveat for Stage 1.** id=96 is the *all-FSC* press list, not an insurance-only
feed, and the monthly profit/loss-and-FX release was not on page 1. Stage 1 must
either paginate this list filtering on title, or find the Insurance Bureau's own
release page. Do not assume a fixed page position.

**Files.** `config/allowlist.tsv`, `README.md` §7.

### 0.11 Releases are located by keyword search across two channels, never by position

**Decision.** `src/tlfx/fsc.py` finds FSC releases by POSTing the press list's
own search form (`keyword`, `qptdate`, `qdldate`, `page`, `pagesize`) and
filtering titles by regex, querying both the FSC list (`id=96`) and the
Insurance Bureau mirror (`id=239`) and merging on `dataserno`. Republic-of-China
years are converted by `roc_to_date` (114年 = 2025).

**Reason.** The earlier open question — "the monthly release was not on page 1"
— was the wrong frame. `id=96` is a single reverse-chronological stream of every
FSC release across banking, securities and insurance, so the monthly release
sits at a different offset every month and no page position is stable. The list
exposes a server-side search, which makes position irrelevant. Both regulators
run the same CMS, so covering the mirror costs one extra request and removes a
single point of failure.

**Rejected.** (i) Walking pages until the title appears — brittle and slow, and
it breaks whenever release cadence changes; (ii) the English list — the README
notes the Chinese carries more detail; (iii) the Insurance Bureau statistics
section as the primary locator, which needs a deeper crawl than the press
search and is not needed while the press channel carries the series.

**Measured outcome, 2026-09-03.** 90 monthly editions, May 2018 to December
2025, with exactly two gaps (March 2019 and March 2020, both to be checked at
Stage 1 — likely retitled rather than missing). That is roughly twenty months
more history than README section 3 assumes for series 4 and 3(a). Field
coverage in the older editions is unverified: Stage 1 must confirm which of the
FX-reserve buckets and the hedge-ratio fields the 2018–2019 releases carry
before extending those series' start dates.

**The material finding: the series stops at December 2025.** The December 2025
edition (`dataserno` 202601270003, published 2026-01-27) is the last one on
either channel. There is no 2026 edition, which contradicts the README's own
reference list; that citation has been corrected. The likely cause is the
IFRS 17 / TW-ICS transition on 1 January 2026, consistent with the FSC's
May 2026 solvency-regime item and its August 2026 amendment to the insurance
financial-reporting preparation standards.

**Stage 1's first task, therefore, is not parsing — it is locating the 2026
sector data.** In order: (i) the Insurance Bureau statistics sections
(`id=48`, `id=385`), whose tables are not exposed as plain anchors and need a
deeper crawl; (ii) the TII statistics service, once the sandbox egress block on
`*.tii.org.tw` is lifted; (iii) the CBC balance sheet (the Stage 2 source,
already reachable), which gives foreign assets and equity but not the hedge
ratio or the reserve buckets, so it is a cross-check rather than a substitute.
If none carries the sector hedge ratio from 2026, series 4 ends in December 2025
and the headline economic ratio must be carried forward from the firm panel
(Stage 3) instead — a definitional change that would need recording here.

**Files.** `src/tlfx/fsc.py`, `README.md` §4.1 and §10.

### 0.12 The 2026 sector hedge ratio is press-reported; the notice's definitions are adopted as v2

**Decision.** From January 2026 the sector hedge ratio and reserve totals are
ingested from press reports of the Insurance Bureau's monthly briefing, stored
with `measurement_basis = 'press_reported'` and the article as `source_doc`.
Firm financial statements (quarterly, notice §10 disclosures) are the
provenance-clean v2 source and the sector aggregate is built from them. The
notice's own definitions of net exposure (§二) and hedge ratio (§九) replace the
README's; its four bucket names replace P/Q/X/Y.

**Reason.** The monthly release page ended at December 2025 but the briefing
did not: the README's 50.2% and 42.9% trace to Economic Daily reports of the
Insurance Bureau deputy director's monthly statements, not to Setser (2019),
which predates them. The Life Insurance Association's public statistics carry
no hedge or FX data (checked 2026-09-03). Media hosts are blocked at the
sandbox egress, so the numbers are reachable only via search snippets — a
degraded channel that must be flagged on every figure it produces.

**Rejected.** Treating series 4 as ended at 2025-12 — the figures exist and are
regulator-sourced. Treating press reports as equal to a release — they are oral
statements transcribed by a journalist, so they get their own basis value.

**Files.** `README.md` §3, §4.1, §9, §10; `config/allowlist.tsv`;
`supabase/migrations/0002_regime_v2.sql`; `docs/sources/`.

---

## Stage 1 — Sector series from the FSC (2026-09-03)

### 1.1 What the monthly release carries — and the parser built for it

**Decision.** `src/tlfx/fsc_parse.py` parses every edition of the monthly
release into the fields the release actually prints, measured across all 91
editions (May 2018 – December 2025): pre-tax profit and owners' equity for
life, non-life and total; an FX table (FX gain/loss, hedging P&L — one line
to 2019-12, split into instrument P&L and swap cost from 2020-01 — net change
in the FX price-fluctuation reserve, and their sum); and a closing paragraph
with the TWD move year-to-date, the life insurers' reserve balance, its change
versus the prior month (to 2019) or prior year-end (2020-09→), and net
foreign-investment income (2020-09→). January and February 2020 alone print
total assets and the foreign-investment total. Flow items are cumulative
year-to-date as published; the table records that (`flows_are_ytd`) and
leaves monthly differencing to `derived_series`. Amounts are stored in NT$
million, converted exactly (×100) from the printed NT$ 億. `vintage` is the
edition's publication date, so a re-release of a month can coexist with the
original. Migration `0003` adds the columns.

Tables are identified by the section header preceding them and by their own
row labels, never by position — December 2019 wraps each header in a
one-cell `<table>` (six tables), March 2020 has one — and a table only counts
once it yields figures.

**Coverage.** 91 editions, two irregularities at source: March 2019 has no
edition under any title on either channel (searched by month, by both title
wordings, and by listing every insurance release published March–May 2019),
and March 2020 is retitled without the profit and equity sections
(`dataserno` 202004300002, found by a second keyword). `fsc.py` now queries
both keywords and accepts both title forms. Because flows are YTD, the
missing March 2019 loses only that month's balance-sheet points, not the flow.

**Checks.** 423 of 423 pass: life + non-life = total for profit and equity;
(1)+(2)+(3) = total in the FX table; the narrative's combined figure = the
table's; and, across editions, prior balance + stated change = this balance
(83 cross-edition ties, largest relative error 0.3%).

**Rejected.** Storing the printed 億 unchanged — the repo convention fixes
NT$ million and the conversion is exact. Storing life+non-life totals only —
the monitor is about lifers and non-life FX P&L is one to two orders of
magnitude smaller, but the totals are what the FSC headlines, so all three are
kept.

**Files.** `src/tlfx/fsc_parse.py`, `src/tlfx/fsc.py`, `src/tlfx/emit.py`,
`scripts/stage1_sector_monthly.py`, `supabase/migrations/0003_*.sql`,
`data/sector_monthly_release.csv`.

### 1.2 The hedge ratio was never in the release: series 4 is press-reported for its whole life

**Decision.** README §4.1 said the release carries the hedge ratio, hedging
cost and the reserve buckets. It does not, in any of the 91 editions; nor
does it carry the foreign-investment total or the regulatory exposure. Those
figures are stated at the Insurance Bureau's monthly press briefing and reach
the public through the press — and this has been so since the briefing series
began in ROC 109 (2020), per Economic Daily's own dating. Series 4 therefore
has one measurement basis, `press_reported`, before and after the 2026 regime
change; the v1/v2 split is a definitional break (notice §九), not a channel
break. README §3 and §4.1 are corrected.

**Consequence for README §3 reconciliation checks 1 and 2.** Both need the
regulatory denominator, which the briefing gives only at year-end (23.0兆 for
2024, 22.8兆 for 2025, each "less FX-policy liabilities" — the notice's
further deductions are not mentioned). Check 1 was run where the inputs exist:
15.4兆 × (1 − 0.5023) = 7.665兆 against the Bureau's stated net exposure of
"約7.7兆" — 0.5% apart, an identity holding within the rounding of a spoken
figure (HANDOFF item 2). Check 2 cannot be run from sector data at all and
moves to Stage 2/3 (CBC foreign assets, firm FX-policy liabilities).

**What was ingested now.** Every 2026 month to July (the latest briefing,
1 September 2026), plus December 2025 and the year-end 2024 anchor, plus the
two 2025 months (August, October) that surfaced while locating the 2026
articles. The 2020–2025 monthly backfill of the briefing series is a
follow-up task: it is a press search month by month, not a parse.

**Rejected.** Treating the briefing as an FSC source with `basis =
'disclosed'` because the speaker is the regulator — the number passes through
a journalist and the articles do restate figures (the February 2026 reserve
balance was later given as 6,277億 against 6,259億 first reported). Kept as
first reported, revision noted in `config/briefing_press.json`.

**Files.** `README.md` §3, §4.1; `config/briefing_press.json`.

### 1.3 The natural key of `sector_monthly` includes the reporting channel

**Decision.** Migration `0004` makes the primary key `(obs_month,
reporting_channel, vintage)`, with `reporting_channel` not null, default
`release`, checked against `release | briefing_press | firm_statements`.

**Reason.** The briefing is held the day the release is posted (August 2025:
both 2025-09-30; October 2025: both 2025-11-27; December 2025: both
2026-01-27), so the release row and the press-reported row of one month share
`(obs_month, vintage)` and the Stage 0 key could hold only one of them. The
channel is part of what the observation is. Consumers must select a channel;
months from August 2025 carry two.

**Rejected.** Folding the channel into `vintage` by shifting the press row a
day — a lie about the date. Keeping the press rows in a separate table — the
columns are the same and Stage 6 wants one series with a basis flag.

**Files.** `supabase/migrations/0004_sector_monthly_pk_channel.sql`,
`scripts/stage1_*.py` (conflict target).

### 1.4 Press-reported rows: figures as printed, verified against the fetched article, with the notice's identities as checks

**Decision.** `config/briefing_press.json` records each figure exactly as the
cited article prints it (億, 兆, %), with the article URL, publication date,
outlet, the official quoted and the sentence. `scripts/stage1_briefing_press.py`
fetches every article in full, fails the run if a figure string is absent
from its own citation, converts units, and runs the identities the February
2026 notice implies: P + Q = reserve total, reserve + X + Y = buffer total,
buffer ÷ net exposure = the "absorbable appreciation" the Bureau quotes, and
net exposure = denominator × (1 − ratio). All 16 checks pass (bucket sums
exact; absorbable-appreciation within 0.4%; the denominator identity within
0.5%). `docs/sources/press/briefing_excerpts.md` keeps the quoted sentences;
full articles stay in the uncommitted cache.

**Measured change since Stage 0.** `money.udn.com`, `news.cnyes.com` and
`news.cts.com.tw` now answer the default User-Agent with 200, so the 2026
figures come from fetched articles, not search snippets; decision 0.12's
"snippets only" caveat is superseded. `udn.com` (apex), `www.cna.com.tw`,
`www.chinatimes.com`, `www.ctee.com.tw` and `taronews.tw` remain 403 at the
proxy; every Economic Daily story id is also served by
`money.udn.com/money/story/5613/{id}`, and CNA copy is carried by CTS.

**Interpretation notes recorded with the rows.** (i) The Bureau's
"實質避險比率" (55–56%) is stored only as `effective_hedge_ratio_memo`. (ii)
From June 2026 the special reserves are quoted as one total (3,651億, up from
2,897億); the Bureau said in March and May that Y stays zero until 2027, so
the total sits under X with the caveat in `source_note`. (iii) 2026 profit
and equity figures are IFRS 17 and are not comparable with the 2025 release
series. (iv) Share-of-instrument figures are spoken bounds (">75%") and are
stored as text notes, not numbers.

**Rejected.** A per-month scraper of the outlets — three outlets, three
layouts, and the numbers must be read in context (month-end versus monthly
flow, restated versus first-reported). A curated config with literal
verification is the honest shape for eleven rows a year.

**Files.** `config/briefing_press.json`, `scripts/stage1_briefing_press.py`,
`docs/sources/press/briefing_excerpts.md`, `data/sector_monthly_briefing.csv`.

### 1.5 `*.tii.org.tw`: the server omits its intermediate certificate; the repo supplies it

**Decision.** The four TII hosts serve only their leaf certificate
(`CN=*.tii.org.tw`, issued by TWCA Secure SSL Certification Authority) with
no intermediate, so every client without that intermediate cached fails with
"unable to get local issuer certificate". Browsers succeed only through AIA
fetching. The intermediate — taken from `www.fsc.gov.tw`'s complete chain,
SHA-256 `1A:2C:75:FD:09:6E:04:99:E9:FF:6A:C7:4E:52:6F:61:EA:AE:3E:DF:C8:C2:EA:44:36:FE:E0:C2:4D:8B:7D:0E`,
valid to 2030-10-16, and verified against the certifi store's TWCA Global
Root CA — is checked in at `config/certs/twca_secure_ssl_ca.pem`.
`provenance.ca_bundle_for(url)` merges it with the default store for
`tii.org.tw` hosts only; `fetch()` and the allowlist probe pass it as
`verify=`. Verification is never disabled. All four hosts answer 200
(2026-09-03). HANDOFF item 1 is closed; Stage 0's "unfinished proxy
provisioning" reading was wrong — the fault is at the origin.

**Rejected.** `verify=False` for those hosts (forbidden, and unnecessary);
asking for an environment change (nothing to change).

**Files.** `config/certs/twca_secure_ssl_ca.pem`, `src/tlfx/provenance.py`,
`scripts/check_allowlist.py`, `config/allowlist.tsv`.

### 1.6 Firm statements as the v2 source: format seen, one figure reconciled, ingestion left to Stage 3

**Decision.** Firm-level 2026 disclosure was looked at firsthand but not
ingested. Cathay's 2Q26 results deck (fetched from `www.cathayholdings.com`,
56 pages) carries a "Cathay Life – FX hedging strategy" page: FX assets
NT$5.54tn, an FX-risk-exposure / reserve-for-FX-policy split of 74/26, hedging
cost 1.21% for 1H26 (0.96% FY23, 1.56% FY24, 1.57% FY25) and an FX volatility
reserve of NT$130.9bn at 1H26 (113.8bn FY25, 123.9bn 1Q26). Economic Daily's
tabulation of all twenty life insurers' Q2 2026 statements (3 September 2026)
gives Cathay 1,309.3億 — the same figure — and a sector total of 6,997.3億,
which matches the Bureau's June briefing figure of 6,997億 to within 0.3億.
The same tabulation puts the twenty firms' 2025 year-end balance at 6,178.2億
against the briefing's 6,137億: a 41億 gap that Stage 3 must explain
(coverage, the IFRS 17 opening-balance transfers the notice §四 allows, or
timing) before the firm aggregate is used as the sector series.

**Reason for deferring.** `entities` is empty, the six-firm scraper is Stage
3's deliverable, and the press tabulation is not the provenance-clean source
the notice §10 disclosure is. Putting press-reported firm rows in
`firm_quarterly` would defeat the point of the v2 path.

**Files.** none (recorded here and in `HANDOFF.md`).

### 1.7 Stage 1 reconciliation set

**Decision.** With the regulatory denominator absent from the release, the
Stage 1 checks are: (a) in-edition arithmetic (four per edition), (b)
cross-edition reserve-balance ties, (c) the v2 identities of 1.4 wherever
their inputs exist. All pass; the run log and check rows are written to
`tlfx.run_log` / `run_reconciliation` alongside the data. README §3's own
checks 1–2 are re-homed to Stages 2–3 in the README text.

**Files.** `README.md` §3, `scripts/stage1_*.py`.

### 1.8 Gold re-step: already applied; decision 0.3 superseded

**Decision.** No action. The `--gold` tokens in all three `:root` blocks of
`docs/artifact_design_system.md` already carry the re-stepped values
(`#8A6A12` light, `#B08C38` dark), and §7 and §10 of the spec record them as
applied. Decision 0.3's "recommended, not applied" was overtaken later in
Stage 0 and the STATUS/HANDOFF lines saying it awaited approval were stale;
both are corrected. Kept as applied: the change is measured (all six hues
pass the CVD and normal-vision checks in both modes), gold is only the fifth
hue and only series 6 needs it, and dash encoding is mandatory from four
series regardless. Sibling monitors adopt the values when they next copy the
spec; a token mismatch between projects until then is cosmetic.

**Files.** `STATUS.md`, `HANDOFF.md`.

### 1.9 The FSC release cannot substitute for the briefing; 2020-01 is the floor

**Decision.** The monthly FSC release is not a source for the hedge ratio or
the regulatory denominator, at any depth of its archive. The backfill stays on
the press-reported briefing and starts at 2020-01. `docs/FSC_OFFICIAL_SOURCE.md`,
written earlier in Stage 1b asserting the opposite, is removed.

**Reason.** A web search for an official source surfaced
`新聞稿-XXX年M月保險業損益、淨值，以及兌換損益、避險損益與外匯價格變動準備金情形`
on `fsc.gov.tw` and it was briefly taken for a new, better-structured channel
reaching back to 2018. It is the release Stage 1 already parses — 91 editions,
2018-05 → 2025-12, channel `release` — so re-fetching it adds nothing, and it
does not carry the fields the backfill needs. Re-verified from the other
direction, four editions spanning the archive:

| Edition | 避險比率 | 曝險 | 國外投資金額 | 避險損益 | 外匯價格變動準備金 |
|---|---|---|---|---|---|
| 107年8月 (2018-08) | 0 | 0 | 0 | 1 | 3 |
| 108年9月 (2019-09) | 0 | 0 | 0 | 7 | 6 |
| 109年6月 (2020-06) | 0 | 0 | 0 | 7 | 6 |
| 114年4月 (2025-04) | 0 | 0 | 0 | 8 | 7 |

(occurrence counts in the fetched page text). This agrees with 1.2's
all-91-edition check. `foreign_investments` is populated in 2 of 91 release rows.

**Consequence — depth of history is asymmetric.** The denominator can be pushed
back (CBC foreign assets, Stage 2, to 2000); the ratio cannot go before 2020,
because the briefing series itself begins in ROC 109 per Economic Daily's own
dating (already cited in the 2025-10 row's note). Hedge principal needs both, so
2020-01 binds. Pre-2020 sector series 1/2/5 need either a different ratio source
— TII/保發中心's statistics database and the LIA are the untested candidates,
and `*.tii.org.tw` is reachable since 1.5 — or they stay on the six-firm panel.

**Rejected.** Extending the backfill to 2018 on the strength of the FSC archive
reaching that far: the depth is real, the fields are not there.

**Files.** `docs/FSC_OFFICIAL_SOURCE.md` (deleted), `BACKFILL_HANDOFF.md`.

### 1.10 cnyes, not udn, is the archive channel; the ratio series is sparser than the statistic

**Decision.** The briefing backfill runs on `news.cnyes.com` for any month older
than about a year, and its deliverable is every month where a figure was
actually published, with gaps recorded as gaps — not a 67-row monthly series.
Coverage is tracked in `docs/briefing_coverage.md`.

**Reason — measured retention.** `money.udn.com` purges at roughly twelve
months: story 8947103 is 404 while 8974899 (dated 2025-08-31) is 200, a clean
cliff, sampled across 29 ids. `news.cnyes.com` returned 200 for all 15 sampled
ids spanning 2020→2026. Search engines still serve cached snippets of the purged
udn stories, so a 2022 article looks reachable and 404s on fetch; two were
chased that way before the cliff was measured. `api.cnyes.com` is 403 at the
proxy, so cnyes's own site search — client-rendered off that API — cannot be
driven server-side; harvesting goes through domain-restricted web search
instead. All three facts are recorded in `config/allowlist.tsv`.

**Reason — the search key.** The Bureau's monthly write-up uses a fixed
construction, `在完全不避險下…有 X% 避險比率後…`. Querying that phrase is far more
productive than month-name queries, which the search engine largely ignores.

**Result.** Two months recovered, 2024-04 (66%) and 2025-04 (63.07%), both
verifying with 0 failures. 2025-04's reserve balance (1,648億) ties exactly to
the release for the same month, independently anchoring the ratio to April 2025.
The method also re-derived 2025-08 and 2025-10 from cnyes and matched the
existing udn rows exactly.

**Consequence — the recoverable history is shorter than the statistic.** No
contemporaneous monthly article carrying the ratio was found anywhere in
2020-01 → 2024-03. cnyes 4510085 (2020-07-30) is the June 2020 monthly write-up
and carries the release's field set with no ratio at all. The inference — and it
is an inference from one article, not a proven start date — is that the
statistic dates from ROC 109 as Economic Daily says, while *press reporting* of
it began materially later. Pre-2024 sector series 1/2/5 should therefore be
planned around year-end anchors plus the six-firm panel, not a monthly briefing
series. Pinning the month monthly reporting begins is the open piece of work.

**Rejected.** Generating a 67-row monthly template (the earlier
`scripts/backfill_hedge_ratio_search.py`, now removed): it encoded a monthly
cadence that the sources do not have, and an unfilled row is not a null — it is
an untested claim that a figure exists.

**Files.** `config/briefing_press.json`, `config/allowlist.tsv`,
`docs/briefing_coverage.md`, `scripts/probe_briefing_article.py` (replaces the
two earlier backfill scripts), `STATUS.md`, `BACKFILL_HANDOFF.md`.

### 1.11 Bisection result: the ratio is reported as a spoken range before 2024, not a figure

**Decision.** Treat 2024-04 as the practical start of the regulatory ratio
series. Pre-2024 press mentions are spoken ranges and must not be substituted
for it (the rule already stated in `BACKFILL_HANDOFF.md`). The
`docs/briefing_coverage.md` "searched without result" window is closed for
2020-01 → 2024-03 by ordinary press search in this environment.

**Reason.** Bisecting between cnyes 4510085 (2020-07-30, June 2020 write-up,
release field set, no ratio) and cnyes 5577871 (2024-05-28, April 2024, "66% 的
避險比率" attributed to 保險局副局長蔡火炎) shows a *precision gradient*, not a
simple on/off:

| Period | How the ratio appears | Source |
|---|---|---|
| 2020-06 | absent from the monthly write-up | cnyes 4510085 |
| 2021–22 | spoken range, "一般都在 60%～70% 以上", attributed to 壽險公會 | cnyes 4900483 |
| 2023–25 | spoken range in commissioned research, "約六至七成" | udn 9297709 |
| 2024-04 | whole percent, "66%", attributed to the Bureau | cnyes 5577871 |
| 2025-04 → | two decimals, 63.07% … 42.94% | cnyes 6000672 etc. |

So the figure firms up from association commentary, to a Bureau round number,
to a published statistic. Only the last two are the regulatory series.

**Method limit, stated plainly.** The search index does reach cnyes's 2021–23
output — it returned 4748550 (2021), 4800682 and 4900483 (2022), 5116875 (2023)
— so the absence of a monthly ratio write-up in that window is evidence, not
merely a failure to look. It is not proof: cnyes articles are fetchable by
direct id but not enumerable, because `api.cnyes.com` is 403 at the proxy, so a
precise monthly figure published in an article the index will not surface cannot
be excluded. Exact-figure queries built from the release channel's own reserve
balances (2,289億 for 2022-12, 920億 for 2023-12, etc.) returned the same
recent-article set and did not break through.

**Also closed.** `www.ib.gov.tw` — the Insurance Bureau's own site — carries the
monthly release verbatim (same title, same fields, 避險損益 and
外匯價格變動準備金 present, 避險比率 and 曝險 absent), so it is a mirror, not a
second channel. The two supervisory research PDFs that would plausibly tabulate
a historical series (`www.tigf.org.tw`, `www.tpefx.com.tw`) are both 403 at the
proxy.

**Consequence.** Stage 2 should treat the sector ratio as beginning 2024-04,
with 2024-12 and 2025-12 as the only denominator-bearing anchors, and derive
pre-2024 sector series 1/2/5 from the six-firm panel rather than the briefing.

**Files.** `docs/briefing_coverage.md`, `config/allowlist.tsv`, `STATUS.md`.

---

## Stage 2 — Sector balance sheet from the CBC (2026-09-04)

### 2.1 Table 8 parsed; the CBC and FSC populations are the same, so the foreign-asset gap is definitional

**Decision.** `scripts/stage2_cbc_balance_sheet.py` ingests CBC Financial
Statistics Monthly appendix table 8 into `sector_balance_sheet`: 30 months
(2016-12 year-ends, then monthly 2024-10 → 2026-07), 450 long-format rows, 15
line codes, 96/96 checks. CBC foreign assets are adopted as the sector
foreign-asset series; the FSC's 國外投資金額 is kept as a separate, differently
defined measure rather than reconciled away.

**Parsing notes.** The file is Big5 with a flattened bilingual multi-row header,
a ROC year stated once per block and carried forward beneath it, and blank
separator rows. It is already in NT$ million, the repo's storage unit, so no
coercion is applied. Year-end and monthly blocks overlap at 2024-12 and 2025-12;
the values agree exactly and are stored once. Three identities hold to NT$ 1 mn
on all 30 rows and are the stage's checks: asset components = total assets;
liabilities + equity = total assets; the three non-financial portfolio parts =
their subtotal.

**Vintage for a rolling file.** The CSV path is stable while its contents roll
monthly and it carries no publication stamp, so the edition is identified by its
latest observation month (here 2026-07). This is deliberate: the natural key is
`(obs_month, line_code, vintage)`, and a retrieval-date vintage would mint a
fresh copy of every row on each run.

**The population question, settled.** CBC equity ties to FSC equity across all
23 overlapping months at 0.00–0.03%: 2018-12 → 2025-12 against channel
`release`, and 2026-05/06 against `briefing_press`. The tie holds across the
IFRS 17 / TW-ICS transition, so table 8 is on the same accounting basis as the
FSC figures throughout. Two consequences: the Stage 2 parse is independently
validated against a pipeline that shares no code with it, and the two agencies
are measuring the same set of companies.

**Therefore the foreign-asset gap is definitional, not coverage.**

| Year-end | FSC 國外投資 | CBC 國外資產 | Gap | Rel |
|---|---|---|---|---|
| 2024-12 | 23.000兆 | 22.472兆 | 0.528兆 | 2.30% |
| 2025-12 | 22.800兆 | 22.009兆 | 0.791兆 | 3.47% |

The 2025-12 gap breaches the repo's 3% tolerance and it is widening. Because
equity ties exactly, this cannot be explained by a different company set.
Candidate explanations, none yet verified: differing treatment of 國際板債券
(foreign-currency bonds issued domestically by non-resident issuers, which have
their own status under the Insurance Act's overseas cap); a valuation-basis
difference; or the FSC figure being a supervisory aggregate rather than a
balance-sheet line. **The two must not be substituted for one another until this
is resolved** — in particular the regulatory denominator is defined off the FSC
measure, so pairing it with a CBC foreign-asset series would mix bases.

**Files.** `scripts/stage2_cbc_balance_sheet.py`, `data/sector_balance_sheet.csv`,
`out/stage2_cbc_*.sql`, `reports/stage2_cbc_*.json`, `STATUS.md`.

---

## Stage 3 — Firm panel (2026-09-04)

### 3.1 The firm decks are the primary source, and they are machine-readable back to 2011

**Decision.** The six-firm panel leads for series 1, 2, 5, 6 and 7; the sector
press route is demoted to a cross-check. README §7's Stage 2 → Stage 3 ordering
is inverted in practice. `scripts/stage3_cathay_decks.py` indexes the decks and
extracts the FX hedging page.

**Reason — the sector route bottoms out, the firm route does not.** Decisions
1.11 put the sector regulatory ratio's practical start at 2024-04, and 2.1 found
a widening definitional gap between FSC 國外投資 and CBC 國外資產 (3.47% at
2025-12) that blocks using CBC foreign assets as the monthly denominator against
an FSC-defined ratio. So sector series 1/2/5 cannot be built before 2024 from
sector sources at all. Against that:

- Cathay's IR site lists **112 results decks back to 2011 Q4**, at a stable path,
  fetched directly (no MOPS dependency; MOPS itself returns an 800-byte JS shell).
- **Every deck sampled is machine-readable text**, 19k–38k characters, including
  2014 and 2016. README §7's plan to "hand-code the 2013–2019 history where PDFs
  are not machine-readable" is not needed — that assumption is withdrawn.
- One page, "Cathay Life – FX hedging strategy", carries the whole disclosure:
  FX asset base (NT$5.54tn at 1H26), the hedging structure split, the FX risk
  exposure vs reserve-for-FX-policy split (74/26), a five-period hedging-cost
  strip and a six-period FX volatility reserve strip. That is series 1, 2, 5, 6
  and 7 inputs from a single page, quarterly, on one consistent basis — numerator
  and denominator from the same document, which is exactly what the sector route
  cannot offer.

**Extraction: bind pie values through the wedge, never straight to the caption.**
The captions sit outside the pie on leader lines, so a value inside one wedge can
be nearer a neighbouring wedge's caption. Direct nearest-caption pairing swaps
the 60% and 4% shares on the 2Q26 deck. The filled wedges are recoverable via
`page.get_drawings()`, and both value→wedge and caption→wedge resolve with a
clear margin, so the join is made on the wedge. With that, 2Q26 extracts exactly:
CS & NDF 36%, proxy & open 60%, FVOCI 4%, FX risk exposure 74%, hedging cost
1.21%, reserve NT$130.9bn — matching the deck.

The 60% proxy-and-open share is not an error: the deck's own note says those
positions are mainly AC bond exposures, which is the 2026 AC FX accounting
treatment, and it is the same reclassification that took the sector ratio from
50.23% to 42.89%.

**Open.** Page selection still mis-fires on some vintages (it picks pages 34/37/38/41
in several 2024–26 decks, which carry the keywords in a different layout), the
reserve-for-FX-policy caption does not always match, and older decks use different
captions again. Cross-vintage layout handling is the remaining work before the
panel can be run over all 112 decks and the other five firms.

**Files.** `scripts/stage3_cathay_decks.py`, `config/cathay_decks.json`.

### 3.2 Statutory filings, not IR decks, are the target; legacy MOPS is usable

**Decision.** The firm panel should be built from statutory financial statements
rather than results decks. The decks stay as a cross-check and as the only source
for figures the statements do not state directly.

**Reason.** The deck gives the hedging split as rounded chart labels (36% / 60% /
4%) that have to be recovered from pie geometry — decisions 3.1 records the
wedge-binding needed to do that safely, which is effort spent on a presentation
artefact rather than on data. Statutory statements carry the underlying NT$
amounts on an audited, fixed-structure basis: derivative notionals by instrument
in the derivatives note, foreign-currency assets by currency under the IFRS 7
currency-risk disclosure, and 外匯價格變動準備金 as a balance-sheet liability
line. The gross hedge ratio can then be **computed** from audited inputs instead
of read off a rounded label, and the 2026 notice §10 disclosure is itself a
statutory requirement.

**Access, measured 2026-09-04.**

| Host | Status | Note |
|---|---|---|
| `mopsov.twse.com.tw` | **usable** | Plain HTML tables, accepts POST. `ajax_t164sb04` with `co_id=2823` returned a table (凱基人壽). |
| `mops.twse.com.tw` | JS shell | 800 bytes to plain HTTP. |
| `doc.twse.com.tw` | JS-gated | 800 bytes; this is where the statement files sit. Drivable with the pre-installed Chromium/Playwright. |
| `insdb.tii.org.tw` | login | Catalogue is premiums/contracts plus standard statements; no hedging detail. |

**Correction to the allowlist.** It recorded MOPS as "JS-rendered, rate-limited;
fallback only". That is true of `mops.twse.com.tw` and false of
`mopsov.twse.com.tw`, which is the one that works. The entry is corrected; the
dismissal had made the whole statutory route look closed when it is not.

**Open.** Land an actual statement for one insurer via Playwright against
`doc.twse.com.tw`, and check whether XBRL is exposed — XBRL would be structured
data and would remove the parsing problem entirely rather than merely improving
it. Then locate the derivatives and currency-risk notes and pin the line items.

**Files.** `config/allowlist.tsv`.

### 3.3 The MOPS statutory route reaches the statement index; the download is gated

**State.** The statutory filing route works end to end **up to the index of
statements**, and stops at the file download. Recorded here so the mechanics are
not re-derived: they are non-obvious and took several attempts.

**The working sequence.**

1. `POST https://mopsov.twse.com.tw/mops/web/ajax_t57sb01_q1` with
   `step=1, firstin=ture, off=1, TYPEK=all, queryName=co_id, inpuType=co_id,
   co_id=<code>, year=<ROC year>`. Note `firstin=ture` — the misspelling is
   MOPS's own, taken from the form on `t57sb01_q1`, and `true` does not work.
2. The reply is not the data. It is a 3 kB page saying results open in a popup,
   carrying the real target in an `onSubmit`/`run` attribute.
3. `GET https://doc.twse.com.tw/server-java/t57sb01?step=1&colorchg=1&co_id=<code>&year=<ROC>&seamon=&mtype=A`
   — a **GET**, with a `mopsov` Referer. `mtype=A` is 財務報告書, `F` is 年報.
   POSTing this returns an 800-byte block page, which is what made it look
   closed earlier.

That returns the index as a clean HTML table. For KGI Life (2823), ROC 113:

| Quarter | File | Size | Uploaded |
|---|---|---|---|
| Q1 | `202401_2823_AI2.pdf` | 5,087,773 | 113/05/15 |
| Q2 | `202402_2823_AI2.pdf` | 4,729,762 | 113/08/20 |
| Q3 | `202403_2823_AI2.pdf` | 2,135,353 | 113/11/13 |
| Q4 | `202404_2823_AI2.pdf` | 3,772,865 | 114/02/27 |

all typed `IFRSs個別財報`. So the document identifiers are recoverable
programmatically, which is most of what an ingester needs.

**Where it stops.** The download itself is gated: `step=9` by POST and by GET,
and the direct `/pdf/<name>` path, all return MOPS's security page (800 B,
"因為安全性考量") rather than the file. One earlier request also drew a 307 to
the same page, so there is rate limiting as well as a referer/session check.

**The browser is not the workaround here.** Playwright with the pre-installed
Chromium is now installed and launches, but `mopsov` and `doc.twse.com.tw` reset
its connections through the egress proxy (`ws_closed_mid_exchange`, repeatably,
across four attempts with unrelated hosts blocked) while plain `requests`
succeeds against the same endpoints. So decisions 3.2's suggestion to drive it
with Playwright is withdrawn: for these two hosts, `requests` is the working
client and the browser is the broken one.

**Next, in preference order.** (a) The insurers' own sites — every insurer must
publish its statements under 保險業資訊公開管理辦法, which avoids MOPS entirely.
`www.kgilife.com.tw` and `www.fubon.com` both answer; `www.cathaylife.com.tw`
errors at the proxy. The disclosure sections need locating per firm, by search
rather than by guessing paths, which is what failed here. (b) Work the MOPS
download gate. (c) Check whether XBRL is exposed anywhere, which would remove
the parsing problem rather than improve it.

**Files.** `config/allowlist.tsv`.

### 3.4 The right firm-level source is the Insurance Bureau's own portal, and it is unreachable here

**Finding.** The statutory route for firm data is neither MOPS nor the IR sites.
It is **保險業公開資訊觀測站** at `ins-info.ib.gov.tw` — the Insurance Bureau's
own centralised disclosure portal, the insurance-sector counterpart to MOPS,
carrying per-company pages (`customer/life.aspx?UID=…`, `Info2-2/2-3.aspx`) and
aggregate tables, among them 表06021011 財務報告彙總 and 表06161610
壽險財務業務指標. Every insurer's disclosure is published there under
人身保險業辦理資訊公開管理辦法.

**It cannot be reached from this environment.** The https tunnel closes
repeatedly at about 12 s (six consecutive attempts, `ws_closed_mid_exchange`
after 517 B); plain http returns 503 "upstream connect error … connection
timeout". This is not a policy denial, so it may be the site or the egress path.

**The same data exists as open data, and that is policy-blocked.**
`data.gov.tw` dataset 7191 is 壽險財務業務指標 published as structured open data,
which would remove scraping from this problem altogether. `data.gov.tw` answers
403 to CONNECT at the proxy. **These two are worth raising with whoever controls
the network policy: between them they are the clean solution to firm-level
data, and both are government sources.**

**What is reachable, and what a statement actually contains.** Cathay Life's own
host `www.cathaylife.com.tw` is 403-blocked, but its statutory statements are
also served from `www.cathayholdings.com`, which is not. One was fetched and
parsed: 127 pages, 108,691 characters of extractable text, with derivatives on
26 pages, hedging on 19, and the FX price-fluctuation reserve on 10.

That statement gives derivative **fair values** by instrument family
(遠期外匯、換匯、換匯換利 assets NT$3.42bn against liabilities NT$8.88bn at
101.6.30) — but its only 名目本金 disclosure covers **related-party** trades with
Cathay United Bank, not the total book. Fair value is not a hedge notional, so
that vintage alone cannot produce a hedge ratio. Whether current statements do
is the open question: IFRS 9 hedge-accounting disclosure and the 2026 notice §10
both require considerably more than this 2012-vintage statement carried, and
that must be checked against a current filing before the approach is judged.

Also reachable and publishing statutory material: `www.fubon.com` (a structured
財務概況 disclosure section), `www.nanshanlife.com.tw` (quarterly 財務概況 PDFs
from `portal-api/File/{id}`), `www.kgilife.com.tw`.

**Files.** `config/allowlist.tsv`.

### 3.5 README reviewed and corrected: sourcing hierarchy, entity codes, stage order

**Decision.** The README is a working document, not a fixed spec. Ten corrections
made, the substantive ones being a stated sourcing hierarchy and the firm filing
codes.

**1 — §4 now opens with a sourcing hierarchy** (open data → regulator's portal →
statutory filing → IR material → press), with the rule that tiers 4 and 5 are
presentation layers, that stopping short of the top tier must be recorded, and
that an unreachable higher-tier source is a finding to escalate rather than a
reason to silently drop a tier. Its absence is what let the project build series
4 off newspapers without anyone first checking 保險業公開資訊觀測站.

**2 — §4.5 had holding-company codes labelled as life companies.** It listed
"Cathay Life (2882), Fubon Life (2881), KGI Life (2883)"; those are the holdcos,
whose financials consolidate banking and securities. The insurers file separately:
Cathay Life 5846, Fubon Life 5865, Nan Shan 5874, KGI Life 2823 (2823 verified
against MOPS, the others taken from the companies' own filed documents). Querying
a filing system with the holdco code returns the wrong entity, silently.

**The rest.** §4.1 puts the Bureau's portal ahead of the press channel and states
that channel's two measured limits (udn purges at ~12 months; the ratio series
starts 2024-04). §4.5 puts statutory filings ahead of decks, corrects the MOPS
characterisation, and records that the one statement parsed gives fair values
rather than notionals. §7 inverts the Stage 2/3 order with the basis reason, and
withdraws the OCR budget for 2013–2019. §3 corrects series 1/2/4 start dates
(sector 2024-04, not 2020) and firm dates to 2011. §8 re-rates Stage 1 to Opus
and splits Stage 2, both having been rated on an assumption of mechanical work
that did not hold. §5 reconciles the allowlist block with measured reality, adds
the press hosts it never listed, and points at `config/allowlist.tsv` as the
operational source of truth. §9 corrects the MOPS pitfall and flags Cathay's Q1
2026 CS/NDF figure against the 1H26 reading of 36%. §10 corrects 90 editions to
91. §6 records `reporting_channel` in the natural key.

**Not changed.** §1, §2 and the interpretation notes other than the two above.
The Cathay Q1 2026 figure is flagged, not corrected: my own Q1 extraction was
unreliable and a 33pp move inside one quarter is possible given the AC
reclassification the deck dates to 1M26. Flagging an unverified tension is
correct; overwriting a sourced figure with a worse-sourced one is not.

**Files.** `README.md`.

### 3.6 The notional test, run on a current statement: the panel needs both documents per quarter

**Question.** Can statutory filings alone yield the firm hedge ratio (3.2's open
question), or are the decks' rounded labels the only firm-level source?

**Answer: neither alone — the panel is statement + deck per quarter.** Run on
Cathay Life's Q1 2026 consolidated report (201 pages, 249k chars of extractable
text, fetched from the cathayholdings quarterly-reports page, which lists **58
quarters of Cathay Life statements, each with PDF and Excel**).

**What the statement carries, at NT$-thousand precision:**

- **The denominator.** The significant-FX-exposure note (p.183) gives assets by
  currency: USD monetary NT$5,089,493mn, USD non-monetary NT$265,552mn, AUD
  NT$149,027mn at 115.3.31 — totalling ≈NT$5.5tn, consistent with the deck's
  rounded "FX asset NT$5.54TN".
- **The buffers.** The FX price-fluctuation reserve reconciliation (p.100):
  opening NT$113,806,568k, fixed and volatility provisions itemised, closing
  NT$123,945,812k — which **ties exactly to the deck's 1Q26 strip (123.9bn)**.
  Series 3 at firm level comes from here, not from chart labels.
- Hedge-accounting notionals for the *designated* sliver only: IRS ≈NT$26.4bn,
  FX forwards NT$44.4bn (p.161–163), with maturity buckets and contracted rates.

**What it does not carry.** The economic hedge book. CS/NDF (~NT$2tn implied by
the deck's 36% of NT$5.54tn) sits at FVTPL, and FVTPL derivatives are disclosed
at fair value, not notional. 避險比率 appears only as policy language (p.100)
and in the Y-reserve formula (p.116), never as a figure. Consistent with the
2012 vintage (3.4): across fourteen years and two accounting regimes, the
statements have never disclosed the total hedge notional.

**Design consequence for Stage 3.** Per firm-quarter: denominator and buffers
from the statement (precise, audited); ratio and composition from the deck
(stated but rounded); the reserve balance as the join check between them — it
ties exactly where tested. The `firm_quarterly` schema already tolerates this
split via its `basis`/missing-field design. The Excel companions to the
statements may make the primary-statement lines trivially parseable and should
be tried before any PDF table work.

**Files.** none yet (finding only; the extractor comes next).

### 3.7 Cathay deck run: 44 quarters extracted; FX assets and shares solid, costs provisional

**Decision.** `stage3_cathay_decks.py --csv` now runs all English decks and emits
`data/cathay_deck_fx.csv` through a validity layer, 44 rows, 2014-03 → 2026-08.
Fields are published at three confidence tiers rather than uniformly.

**Page selection, fixed.** Most decks carry two qualifying pages: the quarterly
body page (~p23–28) and a "Dynamic hedging strategy" appendix whose long-history
chart has **no numeric text layer** (only "FY" axis ticks and glyph-degraded
captions survive). The body page always precedes the appendix, so the selector
takes the *first* page naming the FX asset base beside an instrument caption;
keyword scoring, which preferred the appendix in four vintages, is gone. The
2013 decks and five others (2014×2, 2017-08, 2019×2) have no qualifying page and
are recorded as gaps, not failures.

**Field tiers.**

1. **Solid — regex-anchored text.** `fx_assets_ntd_tn`: all 44 rows, 1.66tn →
   5.54tn, a continuous 12-year quarterly denominator ("NT$…TN", "TR" in 2024).
   Also the 2026 narrative reserve figures and the labelled costs
   ("1H25 Hedging cost 1.45%") from 2024 on.
2. **Conditional — geometric, kept only when the pie closes.** The 74/26
   exposure-vs-FX-policy split (kept when the pair sums 95–105; ~24 rows, stable
   69–76 / 24–31 across a decade) and the full structure split (kept when the
   three shares close; 2026-08 only, after the 2024–25 vintages turned out to
   draw the structure values as vector graphics with no text). CS & NDF alone is
   kept when share-sized (30–85%): ~24 rows, 49% (2015) → 63–67% (2020–24) →
   36% (1H26).
3. **Provisional — do not publish downstream yet.** `hedging_cost_pct` outside
   the labelled/narrative rows: the loose regex can catch a delta or an
   unrelated ratio, and 0.14% (2023-03 deck, FY22) and 0.49% (2023-11) are
   almost certainly such captures. Cross-validation against the FY strips the
   2026-08 deck itself carries (FY23 0.96, FY24 1.56, 1H25 1.45, FY25 1.57) and
   against the Chinese decks is the follow-up.

**The two mis-binding lessons are recorded in the code:** captions wrap across
text blocks, so caption matching uses fragments; and the two pies' captions must
compete in a single pairing pass, otherwise the value-less structure captions
claim the exposure wedges.

**What this yields analytically, already:** Cathay's CS & NDF share halved
between FY24 (~63%) and 1H26 (36%) while the exposure/policy split barely moved
— the firm-level counterpart of the sector ratio's 66% → 43% fall, and the
denominator series to divide the statement-side buffers by.

**Files.** `scripts/stage3_cathay_decks.py`, `data/cathay_deck_fx.csv`.

### 2.2 CBC statistics-database API: monthly history to 1987, on the Chinese endpoint only

**Decision.** `scripts/stage2_cbc_history.py` ingests appendix table 8 from the
CBC Statistical Database's JSON API — `cpx.cbc.gov.tw/API/DataAPI/Get?FileName=
EF67M01` — giving the sector balance sheet **monthly from 1987-05**, 471 months,
thirty-seven years beyond the rolling CSV and seventeen beyond README §7's
"history to 2000" target. 6,960 rows, 1,316/1,316 checks, and **all 443 cells
overlapping the CSV channel agree exactly**.

**Use the Chinese item code; the English one is served through a broken
chunker.** Both endpoints exist (`EF67M01`, `EF67M01en`; the API is documented
in a PDF downloadable from the database's own page, POST `Tree/ExportToAPIInfo`).
The English payload chunks rows at 31 cells including the period marker, while a
period actually owns 31 data cells — so alignment drifts one period every 31
(measured: ~11 periods adrift by 2016, ~15 by 2024) and the stream ends ~15
months short of its labels; 2026 values are absent outright. The Chinese payload
is exact: 471 rows of `[YYYYMMM, (amount, annual growth)×15]` in the same line
order as the CSV. Do not use `…en` for anything.

**One line is null in the API from 2025-01**: 人壽保險與投資合約負債. The CSV
channel carries those months, and the loader inserts on the shared natural key
with the CSV rows taking precedence, so the table is complete.

**The series itself**: foreign assets NT$74mn at 1987-05, NT$121bn at 2000-12,
NT$21.9tn at 2026-07 — the sector's foreign book grew five orders of magnitude
in four decades, and the pre-2000 stub documents that the pre-liberalisation
base was effectively zero.

**Loading convention.** Bulk rows are loaded through the compact
labels/vals CTE form (one INSERT…SELECT per batch), not the emitted
per-row SQL, and a load is verified server-side afterwards — row count, total
checksum and spot values against the local CSV — because content relayed
through conversation calls cannot be assumed faithful without a check.

**Files.** `scripts/stage2_cbc_history.py`, `data/sector_balance_sheet_history.csv`,
`out/stage2b_cbc_api_*.sql`, `reports/stage2b_cbc_api_*.json`.
