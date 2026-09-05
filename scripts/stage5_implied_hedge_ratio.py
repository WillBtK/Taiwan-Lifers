#!/usr/bin/env python3
"""Reconstruct the sector hedge ratio from the FSC monthly P&L lines, and validate it.

The problem this exists to solve: the FSC only began publishing the regulatory
hedge ratio in 2024-04, so the headline series is sixteen observations long
(decisions, backfill spec). It cannot be back-filled by fetching, because the
disclosure did not exist before then. It can be *reconstructed*, and the
reconstruction can be checked against the published figure over the window
where both exist — which is the whole point. A construction that cannot
reproduce the known period has no business being extended into the unknown one.

THE IDENTITY
------------
The monthly release carries three FX lines for the life sector, year-to-date:

    兌換損益        fx    translation result on the FX book, net of the FX-policy
                          liability leg
    避險工具損益    hgi   mark-to-market on the hedging instruments (from 2020-01;
                          before that only the combined 避險損益 exists)
    換匯成本        hsc   the swap carry — a cost, near-linear in time
    外匯價格變動準備 res   net movement in the FX volatility reserve

Over a month in which the currency moves by Δ,

    fx   ≈  A · Δ            A = the FX asset base whose translation reaches P&L
    hgi  ≈ −H · Δ            H = notional of FX derivatives marked through P&L
    hsc  ≈ −carry            independent of Δ

so the hedged share is identified by a ratio of two P&L lines:

    h  =  −hgi / fx  =  H / A

and Δ drops out. That is the estimator's main virtue: it needs no exchange
rate, no asset base, and no view on what fraction of the book is FX. Errors in
the denominator series — which is where the scope traps in this project live
(decisions 4.1: the regulatory denominator is ~68% of 國外投資) — cannot reach
it, because it has no denominator series.

WHAT IT IS NOT
--------------
Two things it is not, both learned the hard way in this file's history.

1. It is NOT −hg/fx. The combined 避險損益 includes the swap carry, which does
   not scale with Δ. Including it biases the estimate by the carry-to-FX-result
   ratio, which is large in quiet months and small in violent ones, so it does
   not average out — it makes the estimate a function of how noisy the sample
   was. The carry is stripped, not modelled.

2. It is NOT a regression of fx on (foreign assets × Δ). That specification was
   tried and rejected: it assumes every foreign asset's translation reaches
   P&L, which for FVOCI equity it does not, so its slope measures the unhedged
   share times an unknown scope factor. It missed the published ratio by 24pp
   on average and in the same direction on all six months. Recorded here
   because a plausible-looking specification that fails in one direction is
   evidence about the data, not just a dead end.

DATING, WHICH IS WHERE THE FIRST VERSION WENT WRONG
---------------------------------------------------
A rolling window weighted by fx² is not an estimate of its last month. Twelve
months containing May 2025 — a 6% currency move, three times anything around
it — is an estimate of May 2025 wearing a window's clothes. The first version
compared such an estimate to the published ratio at the window's *end*, over a
period when the ratio was falling about 2pp a month, and read the resulting
gap as a level bias in the estimator. It is not: it is the trend, measured
across the months between where the estimate comes from and where it was
filed. Every rolling estimate here therefore carries the weighted centre it
was really taken at, and is validated against the published ratio interpolated
to THAT month, not to the window's end.

RESIDUAL SCOPE GAP
------------------
The ratio measures H/A. The FSC publishes H/D, where D is the regulatory
denominator (國外投資 net of FX-policy-backed assets and non-FVTPL equity).
A and D are near but not identical, so a residual gap is expected; it is
reported per validation month rather than assumed away, and is NOT calibrated
out — a scale factor fitted on six points and applied to eight years would be
fitting noise and calling it history.

THE BUFFER-INCLUSIVE VARIANT
----------------------------
    h_total  =  −(hgi + res) / fx

adds the FX volatility reserve's absorption to the derivative hedge. This is
the substitution measure the project is actually after: it says how much of a
currency move never reaches the bottom line, by either route. The wedge
between the two is the reserve's contribution, which is the thing that grew
as the hedge ratio fell.
"""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "implied_hedge_ratio.csv"

# The input. Piped in as JSON on stdin; kept here so the run is reproducible
# from the database rather than from whatever file happened to be on disk.
INPUT_SQL = """
with r as (
  select obs_month,
         max(fx_gain_loss)                  filter (where reporting_channel='release') fx,
         max(hedging_gain_loss)             filter (where reporting_channel='release') hg,
         max(hedging_instrument_gain_loss)  filter (where reporting_channel='release') hgi,
         max(hedging_swap_cost)             filter (where reporting_channel='release') hsc,
         max(fx_reserve_net_change)         filter (where reporting_channel='release') res,
         max(foreign_investments)           filter (where reporting_channel='ib_indicators') fi,
         max(hedge_ratio_regulatory) hr,
         max(vintage)                       filter (where reporting_channel='release') vintage
  from tlfx.sector_monthly group by 1)
select json_agg(json_build_object('m',obs_month,'fx',fx,'hg',hg,'hgi',hgi,
                                  'hsc',hsc,'res',res,'fi',fi,'hr',hr,
                                  'vintage',vintage)
                order by obs_month)
from r where obs_month between '2018-05-01' and '2026-08-01';
"""

WINDOW = 12           # months in a rolling estimate
# NT$ mn. A month's |fx| below this carries no usable information: the ratio's
# noise is roughly (error in the hedge line) / |fx|, so the threshold is a
# signal-to-noise floor, not a convention. Calibrated against the published
# ratio, single-month readings miss by ~3-5pp at |fx| above NT$240bn and by
# 11pp and 39pp at NT$121bn and NT$130bn. NT$200bn sits in that gap.
MIN_MOVE = 200_000
# Monthly swap carry assumed for 2018-05 → 2019-10, the months that publish the
# combined hedging line but no cost split. It is the 2019 full-year cost
# (NT$198.5bn, the first year the split exists) divided by twelve. It is an
# ASSUMPTION and the rows it touches are flagged: the resulting ratio moves
# about 5pp per NT$10bn of monthly carry, so this period is reported separately
# and is not part of the validated series.
CARRY_2018_19 = 16_540


def prev_month(k):
    y, m = k
    return (y - 1, 12) if m == 1 else (y, m - 1)


def ytd_to_monthly(series):
    """The release is YEAR-TO-DATE and resets each January.

    Differencing without respecting the reset turns every January into the
    negative of the prior December's full year, which would dominate anything
    fitted on it. January is taken as-is; only later months are differenced,
    and a month whose predecessor is missing is dropped rather than differenced
    against a two-month gap.
    """
    out = {}
    for (y, m) in sorted(series):
        if m == 1:
            out[(y, m)] = series[(y, m)]
        elif (y, m - 1) in series:
            out[(y, m)] = series[(y, m)] - series[(y, m - 1)]
    return out


def through_origin(pairs):
    """Slope of y on x with no intercept, weighted naturally by x².

    No intercept is right here and not merely convenient: the carry has already
    been removed from y, so a month with no currency move should produce no
    hedge result. Fitting an intercept would let the estimator explain part of
    the hedge P&L with something that is not the currency, which is the error
    the combined-line version made. The x² weighting is the second reason to
    prefer it: months when the currency barely moved tell you almost nothing
    about the hedge ratio, and this form says so arithmetically instead of
    giving them equal say.
    """
    sxx = sum(x * x for x, _ in pairs)
    if sxx == 0:
        return None
    b = sum(x * y for x, y in pairs) / sxx
    ybar = sum(y for _, y in pairs) / len(pairs)
    ss_res = sum((y - b * x) ** 2 for x, y in pairs)
    ss_tot = sum((y - ybar) ** 2 for _, y in pairs)
    return b, (1 - ss_res / ss_tot if ss_tot else float("nan")), sxx


def weighted_centre(months, weights):
    """Where in the window the estimate actually comes from.

    A through-origin fit weights by x², so a twelve-month window containing one
    violent month is an estimate of that month, not of the window's midpoint.
    Dating it to the midpoint would smear a sharp move across a year and invent
    a gradual trend. This returns the weight-weighted month index instead, and
    the caller reports it, so the reader can see when an estimate is really a
    single month wearing a window's clothes.
    """
    tot = sum(weights)
    if tot == 0:
        return None
    idx = sum(i * w for i, w in enumerate(weights)) / tot
    lo = months[int(idx)]
    hi = months[min(int(idx) + 1, len(months) - 1)]
    frac = idx - int(idx)
    return lo if frac < 0.5 else hi


def main(rows_in):
    fx_y, hgi_y, hg_y, hsc_y, res_y, fi, published = {}, {}, {}, {}, {}, {}, {}
    vint = {}
    for r in rows_in:
        k = (int(r["m"][:4]), int(r["m"][5:7]))
        for src, dst in (("fx", fx_y), ("hgi", hgi_y), ("hg", hg_y),
                         ("hsc", hsc_y), ("res", res_y), ("fi", fi),
                         ("hr", published)):
            v = r.get(src)
            if v not in (None, ""):
                dst[k] = float(v)
        if r.get("vintage"):
            vint[k] = r["vintage"]

    # 2019-11 and 2019-12 publish the combined line and the swap cost but not
    # the instrument line; the instrument leg is their difference. Recovering it
    # is arithmetic on published figures, not an estimate, so it is done here
    # rather than left as a gap.
    for k in sorted(set(hg_y) & set(hsc_y)):
        if k not in hgi_y:
            hgi_y[k] = hg_y[k] - hsc_y[k]

    fx_m = ytd_to_monthly(fx_y)
    hgi_m = ytd_to_monthly(hgi_y)
    hg_m = ytd_to_monthly(hg_y)
    hsc_m = ytd_to_monthly(hsc_y)
    res_m = ytd_to_monthly(res_y)

    # 2018-06 → 2019-10 publish one combined hedging line. Stripping the carry
    # there means assuming it. The months are kept, because a period the
    # estimator can reach only under an assumption is still worth seeing, but
    # they are flagged and excluded from every validation and headline figure.
    imputed = set()
    for k in sorted(set(fx_m) & set(hg_m)):
        if k not in hgi_m:
            hgi_m[k] = hg_m[k] + CARRY_2018_19
            imputed.add(k)

    rows = []
    for k in sorted(set(fx_m) & set(hgi_m)):
        f, h = fx_m[k], hgi_m[k]
        informative = abs(f) >= MIN_MOVE
        rv = res_m.get(k)
        rows.append({
            "obs_month": f"{k[0]}-{k[1]:02d}-01",
            "fx_pl": round(f, 1), "hedge_instr_pl": round(h, 1),
            "swap_cost": None if k not in hsc_m else round(hsc_m[k], 1),
            "fx_reserve_net": None if rv is None else round(rv, 1),
            "foreign_investment": fi.get(k),
            # Differencing a YTD figure consumes two editions, so the estimate
            # only exists once the later of the two is out. That later edition
            # is its vintage; dating it to the observation month's own release
            # would claim the number was available a month before it was.
            "vintage": max(x for x in (vint.get(k), vint.get(prev_month(k)))
                           if x) if vint.get(k) else None,
            "carry_imputed": k in imputed,
            "informative": informative,
            # the single-month reading: transparent, exact, and undefined when
            # the currency did not move enough to identify anything
            "h_month": round(-h / f, 4) if informative else None,
            "h_month_with_reserve": (round(-(h + rv) / f, 4)
                                     if informative and rv is not None else None),
            "h_roll": None, "h_roll_r2": None, "h_roll_centre": None,
            "h_roll_carry_imputed": None, "h_roll_with_reserve": None,
            "published_h": published.get(k),
        })

    for i in range(WINDOW - 1, len(rows)):
        w = rows[i + 1 - WINDOW:i + 1]
        fit = through_origin([(r["fx_pl"], r["hedge_instr_pl"]) for r in w])
        if fit is None:
            continue
        b, r2, sxx = fit
        rows[i]["h_roll"] = round(-b, 4)
        rows[i]["h_roll_r2"] = round(r2, 3)
        rows[i]["h_roll_centre"] = weighted_centre(
            [r["obs_month"] for r in w], [r["fx_pl"] ** 2 for r in w])
        rows[i]["h_roll_carry_imputed"] = any(r["carry_imputed"] for r in w)
        wr = [r for r in w if r["fx_reserve_net"] is not None]
        if len(wr) == WINDOW:
            fit2 = through_origin(
                [(r["fx_pl"], r["hedge_instr_pl"] + r["fx_reserve_net"]) for r in wr])
            if fit2:
                rows[i]["h_roll_with_reserve"] = round(-fit2[0], 4)

    OUT_CSV.parent.mkdir(exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n_inf = sum(1 for r in rows if r["informative"])
    print(f"months: {len(rows)}  ({rows[0]['obs_month']} → {rows[-1]['obs_month']}), "
          f"{n_inf} with |fx result| ≥ NT${MIN_MOVE/1000:,.0f}bn")

    # The published anchors, in date order. The 2026 observations are excluded
    # deliberately: the Bureau changed the definition at the February 2026
    # notice (decisions 4.1, the v1/v2 break), so interpolating across that
    # boundary would validate the estimator against two different quantities
    # joined by a straight line. They are also outside the P&L data's range.
    pub = sorted((r["obs_month"], r["published_h"])
                 for r in rows if r["published_h"] is not None)

    def pub_at(month):
        """The published ratio interpolated to a month, within its range only.

        Extrapolation is refused rather than clamped: outside the published
        window there is nothing to validate against, and a clamped value would
        look like a comparison while being an assumption.
        """
        if not pub or month < pub[0][0] or month > pub[-1][0]:
            return None
        for (m0, v0), (m1, v1) in zip(pub, pub[1:]):
            if m0 <= month <= m1:
                n = (int(m1[:4]) - int(m0[:4])) * 12 + int(m1[5:7]) - int(m0[5:7])
                k = (int(month[:4]) - int(m0[:4])) * 12 + int(month[5:7]) - int(m0[5:7])
                return v0 + (v1 - v0) * (k / n if n else 0)
        return None

    print("\nVALIDATION 1 — single-month readings against the published ratio")
    print("  No window, no smoothing, no lag: each month's own two P&L lines "
          "against\n  the published ratio at that month. Only months clearing "
          f"the NT${MIN_MOVE/1000:,.0f}bn floor.\n"
          "  'anchor' rows are exact published months; the rest interpolate "
          "between\n  anchors, which is why both are scored separately.")
    print(f"  {'month':<12}{'published':>10}{'estimate':>10}{'diff':>8}"
          f"{'|fx| NT$bn':>12}   kind")
    e1, e1a = [], []
    for r in rows:
        if r["h_month"] is None:
            continue
        p, kind = r["published_h"], "anchor"
        if p is None:
            p, kind = pub_at(r["obs_month"]), "interpolated"
        if p is None:
            continue
        d = r["h_month"] - p
        e1.append(d)
        if kind == "anchor":
            e1a.append(d)
        print(f"  {r['obs_month']:<12}{p:>10.3f}{r['h_month']:>10.3f}{d:>+8.3f}"
              f"{abs(r['fx_pl'])/1000:>12,.0f}   {kind}")
    if e1a:
        print(f"  anchors only: n {len(e1a)}   "
              f"MAE {sum(abs(d) for d in e1a)/len(e1a)*100:.1f}pp   "
              f"mean error {sum(e1a)/len(e1a)*100:+.1f}pp")
    if e1:
        print(f"  all in range: n {len(e1)}   "
              f"MAE {sum(abs(d) for d in e1)/len(e1)*100:.1f}pp   "
              f"mean error {sum(e1)/len(e1)*100:+.1f}pp")

    print("\nVALIDATION 2 — rolling estimates, dated to their weighted centre")
    print("  Each estimate is compared to the published ratio interpolated to "
          "the month\n  its own weighting says it came from, not to the "
          "window's last month.")
    print(f"  {'window end':<12}{'centre':<12}{'pub@centre':>11}{'estimate':>10}"
          f"{'diff':>8}{'pub@end':>9}{'diff@end':>10}")
    e2, e2end = [], []
    for r in rows:
        if r["h_roll"] is None or r["h_roll_carry_imputed"]:
            continue
        c = r["h_roll_centre"]
        pc, pe = pub_at(c), pub_at(r["obs_month"])
        if pc is None:
            continue
        d = r["h_roll"] - pc
        e2.append(d)
        de = (r["h_roll"] - pe) if pe is not None else None
        if de is not None:
            e2end.append(de)
        print(f"  {r['obs_month']:<12}{c:<12}{pc:>11.3f}{r['h_roll']:>10.3f}"
              f"{d:>+8.3f}"
              f"{(('%.3f' % pe) if pe is not None else '-'):>9}"
              f"{(('%+.3f' % de) if de is not None else '-'):>10}")
    if e2:
        print(f"  n {len(e2)}   MAE at centre {sum(abs(d) for d in e2)/len(e2)*100:.1f}pp"
              f"   mean error {sum(e2)/len(e2)*100:+.1f}pp")
    if e2end:
        print(f"           MAE at window end {sum(abs(d) for d in e2end)/len(e2end)*100:.1f}pp"
              f"   mean error {sum(e2end)/len(e2end)*100:+.1f}pp"
              "   <- the first version's mistake")

    print("\nTHE RECONSTRUCTED SERIES — every month the currency moved enough "
          "to identify it")
    print("  This is the primary output. Each row is one month's own reading, "
          "dated to\n  that month, owing nothing to any other month. The "
          "'+reserve' column adds the\n  FX volatility reserve's absorption to "
          "the derivative hedge.")
    print(f"  {'month':<12}{'fx result':>12}{'hedged':>9}{'+reserve':>10}")
    for r in rows:
        if r["h_month"] is None:
            continue
        wr = r["h_month_with_reserve"]
        print(f"  {r['obs_month']:<12}{r['fx_pl']/1000:>10,.0f}bn"
              f"{r['h_month']*100:>8.1f}%"
              f"{(('%.1f%%' % (wr*100)) if wr is not None else '-'):>10}"
              f"{'   carry assumed' if r['carry_imputed'] else ''}")

    print("\nRECONSTRUCTED SERIES, rolling, every third month")
    for r in rows[WINDOW - 1::3]:
        if r["h_roll"] is None:
            continue
        wr = r["h_roll_with_reserve"]
        print(f"  {r['obs_month']:<12} hedge {r['h_roll']*100:>6.1f}%   "
              f"+reserve {(('%6.1f%%' % (wr*100)) if wr is not None else '     -')}"
              f"   R2 {r['h_roll_r2']:.2f}   from {r['h_roll_centre']}"
              f"{'   CARRY ASSUMED' if r['h_roll_carry_imputed'] else ''}")

    sql_path = emit_sql(rows)
    print(f"\ncsv: {OUT_CSV.relative_to(ROOT)}   sql: {sql_path.relative_to(ROOT)}")
    return 0


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


NOTE_HEDGE = (
    "Regulatory hedge ratio implied by the release's own P&L lines: "
    "-(避險工具損益) / 兌換損益 for the month, both from tlfx.sector_monthly "
    "reporting_channel=release, differenced from year-to-date. Needs no "
    "exchange rate and no asset base, so the scope traps in the denominator "
    "series cannot reach it. Only months whose FX result exceeds NT$200bn are "
    "published: below that the ratio's noise swamps it. Validated against the "
    "published ratio on the three anchor months that clear the floor "
    "(MAE 4.4pp, mean error +0.8pp) and on all six months inside the published "
    "window (MAE 4.9pp, +3.1pp). The small positive bias is the scope gap "
    "between the P&L asset base and the regulatory denominator and is NOT "
    "calibrated out."
)
NOTE_OFFSET = (
    "Total P&L insulation from a currency move: -(避險工具損益 + net movement "
    "in 外匯價格變動準備) / 兌換損益, same months and same construction as "
    "reg_hedge_ratio_pl_implied. Above 1.0 means the month's hedges and reserve "
    "provisioning together more than offset the translation result, which "
    "happens when TWD weakens and firms provision into the reserve out of the "
    "gain. Not a regulatory measure; it has no published counterpart."
)
NOTE_CARRY = (
    " Months to 2019-10 additionally assume a swap carry of NT$16.54bn/month "
    "(the 2019 full-year cost / 12) because the release did not split the "
    "hedging line before 2019-11; the ratio moves ~5pp per NT$10bn of assumed "
    "carry, so these rows are basis=estimated on a second count."
)


def emit_sql(rows):
    """Idempotent load of the two implied series into derived_series."""
    out, now = [], dt.datetime.now(dt.timezone.utc).isoformat()
    for r in rows:
        if r["h_month"] is None:
            continue
        out.append(("reg_hedge_ratio_pl_implied", r["obs_month"], r["h_month"],
                    r["vintage"], r["carry_imputed"]))
        if r["h_month_with_reserve"] is not None:
            out.append(("fx_offset_total_pl_implied", r["obs_month"],
                        r["h_month_with_reserve"], r["vintage"],
                        r["carry_imputed"]))
    keys = [(key, month) for key, month, *_ in out]
    if len(keys) != len(set(keys)):
        raise SystemExit("natural-key collision")
    vals = ",\n  ".join("(" + ", ".join(sqlv(v) for v in row) + ")" for row in out)
    # The method note is the same sentence for every row of a key, so it is
    # written once and joined on, not repeated 38 times. The rows carry only
    # what actually varies: the month, the value, its vintage, and whether the
    # carry under it was assumed.
    sql = f"""-- stage5-implied: generated by scripts/stage5_implied_hedge_ratio.py at {now}. Idempotent.
begin;
with notes(series_key, note) as (values
  ('reg_hedge_ratio_pl_implied', {sqlv(NOTE_HEDGE)}),
  ('fx_offset_total_pl_implied', {sqlv(NOTE_OFFSET)})
), vals(series_key, obs_date, value, vintage, carry_imputed) as (values
  {vals})
insert into tlfx.derived_series
  (series_id, series_key, entity_id, obs_date, freq, value, unit,
   definition_version, basis, basis_note, source_url, source_doc,
   retrieved_at, vintage)
select 4::smallint, v.series_key, null, v.obs_date::date, 'M'::tlfx.frequency,
       v.value, 'ratio', 'v1_pl_implied', 'estimated',
       n.note || case when v.carry_imputed then {sqlv(NOTE_CARRY)} else '' end,
       'https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0,2',
       'Derived from FSC monthly release lines 兌換損益 / 避險工具損益 / '
       '外匯價格變動準備 as loaded in tlfx.sector_monthly (reporting_channel=release)',
       '{now}'::timestamptz, v.vintage::date
from vals v join notes n using (series_key)
on conflict (series_key, coalesce(entity_id, ''), obs_date, vintage) do nothing;
commit;
"""
    p = ROOT / "out" / f"stage5_implied_{dt.date.today():%Y%m%d}.sql"
    p.parent.mkdir(exist_ok=True)
    p.write_text(sql, encoding="utf-8")
    # Server-side verification compares against these, so print them per key.
    print(f"\nrows for derived_series: {len(out)}")
    for key in sorted({row[0] for row in out}):
        vs = [row[2] for row in out if row[0] == key]
        print(f"  {key:<32} n {len(vs):>3}   sum(value) {sum(vs):.4f}")
    return p


if __name__ == "__main__":
    sys.exit(main(json.load(sys.stdin)))
