#!/usr/bin/env python3
"""Stage 3a — Cathay Life quarterly deck -> FX hedging disclosures.

The "Cathay Life – FX hedging strategy" page of each results deck carries, on a
single page, everything series 1, 2, 5, 6 and 7 need at firm level:

    FX asset (NT$ tn)                    the denominator
    FX asset hedging structure           currency swap & NDF / proxy & open / FVOCI
    FX risk exposure vs reserve for FX policy   the FX-policy split
    Hedging cost                         five periods of history per deck
    FX volatility reserve                six periods of history per deck

Decks are listed at /holdings/ir/financial_information/results_presentation and
run back to 2011 Q4. **All of them are machine-readable text** — the README's
assumption that 2013–2019 would need hand-coding does not hold (decisions 3.1).

Extraction is positional, not order-of-appearance: the pie-chart percentages
appear in the text stream detached from their labels, so each value is paired
with the nearest label by page coordinates. The narrative sentence on the same
page ("… hedging cost was X%; FX volatility reserve … to NT$Ybn") is parsed
independently and used as a cross-check on two of the extracted figures; a
mismatch fails the row rather than being silently preferred.

  python3 scripts/stage3_cathay_decks.py --index          # refresh the deck index
  python3 scripts/stage3_cathay_decks.py --limit 8        # extract most recent 8
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pymupdf  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from tlfx.provenance import fetch  # noqa: E402

BASE = "https://www.cathayholdings.com"
LIST_URL = BASE + "/holdings/ir/financial_information/results_presentation"
INDEX = ROOT / "config" / "cathay_decks.json"
CACHE = ROOT / "cache" / "decks"

# Labels as they appear on the page, mapped to the field they qualify.
STRUCTURE_LABELS = {
    "currency swap & ndf": "hedge_cs_ndf_pct",
    "currency swap": "hedge_cs_ndf_pct",
    "proxy & open": "hedge_proxy_open_pct",
    "proxy": "hedge_proxy_open_pct",
    "fvoci": "hedge_fvoci_pct",
}
# Fragments, not full phrases: the captions wrap across text blocks, so the
# full phrase is often split between blocks and never matches whole.
SPLIT_LABELS = {
    "fx risk": "fx_risk_exposure_pct",
    "risk exposure": "fx_risk_exposure_pct",
    "fx policy": "fx_policy_reserve_pct",
}


def build_index() -> list[dict]:
    fr = fetch(LIST_URL, source_doc="Cathay results presentations", timeout=60, basis="disclosed")
    soup = BeautifulSoup(fr.content, "lxml")
    recs: list[dict] = []
    for row in soup.find_all("div", class_=lambda c: c and "border-bottom-light-grey" in c):
        text = re.sub(r"\s+", " ", row.get_text(" ", strip=True))
        m = re.match(r"(20\d\d/\d\d/\d\d)\s+(.*?)\s*(?:Webcast|PDF)", text)
        if not m:
            continue
        pdf = next((a["href"] for a in row.find_all("a", href=True) if ".pdf" in a["href"].lower()), None)
        if pdf:
            recs.append({"date": m.group(1), "title": m.group(2),
                         "lang": "en" if "英文" in m.group(2) else "zh",
                         "pdf": BASE + pdf})
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(recs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return recs


def deck_bytes(rec: dict) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9]+", "_", rec["date"] + "_" + rec["lang"]) + ".pdf"
    path = CACHE / key
    if path.exists():
        return path.read_bytes()
    fr = fetch(rec["pdf"], source_doc=f"Cathay deck {rec['date']}", timeout=150, basis="disclosed")
    path.write_bytes(fr.content)
    return fr.content


def find_fx_page(doc) -> int | None:
    """The quarterly FX hedging page: the FIRST page naming the FX asset base
    alongside a hedging-instrument caption.

    Most decks carry two qualifying pages — the quarterly page in the body
    (pages ~23–28) and a "Dynamic hedging strategy" appendix whose long-history
    chart has no numeric text layer. The body page always precedes the appendix,
    so taking the first candidate selects correctly in every vintage sampled;
    keyword *scoring* preferred the appendix in four of them (decisions 3.1).
    """
    for i, page in enumerate(doc):
        low = page.get_text().lower()
        if ("fx asset" in low or "fx assets" in low) and                 any(k in low for k in ("ndf", "proxy", "fvoci", "currency swap")):
            return i
    return None


def pie_slices(page) -> list[tuple[float, float]]:
    """Centroids of the filled wedges that make up the page's pie charts.

    Filters out the page background, the banner bars and the bar-chart columns,
    which are the other filled shapes on the page, by size and aspect ratio.
    """
    out = []
    for d in page.get_drawings():
        if d.get("fill") is None:
            continue
        r = d["rect"]
        w, h = r.width, r.height
        if not (18 < w < 180 and 18 < h < 180):
            continue
        if not (0.3 < w / h < 3.0):
            continue
        out.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
    return out


def pair_by_position(page, labels: dict[str, str]) -> dict[str, float]:
    """Bind each percentage to its caption *through the pie wedge it sits in*.

    Pairing a value straight to its nearest caption fails on these charts: the
    captions sit outside the pie on leader lines, so a value inside one wedge can
    be closer to a neighbouring wedge's caption. Verified on the 2Q26 deck, where
    direct pairing swaps the 60% and 4% shares. Going through the wedge is
    unambiguous in both directions — value to wedge and caption to wedge each
    resolve with a clear margin — so the join is made on the wedge.
    """
    slices = pie_slices(page)
    if not slices:
        return {}
    words = [(w[4], ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)) for w in page.get_text("words")]

    def nearest_slice(pt):
        return min(range(len(slices)), key=lambda i: math.dist(slices[i], pt))

    # caption -> wedge, using the centroid of the words making up each caption
    blocks = [(re.sub(r"\s+", " ", b[4].strip().lower()), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
              for b in page.get_text("blocks")]
    wedge_field: dict[int, str] = {}
    for text, pt in blocks:
        for lab, field in labels.items():
            if lab in text:
                wedge_field.setdefault(nearest_slice(pt), field)

    out: dict[str, float] = {}
    for token, pt in words:
        if not re.fullmatch(r"\d{1,3}(?:\.\d{1,2})?%", token):
            continue
        field = wedge_field.get(nearest_slice(pt))
        if field:
            out.setdefault(field, float(token.rstrip("%")))
    return out


def extract(doc, page_no: int) -> dict:
    page = doc[page_no]
    text = page.get_text()
    flat = re.sub(r"\s+", " ", text)
    row: dict = {"fx_page": page_no + 1}

    # "NT$5.54TN" in 2025-26 decks, "NT$5.53TR" in 2024 ones
    if m := re.search(r"FX assets?\s*NT\$\s*([\d.]+)\s*T[NR]", flat, re.I):
        row["fx_assets_ntd_tn"] = float(m.group(1))

    # One combined pass: the structure and exposure pies sit on the same page,
    # and in 2024-25 vintages the structure pie's values are graphics with no
    # text layer. Run separately, the value-less structure captions can claim
    # the exposure pie's wedges and mislabel its 69/31. With all captions
    # competing at once, each wedge goes to its nearest caption and the
    # exposure values land on the exposure fields.
    row.update(pair_by_position(page, {**STRUCTURE_LABELS, **SPLIT_LABELS}))

    # narrative / labelled cost line — wording varies by era:
    #   "1H26 hedging cost was 1.21%"   (2026)
    #   "1H25 Hedging cost 1.45%"       (2024-25, with its period label)
    if m := re.search(r"((?:FY|1H|9M|[1-4]Q)\d\d)?\s*hedging cost(?: was)?\s*(?:of\s*)?([\d.]+)\s*%", flat, re.I):
        row["hedging_cost_pct_narrative"] = float(m.group(2))
        if m.group(1):
            row["hedging_cost_period"] = m.group(1)
    if m := re.search(r"FX volatility reserve.*?to NT\$([\d,.]+)\s*bn", flat, re.I):
        row["fx_volatility_reserve_ntd_bn_narrative"] = float(m.group(1).replace(",", ""))

    # snapshot as-of date: some vintages date the structure pie to a month end
    # that is not the reporting quarter end (the March 2026 deck says 2026/1/31)
    if m := re.search(r"(20\d\d/\d{1,2}/\d{1,2})\s*FX asset hedging structure", flat, re.I):
        row["structure_asof"] = m.group(1)

    # validity: the three structure shares should account for the whole pie
    shares = [row.get(k) for k in ("hedge_cs_ndf_pct", "hedge_proxy_open_pct", "hedge_fvoci_pct")]
    if all(v is not None for v in shares):
        row["structure_sums_to"] = round(sum(shares), 1)

    # period-labelled history strips
    periods = re.findall(r"\b((?:FY|1H|9M|[1-4]Q)\d{2})\b", flat)
    row["periods_on_page"] = sorted(set(periods))
    return row


def validate(row: dict) -> dict:
    """Keep only field values that pass era-independent plausibility rules.

    The wedge binding is geometric and occasionally captures a nearby yield or
    cost figure into a share field. Shares are only published when their pie
    closes (sums to ~100), except CS & NDF alone, which is kept when it is
    unambiguously share-sized. Costs are kept only from the labelled or
    narrative sentence forms, which are regex-anchored rather than geometric.
    """
    out: dict = {"fx_page": row.get("fx_page")}
    if v := row.get("fx_assets_ntd_tn"):
        out["fx_assets_ntd_tn"] = v
    exp, pol = row.get("fx_risk_exposure_pct"), row.get("fx_policy_reserve_pct")
    if exp is not None and pol is not None and 95 <= exp + pol <= 105:
        out["fx_risk_exposure_pct"], out["fx_policy_reserve_pct"] = exp, pol
    shares = [row.get(k) for k in ("hedge_cs_ndf_pct", "hedge_proxy_open_pct", "hedge_fvoci_pct")]
    if all(v is not None for v in shares) and 95 <= sum(shares) <= 105:
        out["hedge_cs_ndf_pct"], out["hedge_proxy_open_pct"], out["hedge_fvoci_pct"] = shares
    elif (v := row.get("hedge_cs_ndf_pct")) is not None and 30 <= v <= 85:
        out["hedge_cs_ndf_pct"] = v
    if (c := row.get("hedging_cost_pct_narrative")) is not None and 0.1 <= c <= 3.5:
        out["hedging_cost_pct"] = c
        if row.get("hedging_cost_period"):
            out["hedging_cost_period"] = row["hedging_cost_period"]
    if (r := row.get("fx_volatility_reserve_ntd_bn_narrative")) is not None:
        out["fx_volatility_reserve_ntd_bn"] = r
    if row.get("structure_asof"):
        out["structure_asof"] = row["structure_asof"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", action="store_true", help="refresh the deck index and exit")
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--lang", default="en", choices=("en", "zh"))
    ap.add_argument("--csv", action="store_true",
                    help="write validated rows to data/cathay_deck_fx.csv")
    args = ap.parse_args()

    if args.index or not INDEX.exists():
        recs = build_index()
        print(f"indexed {len(recs)} decks: {recs[-1]['date']} .. {recs[0]['date']} -> {INDEX.relative_to(ROOT)}")
        if args.index:
            return 0
    else:
        recs = json.loads(INDEX.read_text(encoding="utf-8"))

    picked = [r for r in recs if r["lang"] == args.lang][: args.limit]
    emitted: list[dict] = []
    print(f"{'deck':<12}{'pg':>4}{'FX assets':>11}{'CS+NDF':>8}{'proxy':>7}{'FVOCI':>7}{'sum':>6}"
          f"{'exp%':>6}{'pol%':>6}{'cost%':>7}{'reserve':>9}  asof")
    for rec in picked:
        try:
            doc = pymupdf.open(stream=deck_bytes(rec), filetype="pdf")
        except Exception as exc:
            print(f"{rec['date']:<12} ERR {type(exc).__name__}")
            continue
        pg = find_fx_page(doc)
        if pg is None:
            print(f"{rec['date']:<12}   —  (no FX hedging page matched)")
            continue
        raw = extract(doc, pg)
        r = validate(raw) if args.csv else raw
        if args.csv:
            r = {"deck_date": rec["date"].replace("/", "-"), "deck_title": rec["title"],
                 "pdf_url": rec["pdf"], **r}
            emitted.append(r)
        f = lambda k, s="": f"{r[k]:g}{s}" if k in r else "—"
        print(f"{rec['date']:<12}{r['fx_page']:>4}{f('fx_assets_ntd_tn','tn'):>11}"
              f"{f('hedge_cs_ndf_pct','%'):>8}{f('hedge_proxy_open_pct','%'):>7}{f('hedge_fvoci_pct','%'):>7}"
              f"{f('structure_sums_to'):>6}"
              f"{f('fx_risk_exposure_pct','%'):>6}{f('fx_policy_reserve_pct','%'):>6}"
              f"{f('hedging_cost_pct_narrative','%') if not args.csv else f('hedging_cost_pct','%'):>7}"
              f"{f('fx_volatility_reserve_ntd_bn_narrative','bn') if not args.csv else f('fx_volatility_reserve_ntd_bn','bn'):>9}"
              f"  {r.get('structure_asof','')}")
    if args.csv and emitted:
        import csv as _csv
        out = ROOT / "data" / "cathay_deck_fx.csv"
        cols = ["deck_date", "fx_page", "fx_assets_ntd_tn", "hedge_cs_ndf_pct",
                "hedge_proxy_open_pct", "hedge_fvoci_pct", "fx_risk_exposure_pct",
                "fx_policy_reserve_pct", "hedging_cost_pct", "hedging_cost_period",
                "fx_volatility_reserve_ntd_bn", "structure_asof", "deck_title", "pdf_url"]
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(emitted)
        print(f"csv: {out.relative_to(ROOT)} ({len(emitted)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
