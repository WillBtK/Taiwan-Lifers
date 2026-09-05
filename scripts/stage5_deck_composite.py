#!/usr/bin/env python3
"""The bottom-up hedge-ratio composite: Setser & S.T.W. (2019) §II.D, method 1.

The paper's first method for sizing the sector's hedges is to take the hedge
share from the listed insurers' own disclosures and apply it to the CBC's
sector foreign-asset series. This project extracted those disclosures months
ago — Cathay 47 quarters from 2013-10, Fubon 49 from 2013-10, KGI 20 from
2020-10 — and never assembled them. This does that.

WHY IT MATTERS THAT THIS EXISTS
-------------------------------
It is the only measure here that is quarterly, firm-verifiable and long. The
CBC footnote (4.34) is authoritative but sparse — eleven editions the Internet
Archive happens to hold. The P&L reconstruction (4.29) is monthly but starts
2019 and is an inference. This is neither sparse nor inferred: each point is a
number a listed company published about itself.

THE THREE FIRMS DISCLOSE DIFFERENT THINGS, AND THE DIFFERENCE IS THE WHOLE JOB
-----------------------------------------------------------------------------
Each deck draws two cuts of the FX book: a BAR splitting foreign assets into
FX-risk-bearing and FX-policy-backed, and a PIE of instrument shares summing
to 100. What the pie is taken over differs by firm, and reading it wrong moves
the answer by ~30pp (decisions 4.2).

  * Cathay: pie = CS/NDF + proxy&open + FVOCI-equity = 100. None of those is
    FX policy, and policy-backed assets carry no derivative by construction,
    so the pie is over the FX-RISK-BEARING SUBSET only. Hence
        gross = csndf × fx_risk;  economic = gross + fx_policy.
  * KGI: identical structure (cs_ndf + naked + overseas equity = 100, with the
    policy share in a separate bar). Same formulas.
  * Fubon: the big wedge is named 「外匯交換、無本金遠期外匯、外幣保單」 — it
    NAMES FX policy among its own contents, so it is over TOTAL FX assets and
    is the economic hedge ratio as disclosed (4.2, settled).

FUBON IS REPORTED BESIDE THE COMPOSITE, NOT INSIDE IT
-----------------------------------------------------
Two independent reasons, and either alone would be enough.

First, Fubon's wedge cannot be split into derivatives and policy, so it can
never join the gross composite; putting it in the economic one only would mean
the two composites rest on different panels and could not be differenced.

Second and worse, Fubon's own pie changes base. Through 2016 it carries a
separate 股票/共同基金 wedge of 11-15%; from 2017 that wedge is gone. The same
firm therefore reads 76.6% in 2014 and 95.2% in 2018 with no change in
behaviour large enough to explain it — the denominator moved. Normalising the
early years to the later base (dividing by 1 − equity wedge) lines them up
almost exactly (2017Q2 96.9% restated against 2018Q1's published 95.2%), which
confirms the diagnosis but does not license blending, because the equity wedge
is extracted in only 21 of 173 rows and is absent for reasons the extract
cannot distinguish from a genuine zero.

So Fubon is carried as its own disclosed firm series with the base break
flagged, and the composites are built from Cathay and KGI, whose construction
is identical to each other. Mixing two definitions into one line is the error
already recorded at 4.2 and again at 4.30; doing it a third time knowingly
would be worse than not having the series.

A related trap, tripped and removed: where `cs_ndf_policy_pct` is unpublished
it is tempting to recover it as 100 minus the naked and equity wedges. That is
sound only when the equity wedge is known, and it is usually not — the
fallback returned 95.5% for 2017Q1 by silently treating a missing equity wedge
as zero. Only the published wedge is used.

CARRYING THE BAR
----------------
Cathay prints the bar in 23 quarters and the pie in 26, overlapping in 13. The
bar is the slow-moving half — 68-71% across 2019-2025, 76% in 2014, 74% in
2026 — so it is carried to neighbouring quarters from the nearest observation,
within a stated limit. A 2pp error in a ~69% bar moves a ~47% gross ratio by
about 1.4pp, which is inside the dispersion between firms and is reported as
such. The pie is never carried: it is the fast half and the thing being
measured.

WEIGHTS
-------
Foreign investment per firm, from the Insurance Bureau's 資金運用表
(`firm_fund_utilisation`, 4.27) at the year-ends it covers, held flat outside
that window. Cathay's own deck carries its FX assets every quarter and is used
in preference. The equal-weighted composite is reported alongside, because if
the two differ materially the weighting is doing work the data cannot support.

VALIDATION
----------
Three tests, in descending order of how much they would hurt to fail:
 1. the gross composite against the sector gross ratio derived from the FSC's
    own hedge principal (4.1) — same quantity, independent construction;
 2. the gross composite times sector 國外投資 against the CBC's published
    hedge amount (4.34) — the ratio should land near the 0.62-0.77 onshore-swap
    share already established, since the CBC counts swaps and the decks count
    swaps plus NDFs;
 3. dispersion between firms, which bounds how much a three-firm panel can say
    about twenty-three insurers.
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATHAY = ROOT / "data" / "cathay_fx_quarterly.csv"
FUBON = ROOT / "data" / "fubon_deck_fx.csv"
KGI = ROOT / "data" / "kgi_deck_fx.csv"
OUT_CSV = ROOT / "data" / "deck_composite.csv"

# How far a bar reading may be carried to a quarter that lacks one. Four
# quarters: far enough to bridge the gaps these decks actually have, short
# enough that a carried value is never the only thing spanning a regime change.
CARRY_Q = 4

INPUT_SQL = """
select json_build_object(
  'weights', (select json_agg(json_build_object('entity_id',entity_id,
       'obs_date',obs_date,'foreign_investment',foreign_investment))
     from tlfx.firm_fund_utilisation where period_kind='year_end'),
  'sector_fi', (select json_agg(json_build_object('m',obs_month,'v',v)) from (
     select obs_month, max(foreign_investments) v from tlfx.sector_monthly
     where reporting_channel='ib_indicators' group by 1) t),
  'cbc_amt', (select json_agg(json_build_object('m',obs_date,'v',value))
     from tlfx.derived_series where series_key='hedge_outstanding_cbc_footnote'),
  'sector_gross', (select json_agg(json_build_object('m',obs_date,'v',value))
     from tlfx.derived_series where series_key='gross_hedge_ratio'),
  'reg_ratio', (select json_agg(json_build_object('m',obs_date,'v',value))
     from tlfx.derived_series where series_id=4 and series_key='reg_hedge_ratio'));
"""


def num(s):
    if s in (None, "", "-"):
        return None
    try:
        return float(str(s).replace(",", "").replace("%", ""))
    except ValueError:
        return None


def qend(period):
    """'1H26' / '9M23' / 'FY22' / '1Q26' / '23' -> quarter-end date."""
    p = (period or "").strip().upper()
    m = re.fullmatch(r"(\d)Q(\d{2})", p) or re.fullmatch(r"(\d)Q(\d{4})", p)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
    elif re.fullmatch(r"1H(\d{2,4})", p):
        q, y = 2, int(p[2:])
    elif re.fullmatch(r"9M(\d{2,4})", p):
        q, y = 3, int(p[2:])
    elif re.fullmatch(r"(FY)?(\d{2,4})", p):
        q, y = 4, int(re.fullmatch(r"(FY)?(\d{2,4})", p).group(2))
    else:
        return None
    y = y + 2000 if y < 100 else y
    return f"{y}-{q*3:02d}-01"


def carry(series, quarters):
    """Fill gaps in a slow-moving series from the nearest reading, within CARRY_Q.

    Nearest rather than previous: a gap between two readings is bridged from
    whichever side is closer, which is the right choice for a series that
    drifts rather than jumps, and avoids a stale value being preferred to a
    fresher one on the other side of the hole.
    """
    known = sorted(k for k in series if series[k] is not None)
    out = {}
    for q in quarters:
        if series.get(q) is not None:
            out[q] = (series[q], 0)
            continue
        i = quarters.index(q)
        best = None
        for k in known:
            d = abs(quarters.index(k) - i)
            if d <= CARRY_Q and (best is None or d < best[1]):
                best = (series[k], d)
        if best:
            out[q] = best
    return out


def read_cathay():
    rows = {}
    for r in csv.DictReader(open(CATHAY, encoding="utf-8")):
        q = qend(r["period"])
        if q:
            rows[q] = {"csndf": num(r["hedge_cs_ndf_pct"]),
                       "fxrisk": num(r["fx_risk_exposure_pct"]),
                       "fxpol": num(r["fx_policy_reserve_pct"]),
                       "fx_assets": (num(r["fx_assets_ntd_tn"]) or 0) * 1_000_000 or None}
    return rows


def read_kgi():
    rows = {}
    for r in csv.DictReader(open(KGI, encoding="utf-8")):
        q = qend(r["deck_period"])
        if not q:
            continue
        d = rows.setdefault(q, {"csndf": None, "fxrisk": None, "fxpol": None, "fx_assets": None})
        # the same quarter appears in a Chinese and an English deck; take the
        # union rather than one language, since they differ in which cells the
        # extractor could bind, not in what they say
        for k, col in (("csndf", "cs_ndf_pct"), ("fxrisk", "fx_risk_pct"), ("fxpol", "fx_policy_pct")):
            v = num(r[col])
            if v is not None and d[k] is None:
                d[k] = v
    return rows


def read_fubon():
    rows = {}
    for r in csv.DictReader(open(FUBON, encoding="utf-8")):
        q = qend(r["period"])
        if not q:
            continue
        d = rows.setdefault(q, {"econ": None, "equity": None})
        v = num(r["cs_ndf_policy_pct"])          # published only — see docstring
        if v is not None and d["econ"] is None:
            d["econ"] = v
        eq = num(r["equity_fund_pct"])
        if eq is not None and d["equity"] is None:
            d["equity"] = eq
    # restate the pre-2017 readings onto the later base by removing the
    # separately drawn equity wedge, so the series can be read as one line;
    # both are kept and the flag says which is which
    for q, d in rows.items():
        d["econ_restated"] = (round(d["econ"] / (100 - d["equity"]) * 100, 1)
                              if d["econ"] is not None and d["equity"] else d["econ"])
        d["base"] = ("restated_ex_equity_wedge" if d["equity"] else "as_published")
    return rows


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return repr(v) if isinstance(v, float) else str(v)


def main():
    payload = {} if sys.stdin.isatty() else json.load(sys.stdin)
    wts, sector_fi = {}, {}
    for w in payload.get("weights") or []:
        wts.setdefault(w["entity_id"], {})[str(w["obs_date"])[:10]] = float(w["foreign_investment"])
    for x in payload.get("sector_fi") or []:
        sector_fi[str(x["m"])[:10]] = float(x["v"])
    cbc = {str(x["m"])[:10]: float(x["v"]) for x in (payload.get("cbc_amt") or [])}
    secg = {str(x["m"])[:10]: float(x["v"]) for x in (payload.get("sector_gross") or [])}
    reg = {str(x["m"])[:10]: float(x["v"]) for x in (payload.get("reg_ratio") or [])}

    cat, kgi, fub = read_cathay(), read_kgi(), read_fubon()
    quarters = sorted(set(cat) | set(kgi) | set(fub))

    # carry the slow bar for the two firms whose pie is over the risk subset
    cat_risk = carry({q: cat.get(q, {}).get("fxrisk") for q in quarters}, quarters)
    cat_pol = carry({q: cat.get(q, {}).get("fxpol") for q in quarters}, quarters)
    kgi_risk = carry({q: kgi.get(q, {}).get("fxrisk") for q in quarters}, quarters)
    kgi_pol = carry({q: kgi.get(q, {}).get("fxpol") for q in quarters}, quarters)

    def weight(ent, q):
        w = wts.get(ent) or {}
        if not w:
            return None
        ks = sorted(w)
        return w[min(ks, key=lambda k: abs((int(k[:4]) * 4 + int(k[5:7]) // 3)
                                           - (int(q[:4]) * 4 + int(q[5:7]) // 3)))]

    rows = []
    for q in quarters:
        firms = {}
        c = cat.get(q, {})
        if c.get("csndf") is not None and q in cat_risk:
            g = c["csndf"] * cat_risk[q][0] / 100
            firms["cathay_life"] = {"gross": g, "carried": cat_risk[q][1],
                                    "econ": (g + cat_pol[q][0]) if q in cat_pol else None,
                                    "w": c.get("fx_assets") or weight("cathay_life", q)}
        k = kgi.get(q, {})
        if k.get("csndf") is not None and q in kgi_risk:
            g = k["csndf"] * kgi_risk[q][0] / 100
            firms["kgi_life"] = {"gross": g, "carried": kgi_risk[q][1],
                                 "econ": (g + kgi_pol[q][0]) if q in kgi_pol else None,
                                 "w": weight("kgi_life", q)}
        f = fub.get(q, {})                        # reported beside, never blended
        if not firms and not f.get("econ"):
            continue

        def comp(field):
            vals = [(v[field], v["w"]) for v in firms.values() if v[field] is not None]
            if not vals:
                return None, None, None
            eq = sum(x for x, _ in vals) / len(vals)
            aw = (sum(x * w for x, w in vals) / sum(w for _, w in vals)
                  if all(w for _, w in vals) else None)
            spread = (max(x for x, _ in vals) - min(x for x, _ in vals)) if len(vals) > 1 else None
            return aw, eq, spread

        g_aw, g_eq, g_sp = comp("gross")
        e_aw, e_eq, e_sp = comp("econ")
        fi = sector_fi.get(q)
        rows.append({
            "obs_quarter": q,
            "n_firms_gross": sum(1 for v in firms.values() if v["gross"] is not None),
            "n_firms_econ": sum(1 for v in firms.values() if v["econ"] is not None),
            "gross_pct_aw": None if g_aw is None else round(g_aw, 2),
            "gross_pct_ew": None if g_eq is None else round(g_eq, 2),
            "gross_spread_pp": None if g_sp is None else round(g_sp, 1),
            "econ_pct_aw": None if e_aw is None else round(e_aw, 2),
            "econ_pct_ew": None if e_eq is None else round(e_eq, 2),
            "econ_spread_pp": None if e_sp is None else round(e_sp, 1),
            "cathay_gross": None if "cathay_life" not in firms else (
                None if firms["cathay_life"]["gross"] is None else round(firms["cathay_life"]["gross"], 1)),
            "kgi_gross": None if "kgi_life" not in firms else (
                None if firms["kgi_life"]["gross"] is None else round(firms["kgi_life"]["gross"], 1)),
            "fubon_econ_published": f.get("econ"),
            "fubon_econ_restated": f.get("econ_restated"),
            "fubon_base": f.get("base"),
            "bar_carried_q": max((v["carried"] for v in firms.values()), default=0),
            "sector_fi_ntd_mn": fi,
            "implied_hedge_ntd_mn": (round(fi * (g_aw or g_eq) / 100, 1)
                                     if fi and (g_aw or g_eq) else None),
        })

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    g = [r for r in rows if r["gross_pct_aw"] is not None or r["gross_pct_ew"] is not None]
    e = [r for r in rows if r["econ_pct_aw"] is not None or r["econ_pct_ew"] is not None]
    print(f"quarters: {len(rows)}  ({rows[0]['obs_quarter']} → {rows[-1]['obs_quarter']})")
    print(f"  gross composite (CS+NDF / total FX assets): {len(g)} quarters, "
          f"{g[0]['obs_quarter']} → {g[-1]['obs_quarter']}")
    print(f"  economic composite (+ FX policies):         {len(e)} quarters, "
          f"{e[0]['obs_quarter']} → {e[-1]['obs_quarter']}")

    print("\nTHE COMPOSITE, by quarter")
    print(f"  {'quarter':<10}{'gross aw':>9}{'gross ew':>9}{'econ aw':>9}{'econ ew':>9}"
          f"{'spread':>8}{'n':>4}  {'cathay':>7}{'kgi':>6}{'fubon(e)':>9}  carried")
    for r in rows:
        f2 = lambda v, w=7: (("%.1f" % v) if v is not None else "-").rjust(w)
        print(f"  {r['obs_quarter'][:7]:<10}{f2(r['gross_pct_aw'],9)}{f2(r['gross_pct_ew'],9)}"
              f"{f2(r['econ_pct_aw'],9)}{f2(r['econ_pct_ew'],9)}"
              f"{f2(r['econ_spread_pp'] if r['econ_spread_pp'] is not None else r['gross_spread_pp'],8)}"
              f"{max(r['n_firms_gross'], r['n_firms_econ']):>4}  "
              f"{f2(r['cathay_gross'])}{f2(r['kgi_gross'],6)}{f2(r['fubon_econ_restated'],9)}"
              f"{'*' if r['fubon_base']=='restated_ex_equity_wedge' else ' '}"
              f"  {r['bar_carried_q'] or ''}")

    print("\nVALIDATION 1 — gross composite vs the sector gross ratio from the "
          "FSC's own hedge principal")
    errs = []
    for r in rows:
        v = secg.get(r["obs_quarter"])
        est = r["gross_pct_aw"] or r["gross_pct_ew"]
        if v is None or est is None:
            continue
        d = est - v * 100
        errs.append(d)
        print(f"  {r['obs_quarter'][:7]}  composite {est:>5.1f}%   FSC-basis "
              f"{v*100:>5.1f}%   diff {d:>+5.1f}pp")
    if errs:
        print(f"  n {len(errs)}   MAE {sum(abs(x) for x in errs)/len(errs):.1f}pp   "
              f"mean {sum(errs)/len(errs):+.1f}pp")

    print("\nVALIDATION 2 — composite hedge amount vs the CBC's published amount")
    print("  The CBC counts onshore swaps; the decks count swaps AND NDFs, so the")
    print("  ratio should sit near the 0.62-0.77 onshore share established at 4.34.")
    print(f"  {'CBC month':<10}{'composite NT$bn':>17}{'CBC NT$bn':>12}{'CBC/composite':>15}   matched")
    # The CBC prints whatever month its edition covers; the decks are quarterly.
    # Matching on the exact quarter alone throws away most of the overlap, so a
    # CBC month is matched to the composite quarter within one quarter of it and
    # the distance is shown — a reader can discount the matched pairs if the
    # exact ones disagree with them, and here they do not.
    def qi(m):
        return int(m[:4]) * 4 + (int(m[5:7]) - 1) // 3
    rr = []
    for cm, c in sorted(cbc.items()):
        cand = [r for r in rows if r["implied_hedge_ntd_mn"] is not None
                and abs(qi(r["obs_quarter"]) - qi(cm)) <= 1]
        if not cand:
            continue
        r = min(cand, key=lambda x: abs(qi(x["obs_quarter"]) - qi(cm)))
        d = abs(qi(r["obs_quarter"]) - qi(cm))
        rr.append(c / r["implied_hedge_ntd_mn"])
        print(f"  {cm[:7]:<10}{r['implied_hedge_ntd_mn']/1000:>17,.0f}"
              f"{c/1000:>12,.0f}{c/r['implied_hedge_ntd_mn']:>15.2f}"
              f"   {'exact' if d == 0 else r['obs_quarter'][:7]}")
    if rr:
        print(f"  n {len(rr)}   mean {sum(rr)/len(rr):.2f}   range {min(rr):.2f}–{max(rr):.2f}")

    print("\nVALIDATION 3 — dispersion between firms, which bounds what a "
          "three-firm panel can claim")
    sp = [r["econ_spread_pp"] for r in rows if r["econ_spread_pp"] is not None]
    if sp:
        print(f"  economic ratio, max-min across firms: mean {sum(sp)/len(sp):.1f}pp, "
              f"worst {max(sp):.1f}pp, n {len(sp)}")
    gsp = [r["gross_spread_pp"] for r in rows if r["gross_spread_pp"] is not None]
    if gsp:
        print(f"  gross ratio:                          mean {sum(gsp)/len(gsp):.1f}pp, "
              f"worst {max(gsp):.1f}pp, n {len(gsp)}")

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    vals = []
    for r in rows:
        for key, sid, v in (("gross_hedge_ratio_deck_composite", 5, r["gross_pct_aw"] or r["gross_pct_ew"]),
                            ("economic_hedge_ratio_deck_composite", 1, r["econ_pct_aw"] or r["econ_pct_ew"])):
            if v is not None:
                vals.append((sid, key, r["obs_quarter"], round(v / 100, 4),
                             max(r["n_firms_gross"], r["n_firms_econ"]), r["bar_carried_q"]))
    vsql = ",\n  ".join("(" + ", ".join(sqlv(x) for x in v) + ")" for v in vals)
    sql = f"""-- stage5-deck-composite: generated by scripts/stage5_deck_composite.py at {now}. Idempotent.
begin;
with vals(series_id, series_key, obs_date, value, n_firms, bar_carried) as (values
  {vsql})
insert into tlfx.derived_series
  (series_id, series_key, entity_id, obs_date, freq, value, unit,
   definition_version, basis, basis_note, source_url, source_doc, retrieved_at, vintage)
select series_id::smallint, series_key, null, obs_date::date, 'Q'::tlfx.frequency,
  value, 'ratio', 'deck_composite', 'estimated',
  'Bottom-up composite of listed insurers'' own disclosures, the first method of '
  'Setser and S.T.W. (2019) II.D. Firm hedge shares weighted by foreign investment. '
  'Cathay and KGI publish an instrument pie over their FX-RISK-BEARING subset plus a '
  'separate FX-policy bar, so gross = pie share x risk share; Fubon''s wedge names '
  '外幣保單 among its contents so it is over total FX assets and is the economic '
  'ratio as disclosed, contributing to the economic composite only. '
  || n_firms || ' firm(s) this quarter'
  || case when bar_carried > 0 then '; FX-risk bar carried up to '
       || bar_carried || ' quarter(s) from the nearest reading' else '' end || '.',
  'https://www.cathayholdings.com/holdings/investors/',
  'Cathay, Fubon and KGI results decks (data/{{cathay_fx_quarterly,fubon_deck_fx,kgi_deck_fx}}.csv)',
  '{now}'::timestamptz, current_date
from vals
on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) do nothing;
commit;
"""
    out = ROOT / "out" / f"stage5_deck_composite_{dt.date.today():%Y%m%d}.sql"
    out.parent.mkdir(exist_ok=True)
    out.write_text(sql, encoding="utf-8")
    for k in ("gross_hedge_ratio_deck_composite", "economic_hedge_ratio_deck_composite"):
        vs = [v[3] for v in vals if v[1] == k]
        print(f"\n  {k:<38} n {len(vs):>3}  sum {sum(vs):.4f}")
    print(f"csv: {OUT_CSV.relative_to(ROOT)}   sql: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
