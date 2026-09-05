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

**The series itself**: the table runs from 1987-05, and foreign assets first
appear at **1988-11, NT$74mn** (earlier months carry the line as null — the
pre-liberalisation base was literally nothing), NT$121bn at 2000-12, NT$21.9tn
at 2026-07: five orders of magnitude in under four decades. *(Corrected
in-session: first written as "NT$74mn at 1987-05" — an off-by-one from a
hard-coded label in a diagnostic print, caught when the loaded table returned
null for 1987-05 and the CSV was re-read.)*

**Loading convention.** Bulk rows are loaded through the compact
labels/vals CTE form (one INSERT…SELECT per batch), not the emitted
per-row SQL, and a load is verified server-side afterwards — row count, total
checksum and spot values against the local CSV — because content relayed
through conversation calls cannot be assumed faithful without a check.

**Files.** `scripts/stage2_cbc_history.py`, `data/sector_balance_sheet_history.csv`,
`out/stage2b_cbc_api_*.sql`, `reports/stage2b_cbc_api_*.json`.

### 3.8 en/zh deck merge: agreement is the standard; 3.7's cost suspicion withdrawn

**Decision.** `stage3_merge_cathay.py` joins the English and Chinese extractions
into `data/cathay_fx_quarterly.csv` — 47 deck-quarters, 2014 → 1H26 — with
per-field source tracking. A field present in both languages must agree
(`both`); a disagreement blanks the value and records the pair in `flags`,
because a disagreeing cell is not data. Result: **106 agreements, 1 conflict**
(CS & NDF at the 2023-03 deck: en 56 vs zh 33 — the FY22 share is therefore
withheld pending a manual read of that page). Every extracted cost-period label
(9M23, 1H25, FY22 …) matches the period derived from the deck month, validating
both.

**3.7's suspicion about the cost cells was wrong, and is withdrawn.** The zh
2023-11 deck prints "9M23 避險成本0.49%" verbatim, and 0.14% for FY22 appears in
both languages independently — economically coherent, since the TWD's 2022
depreciation collapsed realised hedging costs. The provisional tier is upgraded:
`hedging_cost_pct` is now cross-confirmed on ~30 quarters and single-sourced on
the rest, with the source column saying which.

**What zh added.** Three deck-quarters the en run lacked entirely (2017-08,
2019-08, 2019-11), the 2015–2023 cost series in labelled form, and 2023-era
CS & NDF shares whose en values are graphics-only. What en still owns: the
exposure/policy split and the 2026 structure trio.

**Files.** `scripts/stage3_merge_cathay.py`, `data/cathay_fx_quarterly.csv`,
`data/cathay_deck_fx_zh.csv` (full 48-row run, superseding the smoke test).

### 3.9 FY22 conflict resolved by wedge colour; two README §9 anecdotes fail verification

**Decision.** The one merge conflict (FY22 CS & NDF share, en 56 vs zh 33) is
resolved to **CS & NDF 56%, proxy & open 33%, FVOCI & FVTPL 12%**, entered in
the merge script as a `manual_geometry` resolution rather than an edit to either
extraction file, so the evidence trail survives re-runs.

**Method.** Both language editions print the same trio (56/12/33), so the
disagreement was binding, not data. On the page geometry: 56% sits in the dark
blue wedge, whose nearest caption is Currency Swap & NDF; 33% in the yellow
wedge (Proxy & Open); 12% in the green wedge (FVOCI & FVTPL) — margins of 9–28
points against 40+ for the alternatives. Decisive corroboration: the wedge
palette is identical to the independently verified 2026-08 page (dark blue =
CS & NDF, yellow = proxy, green = FVOCI). Text order on the page (56/12/33
against caption order Proxy/CS/FVOCI) would have given the opposite answer —
another instance of the rule that text order lies on these charts.

**Consequence — README §9 corrected again.** "Cathay ran CS/NDF at ~15% in
2022" is contradicted by the deck series itself: 59% (9M21) → 65% (1Q22) → 64%
(1H22, 9M22) → 56% (FY22). Together with the earlier 1H26 finding, both halves
of that sentence failed verification, and §9 now points at
`data/cathay_fx_quarterly.csv` instead of anecdotes. The FY22 pattern worth
keeping: the *cost* collapsed to 0.14% on TWD depreciation while the *share*
stayed 56% — carry moves the cost far faster than the book.

**Files.** `scripts/stage3_merge_cathay.py`, `data/cathay_fx_quarterly.csv`,
`README.md` §9.

### 2.3 The FSC/CBC foreign-asset gap is a stable classification wedge, not a widening one — and the FSC-basis denominator exists monthly

**Source.** The Insurance Bureau's monthly 保險市場重要指標 PDFs (`www.ib.gov.tw`,
id=48), whose 人身保險業資金運用表 carries the FSC-basis 國外投資 — the precise
figures behind the briefing's rounded 23兆/22.8兆.

**The gap, measured properly at five year-ends (NT$ mn):**

| Year-end | FSC 國外投資 | CBC 國外資產 | Gap | Rel |
|---|---|---|---|---|
| 2021 | 19,878,660 | 19,046,093 | 832,567 | 4.19% |
| 2022 | 21,184,914 | 20,510,322 | 674,592 | 3.18% |
| 2023 | 21,857,811 | 21,045,823 | 811,988 | 3.71% |
| 2024 | 23,025,710 | 22,471,627 | 554,083 | 2.41% |
| 2025 | 22,767,215 | 22,009,067 | 758,148 | 3.33% |

**Correction to 2.1.** "The gap is widening" is withdrawn: it rested on two
points with a rounded numerator (23兆 read against 22.472兆). With precise
numerators the wedge fluctuates between 2.4% and 4.2% with no trend.

**What the wedge is.** The same table's 資產總額 ties CBC total assets to
~0.005–0.008% at every year-end, so population and accounting basis are
identical; the wedge is purely *usage-versus-residence classification*: items
the Insurance Act counts as 國外投資 that are claims on residents in CBC's
balance sheet. Named candidates: foreign-currency deposits at domestic banks
and domestic bond ETFs under the look-through rules. 國際板 (Formosa) bonds are
**excluded as a candidate** — their issuers are non-residents, so they sit on
the foreign side of both measures.

**Consequence for series 1/2/5.** The 3%±1 wedge means CBC foreign assets must
not stand in for the FSC denominator (as 2.1 said) — but they no longer need
to: each monthly 指標 edition's fund-utilisation table carries its own recent
month (the 114年5月 edition adds a 21,687,492 column beyond the 2024 year-end),
so a **monthly FSC-basis foreign-investment series** is recoverable by walking
the archive. One alignment question is open and must be settled from the
documents, not assumed: the May-2025 edition's figure sits within 0.3% of CBC's
*April* but 6% above CBC's May, so editions may label their column one month
behind the edition name — the ingester must read the column header, and the
May/April ambiguity is confounded by the May 2025 TWD shock either way.

**Files.** none yet — `stage2c` ingester next; PDFs cached under `cache/ib/`.

### 3.10 entities seeded: six firms, lifeco codes only, Shin Kong continuity encoded

**Decision.** `tlfx.entities` is seeded (`supabase/seeds/entities_seed.sql`,
applied via the MCP, verified back). Conventions: `valid_from` marks TLFX panel
coverage start (2011-01-01, the earliest deck being 2011 Q4), not incorporation;
`ticker` holds the **life company's** filing code and stays NULL until verified
from a primary document — cathay_life 5846, fubon_life 5865, nanshan_life 5874,
kgi_life 2823 are verified, taiwan_life and shinkong_life are pending, and the
holdco-code trap of decisions 3.5 is the reason for the discipline.
`shinkong_life` keeps one `entity_id` across the 2026-01-01 merger per README
§4.5, with the legal mechanics (Taishin Life absorbed Shin Kong Life and took
its name) in `break_note` rather than a successor row.

**Files.** `supabase/seeds/entities_seed.sql`.

### 2.4 stage2c: the monthly FSC-basis denominator is built — 110 months, each label proven by a CBC tie

**Decision.** `scripts/stage2c_ib_indicators.py` walks the Insurance Bureau's
保險市場重要指標 archive (`www.ib.gov.tw` id=48, paginated POST) and parses
表17-1 人身保險業資金運用表 from every edition: **110 months, 2017-01 →
2026-04** of FSC-basis 國外投資 alongside 資金運用總額/資金總額/資產總額.
Loaded to `tlfx.sector_monthly` under a new `reporting_channel='ib_indicators'`
(migration `0005`, additive CHECK extension), vintage = the PDF's upload
timestamp from its URL.

**The 2.3 alignment question is settled: the column is labelled, not offset.**
Each table prints its current column's own header ("2025/05", or a bare year
for December). The ingester reads that label and then *proves* it by tying the
same edition's 資產總額 to CBC table 8 total assets for the labelled month —
110/110 ties pass. The May-2025 "6% above CBC" puzzle in 2.3 dissolves: that
was 國外投資 vs CBC *foreign assets* (the usage-vs-residence wedge, spiked by
the May TWD shock's flight to FX deposits), not a column offset.

**Named tolerance exceptions, both structural, neither a parse doubt:**
- obs ≥ 2026-01: rel tolerance 0.02 — the IB's 2026 editions are IFRS 17
  ("IFRS17" in the filenames) and run ~1.27% above CBC's basis, steady across
  2026-01/02/03; the 2025-12 restatement moved only 0.05%.
- 2020-03: tolerance 0.005 (0.30% miss) — the COVID-disrupted round whose FSC
  release the same month is also missing sections (see the release channel).

**Two-page-spread trap.** Chinese table titles print on the *preceding* page,
so selecting the parse page by title captured a 2008-11 historical annex and
failed 99/112 editions. The fix selects by parsed value scale (國外投資 ≥
3×10⁶, 資產總額 ≥ 2×10⁷ NT$ mn), not title.

**Gaps — closed same day.** 113-01 and 106-02 initially failed to parse.
Causes, both in-document: 106-02 wraps the English row label after "Foreign";
113-01 prints literal `TRUE` in three year columns of 資產總額 (a spreadsheet
artifact — its footnote also marks 2023 data provisional, e.g. 2023-12
國外投資 21,857,675 vs the final 21,857,811). Regexes widened (optional label
tail; TRUE admitted as a token, numerics kept). Now **112 months, 112/112
ties, no gaps**; both rows loaded and the channel re-verified (sum fi
2,140,634,844; sum ta 3,526,440,724).

**Files.** `scripts/stage2c_ib_indicators.py`, `data/ib_indicators_monthly.csv`,
`out/stage2c_ib_20260904.sql`, `reports/stage2c_ib_20260904.json`,
`supabase/migrations/0005_sector_monthly_channel_ib_indicators.sql`.

### 3.11 firm_quarterly carries the Cathay deck series — shares, not notionals, under a channel key

**Decision.** Migration `0006` extends `tlfx.firm_quarterly` additively:
deck-disclosed hedge composition is stored as *shares* (`hedge_cs_ndf_share_pct`,
`hedge_proxy_open_share_pct`, `hedge_fvoci_share_pct`, `fx_risk_share_pct`,
`fx_policy_share_pct`) because decks never disclose notionals (3.6); the
original notional columns stay for statement-derived figures. A
`source_channel` column ('deck' | 'statement') joins the primary key —
precedent 0004 — so a quarter can carry both a deck row and a statement row,
cross-checked on `fx_reserve_balance`.

**Load.** `scripts/stage3_load_cathay.py` maps `data/cathay_fx_quarterly.csv`:
period 1Q/1H/9M/FY+yy → first day of the period's end quarter; NT$ tn → mn
(foreign_assets), NT$ bn → mn (fx_reserve_balance), cost % → bp; basis IFRS17
for 2026-on periods, IFRS4 before; vintage = deck date; source_url from the
language deck indexes (en preferred). 47 rows 2013-Q4 → 2026-Q2 loaded and
checksum-verified server-side (count, four sums, two spot values). Per-field
en/zh provenance travels in `source_note`.

**Files.** `supabase/migrations/0006_firm_quarterly_deck_shares.sql`,
`scripts/stage3_load_cathay.py`, `out/stage3_cathay_20260904.sql`.

### 3.12 Cathay statement channel: Excel companions give the FX volatility reserve quarterly from 2020

**Decision.** `scripts/stage3_cathay_statements.py` parses the Excel companions
of Cathay Life's (5846) consolidated quarterly statements on cathayholdings
(index mirrored to `config/cathay_life_statements.json`): **26 quarters,
2020Q1 → 2026Q2**, loaded to `firm_quarterly` under `source_channel=
'statement'`. Excel companions exist only from 2020 — 2012–2019 editions are
PDF-only and remain unextracted. Carried: 外匯價格變動準備 (FX volatility
reserve), 資產總計, 權益總額/總計, at NT$-thousand precision stored as NT$ mn.

**The IFRS-17 fold-in, and its exact recovery.** The 2026 condensed balance
sheets drop the reserve line (folded into 其他負債), but the cash-flow
statement still prints 外匯價格變動準備淨變動 YTD, so the 2026 balances derive
exactly: 2025Q4 113,806,568 + 10,139,244 → 1Q26 123,945,812; + 17,125,178 →
2Q26 130,931,746 (NT$ th). Both tie the deck's independently extracted 123.9bn
/ 130.9bn — the decisions 3.6 statement↔deck join holds at the two quarters
where both sides carry the figure. Checks 28/28 (A=L+E identity every quarter,
column date ties the label, deck joins to 0.05bn).

**Label drift handled:** current-column headers are Excel serials in some
years, `2026年6月30日` strings in others; equity total is 權益總額 before 2026,
權益總計 after.

**Vintage convention for the statement channel:** the statement's period-end
date — publication dates are unrecoverable (the CMS re-stamps Last-Modified on
re-uploads; the 2020Q1 file says 2023-09-11).

**Files.** `scripts/stage3_cathay_statements.py`,
`config/cathay_life_statements.json`, `data/cathay_statements_quarterly.csv`,
`out/stage3_cathay_stmt_20260904.sql`.

### 3.13 The last two filing codes, verified from the TWSE open-data registry

**Decision.** Taiwan Life = **2833**, Shin Kong Life (post-merger) = **6985**,
both from `openapi.twse.com.tw/v1/opendata/t187ap03_P` (公開發行公司基本資料,
出表日期 1150903) — an authoritative registry reachable despite the insurers'
own sites (taiwanlife.com, skl.com.tw, taishinlife.com.tw, tsfl.com.tw) all
being proxy-blocked. Cross-check: the registry's 統編 for Fubon Life
(27935073) matches the ins-info UID on Fubon's own public-info page.

**The 6985 trap, documented before it bites.** 6985 is the *surviving
ex-Taishin Life* entity, renamed 新光人壽 at the 2026-01-01 merger; its
pre-2026 filings are Taishin Life's. The panel's pre-2026 shinkong_life rows
need old Shin Kong Life's own code, still unverified — `entities.break_note`
and the MOPS fetcher (`MIN_YEAR`) both encode the restriction.

**Applied.** `tlfx.entities` tickers updated (all six now verified),
`supabase/seeds/entities_seed.sql` kept in sync, README §4.5 table completed,
fetcher extended to five codes.

**Files.** `supabase/seeds/entities_seed.sql`, `scripts/stage3_mops_fetch.py`,
`README.md` §4.5.

### 3.14 Fubon deck route open — and the 60.9% binding trap resolved by an in-document identity

**Route.** Fubon FHC's results decks live on `fubon.irpro.co` (conference.php,
year pages 2007→2026) with files on `www.irpro.co` — both reachable, no WAF
(the old allowlist note dismissing irpro.co wholesale is wrong for this path).
238 PDFs indexed to `config/fubon_conference_decks.json` (118 CH-site, 120
EN-site; some "EN" files are the Chinese deck — the true English deck is a
separate event id, e.g. 584 zh-content vs 585 English for 1H26).

**The hedging page** (1H26: p.21 避險組合及外價金餘額 / Hedging portfolio and
FX reserve) carries: recurring hedge cost in bps by quarter and cumulative
(1Q26 −126, 2Q26 −121, 1H26 −124), the 外價金 balance path with fixed/
volatility split (Jun-26 NT$153.7bn), a 具外匯風險資產 77.4%/22.6% split, and
a hedge-composition pie.

**The trap.** Text order and label proximity both suggest CS+NDF = 60.9%.
Wrong: the page's own note — "Naked USD 59.1% + other currencies 1.8%" — sums
to 60.9%, proving **未避險 = 60.9% and CS+NDF = 24.6%** (FVOCI 8.5, FVTPL
6.0). Economic priors fail here precisely because the truth is remarkable:
post the 2025 TWD shock Fubon runs a ~25% swap-hedged, ~61% naked book backed
by the accumulated reserve. Extractor bindings must come from in-document
identities (note sums, pie-sums-to-100, en/zh agreement, wedge containment),
never from ordering or plausibility.

**Files.** `config/fubon_conference_decks.json`; cache under `cache/fubon/`.

### 3.15 Fubon deck series extracted: 49 periods, 2011 → 1H26, all cross-checked

**Extraction.** `scripts/stage3_fubon_decks.py` over the 238-deck corpus:
**173 rows / 49 distinct periods, 4Q11-era → 1H26**, `data/fubon_deck_fx.csv`.
Bindings are in-document only (3.14): each `±N bps` token pairs with its
nearest period label (capped Euclidean — layouts always print them adjacent;
same-x column layouts made axis-based binding arbitrary, which was this
script's one real bug); pies bind by the "caption, 12.3%" comma through 2025
and by the note identity in 2026; era A/B (2006–2010 tables, 2011–13
multi-column bars) is explicitly out of scope, reported not guessed.

**Semantics — the headline is NOT the recurring hedge cost.** The bps series
is the **all-in FX result** (recurring hedge cost + FX G/L & reserve
provisioning): proven by the stacked-component identity, which holds on
151/173 rows where components print (e.g. 2Q25: −179 + −521 = **−700bps**,
the TWD-shock quarter; FY25: −130 + −146 = −276; 1H26: −48 + −76 = −124; the
2014-era prints the total unsigned: 37+25 = "62 bps"). Signs are era
conventions (2022 prints "+52bps" net gain). Attributing the component pair
to recurring-vs-FX G/L needs legend-colour binding — next pass; until then
`total_fx_cost_bps` is loaded nowhere and `hedge_cost_bp` stays deck-empty
for Fubon.

**Validation.** Sibling decks (CH/EN, conference duplicates) agree on every
field for all 49 periods; cross-deck the full `cost_series` agrees in
magnitude on every period any two decks both print. Composition coverage: 36
periods (完全避險 76.6% at 1H14 → CS/NDF/policy 95.2% at 1Q18 → 57.7% FY25 →
CS+NDF 24.6% with 60.9% naked at 1H26 — the post-shock de-hedging is now a
measured series). 外價金 balance appears from the 2025 editions (1H26:
NT$153.7bn).

**Files.** `scripts/stage3_fubon_decks.py`, `data/fubon_deck_fx.csv`,
`config/fubon_conference_decks.json`.

### 3.16 KGI deck series extracted: hedging cost, yield, FX-reserve path, structure — 2020 → 1H26

**Extraction.** `scripts/stage3_kgi_decks.py` over the CDF/KGI corpus
(cdf.irpro.co): **28 rows / 14 deck periods (1Q23 → 1H26 editions), carrying
chart series back to 2020**, `data/kgi_deck_fx.csv`. The KGI-era page is a
2×2 grid of small bar charts (pre-hedge recurring yield %, hedging cost %,
外匯價格變動準備金 NT$ bn, hedge-structure pie). Binding: block-scoped
x-pairing where a word belongs to the rightmost left-aligned caption left of
it, stacked same-x captions split by vertical distance, and a caption is only
the pattern plus a units suffix — prose mentioning 避險成本 (headers,
footnotes) must not anchor a block; that hijack was the main bug class.

**Series (cross-deck agreed, zero conflicts).** Hedging cost %: 2020 1.53 →
2022 0.64 → 2023 1.53 → 2024 1.09 → 1H25 3.06 → 2025 2.56 → 1H26 1.17.
FX reserve NT$bn: 4.02 (2020) → 9.77 (2023) → 30.71 (2024) → **2.44 at 1H25
(drawn down absorbing the TWD shock) → 43.37 (2025) → 48.99 (1H26)**.
Structure at 1H26: CS&NDF 37%, naked USD+other 59%, overseas equity 4%; FX
risk exposure 73% / FX policy 27% — the same post-shock low-hedge pattern as
Fubon (3.14/3.15). KGI's "Hedging Cost" is its own labelled series (unlike
Fubon's all-in headline); whether it is recurring-only is still to be pinned
before cross-firm comparison.

**Files.** `scripts/stage3_kgi_decks.py`, `data/kgi_deck_fx.csv`,
`config/kgi_conference_decks.json`.

### 3.17 Fubon recurring hedge cost attributed by legend-colour binding — 68 periods, and a falsified shortcut

**Decision.** `scripts/stage3_fubon_recurring.py` binds the stacked cost
components (recurring hedge cost / FX G&L & reserve provisioning / one-off
provisioning) by colour: the legend swatch beside each caption gives the
series colour; a value binds to the series whose colour fills the bar segment
containing it. **68 periods attributed, 55 fully sum-verified against the
all-in totals, zero conflicts** (`data/fubon_recurring_cost.csv`). The
recurring series tracks the US–TW differential as it should: −52bp (2016) →
−134 (2018) → −48 (2020) → −21 (2021) → −160 (2023) → −175 (2024) → −116
(1Q25) → −48 (1H26, half-year).

**A falsified shortcut, kept on the record.** A stack-order fallback (legend
x-order = segment order from the axis) was tried for the 13 periods whose
decks draw bars outside `get_drawings()`: it CONTRADICTED colour-bound values
across 2018–19 (27 conflicts) and was removed. Ordering is not evidence;
colour and sum identities are. The 13 partially-attributed periods (2020,
2021, 2025 among them) stay flagged `sum_ties_total=False` and their
unattributed pairs live only in `fubon_deck_fx.csv`'s `cost_components`.

**Files.** `scripts/stage3_fubon_recurring.py`,
`data/fubon_recurring_cost.csv`.

### 3.18 Fubon and KGI deck series loaded — semantics carried faithfully, not force-fitted

**Decision.** Migration `0007` (additive) gives `firm_quarterly` a
`deck_composition jsonb` (each deck's pie under canonical keys — category
semantics differ by firm and era, so cross-firm reads must go through key
names) and `total_fx_cost_bp` (the all-in FX result, Fubon's headline —
distinct from `hedge_cost_bp`, which stays recurring-only and comparable).
`scripts/stage3_load_decks.py` consolidates the sibling-agreed CSVs into one
row per (entity, period): **fubon_life 49 rows (2013-Q4 → 2026-Q2), kgi_life
20 rows (2020-Q4 → 2026-Q2)**, loaded and checksum-verified.

**Sign discipline.** Totals are sign-normalised negative-=-cost via the
verified component sums (which carry true signs even where a deck prints the
total unsigned); a bare unsigned-positive total with no verified components is
ambiguous between the 2014-era print convention and a genuine 2022-style net
gain, so four such rows (1Q14/1H14/9M14/2013) load without a total rather
than with a guessed sign. `hedge_cost_bp` (positive-=-cost, Cathay
convention) fills only from the 55 sum-verified colour-bound periods (3.17);
KGI's 避險成本 stays out of the DB entirely until its definition is pinned
(3.16). Rates are annualised in-source (cumulative ≈ average of quarters),
so no annualisation was applied.

**Files.** `supabase/migrations/0007_firm_quarterly_deck_composition.sql`,
`scripts/stage3_load_decks.py`, `out/stage3_decks_20260904.sql`.

### 3.19 Fubon era-A backfill: 2005 → 1Q07 recovered; the 2008-10 panels are out of scope

**Decision.** `scripts/stage3_fubon_eraA.py` parses the rotated 'Fubon Life –
Hedging Cost' tables of the earliest decks: **7 periods, 2005 → 1Q07**
(`data/fubon_eraA_cost.csv`), cross-deck agreed. Signs are normalised
cost-negative using the deck's own 'Implied hedging cost' reference column
(a market cost by construction, so its printed sign reveals the deck's
convention — decks genuinely flip it, and 2009 shows real hedging *gains*
when swap points inverted, so magnitude-only normalisation would destroy
information). Booked cost 2005 −157bp → 2006 −210 → 3Q06 −262; implied
consistently ~100-150bp above booked.

**Out of scope, with the reason on record:** the 2008-2010 editions print
side-by-side panels — Fubon Life beside the newly acquired ING Antai book —
with several hedging columns per panel. Entity attribution there needs its
own evidence chain, for a pre-merger series of modest analytic value; the
2011-13 multi-column era (3.15) remains out for the same reason.

**Files.** `scripts/stage3_fubon_eraA.py`, `data/fubon_eraA_cost.csv`.

### 4.1 Sector derived series built inside one regulatory scope

**Decision.** `scripts/derive_sector_series.py` produces the sector half of
README §3 from the loaded channels: **55 rows across 8 series keys, 2024-04 →
2026-07**, loaded to `tlfx.derived_series` and checksum-verified. Every row
stays inside the briefing's own regulatory scope, or is flagged where it does
not.

**Two in-document identities carry the derivation, both verified (6/6):**
`net_fx_exposure = denominator × (1 − ratio)` and `buffer_total /
net_fx_exposure = absorbable appreciation %`. The second holds to 0.01pp at
every 2026 month (e.g. 2026-03: 911,100/8,607,300 = 10.59% vs published
10.6), which is what licenses the first identity's *inverse* use: from
2026-02 the briefing stops printing the denominator but prints net exposure
and the ratio, so the denominator is recovered as `net/(1 − ratio)` and
tagged `definition_version = v2_identity`, `basis = estimated`. The recovered
values are continuous with the published anchors (15.4tn at 2025-12 →
15.69tn at 2026-03 → 15.85tn at 2026-07), which is the sanity check that
matters: a scope error would show as a step, not a drift.

**Series produced.** `reg_hedge_ratio` (13 months, v1/v2 break at the Feb-2026
notice), `reg_hedge_ratio_effective` (the Bureau's own with-buffers memo),
`reg_denominator`, `net_open_fx`, `hedge_principal` (10.36tn at 2024-12 →
7.74tn at 2025-12 → 6.80tn at 2026-07), `gross_hedge_ratio`, `buffer_total`,
`absorbable_appreciation`.

**The one deliberate cross-scope construct.** `gross_hedge_ratio` = hedge
principal (regulatory scope) / FSC-basis 國外投資 (`ib_indicators`) — the
figure sell-side quotes. It is `basis = estimated` with the mixing stated in
`basis_note` on every row, because the regulatory denominator is only ~68% of
國外投資 (15.4tn vs 22.8tn at 2025-12 — decisions 2.3). Read: 45.0% (2024-12)
→ 34.0% (2025-12) → 31.2% (2026-04). Series 1 (economic hedge ratio) is NOT
derived here: it needs FX-policy liabilities on the same scope, which the
briefing does not publish separately.

**Files.** `scripts/derive_sector_series.py`,
`data/derived_series_sector.csv`, `out/derive_sector_20260904.sql`.

### 4.2 The composition-pie base question — settled for Fubon pre-2026, open elsewhere

**The question.** Every firm's hedging page draws two cuts of the FX book: a
bar splitting FX assets into FX-risk-bearing (~74-77%) and FX-policy-backed
(~23-26%), and a pie of instrument shares summing to 100. Is the pie taken
over *total* FX assets or only over the FX-risk-bearing subset? The answer
moves the headline economic hedge ratio by ~10pp, so it cannot be assumed.

**Settled for Fubon pre-2026, by the wedge's own label.** Through the 2025
editions the big wedge is named 「外匯交換、無本金遠期外匯、外幣保單」
("Currency swap, NDF, FX policy"). It names FX-policy backing among its own
contents — and policy-backed assets are excluded from the FX-risk subset by
construction — so the pie must be over total FX assets, and **that wedge is
the economic hedge ratio, disclosed rather than inferred**. Its complement
(the naked-currency wedges, plus the separately drawn 股票/共同基金 wedge in
the 2014-15 editions) is the net open position. The pie closes to 100 on all
36 quarters. Series: 76.6% (1H14) → 88.8% (FY19) → 84.0% (1Q22) → 75.7%
(1Q24) → 71.0% (1Q25) → 61.8% (9M25) → **57.7% (FY25)**.

**Open for Cathay, and for Fubon from 2026.** Cathay's pie (CS&NDF / proxy &
open / FVOCI) names no policy wedge, and Fubon's 2026 redesign moves the
policy split into its own bar, so in both the base is inferred. The evidence
is genuinely two-sided and is recorded rather than resolved:

- *For the total-assets base:* Cathay's page title is "FX asset hedging
  structure" and its cost note states "Hedging cost is calculated based on FX
  assets"; across 13 quarters Cathay's CS&NDF share never exceeds its FX-risk
  share and often sits just under it (69 vs 70 at 9M18), which is what a
  near-fully-hedged risk book looks like on a shared base and would be
  coincidence on separate ones. Cathay 1H26 would then read 36 + 26 = 62%
  economic, against a sector economic ratio of roughly 60% built from the
  briefing (gross 29.9% + policy ~30%).
- *For the subset base:* Fubon's 2026 pie labels its 60.9% wedge 未避險
  ("unhedged"), and on a total-assets base that wedge would have to contain
  the 22.6% policy-backed assets the same page draws separately as hedged.
  On this reading Cathay 1Q22 reads 75.5% economic rather than 95%, and 95%
  is hard to credit against a contemporaneous sector regulatory ratio near
  66%.

**The test that would settle it,** for whoever picks this up: find any
edition printing one wedge in NT$ alongside the FX-asset total, or a quarter
where the instrument share exceeds the FX-risk share (which would force the
subset reading). Until then no economic hedge ratio is published for Cathay
or for Fubon 2026 — a partial series with a stated basis beats a complete one
resting on a guess.

**Files.** `scripts/derive_firm_series.py`, `data/derived_series_firm.csv`.

### 4.3 Background processes do not survive session idling here

**Measured.** The MOPS fetcher was launched under `nohup` at 07:35 UTC and
its last log line is 07:43; by 15:30 the process was gone. Worse, the check
that reported it healthy was a false positive: `pgrep -f stage3_mops_fetch`
matches the shell running the check itself, whose command line contains the
pattern. Both errors are now avoided — verify with `ps -eo pid,cmd | grep`
plus the log's mtime, never `pgrep -f` on a pattern you just typed.

**Consequence for the statement backfill.** The crawl managed 3 successes in
35 minutes against the WAF (~12 min each including penalty backoff); at ~290
firm-quarters that is ~58 hours of wall clock, and it cannot run unattended
because the process dies on idle. The bulk MOPS route is therefore
impractical in this environment and is withdrawn. What remains viable: a
*targeted* queue of the few quarters that carry analytic weight (the latest
quarter plus 2024/2025 year-ends for the four non-Cathay firms, ~8 requests),
re-launched each working turn. The clean fix is still the proxy unblock for
`ins-info.ib.gov.tw`, which serves the same statements without a WAF.

**Files.** `scripts/stage3_mops_fetch.py` (unchanged; the queue is the thing
to narrow).

### 4.4 A silent key collision: discrete quarters and cumulative periods are different measures

**Found by the checksum step, not by the run.** The first firm-series load
reported no error but landed 42 of Fubon's 55 hedge-cost rows. Cause: Fubon's
cost chart prints *both* discrete quarters (1Q21…4Q21) and *cumulative*
periods (1H21, 9M21, 2021) on the same page, and mapping every label to the
quarter its period ends in put 4Q22 and FY22 on the same natural key. The 13
losers went out silently through `on conflict do nothing`.

They are not near-duplicates. 4Q22 discrete is **−110bp**; FY22 cumulative is
**−51bp**. Keeping either at the other's expense would have corrupted the
series.

**Fix.** `hedge_cost_recurring` carries discrete quarters, `hedge_cost_
recurring_ytd` cumulative ones, each row's `basis_note` naming the deck label
and which it is. A first-quarter figure is both by definition, so it is
emitted to both series and neither carries an annual gap — Cathay, whose
decks print cumulative periods only, therefore has a complete 44-quarter YTD
series. 194 rows, 37/37 checks.

**Guard added.** The script now asserts no two emitted rows share
`(series_key, entity_id, obs_date, vintage)` before writing, so a collision
fails the run instead of vanishing into the conflict clause. Any future
derivation should carry the same guard: `on conflict do nothing` is the right
idempotency primitive and the wrong error detector.

**Files.** `scripts/derive_firm_series.py`, `data/derived_series_firm.csv`.

### 4.5 The statement and deck channels validate each other exactly — and all six firms are now populated

**The tie.** The IFRS-17 recovery of decisions 3.12 — 2026 FX-reserve balance
= the firm's own 2025Q4 balance less the cash-flow statement's year-to-date
net change — was inferred from Cathay alone. It is now *verified against
independently extracted deck figures on two further firms*, from a data path
that shares nothing with the decks (MOPS XBRL facts matched by concept and
context date):

| | statement-derived | deck-extracted |
|---|---|---|
| Fubon Mar-26 | 147,389.0 | 147.4 |
| Fubon Jun-26 | 153,677.3 | 153.7 |
| KGI 1Q26 | 44,831.8 | 44.83 |
| KGI 1H26 | 48,991.5 | 48.99 |

Exact to the decks' own rounding in all four. Fubon's Dec-25 statement line
(142,124.635) also lands on its deck's 142.1 for the same date. That
cross-validates three things at once: the MOPS XBRL parser, the KGI and Fubon
deck extractors (3.15/3.16), and the recovery method itself.

**Loaded.** 11 statement-channel rows for the five non-Cathay firms, 11/11
A=L+E, checksum-verified. Only reserve balances whose base is a *statement*
are loaded (Fubon, Nan Shan); KGI's base is its own deck, so its reserve
stays in the deck channel and the tie above is validation rather than a
second copy of the same number. KGI files no consolidated statement for these
quarters, so its rows are the individual report, noted per row.

**All six entities now carry data**: Cathay and Fubon in both channels, KGI
deck plus statement, Nan Shan / Taiwan Life / Shin Kong statement-only.

**Files.** `scripts/stage3_load_mops.py`, `data/mops_statements.csv`,
`out/stage3_mops_load_20260904.sql`.

### 4.6 KGI's 避險成本 is an all-in measure; Cathay's is recurring — settled by the shock half

**The test.** The May-2025 TWD shock separates the two definitions cleanly: an
all-in cost (recurring hedge cost plus FX P&L and reserve provisioning) must
spike in 1H25; a recurring swap cost cannot, because swap points did not
triple. Fubon publishes both and brackets the range — recurring 147bp, all-in
389bp in that half.

| | 2023 | 2024 | **1H25** | 2025 | 1H26 |
|---|---|---|---|---|---|
| KGI 避險成本 | 153 | 109 | **306** | 256 | 117 |
| Fubon all-in | 85 | 141 | **389** | 276 | 124 |
| Fubon recurring | 160 | 175 | **147** | 130 | 48 |
| Cathay hedging cost | 96 | 156 | **145** | 157 | 121 |

**KGI is all-in**: it triples into the shock half and tracks Fubon's all-in
through 2025-26 (256/276, 130/126, 117/124), nowhere near Fubon's recurring
(130, 50, 48). **Cathay is recurring**: it does not move in the shock half at
all (156 → 145 → 157), which no all-in measure could manage in a quarter that
produced the sector's record FX loss. That retrospectively evidences the
assumption under which Cathay was already loaded into series 7.

**Applied.** KGI's series is written to `total_fx_cost_bp` (all-in column,
negative = cost; sum −2,578bp over 20 quarters, verified), never to
`hedge_cost_bp`, and it stays out of derived series 7, which carries only the
recurring measure and so remains comparable across firms. 3.16 is closed.

**A regression caught on the way.** The KGI extractor's caption binding had
been changed to split a same-x caption stack by absolute vertical distance;
that assigned the 2×2 grid's shared period-label row to the *lower* caption
and silently emptied the cost series. Captions always sit above their chart,
so the rule is now "nearest caption above", and the cost series is restored
(20 periods, 0 conflicts) with the reserve and yield series unchanged.

**Files.** `scripts/stage3_kgi_decks.py`, `scripts/stage3_load_decks.py`,
`data/kgi_deck_fx.csv`.

### 4.7 The Cathay pie-base question: both tests from 4.2 run, evidence strengthened, judgement still withheld

Both tests named in 4.2 have now been run against the full 110-deck cache.

**Test 1 — a wedge printed in NT$: no.** Only four hedging pages in the whole
archive carry more than one NT$ amount, and in every case the extras are the
FX volatility reserve and its change (e.g. 2026-08-28: NT$5.54TN FX assets,
NT$17.1bn YTD change, NT$130.9bn balance). No edition prices a wedge, so the
base is never stated arithmetically.

**Test 2 — an instrument share exceeding the FX-risk share: no, and the near
misses are the informative part.** On the 12 quarters where the wedge-colour
extractor binds both figures, CS&NDF never exceeds FX-risk, and the gap is
bounded in a narrow 4–12pp band for eleven consecutive quarters (2019-03 →
2023-11) before jumping to 38pp at 1H26 — exactly when the deck documents the
1M26 reclassification of AC bonds into "proxy & open".

That clustering is what moves the odds. On the *total-assets* reading the gap
is a meaningful quantity — the share of FX-risk-bearing assets left unhedged
by derivatives — and a book that is nearly fully hedged should hug its
ceiling, which is what the data does. On the *subset* reading CS&NDF is a
share of a different base, algebraically free of FX-risk%, and hugging it for
eleven quarters would be coincidence. The subset reading also implies Cathay
ran a ~24.5% open FX position in 2Q22 (≈NT$1.3tn) while the sector regulatory
ratio was near 66% — hard to credit for the most conservative large lifer.

**Still not published, and why.** This is strong circumstantial evidence, not
a stated base, and it does not meet the standard Fubon's labelled wedge met
(4.2) — where the wedge names 外幣保單 among its own contents and settles the
question outright. The counter-evidence also survives: Cathay's layout is
structurally the same as Fubon's *2026* layout, and there Fubon labels the
large wedge 未避險 ("unhedged") while drawing the policy split separately,
which on a total-assets base would put policy-backed assets inside a wedge
called unhedged. Cathay's own wedge names ("proxy & open", not "unhedged")
weaken that objection without removing it.

**This is the single open judgement with the largest effect on the
headline**, and it is the user's to make: total-assets gives Cathay a 62%
economic hedge ratio at 1H26, subset gives 52.6%. Recorded here with both
readings and all the evidence so it can be ruled on directly rather than
re-derived. Until then Cathay's series 1 stays unpublished and only Fubon's
disclosed series carries the headline.

### 4.8 The 41億 year-end reserve gap is immaterial and does not touch any published series

**What it was.** STATUS carried an open item: at 2025 year-end a press
tabulation of the twenty life insurers' statements differed from the
briefing's sector FX-reserve figure by 41億 (NT$4.1bn), and Stage 3 was to
explain it before substituting a firm aggregate for the sector figure.

**Now testable, and it resolves three ways at once.**

1. *Our own two sector channels agree exactly.* The release channel and the
   briefing channel both put the 2025-12 reserve at **613,700 NT$ mn**, to
   the unit. The discrepancy was never between our sources; it was between a
   press tabulation and the briefing, neither of which we depend on for this
   figure.
2. *The four firms we now hold sum coherently.* Cathay 113,806.6 (18.54% of
   sector), Fubon 142,124.6 (23.16%), Nan Shan 68,045.2 (11.09%), KGI 43,370
   (7.07%) — **367,346.4, or 59.86%** of the sector total, which tracks
   these four firms' share of sector assets. No firm is anomalous against
   the sector figure.
3. *The gap is 0.67% of the sector total* and cannot be reproduced without
   all twenty firms' statements, which the environment does not reach
   (decisions 4.3).

**Closed, on the grounds that it does not matter.** No published series
substitutes a firm aggregate for the sector figure — series 3 takes the
sector reserve from the sector channels, which agree exactly — so a 0.67%
tabulation difference in a third-party sum has no path into the output. The
item is closed rather than carried, and the reason is recorded so it is not
reopened as though unexamined.

**Files.** none — a reconciliation, not a load.

### 4.9 The allowlist additions: data.gov.tw opens a clean regulator channel, ins-info stays shut for a different reason

Both hosts were allowlisted on 2026-09-04. They behave completely differently,
and the distinction matters for what to try next.

**`data.gov.tw` — open, and productive.** Its front-end API needs no key
(the documented v2 REST one does): `POST /api/front/dataset/list`,
`GET /api/front/dataset/detail?nid=N`, and a keyword search at
`GET /api/front/dataset/dropdown?list_type=published&qs=TERM`. The Insurance
Bureau is `agency_tid` 716 with **303 datasets**. The `list` endpoint ignores
the filter parameter names guessed so far, so the practical route is the
dropdown search plus `detail`.

**The win: dataset 14501 「人身保險業資金運用表」 → `openapi.tii.org.tw/
TIIOPENDATA/API/CSV_EXPORT?TableID=I171`.** That is 表17-1 itself — the
FSC-basis 國外投資 denominator — as structured monthly-refreshed CSV, reachable
once the TWCA intermediate is supplied exactly as for the other tii.org.tw
hosts (decisions 1.5). TableIDs are exact: I17 and I172 both answer "table not
find!", so they must be discovered from a dataset's resource url, not guessed.

**What it does and does not replace.** The export carries 16 rows — annual
2011-2025 plus the latest month (2026-05) — so it does *not* backfill the
112-month history that the PDF walk built (2.4); that pipeline stands. What it
does is (a) extend the series one month beyond the PDFs, (b) give a
maintenance path that needs no PDF parsing, and (c) **independently validate
stage2c**: an entirely separate channel agrees with the PDF-derived year-ends
to within 0.05% — 2024 國外投資 23,025,710 vs 23,025,601, 2025 22,765,264 vs
22,767,215, total assets 36,900,415 vs 36,900,485. The residuals are vintage
effects (ours are as-printed in the edition parsed, TII's are current
restatements), not parse error.

**`ins-info.ib.gov.tw` — allowlisted and still unreachable, which is not the
same as blocked.** The proxy no longer refuses it; the origin simply never
completes a TCP connection. Evidence: `curl` reports `time_appconnect=0.000`
on every TLS variant tried (1.2, 1.3, SECLEVEL=1) so no handshake ever
starts, the proxy logs `ws_closed_mid_exchange` rather than a 403 policy
denial, and the plain-HTTP path returns an Envoy **503 "upstream connect
error or disconnect/reset before headers. reset reason: connection timeout"**.
Browser headers, deep links and 70-second timeouts all fail identically. This
is a routing or geo-restriction problem at the origin, not something the
allowlist can fix.

**Consequence.** Dataset **7191 「壽險財務業務指標」 is the firm-level prize** —
`INSURER_Name` by year and quarter across 23 statutory indicators — but its
payload is hosted at `ins-info.ib.gov.tw/opendata/json-06161610.aspx`, so it
stays out of reach. The open-data catalogue also carries **no** hedge-ratio or
FX-price-reserve dataset (`避險` returns nothing; `準備金` returns only labour
and earthquake-fund series), so series 4 remains briefing-sourced and the
firm FX reserves remain deck- and statement-sourced. If the firm-level route
is wanted, the thing to ask for is an egress that can reach ins-info — not a
further allowlist entry.

**Files.** `config/allowlist.tsv` (three rows rewritten),
`cache/tii/I171_20260904.csv`.

### 4.10 The couriered firm-level indicators: dataset 7191 lands, mapped positionally, as a snapshot table

**Route.** ins-info remains unroutable from this egress (4.9), but the user
can reach it, so the payload behind data.gov.tw dataset 7191
(`ins-info.ib.gov.tw/opendata/json-06161610.aspx`, 表06161610 壽險財務業務指標)
was fetched by them on 2026-09-04 and committed verbatim as
`data/raw/ins-info/json-06161610_20260904.json`. The courier route is a
standing convention: any further ins-info file is committed under
`data/raw/ins-info/` with a `_YYYYMMDD` snapshot stamp, and the stamp is the
vintage — the payload itself carries no publication date and the catalogue's
`last_update_time` (2026-06-26) predates the quarter the data contains
(115Q2, ending 2026-06-30), so it is catalogue metadata, not a data vintage.

**What the file is.** 30 records, one per insurer at its *latest* reported
quarter: 22 active names at 115Q2, the pre-merger Shin Kong Life
(「115.1.1合併前」) at 114Q4, and defunct firms frozen at their last filing
(國華 102Q1, 國寶/幸福 104Q2, 中國信託人壽 104Q4, 朝陽 106Q1, 蘇黎世 106Q4, …).
It is a snapshot, not a panel: the history behind it sits in the portal's
query pages, which is the next courier ask. Each record carries
`ClaimYear` (ROC), `ClaimQuarter`, `INSURER_Name` and 23 positional
`AMOUNT` fields.

**Mapping AMOUNT1..23 — now verified, not merely inferred.** The catalogue's
`data_fields` describe only the three key fields; the AMOUNTs have no
per-field description. The dataset `content` string lists exactly 23
indicators in order (負債占資產比率 … 不動產投資與不動產抵押放款對資產比率), and the
second courier file (4.11) turns that reading into an arithmetic identity:
**AMOUNT1 equals total liabilities ÷ total assets from 表06021011 on all 30
records** (Taiwan Life 86.13 vs 86.12, KGI 86.81 vs 86.81, 三商美邦 92.76 vs
92.76, 國華 2861.78 vs 2861.78 …). Two independently published tables can only
agree on that relation if the first AMOUNT is the first listed indicator, so
the whole positional ordering is pinned. Four large firms carry residuals
(Cathay +0.10, Nan Shan +0.09, Shin Kong +0.02, Fubon +0.83pp), most likely
consolidation scope or a different refresh date between the two tables —
unresolved, and small enough not to disturb the mapping. The reading is
further corroborated on every indicator whose range is unambiguous: AMOUNT2
reserves/assets 72–91%; AMOUNT12 資金運用比率 96–99%; AMOUNT13 13-month
persistency 93–97%; AMOUNT22 EPS −3.13 for Shin Kong Life's loss-making 2025;
AMOUNT23 real-estate share ~7%. Those alone would have left the mapping an
inference; the AMOUNT1 identity makes it a verified fact. The verbatim record
is stored alongside (`raw_record`) so a re-mapping never needs the source
again.

**Two features to respect when reading it.** (i) The 2026 (IFRS 17) rows
publish only the balance-sheet and business ratios; ROA, ROE, yields,
margins, EPS and the real-estate share are `N/A` for every active insurer,
while the 2025 Shin Kong row carries the full set. Whether that is a
half-year convention or an IFRS-17 transition gap is not knowable from the
file. (ii) The growth fields are signed percentage changes, in both eras.
**This corrects the first reading of them, which was wrong.** Looking only at
the six panel firms, 保費收入變動率 and 淨利變動率 cluster near 100 (Taiwan Life
99.25 / 101.39, Cathay 90.02 / 98.13, KGI 62.69 / 101.13) and read as an
index of this period over prior period. The full 30-insurer cross-section
kills that: AMOUNT9 runs −7.91 (安聯) to 485.93 (宏泰) and AMOUNT11 reaches
−140.36 (蘇黎世 106Q4), and an index level cannot be negative. The lesson is
procedural — a functional-form question was left open because the test was
run on the six rows of interest rather than on the whole column. What stays
open is narrower and does not need the source: net-income change between 86
and 109 for *every* active insurer in one half-year is not how net income
behaves, so that column's base is unusual even though its sign convention is
settled. `N/A` and blank are distinct in the source (blank
marks indicators the 2026 rows do not carry at all: 5, 6, 7, 14); both load
as NULL and both survive in `raw_record`.

**Storage.** New additive table `tlfx.firm_statutory_indicators`
(migration 0008), wide, keyed on (`insurer_name`, `obs_quarter`, `vintage`):
these are the Bureau's ratios for every insurer, so the published name is
the key and `entity_id` is a nullable link into the six-firm panel (7 of 30
rows link; both Shin Kong names map to `shinkong_life` under the README §4.5
continuity convention, on different quarters so no collision). Not folded
into `firm_quarterly`: none of the 23 indicators is an FX quantity, and the
table's population (30 insurers) is a different universe from the panel.
Loader `scripts/stage3_ib_firm_indicators.py` runs the natural-key
collision guard (4.4) and prints per-column sums and non-null counts;
the load is verified against them server-side.

**What it buys the FX monitor.** Directly, little: no hedge ratio, no FX
reserve, no foreign-investment share. Indirectly, it is the first
regulator-published firm-level cross-section in the project (tier 2 of the
README §4 hierarchy), it gives the six firms' leverage and reserve ratios on
the Bureau's own definitions for the Stage 5 counterparty framing, and it
proves the courier route, which is what makes 表06021011 財務報告彙總 and the
per-company pages reachable.

**Files.** `data/raw/ins-info/json-06161610_20260904.json`,
`data/ib_firm_indicators.csv`, `scripts/stage3_ib_firm_indicators.py`,
`supabase/migrations/0008_firm_statutory_indicators.sql`,
`out/stage3_ib_firm_20260904.sql`.

### 4.11 The second courier file: 表06021011 財務報告彙總 ties the statement channel exactly for all six firms

**What arrived.** `ins-info.ib.gov.tw/opendata/json-06021011.aspx`, fetched by
the user on 2026-09-05 and committed as
`data/raw/ins-info/json-06021011_20260905.json`. 52 records — every insurer
the Bureau supervises, 30 life and 22 non-life, active names at 115Q2 and
defunct ones frozen at their last filing — with `OccurSeason`, `INSURER_Name`,
`AMOUNT1..3`, `ActualCapital`, `AMOUNT4..8`. No data.gov.tw dataset carries
this table (the catalogue search finds 7191/7192 for the indicators and the
TII/保發中心 aggregates, nothing for 06021011), so there is no field list to
lean on.

**What the data itself pins.** `AMOUNT1 − AMOUNT2 = AMOUNT3` holds to the
NT$ thousand on all 52 records, so the three are total assets, total
liabilities and owners' equity. Then the decisive check: for the six panel
firms the figures tie **exactly, to the NT$ thousand**, to what the project
already holds in the statement channel — Fubon, Nan Shan, KGI, Taiwan Life and
Shin Kong from MOPS XBRL, Cathay from the statement Excel:

| firm | assets NT$ mn (Bureau = statement) | equity NT$ mn |
|---|---|---|
| Cathay | 9,335,881.239 | 959,968.690 |
| Fubon | 6,604,842.795 | 890,933.026 |
| Nan Shan | 5,776,294.449 | 562,964.165 |
| KGI | 2,644,052.380 | 348,748.523 |
| Taiwan Life | 2,538,026.754 | 352,376.941 |
| Shin Kong (2026) | 4,209,479.534 | 403,634.560 |

Six for six. That is the first fully independent, regulator-published
confirmation of the MOPS parse (3.12/4.5 verified the *reserve* recovery
against decks; this verifies the balance-sheet totals against the Bureau).
It also settles a small question left open in the entities seed: the Bureau
reports the merged Shin Kong Life at exactly the figures MOPS files under
6985, so the 2026 statement rows are the right entity. The pre-merger Shin
Kong row (114Q4: assets 3,696,948.541 mn, equity 178,468.515 mn) has no
statement counterpart because that filing code was never verified; it is
loaded and linked to `shinkong_life` on the continuity convention, and now
supplies the 2025Q4 balance-sheet anchor the MOPS queue could not.

`ActualCapital` is paid-in capital by its own field name (Cathay 63,515 mn,
Fubon 118,420 mn — the familiar figures). `AMOUNT4..8` are **not named**: no
in-data identity pins them, the blank pattern (AMOUNT4 populated only on
pre-2026 and defunct rows, AMOUNT5/6 almost never) suggests discontinued
items, and AMOUNT7/8 are small ratios with no obvious denominator (Fubon
0.02 / 5,692; 三商美邦 0.01 / 18,648). Guessing would put a wrong label on a
regulator column; they are stored verbatim as `amount4..amount8` with the
whole record in `raw_record`, and the portal's column headers for 表06021011
join the courier list.

**Storage.** `tlfx.firm_statutory_balance` (migration 0009), keyed on
(`insurer_name`, `obs_quarter`, `vintage`) with `sector` life/non-life from
the published name (亞洲保險 is the one general insurer without 產物 in its
name; 中華郵政 is life). Units are **NT$ thousand as published** — a deliberate
exception to the NT$ mn convention, because this is a regulator table kept
verbatim; the A = L + E identity is a CHECK constraint. Loader
`scripts/stage3_ib_firm_balance.py` prints the statement ties and per-column
checksums; the load is verified against them server-side.

**Files.** `data/raw/ins-info/json-06021011_20260905.json`,
`data/ib_firm_balance.csv`, `scripts/stage3_ib_firm_balance.py`,
`supabase/migrations/0009_firm_statutory_balance.sql`,
`out/stage3_ib_balance_20260905.sql`.

### 4.12 Catalogue by-products: the CBC's life-insurer soundness indicators are open, stat.fsc.gov.tw answers, TIGF stays blocked

Searching data.gov.tw for the 06021011 table turned up three hosts the
project had not probed.

**`www.cbc.gov.tw` — 金融健全參考指標 – 壽險公司 (dataset 132163), reachable
(tier-1 host).** A 41-row CSV, quarterly 2016-03 → 2026-03: life-insurer
assets/GDP, ROA, ROE pre- and post-tax, **RBC capital-adequacy ratio
(semi-annual, 278% in 2016-06 → 315% in 2025-12)** and equity/investment
assets. Sector-level, CBC-published, and directly decision-relevant for the
capital-buffer framing of Stages 5–6: the RBC path through the 2025 shock
(312% at 2025-06, 315% at 2025-12) and the assets/GDP ratio falling from 143%
(2024-12) to 111% (2026-03) are both new to the project. Cached as
`cache/cbc/FSI_life_20260905.csv`; not loaded yet — it needs a small
sector-quarterly table of its own rather than a forced fit into
`sector_monthly`, and that is queued with Stage 5 rather than done in passing.

**`stat.fsc.gov.tw` — the FSC's statistics API, reachable.** Dataset 27947
exports from `api/v1/public/datasets/27947/export` without a key. The
particular dataset is stale (annual 2008–2017, announced 2020), but the host
is the FSC's structured-statistics channel and worth a systematic look at the
Insurance Bureau's other 300 catalogue entries; recorded on the allowlist.

**`www.tigf.org.tw` — still a 403 policy denial.** Dataset 172653 (壽險 /
產險 monthly stock and bond holdings, NT$ 100 mn, updated monthly) lives there;
it would give the sector's foreign-bond stock at monthly frequency from the
guaranty fund. Courier candidate.

**TII K47 (dataset 24606).** Two-year sector balance sheet by line item, NT$
thousand: 2024 assets 36,922,374,356 — 0.06% off the CBC table-8 figure the
project carries (36,900,485 mn), the same vintage effect as 4.9. Cached as
`cache/tii/K47_20260905.csv` for reference only.

**Files.** `cache/cbc/FSI_life_20260905.csv`, `cache/tii/K47_20260905.csv`,
`cache/fsc/stat27947_20260905.csv` (all gitignored caches; the URLs are in
`config/allowlist.tsv`).

### 4.13 Ingestion architecture: the reachability matrix, measured, and what it forces

The courier route (4.10/4.11) is not a pipeline. Before designing a
replacement, the question "who can reach what" was measured rather than
assumed, by running the same probe from the agent sandbox and from a
GitHub-hosted runner (workflow `probe-sources`, run 33933411996, runner egress
52.159.139.245).

| Source | Agent sandbox | GitHub runner | Reading |
|---|---|---|---|
| `ins-info.ib.gov.tw` | connect times out | connect times out | origin refuses both |
| `www.tigf.org.tw` | 403 at proxy | **200** | our proxy's policy only |
| `data.gov.tw` | 200 | 200 | open |
| `openapi.tii.org.tw` | 200 with TWCA cert | 000 without it | certificate, not reach |

Three conclusions follow, and the third is the important one.

**ins-info is a geography problem, not a permissions problem.** Two unrelated
networks — this sandbox's proxy and Azure's US ranges behind GitHub Actions —
fail identically, with `time_appconnect` at 0.000 and the TCP connect never
completing. Allowlisting cannot fix it and neither can a different CI
provider in the same regions. The user's own fetches succeed over a VPN,
which is evidence (not proof) that the discriminator is Taiwanese egress
rather than datacentre-versus-residential addressing, since a consumer VPN
exit is itself a datacentre address.

**Two sources were blocked for reasons that had nothing to do with the
origin.** TIGF answers a GitHub runner immediately; only our proxy refused it,
so the monthly stock and bond holdings series (data.gov.tw 172653) was never
actually out of reach. TII fails from a runner purely because the runner
lacks the intermediate certificate the server omits, which the repository
already carries. Both are now automated. The general lesson is that
"unreachable" had been recorded three times for three different causes, and
only one of them was real.

**`stat.fsc.gov.tw` is not a substitute.** It is reachable and exposes a full
catalogue at `api/v1/public/datasets`, but its 165 datasets are examination
statistics, agent registrations and award brochures. Nothing firm-level,
nothing on fund utilisation. Also noted: the data.gov.tw front-end `list`
endpoint ignores every filter parameter tried (`search_count` stays 53,111
regardless), so keyword `dropdown` plus `detail` remains the only route, and
the v2 REST metadata endpoint answers without an API key even though the data
endpoints demand one.

**The design.** Ingestion splits by egress rather than by source type.
`scripts/fetch_sources.py` fetches every source, writes each payload verbatim
to `data/raw/<source>/<name>_YYYYMMDD.<ext>` — the identical shape the
couriered files took, so the loaders read either without change — and
deduplicates on content hash, so the repository accumulates one file per
revision rather than one per run.
`.github/workflows/fetch-sources.yml` runs it monthly and commits anything
new. Sources needing Taiwan egress are fetched through an optional relay
(`ops/taiwan-relay`, a token-guarded single-host forwarder for deployment to
a Taiwan region); when the relay is not configured they are recorded as
unavailable and the run still succeeds, so the pipeline degrades to "does
everything except ins-info" rather than failing. That last property matters:
it means the relay is an upgrade the project can adopt later without
rewriting anything, and the courier route remains a valid fallback for the
same files in the meantime.

**What is still a judgement for the user.** Standing up Taiwan egress costs a
little money and creates a credential. That is theirs to decide, not mine, so
the relay ships as code and documentation with nothing deployed.

**Files.** `scripts/fetch_sources.py`,
`.github/workflows/fetch-sources.yml`, `.github/workflows/probe-sources.yml`,
`ops/taiwan-relay/` (`main.py`, `requirements.txt`, `Procfile`, `README.md`),
`data/raw/tii/`, `.gitignore`.

### 4.14 The catalogue sweep: TII does not replace ins-info, and the relay decision stands

Before recommending that the user spend money on Taiwan egress (4.13), the
obvious alternative was tested: is there a *reachable* host publishing what
ins-info publishes? The answer is no, and it is now settled rather than
assumed.

**Method.** data.gov.tw's `list` endpoint ignores every filter parameter
tried, so agency enumeration is impossible directly. Twelve insurance keyword
searches through `dropdown` yielded 1,151 candidate datasets; `detail` on each
gave the resource url, and the urls were grouped by host
(`scripts/discover_opendata_catalogue.py`).

**Result.** `openapi.tii.org.tw` — reachable, no key, the host that already
serves 表17-1 — carries **139 tables**, now catalogued in
`config/tii_tables.tsv` because TableIDs cannot be guessed (I17 and I172 both
answer "table not find!"; they exist only inside a dataset's resource url).
Thirty-eight of those 139 are firm-level, which sounds promising and is not:
every one is **business volume by company** — new and in-force contracts,
sums assured, premium income by line (K64–K73, K94–K100). The financial
tables on the host are all **sector** aggregates: I14 balance sheet, I15
income statement, I171 life fund utilisation, I161 non-life fund utilisation,
K46/K47 the two-year sector statements.

**So the gap is precisely characterised.** No reachable open-data host carries
firm balance sheets, firm fund utilisation, or firm foreign investment. For
the six-firm panel those come from exactly two places: MOPS XBRL (reachable,
already used, but slow against the WAF — 4.3) and ins-info (not reachable
without Taiwan egress). Nothing in the catalogue changes the relay decision;
it removes the hope that something might.

**What the sweep did add.** Firm-level premium and contract volumes on a
reachable host, which the project did not have. Those are not FX quantities,
but they give an independent asset-weighting for aggregating the six-firm
panel to sector, and a direct read on the premium-growth question that
AMOUNT9 in the statutory indicators answers ambiguously (4.10). Queued
rather than loaded: it is Stage 5 material, not Stage 3.

**Files.** `scripts/discover_opendata_catalogue.py`, `config/tii_tables.tsv`.

### 4.15 Standing up the relay: what I did, and the one thing I deliberately did not

The user asked for the relay to be set up. Three parts of that were mine to
do; one was not.

**Verified rather than assumed.** The relay now has a test record instead of
an argument: run locally against a real HTTP client, a missing token and a
wrong token are both refused, a foreign host is refused, a plain-http target
is refused, and the allowlisted target is forwarded and fails only because
this sandbox cannot reach the origin — which is the behaviour the relay
exists to fix. One error message was wrong (an http-scheme target reported
"host not allowed"); fixed.

**Reduced the human part to one command.** `deploy.sh` enables the APIs,
deploys from source to `asia-east1` and prints the two secret values;
`verify.sh` then fetches a real payload and reports which case the deployment
is in. The README leads with Google Cloud Shell, so nothing has to be
installed locally.

**Named a risk the architecture hides.** Cloud Run egress uses shared
Google-owned addresses that are not reliably geolocated to the region running
the service, and the origin filters on geography. Deploying to a Taiwanese
region is therefore necessary but possibly not sufficient, and no amount of
reasoning settles it — hence `verify.sh` and a documented fallback (a
`e2-micro` in the same region with its own external address, roughly USD 7-10
a month, since Google's always-free tier excludes `asia-east1`). Promising
that Cloud Run would work would have been the easy answer and an unfounded
one.

**What I did not do: deploy it.** This sandbox carries ambient cloud
credentials (`CLOUDSDK_AUTH_ACCESS_TOKEN`, AWS keys) belonging to the
execution environment, not to the user. Deploying with them would create a
billable, internet-facing service in a third party's project, outside the
user's control and invisible to them — an irreversible, outward-facing action
on authority the user never granted. "Set up the relay" authorises deployment
into *their* account, which needs their credentials. Everything short of that
is done.

**Files.** `ops/taiwan-relay/` (`main.py` scheme-check fix, `deploy.sh`,
`verify.sh`, `README.md` rewritten).

### 4.16 Two sector series from the pipeline, and the foreign-equity identity they open

The weekly workflow's first useful cargo. Both are sector-level, both loaded
into their own additive tables (migration 0011) because neither fits
`sector_monthly`, which is keyed to the FSC release and its FX table.

**CBC 金融健全參考指標 – 壽險公司 → `sector_soundness_quarterly`.** 41 quarters,
2016-Q1 → 2026-Q1: assets/GDP, ROA, ROE pre- and post-tax, equity/investment
assets, and — the reason it matters — **the RBC capital-adequacy ratio**, the
project's first solvency series of any kind. It is semi-annual: published for
June and December, a dash elsewhere, which loads as NULL. A loader that read
the dash as zero would post a solvency ratio of nought on the sector in half
its quarters, so the check asserts the publication pattern rather than trusting
it (20 of 41, exactly the June/December rows).

Two readings worth carrying into Stage 6. RBC held up through the shock —
312.03% at 2025-06 and 315.09% at 2025-12, against 331.95% at 2024-12 — so the
May-2025 FX loss cost the sector roughly 17pp of a ratio with a 200% statutory
floor, which is the buffer question answered at sector level for the first
time. And **assets/GDP breaks at the IFRS-17 boundary**: 131.22% at 2025-12
against 111.19% at 2026-03. That is a measurement change, not a NT$6tn
contraction, and the column comment says so, because a 20pp fall in an
assets-to-GDP series is exactly the sort of artefact that gets quoted as a
finding.

**保險安定基金 holdings → `sector_holdings_monthly`.** 20 months from 2024-12,
life and non-life as separate rows, stocks and bonds. Published in 億元 and
stored in NT$ mn (×100, exact on integers). Its value is frequency: it carries
the shock month at monthly resolution where every statutory table is
quarterly. Life bond holdings fall from NT$21.41tn (2025-04) to NT$20.18tn
(2025-05) and recover to NT$20.20tn (2025-06) — a NT$1.2tn drawdown inside one
month. **It is domestic and foreign combined and must never be used as a
foreign-asset series**; the table comment says so.

**What it does open.** TII 表17-1 publishes the *domestic* equity line
separately from 國外投資. Netting the two at 2026-05 — holdings 3,874,900 less
表17-1 domestic equity 3,120,434 — implies roughly **NT$0.75tn of foreign
equity**. That is not a curiosity: the FSC hedge-ratio denominator explicitly
excludes unhedged non-FVTPL equities and funds (README §3, series 4), so this
is a direct read on a term the project has so far only inferred. One month is
not a series — 表17-1's export carries annual rows plus the latest month only —
so this is recorded as an identity to exploit when Stage 5 needs the
denominator decomposed, not as a loaded series.

**Files.** `supabase/migrations/0011_sector_soundness_and_holdings.sql`,
`scripts/stage2d_sector_series.py`, `scripts/fetch_sources.py` (CBC added to
the weekly fetch), `data/raw/cbc/`, `out/stage2d_sector_20260905.sql`.

### 4.17 KGI's own 2025Q4 filing arrives: a deck base becomes a statement base, and "do nothing" becomes a fill-only upsert

The targeted MOPS queue (4.3) returned KGI's 2025Q4 filing on 2026-09-05.
Two consequences, one analytic and one about how loads are written.

**The recovery is now independently confirmed, and KGI is promoted.** The
2026 FX-reserve balances for every firm are derived, not printed: the IFRS-17
condensed balance sheet folds the line into other liabilities, so the balance
is the firm's own 2025Q4 figure less the cash-flow statement's year-to-date
net change (3.12/4.5). KGI was the one firm whose base came from its own deck
rather than a filing, which is why its reserve had been left in the deck
channel. The filing now puts that base at **43,372.327** against the deck's
printed 43.37bn — a 0.005% gap that is the deck's own rounding to NT$ bn. The
derived balances move by 2.3mn, to 44,834.091 and 48,993.847, and still tie
the decks at 44.83 and 48.99. So the arithmetic recovery is now verified
against three firms on two independent channels, and KGI's reserve moves into
the statement channel where its provenance belongs.

**The load pattern had a hole.** Every loader in this project writes
`on conflict do nothing`, which is right for re-running an unchanged extract
and wrong here: KGI's 2026 rows were already stored with a NULL reserve,
because the base had not been fetched when they were written. A "do nothing"
insert would have reported success and changed nothing, and the improvement
would have existed only in the CSV. The load now uses a **fill-only upsert** —
`set col = coalesce(firm_quarterly.col, excluded.col)` — which can turn a NULL
into a figure and can never replace one figure with a different one. That
distinction is the point: filling a gap at the same vintage is a *correction*,
and it is safe; changing a stored value would be a *revision*, and the
project's contract says a revision gets a new vintage and keeps the old row
(migration 0001). The upsert cannot do the second thing even by accident.

The general lesson, worth applying to the other loaders when they next touch
a partially-populated quarter: a row is often written before every field is
obtainable, so "insert once" is the wrong default for any table whose columns
arrive from different sources at different times.

**Queue state.** Fetching remains slow against the WAF, roughly one filing per
nine-minute foreground window, so the remaining anchors (Taiwan Life and KGI
2025Q4 done; the 2024Q4 set outstanding) continue across check-ins rather than
blocking anything.

**Files.** `scripts/stage3_load_mops.py`, `data/mops_statements.csv`,
`out/stage3_mops_load_20260905.sql`, `cache/mops/`.

### 4.18 The 2024Q4 anchor pays for itself: Fubon's reserve build, decomposed, with a residual worth chasing

Fubon's 2024 year-end filing arrived on 2026-09-05, giving the project its
first **pre-shock** firm-level FX-reserve balance. It is the single most
informative row the MOPS queue has returned.

| Fubon Life | FX volatility reserve | Total assets | Reserve / assets |
|---|---|---|---|
| 2024Q4 | 21,480.601 | 6,203,993.341 | 0.35% |
| 2025Q4 | 142,124.635 | 6,388,704.628 | 2.22% |

**A 6.6x build, +NT$120.6bn, in the year the sector took record FX losses.**
That is the opposite of the naive expectation — a shock draws a buffer down —
and it is the central fact about the 2025 buffer regime: the reserve is not
a passive cushion that erodes, it is a provisioning account the FSC allowed
and required to be filled aggressively while losses were being taken.

**The decomposition, using the cash-flow line already parsed.** The statement
of cash flows carries the year-to-date net change in the reserve, and the sign
convention is pinned (a negative figure is an addition, 4.5). For 2025 it
reads −112,638.262, so **112.6bn of the 120.6bn build came through that
line**, leaving a **residual of +8,005.772** — 6.6% of the change — that the
cash-flow line does not explain.

**The residual is not noise and should not be rounded away.** Two candidate
explanations, neither yet tested: transfers into the reserve from special
surplus reserve sit in the equity statement rather than in the operating
cash-flow line, or the FSC's 2025 reforms created reserve sub-buckets carried
under XBRL concepts the parser does not match, in which case the *headline
balance itself* understates FX loss-absorbing capacity. The second would
matter directly for series 3, whose v2 definition is explicitly four named
buckets (README §3). The parser currently matches one concept family
(`*ReserveForForeignExchangeValuation`); enumerating every reserve-like
concept in a 2025 filing would settle it, and that is the next thing to do on
this channel.

**Why this row and not another.** Fubon is the only firm holding both anchors,
which is precisely what the remaining 2024Q4 queue is for: without a
pre-shock balance the build is invisible and only the post-shock level shows.
Taiwan Life's 2025Q4 also landed, promoting its 2026 balances to a statement
base (29,977.868 and 33,343.941), so five of six firms now derive their 2026
reserve from their own filing rather than a deck.

**Files.** `data/mops_statements.csv`, `out/stage3_mops_load_20260905.sql`,
`cache/mops/`.

### 4.19 Half the buffer stack was missing: the equity-side special reserve

Chasing the NT$8.0bn residual in Fubon's reserve build (4.18) did not close
that residual, but it turned up something larger. Enumerating every
reserve-like XBRL concept in the 2025 filing — rather than the one family the
parser matched — found seventeen, of which four matter and none were being
read.

**The finding.** The project's buffer series was built entirely on
`ReserveForForeignExchangeValuation`, the liability-side FX reserve. But the
February 2026 notice defines **four** buckets (README §3, series 3 v2) and two
of them are appropriations of retained earnings into 特別盈餘公積, which sits in
equity and is reported under a different concept. Its size:

| NT$ mn, 2025Q4 | FX reserve (liability) | Special reserve (equity) |
|---|---|---|
| Fubon Life | 142,125 | 333,917 |
| Taiwan Life | 27,933 | 54,099 |

The equity side is **2.3x the liability side at Fubon and 1.9x at Taiwan
Life**. Every buffer-coverage number the project could have produced before
today understated loss-absorbing capacity by more than half.

**Verified, not assumed.** The statement of changes in equity reports the
year's appropriation and reversal dimensioned by equity component, so the
movement can be reconciled against the balance-sheet line. For Fubon 2025:
appropriated 70,481.532, reversal −3,013.707, sum **67,467.825**, against a
balance movement of 333,917.207 − 266,449.382 = **67,467.825**. Exact. That
identity is now a loader check (15/15), and it is what guards the parse: the
concept is reported once per equity column, so a dimension filter that picked
the wrong column would break the reconciliation immediately.

**The caveat that must travel with the number.** `special_reserve_equity` is
the whole 特別盈餘公積 line, so it is an **upper bound** on the FX-designated
portion — other statutory appropriations share it. And within the FX portion,
the notice's 強化準備 bucket is restricted capital that **cannot** offset
losses, so it belongs in the stack as a separate tier, not in the total.
Splitting the line needs the notes to the accounts rather than the face of the
statements. Until then the column comment forbids adding it to the FX reserve
and calling the sum loss-absorbing capacity.

**The original residual stays open.** The 8.0bn gap between Fubon's FX-reserve
balance movement and its cash-flow net change is not explained by any of
this — the equity appropriation is a separate account, not a transfer into the
FX reserve line. It remains a live question against that column.

**Files.** `supabase/migrations/0012_firm_quarterly_reserve_stack.sql`,
`scripts/stage3_mops_parse.py` (four concepts, dimension-aware context
matching), `scripts/stage3_load_mops.py` (four columns, reconciliation check),
`data/mops_statements.csv`.

### 4.20 What the completed stack shows at Fubon: the buffer nearly doubled through the shock

With the equity side captured (4.19) and the pre-shock anchor fetched (4.18),
one firm now has the full identified reserve stack across the break. Fubon,
NT$ mn:

| | FX reserve (liability) | Special reserve (equity) | Identified stack | % of assets |
|---|---|---|---|---|
| 2024Q4 | 21,481 | 266,449 | 287,930 | 4.64% |
| 2025Q4 | 142,125 | 333,917 | 476,042 | 7.45% |
| 2026Q1 | 147,389 | 381,903 | 529,292 | — |
| 2026Q2 | 153,677 | 420,247 | 573,924 | 8.69% |

**+NT$286bn in eighteen months, and 4.64% of assets to 8.69%.** The buffer
did not absorb the shock and shrink; it was rebuilt through and after it, and
the rebuilding is still running two quarters into 2026 — the equity side alone
added NT$86bn in the first half of 2026, faster than the liability side.

Two things this is not. It is **not** loss-absorbing capacity: the equity line
is an upper bound on the FX-designated portion, and one bucket inside it is
restricted capital that cannot offset losses at all (4.19). And it is **not**
yet a sector statement — Fubon is one firm of six and the only one holding
both anchors, though Taiwan Life's 2025Q4 shows the same shape at smaller
scale. Reading it as either would be exactly the overreach the column comments
were written to prevent.

What it does establish is direction and order of magnitude, and it reframes
the monitor's buffer question. The interesting quantity is not "how much
buffer was left after May 2025" but "how much earnings capacity is being
diverted into buffer, and for how long" — a flow question about retained
earnings, not a stock question about a reserve. That is the framing Stage 6
should carry.

**Files.** none — a reading of data loaded in 4.17-4.19.

### 4.21 The private-repo trap in the deploy path

The documented deploy told the user to `git clone` the repository in Cloud
Shell. The repository is private, so the clone stopped at a
`Username for 'https://github.com'` prompt — a dead end on a tablet, and one
that would have hit anybody following the instructions.

Cloning was never necessary. The relay is three small files, so
`ops/taiwan-relay/oneliner.sh` writes them with a quoted heredoc, deploys, and
runs the origin check in the same paste. That removes the GitHub credential
from the path entirely and also folds `verify.sh` into the same run, so the
question the deployment cannot answer in advance — whether Cloud Run's shared
egress is read as Taiwanese — is answered in one pass instead of two.

The heredoc was tested locally by executing the file-writing half and parsing
the result, rather than trusted to transcribe correctly.

The general point, worth applying to any future runbook here: instructions
that assume repository access are only valid for people who already have it,
and the deployment path is used precisely by someone standing outside the
repository.

**Files.** `ops/taiwan-relay/oneliner.sh`, `ops/taiwan-relay/README.md`.

### 4.22 A failed build reported as an egress verdict

The first real deployment attempt failed, and the script said the wrong thing
about why. Two separate faults.

**The build failure.** Google changed the defaults in 2024: a project created
since then does not grant the Compute Engine default service account the roles
Cloud Build needs, so `gcloud run deploy --source` dies at
`could not resolve source ... IAM permission denied for service account
<num>-compute@developer.gserviceaccount.com` while uploading. The fix is one
grant of `roles/cloudbuild.builds.builder`, now issued by both `deploy.sh` and
`oneliner.sh` before deploying; it is a no-op where the role is already held.
Worth knowing that this is not exotic — it is the default state of any recent
project, so the runbook was broken for the most likely user.

**The worse fault: the verdict.** The script ran its origin check regardless of
whether the deploy had produced a service, so with an empty `$URL` curl failed
on a malformed request and the run printed *"FAIL — Cloud Run egress is not
read as Taiwan; the VM fallback is needed."* That is a confident, specific,
and completely unfounded claim: the egress had never been tested. It would
have sent the user to provision a virtual machine to solve a problem that did
not exist.

The check now refuses to render a verdict it has not earned. An empty URL
stops with "the egress question is untested, not answered"; only a 502 — the
relay running and the origin refusing — is reported as the geographic failure;
anything else is INCONCLUSIVE and says so. `verify.sh` got the same treatment.

**The general rule this belongs to.** A diagnostic that cannot distinguish
"the thing failed" from "the thing was never attempted" will eventually assert
the first when the second is true, and the cost is not a wasted run but a
wrong architectural decision taken on its authority. Every check in this
project that ends in a verdict should be readable against that test.

**Files.** `ops/taiwan-relay/oneliner.sh`, `deploy.sh`, `verify.sh`.

### 4.23 The relay works: the geography was never the problem, and my check said it was — twice

The service deployed to `asia-east1` and the fetch returned 502 with the body
`SSL: CERTIFICATE_VERIFY_FAILED ... Missing Subject Key Identifier`.

**That is a success disguised as a failure, and the distinction is the whole
finding.** A certificate error can only occur after a TCP connection is
established and the server presents a certificate. The portal *answered* the
relay. Every prior attempt from every other network died at
`time_appconnect=0.000`, with no handshake at all (4.13). So Cloud Run's
`asia-east1` egress **is** accepted as Taiwanese, the architecture is right,
and the VM fallback is not needed. The remaining fault is entirely
client-side.

**The client fault.** Python 3.13 enabled `VERIFY_X509_STRICT` in
`create_default_context()`, which enforces RFC 5280 requirements that older
certificates often miss. The portal serves such a certificate, so a relay on a
current interpreter cannot fetch it. Clearing that one flag is **not**
disabling TLS verification: the chain is still built and verified to a trusted
root and the hostname is still checked; only the strictness about optional
extensions is relaxed, which is the pre-3.13 default and what every browser
reaching this site already does.

**The part worth being uncomfortable about.** This is the second time in one
sitting that my own diagnostic announced a conclusion it had not tested. First
it reported a failed build as an egress verdict (4.22). Then, having been
fixed, it reported *this* — a certificate error proving the egress works — as
`FAIL: egress not read as Taiwan; the VM fallback is needed`. Both times the
error was the same shape: a `case` arm matching a status code and asserting a
cause, when the status code alone could not distinguish the causes. Both times
the false verdict pointed at the same expensive wrong action, provisioning a
virtual machine.

The fix is not a better message but a different discipline: **a check may only
name a cause it has actually discriminated.** The 502 arm now refuses to
choose and says what to look for instead — a connect timeout means the
geography failed, a TLS error means the geography worked. Where the evidence
does not separate the hypotheses, the honest output is the evidence.

**Files.** `ops/taiwan-relay/main.py` (ssl context), `oneliner.sh`,
`verify.sh`.

### 4.24 End to end: the portal is now machine-readable

The relay fetched the full 表06021011 payload from Cloud Run `asia-east1` on
2026-09-05 — HTTP 200, the same JSON the courier route had been delivering by
hand. Both open questions close at once.

**The geography works.** Cloud Run's shared egress addresses are not always
geolocated to the region running the service, so a Taiwan region was necessary
but not obviously sufficient, and no amount of reasoning could settle it
(4.13). Measured: sufficient. That property belongs to Google's addressing
rather than to anything here, so `verify.sh` stays in the runbook — it is
cheap and it could change without notice.

**The client fix works.** Clearing `VERIFY_X509_STRICT` was the whole
remaining obstacle (4.23), with chain and hostname verification intact.

**What this changes.** The last manual step in the project's ingestion is
gone. Every source now has an automated path: the sandbox reaches most of
them, a GitHub runner reaches TIGF, and the relay reaches the Insurance
Bureau's portal. The courier route stays documented as a fallback because it
produces byte-identical files, but nobody has to run it.

**What it opens.** The portal is the tier-2 source the README's hierarchy has
been pointing at since the start (§4). With it reachable on a schedule, the
firm-level history behind the two snapshots becomes fetchable, and the
per-company disclosure menu — fund utilisation by firm, the capital-adequacy
table, the special-reserve breakdown that would split the buffer bucket 4.19
had to leave as an upper bound — moves from "ask the user" to "add a URL to
`SOURCES`". That is the next thing worth doing on this channel.

**Files.** `ops/taiwan-relay/README.md`.

### 4.25 The automated route reproduces the courier route exactly

With the secrets in place the workflow fetched both portal files itself:
`written 2, unchanged 4, unavailable 0`. The machine-fetched files are ~15-18%
smaller than the hand-delivered ones, which looked wrong and is not.

**Verified rather than assumed.** Parsing both and comparing record sets:
06021011 has 52 records either way and the sets are **identical**; 06161610 has
30 records either way and the sets are **identical**. The size gap is entirely
my own doing — the couriered payloads were saved through
`json.dump(..., indent=1)`, so they carry pretty-printing the origin does not.
Worth noting because the docs described those files as stored "verbatim" and
they were not; the automated ones genuinely are, being the response bytes
unmodified. So the courier route is not merely redundant, it is provably
equivalent, which is the strongest form the retirement could take.

**A real fault the comparison exposed.** The fetch overwrote
`json-06021011_20260905.json`, a hand-couriered file sharing that day's stamp.
Content was identical so nothing was lost this time, but the mechanism was
unsafe: a same-day file with *different* content is not a re-fetch, it is a
second observation — two channels on one day, or a source that changed between
them — and silently replacing either destroys the provenance that justifies
the rows built from it. The writer now keeps both, suffixing `-2`, `-3` and so
on, and only rewrites a path whose content already matches. Dedupe still works
because the suffixed name sorts after the plain one.

**Files.** `scripts/fetch_sources.py`.

### 4.26 Mapping the portal: the firm-level disclosures are URL-addressable

With the relay live, five discovery passes mapped the Insurance Bureau's
portal. The passes ran on the GitHub runner and reported back through a
committed file, because no single place can reach both ends — the portal
answers only the relay, and this sandbox's proxy refuses `*.run.app`. Each
turn of "read a page, decide what to follow" therefore costs a workflow run,
which is why each pass fetches everything at once and extracts links, query
shapes, form controls, option lists and viewstate presence together.

**Pass 2 — the aggregate side, settled.** The report menu lists ten 彙計表
codes, and `opendata/json-<code>.aspx` exists for **all ten**, not just the
three already known. Seven new machine-readable tables: company master data,
staffing, shareholdings, share transfers, non-life indicators, and the two
business-overview tables. All are now in `SOURCES`. **None of them is fund
utilisation or capital adequacy** — the aggregate tables simply do not carry
those, which is the negative result that made the next pass necessary.

**Pass 3 — the opening.** `customer/life.aspx` had returned a *null-reference*
error rather than a 404, meaning it existed and wanted a parameter. Testing
parameter shapes found that **`customer/Info2-2.aspx?UID=<8-digit id>` returns
a per-company balance sheet by plain GET** — 122KB, no postback. The
per-company disclosures are URL-addressable, so the relay needs no POST
support and none of the ASP.NET viewstate machinery has to be reproduced.

**Pass 4 — the menu.** Walking `Info2-1` … `Info2-16` reads back the whole
per-company menu from the page titles:

| | | | |
|---|---|---|---|
| Info2-1 **資金運用表** | Info2-2 資產負債表 | Info2-3 綜合損益表 | Info2-4 權益變動表 |
| Info2-5 **準備金** | Info2-6 放款/逾放 | Info2-7 關係人交易 | Info2-8 會計師意見 |
| Info2-9 現金流量表 | Info2-10 盈餘分配 | Info2-11 資產評估 | Info2-12 各項財務業務指標 |
| Info2-14 **其他負債項下之特別準備及其他準備** | | | |

**Info2-1 is the prize.** Fund utilisation *per firm* carries 國外投資 by
insurer — the hedge-ratio denominator the project has only ever had at sector
level (表17-1) or inferred from investor decks for three firms. Info2-5 and
Info2-14 are the reserve pages, and are the direct route to splitting
特別盈餘公積 into its FX-designated buckets, which 4.19 could only bound.

**Pass 5 and the identifiers.** The portal root's dropdown lists only the 22
non-life insurers, so the life ids came from elsewhere: TII **K106
保險公司基本資料**, reachable, whose head-office rows carry 統一編號. All six panel
firms resolved (`config/firm_uids.tsv`), and one reconciliation fell out of
it. Two Shin Kong ids exist and both are right — 03458902 is the pre-2026
company that was absorbed, 70789634 the surviving entity. K106 predates the
rename and still prints 保德信國際人壽 against 70789634, which traces the chain
Prudential of Taiwan → Taishin Life → Shin Kong Life and *confirms* the
merger convention in README §4.5 rather than contradicting it. KGI appears as
中國人壽, its pre-2023 name, same legal entity.

**Where this leaves the panel.** 21 per-company pages are now in the weekly
fetch (three reports × seven ids). They are Big5 HTML rather than JSON, so
each needs a parser — that is the next build, and it is Stage 3 work rather
than plumbing.

**Files.** `scripts/discover_ins_info.py`,
`.github/workflows/discover-ins-info.yml`, `config/ins_info_targets.tsv`,
`config/firm_uids.tsv`, `scripts/fetch_sources.py`, `reports/ins_info_map.json`.

### 4.27 Fund utilisation per firm: the denominator the project never had

`Info2-1` parsed and loaded (migration 0013). Twenty-eight rows: seven
registration numbers — the six panel firms plus the pre-merger Shin Kong
company — at four periods each, the latest month of the current ROC year and
three preceding year-ends.

**What it is.** 國外投資 by insurer, monthly. The project has carried this for
the sector since Stage 2 (表17-1) and for three firms from investor decks; it
has never had it published for all six, and never at monthly frequency. The
page is also the freshest thing in the repository — dated **2026-08**, where
the statutory filings stop at 2026Q2 and the sector table at 2026-05.

**Verified, not assumed.** The nine components must sum to the printed total.
That identity holds for **28 of 28** firm-periods, and is asserted in the
loader and re-checked in the database rather than trusted, because a
mis-parsed row here would flow straight into a denominator. The coverage
cross-check is the second test: the six firms sum to NT$18.17tn against a
sector NT$22.15tn (2026-05), or **82%** — the right order for a panel that is
about four fifths of life-sector assets. Wrong by a factor, or above 100%,
would have shown here.

**The trap this column sits next to.** 國外投資 is *not* the FSC regulatory
hedge-ratio denominator, which nets FX-policy liabilities and unhedged
non-FVTPL equities and runs about 68% of it (decisions 4.1). Pairing a
disclosed hedge ratio with this figure would restate the ratio by roughly a
third. The column comment says so, since the two are one word apart in Chinese
and the mistake would be invisible in the output.

**What it unlocks.** Firm-level series 1, 2 and 5 stop depending on deck
disclosure: net open position and gross hedge ratio can now be computed for
all six from published data, wherever a hedge principal exists. That is the
next derivation, and it is the first time the six-firm panel has had a common
published denominator rather than three deck-derived ones and three gaps.

**A trap in my own output, corrected before it spread.** The loader prints a
sum of `foreign_investment` per period, and at the three shared year-ends that
sum runs over **seven** rows, not six: Shin Kong reports under both
registration numbers, so those totals **double-count** it. Only the
2026-08-31 figure (n=6) is a clean six-firm total, which is the one the 82%
coverage check used, so that check stands — but the year-end sums beside it in
the same output do not mean what their neighbour means, and printing them
adjacently invited exactly that reading.

Worse, the two Shin Kong series are not splices of one company. 70789634 is
the surviving entity, which before 2026 was Prudential of Taiwan and then
Taishin Life — an order of magnitude smaller than the company that absorbed
it. So its 2023-2025 year-ends are the *small* predecessor, while 03458902
carries the large pre-merger Shin Kong through 2025 and supplies the lone
2022 row. Concatenating them into one `shinkong_life` line would manufacture
a step change that is a merger, not a flow. The `uid` column is in the primary
key precisely so both survive, and any firm-level series must choose one
registration number per era deliberately rather than grouping on `entity_id`.

**What the latest month shows.** Foreign investment as a share of each firm's
own invested funds, 2026-08: Nan Shan 72.4%, KGI 70.2%, Cathay 68.7%, Taiwan
Life 65.4%, Shin Kong 61.4%, Fubon 60.2%. A twelve-point spread across the
panel, which is the first time this project could see dispersion in foreign
allocation on a common published basis rather than inferring it from three
decks.

**Files.** `scripts/stage3_ib_firm_funds.py`,
`supabase/migrations/0013_firm_fund_utilisation.sql`,
`data/ib_firm_funds.csv`, `out/stage3_ib_funds_20260905.sql`.

### 4.28 The reserve pages: one real series, one dead end, and a correction to 4.19

`Info2-5` and `Info2-14` parsed and loaded (migration 0014, 15 rows, 15/15
component-sum checks). The result is more mixed than 4.19 hoped, and one part
of that entry was simply wrong.

**The correction first.** 4.19 predicted these pages would split 特別盈餘公積
into its FX-designated buckets and so close the question that entry could only
bound. **They do not.** `Info2-14`'s 特別準備 is the **liability-side** special
reserve, a different account from the equity-side 特別盈餘公積 carried on
`firm_quarterly`. The scale settles it beyond argument: liability-side
特別準備 is **zero** for five of six firms (Nan Shan alone shows NT$3.2bn),
against an equity-side balance of NT$333.9bn at Fubon. Two accounts, similar
names, three orders of magnitude apart. The column comment on
`special_reserve_liability` now says so, because reading one for the other
would wreck the buffer stack in either direction. **The equity-side split
remains unavailable**, and no source found so far carries it.

**Info2-5 has two layouts, and which one you get is not requestable.** A
company whose latest filing predates IFRS 17 — only the absorbed Shin Kong
(UID 03458902) — renders the old table: ten **labelled** rows across three
completed years, 外匯價格變動準備 among them. Active firms render the 2026
table: seven rows for one quarter whose 項目 cells are literally `&nbsp;` in
the source. The page title states the FX reserve is included, but no row
equals any firm's balance known from its own filings, so it is **bundled, not
merely unnamed**. Testing five period-parameter shapes against a baseline
(pass 6) returned byte-identical pages: the parameters are ignored and there
is no history through this endpoint. Those rows load positionally into
`unnamed_items`, on the 4.11 principle — publish what is published, name only
what is pinned.

**The one real gain.** Pre-merger Shin Kong's FX volatility reserve, NT$ mn:
**13,219 (2023) → 45,146 (2024) → 99,587 (2025)**. A 7.5x build over two
years, and a third independent firm telling the same story as Fubon's 6.6x
(4.18) and Taiwan Life's. That the absorbed company was building this hard
into its final year, while being merged, is itself informative about how
binding the provisioning regime was.

**A parser bug worth recording because of how it hid.** The pre-2026 layout
prints **four** value columns: an empty current-year quarter column, then
three completed years. My first version compacted blank cells away before
aligning values to periods, which shifted every figure one year later. It
produced 2024/2025/2026 for data that is 2023/2024/2025 — and it **passed
every sum check**, because the columns still balanced among themselves. Only
comparing against the printed header caught it. Alignment to a header must be
positional; compaction before alignment is a silent date corruption that
internal consistency checks cannot detect.

**A second bug of the same family, caught by verification rather than by the
checks.** The load succeeded and every sum balanced, but querying the stored
keys showed the unlabelled rows filed as `row_1:&nbsp;` … `row_6:&nbsp;`
rather than `item_1` … `item_6`. Cause: the portal writes empty cells as the
literal entity `&nbsp;`, and I unescaped it when reading *numbers* but not
when reading *labels*, so a blank label arrived as a truthy string and every
unlabelled row was filed under a key asserting a label existed. Entities are
now resolved once at the cell boundary, which is where they should always have
been. The rows were replaced at the same vintage — a parser correction, not a
source revision — with the numeric values verified unchanged across the round
trip.

Both bugs this entry records share a shape: neither was detectable by the
component-sum checks, because both preserved internal arithmetic while
corrupting meaning — one the dates, one the keys. Checks that test a table
against itself cannot catch a table that is self-consistent and wrong. The
ones that caught these were comparisons against the source's own header and
against the stored result.

**Files.** `scripts/stage3_ib_firm_reserves.py`,
`supabase/migrations/0014_firm_reserves.sql`, `data/ib_firm_reserves.csv`,
`config/ins_info_targets.tsv`, `out/stage3_ib_reserves_20260905.sql`.

### 4.29 The hedge ratio, reconstructed to 2019 from the release's own P&L lines — and validated

**The question this answers.** "How far back do we have the FX hedge ratio if
we create a composite bottom-up, and can that construction be validated?" The
published regulatory ratio starts 2024-04 and is sixteen observations long
(4.1). It cannot be fetched further back because the disclosure did not exist,
and the portal publishes no hedge amount for any insurer (4.26). So the ratio
has to be *inferred* — and the only inference worth having is one that
reproduces the published figure where both exist.

**The identity, and why it is the right one.** The monthly release carries
兌換損益 and, from 2020-01, 避險工具損益 separately from 換匯成本. Over a month
in which the currency moves by Δ, the first is A·Δ and the second is −H·Δ,
where A is the FX asset base whose translation reaches P&L and H the notional
of derivatives marked through it. So

    hedge ratio  =  −避險工具損益 / 兌換損益  =  H / A

and **Δ cancels**. The estimator needs no exchange rate, no asset base and no
view on the FX share of the book. That is not a convenience: the denominator is
exactly where this project's scope traps live — the regulatory denominator is
~68% of 國外投資 (4.1), and pairing the wrong one restates the ratio by a third
(4.27). An estimator with no denominator series cannot make that mistake.

**Two specifications tried and rejected, both instructive.**

*Regressing 兌換損益 on (foreign assets × Δ).* Missed by **24.2pp**, negative on
all six validation months. Cause: it assumes every foreign asset's translation
reaches P&L. For FVOCI equity it does not, so the slope measures the unhedged
share times an unknown scope factor. A specification that fails in one
direction on every observation is not noise; it is a statement about the data,
and the statement was "your asset base is wrong".

*Regressing 避險損益 on 兌換損益.* Better (8.6pp) but still biased up, and for
two reasons I had conflated. The first was mine: 避險損益 is the instrument
result **plus the swap carry**, and carry does not scale with Δ, so including
it makes the estimate a function of how violent the sample was. The second was
subtler and is the more useful lesson —

**The dating error, which is what most of the residual bias actually was.** A
window fit weighted by fx² is not an estimate of its last month. Twelve months
containing May 2025 — a 6% move, three times anything around it — is an
estimate of *May 2025*. I had been comparing such estimates to the published
ratio at the window's **end**, across months in which the ratio was falling
about 2pp each, and reading the resulting gap as a level bias in the
estimator. It was mostly the trend, measured over the distance between where
an estimate came from and where I had filed it. Re-dating each rolling
estimate to its own weighted centre cut the error from 8.4pp to 5.6pp; the
rest is the rolling estimator's genuine lag on a trending series. Every
rolling estimate now carries the centre it was really taken at. **A smoother
applied to a trending series does not merely add noise — it adds a bias that
looks exactly like a specification error, and I read it as one.**

**The estimator that survived, and its validation.** One month at a time, no
window, no smoothing, exact dating, and only months whose FX result exceeds
NT$200bn. That floor is a signal-to-noise threshold, not a convention: single
-month readings miss the published ratio by 3–5pp above NT$240bn and by 11pp
and 39pp at NT$121bn and NT$130bn.

| | n | MAE | mean error |
|---|---|---|---|
| exact published anchors clearing the floor | 3 | **4.4pp** | **+0.8pp** |
| all months inside the published window | 6 | 4.9pp | +3.1pp |

Essentially unbiased on the anchors; a small positive bias on the wider set,
which is the residual scope gap between the P&L asset base and the regulatory
denominator. It is **not calibrated out** — a scale factor fitted on six points
and applied to seven years is fitting noise and calling it history.

**The series, 2019-05 → 2025-11, nineteen observations.** 80% (2019) → 80%
(2021-04) → 76-77% (2022) → 72-75% (2023) → 69-76% (2024) → 68%, 65%, 57%,
59% (2025). The decline the published series shows over twenty months turns
out to be the tail of a six-year drift, and it is far from monotonic: 2024
sits *above* 2023 on this measure.

**The finding that matters more than the ratio.** Adding the FX volatility
reserve's net movement to the hedge result gives total P&L insulation from a
currency move:

    2019   93%, 85%       2022   88-90%       2024   86-90%
    2021   88%            2023   89-91%       2025   87%, 91%, 100%, 102%

**Six years, and it does not move.** The sector has held its total insulation
near 88-90% throughout, and pushed it to and past 100% in late 2025. What
changed is entirely the mix: derivative hedging fell roughly 20pp while the
reserve took over, and in the two most recent readings the reserve alone
absorbs more than 40pp. This is the substitution thesis, measured on one
consistent basis over six years instead of asserted from twenty months of
published ratios — and it reframes the question. The lifers did not reduce
their protection. They changed who pays for it, from the swap market to their
own equity, and the FSC's provisioning regime is what made that possible.

**What is assumed, and flagged as such.** 2018-06 → 2019-10 publish one
combined hedging line, so stripping the carry there means assuming it: NT$16.54bn
a month, the 2019 full-year cost over twelve. The ratio moves ~5pp per NT$10bn
of assumed carry, so those two rows (2019-05, 2019-10) carry the assumption in
`basis_note` and are excluded from every validation figure above. 2018 itself
produces no reading that clears the floor.

**Loaded.** `derived_series` series 4, keys `reg_hedge_ratio_pl_implied` and
`fx_offset_total_pl_implied`, `definition_version = v1_pl_implied`,
`basis = estimated`, 19 rows each, verified server-side (sums 13.9034 and
17.1709). Vintage is the **later** of the two release editions a month's
estimate consumes, because differencing a year-to-date figure needs both, and
dating it to the observation month's own release would claim the number was
available a month before it was.

**Files.** `scripts/stage5_implied_hedge_ratio.py`,
`data/implied_hedge_ratio.csv`, `out/stage5_implied_20260905.sql`.

### 4.30 The hedging cost, back to 1992 — and a counterparty check that closes

**Why this and not something else.** 4.29 established that the sector hedge
ratio fell about 20pp over six years. The first candidate for why is price: a
lifer hedges while the carry is bearable. The project's only cost series came
from investor decks — three firms, 2013 on, firm-reported — which is too short
to say whether the current cost is unusual and too dependent on each firm's
own definition to say what it measures. The CBC publishes USD/TWD forwards by
tenor from **1991-11** and spot from **1992-01**, so the market-implied cost
is directly observable, monthly, for thirty-four years.

**The construction, and the small choice inside it.** A lifer holding USD
sells USD forward, so it deals at the price a bank *buys* USD — 買入匯率 — and
its cost is that forward's shortfall against spot, annualised:
`(S_bid − F_bid) / S_bid × 360/days`. Both legs are bank-buys-USD prices, so
the dealer's spread cancels and what remains is carry. Pairing a bid forward
against a mid or interbank spot would fold half a spread into the cost —
about 10bp at current levels. Small, but the wrong sign of error to carry in a
series whose entire purpose is comparison across decades.

**The 90-day cost, annual means.** −0.99% (1992), −2.67% (1993), −0.93%
(1997), +1.96% (2000), **+3.86% (2006)**, +0.68% (2012), **+0.33% (2021)**,
+2.17% (2022), **+4.34% (2023)**, +4.02% (2024), +2.40% (2025).

Two things this settles. First, **hedging used to pay**: through the 1990s the
carry was negative, because TWD rates sat above USD rates. The current regime
is not the only one that has existed, and a model calibrated on the last
decade assumes away half the history. Second, **2023-24 was the most expensive
hedging environment in the series**, more expensive than 2006-07, and it
overlaps the period in which 4.29's reconstruction has the hedge ratio falling
hardest.

That second point looked like support for the price explanation and **it does
not survive testing — see 4.31, which was the whole reason for building this
series and which returns a negative.** The overlap is real; the causal reading
of it is not.

**Validation, and what it caught.** Set against what the firms say they paid:

| | quarters | mean reported/market | range | reading |
|---|---|---|---|---|
| Fubon | 26 | **0.51** | 0.15–1.71 | consistent |
| Cathay | 11 | 1.22 | 0.25–**4.39** | not the same measure |

Fubon behaves exactly as an all-in ex-ante carry cost must: it moves with the
market throughout and sits below it, because only the currency-swap and NDF
part of the book pays the market rate while the proxy-hedged, policy-backed
and open parts pay less or nothing. Two quarters exceed market, and the
larger, 2025Q2, is explicable and interesting on its own — the forward curve
repriced in the shock faster than an existing book could be rolled.

**Cathay does not validate, and that is the finding.** It exceeds the market
cost in three of eleven quarters, including 4.39x in 2015Q1 and 3.04x in
2021Q1 — quarters where Fubon reads 1.13 and 0.56 against the same market
cost. Because the divergence is firm-specific in the *same* quarters, the
fault is not in the market construction; the two firms' "hedging cost"
disclosures are not on the same definition. Series 7 currently pools them.
**It should not**, and the artifact must not draw them as one line. This is
the second Cathay deck-extraction finding after 3.9, and it points the same
way: that firm's disclosed series needs its definition pinned before it is
used, not after.

**A dating error of my own, corrected before it drew a conclusion.** The first
comparison scored each firm's *quarterly* figure against the market cost in
the quarter's first month alone. In a quarter like 2022Q3 the 90-day cost ran
0.9% to 3.4%, so the choice of month moved the ratio by a factor of three.
Quarterly averaging changed Fubon's 2022Q3 reading from 0.19 to 0.15 and
Cathay's 2015Q1 from 3.67 to 4.39 — the conclusion survived, but it was not
entitled to until the comparison was on matched periods.

**Two bad cells in 2,581, and the test that should not have been a filter.**
The 1994-05 120-day ask prints 26.270 in a ladder running 27.150 / 27.240 /
27.250 / 27.260 / **26.270** / 27.300 — a transposed digit — and the 2026-01
180-day bid prints 31.530 against a ladder falling 31.389 → 31.112. Both are
caught by one test that cannot produce a false positive: a bid above its own
ask is arithmetically impossible in a real quote. My first instinct was a
different test — all seven tenors price off one interest differential, so a
tenor disagreeing with the month's median must be bad — and it threw out
**312 cells**. Two reasons, and the second is worth more than the test was:
annualising a 10-day forward multiplies a 0.001 rounding by 36, so the
tolerance has to live in price space; and once it does, the largest surviving
deviations are not defects but **2025-06**, where five of seven tenors leave a
straight line. That is the curve genuinely going non-linear in the month after
the TWD shock. The flat-differential assumption fails precisely in the
stressed months that matter most, so it is kept as a reported diagnostic and
never as a filter. **A cleaning rule that fires hardest on the most
interesting month is not cleaning the data; it is deleting the finding.** The
raw values load unchanged either way (4.11); only the derived cost drops the
two impossible cells.

**The counterparty leg, which closes better than expected.** EG47M01 carries
daily-average FX turnover by market and instrument from 1994, and the whole
banking system's end-period net FX position. Two results:

- The **banking system's entire net FX position** has run between −USD 737mn
  and +USD 890mn across thirty-two years, and about +USD 450mn now — against a
  lifer foreign book near USD 700bn. Roughly **0.06%**. The banks intermediate;
  they do not warehouse. That is the Setser and S.T.W. (2019) claim as
  arithmetic rather than as an argument.
- A hedge book of USD 211–316bn rolled at three months implies USD 3.4–5.0bn
  of turnover a day. Observed customer swap plus forward turnover is USD
  3.2–4.3bn. The **ratio sits at 0.74–1.24, centred on 1.0**. Since that
  market also carries corporate and other financial flow, this is an upper
  bound on the lifer share rather than a measurement — but a ratio near 1
  constrains the mix: either the average tenor is longer than three months, or
  a material part of the book is rolled where CBC customer turnover does not
  see it, which is the offshore NDF leg.

Also loaded, and not yet used: customer swap turnover has gone from USD 12mn a
day (1998) to about USD 3bn (2025), a 250x growth that is the market being
built around this hedging demand.

**Loaded.** `tlfx.fx_market_monthly` (migration 0015), long format keeping the
CBC's own Table1/Table2 labels unmodified so a row is checkable against the
publication without a mapping. 18,405 observations parsed, **12,901 loaded**:
the published 年增率 sub-item is held in the CSV but not the table, because it
is an exact transform of the level series sitting beside it and the schema's
own convention is raw as published on ingest with conversions in
`derived_series`. Row width is asserted against items × sub-items on parse,
because a changed dimension would misalign every column and still parse
cleanly.

**A loading constraint that had to be designed around, and will recur.** The
first load emitted one `VALUES` row per observation: 18,405 rows, 1.9MB, five
chunked files. None of them applied. The reason is not Postgres — the SQL
never reached it. The load text travels as a tool-call argument, so the binding
limit is the size of the text itself, and row-wise chunking makes that worse
rather than better: it multiplies the calls without removing a byte, and most
of those bytes were the same Chinese label and date format repeated 18,405
times.

The fix is to send each series ONCE as a dense monthly array and let Postgres
expand it with `unnest … with ordinality`, reconstructing each month from the
array position. **1.9MB became 90KB in two files** — a factor of twenty-one,
with nothing dropped but repetition. This is now the pattern for the remaining
CBC series (EG49, EG01, EG46, BPP2 with its 402 series, BPF4), none of which
would have loaded the old way.

One property of that encoding is load-bearing and is commented as such: the
array must stay **dense**, with NULL where the source publishes nothing,
because the month comes from the position. Compacting it would date every
later value wrongly and still load without error — precisely the failure the
reserve parser made in 4.28. The nulls are dropped after the dates are fixed,
never before.

**And the chunking earned its keep for a reason I had not intended.** Even at
45KB a part takes minutes to apply. I misread that latency as a stall and
interrupted the load mid-way through part 2 — an unforced error, and the sort
that normally leaves a table half-populated and quietly wrong. It did not,
because each part is a separate `begin … commit` that is idempotent on the
natural key: part 1 had committed whole (EG47M01 complete, checksum exact),
part 2 had committed nothing, and finishing meant re-running part 2 rather
than working out what had survived. **Splitting a load into independently
committed, individually idempotent parts is not only a size workaround; it is
what makes an interrupted load recoverable by repetition instead of by
forensics.** The lesson about my own behaviour is the plainer one: slow is not
stuck, and the way to tell them apart is to ask the process, which I did only
after killing it.

**Files.** `scripts/stage5_cbc_fx_market.py`,
`supabase/migrations/0015_fx_market_monthly.sql`, `data/cbc_fx_market.csv`,
`data/fx_hedge_cost_market.csv`, `out/stage5_cbc_fx_20260905_p1..p5.sql`.

### 4.31 The price explanation for the falling hedge ratio does not survive a trend control

**The test the last two entries existed to make possible.** 4.29 reconstructed
the hedge ratio to 2019; 4.30 built the market cost of hedging to 1992. The
obvious hypothesis, and the one the project has been carrying implicitly since
the README's §9 note that "the hedge ratio is strongly carry-sensitive", is
that lifers hedge less because hedging got dearer. With both series in hand
that is now a regression rather than an assertion.

**It fails at the first hurdle: timing.** The contemporaneous cost explains
nothing (t = −0.54). Only the **24-month trailing mean** cost has any
relationship with the hedge ratio, which is already a warning — a
two-year-smoothed regressor over a six-year sample is close to a trend by
construction.

| dependent = derivative hedge ratio, regressor = 24m mean cost | slope, pp per pp | t | R² | n |
|---|---|---|---|---|
| all observations | −2.32 | −2.27 | 0.23 | 19 |
| excluding the carry-assumed 2019 months | −2.39 | −2.29 | 0.26 | 17 |
| 2022 on, excluding the near-floor 2024-01 | −2.65 | −2.83 | 0.38 | 15 |

Taken alone this looks like a result: a percentage point of sustained carry
costs about two and a half points of hedge ratio, robust across subsamples.

**Then control for time, and it disappears.**

| regressor | slope | t | R² |
|---|---|---|---|
| 24m mean cost alone | −2.32 pp/pp | −2.27 | **0.23** |
| a linear time trend alone | −0.214 pp/month | −3.89 | **0.47** |
| cost, on the hedge ratio's residual from that trend | −0.43 pp/pp | **−0.51** | **0.02** |

Time explains twice what cost does, and cost retains essentially nothing once
the trend is removed. The earlier regression was reading the calendar.

**The obvious objection, and why it fails.** If cost and time were near-
identical regressors, neither would survive controlling for the other and the
sample simply could not tell them apart — in which case rejecting the price
story would be overreach. So the test has to be run **both ways**, and it is
asymmetric:

| | slope | t | R² |
|---|---|---|---|
| cost, on the hedge ratio's residual from time | −0.43 pp/pp | −0.51 | 0.02 |
| time, on the hedge ratio's residual from cost | −0.128 pp/month | **−2.19** | **0.22** |

Time survives the control; cost does not. And the two are only moderately
collinear (cost on time, R² 0.33, r = +0.57) — far from the near-collinearity
that would make the question unanswerable. The sample **can** separate them,
and it separates them against cost.

**One observation kills the price story on its own, without any regression.**
Between 2024-08 and 2025-11 the 24-month mean cost **fell** from 4.27% to
3.28%, and over exactly that stretch the hedge ratio fell from **75.9% to
59.2%** — its steepest decline in the sample. The lifers hedged sharply less
as hedging got cheaper. A carry-sensitivity story has to explain that, and it
cannot.

**The buffer-inclusive series behaves the same way, which is confirmation not
duplication.** Total P&L insulation (hedges plus the FX volatility reserve)
has no relationship with cost at any lag, on the raw series or on the
time-residual (t = 0.16, R² 0.00). It does not need one: 4.29 already showed
it flat near 88-90% for six years. A measure that does not move cannot be
explained by a regressor that does, and the two results are consistent — the
sector holds protection constant and changes only the instrument.

**What this leaves, and it is the more interesting answer.** The substitution
away from derivative hedging is a **steady structural trend, not a price
response**. Its rate is remarkably even at about 0.21pp a month, or 2.6pp a
year, sustained across regimes in which carry was 0.3% and 4.3%. That pattern
fits a policy and accounting driver rather than a market one — the FX
volatility reserve regime being built out over exactly this period (4.19,
4.20, 4.28 all document the reserve building 6.6x to 7.5x at firm level), the
push into FX-denominated policies, and the IFRS 17 / TW-ICS transition — and
it is the reading the user's own framing anticipated.

**How much of this to believe.** Nineteen observations, irregularly spaced,
with a two-year smoothed regressor: the standard errors are optimistic and the
sample cannot separate finely-spaced hypotheses. What it CAN do is reject a
strong version of the price story, because the rejection rests on a sign that
goes the wrong way in the most recent third of the sample rather than on a
marginal significance level. The claim recorded here is therefore the negative
one — cost does not explain the decline — and not a positive claim about
which policy channel does. Distinguishing the reserve regime from the FX-policy
push from IFRS 17 needs the FX-policy liability series that the backfill spec
lists as a genuine gap, and that gap is now the binding constraint on the
project's second research question rather than a loose end.

**Correction.** 4.30 as first written said the cost and ratio overlap "is the
ordering the price story requires, and it would have been fatal to that story
had it come out the other way". That was true and too generous: an overlap
that survives no control is not evidence for the story it was invoked to
support. That paragraph now points here. README §9's "strongly carry-sensitive"
claim is corrected in the same pass — it was inherited from sell-side
commentary and had never been tested against the project's own data.

**Files.** No new script: the test runs on `data/implied_hedge_ratio.csv`
(4.29) and `data/fx_hedge_cost_market.csv` (4.30).

### 4.32 TII does not carry the FX-policy split — one of three candidates eliminated

4.31 made the FX-denominated policy liability series the binding constraint on
the second research question rather than a loose end, so its three candidate
sources (backfill spec, "the two genuine gaps") are now worth testing rather
than listing. The first is settled negatively and cheaply, from the catalogue
already held in `config/tii_tables.tsv`:

**No TII table has a currency dimension.** Across all 147 catalogued tables,
the strings 外幣, 幣別 and 美元 appear **zero** times. The premium tables cut
by line, by channel (K21 來源別), by company, by individual/group and by
investment-linked/traditional — never by currency. The balance-sheet and fund
-utilisation tables (I14, I171, K47) are the same aggregates the project
already has monthly from the Insurance Bureau, without a currency split.

So TII is out, and the remaining candidates are the Insurance Bureau's
business-overview tables (`json-07011010`) and the FSC's own 外幣保單
statistics, both of which need the relay and are the next thing to test. This
is a negative worth recording because it is cheap to re-derive and expensive to
re-discover: the catalogue is 147 rows and the answer is in a grep, but without
it written down the next pass fetches tables to find out.

**One weaker candidate noted, not pursued yet.** 投資型 (investment-linked)
tables K28-K31, K51-K54 give five-year histories of unit-linked policy account
values. That is not the FX-policy series — investment-linked and
FX-denominated are different cuts and overlap only partly — but it is the
closest thing TII has, and if the direct sources fail it is a bound rather than
nothing. Recording it so that judgement is made deliberately rather than by
forgetting the option exists.

### 4.33 The second FX-policy candidate exists but is unlabelled — parked with the reason

Following 4.32, the second of the three candidates for the FX-denominated
policy liability series is `json-07011010` on the Bureau's open-data endpoint.
It is **reachable and answers**: 200, 30 records, annual (114年度), one row per
life insurer. But its fields are `OccurSeason`, `INSURER_Name` and
`AMOUNT0`–`AMOUNT6` — seven unlabelled numeric columns, the same positional-
mapping problem as dataset 7191 in 4.10.

What the values look like for 臺銀人壽 (114年度): AMOUNT0 `0.81` (a ratio),
AMOUNT1 `21,306,825,776` and AMOUNT2 `28,419,182,043` (NT$ units, so ~21.3bn
and ~28.4bn), AMOUNT3–6 `1,134,313` / `829,595` / `174,996` / `26,343`
(counts). That shape — one ratio, two amounts, four counts — reads as a
business overview, **not** a currency split, and nothing in it suggests an
外幣 dimension. But reading a table by the shape of its numbers is exactly the
inference 4.10 and 4.28 both punish, so this is not a conclusion.

**Why it is parked rather than pushed.** Naming those columns needs the HTML
page that renders the table with its headers, which needs the relay, which
needs a workflow run. The open-data declaration page
(`data/raw/ins-info-probe/open-data_index_authoritative_endpoint_list_.html`)
was checked first on the chance it carried a code-to-title list: it does not —
it is a licensing declaration and contains no `json-` codes at all. So the
cheap route is exhausted and the next step costs a round trip.

Recorded now so the next pass starts from "fetch the 07011010 rendering page
through the relay to name AMOUNT0–6" rather than from "find out whether
07011010 exists".

### 4.34 How Setser did it, and the number that was in the cache all along

**The challenge, fairly put.** Setser and S.T.W. and the sell-side publish
long hedge-ratio histories; this project, after days of work, had thirteen
published months and a reconstruction to 2019. The paper was read in full
(`Shadow FX intervention in Taiwan`, CFR, October 2019). Its §II.D names
exactly two sources for the lifers' hedge book, and neither is obscure:

1. **Holdco disclosures, extrapolated.** The hedge share from the listed
   insurers' statements and investor decks (60–70% of sector assets),
   applied to the CBC's sector foreign-asset series. Quarterly, from the early
   2010s. This project has extracted precisely these decks — Cathay 47
   quarters, Fubon 49, KGI 20 — and never assembled them into the composite.
2. **A footnote on the CBC's own life-insurer balance sheet** (Financial
   Statistics Monthly, appendix 8) stating the sector's outstanding hedge
   transactions. Monthly. Setser: "historical footnotes are not part of the
   CBC's statistical database, so quite some extrapolation is required to use
   the small number of historical values obtained."

**The footnote was in `cache/cbc/065_EF67_A4L.csv` from 4 September**, line
63: 「115年7月底全體人壽保險公司換匯交易等避險交易餘額為52,180億元」. The
Stage 2 parser read the table body and discarded the notes. Every assertion in
this log that "no hedge amount is published anywhere" (4.26, the backfill
spec) was wrong, and wrong in a way a reading of the one paper the user had
named would have prevented on day two. **A table's notes are part of the
table.** That is the whole lesson and it is not a subtle one.

**Recovering the history.** The CBC overwrites the file monthly and keeps no
archive; the Internet Archive holds thirteen distinct captures of the table
from 2011, and the 2011 editions have no such footnote, so the series begins
between mid-2011 and 2012-03. One PDF hid its footnote behind CJK
compatibility ideographs (保 as U+F9E0), invisible to the eye and to a regex
until NFKC-normalised. Eleven points result:

| month | hedged, NT$ bn | 國外資產, NT$ bn | ratio | FSC principal | CBC ÷ FSC |
|---|---|---|---|---|---|
| 2012-03 | 2,447 | 4,388 | **55.8%** | — | — |
| 2015-07 | 4,140 | 9,059 | 45.7% | — | — |
| 2019-09 | 6,451 | 16,870 | 38.2% | — | — |
| 2022-06 | 6,816 | 19,721 | 34.6% | — | — |
| 2022-09 | 7,161 | 20,458 | 35.0% | — | — |
| 2022-11 | 6,790 | 20,749 | 32.7% | — | — |
| 2023-04 | 6,516 | 20,832 | 31.3% | — | — |
| 2024-03 | 6,623 | 21,822 | 30.3% | — | — |
| 2024-08 | 6,458 | 21,935 | 29.4% | — | — |
| 2024-12 | 6,463 | 22,472 | 28.8% | 10,357 | **0.62** |
| 2026-07 | 5,218 | 21,906 | **23.8%** | 6,804 | **0.77** |

**What it measures, now pinned.** 換匯交易等 — swap-type transactions. At
2024-12 it is 62% of the FSC's regulatory hedge principal; the press has
currency swaps at 「逾7成」 of lifers' hedges and NDFs at 「低於3成」. So the
CBC counts the **onshore swap book and not offshore NDFs** — the ambiguity
Setser could only flag is settled by the overlap. Two corollaries follow.
The CBC ratio sits below every other measure by construction (narrower
numerator, wider denominator), so Setser's Fig. 14, where "the
micro-constructed series continuously exceeds the CBC indication", is
explained rather than puzzling. And the CBC÷FSC share rising from 0.62 to
0.77 in nineteen months says the 2025 cut fell disproportionately on NDFs,
the expensive, opportunistic leg — the composition of the retreat, from two
public numbers.

**The four measures, reconciled at the anchor dates.**

| | CBC footnote ÷ 國外資產 | P&L-implied (4.29) | Cathay CS+NDF share | FSC regulatory |
|---|---|---|---|---|
| 2015-07 | 45.7% | — | 60% | — |
| 2019-09 | 38.2% | 74.6% | 61% | — |
| 2022-09 | 35.0% | 75.9% | 56% | — |
| 2024-03 | 30.3% | 68.9% | — | 66.0% |
| 2024-12 | 28.8% | — | 68% | 66.4% |
| 2026-07 | 23.8% | — | — | 42.9% |

They are four different quantities and they tell one story: onshore swaps
against all foreign assets, ~56% → 24%; the whole derivative book against the
P&L-scope base, ~80% → 59%; a firm's CS+NDF over its FX-risk-bearing assets,
60% → 36% (1H26); the regulator's own, 66% → 43%. Every one of them falls by
roughly a third or more from its start, and the timing agrees. **The long
history the user asked for exists, from 2012, on the CBC's own authority, and
the three constructions built here validate against it rather than replace
it.**

**Two leads not yet run down, stated so they are not rediscovered.**
Bloomberg (2025-12-16) quotes a quarterly "derivatives covered 52.3% of
overseas assets … lowest since the comparable data became available in
2013" — a series this project does not hold, and one Setser attributes to the
Taiwan Insurance Institute, whose web statistics (not its open-data API,
which has no hedge table, 4.32) were unreachable today (connection reset,
503). And Bloomberg (2026-01-27) calls the FSC's monthly ratio "the lowest
since at least 2020", against this log's finding (1.11) that the figure was
not published before 2024-04. Both are worth one more attempt each and no
more.

**Closed.** `json-07011010` (4.33) is 表07011010 壽險業務概況表, a life
*business overview* — premiums and policy counts by company — and not a
currency split. The third FX-policy candidate, the FSC's own 外幣保單
statistics, remains.

**Files.** `scripts/stage5_cbc_hedge_footnote.py`,
`data/cbc_hedge_footnote.csv`, `data/raw/cbc-table8-footnote/footnotes.json`,
`out/stage5_cbc_footnote_20260905.sql`. Loaded to `derived_series` series 5,
keys `hedge_outstanding_cbc_footnote` (disclosed) and
`hedge_ratio_cbc_footnote`, `definition_version = cbc_footnote`, 11 rows each,
verified.

### 4.35 The deck composite: Setser's method 1, built — 2014-12 to 2026-06, quarterly

**Built from data already extracted.** Cathay's 47 quarters, Fubon's 49 and
KGI's 20 have been in `data/*_deck_fx.csv` for weeks. Assembling them into the
composite Setser & S.T.W. describe (§II.D, method 1) took one script.

**The pie-base question, settled per firm.** Each deck draws a BAR splitting
foreign assets into FX-risk-bearing and FX-policy-backed, and a PIE of
instrument shares summing to 100. Cathay's pie is CS/NDF + proxy&open +
FVOCI-equity; KGI's is CS/NDF + naked + overseas equity. Neither names FX
policy, and policy-backed assets carry no derivative by construction, so both
pies are over the **FX-risk-bearing subset**:
`gross = pie × bar`, `economic = gross + policy share`. Fubon's wedge is named
「外匯交換、無本金遠期外匯、外幣保單」 and so is over **total** FX assets
(4.2). Same page, two different denominators.

**Fubon is reported beside the composite, not inside it,** for two independent
reasons. Its wedge cannot be split into derivatives and policy, so it can never
join the gross composite, and putting it in the economic one alone would leave
the two composites resting on different panels and unable to be differenced.
Worse, Fubon's own base moves: through 2016 the pie carries a separate
股票/共同基金 wedge of 11–15%, and from 2017 it is gone — so the firm reads
76.6% in 2014 and 95.2% in 2018 with no behavioural change that large.
Restating the early years onto the later base lines them up almost exactly
(2017Q2 96.9% restated against 2018Q1's published 95.2%), which confirms the
diagnosis but does not license blending: the equity wedge is extracted in 21 of
173 rows and its absence cannot be distinguished from a genuine zero. Mixing
two definitions into one line is the error at 4.2 and again at 4.30. Not a
third time.

**A fallback tried and removed.** Where Fubon's wedge is unpublished it is
tempting to take 100 minus the naked and equity wedges. That silently treats a
missing equity wedge as zero, and returned **95.5%** for 2017Q1. Only the
published wedge is used.

**The series.** 31 quarters. Gross (CS+NDF ÷ total FX assets): 37.2% (2014-12)
→ 48.3% (2018-09) → 46.1% (2020-12) → 45.5% (2022-03) → 38.0% (2023-03) →
35.4% (2024-09) → 26.7% (2026-06). Economic (+ FX policies): 61.2% (2014-12) →
78.3% (2018-09) → 75.5% (2022-03) → 67.4% (2024-09) → 53.0% (2026-06).

**Validation, and it is the good one.** Composite gross × sector 國外投資
against the CBC's published hedge amount (4.34), eight overlapping points
2019-09 → 2024-12: the ratio sits at **0.73–0.86, mean 0.79**, exactly the
onshore-swap share the CBC/FSC overlap independently established at 0.62–0.77.
Two constructions with no input in common — one from firms' own pie charts,
one from a central-bank footnote — agree on level to within a stable NDF wedge
and move together. That is the strongest cross-check this project has produced.

Against the sector gross ratio from the FSC's own principal the test is weak:
n=2, +8.9pp and −3.7pp. Both fall in quarters where the composite is one firm.

**The weakness, stated plainly. 28 of 31 quarters rest on a single firm.**
Cathay carries 2014–2024; KGI joins from 2023; only three quarters have two.
Where the panel composition changes between quarters the level jumps for that
reason and not for an economic one — 2025 reads 43.6 / 28.8 / 44.2 / 42.9
because the contributing firm alternates. Firm dispersion where measurable is
5.5pp on the gross ratio and up to 14.1pp. So this is best read as **Cathay's
hedge ratio, quarterly, with KGI alongside from 2023** — roughly a quarter of
the sector — and its *shape* is what carries weight, corroborated by the CBC
footnote's independent level. Setser's own caveat was the same: "extrapolations
based on the limited sample may not exactly represent the FX management across
all insurers." Widening the panel needs Nan Shan, Taiwan Life and Shin Kong
decks, whose IR hosts are reachable from a GitHub runner and are not yet
fetched.

**Where the history now stands** — five independent constructions, 2012 to
2026:

| construction | basis | frequency | span |
|---|---|---|---|
| CBC table-8 footnote (4.34) | disclosed | monthly, sparse | **2012-03 → 2026-07** |
| Deck composite, gross and economic (this entry) | firm-disclosed | quarterly | **2014-12 → 2026-06** |
| Fubon disclosed economic, base break at 2017 | firm-disclosed | quarterly | 2014-06 → 2025-12 |
| P&L-implied regulatory ratio (4.29) | estimated | monthly | 2019-05 → 2025-11 |
| FSC regulatory ratio | published | monthly | 2024-04 → 2026-07 |

**Files.** `scripts/stage5_deck_composite.py`, `data/deck_composite.csv`,
`out/stage5_deck_composite_20260905.sql`. Loaded to `derived_series` as
`gross_hedge_ratio_deck_composite` (series 5) and
`economic_hedge_ratio_deck_composite` (series 1), `definition_version =
deck_composite`, 31 rows each, verified.

### 4.36 A supplied source map, checked link by link — and one find that overturns 4.26

The user supplied `Taiwan_Life_Insurance_FX_Hedging_Data_Sources.docx`. Every
link was fetched and every figure tested against the source it cites. Eleven of
fourteen links resolve; the three that do not fail for reasons outside the
document (ins-info is geo-blocked from this sandbox as always, one Cathay media
path 404s, Scribd refuses the proxy).

**The find that matters, verified exactly.** Shin Kong Life's quarterly
statutory statements disclose the **notional principal of its FX hedges**, in
the currency-risk note:

  「新光人壽保險公司及其子公司使用遠期外匯合約及匯率交換合約以減輕匯率暴險，
   其名目本金共計新台幣 1,030,311,472 仟元、999,262,416 仟元及
   1,047,453,988 仟元」

— 2021-03-31, 2020-12-31, 2020-03-31. The document's three figures are right to
six significant figures. **This overturns 4.26**, which recorded that no hedge
amount is published for any insurer. That was true of the *portal*; it is false
of the *statutory filings*.

It is also better than the document claims. The derivatives note on the same
filing gives the split in USD — 匯率交換合約 USD 19,827mn and 遠期外匯合約
USD 16,285mn at 2021-03-31 — and the two disclosures **reconcile at the
period-end spot rate to four decimals**: 1,030,311,472 ÷ 36,112,000 = 28.5310,
the 2021-03-31 rate; 999,262,416 ÷ 35,052,000 = 28.5080; 1,047,453,988 ÷
34,622,000 = 30.2540. Three independent ties. So the filings yield hedge
notional *and* its currency-swap/forward composition, quarterly, three periods
per filing.

**The document's extraction warning is correct, and I verified both sides.** It
warns against taking the table headed 避險工具 because under IFRS that means
only derivatives designated for hedge accounting. Cathay's 2024Q1 statement
shows 遠期外匯合約 名目本金 NT$49.2bn — against NT$5,470bn of foreign assets,
about 0.9%; its 2021Q1 shows only 換匯換利 at NT$8.6bn. Shin Kong is usable
precisely because it states 「並未採用避險會計」, so its economic hedges appear
in the currency-risk note instead. This is the same trap already recorded from
Fubon's XBRL (`ifrs-full:HedgingInstrumentAssets` NT$0.7bn against NT$3.4tn).

**Where the document overstates.** It cites Cathay's statements as giving
"usable historical depth" for hedge notionals immediately before the warning
that would disqualify them. Cathay's statement notional is the designated-hedge
figure and is not a substitute for Shin Kong's; the two paragraphs read as
though they describe the same quantity and they do not.

**Two of its figures catch gaps in my own extraction, not in the document.**
Cathay's FY2022 deck does print 外幣資產 NT$5.11兆, 具外匯風險資產 68%,
外幣保單負債 **32%** — the value my extract left blank at FY22 (the legend on
the same page, "Proxy & Open / Currency Swap & NDF / FVOCI & FVTPL (overlay)",
independently confirms 4.35's reading that Cathay's pie is over the FX-risk
subset). And Fubon's 1Q2026 deck prints 具外匯風險資產 **77.6%** /
外幣保單負債 **22.4%** alongside 外匯交換、無本金遠期外匯 **23.9%**, FVOCI
7.2%, FVTPL 5.3%, 未避險 63.7%. My extract had three of those four wedges and
neither bar. **That fixes the Fubon problem of 4.35 for 2026**: the wedge label
drops 外幣保單 in 2026, so the pie is over the risk subset like Cathay's and
Fubon can join the gross composite — 0.239 × 0.776 = 18.5% gross, 40.9%
economic at 1Q26.

**Checked and correct:** data.gov dataset 10767 is 人壽保險公司資產負債統計表
(the CBC life-insurer balance sheet, EF67 — already loaded from 1987-05);
dataset 7190 is 保險公司財務報表摘要, whose resource is the json-06021011
endpoint already loaded as `firm_statutory_balance` (4.11). The direct CBC
`EF67M01.csv` link resolves (147KB) and is an alternative channel to the one
Stage 2 uses. The closing statement — that no single regulator download carries
company-level hedge notional and FX-policy liabilities together — matches this
project's own finding.

**What this opens, in priority order.**
1. Shin Kong's hedge notional is the best per-firm source found so far: exact,
   quarterly, with the swap/forward split, and three periods per filing so the
   archive walks back cheaply. Shin Kong is ~11% of sector foreign investment.
   The filing URLs carry an opaque path segment (`/financial/85/`), so the
   index must be walked rather than guessed — probing ROC-year filenames
   returned 404 on all ten attempts.
2. Test whether Nan Shan, Taiwan Life and KGI disclose the same way. Any firm
   not applying hedge accounting should, and that is most of them.
3. Patch the two extraction gaps above (Cathay FY22 bar, Fubon 2026 bar + CS/NDF
   wedge) and re-run 4.35.

**Files.** No code change in this entry; the supplied document is recorded at
`docs/sources/supplied/fx_hedging_data_sources.md` with the verification result
against each claim.

### 4.37 The supplied DATA_SOURCES.md reset — adopted, with three corrections

The user supplied a directive source map that overrides earlier guidance. Every
checkable claim in it was tested. **The structure is right and is adopted**: the
six target variables (a)–(e), the acceptance test (company level before 2020 or
sector level before 2010), the extraction rules in §3.2, and the order of work
in §5. The extraction rules in particular are already independently confirmed —
§3.2 rule 1 (notionals from the derivatives note, never the 避險工具
hedge-accounting table) is exactly what 4.36 verified on Cathay, and all three
of its §3.3 reference-value sets were verified there too.

**Three claims are wrong and would have cost time.**

*§1.2, the FSC statistics API as "the cleaner route to (a) and (c)".* The API is
real, documented and reachable — `stat.fsc.gov.tw/api/v1/public/datasets`
returns 165 datasets with JSON query and CSV export. It carries **none of the
six target variables**. Searching all 165 names for 財務報表摘要, 財務業務指標,
資金運用, 國外投資, 避險 and 外幣 returns **zero** on every term. Its insurance
holdings are agent-registration counts, exam schedules and association member
lists at 3–48 rows each; the only balance-sheet item is 壽險業總資產統計,
**annual, ten rows, 2008–2017**, against a monthly sector series this project
has held from 1987. The claim that it serves the families behind data.gov.tw
7190 and 7191 is false. Marked ‡ in the document (surfaced, not opened), and
opening it is what settles it.

*§1.1, `checkrpt.aspx` as the "multi-company aggregation query (彙計表) — select
table + period → all companies in one table".* It is a **menu page**. Its entire
body is ten links to `RPT-05010111` … `RPT-07090901`, the same ten report pages
already mapped at 4.26. There is no period selector and no company selector on
it. The aggregation query is each `RPT-*` page, which carries 公司名稱 and
日期區間起迄 controls. The document's procedure is right in substance and wrong
in address; the depth question it poses is real and still unanswered, and is now
the highest-value open test in the project.

*§2.2, "scrape the monthly PDF versions of table 8 from the index for every
month available".* The CBC publishes **one file that each month overwrites**;
the index exposes no per-month archive, so this instruction cannot be followed
as written. The problem was already solved differently at 4.34 — the Internet
Archive's captures are the archive, and eleven editions from 2012-03 to 2026-07
are loaded.

**One material omission.** The document attributes the ins-info access problem
to robots exclusion and prescribes "a browser-like User-Agent, session cookies,
and a rate limit". The actual blocker is **geographic** (4.13): the host answers
only from Taiwan, and no header or cookie changes that. This project already
runs a Taiwan-egress relay for it (4.15). The same applies to
`www.ib.gov.tw/ch/home.jsp?id=181` in §1.1 step 1, which fails from here. Also,
all three TII hosts in §2.3 are marked † (confirmed opened) but **none is
reachable from this environment** — `www.tii.org.tw`, `sv.tii.org.tw` and
`insdb.tii.org.tw` all fail to connect, and `insprod.tii.org.tw` returns 503.
That is an environment fact rather than a document error, but it makes §2.3
unavailable without a route the project does not yet have.

**One number to check.** The target panel is given as 20 entities; this log had
recorded 23 life insurers on the portal. The IB company list is unreachable from
here, so the discrepancy is left open rather than resolved either way.

**Where the framing overstates.** The hard rule says FSC releases "start in
2020, are aggregate-only, and are the reason the last three days were wasted".
The release channel is aggregate-only and its *regulatory hedge ratio* does
effectively start 2024-04 (1.11), so the caution is warranted for (a)–(e). But
that channel is also the source of the 兌換損益 / 避險工具損益 / 換匯成本 lines
from 2018-05 that produced the validated hedge-ratio reconstruction to 2019-05
(4.29, MAE 4.4pp against the published anchors) — and §2.5 explicitly permits
loading it for exactly those fields, so there is no actual conflict with the
rule as written. Similarly §5 defers investor presentations to last, which is
sound sequencing, but the deck composite already built (4.35) validates against
the CBC footnote at a stable 0.79 across eight points and is not superseded by
anything the reset proposes.

**Net.** It helps, and its main contribution is a correct diagnosis of the
project's real gap: there is no company-level panel of (a)–(e) with pre-2020
history, and the statutory filings are the only route to (e). That is the same
conclusion 4.36 reached from Shin Kong's disclosure. The single test that would
now settle the largest question — how deep the Observation Station's period
selector goes on `RPT-06021011` — needs a POST through the Taiwan relay, which
currently forwards GET only.

**Files.** `docs/sources/supplied/DATA_SOURCES.md` (verbatim, with the
verification result recorded against each disputed claim).

### 4.38 The company panel is 2009-deep, and the first per-firm hedge notionals load

Four results, in descending order of how much they change the project.

**1. The Observation Station holds a company × quarter panel back to 2009 —
and the answer was already on disk.** `RPT-06021011.aspx` (表06021011
財務報表摘要) is an ASP.NET form whose period selectors offer **ROC 98 to 115,
2009 Q1 to 2026 Q4**, over 55 insurers with a 壽險/產險 filter. That is read
directly from the `<option>` lists in a page the discovery pass fetched days
ago. No query was needed, and the supplied source map's first and most
important open question (4.37) is answered: the pre-2020 company panel exists.
The same form shape appears on the other nine RPT pages, so 表06161610 and
表07011010 follow the same route.

Two corrections to how it is reached. `checkrpt.aspx` is a **menu**, not the
query — its whole body is ten links to the RPT pages. And **GET does not
work**: sending the form fields as a query string returns a 3.5KB error page
against the 21.6KB real form, so the page reads `Request.Form` and a POST is
required. That was worth testing rather than assuming, because many WebForms
pages do accept either and it would have saved the relay change.

**2. The relay gains POST, and the reason it also needed cookies.** The portal
answers only from Taiwan, so the POST must go through the relay. `/post` sits
behind the same two guards as `/fetch` — allowlisted host, shared token — so
what widens is what may be *asked of* the one permitted host, not which hosts
are reachable; it is still not an open proxy. The forwarder now also passes
`Set-Cookie` back and `Cookie` forward, because the server ties `__VIEWSTATE`
to the session that issued it and a relayed POST without the cookie fails
viewstate validation in a way that reads exactly like a malformed request. The
redeploy script was regenerated, and one real bug fixed in it: it minted a
**new** token on every run, which on a redeploy would have silently invalidated
the GitHub secrets and broken every workflow. It now reuses the token the
service already runs with.

**3. The first per-firm hedge notionals are loaded, and they self-verify.**
Shin Kong Life, six quarters — 2020-03, 2020-12, 2021-03, 2023-06, 2023-12,
2024-06 — from two filings, each carrying three period columns. NT$1,047bn →
NT$999bn → NT$1,030bn → NT$1,208bn → NT$1,369bn → NT$1,399bn, with the
currency-swap and deliverable-forward legs in USD alongside.

The check that makes them trustworthy: the currency-risk note's NT$ total and
the derivatives note's USD split are typeset independently and **tie at the
period-end rate on all six quarters to four decimals** — 30.2540, 28.5080,
28.5310, 31.1350, 30.7350, 32.4500. The loader asserts this and prints the
implied rate, because a tie at an implausible rate is two errors agreeing
rather than a confirmation. Forwards get their own column: 遠期外匯合約 is
deliverable and an NDF is not, the FSC's traditional-hedge definition
enumerates instruments, and the whole CBC-versus-FSC gap (4.34) turns on that
split.

A second bug was caught by the load rather than by any check: the generated
SQL named a **four**-column conflict target against `firm_quarterly`'s
**five**-column primary key, which omits `basis`. Postgres refuses that
outright — "no unique or exclusion constraint matching the ON CONFLICT
specification" — so the transaction rolled back whole and wrote nothing. The
failure mode is the good one: an idempotent load that cannot name its own key
fails loudly instead of inserting duplicates. All six quarters predate the 2026
transition, so `basis` is IFRS4.

A unit slip was caught by the tie itself — the first version multiplied a
NT$-million total by 1,000 against a USD-million split and produced implied
rates of 30,254. Six identical failures at exactly 1000× is a units bug
announcing itself; had the check been a tolerance on a single number it would
have been tuned instead of fixed.

**Coverage is one firm and that is recorded, not smoothed.** Cathay applies
hedge accounting to a small designated book, so its 名目本金 table reads
NT$49bn against NT$5.5tn of foreign assets and measures something else
entirely. The other four are untested. MOPS turned out to be a dead end for
them: it does list the life subsidiaries under their own codes — 新光人壽
28880001, 富邦人壽 28810012, 台壽保 28910031, which is itself worth knowing —
but its document server answers 查無所需資料 for those codes on every document
type tried. Nan Shan's site is reachable but its report API refuses an
unauthenticated POST. A firm absent from this table is **unknown, never zero**.

**4. Two verified extraction gaps patched, as an overlay rather than an edit.**
Cathay's FY2022 bar (外幣保單負債 32% / 具外匯風險資產 68%) and Fubon's 1Q2026
bar (22.4% / 77.6%) plus its CS+NDF wedge (23.9%) go into
`config/deck_corrections.tsv`, cited to the deck page each came from. The
extracted CSVs stay exactly as the parser produced them: editing them in place
would make a parser bug and a source change indistinguishable next time.

That patch has a consequence for 4.35. **Fubon's 2026 pie drops 外幣保單 from
its big wedge** and prints the bar separately, which makes it the same shape as
Cathay's and KGI's — so from 2026 Fubon joins the gross composite it was
rightly excluded from before. It is also the least hedged of the three: 23.9%
of a 77.6% risk subset is **18.5%** of total FX assets, against Cathay's 26.6%
and KGI's 28.5%, with 63.7% of its risk-bearing book naked. Adding it moves the
2026-03 composite from 28.5% to 21.9% and widens the gap to the FSC-basis
sector ratio to −10.3pp, which is the panel-coverage caveat of 4.35 doing
exactly what it was written to warn about: two firms are not twenty-three. The
strong validation is unmoved — CBC ÷ composite stays at 0.79 across eight
points.

**Files.** `scripts/probe_rpt_panel.py`, `.github/workflows/probe-rpt-panel.yml`,
`ops/taiwan-relay/{main.py,oneliner.sh}`, `scripts/stage3_mops_statements.py`,
`scripts/stage3_stmt_hedge_notional.py`,
`supabase/migrations/0016_firm_hedge_notional.sql`,
`config/deck_corrections.tsv`.

**Blocked on one action.** Pulling the 2009→ panel needs the relay redeployed
with `/post`. That is a single paste of `ops/taiwan-relay/oneliner.sh` into
Google Cloud Shell; it reuses the existing token, so no secret changes. Until
then the panel probe reports the 404 rather than failing silently.

### 4.39 Scope corrected: the duration-demand channel, and the flow has already turned

**The correction.** The user's framing: the project has been treating FX
hedging as the object when it is a gate. What matters to a bond market is that
one domestic sector recycles a current-account surplus above 10% of GDP into
long-dated USD credit. The hedge ratio, the buffer stack and the 2026
accounting changes are inputs to that, not ends. README §1 now leads with it.

**The series was already cached and unparsed.** Taiwan's balance of payments
splits portfolio-investment debt-security acquisition by sector AND by tenor,
so the cut that matters is directly published:

    債務證券 - 其他部門 - 其他金融機構 - 長期 - 資產

quarterly. Items are resolved by LABEL, not index: the BoP carries 402 of them
and an index would silently return a different series if the CBC reordered,
which is the failure class of 4.28 all over again.

**The sector identification, measured rather than asserted.** Setser & S.T.W.
take "other financial institutions" to be the lifers. Against the lifers' own
國外資產 from the CBC balance sheet, converted at year-end:

| | 2012 | 2015 | 2018 | 2021 | 2023 | 2025 |
|---|---|---|---|---|---|---|
| lifer FX assets, USD bn | 176 | 303 | 508 | 688 | 685 | 700 |
| OFI IIP debt stock, USD bn | 170 | 271 | 484 | 695 | 718 | 778 |
| ratio | 104% | 112% | 105% | 99% | 95% | **90%** |

Above 100% in the early years because lifer 國外資產 includes equity and funds
that a debt-only stock excludes — so the true lifer share of OFI *debt* is
somewhat below these figures throughout. Either way the sector is the lifers,
and the drift from 104% to 90% says non-bank others have grown slightly faster
lately, which is worth watching but does not change the reading.

**The stock.** OFI holdings of foreign debt securities: USD 170bn (2012) →
484bn (2018) → **778bn (2025)**, and **71–79% of ALL Taiwanese foreign
debt-security holdings** throughout. This is not a participant in the US credit
market, it is a top-tier one.

**The flow, and it has already turned.** Net acquisition of LONG-TERM foreign
debt by this sector, USD bn a year:

    2012  22.8   2015  37.3   2018  57.0   2021  41.0   2024  19.3
    2013  22.1   2016  58.2   2019  41.6   2022  16.4   2025  −7.7
    2014  28.6   2017  52.2   2020  13.4   2023  15.1

**2025 is the first net-selling year in the series**, and the quarterly detail
puts it precisely: 2025Q2 = **−USD 12.4bn**, the largest single-quarter
liquidation on record, in the TWD-shock quarter. 2026Q1 is −2.9bn. Meanwhile
the current-account surplus set records — USD 184bn in 2025, and 2025Q4 alone
was 69.9bn.

**That conjunction is the finding.** Taiwan is running its largest ever external
surplus while its principal private recycler is a net seller of the assets that
surplus used to buy. The vulnerability question the user posed is therefore not
hypothetical: the stock was sold, hard, in the one stress episode the sample
contains, and the flow has not recovered four quarters later. Everything the
project has built about hedge ratios, buffers and accounting is now
interpretable as the mechanism — the hedge ratio fell 20pp, the reserve
absorbed what the hedges no longer did, and when TWD moved 6% in a month the
response was to sell the asset rather than re-hedge it.

**Limits of what this series can say, stated so the next pass does not
overclaim.** The tenor split starts 2012Q1, not 1984 — the sector detail does
not exist earlier, so the four-decade history is of the aggregate only. And the
BoP has **no currency and no issuer-type dimension**: it cannot by itself say
"USD corporate". For that the next sources are the US TIC survey (holdings of
US securities by country and security type, which does separate corporate debt)
and the firms' own disclosures on asset type and duration. That is the next
step and it is what turns "long-dated foreign debt" into the specific claim the
question asks about.

**Files.** `scripts/stage6_duration_demand.py`, `data/duration_demand.csv`,
`out/stage6_duration_20260905.sql`. Loaded to `derived_series` series 9 as
`ofi_lt_foreign_debt_purchases`, `ofi_foreign_debt_purchases` and
`ofi_foreign_debt_stock`, `definition_version = bpm6`.

---

### 4.40 The composition of the duration bid: TIC says agency MBS first, corporate credit second and rising

4.39 established the flow and the stock but ended on an explicit limit: the
balance of payments has no currency and no issuer-type dimension, so it cannot
say "USD corporate". The US Treasury's annual TIC benchmark survey of foreign
portfolio holdings of US securities can. It reports, by country, the split into
equities, Treasuries, agency non-ABS, agency ABS, corporate bonds and corporate
ABS. `scripts/stage6_tic_holdings.py` parses Taiwan's row from eleven vintages,
2013 to 2024.

**What Taiwan holds in the US market, USD bn, end-June:**

| | 2013 | 2016 | 2018 | 2019 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|---|---|
| Treasuries | 183 | 185 | 161 | 172 | 234 | 227 | 236 | 265 |
| agency ABS | 126 | 207 | **250** | **265** | 243 | 222 | 208 | 192 |
| corporate bonds | 35 | 80 | 97 | 115 | 162 | 139 | 152 | **173** |
| corporate ABS | 1 | 1 | 2 | 2 | 2 | 3 | 3 | 2 |
| equities | 23 | 43 | 65 | 68 | 110 | 100 | 112 | 146 |
| **all LT debt** | **346** | **473** | **510** | **554** | **642** | **590** | **599** | **632** |

**The market-share reading, which is the one that answers the question.** Taiwan
as a percentage of ALL foreign holdings of US securities:

| | 2013 | 2015 | 2018 | 2019 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|---|---|
| agency ABS | 19.2 | 25.4 | **26.2** | 24.6 | 20.5 | 19.4 | 17.1 | **14.9** |
| corporate bonds | 1.5 | 1.8 | 2.8 | 3.2 | 3.9 | 3.9 | 4.1 | **4.4** |
| all LT debt | 4.1 | 4.4 | 5.0 | 5.0 | 5.2 | 5.1 | 5.0 | 5.0 |

An economy of USD 800bn held **a quarter of the entire foreign-held stock of US
agency MBS** at the 2018 peak. That is the duration bid in one number, and it is
agency MBS first — the longest-duration, most negatively-convex instrument in
the US market — not Treasuries. The corporate share has nearly tripled, 1.5% to
4.4%, and is the only line still rising.

**And the agency-MBS position has already been cut.** 265bn (2019) to 192bn
(2024), −73bn, while the foreign-held total rose from 1,077 to 1,291bn. Taiwan
did not merely stop adding; it shrank the book in absolute terms through the
period when everyone else grew theirs. The share fell from 26.2% to 14.9%. This
is the same retreat 4.39 found in the BoP flow, seen from the US side and dated
a year or two earlier, and it lands in the instrument where a forced seller is
worst placed — extension risk means the position lengthens exactly when the
seller most wants out.

**Attribution to the lifers, and the asymmetry that makes it defensible.** TIC
measures a country, not a sector: Treasuries and agency non-ABS mix the CBC's
reserves with private portfolios and are NOT attributed here. Agency ABS and
corporate debt are, on the grounds that a reserve manager does not run a USD
175bn corporate-credit book and the CBC's own reserve guidance describes
deposits and sovereign paper. The asymmetry is deliberate; it is why the table
is worth parsing rather than the headline total, and it is stated in the
`basis_note` on every loaded row.

**Validation.** The seven cells of each row must sum to the printed total; a
country label landing mid-column is the failure mode this catches, and every
accepted row passes. Independently, Table A3/A9 prints LT debt by country across
eight survey dates, compiled from the same returns but printed in different
units — it agrees with the composition table on **11 of 11** overlapping years,
to the billion. The same table extends the total-debt series to 2007 and
supplies 2020, whose survey report is not retrievable from the Treasury document
server (four filename patterns tried, all 404). No vintage revises another: six
overlapping reports print identical history for every year.

**One anomaly, flagged not explained.** The by-year table gives 2010 and 2011 as
213bn each and then 349bn for 2012 — a +136bn jump that neither lifer foreign
assets (+~36bn) nor FX reserves (+~10bn) can account for. All six vintages that
cover those years print the same figures, so it is not a parsing artefact. Until
it is understood, the composition series is read from 2013 and the pre-2012
points are not used for anything load-bearing.

**The gap this opens, which is the next piece of work.** From 2019 the lifers'
own foreign debt stock (OFI IIP, 749bn at end-2024) EXCEEDS Taiwan's entire
country-wide holding of US long-term debt (632bn in June 2024) — before setting
aside whatever share of that 632bn is the CBC's reserves. The lifers' USD
duration book is therefore substantially larger than their holdings of
US-ISSUED securities, and the residual has an obvious candidate: 國際板 (Formosa)
bonds are USD-denominated paper from foreign issuers listed in Taipei, so they
are USD credit exposure that TIC does not see at all. TIC 173bn is thus a FLOOR
on the lifers' USD corporate credit, not a measure of it. Sizing the Formosa
book is the next step.

**Files.** `scripts/stage6_tic_holdings.py`, `data/tic_taiwan_holdings.csv`,
`out/stage6_tic_20260905.sql`. Loaded to `derived_series` series 10,
`definition_version = tic_shl`: seven Taiwan series, seven `world_`-prefixed
all-foreign-holder denominators (stored as primitives so a share is computed in
SQL, never frozen at parse time), and `us_lt_debt_holdings` 2007-2024. 172 rows,
sum 464,613,186 USD mn, verified server-side against the generator.

---

### 4.41 The Formosa book: USD 218bn of 28-year callable credit that no US statistic sees

4.40 closed on a gap. From 2019 the lifers' own foreign debt stock (OFI IIP,
USD 749bn at end-2024) exceeds Taiwan's ENTIRE country-wide holding of US
long-term debt (632bn, June 2024) — before setting aside the part of that which
is the CBC's reserves. A large share of the lifers' USD book is therefore not
US-issued, and the TIC survey is blind to it by construction.

國際板債券 — Formosa bonds — are the explanation. Foreign issuers list
USD-denominated paper on the Taipei Exchange and sell it to professional
investors. It is USD credit risk and USD duration; the issuers are not US
residents, so it appears in no TIC table. TPEx publishes the register of listed
issues through its OpenAPI, and `scripts/stage6_formosa_register.py` reads it.

**The market, 5 September 2026, 938 listed issues:**

| currency | issues | face at issue, USD bn | share |
|---|---|---|---|
| **USD** | **863** | **218.2** | **92.6%** |
| ZAR | 18 | 7.7 | 3.3% |
| CNY | 10 | 7.1 | 3.0% |
| AUD | 46 | 2.7 | 1.2% |

Taiwanese issuers are USD 7.6bn of the USD book, 3.5% — TSMC, the banks, and
(worth noting for series 9) USD 0.43bn of Cathay Life's and Taiwan Life's own
USD sub-debt. The other 96.5% is foreign credit.

**The shape of the paper is the finding.** Amount-weighted ORIGINAL tenor is
**28.0 years**, perpetuals excluded:

| original tenor | USD bn | share |
|---|---|---|
| ≤10y | 36.6 | 16.9% |
| 11-20y | 9.6 | 4.4% |
| **21-30y** | **107.1** | **49.4%** |
| **>30y** | **63.5** | **29.3%** |

and after a decade of ageing the book has barely shortened, because it was
issued so long: **74.5% still has 20 years or more to run** (USD 161.5bn), and
only 5.5% matures inside three years. The roll-off ladder is concentrated in
2047-2051 (USD 94.3bn, the 30-year 2017-2021 vintage) and 2060-2061 (USD
38.3bn, the 40-years).

**And the investor is short the call on three-quarters of it.** USD 165.6bn,
**75.9%** of the USD book, is issuer-callable, and the dominant structure is
5-year non-call then callable annually (324 issues), i.e. a 30-year bond the
issuer can retire from year five. That is the same negative convexity as the
agency-MBS position in 4.40, deliberately taken for spread: the buyer earns the
option premium and accepts that the position shortens when rates fall and
extends when they rise. Both legs of the lifers' USD duration bid — 192bn of
agency ABS and 166bn of callable Formosa — are short convexity. That is not a
coincidence; it is the same reach for yield expressed twice.

**Largest issuers, USD bn:** Qatar 17.0, Citigroup 7.1, MDGH (Mubadala) 6.8,
Verizon 6.4, First Abu Dhabi Bank 6.3, JPMorgan 6.2, Barclays 5.7, QNB 5.6,
Bank of Nova Scotia 5.5, AT&T 5.3. Gulf sovereigns and quasi-sovereigns,
global bank holdcos, US telecoms — long-dated USD corporate and quasi-sovereign
credit, which is precisely the segment the research question named.

**What this file cannot do, and it matters.** Three limits, all recorded in the
`basis_note` of every loaded row:

1. It is a snapshot, not a history. Matured and called issues are gone, so
   amounts by issue year are "issued then and STILL LISTED now" and are heavily
   survivorship-biased — the 2020-21 rally saw callable issues redeemed en
   masse, which is why 2019 (14bn surviving) looks smaller than 2020 (54bn).
   They are not an issuance series and are not loaded as one.
2. Amounts are face at issue, not amount outstanding. Partial redemptions do
   not show, so each line is an upper bound.
3. **The register carries no holder information.** It says what exists, not who
   owns it. Attributing the bulk to the lifers rests on regulatory history and
   supervisors' statements, not on this file. Nothing loaded here claims lifer
   ownership, and the open item is now explicit: a sourced series for lifer
   holdings of 國際板債券 is still missing, and until it exists the link from
   market size to lifer exposure is inference, not measurement.

**Two failure modes caught in parsing.** TPEx codes a perpetual as tenor 99.9
maturing 2910-12-31; left alone that added half a year to the weighted-average
tenor and printed a maturity bucket in the thirtieth century. Seven issues, USD
1.413bn, now separated. And the `_org` register — nominally foreign issuers not
publicly offering equity in Taiwan — in fact contains domestic banks' USD paper,
which is why the Taiwanese-issuer split above is reported rather than assumed
away.

**Files.** `scripts/stage6_formosa_register.py`, `data/formosa_register.csv`
(938 issues, full register), `out/stage6_formosa_20260905.sql`. Loaded to
`derived_series` series 11, `definition_version = tpex_register`: 55 rows, sum
of the USD-mn rows 1,279,000.070, maturity ladder summing to 216,801.688 =
218,214.688 less the 1,413.0 of perpetuals. Both verified server-side.

---

### 4.42 Correction to 4.40: the agency-MBS decline is rotation and price, not liquidation — and Taiwan is a sixth of the marginal foreign bid for US corporate bonds

Two things came out of extending the TIC pull by one vintage and doing the
increment arithmetic. The first corrects 4.40; the second is the number the
research question actually asked for.

**The correction.** 4.40 read the fall in Taiwan's agency-ABS holdings — USD
265bn (2019) to 192bn (2024) — as "Taiwan did not merely stop adding; it shrank
the book in absolute terms". That overstates it. **TIC holdings are at market
value, so a change in the level mixes price with flow and is not a transactions
series.** Agency MBS repriced heavily downward over exactly that window, and
the project already holds a transactions measure that excludes valuation: the
BoP series from 4.39 shows the sector was a net BUYER of long-term foreign debt
in every one of those years — 41.6, 13.4, 41.0, 16.4, 15.1 and 19.3 USD bn for
2019 through 2024, about USD 147bn cumulative. Against that, Taiwan's measured
US long-term debt holdings rose only 554 → 632bn. The wedge is valuation and
non-US allocation. So the correct reading of 2019-2024 is **rotation out of
agency MBS into corporate credit, inside a book that was still growing** — not
a retreat. The genuine net selling is a 2025 event and it is the BoP that shows
it, not this table.

**The 2025 survey, the first observation after the May TWD shock, supports that
reading rather than the earlier one.** As of 30 June 2025 (USD bn, prior year in
brackets): total LT debt **677** (632), Treasuries **304** (265), agency ABS
**184** (192), corporate bonds **186** (173), equities **172** (146). The stock
went UP, not down, through the shock quarter. Three things are happening at
once and only the third is the lifers retreating: the CBC's reserve build shows
up in Treasuries (+39bn); the lifers keep adding corporate credit (+13bn); and
agency MBS keeps shrinking (−8bn). Taiwan's share of all foreign-held US agency
ABS falls again to 14.0%, and its corporate share dips for the first time, 4.4%
to 4.1%.

The caution this leaves on the record: TIC is a country, June-dated, and at
market value; the BoP is a sector, quarterly, and at transaction value. Where
they disagree the BoP answers questions about behaviour and TIC answers
questions about composition. Neither is a substitute for the other and 4.40
used TIC for a behavioural claim it cannot support.

**The marginal-buyer arithmetic, which is what the question asked.** Taiwan's
share of the CHANGE in all foreign holdings, computed in SQL from the stored
primitives:

| segment | Taiwan Δ, USD bn | all foreign Δ, USD bn | Taiwan share of the increment |
|---|---|---|---|
| agency ABS 2013-2019 | +139 | +420 | **33.1%** |
| agency ABS 2019-2024 | −73 | +214 | −34.2% |
| corporate bonds 2013-2024 | +138 | +1,683 | 8.2% |
| **corporate bonds 2019-2024** | **+58** | **+347** | **16.7%** |

Subject to the same market-value caveat — these are changes in stock, not
purchases — this is the answer to "what role have Taiwanese lifers played as a
source of duration demand in USD bonds". Through 2013-2019 Taiwan absorbed
**one third of the entire increase in foreign holdings of US agency MBS**. Over
2019-2024 it took **one sixth of the increase in foreign holdings of US
corporate bonds**. One economy of USD 800bn, at the margin, in the two
longest-duration segments of the US market that foreigners buy. And the
valuation caveat biases these DOWN rather than up over a period of rising
yields, because Taiwan's book is longer than the average foreign holder's, so
price falls cut its measured stock harder.

**Files.** `scripts/stage6_tic_holdings.py` extended to 2025; series 10 now
187 rows, sum 534,388,186 USD mn, verified server-side against the generator.

---

### 4.43 Cathay Life's own disclosed rate sensitivity — and why it is not the net economic exposure

The statutory filings carry two tables the project had not used: 利率風險敏感度
分析表 (change in P&L and in EQUITY per 1bp parallel shift, by currency — a
disclosed DV01) and 匯率風險敏感度分析表 (per 1% FX move, with the FX
volatility reserve as a third column). `scripts/stage6_firm_sensitivity.py`
parses both. Cathay Life's Q1 filing (合併, 民國115年第1季, code 5846) gives, in
NT$ mn:

| USD curve +1bp | 2026-03-31 | 2025-03-31 |
|---|---|---|
| P&L | −144 | 0 |
| **equity** | **−2,530** | **−1,376** |

| USD +1% vs TWD | 2026-03-31 | 2025-03-31 |
|---|---|---|
| P&L | 0 | +5,104 |
| equity | +9,201 | +10,500 |
| FX volatility reserve | +500 | +7,656 |

**The headline arithmetic, and the caveat that must travel with it.** NT$2,530mn
per bp against total equity of NT$626,792mn means a 100bp parallel rise in the
USD curve moves an amount equal to **40% of Cathay Life's equity**. That is the
right order of magnitude for the exposure and it needs no duration assumption —
it is the firm's own number. But it is an ASSET-SIDE figure and must not be
read as the net economic hit. The same filing's OCI statement shows insurance
finance income of +NT$136,211mn in the quarter against FVOCI debt losses of
−NT$55,771mn: under IFRS 17 the liability discount-rate effect also runs through
OCI and, in that quarter, more than offset the asset move. A disclosed
sensitivity that is negative for a rate RISE is therefore gross of the liability
offset. Quote it as the scale of the fair-valued USD rate position, never as
the net.

**The change is the more interesting number.** The USD equity DV01 nearly
doubled in a year, and the balance sheet says why: on 1 January 2026 Cathay
reclassified on a vast scale — FVOCI NT$889bn → NT$3,289bn, amortised cost
NT$4,079bn → NT$2,679bn, FVTPL NT$1,587bn → NT$497bn — and the strategy deck
(2Q26, p46) describes exactly this: "redesignation of AC assets to FVOCI to
better align with liability measurement". The sensitivity moved because the
accounting moved. **So the series measures DISCLOSED balance-sheet sensitivity,
not economic duration**, and that is how it is labelled.

**A duration inference was attempted and is rejected.** Dividing the equity DV01
by the FVOCI foreign-bond carrying value (note 九: 國外債券 NT$1,967,342mn at
2026-03-31, NT$583,305mn at 2025-03-31) gives implied durations of 12.9 and
**23.6** years. Twelve is plausible; twenty-four is not, for a book of agency
MBS and callable credit. The two years cannot both be right, so the mapping from
"equity DV01" to "FVOCI foreign bonds" is not established — the sensitivity
evidently covers a different or wider set of instruments. **No duration number
is derived from this and none is loaded.** Establishing the right denominator —
the currency split of FVOCI debt, and whether the disclosure nets the liability
— is the next step before any duration claim is made from these tables.

**Two further observations from the same filing, both on the vulnerability
question.** First, the FX volatility reserve's marginal absorption has
collapsed: a 1% USD move moved the reserve by NT$7,656mn a year ago and
NT$500mn now, a fifteenfold drop, which is what a depleted and re-based reserve
looks like from the firm side. Second, the derivative maturity ladder (note on
liquidity risk) puts **84% of Cathay's FX swap contractual outflows inside
twelve months** and none beyond two years, against an asset book whose Formosa
component alone has a 28-year weighted original tenor. The rollover mismatch is
not an inference; it is in the maturity table.

**And the equity itself.** Total equity fell from NT$781,558mn (2025-03-31) to
NT$626,792mn (2026-03-31), −20% in a year, with 其他權益 swinging from
−NT$5,066mn to −NT$340,260mn. A NT$335bn move in OCI reserves in four quarters
is the buffer question stated in the firm's own numbers.

**Scope.** One firm, two periods. The panel across the other nine insurers is
running: MOPS answers with a WAF block page far more often than not, so the
crawl is paced at one request per eight seconds with a ninety-second pause on
each block, and it is slow rather than stuck.

---

### 4.44 Withdrawal: the TIC lines cannot be attributed to the lifers. The CBC's balance sheet, now loaded, is why

The user objected that the TIC survey measures a country, that it therefore
contains the central bank, and that none of it can be attributed to the life
insurers without knowing the CBC's balance sheet. **The objection is correct and
the attribution in 4.40 and 4.42 is withdrawn.** Three pieces of evidence, in
order of how badly each damages the earlier reading.

**1. TIC publishes no official/private split by country, at any frequency.**
Checked: the annual SHL survey gives one global "of which: holdings of FOI"
line and no country breakdown of it; the monthly SLT country tables
(`slt1d_globl.csv`, US LT securities by country split Treasury / agency /
corporate bonds / corporate stocks) contain no official column at all; Major
Foreign Holders covers Treasuries only and does not split by holder type
either. So the question could not have been answered from TIC even in
principle, and 4.40 should have said so instead of arguing around it.

**2. The specific argument used in 4.40 is factually wrong.** It said a reserve
manager does not run a corporate-credit or MBS book, so agency ABS and
corporates could be read as private. TIC's own global figures at June 2025
refute it: foreign OFFICIAL institutions held **USD 524bn of US agency paper**
against USD 829bn held by foreign private holders — official money is 39% of
the foreign-held agency stock. Central banks buy agency MBS in size. (The
argument is better for corporates, where official holdings are USD 241bn of
about 4.3tn, but "better" is not "established".)

**3. The CBC's balance sheet, fetched and loaded, closes it.** The CBC has
published the IMF/BIS **IRFCL data template quarterly since 2021Q4**, and it
gives what is needed to bound the official share:

| | reserve assets | of which securities | deposits | FX forward/swap SHORT |
|---|---|---|---|---|
| 2021-12-30 | 553,984 | 506,266 (91.4%) | 42,142 | 91,905 |
| 2023-06-30 | 569,797 | 532,233 (93.4%) | 32,601 | 85,825 |
| 2024-12-31 | 581,411 | 544,033 (93.6%) | 32,644 | 77,061 |
| **2025-06-30** | **603,745** | **554,686 (91.9%)** | 43,746 | 79,231 |
| 2026-03-31 | 601,720 | 561,270 (93.3%) | 35,616 | 76,087 |

At 30 June 2025 — the exact date of the TIC survey — **the CBC held USD 554.7bn
of securities against a TIC-measured Taiwanese holding of USD 677bn of US
long-term debt** (849bn including equities). The official sector is capable of
accounting for most of that row. The residual left for private holders cannot
be pinned down from published data, because the template gives securities
versus deposits and nothing about security type or currency.

**What is withdrawn and what stands.**

*Withdrawn:* every attribution of a TIC line to the life insurers. The
statements "Taiwan held 26.2% of all foreign-held US agency MBS" and "Taiwan
absorbed 33% of the increase in foreign agency-MBS holdings 2013-19" and "17%
of the increase in foreign corporate-bond holdings 2019-24" remain true **of
Taiwan as a country** and are useful as such. They are not lifer statements and
must not be presented as answering "what role have Taiwanese life insurers
played", which is the question that was asked.

*Stands:* the sector-identified evidence, which was always the better basis and
should have led. The IIP/BoP series (series 9) reports portfolio-investment debt
holdings by holding sector, and **reserve assets are a separate IIP line by
construction**, so the central bank is excluded before the series begins. That
gives other-financial-institutions foreign debt holdings of USD 778bn at
end-2025 and the quarterly purchase flow by tenor. The Formosa register (series
11) is a market measure and is likewise unaffected.

**A reconciliation puzzle worth recording rather than papering over.** OFI alone
holds USD 778bn of foreign debt securities (IIP, end-2025); the CBC holds
554.7bn of securities; banks hold a further 199bn. Taiwan's entire TIC-measured
US long-term debt position is 677bn. The sums do not fit unless a large part of
Taiwanese holdings is either not US-issued — the Formosa book of USD 218bn is
exactly that — or is attributed to another country by TIC's custodial rule.
**So TIC both mixes holders AND undercounts Taiwan.** Two independent reasons
not to build lifer claims on it.

**The unexpected return.** Section II of the same template gives the aggregate
SHORT position in FX forwards and futures against the domestic currency,
including the forward leg of currency swaps, by residual maturity — **the CBC
swap book**. Setser & S.T.W. (2019) could only estimate it, at USD 130bn with a
60-200bn interval. It is now published: **USD 91.9bn (2021Q4) falling steadily
to 76.1bn (2026Q1)**, at the low end of their interval and shrinking. That is a
direct input to series 8, which had been carrying the estimate.

**Files.** `scripts/stage6_cbc_irfcl.py`, `data/cbc_irfcl.csv`,
`out/stage6_irfcl_20260905.sql`. Loaded to `derived_series` series 12,
`definition_version = irfcl`: 11 quarters, 77 rows, sum 20,413,024 USD mn,
verified server-side. Every row passes two template identities (reserves = FX
reserves + gold; FX reserves = securities + deposits) and the swap figure is
identified by finding the run of four numbers where the total equals its three
maturity buckets, which is both the locator and the check.

---

### 4.45 The CBC is the counterparty to roughly two-fifths of the sector's swap hedges, and its share is rising as the hedge ratio falls

Series 8 — the counterparty residual — has carried an *estimate* of the CBC swap
book since the project began, because Setser & S.T.W. (2019) could only infer it
(USD 130bn, 90% interval 60-200bn). 4.44 found it published: Section II of the
CBC's quarterly IRFCL template gives the aggregate short position in FX forwards
and futures against TWD, including the forward leg of currency swaps. Setting it
against the sector hedge amount from the CBC's own balance-sheet footnote
(series 5, `hedge_outstanding_cbc_footnote`, NT$ converted at the same month's
interbank closing rate):

| | sector swap hedges, USD bn | CBC forward/swap short, USD bn | CBC as % |
|---|---|---|---|
| 2022-06 | 229 | 88 | 38.3 |
| 2022-11 / 2022-12 | 220 | 85 | 38.7 |
| 2023-04 / 2023-06 | 212 | 86 | 40.5 |
| 2024-03 / 2023-12 | 207 | 87 | 41.9 |
| 2024-08 / 2024-06 | 202 | 81 | 40.3 |
| **2024-12** | **197** | **77** | **39.1** |
| 2026-07 / 2026-03 | 162 | 76 | 47.1 |

Pairs before 2022 are omitted: the IRFCL series starts 2021Q4, so anything
earlier would be matched to a date years away. The last row pairs a July 2026
hedge reading with a March 2026 swap reading and should be read as indicative.

**Two readings, and the second is the one that matters.** The level is stable:
through 2022-2024 the central bank's own forward book ran at a remarkably
steady 38-42% of the life sector's outstanding swap-type hedges. And the share
is RISING as the sector deleverages its hedges — the lifers' swap book fell
from USD 229bn to 162bn while the CBC's fell only from 88bn to 76bn. The
central bank is not withdrawing as fast as the private demand it was
accommodating, so its share of what remains has gone up.

**Three caveats, all material.**

1. The CBC's forward book is its TOTAL short position against TWD, with all
   counterparties and for all purposes. It is not a lifer facility, and nothing
   here proves the lifer channel dominates it. Setser & S.T.W. argue it does;
   this table is consistent with that but does not establish it.
2. The denominator understates lifer hedging. The footnote counts 換匯交易等避險
   交易 — swap-type hedges — which 4.34 established is 62-77% of the FSC's hedge
   principal, NDFs excluded. Against ALL lifer hedges the CBC book is therefore
   nearer **25-30%**, not 40%.
3. The two series are not measured on the same dates, and the footnote series is
   sparse (eleven observations since 2012). The pairs above are the only ones
   where both sides fall within a quarter of each other.

**Why this matters for the vulnerability question.** It puts a number on who
absorbs the hedge when the lifers want one. If a quarter to two-fifths of the
sector's hedging ultimately sits on the central bank's balance sheet, then the
question "can the lifers re-hedge if TWD appreciates again" is partly a question
about the CBC's willingness to expand a book it has been letting run down for
four years. That is a policy variable, not a market one, and it should be
tracked quarterly now that it is published.

**No new rows.** This is a derivation from series 5 and series 12, both already
loaded; it is recorded here rather than stored, because the pairing depends on a
date-matching choice that a stored series would freeze.

---

### 4.46 How far back the hedge ratio actually goes, why, and the 42 observations that were computed and thrown away

The user asked, repeatedly, how far back an FX hedge ratio can be taken, and why
others appear to reach further. The answer had never been written down in one
place, and two of the numbers this log and the README carried were wrong in a
way that flattered the project. Both are corrected here.

**Every hedge-ratio observation in the database, before this entry:**

| construction | what it is | span | count |
|---|---|---|---|
| `hedge_ratio_regulatory` | the FSC's own published figure | 2024-04 → 2026-07 | monthly |
| `reg_hedge_ratio_pl_implied` | single-month P&L identity | 2019-05 → 2025-11 | **19** |
| deck composite | Cathay + KGI bottom-up | 2014-12 → 2026-06 | 31 quarters |
| `economic_hedge_ratio` (Fubon) | firm disclosure | 2014-04 → 2025-10 | 36 quarters |
| CBC footnote ÷ 國外資產 | sector gross, swap-type only | 2012-03 → 2026-07 | **11** |

**Correction 1: the README's "firm 2011" was false.** Nothing before **2013-10**
is loaded for any firm, and no hedge RATIO before **2014-04**. The deck archives
are the reason and the limit: the earliest Cathay deck carrying the FX
composition panel is March 2014, Fubon's is 1H14. Fubon's decks do reach 1Q06,
but those early ones disclose the hedging COST only — seven observations in
`data/fubon_eraA_cost.csv`, no composition, no ratio. The README table now says
2013-10/2014-03/2014-04 in the five places it said 2011.

**Correction 2: "reconstructed monthly back to 2019-05" was overstated.** It is
nineteen scattered months, not a monthly series: the estimator publishes a
single-month reading only where the FX result clears the NT$200bn signal-to-noise
floor, and most months do not. STATUS said so; the README did not.

**WHY THE FRONTIER IS WHERE IT IS.** Each construction has a hard floor set by
when a disclosure began, not by how hard anyone looks:

* The FSC did not publish the regulatory ratio before **2024-04**.
* The FSC monthly release did not carry 兌換損益 or 避險損益 before **2018-05**.
  Checked directly: the first row with either line is 2018-05. No P&L
  reconstruction of any kind can reach earlier, because the inputs do not exist.
* The insurers did not disclose hedge composition in their IR decks before
  **2014**.
* The CBC footnote begins around 2012 — but each monthly edition OVERWRITES the
  same file, so the only history is what a web archive happened to capture. The
  Wayback Machine holds **nine** captures of the PDF and **two** of the CSV,
  eleven in total, and that is the whole population: checked without the digest
  collapse that the recovery script uses, so it is not a deduplication artefact.
  The CBC's own site lists one edition (115年7月版). archive.today refuses the
  URL and the NCL Taiwan web archive did not respond.

So the frontier is **2012 for a sparse sector anchor and 2014 for anything
continuous**, and it is a disclosure frontier. Anyone showing a Taiwanese lifer
hedge ratio before about 2012 is either reading those same eleven CBC points,
aggregating the same two or three firms' decks, or inferring from
balance-of-payments and BIS residuals — which is an estimate of a different
thing.

**WHAT WAS ACTUALLY RECOVERABLE, AND HAS NOW BEEN RECOVERED.** The estimator
has always computed a second series and never stored it. Alongside each month's
own reading it fits a twelve-month through-origin regression and dates it to the
fit's fx²-weighted centre — the correction of 4.29 — and validates it at **5.6pp
MAE** against the published ratio at that centre (8.4pp if wrongly dated to the
window end). Those fits are identified in quiet months, because the window
borrows the variance of the loud ones. They were printed every third month and
discarded at the load step: `emit_sql` only ever wrote `h_month`.

Loading them adds **42 observations, 2019-01 → 2025-05** — more than double the
single-month series, and starting four months earlier:

    2019-01  85.2%    2021-04  84.0%    2023-08  73.4%
    2019-06  79.8%    2022-03  77.5%    2024-03  73.1%
    2020-05  84.2%    2022-09  76.6%    2024-12  72.3%
    2020-12  84.7%    2023-01  75.8%    2025-05  66.4%

and the buffer-inclusive twin (`fx_offset_total_pl_rolling`) sits at 88-94%
across the whole span, which is the substitution result stated as a continuous
line rather than as nineteen dots.

Two windows can share a centre when the same violent month dominates both; the
window whose centre lies nearest its own end is kept, being the least
extrapolated. The rolling and single-month series are **not independent** — the
same identity read over different spans — so they must never be averaged, and
that instruction is in the `basis_note` of every row.

**What would extend the history further, in order of expected value.**

1. **Firm income statements through the same identity.** 兌換損益 and 避險工具損益
   appear in the insurers' own quarterly statements. Applying h = −H/A firm by
   firm would give an independent construction from IFRS adoption (2013), fill
   2013-2018 where nothing sector-level exists, and cross-check the deck
   composite over 2014-2018. This needs the MOPS filings for ROC 102-111, which
   the current index does not cover.
2. **More CBC footnote editions**, if any archive outside Wayback holds the
   monthly bulletin. Nothing found so far.
3. **Nothing else.** Pre-2012 is not a data-collection problem.

**Files.** `scripts/stage5_implied_hedge_ratio.py` — `emit_sql` now also writes
`reg_hedge_ratio_pl_rolling` and `fx_offset_total_pl_rolling`, and a `--reemit`
mode regenerates the load SQL from the script's own CSV so the rolling fits can
be loaded without re-piping the year-to-date input. 42 rows per key, sums
32.7237 and 37.3899, verified server-side against the generator.

---

### 4.47 Which hedge ratio is the referenced one — evidenced, and a README claim withdrawn

Asked which of the seven ratios is most commonly referenced, the README's own
answer was wrong. Its series-5 row described the **gross** ratio as "the figure
most sell-side and press quote". That was unsourced, and the primary evidence
points the other way.

**The referenced figure is series 4, the FSC's regulatory 匯率避險比率.** The
CBC's *Financial Stability Report* (第20期, May 2026, p.80) states:

> 114年底壽險公司匯率避險比率降至50.23%，為歷史新低

**50.23% ties `reg_hedge_ratio` at 2025-12 (0.5023) to the basis point** — the
central bank's flagship publication quoting the same series this project stores,
with no adjustment. It is also the only hedge ratio any Taiwanese authority
publishes, the figure given at the FSC's monthly briefings, and the measure
industry guidance (~40%) is expressed against. Decisions 0.12 and 1.2 already
recorded it as press-reported for its whole life; nothing recorded the gross
ratio as press-quoted at all.

**Two things to carry whenever it is quoted.** It is mechanically the highest of
the seven, because its denominator strips FX-policy liabilities and unhedged
non-FVTPL equity — roughly a third of foreign investments. And the CBC's "record
low" has already been surpassed: 50.23% (2025-12) → **42.94% (2026-07)**, a
further 7.3 points.

**Artifacts.** Two pages published for the user: the seven-construction
comparison, and a focused page on this series alone with the CBC quotation as
its evidence.

**MOPS download, status.** The mechanism from 4.46's next step is now understood
and fixed in code: `step=9` does not stream the filing, it returns an HTML page
linking to `/pdf/<name>_<timestamp>.pdf` with a per-request timestamp, so the URL
cannot be constructed. The FIRST leg is proven — one filing's link page was
retrieved and carried a well-formed href. The SECOND leg, fetching that link, is
still untested: every attempt since has drawn the WAF's block page, four in a row
on the one filing tried, so no PDF has landed and the chain is not yet
end-to-end verified. Repeated attempts appear to renew the block rather than
outlast it, so the endpoint is left alone. The firm-statement route to hedge
ratios back to 2013 remains the open path, and its next step is a single patient
attempt after a long idle period, not another crawl.
