#!/usr/bin/env python3
"""Per-firm 資金運用表 (fund utilisation) from archived captures of ins-info.

WHY THE ARCHIVE AND NOT THE LIVE SITE
`Info2-1.aspx?UID=<統編>` needs no POST and no period parameter: a plain GET
returns 國外投資 (line 6) for the latest month plus the three prior year-ends.
That is the whole disclosure — there is no year selector to drive further back
(decision 4.51). The window is what it is, and it rolls.

So the only way to see an earlier window is to look at an earlier copy of the
page, and the Wayback Machine holds 51 captures back to 2016. A 2019 capture
shows FY105-108 where today's shows FY112-115. Chaining captures extends the
per-firm history by as much as the archive's coverage of that firm allows.

WHAT THIS IS AND IS NOT
It is a supplement, not the critical path. The archive's coverage of this page
is overwhelmingly 產物保險 (non-life); life insurers appear rarely. The
defensible hedge-ratio history still depends on the statutory statements, which
carry both legs of the official ratio. This fills in denominator observations
where the archive happens to have them, and — because the same firm-year
appears in several captures — the overlaps are a free consistency check on the
parse rather than merely more rows.

Amounts are NT$ thousands, as the page states (單位：新臺幣仟元).
"""
import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "ins_info_wayback"
OUT = ROOT / "data" / "firm_fund_utilisation_wayback.csv"
REPORT = ROOT / "reports" / "ins_info_wayback.json"
CDX = ("https://web.archive.org/cdx/search/cdx?url="
       "ins-info.ib.gov.tw%2Fcustomer%2FInfo2-1.aspx*"
       "&output=json&fl=timestamp,original&filter=statuscode:200&limit=3000")
UA = "Mozilla/5.0 (compatible; TLFX/1.0)"

# The nine rows of the table, in the order the page prints them. Row 6 is the
# one this project exists for; the rest are kept because the total is the only
# check available that the row labels were matched to the right columns.
ITEMS = ["銀行存款", "有價證券", "不動產", "放款", "專案運用及公共投資",
         "國外投資", "保險相關事業", "衍生性商品", "其他"]
TOTAL = "資金運用總計"


def fetch(url, timeout=120):
    """Archived copies only. `id_` asks for the original bytes, unrewritten."""
    key = re.sub(r"[^A-Za-z0-9]+", "_", url)[-120:]
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{key}.html"
    if p.exists() and p.stat().st_size > 2000:
        return p.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    for enc in ("utf-8", "big5", "cp950"):
        try:
            text = body.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = body.decode("utf-8", "replace")
    p.write_text(text, encoding="utf-8")
    return text


def flatten(t):
    t = re.sub(r"<script.*?</script>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    return [l.strip() for l in html.unescape(t).split("\n") if l.strip()]


def parse(text):
    """Company, the four column dates, and every row's four amounts.

    The columns are headed "115年度最新一期金額" then three "1NN年度金額". The
    first is the month named in 資料日期 — a part-year figure — and the rest are
    year-ends. Conflating the two would silently date a partial year as a
    December observation, so the latest column carries the actual month and is
    flagged; the others are 12-31.
    """
    lines = flatten(text)
    joined = "\n".join(lines)
    if "資金運用表" not in joined:
        return None
    name = next((l for l in lines if l.endswith("股份有限公司")
                 or l.endswith("公司台灣分公司")), None)
    m = re.search(r"資料日期：中華民國\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月", joined)
    if not (name and m):
        return None
    latest_y, latest_m = int(m.group(1)), int(m.group(2))

    # Column headers, in order. The current-year column is headed either
    # "最新一期金額" or "第N季金額" depending on the vintage, and the second
    # variant is why this needs care: matching only "最新一期" dropped that
    # column, after which every value landed under the date of the column to
    # its right. The check() additivity test does not catch that — a uniformly
    # shifted table still adds up — and it only surfaced because the same
    # firm-period read from two captures disagreed.
    cols, unknown = [], []
    for l in lines:
        h = re.match(r"^(\d{2,3})\s*年度\s*(最新一期|第\s*([1-4])\s*季)?\s*金額$", l)
        if h:
            y, q = int(h.group(1)), h.group(3)
            if q:                       # quarter column: dated to quarter end
                cols.append((f"{1911 + y}-{3 * int(q):02d}", True))
            elif h.group(2):            # "latest": the month in 資料日期
                cols.append((f"{1911 + y}-{latest_m:02d}", True))
            else:
                cols.append((f"{1911 + y}-12", False))
        elif re.match(r"^\d{2,3}\s*年度.*金額$", l):
            unknown.append(l)
    if unknown:
        # a header shape not seen before would shift the columns silently
        return {"error": f"unrecognised column header(s): {unknown}"}
    if len(cols) < 2:
        return None

    def amounts(after):
        """The whole run of numbers following a row label.

        Deliberately NOT capped at len(cols): reading exactly as many values as
        headers were found is what let a missed header shift a table silently,
        because the run simply stopped one short and every value moved left.
        Taking the full run lets the caller compare its length against the
        header count and reject the capture when they disagree.
        """
        out = []
        for k in range(after + 1, len(lines)):
            l = lines[k]
            v = l.replace(",", "")
            # The table prints 列號 before each label, so the run of a row's
            # values runs straight into the NEXT row's number. Stop on a number
            # whose successor is a row label: that number is the next 列號, not
            # this row's last column.
            nxt = lines[k + 1].replace(" ", "") if k + 1 < len(lines) else ""
            if re.fullmatch(r"-?\d+", v) and (nxt in ITEMS or nxt == TOTAL):
                return out
            if re.fullmatch(r"-?\d+", v):
                out.append(float(v))
            elif re.fullmatch(r"[-–—]", l):
                out.append(0.0)
            elif out:            # a non-numeric line ends the row
                return out
        return out

    rows = {}
    for i, l in enumerate(lines):
        label = l.replace(" ", "")
        if label in ITEMS and label not in rows:
            rows[label] = amounts(i)
        elif label == TOTAL and TOTAL not in rows:
            rows[TOTAL] = amounts(i)
    # Every complete row must carry exactly one value per column header. More
    # values than headers means a header was missed and the columns are
    # shifted; fewer means the row is ragged. Either way the table cannot be
    # read, and guessing which end to trim is how a shift becomes data.
    widths = {len(v) for v in rows.values() if v}
    if widths and max(widths) != len(cols):
        return {"error": f"{len(cols)} column headers but rows carry "
                         f"{sorted(widths)} values"}
    return {"insurer": name, "as_of_latest": f"{1911 + latest_y}-{latest_m:02d}",
            "columns": cols, "rows": rows}


def check(p):
    """The nine components must sum to the printed total, per column.

    This is the parse's only defence. The amounts are read as the run of
    numbers following a label, and if a label were matched to the wrong run —
    or a column were missed — the components would stop adding up. Without the
    check a misalignment would look exactly like data.
    """
    bad = []
    for j, (date, _) in enumerate(p["columns"]):
        parts = [p["rows"][i][j] for i in ITEMS
                 if i in p["rows"] and j < len(p["rows"][i])]
        tot = p["rows"].get(TOTAL, [])
        if len(parts) != len(ITEMS) or j >= len(tot):
            bad.append((date, "incomplete"))
            continue
        if abs(sum(parts) - tot[j]) > max(1.0, 5e-6 * abs(tot[j])):
            bad.append((date, f"{sum(parts):,.0f} != {tot[j]:,.0f}"))
    return bad


def main():
    import csv
    raw = fetch(CDX, timeout=180)
    caps = [c for c in json.loads(raw)[1:]]
    print(f"{len(caps)} archived captures")

    out, seen, report = [], {}, []
    for ts, url in caps:
        wb = f"https://web.archive.org/web/{ts}id_/{url}"
        try:
            p = parse(fetch(wb))
        except Exception as e:
            print(f"  ! {ts} {type(e).__name__}: {e}")
            continue
        if not p:
            continue
        if "error" in p:
            print(f"  {ts[:6]} {url[-12:]:<12} REJECTED: {p['error']}")
            report.append({"timestamp": ts, "rejected": p["error"]})
            continue
        bad = check(p)
        uid = (re.search(r"UID=(\w+)", url) or [None, ""])[1]
        print(f"  {ts[:6]} {uid:<9} {p['insurer'][:22]:<24} "
              f"{'/'.join(d for d, _ in p['columns'])}"
              + (f"   CHECK FAILED {bad}" if bad else ""))
        report.append({"timestamp": ts, "uid": uid, "insurer": p["insurer"],
                       "columns": [d for d, _ in p["columns"]],
                       "check_failed": bad})
        if bad:
            continue
        for j, (date, partial) in enumerate(p["columns"]):
            for item, vals in p["rows"].items():
                if j >= len(vals):
                    continue
                k = (p["insurer"], date, item)
                if k in seen and seen[k] != vals[j]:
                    # the same firm-period read from two captures must agree;
                    # a restatement is possible, a parse error more likely
                    print(f"    ~ CONFLICT {k}: {seen[k]:,.0f} vs {vals[j]:,.0f}")
                if k in seen:
                    continue
                seen[k] = vals[j]
                out.append({"insurer": p["insurer"], "uid": uid,
                            "as_of": date, "partial_year": partial,
                            "item": item, "amount_ntd_k": vals[j],
                            "source_capture": ts})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()) if out else
                           ["insurer", "uid", "as_of", "partial_year", "item",
                            "amount_ntd_k", "source_capture"])
        w.writeheader()
        w.writerows(out)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(
        {"run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
         "captures": report}, indent=1, ensure_ascii=False), encoding="utf-8")

    fx = sorted({(r["insurer"], r["as_of"]) for r in out
                 if r["item"] == "國外投資"})
    print(f"\n{len(out)} rows -> {OUT.relative_to(ROOT)}")
    print(f"{len(fx)} firm-period 國外投資 observations, "
          f"{min(d for _, d in fx) if fx else '-'} to "
          f"{max(d for _, d in fx) if fx else '-'}")
    firms = {}
    for n, d in fx:
        firms.setdefault(n, []).append(d)
    for n, ds in sorted(firms.items()):
        print(f"  {n[:26]:<28} {len(ds):>2}  {min(ds)} .. {max(ds)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
