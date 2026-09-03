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
