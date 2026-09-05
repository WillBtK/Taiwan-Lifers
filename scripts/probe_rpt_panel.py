#!/usr/bin/env python3
"""Pull the Observation Station's company x quarter panel, 2009 onward.

THE FINDING THIS ACTS ON
------------------------
`RPT-06021011.aspx` (表06021011 財務報表摘要) is an ASP.NET form whose period
selectors offer **ROC 98 to 115 — 2009 Q1 to 2026 Q4** across 55 insurers with
a 壽險/產險 filter. That was read straight out of the page body already saved by
the discovery pass; it needed no query at all. It answers the question the
supplied source map (4.37) put first and could not settle: the company-level
panel with pre-2020 history exists, and this is where it lives.

The same form shape appears on the other nine RPT pages, so whatever works here
works for 表06161610 (壽險財務業務指標) and 表07011010 next.

TWO ROUTES, TRIED IN ORDER
--------------------------
1. **GET with the form fields as a query string.** Many WebForms pages read
   `Request[...]`, which takes query and form alike; where that is true the
   whole panel is one URL and the existing GET-only relay is enough. Cheap to
   try and it costs one request to find out.
2. **POST, the way a browser does it.** GET the page, take __VIEWSTATE and
   __EVENTVALIDATION and the session cookie, POST them back with the
   selections. This needs the relay's /post endpoint; against an older relay it
   returns 404 and the script says so rather than failing obscurely.

Both go through the Taiwan relay because the portal answers only from Taiwan
(4.13) — a geographic restriction, not a robots one, so no User-Agent or cookie
changes it.

WHAT IS ASKED FOR
-----------------
One query spanning the full offered range, life insurers only. If the server
caps the span it will say so, and the fallback is to walk year by year; asking
for everything first means one request establishes both the cap and the shape.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "rpt_panel_probe.json"
KEEP = ROOT / "data" / "raw" / "ins-info-rpt"
UA = "Mozilla/5.0 (compatible; TLFX/1.0)"

BASE = "https://ins-info.ib.gov.tw/customer/RPT-06021011.aspx"
FIELDS = {
    "ddlComapnyType": "1",        # 1 = 壽險
    "ddlComapnyName": "0",        # 0 = 全部
    "DropDownList_BYear": "98",   # ROC 98 = 2009
    "DropDownList_BQuarter": "1",
    "DropDownList_EYear": "115",  # ROC 115 = 2026
    "DropDownList_EQuarter": "4",
    "btnQuery": "查詢",
}


def relay():
    base = os.environ.get("TAIWAN_RELAY_URL", "").strip().rstrip("/")
    token = os.environ.get("TAIWAN_RELAY_TOKEN", "").strip()
    if not base or not token:
        raise SystemExit("relay not configured (TAIWAN_RELAY_URL/TOKEN)")
    return base, token


def call(path, target, data=None, cookie=None):
    base, token = relay()
    url = f"{base}{path}?url=" + urllib.parse.quote(target, safe="")
    headers = {"User-Agent": UA, "X-Relay-Token": token}
    if cookie:
        headers["X-Relay-Cookie"] = cookie
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read(), r.headers.get("X-Relay-Set-Cookie")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None


def decode(b):
    for enc in ("utf-8", "big5", "cp950"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("big5", "replace")


def describe(text):
    """What came back: is it a results table, and how much of one?"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I)
    cells = [[re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip()
              for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
             for tr in rows]
    cells = [c for c in cells if c]
    # a results table has many rows whose first cell is a company name
    named = [c for c in cells if c and ("保險" in c[0] or "人壽" in c[0])]
    periods = sorted({m for m in re.findall(r"\b(\d{2,3})年第?([1-4])季", text)})
    return {
        "bytes": len(text), "table_rows": len(cells), "company_rows": len(named),
        "distinct_periods_mentioned": len(periods),
        "period_range": (f"{periods[0][0]}Q{periods[0][1]}–{periods[-1][0]}Q{periods[-1][1]}"
                         if periods else None),
        "sample_rows": named[:3],
        "has_error_text": any(k in text for k in ("錯誤", "查無", "無資料", "Exception")),
    }


def main():
    KEEP.mkdir(parents=True, exist_ok=True)
    report = {"run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "target": BASE, "fields": FIELDS, "attempts": []}

    def record(name, status, body, note=None):
        text = decode(body) if body else ""
        (KEEP / f"{name}.html").write_text(text, encoding="utf-8")
        e = {"attempt": name, "status": status, "note": note}
        if text:
            e.update(describe(text))
        report["attempts"].append(e)
        print(f"  {name:<22} status {status}  " +
              (f"{e.get('company_rows')} company rows, {e.get('bytes')}b, "
               f"periods {e.get('period_range')}" if text else (note or "")))
        return text

    print("1) GET with the form fields as a query string")
    st, body, _ = call("/fetch", BASE + "?" + urllib.parse.urlencode(FIELDS), None)
    record("get_with_params", st, body)

    print("2) baseline GET, no parameters (the control)")
    st, body, cookie = call("/fetch", BASE)
    base_text = record("get_baseline", st, body)

    print("3) POST the form the way a browser does")
    tok = {}
    for k in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        m = re.search(r'id="%s"[^>]*value="([^"]*)"' % k, base_text)
        if m:
            tok[k] = m.group(1)
    if not tok.get("__VIEWSTATE"):
        report["attempts"].append({"attempt": "post", "note": "no __VIEWSTATE on the baseline GET"})
        print("  post                   skipped: no __VIEWSTATE on the baseline page")
    else:
        form = dict(tok)
        form.update(FIELDS)
        st, body, _ = call("/post", BASE,
                           urllib.parse.urlencode(form, encoding="utf-8").encode(),
                           cookie=cookie)
        if st == 404:
            record("post", st, b"", note="relay has no /post yet — redeploy ops/taiwan-relay")
        else:
            record("post", st, body)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    best = max((a.get("company_rows") or 0) for a in report["attempts"])
    print(f"\nbest attempt returned {best} company rows -> {OUT.relative_to(ROOT)}")
    # Reaching the portal at all is the success condition here; which route wins
    # is the finding, and a route that fails is as informative as one that works.
    return 0


if __name__ == "__main__":
    sys.exit(main())
