#!/usr/bin/env python3
"""Regression tests for the statement-note parsers, on real filing text.

Every one of these fixtures is text lifted verbatim from a filing, and every
one of them exists because a parser got it wrong first. They are the only
defence against the failure mode this extraction actually has: output that is
plausible, correctly shaped, right order of magnitude, and wrong.

Run: python3 tests/test_note_parsers.py
"""
import importlib.util
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"

spec = importlib.util.spec_from_file_location(
    "s6", ROOT / "scripts" / "stage6_firm_sensitivity.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def flat(name):
    raw = (FIX / name).read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", raw))


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}: {got!r}"
          + ("" if ok else f"  want {want!r}"))
    return ok


def test_fubon_notionals():
    """Notional is the SECOND number after the instrument; 匯率交換合約 is 84%."""
    print("\nfubon 113Q4 derivatives note")
    rows = m.parse_note(flat("fubon_113q4_derivatives_note.txt"))
    got = {(r["as_of"], r["instrument"]): r["notional_ntd_k"] for r in rows}
    ok = check("row count", len(rows), 10)
    ok &= check("2024 遠期外匯合約", got.get(("2024-12-31", "遠期外匯合約")), 198008832.0)
    ok &= check("2024 匯率交換合約", got.get(("2024-12-31", "匯率交換合約")), 1213827456.0)
    ok &= check("2023 匯率交換合約", got.get(("2023-12-31", "匯率交換合約")), 1185408963.0)
    # reconciles to the printed 合計 less 其他, which the parser does not read
    ok &= check("2024 sum", sum(v for (d, _), v in got.items() if d == "2024-12-31"),
                1437334557.0)
    trad = sum(r["notional_ntd_k"] for r in rows
               if r["as_of"] == "2024-12-31" and r["traditional"])
    ok &= check("2024 傳統避險本金", trad, 1434209710.0)
    return ok


def test_fubon_sensitivity():
    """One combined table; 50BPS and 3% shocks, not 1bp and 1%."""
    print("\nfubon 113Q4 sensitivity")
    f = flat("fubon_113q4_sensitivity.txt")
    heads = [(x.start(), f"{1911 + int(x.group(1))}-{int(x.group(2)):02d}-"
              f"{int(x.group(3)):02d}") for x in m.PERIOD.finditer(f)]
    rows = []
    for pat, tb, lab in ((m.RATE_ROW, "rate", None), (m.FX_ROW, "fx", None),
                         (m.EQ_ROW, "equity", "價格指數")):
        for x in pat.finditer(f):
            v = m.numbers(f[x.end(): x.end() + 90], 2)
            if len(v) < 2:
                continue
            d = next((y for pos, y in reversed(heads) if pos < x.start()), None)
            label = (lab or (x.group(1) if tb == "rate"
                             else f"{x.group(1)}/{x.group(2)}"))
            shock = (f"{x.group(3)}bp" if tb == "rate" else
                     f"{x.group(4)}%" if tb == "fx" else f"{x.group(2)}%")
            direction = x.group(2) if tb != "fx" else x.group(3)
            rows.append((d, tb, label, direction, v[0], v[1]))
    ok = check("row count", len(rows), 20)
    g = {(a, b, c, d): (e, f2) for a, b, c, d, e, f2 in rows}
    ok &= check("2024 USD +50bp", g.get(("2024-12-31", "rate", "美元", "上移")),
                (-10491.0, -33214324.0))
    ok &= check("2023 USD +50bp", g.get(("2023-12-31", "rate", "美元", "上移")),
                (-10365.0, -29985054.0))
    ok &= check("2024 TWD +3% FX", g.get(("2024-12-31", "fx", "新台幣/所有外幣", "升值")),
                (-19576217.0, -14386749.0))
    return ok


def test_taiwan_life_by_currency():
    """Notionals stated by currency in FX thousands, with no NT$ column."""
    print("\ntaiwan life 114Q4 notionals by currency")
    rows = m.parse_note_by_currency(flat("taiwan_life_114q4_notional_by_ccy.txt"))
    got = {(r["as_of"], r["instrument"], r["currency"]): r["notional_ccy_k"]
           for r in rows}
    ok = check("row count", len(rows), 16)
    ok &= check("2025 CCS USD", got.get(("2025-12-31", "匯率交換合約", "USD")), 5775000.0)
    ok &= check("2025 fwd USD", got.get(("2025-12-31", "遠期外匯合約", "USD")), 12165040.0)
    ok &= check("2025 fwd JPY", got.get(("2025-12-31", "遠期外匯合約", "JPY")), 4000000.0)
    # a "-" is a genuine absence, not a zero to be carried
    ok &= check("2025 CCS AUD absent", ("2025-12-31", "匯率交換合約", "AUD") in got, False)
    ok &= check("2024 CCS AUD present", got.get(("2024-12-31", "匯率交換合約", "AUD")), 35000.0)
    ok &= check("2024 fwd THB absent", ("2024-12-31", "遠期外匯合約", "THB") in got, False)
    return ok


def test_cathay_ifrs17():
    """Eight columns, 1bp and 1% shocks, subtotals that must add up."""
    print("\ncathay 115Q2 sensitivity (IFRS 17 split)")
    rows = m.parse_sensitivity_ifrs17(flat("cathay_115q2_sensitivity.txt"))
    ok = check("row count", len(rows), 2)
    by = {r["table"]: r for r in rows}
    ok &= check("rate shock", by.get("rate", {}).get("shock"), "1bp")
    ok &= check("fx shock", by.get("fx", {}).get("shock"), "1%")
    ok &= check("rate direction", by.get("rate", {}).get("direction"), "上升")
    ok &= check("rate equity total", by.get("rate", {}).get("equity_ntd_k"), 5585966.0)
    ok &= check("fx pnl total", by.get("fx", {}).get("pnl_ntd_k"), 19230112.0)
    for r in rows:
        sp = (r["pnl_insurance_ntd_k"] + r["pnl_reinsurance_ntd_k"]
              + r["pnl_instruments_ntd_k"])
        se = (r["eq_insurance_ntd_k"] + r["eq_reinsurance_ntd_k"]
              + r["eq_instruments_ntd_k"])
        ok &= check(f"{r['table']} P&L adds up", sp, r["pnl_ntd_k"])
        ok &= check(f"{r['table']} equity adds up", se, r["equity_ntd_k"])
    return ok


def test_nanshan_trailing_parens():
    """Accounting marks TRAIL the number; the middle column is negative."""
    print("\nnan shan 115Q2 FX sensitivity (trailing parentheses)")
    rows = m.parse_sensitivity_nanshan(flat("nanshan_115q2_fx_sensitivity.txt"))
    ok = check("row count", len(rows), 6)
    if len(rows) != 6:
        return ok
    a, b, c, d, e, _ = rows
    ok &= check("assets, TWD +5%",
                (a["pnl_ntd_k"], a["oci_ntd_k"], a["equity_ntd_k"]),
                (36169702.0, -950095.0, 35219607.0))
    ok &= check("insurance liabilities, TWD +5%",
                (b["pnl_ntd_k"], b["oci_ntd_k"], b["equity_ntd_k"]),
                (-36971568.0, -169395.0, -37140963.0))
    # the FX reserve absorbs the whole P&L effect (100% offset from 2025-05)
    ok &= check("company total P&L is nil", c["pnl_ntd_k"], 0.0)
    ok &= check("company total equity", c["equity_ntd_k"], -1119490.0)
    # depreciation must mirror appreciation exactly, or a sign was misread
    ok &= check("assets mirror", (d["pnl_ntd_k"], d["equity_ntd_k"]),
                (-a["pnl_ntd_k"], -a["equity_ntd_k"]))
    ok &= check("liabilities mirror", (e["pnl_ntd_k"], e["equity_ntd_k"]),
                (-b["pnl_ntd_k"], -b["equity_ntd_k"]))
    return ok


def test_nanshan_notionals():
    """Asset/liability blocks summed; instruments carry no 合約 suffix."""
    print("\nnan shan 115Q2 derivatives note (asset/liability blocks)")
    rows = m.parse_note_nanshan(flat("nanshan_115q2_notional.txt"))
    ok = check("row count", len(rows), 12)
    agg = {}
    for r in rows:
        agg[r["as_of"]] = agg.get(r["as_of"], 0.0) + r["notional_ntd_k"]
    # each equals the filing's own printed subtotal for assets plus liabilities
    ok &= check("2026-06-30 total", agg.get("2026-06-30"), 1510111252.0)
    ok &= check("2025-12-31 total", agg.get("2025-12-31"), 1634729164.0)
    ok &= check("2025-06-30 total", agg.get("2025-06-30"), 2008817182.0)
    # the asset/liability split inverts after the May 2025 TWD appreciation:
    # short-USD hedges that were liabilities become assets
    a26 = sum(r["notional_ntd_k"] for r in rows
              if r["as_of"] == "2026-06-30" and r["side"] == "金融資產")
    a25 = sum(r["notional_ntd_k"] for r in rows
              if r["as_of"] == "2025-06-30" and r["side"] == "金融資產")
    ok &= check("asset side 2026-06 < 2025-06", a26 < a25, True)
    return ok


def test_numbers():
    """A bare comma is not a number; a bare dash is a nil."""
    print("\nnumber parsing")
    ok = check("stray commas", m.numbers(", , ,", 4), [])
    ok &= check("parens negative", m.numbers("$ 144,217 ( 2,905 )", 2),
                [144217.0, -2905.0])
    ok &= check("dash is nil", m.numbers("- 1,000", 2), [0.0, 1000.0])
    return ok


def main():
    tests = [test_numbers, test_fubon_notionals, test_fubon_sensitivity,
             test_taiwan_life_by_currency, test_cathay_ifrs17,
             test_nanshan_trailing_parens,
             test_nanshan_notionals]
    results = [(t.__name__, t()) for t in tests]
    print("\n" + "=" * 60)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
