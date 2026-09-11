#!/usr/bin/env python3
"""The Asia page: Taiwan and Japan side by side.

Builds the JSON behind artifact/asia/index.html from the Taiwan series this
repo already assembles for its own page (imported from
stage8_artifact_blob, so the two pages cannot disagree) and the Japanese
series copied from the JLIM repository into data/japan/ (see its README).

Taiwan side, quarterly 2017-12 to 2026-06 with monthly detail:
  hedge amount   = derivatives-only hedge ratio of the four slide-publishing
                   firms x the regulator's sector foreign investments, so it is
                   on the same measure as the BoJ series (derivatives over
                   total foreign assets, policy-backed assets counted as open);
                   the FSC hedge principal and the CBC footnote are drawn as
                   the published checks on it
  FX assets      = FSC 表17-1 monthly
  flows          = BoP other-financial-institutions net purchases of foreign
                   long-term debt, quarterly, rolling four quarters
Japan side, fiscal-year to March 2025 plus the September 2025 interim:
  BoJ FSR chart III-2-5 for the nine majors: open, currency-swap-hedged,
  FX-swap-hedged, ratio; MOF investor-type flows for life insurers, monthly.
Both in local currency and in US$ at the month's rate; the page switches.

Run: python3 scripts/stage9_asia_blob.py
"""
import csv
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
J = D / "japan"
OUT_DIR = ROOT / "artifact" / "asia"
BLOB = OUT_DIR / "data_blob.json"
TEMPLATE = ROOT / "artifact" / "index.template.html"
PAGE_JS = OUT_DIR / "page.js"
PAGE = OUT_DIR / "index.html"
TITLE = "Two Ways to Stop Hedging"
EYEBROW = "TLFX · Taiwan and Japan life insurers"

_s = importlib.util.spec_from_file_location("s8", ROOT / "scripts" / "stage8_artifact_blob.py")
s8 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(s8)


def rows(p):
    return list(csv.DictReader(open(p, newline="", encoding="utf-8")))


def num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def r1(v, nd=1):
    return None if v is None else round(v, nd)


xm, xq = s8.xm, s8.xq
usdtwd = s8.fx
twd_per_jpy = {r["obs_month"]: float(r["twd_per_unit"]) for r in rows(D / "twd_rates_monthly.csv")
               if r["currency"] == "JPY"}
usdjpy = {m: usdtwd[m] / twd_per_jpy[m] for m in twd_per_jpy if m in usdtwd}

# ------------------------------------------------------------------ Taiwan
deck = {a["d"]: a["deck"] for a in s8.aggregate if a["deck"] is not None}
tw_hedge = []
for e in s8.exposure:
    r = deck.get(e["d"])
    if r is None:
        continue
    hedged = e["fa_ntd_bn"] * r / 100
    tw_hedge.append({"d": e["d"], "x": e["x"], "ratio": r, "fa_ntd_bn": e["fa_ntd_bn"], "fa_usd_bn": e["fa_usd_bn"],
                     "hedged_ntd_bn": r1(hedged, 0), "hedged_usd_bn": r1(hedged / e["usdtwd"], 0),
                     "unhedged_ntd_bn": r1(e["fa_ntd_bn"] - hedged, 0),
                     "unhedged_usd_bn": r1((e["fa_ntd_bn"] - hedged) / e["usdtwd"], 0),
                     "protected_pct": r1(100 - e["unprot_pct"]), "usdtwd": e["usdtwd"]})
tw_principal = [{"m": r["m"], "x": r["x"], "ntd_bn": r1(r["v"] * 1000, 0),
                 "usd_bn": r1(r["v"] * 1000 / usdtwd[r["m"]], 0)} for r in s8.fsc["hedge_principal"]]
tw_footnote = [{"m": c["m"], "x": c["x"], "ntd_bn": r1(c["hedge_tn"] * 1000, 0),
                "usd_bn": r1(c["hedge_tn"] * 1000 / usdtwd[c["m"]], 0), "fa_ntd_bn": r1(c["fa_tn"] * 1000, 0),
                "ratio": c["ratio"]} for c in s8.cbc]
tw_flows, roll = [], []
for r in rows(D / "duration_demand.csv"):
    v = num(r["debt_ofi_long_term_usd_mn"])
    if v is None or r["period"] < "2010Q1":
        continue
    y, q = int(r["period"][:4]), int(r["period"][-1])
    roll.append(v)
    roll = roll[-4:]
    tw_flows.append({"q": r["period"], "x": y + (q - 1) / 4, "usd_bn": r1(v / 1e3),
                     "roll4_usd_bn": r1(sum(roll) / 1e3) if len(roll) == 4 else None})

# ------------------------------------------------------------------- Japan
jp_boj = []
for r in rows(J / "hedge_exposure_sector.csv"):
    fy, per = int(r["fy"]), r["period"]
    m = f"{fy + 1}-03" if per == "annual" else f"{fy}-09"
    rate = usdjpy.get(m)
    tot, opn = float(r["total_foreign_exposure_tn"]), float(r["open_unhedged_tn"])
    cs, fxs = float(r["hedge_currency_swap_tn"]), float(r["hedge_fx_swap_tn"])
    jp_boj.append({"fy": fy, "period": per, "m": m, "x": xm(m), "label": (f"FY{fy}" if per == "annual" else f"Sep {fy}"),
                   "total_tn": tot, "open_tn": opn, "cs_tn": cs, "fxs_tn": fxs, "hedged_tn": r1(cs + fxs, 2),
                   "ratio": float(r["hedge_ratio_line_pct"]), "usdjpy": r1(rate, 1) if rate else None,
                   "total_usd_bn": r1(tot * 1000 / rate, 0) if rate else None,
                   "hedged_usd_bn": r1((cs + fxs) * 1000 / rate, 0) if rate else None,
                   "open_usd_bn": r1(opn * 1000 / rate, 0) if rate else None})
# The statutory rollup JLIM's own page uses: hedge-accounting notional over
# foreign securities, summed over the firms that had reported at each date.
# Two interim points with one or two firms (Sep 2019, Sep 2020) are left out,
# as that page leaves them out, and every point carries its firm count.
agg = {}
for r in rows(J / "hedge_ratio_firm.csv"):
    k = (int(r["fy"]), r["period"])
    a = agg.setdefault(k, [0.0, 0.0, set()])
    a[0] += float(r["hedge_notional_yen_bn"])
    a[1] += float(r["fx_asset_total_yen_bn"])
    a[2].add(r["firm_id"])
jp_rollup = []
for (fy, per), (hn, fa, firms) in sorted(agg.items()):
    if len(firms) < 3:
        continue
    m = f"{fy + 1}-03" if per == "annual" else f"{fy}-09"
    rate = usdjpy.get(m)
    jp_rollup.append({"fy": fy, "period": per, "m": m, "x": xm(m), "label": (f"FY{fy}" if per == "annual" else f"Sep {fy}"),
                      "hedged_tn": r1(hn / 1000, 2), "fa_tn": r1(fa / 1000, 2), "ratio": r1(hn / fa * 100),
                      "n_firms": len(firms), "hedged_usd_bn": r1(hn / rate, 0) if rate else None,
                      "fa_usd_bn": r1(fa / rate, 0) if rate else None})
jp_flows = []
for r in rows(J / "mof_lifer_foreign_bond_flows_monthly.csv"):
    m = r["obs_month"]
    if m < "2010-01":
        continue
    rl = num(r["rolling12_yen_bn"])
    rate = usdjpy.get(m)
    jp_flows.append({"m": m, "x": xm(m), "net_yen_bn": float(r["net_yen_bn"]), "roll12_yen_bn": rl,
                     "roll12_usd_bn": r1(rl / rate, 1) if (rl is not None and rate) else None})
jp_flow_years = {}
for r in rows(J / "mof_lifer_foreign_bond_flows_monthly.csv"):
    y = r["obs_month"][:4]
    jp_flow_years[y] = round(jp_flow_years.get(y, 0) + float(r["net_yen_bn"]) / 1000, 2)
tw_flow_years = {}
for f in tw_flows:
    y = f["q"][:4]
    tw_flow_years[y] = round(tw_flow_years.get(y, 0) + f["usd_bn"], 1)
smr = [r for r in rows(J / "smr_sensitivity.csv") if r["fy"] == "2025" and r["consolidation"] == "non_consolidated"]
jp_net_assets_tn = round(sum(float(r["net_assets_base_yen_mn"]) for r in smr) / 1e6, 1)
jp_net_assets_firms = sorted(r["firm_id"] for r in smr)

# ---------------------------------------------------------------- headline
L = s8.latest
b1, b0 = jp_boj[-1], jp_boj[0]
b_peak = max(jp_boj, key=lambda b: b["ratio"])
b_2021 = next(b for b in jp_boj if b["fy"] == 2021)
t1, t0 = tw_hedge[-1], tw_hedge[0]
jp_last_month = jp_flows[-1]["m"]
jp_cum_2020 = round(sum(v for y, v in jp_flow_years.items() if y >= "2020"), 1)
latest = {
    "tw": {"as_of": t1["d"], "fa_usd_bn": t1["fa_usd_bn"], "fa_ntd_bn": t1["fa_ntd_bn"], "ratio": t1["ratio"],
           "ratio_2017": t0["ratio"], "hedged_usd_bn": t1["hedged_usd_bn"], "unhedged_usd_bn": t1["unhedged_usd_bn"],
           "unhedged_usd_bn_2017": t0["unhedged_usd_bn"], "open_incl_policy_usd_bn": L["unhedged_usd_bn"],
           "open_incl_policy_usd_bn_2017": L["unhedged_usd_bn_2017"],
           "open_incl_policy_pct": L["unprot_pct"], "protected_pct": L["protected_pct"],
           "protected_pct_2017": L["protected_pct_2017"], "reg_first": L["reg_ratio_first"], "reg_last": L["reg_ratio_last"],
           "equity_bn": L["equity_bn"], "equity_m": L["equity_m"], "unhedged_ntd_tn": L["unhedged_ntd_tn"],
           "cbc_swap_bn": L["cbc_swap_last"]["swap_bn"], "cbc_swap_m": L["cbc_swap_last"]["m"],
           "hp_usd_last": L["hp_usd_last"], "book_peak": L["book_peak"], "book_last": L["book_last"],
           "flow_years": tw_flow_years, "cover_last": L["cover"]},
    "jp": {"as_of": b1["m"], "label": b1["label"], "total_tn": b1["total_tn"], "total_usd_bn": b1["total_usd_bn"],
           "open_tn": b1["open_tn"], "open_usd_bn": b1["open_usd_bn"], "hedged_tn": b1["hedged_tn"],
           "hedged_usd_bn": b1["hedged_usd_bn"], "ratio": b1["ratio"], "ratio_peak": b_peak["ratio"],
           "ratio_peak_label": b_peak["label"], "fxs_2021": b_2021["fxs_tn"], "fxs_last": b1["fxs_tn"],
           "cs_2021": b_2021["cs_tn"], "cs_last": b1["cs_tn"], "open_2021_tn": b_2021["open_tn"],
           "open_2021_usd_bn": b_2021["open_usd_bn"], "usdjpy_2021": b_2021["usdjpy"], "usdjpy": b1["usdjpy"],
           "net_assets_tn": jp_net_assets_tn, "net_assets_firms": jp_net_assets_firms,
           "rollup_last": jp_rollup[-1], "rollup_peak": max(jp_rollup, key=lambda r: r["ratio"]),
           "flow_years": jp_flow_years, "flows_last_month": jp_last_month, "cum_since_2020_tn": jp_cum_2020,
           "first": b0},
}

blob = {"meta": {"built": dt.date.today().isoformat(), "tw_sector_last": s8.sec_last, "jp_last": b1["m"],
                 "jp_flows_last": jp_last_month},
        "latest": latest, "usdtwd": {m: v for m, v in usdtwd.items() if m >= "2010-01"},
        "usdjpy": {m: round(v, 2) for m, v in usdjpy.items() if m >= "2010-01"},
        "tw": {"hedge": tw_hedge, "principal": tw_principal, "footnote": tw_footnote, "reg_ratio": s8.fsc["reg_hedge_ratio"],
               "book": [{"m": b["m"], "x": b["x"], "ntd_bn": b["fa_ntd_bn"], "usd_bn": b["fa_usd_bn"]} for b in s8.book_monthly],
               "flows": tw_flows, "exposure": s8.exposure},
        "jp": {"boj": jp_boj, "rollup": jp_rollup, "flows": jp_flows}}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))
    BLOB.write_text(txt, encoding="utf-8")
    print(f"-> {BLOB.relative_to(ROOT)}  ({len(txt) / 1024:.0f} KB)")
    tw, jp = latest["tw"], latest["jp"]
    print(f"   TW {tw['as_of']}: FA US${tw['fa_usd_bn']}bn, derivatives ratio {tw['ratio']}% (2017 {tw['ratio_2017']}%), "
          f"open excl. policies US${tw['unhedged_usd_bn']}bn; incl. policy backing US${tw['open_incl_policy_usd_bn']}bn")
    print(f"   JP {jp['label']}: FA ¥{jp['total_tn']}tn = US${jp['total_usd_bn']}bn at {jp['usdjpy']}, ratio {jp['ratio']}% "
          f"(peak {jp['ratio_peak']}% {jp['ratio_peak_label']}), open ¥{jp['open_tn']}tn = US${jp['open_usd_bn']}bn "
          f"(FY2021 US${jp['open_2021_usd_bn']}bn); FX-swap hedged ¥{jp['fxs_2021']}tn -> ¥{jp['fxs_last']}tn")
    print(f"   JP flows since 2020: ¥{jp['cum_since_2020_tn']}tn; net assets FY2025 ¥{jp['net_assets_tn']}tn ({len(jp['net_assets_firms'])} firms)")
    print(f"   TW flows by year US$bn: { {k: v for k, v in tw['flow_years'].items() if k >= '2022'} }")
    if TEMPLATE.exists() and PAGE_JS.exists():
        page = TEMPLATE.read_text(encoding="utf-8")
        page = page.replace("/*DATA_BLOB*/", txt.replace("</", "<\\/"))
        page = page.replace("/*PAGE_SCRIPT*/", PAGE_JS.read_text(encoding="utf-8"))
        page = page.replace("{{TITLE}}", TITLE).replace("{{EYEBROW}}", EYEBROW)
        PAGE.write_text(page, encoding="utf-8")
        print(f"-> {PAGE.relative_to(ROOT)}  ({PAGE.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
