# Japanese life-insurer series used by the Asia page

Copied unchanged from the sibling repository `WillBtK/Japan-Lifers` (JLIM), commit
`f84873c`, on 2026-09-11. That repository is the source of record for their
construction and provenance; nothing here is re-derived.

| file | what it is | origin in JLIM |
|---|---|---|
| `hedge_exposure_sector.csv` | BoJ Financial System Report chart III-2-5, 生命保険会社の為替ヘッジ比率: the nine major firms' general-account foreign exposure split into open, currency-swap-hedged and FX-swap-hedged, in yen trillions, with the hedge ratio, FY2011 to the September 2025 interim. Digitised from the chart's vector geometry; the two independently drawn series (bars and line) cross-check within 0.1pt. The BoJ's own note says the open segment includes assets backing foreign-currency insurance, so the ratio is derivatives over total foreign assets with policy-backed assets counted as open. | `build/boj_hedge_chart.py`, source `raw/boj_fsr/2025/other/fsr260421a.pdf` p.29 |
| `hedge_ratio_firm.csv` | The accounting hedge ratio per firm, fiscal year and period: notional of currency derivatives under hedge accounting over the book value of foreign securities, from statutory footnotes, FY2008 to the September 2025 interim, 185 rows. Summed to the sector it is the series in JLIM's published page (artifact 227bdb8a); the panel is a subset of ten firms in any period and is never scaled up. The by-currency table was checked and not copied: JLIM found it structurally unreliable (Sumitomo and Japan Post never itemise by currency; Dai-ichi and Meiji Yasuda drop out of currency detail after FY2022 and FY2023). | `build/hedge_ratio_firm.py` |
| `smr_sensitivity.csv` | Statutory net assets (and solvency-margin sensitivities) per firm, non-consolidated, from the disclosure booklets; used here only for the FY2025 net-asset total that scales the open position. | `build/build_smr_panel.py` |
| `esr_anchors.csv` | Firms' own disclosed economic solvency ratio sensitivities at March 2026: ESR change in points for ±50bp in domestic and foreign rates (Asahi group internal basis; Nippon internal model, preliminary). Used for the direction and size of the rate legs in the scenario table. | `build/esr_anchors.py` |
| `mof_lifer_foreign_bond_flows_monthly.csv` | Not from JLIM: MOF, purchases and sales of foreign long-term debt securities by resident investor type, 生命保険会社 net, monthly from 2005. Built by `scripts/stage9_mof_lifer_flows.py` in this repo. | — |

Fiscal-year convention: JLIM's `fy` is the Japanese fiscal year, so `fy = 2024, annual`
is the position at 31 March 2025, and `fy = 2025, interim` is 30 September 2025.
