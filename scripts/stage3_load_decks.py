#!/usr/bin/env python3
"""Load the Fubon and KGI deck series into tlfx.firm_quarterly (deck channel).

Consolidates data/fubon_deck_fx.csv + data/fubon_recurring_cost.csv and
data/kgi_deck_fx.csv into one row per (entity, period), mapped as:

Fubon:
  total_fx_cost_bp  — sign-normalised all-in FX result: the sum of verified
    components where they exist (signs are printed properly there); otherwise
    the printed value only when negative (2014-15 print costs unsigned, and a
    bare positive is ambiguous between that convention and a genuine 2022-style
    net gain, so unsigned-positive unverified rows are SKIPPED, not guessed).
  hedge_cost_bp     — recurring cost as positive bp (Cathay convention),
    only from sum-verified colour-bound rows (decisions 3.17).
  fx_reserve_balance — 外價金 NT$ bn -> mn (2025-era on).
  fx_risk/fx_policy share columns; everything else -> deck_composition jsonb.

KGI:
  recurring_yield_pre, fx_reserve_balance, composition pie (+ fx_risk/policy).
  KGI's 避險成本 stays OUT of the database until its definition is pinned
  (decisions 3.16) — it lives only in data/kgi_deck_fx.csv.

vintage = the period's own deck upload timestamp (14-digit filename stamp);
period end when no stamp exists (older Fubon filenames), noted per row.
"""
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Q_START = {3: "01-01", 6: "04-01", 9: "07-01", 12: "10-01"}
Q_END = {3: "03-31", 6: "06-30", 9: "09-30", 12: "12-31"}


def period_parts(p):
    """'1Q25'/'1H26'/'9M24'/'2020'/'23' -> (year, end_month)."""
    if re.fullmatch(r"20\d\d", p):
        return int(p), 12
    if re.fullmatch(r"\d\d", p):
        return 2000 + int(p), 12
    m = re.fullmatch(r"([1-4])Q(\d\d)", p)
    if m:
        return 2000 + int(m.group(2)), int(m.group(1)) * 3
    m = re.fullmatch(r"1H(\d\d)", p)
    if m:
        return 2000 + int(m.group(1)), 6
    m = re.fullmatch(r"9M(\d\d)", p)
    if m:
        return 2000 + int(m.group(1)), 9
    raise ValueError(p)


def stamp(url):
    m = re.search(r"/(\d{14})-\d\.pdf", url)
    return f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}" if m else None


def sqlv(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def num(s):
    return None if s in (None, "") else float(s)


def fubon_rows():
    rec = {}
    with open(ROOT / "data" / "fubon_recurring_cost.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rec[r["period"]] = r
    per = {}
    with open(ROOT / "data" / "fubon_deck_fx.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = r["period"]
            cur = per.setdefault(p, {"period": p, "urls": []})
            cur["urls"].append((r["url"], r["lang"]))
            for k in ("total_fx_cost_bps", "fx_reserve_ntd_bn", "fx_assets_bond_pct",
                      "cs_ndf_policy_pct", "cs_ndf_pct", "naked_usd_pct",
                      "naked_other_pct", "naked_usd_other_pct", "equity_fund_pct",
                      "fvoci_equity_pct", "fvtpl_equity_pct", "components_ok",
                      "cost_components"):
                if r.get(k) not in (None, ""):
                    cur.setdefault(k, r[k])
    out, skipped = [], []
    for p, c in sorted(per.items()):
        y, em = period_parts(p)
        printed = num(c.get("total_fx_cost_bps"))
        comps = json.loads(c.get("cost_components", "[]") or "[]")
        rrow = rec.get(p) if rec.get(p, {}).get("sum_ties_total") == "True" else None
        if comps and c.get("components_ok") == "True":
            total = float(sum(comps))
        elif rrow:
            # colour-bound, sum-verified components from sibling decks carry
            # the true signs even where this deck prints the total unsigned
            total = float(sum(num(rrow[k]) for k in ("recurring_bps", "fxgl_bps", "oneoff_bps")
                              if rrow.get(k) not in (None, "")))
        elif printed is not None and printed < 0:
            total = printed
        elif printed is not None:
            skipped.append(f"fubon {p}: unsigned-positive total {printed} unverified")
            total = None
        else:
            total = None
        comp = {k: num(c[k]) for k in ("cs_ndf_policy_pct", "cs_ndf_pct",
                                       "naked_usd_pct", "naked_other_pct",
                                       "naked_usd_other_pct", "equity_fund_pct",
                                       "fvoci_equity_pct", "fvtpl_equity_pct",
                                       "fx_assets_bond_pct") if c.get(k)}
        url = sorted(c["urls"], key=lambda t: t[1] != "CH")[0][0]
        v = stamp(url)
        out.append({
            "entity": "fubon_life", "obs": f"{y}-{Q_START[em]}",
            "vintage": v or f"{y}-{Q_END[em]}",
            "vnote": "deck upload stamp" if v else "period end (no stamp in filename)",
            "basis": "IFRS17" if y >= 2026 else "IFRS4",
            "total_bp": total,
            "hedge_bp": -num(rrow["recurring_bps"]) if rrow else None,
            "reserve_mn": num(c.get("fx_reserve_ntd_bn")) and num(c["fx_reserve_ntd_bn"]) * 1000,
            "yield_pre": None,
            "fx_risk": None, "fx_policy": None,
            "comp": comp or None, "url": url, "period": p,
        })
    return out, skipped


def kgi_rows():
    per = {}
    deck_url = {}
    rows = list(csv.DictReader(open(ROOT / "data" / "kgi_deck_fx.csv", encoding="utf-8")))
    for r in rows:
        dp = r["deck_period"] or ""
        try:
            y, em = period_parts(dp)
            key = (y, em)
            if key not in deck_url or r["lang"] == "CH":
                deck_url[key] = r["url"]
        except ValueError:
            pass
        for field, col in (("yield_pre_hedge_pct_series", "yield_pre"),
                           ("fx_reserve_ntd_bn_series", "reserve_bn")):
            for p, v in json.loads(r[field] or "{}").items():
                y, em = period_parts(p)
                per.setdefault((y, em), {})[col] = v
        # pie belongs to the deck's own period
        try:
            y, em = period_parts(dp)
        except ValueError:
            continue
        cur = per.setdefault((y, em), {})
        for k in ("cs_ndf_pct", "naked_usd_other_pct", "overseas_equity_pct"):
            if r.get(k):
                cur.setdefault("comp", {})[k] = float(r[k])
        for k, col in (("fx_risk_pct", "fx_risk"), ("fx_policy_pct", "fx_policy")):
            if r.get(k):
                cur[col] = float(r[k])
    out = []
    for (y, em), c in sorted(per.items()):
        url = deck_url.get((y, em))
        v = stamp(url) if url else None
        out.append({
            "entity": "kgi_life", "obs": f"{y}-{Q_START[em]}",
            "vintage": v or f"{y}-{Q_END[em]}",
            "vnote": "deck upload stamp" if v else "period end (figure from later decks' charts)",
            "basis": "IFRS17" if y >= 2026 else "IFRS4",
            "total_bp": None, "hedge_bp": None,
            "reserve_mn": c.get("reserve_bn") and c["reserve_bn"] * 1000,
            "yield_pre": c.get("yield_pre"),
            "fx_risk": c.get("fx_risk"), "fx_policy": c.get("fx_policy"),
            "comp": c.get("comp"),
            "url": url or "https://cdf.irpro.co/tw/investor-conference.php",
            "period": f"{y}-{em:02d}",
        })
    return out


def main():
    fub, skipped = fubon_rows()
    kgi = kgi_rows()
    rows = fub + kgi
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    vals = ",\n  ".join(
        "(" + ", ".join([
            sqlv(r["entity"]), sqlv(r["obs"]), sqlv(r["vintage"]), sqlv(r["basis"]),
            sqlv(r["total_bp"]), sqlv(r["hedge_bp"]), sqlv(r["reserve_mn"]),
            sqlv(r["yield_pre"]), sqlv(r["fx_risk"]), sqlv(r["fx_policy"]),
            sqlv(json.dumps(r["comp"], ensure_ascii=False) if r["comp"] else None),
            sqlv(r["url"]),
            sqlv(f"results deck series, period {r['period']}; vintage = {r['vnote']}"),
        ]) + ")" for r in rows)
    sql = f"""-- stage3-decks: generated by scripts/stage3_load_decks.py at {now}. Idempotent.
begin;
with vals(entity_id, obs_quarter, vintage, basis, total_bp, hedge_bp, reserve_mn,
          yield_pre, fx_risk, fx_policy, comp, url, note) as (values
  {vals})
insert into tlfx.firm_quarterly
  (entity_id, obs_quarter, vintage, basis, source_channel, total_fx_cost_bp,
   hedge_cost_bp, fx_reserve_balance, recurring_yield_pre, fx_risk_share_pct,
   fx_policy_share_pct, deck_composition, source_url, source_doc, source_note,
   retrieved_at)
select entity_id, obs_quarter::date, vintage::date, basis::tlfx.accounting_basis,
  'deck', total_bp, hedge_bp, reserve_mn, yield_pre, fx_risk, fx_policy,
  comp::jsonb, url,
  case entity_id when 'fubon_life' then '富邦金控 results decks (fubon.irpro.co), Fubon Life hedging page'
                 else '凱基金控 results decks (cdf.irpro.co), KGI Life investment-performance page' end,
  note, '{now}'::timestamptz
from vals
on conflict (entity_id, obs_quarter, basis, source_channel, vintage) do nothing;
commit;
"""
    tag = dt.date.today().strftime("%Y%m%d")
    out = ROOT / "out" / f"stage3_decks_{tag}.sql"
    out.write_text(sql, encoding="utf-8")

    def s(key, sub):
        return round(sum(r[key] or 0 for r in rows if r["entity"] == sub), 3)
    print(f"rows: {len(rows)} (fubon {len(fub)}, kgi {len(kgi)}); skipped: {len(skipped)}")
    for x in skipped:
        print("  SKIP", x)
    print(f"checksums fubon: sum total_bp {s('total_bp','fubon_life')}; "
          f"sum hedge_bp {s('hedge_bp','fubon_life')}; sum reserve_mn {s('reserve_mn','fubon_life')}")
    print(f"checksums kgi: sum reserve_mn {s('reserve_mn','kgi_life')}; "
          f"sum yield_pre {s('yield_pre','kgi_life')}")
    print(f"sql: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
