#!/usr/bin/env python3
"""Per-firm interest-rate and FX sensitivity, from the statutory statements.

WHY A SECOND MOPS SCRIPT
------------------------
`stage3_mops_statements.py` looked for the insurers under holding-company
subsidiary codes (28880001 and the like) and found nothing, because MOPS does
not serve those. The right codes were already established in decisions 3.13 and
are in README section 4: each insurer is a public company in its own right — it
issues subordinated debt, so it is 公開發行 and files quarterly. TWSE's open
registry lists ten, effectively the whole sector:

    2823 凱基人壽   2833 台灣人壽   2867 三商美邦   2876 宏泰人壽
    5846 國泰人壽   5865 富邦人壽   5873 全球人壽   5874 南山人壽
    6025 臺銀人壽   6985 新光人壽

What is new here is the index parsing. The filing table no longer contains the
readfile() javascript the old parser scraped — the filenames sit in the table
cells themselves, which is why the earlier run found zero filings even for codes
that work. The download step (step=9 on the same endpoint) is recorded in 3.3 as
gated; it is attempted here and the result is reported rather than assumed.

WHAT IS EXTRACTED AND WHY IT IS THE RIGHT NUMBER
------------------------------------------------
Two tables in the financial-risk note:

  利率風險敏感度分析表 — the change in P&L and in EQUITY for a 1bp parallel
  shift in each currency's yield curve. This is a DV01, disclosed by the firm,
  by currency. It is the direct measure of how much duration risk is actually
  carried on the balance sheet, and it is far better than any inference from
  asset mix, because it is net of hedges and reflects the firm's own accounting
  classification.

  匯率風險敏感度分析表 — the change in P&L, in EQUITY and in the FX volatility
  reserve for a 1% move in each currency. The reserve column is the one this
  project has spent most effort on from the sector side; here it is per firm.

THE CLASSIFICATION TRAP, WHICH IS THE POINT
-------------------------------------------
Equity DV01 covers only the assets carried at fair value through OCI. Bonds at
amortised cost do not move equity, so a firm that holds its long bonds at AC
reports a small equity DV01 while carrying the same economic duration. That
makes the series a measure of DISCLOSED balance-sheet sensitivity, not of
economic duration — and it makes changes in it informative in their own right:
Cathay's USD equity DV01 nearly doubled between 2025Q1 and 2026Q1 while its
strategy deck describes "redesignation of AC assets to FVOCI". The number moved
because the accounting moved. Both facts belong in the series, so the loaded
rows are labelled as disclosed sensitivity and never as duration.

UNITS
-----
Statements are in NT$ thousands. Values are converted to NT$ mn on load.

RATE
----
TWSE resets connections under load. One request every REQUEST_GAP seconds,
everything cached to disk, cache consulted first, so a re-run is free and a
partial run resumes.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "mops_stmt"
PDFS = ROOT / "cache" / "mops_pdf"
OUT = ROOT / "data" / "firm_sensitivity.csv"
NOTIONAL_OUT = ROOT / "data" / "firm_hedge_notional.csv"
DOC = "https://doc.twse.com.tw/server-java/t57sb01"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")
def _envf(name, default):
    """os.environ.get(name, default) returns '' when the variable is SET BUT
    EMPTY, so the default never applies and float('') raises. A workflow_dispatch
    input that is absent on a push-triggered run arrives exactly that way, which
    is what killed the first CI run at import time."""
    return float((os.environ.get(name) or "").strip() or default)


REQUEST_GAP = _envf("TLFX_MOPS_GAP", 8)
# Earliest ROC year to DOWNLOAD, applied independently of what the index
# happens to hold. The index is cumulative and an earlier run may have written
# years beyond this range; without a floor here those would be pulled anyway
# and the run would not finish in one pass, which is the point of the range.
MIN_YEAR = int(_envf("TLFX_MOPS_MIN_YEAR", 105))
# Stop downloading with time to spare and exit cleanly. Being killed at the
# job's ceiling ends the process mid-filing; stopping first means the last
# checkpoint is written and the run reports how far it actually got, which is
# the difference between "resume from here" and "work out where it died".
DEADLINE = _envf("TLFX_MOPS_DEADLINE_MIN", 280) * 60
_started = time.time()
# The WAF answers 200 with a "FOR SECURITY REASONS" page rather than a 4xx. A
# first pass at 3s between requests hit it, and — worse — cached the block page,
# so a rate-limited company-year became a permanent "0 filings". Blocked
# responses are now recognised, never cached, and retried after a long pause;
# purge() clears any that an earlier run stored.
BLOCKED = "FOR SECURITY REASONS"
BLOCK_WAIT = _envf("TLFX_MOPS_BLOCK_WAIT", 90)

FIRMS = {"2823": "kgi_life", "2833": "taiwan_life", "2867": "mercuries_life",
         "2876": "hontai_life", "5846": "cathay_life", "5865": "fubon_life",
         "5873": "transglobe_life", "5874": "nanshan_life",
         "6025": "banktaiwan_life", "6985": "shinkong_life"}
QUARTER = {"第一季": 1, "第二季": 2, "第三季": 3, "第四季": 4}

_last = [0.0]


def _sleep():
    gap = REQUEST_GAP - (time.time() - _last[0])
    if gap > 0:
        time.sleep(gap)


def post(**form):
    """One cached, rate-limited POST to the MOPS document server (HTML)."""
    key = urllib.parse.urlencode(sorted(form.items()))
    p = CACHE / (re.sub(r"[^A-Za-z0-9_=&.-]+", "_", key)[:150] + ".html")
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    _sleep()
    req = urllib.request.Request(
        DOC, data=urllib.parse.urlencode(form).encode(),
        headers={"User-Agent": UA, "Referer": "https://doc.twse.com.tw/",
                 "Content-Type": "application/x-www-form-urlencoded"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
            _last[0] = time.time()
            text = body.decode("big5", "replace")
            if BLOCKED in text or "ｅ" == text[:1]:
                print(f"    ~ WAF block, pausing {BLOCK_WAIT:.0f}s")
                time.sleep(BLOCK_WAIT)
                _last[0] = time.time()
                continue
            CACHE.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            return text
        except Exception as e:
            _last[0] = time.time()
            if attempt == 3:
                return f"__ERROR__ {type(e).__name__}: {e}"
            time.sleep(5 * (attempt + 1))
    return "__ERROR__ blocked by WAF after 4 attempts"


def purge():
    """Drop cached WAF block pages left by an earlier run."""
    n = 0
    for f in CACHE.glob("*.html"):
        try:
            if BLOCKED in f.read_text(encoding="utf-8", errors="replace"):
                f.unlink()
                n += 1
        except OSError:
            pass
    if n:
        print(f"  purged {n} cached block pages")


def rows_of(text):
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        c = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).replace("\xa0", " ").strip()
             for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        c = [x for x in c if x]
        if c:
            out.append(c)
    return out


def index(co_id, roc_year):
    """Filing rows for one company-year. The filename sits in the table itself;
    the readfile() javascript the older page used is gone from this template,
    which is why the earlier attempt found nothing here."""
    t = post(step="1", colorchg="1", co_id=co_id, year=str(roc_year), seamon="",
             mtype="A")
    if t.startswith("__ERROR__"):
        return [], t
    out = []
    for c in rows_of(t):
        if len(c) < 8 or c[0] != co_id:
            continue
        m = re.search(r"第[一二三四]季", c[1])
        fn = next((x for x in c if x.endswith(".pdf")), None)
        if not (m and fn):
            continue
        out.append({"co_id": co_id, "roc_year": int(re.search(r"\d+", c[1]).group()),
                    "quarter": QUARTER[m.group()], "kind": c[5], "filename": fn})
    return out, None


HREF = re.compile(r"href='(/pdf/[^']+\.pdf)'", re.I)


def _get(url, ref):
    """One paced GET, returning the body, or None on a WAF block."""
    _sleep()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": ref})
    with urllib.request.urlopen(req, timeout=300) as r:
        body = r.read()
    _last[0] = time.time()
    return body


def pdf(co_id, filename):
    """Fetch one filing.

    step=9 does NOT stream the PDF. It returns a small HTML page — 電子資料查詢
    作業 — carrying a link to /pdf/<name>_<timestamp>.pdf, and the timestamp is
    minted per request, so the URL cannot be constructed and the two-step is
    unavoidable. An earlier version read that page as "not a PDF" and abandoned
    the whole queue on the first filing; 3.3's note that the download is "gated"
    appears to be the same misreading.

    Two responses still mean wait rather than fail: the WAF's "FOR SECURITY
    REASONS" page, and a transport error. Anything else is genuinely absent.
    """
    PDFS.mkdir(parents=True, exist_ok=True)
    p = PDFS / filename
    if p.exists() and p.stat().st_size > 10000:
        return p
    form = {"step": "9", "kind": "A", "co_id": co_id, "filename": filename}
    for attempt in range(4):
        _sleep()
        req = urllib.request.Request(
            DOC, data=urllib.parse.urlencode(form).encode(),
            headers={"User-Agent": UA, "Referer": "https://doc.twse.com.tw/",
                     "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                body = r.read()
            _last[0] = time.time()
            if body[:4] == b"%PDF":              # not observed, but harmless
                p.write_bytes(body)
                return p
            text = body.decode("big5", "replace")
            if BLOCKED in text:
                print(f"    ~ WAF block on {filename}, pausing {BLOCK_WAIT:.0f}s")
                time.sleep(BLOCK_WAIT)
                _last[0] = time.time()
                continue
            m = HREF.search(text)
            if not m:
                print(f"    ! {filename}: no download link in the step-9 page "
                      f"({len(body)}b)")
                return None
            doc = _get("https://doc.twse.com.tw" + m.group(1), DOC)
            if doc[:4] != b"%PDF":
                if BLOCKED in doc.decode("big5", "replace"):
                    print(f"    ~ WAF block fetching {filename}, "
                          f"pausing {BLOCK_WAIT:.0f}s")
                    time.sleep(BLOCK_WAIT)
                    _last[0] = time.time()
                    continue
                print(f"    ! {filename}: link served {len(doc)}b, not a PDF")
                return None
            p.write_bytes(doc)
            return p
        except Exception as e:
            _last[0] = time.time()
            # The reason, not just the class. "URLError" alone cannot
            # distinguish a timeout from a reset from a refused connection,
            # and those call for opposite responses (wait longer vs back off
            # entirely). A whole run's worth of these said nothing diagnosable.
            print(f"    ! {filename}: {type(e).__name__}: "
                  f"{getattr(e, 'reason', None) or e}")
            time.sleep(5 * (attempt + 1))
    print(f"    ! {filename}: gave up after 4 attempts")
    return None


# ------------------------------------------------------------------ parsing
# The PDF emits CJK table headers one glyph per line, so the text is flattened
# to a single whitespace-collapsed string before anything is matched. Numbers
# arrive as "( $ 144,217 )" split across lines; a bare "-" is nil, not missing.
BLOCK = re.compile(r"(利率|匯率)\s*風\s*險\s*敏\s*感\s*度\s*分\s*析\s*表")
PERIOD = re.compile(r"(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*\d{1,2}\s*日\s*至\s*"
                    r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")
RATE_ROW = re.compile(r"殖利率曲線\s*\(\s*([^)]+?)\s*\)\s*平移上升\s*(\d+)\s*bp")
FX_ROW = re.compile(r"([一-鿿]{2,4})兌([一-鿿]{2,4})升值\s*(\d+)\s*%")
# Each numeric alternative must START with a digit. Written as [\d,]+ it also
# matches a bare "," — and flattening the PDF's one-glyph-per-line CJK leaves
# plenty of stray separators — whereupon "".replace(",","") is the empty string
# and float() raises. That killed a whole CI run over one comma.
NUM = re.compile(r"\(\s*\$?\s*(\d[\d,]*)\s*\)|\$?\s*(-)(?![\d,])|\$?\s*(\d[\d,]*)")


def numbers(seg, n):
    out = []
    for m in NUM.finditer(seg):
        neg, nil, pos = m.groups()
        if nil is not None:
            out.append(0.0)
        elif neg is not None:
            out.append(-float(neg.replace(",", "")))
        else:
            out.append(float(pos.replace(",", "")))
        if len(out) == n:
            break
    return out


def sensitivities(path):
    """Every 利率/匯率 sensitivity row in one filing, both periods it prints."""
    import pymupdf
    doc = pymupdf.open(path)
    pages = [unicodedata.normalize("NFKC", p.get_text()) for p in doc]
    text = "\n".join(t for t in pages if "敏感度分析表" in t)
    if not text:
        return []
    flat = re.sub(r"\s+", " ", text)
    marks = [m for m in BLOCK.finditer(flat)]
    out = []
    for i, m in enumerate(marks):
        # bound each block at the next one, or a stray tail duplicates the rows
        # of the following block under this block's period
        seg = flat[m.start(): marks[i + 1].start() if i + 1 < len(marks) else len(flat)]
        per = PERIOD.search(seg)
        if not per:
            continue
        yr, _, m2, d2 = per.groups()
        end = f"{1911 + int(yr)}-{int(m2):02d}-{int(d2):02d}"
        kind = "rate" if m.group(1) == "利率" else "fx"
        # the FX table carries a third column (the FX volatility reserve) only
        # where the firm runs one; read the column count off the header
        ncol = 3 if (kind == "fx" and "準" in seg[:220]) else 2
        pat = RATE_ROW if kind == "rate" else FX_ROW
        body = seg[per.end():]
        hits = list(pat.finditer(body))
        for j, h in enumerate(hits):
            stop = hits[j + 1].start() if j + 1 < len(hits) else min(len(body),
                                                                     h.end() + 140)
            vals = numbers(body[h.end():stop], ncol)
            if len(vals) < 2:
                continue
            row = {"period_end": end, "table": kind,
                   "label": h.group(1) if kind == "rate"
                            else f"{h.group(1)}/{h.group(2)}",
                   "shock": h.group(2) + ("bp" if kind == "rate" else ""),
                   "pnl_ntd_k": vals[0], "equity_ntd_k": vals[1],
                   "fx_reserve_ntd_k": vals[2] if len(vals) > 2 else None}
            if kind == "fx":
                row["shock"] = h.group(3) + "pct"
            out.append(row)
    # a filing prints the current and comparative periods; identical rows can
    # appear twice when a table straddles a page break
    seen, uniq = set(), []
    for r in out:
        k = (r["period_end"], r["table"], r["label"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


# ------------------------------------------------- hedge notionals
# THE TRAP, WHICH IS THE WHOLE REASON THIS IS LABELLED RATHER THAN SUMMED.
# A filing can disclose FX derivative notionals in two different notes and they
# mean different things:
#
#   designated   — the 避險活動 / 避險會計 note lists ONLY instruments formally
#                  designated for hedge accounting. Cathay's designated forward
#                  notional is NT$44bn against a ~NT$5tn foreign book, so summing
#                  this across firms understates the sector by two orders of
#                  magnitude for any firm that designates (decisions 4.36).
#   currency_risk — the 外幣/匯率風險 note, where a firm stating 並未採用避險會計
#                  reports its ECONOMIC hedges. This is the one that corresponds
#                  to 傳統避險本金 in the FSC notice §三(九).
#
# So every row carries note_kind, and nothing is aggregated here. A firm that
# discloses only `designated` has NOT disclosed its hedge principal, and must be
# recorded as unknown rather than as a small number.
INSTR = re.compile(r"(遠期外匯合約|換匯換利合約|換匯合約|貨幣交換合約|"
                   r"無本金交割遠期外匯|利率交換合約)")
DESIG = re.compile(r"避險活動|避險會計|避險工具之明細|現金流量避險|公允價值避險")
CCYRISK = re.compile(r"匯率風險|外幣.{0,6}風險|未避險|並未採用避險會計")


def notionals(path):
    """Every disclosed derivative notional, labelled by the note it came from."""
    import pymupdf
    doc = pymupdf.open(path)
    out = []
    for page in doc:
        raw = unicodedata.normalize("NFKC", page.get_text())
        if not INSTR.search(raw) or not re.search(r"名目|合約金額|契約金額", raw):
            continue
        kind = ("designated" if DESIG.search(raw)
                else "currency_risk" if CCYRISK.search(raw) else "unclassified")
        flat = re.sub(r"\s+", " ", raw)
        # One page carries the current period AND its comparatives, each under
        # its own date header. Attributing every row to the page's first date
        # would silently stamp last year's numbers with this year's date, so
        # each row takes the nearest date header ABOVE it.
        heads = [(m.start(),
                  f"{1911 + int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
                 for m in re.finditer(r"(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", flat)]
        for h in INSTR.finditer(flat):
            tail = flat[h.end():h.end() + 160]
            v = numbers(tail, 1)
            if not (v and v[0] > 0):
                continue
            asof = next((d for pos, d in reversed(heads) if pos < h.start()), None)
            out.append({"as_of": asof, "note_kind": kind,
                        "instrument": h.group(1), "notional_ntd_k": v[0],
                        "page": page.number + 1})
    seen, uniq = set(), []
    for r in out:
        k = (r["as_of"], r["note_kind"], r["instrument"], r["notional_ntd_k"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


IDX = ROOT / "reports" / "mops_filing_index.json"
# Filings downloaded and parsed, whatever they yielded. A filing that parses to
# no rows leaves no trace in either CSV, so without this list it would be
# re-downloaded on every future run for ever.
ATTEMPTED = ROOT / "reports" / "mops_parsed_filings.json"


def build_index(years):
    purge()
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else {}
    for co, name in FIRMS.items():
        got = {(r["roc_year"], r["quarter"], r["filename"]): r
               for r in idx.get(co, [])}
        for y in years:
            rows, err = index(co, y)
            if err:
                print(f"  {co} {name} {y}: ERROR {err[:60]}")
                continue
            for r in rows:
                got[(r["roc_year"], r["quarter"], r["filename"])] = r
        idx[co] = sorted(got.values(), key=lambda r: (r["roc_year"], r["quarter"]))
        qs = sorted({(r["roc_year"], r["quarter"]) for r in idx[co]})
        print(f"  {co} {name:<16} {len(idx[co]):>3} filings  "
              + " ".join(f"{y}Q{q}" for y, q in qs))
        IDX.parent.mkdir(exist_ok=True)
        IDX.write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nindex: {IDX.relative_to(ROOT)}")
    return idx


def _write(path, rows, keyf):
    """Dedupe on keyf and write; returns the rows written.

    Rows carried in from an earlier run are dicts read back from CSV, so every
    value is a string, while freshly parsed rows hold floats and None. Keying
    on str() puts both in the same space — otherwise the same observation
    reappears each run under a key that never matches its predecessor and the
    file grows without bound.
    """
    import csv
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda r: tuple(str(x) for x in keyf(r))):
        k = tuple(str(x) for x in keyf(r))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    if not uniq:
        return []
    # a run resumed from CSV has string cells; a fresh row may carry a key the
    # older file lacked, so the header is the union rather than the first row's
    cols = list(dict.fromkeys(c for r in uniq for c in r))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in uniq:
            w.writerow({c: r.get(c) for c in cols})
    return uniq


def _prior(path, key="filing"):
    """Rows already extracted by an earlier run, and the filings they came from.

    The PDFs are not committed (they are large and disposable), so every run
    starts with an empty cache and re-fetches from scratch. At eight seconds a
    request and two requests a filing, a decade of filings does not fit in one
    run's time budget — and a run that times out three-quarters of the way
    through used to leave nothing behind.

    Carrying the output forward makes runs additive instead: each one skips
    what is already extracted and spends its budget on filings never seen. The
    history therefore deepens one run at a time rather than needing a single
    run long enough for all of it.
    """
    import csv
    if not path.exists():
        return [], set()
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return rows, {r[key] for r in rows if r.get(key)}


def pull():
    """Download the consolidated filings named in the index and parse them."""
    import csv
    idx = json.loads(IDX.read_text(encoding="utf-8"))
    rows, done_sens = _prior(OUT)
    notional_rows, done_not = _prior(NOTIONAL_OUT)
    # A filing that parsed to nothing is still done: without recording it, an
    # empty result would be retried on every future run, for ever.
    attempted = set(json.loads(ATTEMPTED.read_text(encoding="utf-8"))
                    ) if ATTEMPTED.exists() else set()
    done = (done_sens | done_not | attempted)
    if done:
        print(f"  {len(done)} filings already extracted; skipping those\n")
    # One filing per firm-quarter. Insurers with subsidiaries file 合併財報 and
    # that is the one to take; several file only 個別/個體財報, which carries the
    # same risk note for an entity with nothing to consolidate. The 英文版 is a
    # translation of a filing already in the list and is never fetched.
    def rank(kind):
        return 0 if "合併" in kind else 1 if "個別" in kind else 2 if "個體" in kind else 9

    def checkpoint():
        """Persist after every firm.

        The job's wall-clock ceiling is a real constraint, and a cancelled run
        writes nothing from inside the loop. Saving per firm means the worst a
        timeout costs is the firm in progress, not the whole run.
        """
        ATTEMPTED.parent.mkdir(parents=True, exist_ok=True)
        ATTEMPTED.write_text(json.dumps(sorted(attempted), indent=0), encoding="utf-8")
        _write(NOTIONAL_OUT, notional_rows,
               lambda r: (r["entity_id"], r["as_of"], r["note_kind"],
                          r["instrument"], r["notional_ntd_k"]))
        _write(OUT, rows,
               lambda r: (r["entity_id"], r["period_end"], r["table"], r["label"]))

    stopped = [False]
    for co, name in FIRMS.items():
        if stopped[0]:
            break
        best = {}
        for f in idx.get(co, []):
            if "英文版" in f["kind"] or int(f["roc_year"]) < MIN_YEAR:
                continue
            k = (f["roc_year"], f["quarter"])
            if k not in best or rank(f["kind"]) < rank(best[k]["kind"]):
                best[k] = f
        # newest first: the WAF may cut the run short at any point, so the most
        # recent periods should be the ones already on disk when it does
        for f in sorted(best.values(),
                        key=lambda r: (r["roc_year"], r["quarter"]), reverse=True):
            if f["filename"] in done:
                continue
            if time.time() - _started > DEADLINE:
                print(f"\n  deadline reached ({DEADLINE / 60:.0f} min); stopping "
                      f"with {len(attempted)} filings extracted. Re-run to "
                      f"continue from here.")
                stopped[0] = True
                break
            p = pdf(co, f["filename"])
            if not p:
                continue
            attempted.add(f["filename"])
            # One malformed filing must cost that filing, not the run. Each
            # download is minutes of rate-limited fetching, so an exception
            # raised here discards every earlier firm's work as well — which
            # is exactly what happened, over a single unparseable cell.
            try:
                got = sensitivities(p)
                nots = notionals(p)
            except Exception as e:
                print(f"  {name:<16} {f['roc_year']}Q{f['quarter']} "
                      f"{f['filename']:<24} PARSE FAILED: {type(e).__name__}: {e}")
                continue
            print(f"  {name:<16} {f['roc_year']}Q{f['quarter']} "
                  f"{f['filename']:<24} {len(got):>3} sens  {len(nots):>3} notional")
            for r in got:
                rows.append({"entity_id": name, "co_id": co,
                             "filing": f["filename"], **r})
            for r in nots:
                notional_rows.append({"entity_id": name, "co_id": co,
                                      "filing": f["filename"], **r})
        checkpoint()

    uniq = _write(NOTIONAL_OUT, notional_rows,
                  lambda r: (r["entity_id"], r["as_of"], r["note_kind"],
                             r["instrument"], r["notional_ntd_k"]))
    if uniq:
        print(f"\n{len(uniq)} notional rows -> {NOTIONAL_OUT.relative_to(ROOT)}")
        by_kind = {}
        for r in uniq:
            by_kind[r["note_kind"]] = by_kind.get(r["note_kind"], 0) + 1
        print("  by note: " + ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items()))
              + "   (only currency_risk corresponds to 傳統避險本金)")

    # a later filing restates the same comparative period; keep one
    uniq = _write(OUT, rows,
                  lambda r: (r["entity_id"], r["period_end"], r["table"], r["label"]))
    if not uniq:
        print("  no sensitivity rows parsed")
        return []
    print(f"\n{len(uniq)} unique observations -> {OUT.relative_to(ROOT)}")
    usd = [r for r in uniq if r["table"] == "rate" and r["label"] == "美金"]
    if usd:
        print("\nUSD DV01 ON EQUITY, NT$ mn per bp (disclosed sensitivity, "
              "fair-valued assets only)")
        for r in sorted(usd, key=lambda r: (r["entity_id"], r["period_end"])):
            print(f"  {r['entity_id']:<16} {r['period_end']}  "
                  f"{-r['equity_ntd_k'] / 1000:>10,.1f}")
    return uniq


def main():
    args = sys.argv[1:]
    if args and args[0] == "pull":
        pull()
        return 0
    # ROC 105-115 = calendar 2016-2026. Chosen so the whole span completes in
    # ONE run rather than accumulating over several: at two requests a filing
    # and eight seconds a request, eleven years fits inside the job's ceiling
    # and fourteen does not. A dense decade now beats a fuller history later.
    default = [str(y) for y in range(115, MIN_YEAR - 1, -1)]
    build_index([int(y) for y in (args or default)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
