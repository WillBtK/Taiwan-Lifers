#!/usr/bin/env python3
"""Per-firm FX hedge notionals from the statutory statements, via MOPS.

WHY THIS EXISTS
---------------
4.36 established that Shin Kong Life's quarterly statements disclose the
notional principal of its FX hedges — the exact figure this project spent days
concluding was unpublished — and that the two disclosures in the filing (a NT$
total in the currency-risk note, a USD swap/forward split in the derivatives
note) reconcile at period-end spot to four decimals. The open question was
whether that is one firm's habit or a sector-wide disclosure.

Answering it needs the filings, and the insurers' own IR sites are a poor route:
Nan Shan's is a single-page app whose report API refuses an unauthenticated
POST, Shin Kong's index returns 403, and each firm's URL scheme differs. MOPS is
the uniform one. Every insurer — listed, unlisted-but-public, and the life
subsidiaries of the financial holding companies — files there under its own
company code, and **the life subsidiary files separately from its parent**:
新光人壽 is 28880001, not 2888. That is the fact that makes a panel possible,
because the parent's consolidated report buries the insurer inside a bank.

THE DISCLOSURE, AND THE TRAP
----------------------------
Take notionals from the DERIVATIVES / currency-risk notes, never from the
hedge-accounting table headed 避險工具. Under IFRS that table lists only
instruments formally designated for hedge accounting, and Taiwanese lifers
mostly do not designate: Cathay's designated forward notional is NT$49bn
against NT$5.5tn of foreign assets, and Fubon's XBRL hedging-instrument asset
is NT$0.7bn against NT$3.4tn. Shin Kong is legible precisely because it states
「並未採用避險會計」 and so reports its economic hedges in the currency-risk
note instead. A firm that says nothing there has not necessarily hedged
nothing — it may have designated, or disclosed elsewhere — so a null here is
recorded as unknown, never as zero.

RATE
----
TWSE sits behind a WAF that resets connections under load; an earlier crawl in
this project was withdrawn as impractical at roughly twelve minutes a quarter.
So: one request every REQUEST_GAP seconds, every response cached to disk, and
the cache consulted before the network. A re-run costs nothing and a partial
run resumes.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "mops_stmt"
OUT = ROOT / "reports" / "mops_statements.json"
DOC = "https://doc.twse.com.tw/server-java/t57sb01"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
REQUEST_GAP = 3.0

# Financial holding companies whose life subsidiary files its own statements,
# plus the insurers that file directly. The subsidiary codes are discovered
# rather than assumed — MOPS lists them on the parent's filing page — but the
# ones already found are pinned so a re-run does not re-derive them.
PARENTS = {"2882": "國泰金", "2881": "富邦金", "2888": "新光金",
           "2891": "中信金", "2883": "凱基金", "2823": "中壽"}
KNOWN_LIFE = {"28880001": "新光人壽", "28910031": "台灣人壽"}

_last = [0.0]


def fetch(**form):
    """One cached, rate-limited POST to the MOPS document server."""
    key = urllib.parse.urlencode(sorted(form.items()))
    p = CACHE / (re.sub(r"[^A-Za-z0-9_=&.-]+", "_", key)[:150] + ".html")
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    gap = REQUEST_GAP - (time.time() - _last[0])
    if gap > 0:
        time.sleep(gap)
    req = urllib.request.Request(
        DOC, data=urllib.parse.urlencode(form).encode(),
        headers={"User-Agent": UA, "Referer": "https://doc.twse.com.tw/",
                 "Content-Type": "application/x-www-form-urlencoded"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read()
            _last[0] = time.time()
            text = body.decode("big5", "replace")
            CACHE.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            return text
        except Exception as e:
            _last[0] = time.time()
            if attempt == 2:
                return f"__ERROR__ {type(e).__name__}: {e}"
            time.sleep(5 * (attempt + 1))


def rows_of(text):
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        c = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).replace("\xa0", " ").strip()
             for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        c = [x for x in c if x]
        if c:
            out.append(c)
    return out


def life_subsidiaries(parent, year="113"):
    """The life-insurance subsidiaries MOPS lists under a holding company."""
    t = fetch(step="1", colorchg="1", co_id=parent, year=year, seamon="", mtype="A")
    if t.startswith("__ERROR__"):
        return [], t
    got = []
    for c in rows_of(t):
        if len(c) >= 2 and re.fullmatch(r"\d{4,8}", c[0]) and "壽" in c[1]:
            got.append((c[0], c[1]))
    return got, None


def filings(co_id, year):
    """Filing rows for one company-year, with the readfile() filenames."""
    t = fetch(step="1", colorchg="1", co_id=co_id, year=str(year), seamon="", mtype="A")
    if t.startswith("__ERROR__"):
        return [], t
    calls = re.findall(r"readfile2?\('([^']*)','([^']*)','([^']*)'\)", t)
    return [{"kind": k, "co_id": c, "filename": f} for k, c, f in calls], None


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    report = {"life_subsidiaries": {}, "filings": {}, "errors": []}

    print("Life subsidiaries listed under each holding company (MOPS):")
    life = dict(KNOWN_LIFE)
    for parent, name in PARENTS.items():
        got, err = life_subsidiaries(parent)
        if err:
            report["errors"].append({"parent": parent, "error": err[:120]})
            print(f"  {parent} {name:<8} ERROR {err[:70]}")
            continue
        report["life_subsidiaries"][parent] = got
        for code, nm in got:
            life[code] = nm
        print(f"  {parent} {name:<8} {got if got else '(none listed)'}")

    print(f"\nLife-insurer company codes to pull: {life}")
    for code, nm in sorted(life.items()):
        for year in (113, 112):
            f, err = filings(code, year)
            if err:
                report["errors"].append({"co_id": code, "year": year, "error": err[:120]})
                print(f"  {code} {nm} {year}: ERROR")
                continue
            report["filings"].setdefault(code, {})[year] = f
            print(f"  {code} {nm:<10} ROC{year}: {len(f)} filings"
                  + (f"  e.g. {f[0]['filename']}" if f else ""))

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    n = sum(len(v) for d in report["filings"].values() for v in d.values())
    print(f"\n{len(life)} life insurers, {n} filings listed -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
