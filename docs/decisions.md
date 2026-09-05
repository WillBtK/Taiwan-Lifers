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
