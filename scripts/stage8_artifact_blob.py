#!/usr/bin/env python3
"""Assemble the single JSON payload behind the TLFX artifact page.

The page answers one question — how large is the life sector's unhedged
foreign-currency exposure, and is the sector cutting the book or carrying the
risk — and everything it draws comes from this blob. Nothing on the page is
typed by hand; every number is traceable back through this script to a file in
data/, and from there to a source URL.

Series assembled here:
  exposure     quarterly, 2017-12 to 2026-06: sector foreign investments in
               NT$ and US$, the unprotected share (naked + equity) of the
               firms that disclose it, and the unhedged US$ amount that share
               implies for the whole book
  composition  the four-bucket split (hedged / FX policy / naked / equity),
               sector-weighted over the firms that draw the pie
  aggregate    the two derivatives-only hedge ratios (mixed, deck-only)
  firm_ratio   each firm's contribution to the aggregate, by quarter
  book_monthly the sector's foreign investments every month, NT$ and US$
  release      equity, FX reserve, FX loss and swap cost from the FSC monthly
  fsc          the regulator's own 2024-26 briefing numbers
  cbc          the central bank's 2012-26 hedge-ratio footnote
  cost         forward-implied 3-month hedge cost, and Fubon's recurring cost
  jpm          the 55-cell benchmark grid against our own reading
  paired       accounts notional vs slide, the 16 rows behind the ceiling claim
  tic          Taiwan's US long-term securities holdings by class
  balance      CBC balance sheet: foreign assets and equity, monthly

Run: python3 scripts/stage8_artifact_blob.py
Writes artifact/data_blob.json and, if artifact/index.template.html exists,
artifact/index.html with the blob spliced in.
"""
import collections
import csv
import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
OUT_DIR = ROOT / "artifact"
BLOB = OUT_DIR / "data_blob.json"
TEMPLATE = OUT_DIR / "index.template.html"
PAGE = OUT_DIR / "index.html"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ag = load("stage6_aggregate_hedge_ratio")
mc = load("stage7_measure_check")


def rows(name):
    return list(csv.DictReader(open(D / name, newline="", encoding="utf-8")))


def num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def xq(d):
    """Quarter-end date -> year + (q-1)/4."""
    y, m = int(d[:4]), int(d[5:7])
    return y + ((m - 1) // 3) / 4


def xm(m):
    """'YYYY-MM' -> year + (month-1)/12."""
    return int(m[:4]) + (int(m[5:7]) - 1) / 12


def r1(v, nd=1):
    return None if v is None else round(v, nd)


# ----------------------------------------------------------------- sector
sec = ag.sector_bn()                                     # NT$bn by 'YYYY-MM'
fx = {r["obs_month"]: float(r["usdtwd"]) for r in rows("usdtwd_monthly.csv")}
fi = ag.firm_bn()
share = {e: {m: v / sec[m] for m, v in d.items() if m in sec} for e, d in fi.items()}
sec_last = max(sec)
QUARTERS = ag.quarters("2017-12-31", "2026-06-30")


def level(d):
    """Sector foreign investments at a quarter-end, NT$bn (held one quarter
    past the last monthly print, as the aggregate does)."""
    m = d[:7]
    if m in sec:
        return sec[m]
    return ag.interp(sec, d)


def usd(d):
    return fx.get(d[:7])


# --------------------------------------------- unprotected share, per firm
unp = collections.defaultdict(dict)   # naked + equity
pie = collections.defaultdict(dict)   # full four-bucket pies (deck firms)
for r in rows("deck_pie.csv"):
    e, d = r["entity_id"], r["as_of"]
    pie[e][d] = {k: float(r[k]) for k in ("hedged_pct", "fx_policy_pct", "naked_pct", "equity_pct")}
    pie[e][d]["at_risk"] = num(r.get("cs_ndf_pct_of_risk"))
    unp[e][d] = pie[e][d]["naked_pct"] + pie[e][d]["equity_pct"]
fubon_b = {}
for r in rows("hedging_structure.csv"):
    if r["entity_id"] == "fubon_life" and r["proxy_naked_pct"] and r["equity_fund_pct"]:
        unp["fubon_life"][r["as_of"]] = float(r["proxy_naked_pct"]) + float(r["equity_fund_pct"])
        fubon_b[r["as_of"]] = {"protected": 100 - unp["fubon_life"][r["as_of"]],
                               "naked": float(r["proxy_naked_pct"]),
                               "equity": float(r["equity_fund_pct"])}

exposure = []
for d in QUARTERS:
    lvl, rate = level(d), usd(d)
    if not lvl or not rate:
        continue
    n = den = wsum = 0.0
    firms = []
    for e in unp:
        w = ag.interp(share.get(e, {}), d)
        u = ag.interp(unp[e], d, 4)
        if w is None or u is None:
            continue
        wsum += w * u
        den += w
        n += 1
        firms.append(ag.NAME.get(e, e))
    if not den:
        continue
    u = wsum / den
    exposure.append({
        "d": d, "x": xq(d),
        "fa_ntd_bn": r1(lvl, 0), "usdtwd": rate, "fa_usd_bn": r1(lvl / rate, 0),
        "unprot_pct": r1(u), "unhedged_usd_bn": r1(lvl * u / 100 / rate, 0),
        "unhedged_ntd_tn": r1(lvl * u / 100 / 1000, 2),
        "n": int(n), "cover": r1(den * 100, 0), "firms": firms,
    })

# --------------------------------------------- four-bucket composition
composition = []
for d in QUARTERS:
    acc = collections.defaultdict(float)
    den = 0.0
    n = 0
    for e in pie:
        w = ag.interp(share.get(e, {}), d)
        if w is None:
            continue
        vals = {}
        ok = True
        for k in ("hedged_pct", "fx_policy_pct", "naked_pct", "equity_pct"):
            v = ag.interp({dd: p[k] for dd, p in pie[e].items()}, d, 4)
            if v is None:
                ok = False
                break
            vals[k] = v
        if not ok:
            continue
        for k, v in vals.items():
            acc[k] += w * v
        den += w
        n += 1
    if not den:
        continue
    composition.append({
        "d": d, "x": xq(d), "n": n, "cover": r1(den * 100, 0),
        "hedged": r1(acc["hedged_pct"] / den), "policy": r1(acc["fx_policy_pct"] / den),
        "naked": r1(acc["naked_pct"] / den), "equity": r1(acc["equity_pct"] / den),
    })

# --------------------------------------------- aggregates and firm lines
FIRM_RE = re.compile(r"([^=;]+)=([\d.]+)@w([\d.]+)")
mixed = {r["as_of"]: r for r in rows("aggregate_hedge_ratio.csv")}
deck = {r["as_of"]: r for r in rows("aggregate_hedge_ratio_deck_only.csv")}
aggregate = []
firm_ratio = collections.defaultdict(list)
for d in sorted(set(mixed) | set(deck)):
    m, k = mixed.get(d), deck.get(d)
    aggregate.append({
        "d": d, "x": xq(d),
        "mixed": r1(num(m and m["hedge_ratio"]) and num(m["hedge_ratio"]) * 100),
        "mixed_cov": r1(num(m and m["coverage_share"]) and num(m["coverage_share"]) * 100, 0),
        "mixed_n": int(m["n_firms"]) if m else None,
        "deck": r1(num(k and k["hedge_ratio"]) and num(k["hedge_ratio"]) * 100),
        "deck_cov": r1(num(k and k["coverage_share"]) and num(k["coverage_share"]) * 100, 0),
        "deck_n": int(k["n_firms"]) if k else None,
    })
    if m:
        for name, v, w in FIRM_RE.findall(m["firms"]):
            firm_ratio[name.strip()].append([xq(d), round(float(v) * 100, 1), round(float(w) * 100, 1)])

SLIDE = {"Cathay", "KGI", "Shin Kong", "Taiwan Life"}
MEASURE = {n: ("slide" if n in SLIDE else "ceiling") for n in firm_ratio}
MEASURE["Fubon"] = "ceiling"

# --------------------------------------------- monthly book
book_monthly = []
for r in rows("ib_indicators_monthly.csv"):
    m = r["obs_month"][:7]
    fa = num(r["foreign_investments"])
    ta = num(r["total_assets"])
    if fa is None or m not in fx:
        continue
    book_monthly.append({
        "m": m, "x": xm(m), "fa_ntd_bn": r1(fa / 1e3, 0), "usdtwd": fx[m],
        "fa_usd_bn": r1(fa / 1e3 / fx[m], 0),
        "total_ntd_bn": r1(ta / 1e3, 0) if ta else None,
        "foreign_share": r1(fa / ta * 100) if ta else None,
    })

# --------------------------------------------- FSC monthly release
release = []
for r in rows("sector_monthly_release.csv"):
    m = r["obs_month"][:7]
    release.append({
        "m": m, "x": xm(m),
        "equity_bn": r1(num(r["owners_equity"]) and num(r["owners_equity"]) / 1e3, 0),
        "reserve_bn": r1(num(r["fx_reserve_total"]) and num(r["fx_reserve_total"]) / 1e3, 0),
        "fx_gl_ytd_bn": r1(num(r["fx_gain_loss"]) and num(r["fx_gain_loss"]) / 1e3, 0),
        "hedge_gl_ytd_bn": r1(num(r["hedging_gain_loss"]) and num(r["hedging_gain_loss"]) / 1e3, 0),
        "combined_ytd_bn": r1(num(r["fx_combined_effect"]) and num(r["fx_combined_effect"]) / 1e3, 0),
        "swap_cost_ytd_bn": r1(num(r["hedging_swap_cost"]) and num(r["hedging_swap_cost"]) / 1e3, 0),
        "twd_ytd_pct": num(r["twd_change_ytd_pct"]),
    })

# --------------------------------------------- the regulator's briefing series
fsc = collections.defaultdict(list)
for r in rows("derived_series_sector.csv"):
    m = r["obs_date"][:7]
    v = float(r["value"])
    key = r["series_key"]
    if key in ("reg_hedge_ratio", "reg_hedge_ratio_effective", "gross_hedge_ratio"):
        v = v * 100
    elif key in ("net_open_fx", "reg_denominator", "hedge_principal"):
        v = v / 1e6            # NT$mn -> NT$tn
    elif key == "buffer_total":
        v = v / 1e3            # NT$mn -> NT$bn
    fsc[key].append({"m": m, "x": xm(m), "v": round(v, 3), "basis": r["basis"]})

# --------------------------------------------- CBC footnote and balance sheet
cbc = [{"m": r["obs_month"][:7], "x": xm(r["obs_month"][:7]),
        "ratio": round(float(r["ratio"]) * 100, 1),
        "hedge_tn": r1(float(r["hedge_outstanding_ntd_mn"]) / 1e6, 2),
        "fa_tn": r1(float(r["foreign_assets_ntd_mn"]) / 1e6, 2)}
       for r in rows("cbc_hedge_footnote.csv")]
balance = collections.defaultdict(dict)
for r in rows("sector_balance_sheet.csv"):
    if r["line_code"] in ("foreign_assets", "equity"):
        balance[r["obs_month"][:7]][r["line_code"]] = r1(float(r["value_ntd_mn"]) / 1e3, 0)
balance = [{"m": m, "x": xm(m), **v} for m, v in sorted(balance.items())]

# --------------------------------------------- hedge cost
cost_market = []
for r in rows("fx_hedge_cost_market.csv"):
    m = r["obs_month"][:7]
    v = num(r.get("cost_mid_ann_pct_90"))
    if v is not None and m >= "2010-01":
        cost_market.append([xm(m), round(v, 2)])
fubon_cost = {}
for r in rows("fubon_recurring_cost.csv"):
    d = ag.qend(r["period"])
    if not d or not r["recurring_bps"]:
        continue
    x = xq(d)
    # one point per quarter: a single-quarter label beats a cumulative one
    # (1H26 and 2Q26 end in the same quarter; the quarter is the finer read)
    if x in fubon_cost and not re.match(r"\dQ", r["period"]):
        continue
    fubon_cost[x] = [x, -float(r["recurring_bps"]), r["period"]]
fubon_cost = [fubon_cost[k] for k in sorted(fubon_cost)]

# --------------------------------------------- JPM benchmark grid
jpm = []
for r in rows("benchmark_jpm_hedging_structure.csv"):
    e, d = r["entity_id"], r["as_of"]
    ours = pie.get(e, {}).get(d)
    fb = fubon_b.get(d) if e == "fubon_life" else None
    jh, jp = num(r["traditional_hedge_pct"]), num(r["fx_policy_pct"])
    # group by entity, not by the workbook's label: it calls KGI Life "China
    # Life" before the 2023 rename, which would split one firm into two rows
    jpm.append({
        "firm": ag.NAME.get(e, r["firm_label"]), "d": d, "x": xq(d),
        "jpm_hedge": jh, "jpm_policy": jp,
        "jpm_protected": r1(jh + jp) if jh is not None and jp is not None else None,
        "ours_hedge": ours["hedged_pct"] if ours else None,
        "ours_policy": ours["fx_policy_pct"] if ours else None,
        "ours_protected": (r1(ours["hedged_pct"] + ours["fx_policy_pct"]) if ours
                           else r1(fb["protected"]) if fb else None),
    })
jpm.sort(key=lambda r: (r["firm"], r["d"]))

# --------------------------------------------- accounts vs slide
paired = [{"firm": n, "d": d, "accounts": round(a, 1), "slide": round(s, 1),
           "ratio": round(a / s, 2)} for n, d, a, s in mc.paired()]

# --------------------------------------------- TIC
tic = []
for r in rows("tic_taiwan_holdings.csv"):
    g = lambda k: (num(r[k]) or 0) / 1e3
    tic.append({"year": int(r["survey_year"]), "total": r1(g("lt_total"), 0),
                "treasuries": r1(g("treasuries"), 0),
                "agency": r1(g("agency_nonabs") + g("agency_abs"), 0),
                "corporate": r1(g("corp_nonabs") + g("corp_abs"), 0),
                "equities": r1(g("equities"), 0)})

# --------------------------------------------- the central bank
# The IRFCL template's section II short forward position (the forward leg of
# the CBC's currency swaps) beside the two measures of the lifers' hedge book,
# all in US$bn at the month's rate: the FSC's hedge principal (all traditional
# hedges, from the briefing) and the CBC's own balance-sheet footnote (swap-type
# hedges only, so NDFs excluded). Decision 4.45 for the reading.
irfcl = []
for r in rows("cbc_irfcl.csv"):
    m = r["obs_date"][:7]
    irfcl.append({"m": m, "x": xm(m), "reserves_bn": r1(float(r["fx_reserves"]) / 1e3, 1),
                  "securities_bn": r1(float(r["reserve_securities"]) / 1e3, 1),
                  "swap_bn": r1(float(r["fx_forward_short_total"]) / 1e3, 1)})
fx_reserves = []
for r in rows("cbc_fx_reserves_monthly.csv"):
    m = r["obs_month"]
    if m >= "2012-01":
        fx_reserves.append({"m": m, "x": xm(m), "v": r1(float(r["fx_reserves_usd_mn"]) / 1e3, 1)})
hp_usd = {r["obs_date"][:7]: float(r["value"]) / 1e3 / fx[r["obs_date"][:7]]
          for r in rows("derived_series_sector.csv") if r["series_key"] == "hedge_principal"}
fn_usd = {r["obs_month"][:7]: float(r["hedge_outstanding_ntd_mn"]) / 1e3 / fx[r["obs_month"][:7]]
          for r in rows("cbc_hedge_footnote.csv")}


def nearest(d, m, within):
    best = None
    for k in d:
        gap = abs(mo_(k) - mo_(m))
        if gap <= within and (best is None or gap < best[0]):
            best = (gap, k)
    return best[1] if best else None


def mo_(m):
    return int(m[:4]) * 12 + int(m[5:7])


cbc_share = []
for q in irfcl:
    fm = nearest(fn_usd, q["m"], 3)
    hm = nearest(hp_usd, q["m"], 1)
    if fm is None and hm is None:
        continue
    cbc_share.append({
        "m": q["m"], "swap_bn": q["swap_bn"],
        "fsc_m": hm, "fsc_bn": r1(hp_usd[hm], 0) if hm else None,
        "fsc_share": r1(q["swap_bn"] / hp_usd[hm] * 100, 0) if hm else None,
        "fn_m": fm, "fn_bn": r1(fn_usd[fm], 0) if fm else None,
        "fn_share": r1(q["swap_bn"] / fn_usd[fm] * 100, 0) if fm else None,
        "indicative": False,
    })
# the latest hedge readings sit after the latest published quarter of the
# template; pair them with it and say so
last_q = irfcl[-1]
hm, fm = max(hp_usd), max(fn_usd)
if mo_(hm) > mo_(last_q["m"]):
    cbc_share.append({
        "m": hm, "swap_bn": last_q["swap_bn"],
        "fsc_m": hm, "fsc_bn": r1(hp_usd[hm], 0), "fsc_share": r1(last_q["swap_bn"] / hp_usd[hm] * 100, 0),
        "fn_m": fm, "fn_bn": r1(fn_usd[fm], 0), "fn_share": r1(last_q["swap_bn"] / fn_usd[fm] * 100, 0),
        "indicative": True, "swap_m": last_q["m"],
    })

# --------------------------------------------- firm table, latest
firms_latest = []
for name, pts in firm_ratio.items():
    x, v, w = pts[-1]
    firms_latest.append({"firm": name, "x": x, "ratio": v, "weight": w,
                         "measure": MEASURE[name]})
firms_latest.sort(key=lambda r: -r["weight"])
for f in firms_latest:
    eid = next((k for k, v in ag.NAME.items() if v == f["firm"]), None)
    p = pie.get(eid)
    if p:
        d = max(p)
        f["pie_d"] = d
        f["pie"] = {k: p[d][k] for k in ("hedged_pct", "fx_policy_pct", "naked_pct", "equity_pct")}
    if eid == "fubon_life" and fubon_b:
        d = max(fubon_b)
        f["pie_d"] = d
        f["fubon_b"] = fubon_b[d]

# --------------------------------------------- headline values
last_exp = exposure[-1]
first_exp = exposure[0]
yr_ago = next(e for e in exposure if e["d"] == "2025-06-30")
rel_last = next(r for r in reversed(release) if r["equity_bn"] and r["reserve_bn"])
latest = {
    "as_of": last_exp["d"],
    "unhedged_usd_bn": last_exp["unhedged_usd_bn"],
    "unhedged_ntd_tn": last_exp["unhedged_ntd_tn"],
    "unprot_pct": last_exp["unprot_pct"],
    "fa_usd_bn": last_exp["fa_usd_bn"],
    "fa_ntd_bn": last_exp["fa_ntd_bn"],
    "usdtwd": last_exp["usdtwd"],
    "cover": last_exp["cover"], "n": last_exp["n"],
    "unhedged_usd_bn_year_ago": yr_ago["unhedged_usd_bn"],
    "unhedged_usd_bn_2017": first_exp["unhedged_usd_bn"],
    "unprot_pct_2017": first_exp["unprot_pct"],
    "equity_bn": rel_last["equity_bn"], "equity_m": rel_last["m"],
    "reserve_bn": rel_last["reserve_bn"],
    "fsc_net_open_tn": fsc["net_open_fx"][-1]["v"], "fsc_net_open_m": fsc["net_open_fx"][-1]["m"],
    "fsc_buffer_bn": fsc["buffer_total"][-1]["v"], "fsc_buffer_m": fsc["buffer_total"][-1]["m"],
    "fsc_absorb_pct": fsc["absorbable_appreciation"][-1]["v"],
    "reg_ratio_first": fsc["reg_hedge_ratio"][0], "reg_ratio_last": fsc["reg_hedge_ratio"][-1],
    "mixed_first": aggregate[0]["mixed"], "mixed_last": aggregate[-1]["mixed"],
    "deck_first": aggregate[0]["deck"], "deck_last": aggregate[-1]["deck"],
    "book_peak": max(book_monthly, key=lambda b: b["fa_usd_bn"]),
    "book_last": book_monthly[-1],
    "cbc_equity_last": next((b for b in reversed(balance) if b.get("equity")), None),
    "paired_ceiling": sum(1 for p in paired if p["accounts"] >= p["slide"]), "paired_n": len(paired),
    "jpm_cells": len(jpm),
    "jpm_have_hedge": sum(1 for j in jpm if j["ours_hedge"] is not None),
    "jpm_have_protected": sum(1 for j in jpm if j["ours_protected"] is not None),
    "cbc_swap_first": irfcl[0], "cbc_swap_last": irfcl[-1],
    "hp_usd_last": {"m": max(hp_usd), "v": r1(hp_usd[max(hp_usd)], 0)},
    "fn_usd_last": {"m": max(fn_usd), "v": r1(fn_usd[max(fn_usd)], 0)},
    "fn_usd_2022": {"m": "2022-06", "v": r1(fn_usd.get("2022-06"), 0)},
    "reserves": {m: next(r["v"] for r in fx_reserves if r["m"] == m)
                 for m in ("2024-12", "2025-04", "2025-05", "2025-06", "2025-12")},
    "reserves_last": fx_reserves[-1],
    "protected_pct": r1(100 - last_exp["unprot_pct"]),
    "protected_pct_2017": r1(100 - first_exp["unprot_pct"]),
    "protected_pct_year_ago": r1(100 - yr_ago["unprot_pct"]),
    "reg_eff_last": fsc["reg_hedge_ratio_effective"][-1],
}

blob = {
    "meta": {"built": dt.date.today().isoformat(), "sector_last_month": sec_last,
             "usdtwd_last_month": max(fx)},
    "latest": latest, "exposure": exposure, "composition": composition,
    "aggregate": aggregate, "firm_ratio": firm_ratio, "measure": MEASURE,
    "firms_latest": firms_latest, "book_monthly": book_monthly, "release": release,
    "fsc": fsc, "cbc": cbc, "balance": balance, "cost_market": cost_market,
    "fubon_cost": fubon_cost, "jpm": jpm, "paired": paired, "tic": tic,
    "irfcl": irfcl, "fx_reserves": fx_reserves, "cbc_share": cbc_share,
    "usdtwd": {m: v for m, v in fx.items() if m >= "2012-01"},
}
PAGE_JS = OUT_DIR / "page.js"


def main():
    OUT_DIR.mkdir(exist_ok=True)
    txt = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))
    BLOB.write_text(txt, encoding="utf-8")
    print(f"-> {BLOB.relative_to(ROOT)}  ({len(txt) / 1024:.0f} KB)")
    print(f"   exposure {len(exposure)}q  composition {len(composition)}q  aggregate {len(aggregate)}q")
    print(f"   book {len(book_monthly)}m  release {len(release)}m  jpm {len(jpm)}  paired {len(paired)}")
    e = latest
    print(f"   latest {e['as_of']}: unhedged US${e['unhedged_usd_bn']}bn = {e['unprot_pct']}% of "
          f"US${e['fa_usd_bn']}bn; a year earlier US${e['unhedged_usd_bn_year_ago']}bn; "
          f"2017 US${e['unhedged_usd_bn_2017']}bn")
    if TEMPLATE.exists():
        page = TEMPLATE.read_text(encoding="utf-8")
        marker = "/*DATA_BLOB*/"
        if marker not in page:
            raise SystemExit(f"{TEMPLATE.name} has no {marker} marker")
        # a JSON payload inside <script> must not contain '</script'
        page = page.replace(marker, txt.replace("</", "<\\/"))
        # the authored page code lives in page.js so the template stays the
        # design system's chrome and nothing else
        if "/*PAGE_SCRIPT*/" in page:
            page = page.replace("/*PAGE_SCRIPT*/", PAGE_JS.read_text(encoding="utf-8"))
        page = (page.replace("{{TITLE}}", "Taiwan's Unhedged Dollar Book")
                    .replace("{{EYEBROW}}", "TLFX · Taiwan life insurers"))
        PAGE.write_text(page, encoding="utf-8")
        print(f"-> {PAGE.relative_to(ROOT)}  ({PAGE.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
