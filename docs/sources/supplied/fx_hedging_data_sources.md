<!-- Supplied by the user 2026-09-05; verified link by link at decisions 4.36.
     Text extracted verbatim from the .docx, hyperlinks inlined as [LINK: url].
     Verification summary: 11/14 links resolve; the Shin Kong notional-principal
     claim is exact and overturns 4.26; the Cathay statement-notional paragraph
     overstates (that figure is hedge-accounting only). -->

## Taiwanese Life Insurers: Historical FX Hedging and Liability Data Sources
Validated public sources for FX hedge notionals, total assets, and domestic/foreign-currency liabilities
Bottom line. There are usable public sources, but there is not one public database containing all three variables at company level. The source map below separates clean regulator datasets from variables that require extraction from insurer financial statements or investor presentations.
Variable
Best validated source
Frequency
Company level?
Historical?
Assessment
Total assets
FSC Insurance Bureau / company financial statements
Quarterly
Yes
Yes
Clean
Total assets
Central Bank of Taiwan life-insurer balance sheet
Monthly
No, industry aggregate
May 1987 onward
Very clean
FX hedge notional
Quarterly reviewed/audited insurer financial statements
Quarterly
Yes
Yes
Usable; requires extraction
Foreign-currency financial liabilities
Currency-risk note in quarterly financial statements
Quarterly
Yes
Yes
Clean, but narrower than total liabilities
Foreign-currency policy liabilities
Insurer/FHC quarterly investor presentations
Quarterly
Yes for major firms
Varies
Very useful but not universal
Complete domestic/foreign-currency split of all liabilities
No standard public panel verified
—
—
—
Not verified as a standard public series
## 1. Total assets: straightforward
Industry aggregate. The Central Bank of the Republic of China (Taiwan) publishes dataset 10767, “Life Insurance Company Balance Sheet Statistics” (人壽保險公司資產負債統計表). It contains monthly data from May 1987, including total assets, and is downloadable as CSV.
CBC/Data.gov life-insurer balance-sheet dataset 10767 [LINK: https://data.gov.tw/dataset/10767]
Direct CBC monthly CSV (EF67M01) [LINK: https://www.cbc.gov.tw/public/data/OpenData/%E7%B6%93%E7%A0%94%E8%99%95/EF67M01.csv]
Individual companies. The FSC Insurance Bureau publishes dataset 7190, “Insurance Company Financial Statement Summary” (保險公司財務報表摘要). The resource contains insurer name, reporting season and total assets (資產總額, thousand NT dollars), along with total liabilities and equity. The official machine-readable resource is JSON.
FSC/Data.gov company financial-statement summary, dataset 7190 [LINK: https://data.gov.tw/dataset/7190]
FSC Insurance Bureau JSON resource [LINK: https://ins-info.ib.gov.tw/opendata/json-06021011.aspx]
Caution. The JSON endpoint appears designed principally as a current reporting-period resource, so I would not rely on it alone for a historical company panel. Historical company series should instead be taken from the quarterly financial-statement archives. Cathay Life, for example, still exposes individual quarterly reviewed statements such as its 2021 Q1 filing.
Example: Cathay Life 2021 Q1 financial statement [LINK: https://www.cathayholdings.com/holdings/-/media/bae2b599dd3149989bccae42451fcec4.pdf?sc_lang=zh-tw]
## 2. FX hedge notionals: quarterly financial statements are the best source
The important finding is that at least some Taiwanese insurers disclose the actual notional principal of FX hedges, rather than only derivative fair values or hedge-accounting balances.
Shin Kong Life validation. Its 2021 Q1 filing explicitly states that Shin Kong Life and subsidiaries use FX forwards and FX swaps to mitigate FX exposure and reports their aggregate notional principal (名目本金):
31 March 2020: NT$1.047454tn
31 December 2020: NT$0.999262tn
31 March 2021: NT$1.030311tn
Shin Kong 2021 Q1 financial statement PDF [LINK: https://www.ir-cloud.com/taiwan/2888/financial/85/CH/SKFH110Q1.pdf]
The same disclosure persists in later filings. Its 2024 Q2 report gives:
30 June 2023: NT$1.207540tn
31 December 2023: NT$1.369091tn
30 June 2024: NT$1.398984tn
Shin Kong 2024 Q2 financial statement PDF [LINK: https://www.irpro.co/2888/financial/111/CH/20240904152810-2.pdf]
This is strong evidence that a genuine quarterly time series can be constructed. Each interim report also provides comparison periods, which makes backfilling more efficient.
Cathay Life also provides usable historical depth. Its quarterly financial statements contain notional amounts and maturity buckets for FX-forward hedging instruments at multiple comparison dates.
Cathay Life 2024 Q1 financial statement PDF [LINK: https://www.cathayholdings.com/holdings/-/media/e64eb94b29ab46b7bf58715903a64ca5.pdf?sc_lang=zh-tw]
Cathay Life 2024 Q2 financial statement PDF [LINK: https://www.cathaylife.com.tw/cathaylife/-/media/9269373d79d547c986a3fa68ce972414.pdf?sc_lang=zh-tw]
Extraction warning. Do not simply take the table headed “hedging instruments” (避險工具) for every insurer. Under IFRS this can mean only derivatives formally designated for hedge accounting. Taiwanese life insurers also use FX swaps, NDFs and forwards held at FVTPL as economic hedges. Shin Kong is unusually useful because its disclosure identifies derivatives actually used to mitigate FX exposure. For other firms, inspect both the derivatives and currency-risk notes and identify contracts comprising the insurer’s “traditional hedge”.
Regulatory definition. Taiwan’s FSC defines traditional FX hedging as FX/TWD forwards, FX swaps, cross-currency swaps and NDFs, with the relevant quantity being their notional principal.
FSC-commissioned study on FX-risk management and supervision [LINK: https://www.scribd.com/document/997861501/%E5%BC%B7%E5%8C%96%E4%BF%9D%E9%9A%AA%E6%A5%AD%E5%9C%8B%E5%A4%96%E6%8A%95%E8%B3%87%E4%B9%8B%E5%8C%AF%E7%8E%87%E9%A2%A8%E9%9A%AA%E7%AE%A1%E7%90%86%E8%88%87%E7%9B%A3%E7%90%86%E6%A9%9F%E5%88%B6%E4%B9%8B%E7%A0%94%E7%A9%B6]
## 3. Currency liabilities: two different variables
This distinction matters because IFRS “foreign-currency financial liabilities” are not the same thing as the insurer’s foreign-currency policy liabilities or a complete currency split of all liabilities.
## A. Foreign-currency financial liabilities
Quarterly statements commonly contain a section called 外幣金融資產及負債之匯率資訊 (“exchange-rate information on foreign-currency financial assets and liabilities”). Shin Kong’s 2021 Q1 filing explicitly contains this section and breaks foreign-currency financial liabilities down by currency, distinguishing monetary and non-monetary items and giving both original-currency amounts and NT-dollar equivalents. Its 2024 Q2 filing does the same.
Shin Kong 2021 Q1 financial statement [LINK: https://www.ir-cloud.com/taiwan/2888/financial/85/CH/SKFH110Q1.pdf]
Shin Kong 2024 Q2 financial statement [LINK: https://www.irpro.co/2888/financial/111/CH/20240904152810-2.pdf]
Important limitation. This is not a complete currency split of the insurer’s liabilities. Insurance-contract reserves are not simply included in the IFRS financial-liability currency-risk table. Therefore “total liabilities minus foreign-currency financial liabilities” should not be treated as domestic-currency liabilities.
## B. Foreign-currency policy liabilities
For assessing Taiwanese insurers’ structural FX mismatch, this is probably the more relevant variable: 外幣保單負債, i.e. liabilities generated by foreign-currency insurance policies. The FSC explicitly recognises this concept in its regulatory FX framework. Foreign-currency non-investment-linked insurance liabilities are deducted from foreign assets when determining the amount genuinely exposed to FX risk.
FSC-commissioned study on FX-risk management and supervision [LINK: https://www.scribd.com/document/997861501/%E5%BC%B7%E5%8C%96%E4%BF%9D%E9%9A%AA%E6%A5%AD%E5%9C%8B%E5%A4%96%E6%8A%95%E8%B3%87%E4%B9%8B%E5%8C%AF%E7%8E%87%E9%A2%A8%E9%9A%AA%E7%AE%A1%E7%90%86%E8%88%87%E7%9B%A3%E7%90%86%E6%A9%9F%E5%88%B6%E4%B9%8B%E7%A0%94%E7%A9%B6]
Cathay Life is particularly useful. Its quarterly investor presentations report foreign assets and foreign-currency policy liabilities as a percentage of foreign assets, allowing the liability notional to be reconstructed directly:
Period
Foreign assets
FX policy liabilities / foreign assets
Source
FY2022
NT$5.11tn
32%
PDF [LINK: https://www.cathayholdings.com/holdings/-/media/90a813863a24426bb8c43bab421cc897.pdf?sc_lang=zh-tw]
2Q2023
NT$5.26tn
32%
PDF [LINK: https://www.ir-cloud.com/taiwan/2882/events/465/CH/Cathay%20FHC_2Q23_NDR_Chinese_Vupload_CHFnHY75AjBF.pdf]
3Q2023
NT$5.36tn
32%
PDF [LINK: https://www.cathayholdings.com/holdings/-/media/f268807d96174525b0dfe6fef0be1c55.pdf?sc_lang=zh-tw]
2Q2024
NT$5.53tn
31%
PDF [LINK: https://www.cathayholdings.com/holdings/-/media/da506f05db7c4663b3ea288da8f0bf7d.pdf?sc_lang=zh-tw]
3Q2024
NT$5.54tn
31%
PDF [LINK: https://www.cathayholdings.com/holdings/-/media/d534bedad3244243bcf01603ffb97729.pdf?sc_lang=zh-tw]
FY2024
NT$5.60tn
31%
PDF [LINK: https://www.cathayholdings.com/holdings/-/media/12980e61fd384a2b97c013df921c5b5a.pdf?sc_lang=zh-tw]
3Q2025
NT$5.42tn
31%
PDF [LINK: https://www.cathayholdings.com/holdings/-/media/63027f62d43040bbaf4ff910f2e4d5ba.pdf?sc_lang=zh-tw]
1Q2026
NT$5.44tn
26%
PDF [LINK: https://www.cathayholdings.com/holdings/-/media/774585871f6541e8a9d8d2c0f6ed10ec.pdf?sc_lang=zh-tw]
Example reconstruction. FY2022 foreign-currency policy liabilities are approximately NT$1.64tn (= NT$5.11tn × 32%).
Fubon also reports this metric. Its 1Q2026 presentation reports foreign-currency policy liabilities as 22.4% of foreign financial assets, alongside FX swap/NDF and unhedged/proxy components.
Fubon 1Q2026 investor presentation [LINK: https://www.irpro.co/2881/events/575/EN/20260525150603-1.pdf]
## 4. Recommended construction of a company-level quarterly panel
Quarterly statutory financial statements: Canonical source for total assets, total liabilities, FX forward/FX swap/NDF/CCS notionals, and foreign-currency financial liabilities.
Quarterly FHC/insurer investor presentations: Source for foreign-currency policy liabilities, foreign assets, and economically hedged versus proxy/open FX exposure.
FSC Insurance Public Information Observation Station and insurer disclosure archives: Use as the master historical archive rather than relying only on the current Data.gov JSON snapshot. An FSC-commissioned study constructed insurer panels from the Observation Station for 2013–2016, demonstrating historical company-by-company availability.
FSC-commissioned study using insurer-level historical data [LINK: https://www.scribd.com/document/997861501/%E5%BC%B7%E5%8C%96%E4%BF%9D%E9%9A%AA%E6%A5%AD%E5%9C%8B%E5%A4%96%E6%8A%95%E8%B3%87%E4%B9%8B%E5%8C%AF%E7%8E%87%E9%A2%A8%E9%9A%AA%E7%AE%A1%E7%90%86%E8%88%87%E7%9B%A3%E7%90%86%E6%A9%9F%E5%88%B6%E4%B9%8B%E7%A0%94%E7%A9%B6]
Initial company set. Cathay Life, Fubon Life, Shin Kong/Taishin Life, Taiwan Life, Nan Shan and KGI Life. Shin Kong gives the cleanest proof that exact hedge notional is extractable; Cathay gives the cleanest proof that quarterly foreign-policy-liability exposure is reconstructible.
What I have not validated. I have not found a single regulator download containing a historical company-level series of traditional FX hedge notional plus foreign-currency policy liabilities. The FSC receives the underlying information, but I would not represent a public downloadable panel containing both fields as existing without further evidence.