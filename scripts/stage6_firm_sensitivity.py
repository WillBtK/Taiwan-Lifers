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
Two disclosures, both read from the real filings rather than assumed:

  敏感度分析表 — ONE table covering equity, rate and FX risk together, not the
  two separate 利率風險/匯率風險 tables this script originally looked for. Rows
  give the change in P&L and in EQUITY for a stated shock, and the shocks are
  NOT unit shocks: Fubon discloses a 50BPS parallel curve move by currency and
  a 3% move in TWD against all foreign currencies. Calling these DV01s would
  overstate per-basis-point sensitivity fiftyfold, so the shock size travels
  with every row and any per-bp figure is derived downstream.

  衍生性金融商品 — the derivatives note, laid out period-major as
  帳面價值 | 名目本金 for each period side by side. The notional is therefore
  the SECOND number after an instrument name; reading the first silently
  recorded the carrying value instead. §三(五)'s 傳統避險 set (forwards, FX
  swaps, CCS, NDFs) is selected by instrument label, so the interest-rate swaps
  and options in the same table are excluded from the hedge numerator.

  Not to be confused with the 避險活動 note, which lists only instruments
  formally DESIGNATED as hedges — NT$67bn for Fubon against a NT$1,437bn
  economic book. The two are labelled separately and never summed.

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
POLICY_OUT = ROOT / "data" / "firm_fx_policy.csv"
# The flattened text of every page carrying a note we parse. This is the
# expensive thing: each filing costs two rate-limited requests, so a full
# pull is hours, and until now a parser change meant paying that again. The
# text is small enough to commit gzipped and makes re-parsing free - which
# matters because every firm lays these notes out differently and the parser
# will need many more passes.
NOTE_TEXT = ROOT / "data" / "mops_note_text.json.gz"
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
# The relative deadline is measured from when THIS process starts, which is the
# download step — but the job's ceiling runs from when the JOB started, and the
# index step before it took anywhere from 39 to 60 minutes. On the current run
# the two land within a minute of each other, so the "stop cleanly with time to
# spare" margin is gone precisely when a slow index makes it matter most.
#
# An absolute epoch passed by the workflow removes the guesswork: the workflow
# knows when the job began and what its ceiling is, and this only has to obey.
# Falls back to the relative deadline when unset.
_abs = (os.environ.get("TLFX_MOPS_DEADLINE_EPOCH") or "").strip()
if _abs:
    DEADLINE = max(60.0, float(_abs) - _started)
    print(f"  deadline: {DEADLINE / 60:.0f} min from now (absolute, set by the job)")
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
# Numbers arrive as "( $ 144,217 )" split across lines; a bare "-" is nil, not
# missing. Each numeric alternative must START with a digit -- written [\d,]+ it
# also matches a bare ",", and flattening the PDF's one-glyph-per-line CJK
# leaves plenty of stray separators, whereupon "".replace(",","") is the empty
# string and float() raises. That killed a whole CI run over one comma.
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


# The market-risk sensitivity disclosure is ONE table covering equity, rate and
# FX risk, headed 敏感度分析表 with an optional (本公司)/(子公司X) scope, not the
# two separate 利率風險敏感度分析表 / 匯率風險敏感度分析表 this used to look
# for. Nothing matched, so every filing reported "0 sens" while the table sat
# in the document unread.
BLOCK = re.compile(r"敏\s*感\s*度\s*分\s*析\s*表\s*(?:[（(]\s*([^）)]{1,20})\s*[）)])?")
# Periods inside it are dot dates (113.12.31), not the 年/月/日至/月/日 range.
PERIOD = re.compile(r"\b(\d{2,3})\.(\d{1,2})\.(\d{1,2})\b")
# 殖利率曲線(美元)平行上移50BPS -- 平行上移/下移, and BPS, not 平移上升 ... bp.
# The shock is 50bp, not 1bp, so these are NOT DV01s and must not be labelled
# as such; the size is carried on every row.
RATE_ROW = re.compile(r"殖利率曲線\s*[（(]\s*([^）)]{1,8}?)\s*[）)]\s*"
                      r"平行(上移|下移)\s*([\d.]+)\s*(?:BPS|bps|bp|基點)")
# 新台幣兌所有外幣升值3% -- the counter-currency may be 所有外幣 rather than a
# single currency, and the shock is 3%, not 1%.
FX_ROW = re.compile(r"([一-鿿]{2,4})\s*兌\s*([一-鿿]{2,6})\s*(升值|貶值)\s*"
                    r"([\d.]+)\s*%")
EQ_ROW = re.compile(r"價格指數\s*(上升|下跌)\s*([\d.]+)\s*%")


# 匯率交換合約 was missing, and it is the LARGEST line in the book: Fubon Life
# at 113.12.31 disclosed NT$1,213.8bn of it against NT$198.0bn of forwards --
# 84% of the total notional, invisible to the pattern that omitted it.
# Order matters: 換匯換利合約 must precede 換匯合約, or the shorter alternative
# matches its prefix and mislabels a CCS as an FX swap.
INSTR = re.compile(r"(遠期外匯合約|換匯換利合約|匯率交換合約|換匯合約|"
                   r"貨幣交換合約|無本金交割遠期外匯(?:合約)?|利率交換合約|"
                   r"選擇權合約)")
# §三(五) counts only 傳統避險: forwards, FX swaps, CCS and NDFs against TWD.
# Interest-rate swaps and options are disclosed in the same table and are not
# part of it, so the instrument label decides inclusion, not the table.
TRADITIONAL = {"遠期外匯合約", "匯率交換合約", "換匯換利合約", "換匯合約",
               "貨幣交換合約", "無本金交割遠期外匯", "無本金交割遠期外匯合約"}
# The columns of the derivatives note, in the order they are headed.
COLHEAD = re.compile(r"(帳面價值|名目本金|合約金額|契約金額|公允價值)")
# 113.12.31 style period headers. The bounds are not decoration: an unbounded
# (\d{2,3})\.(\d{1,2})\.(\d{1,2}) matches any dotted numeral in the text and
# produced dates like 2023-12-00 and 2021-12-16 from things that were never
# dates, which then became the period key for real notionals. ROC years for
# these filings run 90-130; months 1-12; days 1-31.
DOTDATE = re.compile(r"\b(9\d|1[0-2]\d)\.(0?[1-9]|1[0-2])\.(0?[1-9]|[12]\d|3[01])\b")
# Which TABLE a page carries, not which section it sits in. The old pattern
# matched the section heading -- Fubon's is "(三)衍生性金融工具及避險會計",
# naming both topics -- so the MAIN derivatives table was filed as "designated"
# and dropped from the numerator. 173 of 189 rows landed in the wrong bucket
# and the 傳統避險本金 series was empty as a result.
#
# The designated-hedge table has markers of its own: it reports the carrying
# amount of the hedging instrument and the value change used to compute hedge
# ineffectiveness. Those appear in that table and nowhere else.
DESIG = re.compile(r"避險工具之帳面金額|避險無效性|避險工具之明細|"
                   r"指定為避險工具|被避險項目")
CCYRISK = re.compile(r"匯率風險|外幣.{0,6}風險|未避險|並未採用避險會計")
# The main derivatives table, identified structurally: notional beside carrying
# value. This IS the economic book and is what §三(九)'s numerator draws on.
ECONOMIC = re.compile(r"名目本金|合約金額|契約金額")


# Cathay presents the same disclosure under IFRS 17, split across eight
# columns: 損益變動 and 權益變動 each broken into 所發行之保險合約 /
# 所持有之再保險合約 / 金融工具 / 小計. The 小計 columns are the comparable
# figures; the financial-instruments column alone is what a pre-IFRS17 series
# would have shown, so both are kept.
#
# Two things differ beyond layout and matter for interpretation. The shock is
# 1bp and 1%, against Fubon's 50BPS and 3% — so the levels are NOT comparable
# without dividing by the shock. And the rate row is 各幣別 (all currencies
# together), not per currency, so no USD-specific figure exists in this table.
IFRS17_COLS = re.compile(r"所\s*發\s*行\s*之\s*保\s*險\s*合\s*約")
PERIOD_CJK = re.compile(r"(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
# 115年1月1日至3月31日 -- the reporting date is the END of the range.
PERIOD_RANGE = re.compile(r"(\d{2,3})\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*至\s*"
                          r"(?:(\d{2,3})\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日")
# Whitespace can fall ANYWHERE, including inside a two-character word: the
# PDF wraps mid-term and flattening leaves "平移上 升1bp". Allowing \s* only
# between terms and not within them is why the rate row matched nothing while
# the FX row, which happened not to wrap, matched fine.
IFRS17_FX = re.compile(r"各\s*外\s*幣\s*兌\s*新\s*台\s*幣\s*"
                       r"(升\s*值|貶\s*值)\s*([\d.]+)\s*%")
IFRS17_RATE = re.compile(r"各\s*幣\s*別\s*殖\s*利\s*率\s*曲\s*線\s*平\s*移\s*"
                         r"(上\s*升|下\s*降)\s*([\d.]+)\s*(?:bp|BPS|bps|基點)")


def parse_sensitivity_ifrs17(flat):
    """The eight-column IFRS 17 sensitivity table (Cathay's shape)."""
    if not IFRS17_COLS.search(flat):
        return []
    # An interim table is headed by a RANGE -- 115年1月1日至3月31日 -- and the
    # balance it reports is the one at the END of it. Taking the range's first
    # date dated every Cathay observation to 1 January of the wrong year: eight
    # quarters that looked like a plausible annual series and were each two to
    # six months out, which is worse than a gap because it lines up with
    # nothing and nothing says so.
    spans = []
    heads = []
    for m in PERIOD_RANGE.finditer(flat):
        y = int(m.group(2) or m.group(1))
        heads.append((m.start(), f"{1911 + y}-{int(m.group(3)):02d}-"
                                 f"{int(m.group(4)):02d}"))
        spans.append((m.start(), m.end()))
    for pat in (PERIOD_CJK, DOTDATE):
        for m in pat.finditer(flat):
            if any(a <= m.start() < b for a, b in spans):
                continue
            heads.append((m.start(), f"{1911 + int(m.group(1))}-"
                                     f"{int(m.group(2)):02d}-"
                                     f"{int(m.group(3)):02d}"))
    heads.sort()
    if not heads:
        return []
    out = []
    for pat, table in ((IFRS17_RATE, "rate"), (IFRS17_FX, "fx")):
        for m in pat.finditer(flat):
            v = numbers(flat[m.end(): m.end() + 320], 8)
            if len(v) < 8:
                continue
            d = next((x for pos, x in reversed(heads) if pos < m.start()), None)
            if not d:
                continue
            out.append({"period_end": d, "scope": "ifrs17", "table": table,
                        "label": "各幣別" if table == "rate" else "各外幣/新台幣",
                        "shock": (f"{m.group(2)}bp" if table == "rate"
                                  else f"{m.group(2)}%"),
                        "direction": re.sub(r"\s+", "", m.group(1)),
                        "pnl_insurance_ntd_k": v[0], "pnl_reinsurance_ntd_k": v[1],
                        "pnl_instruments_ntd_k": v[2], "pnl_ntd_k": v[3],
                        "eq_insurance_ntd_k": v[4], "eq_reinsurance_ntd_k": v[5],
                        "eq_instruments_ntd_k": v[6], "equity_ntd_k": v[7]})
    return out


# Nan Shan's FX sensitivity table extracts RIGHT-TO-LEFT, so the accounting
# marks TRAIL their number instead of surrounding it:
#     36,169,702 $   950,095) ($   35,219,607 $
# meaning 36,169,702 / (950,095) / 35,219,607. numbers() reads the middle one
# as POSITIVE — the magnitudes all look right and one sign is silently
# inverted, which on a hedge disclosure reverses the direction of the effect.
NS_ROW = re.compile(r"(金融資產|保險合約及所持有之再保險合約|公司整體[^ ]{0,12})\s*"
                    r"外幣兌新台幣\s*(升值|貶值)\s*([\d.]+)\s*%")
# The trailing ")" is INSPECTED, not consumed. Matching it as part of the
# token ate the whitespace the next token needed to start, so a three-column
# row yielded two values and was dropped -- the row vanished rather than
# arriving wrong, which at least fails loudly, but it dropped four of six.
NS_NUM = re.compile(r"(?<![\d,])(\d[\d,]*|-)(?![\d,])")


def numbers_trailing(seg, n):
    """Read n numbers whose negative marker follows them rather than wraps."""
    out = []
    for m in NS_NUM.finditer(seg):
        tok = m.group(1)
        v = 0.0 if tok == "-" else float(tok.replace(",", ""))
        after = seg[m.end(): m.end() + 4].lstrip()
        out.append(-v if after.startswith(")") else v)
        if len(out) == n:
            break
    return out


def parse_sensitivity_nanshan(flat):
    """FX sensitivity where the parentheses trail the figure."""
    rows = list(NS_ROW.finditer(flat))
    if not rows:
        return []
    # the period header sits AFTER the table here, not before it
    d = None
    for m in PERIOD_CJK.finditer(flat):
        d = (f"{1911 + int(m.group(1))}-{int(m.group(2)):02d}-"
             f"{int(m.group(3)):02d}")
    if not d:
        return []
    out = []
    for i, m in enumerate(rows):
        end = rows[i + 1].start() if i + 1 < len(rows) else len(flat)
        v = numbers_trailing(flat[m.end():end], 3)
        if len(v) < 3:
            continue
        out.append({"period_end": d, "scope": m.group(1), "table": "fx",
                    "label": "外幣/新台幣", "shock": f"{m.group(3)}%",
                    "direction": m.group(2), "pnl_ntd_k": v[0],
                    "oci_ntd_k": v[1], "equity_ntd_k": v[2]})
    return out


def sensitivities(path):
    """The market-risk sensitivity table: equity, rate and FX rows, per period.

    One table, not two, and the shocks are NOT unit shocks: Fubon discloses a
    50bp parallel curve move and a 3% FX move. Reporting these as DV01s would
    overstate per-basis-point sensitivity fiftyfold, so the shock size travels
    with every row and the caller divides if it wants a DV01.

    Rows carry two columns, 損益變動 and 權益變動 -- P&L and equity. A "-" is a
    genuine nil (a TWD curve move does not touch P&L when the TWD book is at
    amortised cost), not a missing value.
    """
    import pymupdf
    doc = pymupdf.open(path)
    out = []
    for page in doc:
        raw = unicodedata.normalize("NFKC", page.get_text())
        if not BLOCK.search(raw) or not RATE_ROW.search(raw) \
                and not FX_ROW.search(raw):
            continue
        flat = re.sub(r"\s+", " ", raw)
        scope = (BLOCK.search(flat).group(1) or "本公司").strip()
        # each row belongs to the nearest period header ABOVE it; the table
        # prints the current period then the comparative, same shape twice
        heads = [(m.start(),
                  f"{1911 + int(m.group(1))}-{int(m.group(2)):02d}-"
                  f"{int(m.group(3)):02d}")
                 for m in PERIOD.finditer(flat)]
        if not heads:
            continue

        def emit(m, table, label, shock, sign):
            vals = numbers(flat[m.end(): m.end() + 90], 2)
            if len(vals) < 2:
                return
            d = next((x for pos, x in reversed(heads) if pos < m.start()), None)
            if not d:
                return
            out.append({"period_end": d, "scope": scope, "table": table,
                        "label": label, "shock": shock, "direction": sign,
                        "pnl_ntd_k": vals[0], "equity_ntd_k": vals[1]})

        for m in RATE_ROW.finditer(flat):
            emit(m, "rate", m.group(1), f"{m.group(3)}bp", m.group(2))
        for m in FX_ROW.finditer(flat):
            emit(m, "fx", f"{m.group(1)}/{m.group(2)}",
                 f"{m.group(4)}%", m.group(3))
        for m in EQ_ROW.finditer(flat):
            emit(m, "equity", "價格指數", f"{m.group(2)}%", m.group(1))
    seen, uniq = set(), []
    for r in out:
        k = (r["period_end"], r["scope"], r["table"], r["label"],
             r["shock"], r["direction"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


def header_span(flat):
    """Where the column headers stop: at the first instrument row.

    A fixed character window is the wrong tool — too short and a firm with a
    long preamble loses its dates, too long and it swallows data rows and their
    dates, which breaks the columns-per-period arithmetic. Widening 400 to 520
    gained one firm and lost another for exactly that reason. The header block
    is, by construction, everything before the first data row.
    """
    m = INSTR.search(flat)
    return min(m.start(), 900) if m else 520


def find_dates(flat, window=None):
    """Period headers in a table, in printed order, from EITHER date style.

    Fubon heads its columns 113.12.31; Cathay, Nan Shan and Hontai head theirs
    115年6月30日. parse_note only knew the dotted form, so it returned nothing
    for those firms and they read as "discloses nothing" rather than "not
    parsed" — three of the ten insurers, including the largest.
    """
    w = window or header_span(flat)
    hits = [(mm.start(), int(mm.group(1)), int(mm.group(2)), int(mm.group(3)))
            for mm in DOTDATE.finditer(flat[:w])]
    hits += [(mm.start(), int(mm.group(1)), int(mm.group(2)), int(mm.group(3)))
             for mm in PERIOD_CJK.finditer(flat[:w])]
    out, seen = [], set()
    for _, y, mo, d in sorted(hits):
        iso = f"{1911 + y:04d}-{mo:02d}-{d:02d}"
        if iso not in seen:
            seen.add(iso)
            out.append(iso)
    return out


# Nan Shan's derivatives note is a fourth shape again. Its instruments carry
# no 合約 suffix (匯率交換, 遠期外匯), so INSTR matches nothing at all; the
# figures use the trailing-$ layout; the book is split into 金融資產 and
# 金融負債 blocks that must be SUMMED to get the gross notional; and the period
# headers are printed at the END, after all six blocks.
NS_BLOCK = re.compile(r"(金融資產|金融負債)")
NS_INSTR = re.compile(r"(匯率交換|遠期外匯|換匯換利|無本金交割遠期外匯)"
                      r"(?:\(註\d\))?")
# A block header is followed IMMEDIATELY by the table it heads — the column
# heading 帳面金額 (or 帳面價值, which is the wording before 2024) or, for the
# liability block, its first instrument. Anchoring matters: the prose sentence
# "金融資產及金融負債互抵資訊請詳附註六(九)" sits directly above the table, so a
# WINDOW of any width sees the real table's own 帳面金額 through it and keeps the
# prose as a block. That gave 8 blocks against 6 real ones, the asset/liability
# pairing check then failed, and this parser returned NOTHING from 2024-12
# onwards — Nan Shan, the sector's second-largest foreign book, simply stopped
# at 2024-06 in the aggregate.
NS_HEAD = re.compile(r"^[\s:：]*(?:帳面(?:金額|價值)|"
                     r"匯率交換|遠期外匯|換匯換利|無本金交割遠期外匯)")


def ns_blocks(flat):
    """The 金融資產 / 金融負債 occurrences that actually head a table."""
    return [b for b in NS_BLOCK.finditer(flat)
            if NS_HEAD.match(flat[b.end(): b.end() + 40])]


def parse_note_nanshan(flat):
    """Gross derivative notionals from the asset/liability block layout."""
    if "名目本金" not in flat or not NS_BLOCK.search(flat):
        return []
    # The period headers trail the table, so they must be read from the TAIL,
    # after the last block - not from the whole page. Note 2 of this same note
    # recites the same three dates in prose ("...於民國115年6月30日、114年12月
    # 31日及114年6月30日分別為..."), and scanning the whole page picked those
    # up instead, attaching block values to the wrong periods. The same four
    # figures then appeared under 2018-12-31 in one filing and 2020-12-31 in
    # another, which is what the doubling was.
    _blocks = ns_blocks(flat)
    if not _blocks:
        return []
    # Newest first, NOT printed order. The trailing dates come out of the PDF
    # in whatever order the extractor walked the footer, and on 4 of 25 Nan Shan
    # tables that is not the order the columns are in: 202502 yields
    # 2025-06-30, 2024-06-30, 2024-12-31, which would put the year-end block
    # under the prior interim and vice versa. Taiwanese interim statements
    # print current period, prior year-end, prior interim, so descending is the
    # column order and the footer is only evidence of WHICH dates, not their
    # sequence.
    dates = sorted(find_dates(flat[_blocks[-1].start():], len(flat)),
                   reverse=True)
    blocks = _blocks
    if not dates or len(blocks) < 2:
        return []
    # blocks run asset, liability, asset, liability ... one PAIR per period,
    # in the same order as the dates printed at the foot
    if len(blocks) != 2 * len(dates):
        return []
    out = []
    for i, b in enumerate(blocks):
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(flat)
        seg = flat[b.end():end]
        d = dates[i // 2]
        for h in NS_INSTR.finditer(seg):
            v = numbers_trailing(seg[h.end(): h.end() + 70], 2)
            if len(v) < 2 or v[1] <= 0:
                continue
            out.append({"as_of": d, "instrument": h.group(1),
                        "notional_ntd_k": v[1],
                        "carrying_ntd_k": v[0],
                        "side": b.group(1),
                        "traditional": True})
    return out


# A FIFTH shape, and the only one that is not a table at all. Shin Kong/Taishin,
# Hontai and Mercuries state the notional in a sentence, denominated in USD:
#
#   (2) 本集團尚未到期之衍生工具合約金額(名目本金)如下:
#       115.6.30      114.12.31     114.6.30
#       匯率交換合約   USD 19,200,000千元 USD19,700,000千元 USD800,000千元
#       遠期外匯合約   USD 1,675,000千元  USD7,700,000千元  -
#
# No table reader finds this, which is why 13 Shin Kong filings produced zero
# notional rows and read as "discloses nothing". It is in fact the CLEANEST
# disclosure of the five: an explicit per-instrument notional already in
# dollars, needing no FX conversion and no reconciliation to a printed total.
# The amounts can also run together without a separator —
# "USD695,000千元USD890,000千元" — so the reader must not depend on whitespace.
USD_ANCHOR = re.compile(r"尚\s*未\s*到\s*期\s*之\s*衍\s*生\s*工\s*具"
                        r"[^。]{0,40}?名\s*目\s*本\s*金")
USD_STOP = re.compile(r"本\s*[公集][司團]\s*從\s*事|避\s*險\s*會\s*計|"
                      r"[（(]\s*\d+\s*[）)]\s*本\s*[公集]")
USD_AMT = re.compile(r"(?:USD|美\s*[元金])\s*([\d,]+)\s*千\s*元"
                     r"|(?<![\d,])(-)(?![\d,])")
# 外匯換匯合約 is Taishin's wording for an FX swap. Without it INSTR matches the
# 換匯合約 tail and the row is still an FX swap, but the label loses the 外匯
# prefix; naming it explicitly keeps the instrument taxonomy honest.
USD_INSTR = re.compile(r"(外匯換匯合約|" + INSTR.pattern[1:-1] + r")")


def parse_note_usd_prose(flat):
    """Per-instrument notionals stated in a sentence, in USD thousands."""
    m = USD_ANCHOR.search(flat)
    if not m:
        return []
    tail = flat[m.end(): m.end() + 900]
    stop = USD_STOP.search(tail)
    seg = tail[: stop.start()] if stop else tail
    first = USD_INSTR.search(seg)
    if not first:
        return []
    dates = find_dates(seg[: first.start()], first.start())
    if not dates:
        return []
    out = []
    hits = list(USD_INSTR.finditer(seg))
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(seg)
        vals = []
        for a in USD_AMT.finditer(seg[h.end():end]):
            vals.append(None if a.group(2) else
                        float(a.group(1).replace(",", "")))
            if len(vals) == len(dates):
                break
        for d, v in zip(dates, vals):
            # A dash is a genuine absence, not a zero to be carried forward.
            if v is None or v <= 0:
                continue
            out.append({"as_of": d, "instrument": h.group(1),
                        "currency": "USD", "notional_ccy_k": v,
                        "traditional": h.group(1) in TRADITIONAL
                        or h.group(1) == "外匯換匯合約"})
    return out


def parse_note(flat):
    """Rows of one derivatives-note table, read off its column headers.

    The table is laid out period-major:

        113.12.31              112.12.31
        帳面價值    名目本金     帳面價值    名目本金
        遠期外匯合約 $ (1,309,890) 198,008,832 2,769,845 634,021,774

    so the notional is the SECOND number after the instrument name, not the
    first. Reading the first number -- which is what this did -- silently
    recorded 帳面價值, the carrying value, as though it were the notional.
    Nothing about the output looked wrong; the magnitudes are simply someone
    else's.

    So the header is parsed rather than assumed: the run of column labels gives
    both the width of a row and which position within each period is the
    notional, and the run of period dates says which period each block belongs
    to. A table whose header does not divide evenly into the dates is refused
    rather than guessed at.
    """
    w = header_span(flat)
    dates = find_dates(flat, w)
    heads = COLHEAD.findall(flat[:w])
    if not dates or not heads or len(heads) % len(dates):
        return []
    per = len(heads) // len(dates)                    # columns per period
    want = [i for i, h in enumerate(heads[:per])
            if h in ("名目本金", "合約金額", "契約金額")]
    if not want:
        return []
    out = []
    for h in INSTR.finditer(flat):
        vals = numbers(flat[h.end():h.end() + 260], per * len(dates))
        if len(vals) < per * len(dates):
            continue
        for di, date in enumerate(dates):
            for w in want:
                v = vals[di * per + w]
                if v > 0:
                    out.append({"as_of": date, "instrument": h.group(1),
                                "notional_ntd_k": v,
                                "traditional": h.group(1) in TRADITIONAL})
    return out


# Taiwan Life states notionals BY CURRENCY, in thousands of that currency,
# with no NT$ column at all:
#     名目本金/合約金額明細如下(單位:千元):
#     幣別      114.12.31   113.12.31
#     匯率交換合約
#       USD      5,775,000   5,555,000
# parse_note() sees the instrument, reads the next numbers as if they were the
# NT$ notional and its comparative, and produces two wrong figures instead of
# nothing — which is worse. The header is what distinguishes the two shapes.
CCY = re.compile(r"\b(USD|EUR|JPY|AUD|HKD|RMB|CNY|GBP|CHF|CAD|NZD|SGD|THB|ZAR|KRW)\b")
BYCCY_HEAD = re.compile(r"幣\s*別")


# Two different tables both head a currency column, and they are not read the
# same way. Taiwan Life prints 幣別 ONCE and the periods across it:
#
#     幣 別      115.6.30   114.12.31  114.6.30
#     遠期外匯合約 AUD  -          -        76,000
#                USD  5,464,040  12,165,040  12,435,040
#
# Mercuries repeats the whole triple per period, so the currency appears once
# for every column and each occurrence owns exactly one figure:
#
#     項目   帳面金額 幣別 名目本金 | 帳面金額 幣別 名目本金 | 帳面金額 幣別 名目本金
#     遠期外匯…合約 $15,663,818 USD 10,590,000  1,320,395 USD 1,550,000  41,670 USD 300,000
#
# Read as though it were the first shape, the second one takes 1,550,000 —
# December's figure — as June's, and Mercuries' hedge ratio came out between
# 97% and 170% of its own foreign assets. How many times 幣別 appears in the
# header is what tells the two apart.
BYCCY_ROW = re.compile(r"期\s*貨|選\s*擇\s*權|合\s*計|小\s*計|〜")


def parse_note_by_currency(flat):
    """Instrument -> currency -> per-period notional, in FX thousands.

    No conversion happens here. The rate to use is the reporting date's
    closing rate, which belongs with the loader that has the FX series, not
    with a text parser; carrying the currency through keeps that explicit
    rather than burying a conversion nobody can audit later.

    The table is also not always two periods. A half-year filing carries three
    — 115.6.30, 114.12.31, 114.6.30 — and taking the first two read the third
    column's figures as the second's. The header row says how many there are.
    """
    head = BYCCY_HEAD.search(flat)
    if not head:
        return []
    # The periods are the ones printed in this table's own header, not every
    # dot date on the page: the prose above it carries its own.
    span = flat[head.end(): head.end() + 160]
    cols = [f"{1911 + int(y)}-{int(m):02d}-{int(d):02d}"
            for y, m, d in DOTDATE.findall(span)]
    if not cols:
        cols = [f"{1911 + int(y)}-{int(m):02d}-{int(d):02d}"
                for y, m, d in DOTDATE.findall(flat)]
    seen, dates = set(), []
    for d in cols:
        if d not in seen:
            seen.add(d)
            dates.append(d)
    dates = dates[:4]
    if not dates:
        return []
    # 幣別 repeated across the header means one currency column per period.
    repeated = len(BYCCY_HEAD.findall(flat[head.start():
                                           head.start() + 160])) >= 2

    out = []
    hits = list(INSTR.finditer(flat, head.end()))
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(flat)
        seg = flat[h.end(): end]
        # The last instrument's segment otherwise runs to the end of the page
        # and swallows the 期貨 row beneath the table.
        stop = BYCCY_ROW.search(seg)
        if stop and i + 1 == len(hits):
            seg = seg[: stop.start()]
        marks = list(CCY.finditer(seg))
        for k, c in enumerate(marks):
            tail = seg[c.end(): c.end() + 30 * len(dates)]
            nxt = marks[k + 1].start() - c.end() if k + 1 < len(marks) else None
            if nxt is not None:
                tail = tail[:nxt]
            if repeated:
                # one figure per occurrence, in column order
                vals = numbers(tail, 1)
                pairs = [(dates[k % len(dates)], vals[0])] if vals else []
            else:
                vals = numbers(tail, len(dates))
                pairs = [(d, vals[di]) for di, d in enumerate(dates)
                         if di < len(vals)]
            for d, v in pairs:
                if v > 0:
                    out.append({"as_of": d, "instrument": h.group(1),
                                "currency": c.group(1), "notional_ccy_k": v,
                                "traditional": h.group(1) in TRADITIONAL})
    return out


# The FX-denominated insurance liability, by currency, with the rate and the
# NT$ equivalent beside it:
#
#   本公司於資產負債表日以外幣計價之保險合約及再保險合約之帳面金額如下:
#   115年3月31日        外 幣      匯 率     新 台 幣
#   保險及再保險合約 資 產 貨幣性項目
#     美 金        $ 125       31.98    $ 3,982
#     ...                                $ 4,051
#   保險及再保險合約 負 債 貨幣性項目
#     美 金      5,318,560     31.98  $ 170,087,557
#     ...                              $ 170,461,433
#
# The LIABILITY total is the quantity that matters: it is the foreign-currency
# policy book, which is the bucket Fubon's slide merges into its hedge wedge
# and never splits (4.78). Its own printed total is the check — the currency
# rows must sum to it, or the table has been read at the wrong offset.
POLICY_HEAD = re.compile(r"以\s*外\s*幣\s*計\s*價\s*之\s*保\s*險\s*合\s*約"
                         r"\s*及\s*再\s*保\s*險\s*合\s*約")
POLICY_SIDE = re.compile(r"(資\s*產|負\s*債)\s*貨\s*幣\s*性\s*項\s*目")
# A currency name, then three figures: the foreign amount, the rate, the NT$.
POLICY_ROW = re.compile(
    r"(美\s*金|澳\s*幣|歐\s*元|日\s*圓|英\s*鎊|港\s*幣|人民幣(?:\(離岸\))?|"
    r"南\s*非\s*幣|紐\s*幣|新\s*加\s*坡\s*幣|加\s*拿\s*大\s*幣|瑞\s*士\s*法\s*郎)"
    r"[^0-9(]{0,6}\(?\$?\s*([\d,]+(?:\.\d+)?)\s*\)?"
    r"[^0-9]{0,4}([\d]+\.\d+)"
    r"[^0-9(]{0,6}\(?\$?\s*([\d,]+)")


def parse_policy_fx(flat):
    """Foreign-currency insurance liabilities, NT$ thousands, per period.

    Returns one row per balance-sheet date found, with the printed total and
    whether the currency rows reconcile to it. A table that does not reconcile
    is reported rather than dropped: the number is wanted precisely where a
    firm's layout is new, and a silent drop would look like non-disclosure.
    """
    out = []
    for h in POLICY_HEAD.finditer(flat):
        seg = flat[h.end(): h.end() + 1400]
        d = PERIOD_CJK.search(seg)
        if not d:
            continue
        as_of = (f"{1911 + int(d.group(1))}-{int(d.group(2)):02d}-"
                 f"{int(d.group(3)):02d}")
        sides = list(POLICY_SIDE.finditer(seg))
        for i, sd in enumerate(sides):
            if "負" not in sd.group(1):
                continue
            end = sides[i + 1].start() if i + 1 < len(sides) else len(seg)
            block = seg[sd.end(): end]
            rows = [(m.group(1), float(m.group(2).replace(",", "")),
                     float(m.group(3)), float(m.group(4).replace(",", "")))
                    for m in POLICY_ROW.finditer(block)]
            if not rows:
                continue
            # The printed total is the last large figure in the block. Where a
            # layout omits it this picks up the last row instead, the check
            # fails, and the row is flagged rather than silently wrong.
            nums = [float(x.replace(",", ""))
                    for x in re.findall(r"([\d,]{7,})", block)]
            summed = sum(r[3] for r in rows)
            total = nums[-1] if nums else summed
            out.append({"as_of": as_of, "policy_ntd_k": summed,
                        "printed_total_ntd_k": total,
                        "currencies": ";".join(
                            f"{c.replace(' ', '')}={v:,.0f}" for c, v, _r, _n
                            in rows),
                        "reconciles": abs(summed - total) <= max(
                            1.0, 5e-4 * abs(total))})
    return out


def note_total(flat):
    """The 合計 notional printed on the page, per period.

    This is the filing's own arithmetic and the only independent check on the
    extraction: instrument rows that do not sum to it have been read at the
    wrong offset, matched in prose, or double-counted. Without it, 910 rows of
    unknown quality is all there is.

    The 合計 taken is the one AFTER the last instrument row, not the first on
    the page. Fubon prints an expected-credit-loss table above the derivatives
    note with its own 合 計, and taking the first match read that one — the
    derivative rows then failed to sum to a total belonging to a different
    table, and every Fubon quarter from 2022-09 to 2024-09 was discarded as
    unverifiable. Fifteen per cent of the sector, absent from nine quarters of
    the aggregate, because of a table that happened to sit higher on the page.
    """
    first = INSTR.search(flat)
    m = re.search(r"合\s*計\s*(.{0,220})",
                  flat[first.start():] if first else flat)
    if not m:
        return {}
    w = header_span(flat)
    dates = find_dates(flat, w)
    heads = COLHEAD.findall(flat[:w])
    if not dates or not heads or len(heads) % len(dates):
        return {}
    per = len(heads) // len(dates)
    want = [i for i, h in enumerate(heads[:per])
            if h in ("名目本金", "合約金額", "契約金額")]
    v = numbers(m.group(1), per * len(dates))
    if not want or len(v) < per * len(dates):
        return {}
    return {d: v[i * per + want[0]] for i, d in enumerate(dates)}


def notionals(path):
    """Every disclosed derivative notional, labelled by the note it came from.

    The total row is the check: the instrument notionals of a period must sum
    to the 合計 the filing prints for it. That is what catches a column read at
    the wrong offset, which is otherwise invisible -- wrong numbers of the
    right order of magnitude, in the right shape.
    """
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
        rows = parse_note(flat)
        if not rows:
            continue
        # 合計 / 合 計 -- the printed total for each period. Read by the same
        # header logic parse_note uses, rather than a hardcoded 400-character
        # window: the two disagreed on any page where the derivatives note is
        # not the first table, and the rows then failed a check against a total
        # that was never theirs.
        tot = note_total(flat)
        for r in rows:
            r["note_kind"] = kind
            r["page"] = page.number + 1
            r["total_ntd_k"] = tot.get(r["as_of"])
        # additivity, per period: a mis-offset column still looks like data
        for d, t in tot.items():
            s = sum(r["notional_ntd_k"] for r in rows if r["as_of"] == d)
            if t and abs(s - t) > max(1.0, 5e-4 * t):
                print(f"    ! p{page.number + 1} {d}: instruments sum to "
                      f"{s:,.0f} but 合計 says {t:,.0f}")
        out += rows
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
# Bump whenever the extraction changes meaning. The resume logic skips filings
# already attempted, which is right for re-running the SAME parser and exactly
# wrong after fixing one: without this, a run that recorded 400 filings under a
# broken parser would cause the fixed parser to skip all 400 and quietly keep
# the bad numbers. A version change invalidates the record and re-parses.
PARSER_VERSION = 4


# A company-year that already has all four quarters in the cache is FINISHED:
# a 2019 annual report is not going to be filed again. Re-querying it costs two
# requests at eight seconds each and a WAF pause when the site tires of us, and
# the index step of a recent run spent fifty minutes re-establishing facts it
# already held. Only the two most recent ROC years are re-read, because that is
# where a filing can still appear.
#
# TLFX_MOPS_REINDEX=1 forces the full sweep, for the case where the cache is
# suspected wrong rather than merely old.
FRESH_YEARS = 2


def _settled(rows, co, y):
    qs = {r["quarter"] for r in rows if r["co_id"] == co and r["roc_year"] == y}
    return len(qs) >= 4


def build_index(years):
    purge()
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else {}
    force = (os.environ.get("TLFX_MOPS_REINDEX") or "").strip() == "1"
    recent = sorted(years, reverse=True)[:FRESH_YEARS]
    skipped = 0
    for co, name in FIRMS.items():
        got = {(r["roc_year"], r["quarter"], r["filename"]): r
               for r in idx.get(co, [])}
        for y in years:
            if not force and y not in recent and _settled(idx.get(co, []), co, y):
                skipped += 1
                continue
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
    if skipped:
        print(f"\n  {skipped} company-years already complete in the cache, "
              f"not re-queried (TLFX_MOPS_REINDEX=1 to force)")
    print(f"index: {IDX.relative_to(ROOT)}")
    return idx


def load_note_text():
    if not NOTE_TEXT.exists():
        return {}
    import gzip
    with gzip.open(NOTE_TEXT, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def save_note_text(store):
    import gzip
    NOTE_TEXT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(NOTE_TEXT, "wt", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False)


# The FX-denominated INSURANCE liability, which is a different disclosure from
# anything above and was never being kept. It matters because Fubon's investor
# slide merges its derivative hedge and its foreign-currency policies into one
# wedge and never splits them — the one gap in the sell-side comparison that is
# a property of the disclosure rather than of this project (4.71). If the
# statements state the policy liability by currency, the split follows:
# policy = FX policy liabilities / foreign assets, hedge = wedge - policy.
#
# Mercuries states it plainly — "以外幣計價之保險合約及再保險合約之帳面金額",
# US$5,318,560 thousand at NT$31.98 — and its page survived the old filter only
# because it happens to mention 遠期外匯合約 as well. Whether the other insurers
# state it is unknown, because their equivalent pages were never captured.
POLICY_FX = re.compile(r"以\s*外\s*幣\s*計\s*價\s*之\s*(?:所\s*發\s*行\s*之\s*)?"
                       r"保\s*險\s*合\s*約|保\s*險\s*及\s*再\s*保\s*險\s*合\s*約")
# A page kept for this reason alone would not otherwise be re-fetched, so the
# capture version is what tells a later run that its stored pages predate the
# widened filter and the filing is worth downloading again.
CAPTURE_VERSION = 2


def note_pages(path):
    """Flattened text of the pages carrying a note we care about.

    Kept deliberately generous: a page is captured if it mentions an
    instrument, a notional heading or 敏感度 with numbers on it. Being
    over-inclusive costs a little disk; being under-inclusive costs another
    full download when a parser turns out to need a page that was not kept.
    """
    import pymupdf
    out = {}
    doc = pymupdf.open(path)
    chars = 0
    for page in doc:
        raw = unicodedata.normalize("NFKC", page.get_text())
        chars += len(raw.strip())
        if not (INSTR.search(raw) or "敏感度" in raw
                or re.search(r"名目本金|合約金額|契約金額", raw)
                or POLICY_FX.search(raw)):
            continue
        if len(re.findall(r"\d{1,3}(?:,\d{3})+", raw)) < 4:
            continue                      # prose mentioning it, not a table
        out[str(page.number + 1)] = re.sub(r"\s+", " ", raw)
    # WHY a filing yielded nothing, because the two reasons need opposite
    # treatment. A filing with pages but no TEXT is a scan, and re-downloading
    # it a hundred times will not produce a table; a filing with plenty of text
    # and no match is a layout this filter has not met, and is worth another
    # look. Sixty-two filings sit at zero pages — every Fubon and Mercuries
    # filing before 2020, every Cathay one before 2019 — and until now the
    # record could not tell the two apart.
    if not out:
        return {}, {"pages": doc.page_count, "text_chars": chars,
                    "why": "no text layer (scan)" if chars < 200 * doc.page_count
                           else "text present, no note matched"}
    return out, None


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
    policy_rows = []
    # A filing that parsed to nothing is still done: without recording it, an
    # empty result would be retried on every future run, for ever.
    attempted, prior_ver = set(), None
    if ATTEMPTED.exists():
        rec = json.loads(ATTEMPTED.read_text(encoding="utf-8"))
        if isinstance(rec, dict):
            prior_ver = rec.get("parser_version")
            attempted = set(rec.get("filings", []))
        else:                       # v1 wrote a bare list
            attempted = set(rec)
    if prior_ver != PARSER_VERSION:
        # the stored results came from a different extraction; keeping them
        # would preserve the very numbers the new parser exists to replace
        print(f"  parser v{prior_ver} -> v{PARSER_VERSION}: discarding "
              f"{len(attempted)} prior filings and {len(rows)} + "
              f"{len(notional_rows)} prior rows, re-parsing from scratch")
        attempted, rows, notional_rows = set(), [], []
        done_sens = done_not = set()
        # Clearing the in-memory rows is not enough: _write() leaves an
        # existing file untouched when it has nothing to write, so a run that
        # parsed nothing would leave the previous parser's CSV in place and
        # looking current.
        for f in (OUT, NOTIONAL_OUT):
            f.unlink(missing_ok=True)
        # NOTE_TEXT is deliberately NOT cleared: it is raw captured input, not
        # a parser output, and discarding it would throw away the downloads
        # this whole mechanism exists to avoid repeating.
    # A filing captured with ZERO note pages and no recorded reason was never
    # actually examined — the record was written, `done` swallowed it, and it
    # could never be retried. That is why 62 filings, all of them the earliest
    # years, have sat empty since the first pull: the retry was locked out by
    # the failure it was meant to correct. One whose emptiness has since been
    # EXPLAINED stays done, so a scan is not re-fetched for ever.
    _notes_now = load_note_text()
    retry = {k for k, v in _notes_now.items()
             if not v.get("pages") and not v.get("empty")}
    stale = {k for k, v in _notes_now.items()
             if v.get("capture_version", 1) < CAPTURE_VERSION}
    if stale:
        print(f"  {len(stale)} filings captured under an older page filter; "
              f"re-fetching so the widened one sees them")
        retry |= stale
    if retry:
        print(f"  {len(retry)} filings captured no note pages and no reason; "
              f"retrying those")
    done = (done_sens | done_not | attempted) - retry
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
        ATTEMPTED.write_text(json.dumps(
            {"parser_version": PARSER_VERSION, "filings": sorted(attempted)},
            indent=0), encoding="utf-8")
        save_note_text(notes)
        _write(NOTIONAL_OUT, notional_rows,
               lambda r: (r["entity_id"], r["as_of"], r["note_kind"],
                          r["instrument"], r["notional_ntd_k"]))
        _write(OUT, rows,
               lambda r: (r["entity_id"], r["period_end"], r["table"], r["label"]))

    notes = load_note_text()
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
            # Capture the note text BEFORE parsing. This is what makes future
            # parser passes free: the download is the expensive half and every
            # firm lays these notes out differently, so there will be many.
            try:
                pages, empty_why = note_pages(p)
                rec = {"entity_id": name, "co_id": co,
                       "roc_year": f["roc_year"], "quarter": f["quarter"],
                       "capture_version": CAPTURE_VERSION, "pages": pages}
                if empty_why:
                    rec["empty"] = empty_why
                    print(f"    ~ {f['filename']}: no note pages — "
                          f"{empty_why['why']} ({empty_why['pages']}pp, "
                          f"{empty_why['text_chars']:,} chars)")
                notes[f["filename"]] = rec
            except Exception as e:
                print(f"    ! {f['filename']}: text capture failed: "
                      f"{type(e).__name__}: {e}")
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
                ent = entity_at(name, f["filename"], r.get("as_of"))
                if ent is None:
                    continue
                notional_rows.append({"entity_id": ent, "co_id": co,
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


def reparse():
    """Re-run the parsers over the captured note text. No network at all.

    This is the loop that matters now. Every firm lays the derivatives and
    sensitivity notes out differently - Cathay shocks by 1bp and splits
    insurance from financial instruments, Fubon by 50bp in one table, Nan Shan
    by 5% with trailing currency marks, Taiwan Life states notionals by
    currency in FX units rather than NT$ - so the parsers will need many more
    passes. Each one used to cost a full re-download; from the captured text it
    costs seconds.
    """
    notes = load_note_text()
    if not notes:
        # Nothing captured yet is a legitimate state, not a failure: the pull
        # that produces the text runs for hours and this workflow fires on
        # every parser edit. Exiting non-zero here reported a broken build to
        # the user when nothing was broken, which is worse than useless — it
        # spends the credibility a real failure needs.
        print(f"no captured text at {NOTE_TEXT.relative_to(ROOT)} yet; "
              f"nothing to re-parse. The pull that produces it is the source, "
              f"and it takes hours — this is not an error.")
        return 0
    rows, notional_rows, policy_rows = [], [], []
    per_firm = {}
    for filing, rec in sorted(notes.items()):
        flat_all = " ".join(rec["pages"].values())
        n = s = 0
        for page, flat in rec["pages"].items():
            # Order matters: a page carrying the notional table is the
            # economic book even when the surrounding section also discusses
            # hedge accounting. Only the designated table's own markers, in
            # the ABSENCE of a notional table, mean designated.
            kind = ("currency_risk" if ECONOMIC.search(flat)
                    and not DESIG.search(flat)
                    else "designated" if DESIG.search(flat)
                    else "currency_risk" if CCYRISK.search(flat)
                    else "unclassified")
            meta = dict(entity_id=rec["entity_id"], co_id=rec["co_id"],
                        filing=filing, page=int(page), note_kind=kind)
            # Two notional shapes, and they are mutually exclusive: a page
            # headed 幣別 states amounts in foreign-currency thousands with no
            # NT$ column, and running the NT$ parser over it would read the
            # currency rows as if they were NT$ figures — wrong numbers rather
            # than none, which is the harder error to notice.
            # Four shapes, tried most-specific first. Nan Shan's asset/
            # liability blocks and Taiwan Life's by-currency table both look
            # like nothing at all to the NT$ parser, so neither can be a
            # fallback for the other.
            # Five shapes now, tried most-specific first. The USD prose
            # sentence goes FIRST because the pages carrying it also carry an
            # NT$ table of derivative CARRYING values, and letting the table
            # reader see the page would record fair values as notionals.
            usd = parse_note_usd_prose(flat)
            ns = [] if usd else parse_note_nanshan(flat)
            byccy = [] if (usd or ns) else parse_note_by_currency(flat)
            rows_here = usd or ns or byccy or parse_note(flat)
            tot = {} if (usd or ns or byccy) else note_total(flat)
            # Mark each row with whether ITS table reconciles to the filing's
            # own 合計. Shipping 900 rows of mixed provenance and letting the
            # reader guess which are sound is worse than shipping fewer: the
            # flag is what makes a subset defensible.
            # A "notional" worth a ten-thousandth of its own table's 合計 is not
            # a notional. Fubon's 2026 Q2 page 56 yields 匯率交換合約 4, 6 and
            # 115 thousand alongside the real 708 billion, because a maturity
            # or count column sits under the same instrument labels further
            # down the page. Those rows are small enough that the additivity
            # check still passes for the periods where the real figures are
            # also present, and they become the ONLY rows for the periods where
            # they are not — a 12-thousand hedge book reported as reconciled.
            if tot:
                rows_here = [r for r in rows_here
                             if not r.get("notional_ntd_k")
                             or not tot.get(r["as_of"])
                             or r["notional_ntd_k"] >= 1e-4 * abs(
                                 tot[r["as_of"]])]
            page_sum = {}
            for r in rows_here:
                if r.get("notional_ntd_k"):
                    page_sum[r["as_of"]] = (page_sum.get(r["as_of"], 0.0)
                                            + r["notional_ntd_k"])
            for r in rows_here:
                tv = tot.get(r["as_of"])
                if tv:
                    s = page_sum.get(r["as_of"], 0.0)
                    flag = "yes" if abs(s - tv) <= max(1.0, 5e-4 * abs(tv)) else "no"
                else:
                    flag = "no_total"
                r.update(meta, total_ntd_k=tv, reconciles=flag)
                # A filing code is not an insurer. 6985 is Taishin Life until
                # the 2026 rename and the Shin Kong survivor after it, so the
                # row's own date decides which company it belongs to.
                ent = entity_at(meta["entity_id"], filing, r.get("as_of"))
                if ent is None:
                    continue
                r["entity_id"] = ent
                notional_rows.append(r)
                n += 1
            for r in (parse_sensitivity_ifrs17(flat) or []):
                r.update(meta)
                rows.append(r)
                s += 1
            for r in parse_policy_fx(flat):
                r.update(entity_id=meta["entity_id"], co_id=meta["co_id"],
                         filing=meta["filing"], page=meta["page"])
                policy_rows.append(r)
        st = per_firm.setdefault(rec["entity_id"], [0, 0, 0])
        st[0] += 1
        st[1] += n
        st[2] += s
        _ = flat_all
    print(f"{len(notes)} filings with captured text\n")
    print(f"  {'firm':<18}{'filings':>8}{'notional rows':>15}")
    for ent, (f, n, s) in sorted(per_firm.items()):
        print(f"  {ent:<18}{f:>8}{n:>15}" + ("   <- NO ROWS" if not n else ""))
    # Two row shapes share this file: NT$ rows carry notional_ntd_k, by-currency
    # rows carry notional_ccy_k plus a currency. Keying on the NT$ field alone
    # raises on the currency rows, and dropping the currency from the key would
    # collapse a firm's USD and JPY legs into one.
    if policy_rows:
        _write(POLICY_OUT, policy_rows,
               lambda r: (r["entity_id"], r["as_of"]))
        ok = sum(1 for r in policy_rows if r["reconciles"])
        firms = sorted({r["entity_id"] for r in policy_rows})
        print(f"\n  {len(policy_rows)} foreign-currency policy-liability rows "
              f"({ok} reconcile to their own printed total) "
              f"-> {POLICY_OUT.relative_to(ROOT)}")
        print(f"    firms disclosing it: {', '.join(firms)}")
    else:
        print("\n  no firm's captured pages carry the foreign-currency "
              "policy liability")
    _write(NOTIONAL_OUT, notional_rows,
           lambda r: (r["entity_id"], r["as_of"], r["note_kind"],
                      r["instrument"], r.get("currency") or "NTD",
                      r.get("notional_ntd_k"), r.get("notional_ccy_k")))
    print(f"\n{len(notional_rows)} notional rows -> "
          f"{NOTIONAL_OUT.relative_to(ROOT)}")
    return 0


# MOPS code 6985 is not one insurer. It is Taishin Life — about NT$300bn of
# invested assets — until the Shin Kong merger, and the renamed survivor
# afterwards, an insurer ten times the size (4.61). Keying rows on the code
# alone put a 1.1% hedge ratio into Shin Kong's series for five quarters, which
# is Taishin's ratio and correct for Taishin.
#
# The split is on the FILING, not on the row's own date, because 2025-12-31 is
# reported twice and means two different companies:
#
#   202504_6985 (FY25, standalone)     USD   870,000 千元  -> Taishin Life
#   202601_6985 (1Q26, comparative)    USD 27,400,000 千元  -> Shin Kong Life
#
# The second is the merged book restated. Dating on as_of would have taken the
# larger of the two and called it Taishin; dating on the filing keeps both, as
# what each of them is.
#
# Splitting rather than dropping also keeps Taishin Life, a tenth insurer the
# sell-side workbook does not carry at all.
RENAMED = {"shinkong_life": ("taishin_life", (2026, 1))}


def entity_at(name, filing, as_of=None):
    """The insurer that filing code actually was when the filing was made.

    Returns None for a row that cannot be attributed. Under a renamed code a
    COMPARATIVE column cannot be: the 1Q26 filing shows 2025-12-31 at USD
    27.4bn and 2025-03-31 at USD 840mn in the same table — one restated for the
    merger and one not — and nothing on the page says which is which. Only the
    period a filing is primarily about is unambiguous, so under a renamed code
    that is all that is kept. Nothing is lost by it: Shin Kong's own deck
    covers every quarter this discards.
    """
    before = RENAMED.get(name)
    if not before:
        return name
    m = re.match(r"(\d{4})(\d{2})_", filing or "")
    if not m:
        return None
    y, q = int(m.group(1)), int(m.group(2))
    if as_of and as_of != f"{y}-{QUARTER_END.get(q, '12-31')}":
        return None
    return name if (y, q) >= before[1] else before[0]


QUARTER_END = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


def main():
    args = sys.argv[1:]
    if args and args[0] == "reparse":
        return reparse()
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
