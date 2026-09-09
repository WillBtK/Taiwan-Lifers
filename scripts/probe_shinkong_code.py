#!/usr/bin/env python3
"""Find where the PRE-2026 Shin Kong Life's statements are filed.

WHY THIS EXISTS
MOPS code 6985 is Taishin Life, renamed Shin Kong Life on 2026-01-01 after
Taishin absorbed the group (decision 4.61). The insurer every external series
means by "Shinkong" — 統編 03458902, about NT$3.5tn of invested assets — is a
different legal entity, and this project holds no filing for it at all. Without
one, Shinkong is the one firm whose history cannot be verified independently by
any route.

Shin Kong Life was a wholly owned subsidiary of Shin Kong Financial Holding,
MOPS code 2888. Two candidate routes follow from that, and this probe settles
which:

  2888        the holding company's own consolidated filings. Shin Kong
              Financial was overwhelmingly the life company by assets, so its
              consolidated derivatives note and market-risk sensitivity are
              substantially the life company's. This is the likely answer.
  own code    the other nine insurers each file under a code of their own
              because each is 公開發行 in its own right (it issues subordinated
              debt). Shin Kong Life plausibly had one too, now retired from the
              registry after absorption — so the registry read that produced
              the current ten-firm list would no longer show it.

Subsidiary-style codes (28880001) are NOT a candidate: the script header of
stage6_firm_sensitivity records that MOPS does not serve them, and a direct
probe of 28880001 for ROC 113 returned nothing.

WHY IT RUNS IN CI
doc.twse.com.tw answers with a WAF page rather than a 4xx and is currently
blocking the development sandbox — a probe from here returned four consecutive
block pages. A runner has a different address. Same reasoning as
probe-derivative-note and pull-firm-statements.

Run: python3 scripts/probe_shinkong_code.py [co_id ...]
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "s6", ROOT / "scripts" / "stage6_firm_sensitivity.py")
s6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s6)

# 2888 first because it is the hypothesis. The rest of the list is the 58xx
# block the other unlisted insurers occupy (5846 Cathay, 5865 Fubon, 5873
# TransGlobe, 5874 Nan Shan are known), swept for a retired neighbour.
# The codes the first full sweep found to have filings, so the run goes
# straight to identification instead of re-sweeping fifty codes for twenty
# minutes. 2888 leads because it is still the hypothesis.
CANDIDATES = ["2888", "5840", "5841", "5842", "5843", "5844", "5847", "5848",
              "5849", "5852", "5854", "5857", "5858", "5859", "5862", "5863",
              "5864", "5866", "5867", "5870", "5871", "5872", "5875", "5876",
              "5878"]
# Years chosen so the entity is unambiguously the OLD Shin Kong Life: well
# before the 2025 group merger and the 2026-01-01 rename.
SWEEP_YEAR = 112
CONFIRM_YEARS = [112, 110]
NAME = re.compile(r"([一-鿿]{2,10}(?:人壽|金融控股|產物|保險)"
                  r"[一-鿿]{0,8}股份有限公司)")


def identify(co_id, filing):
    """Read the filer's own name off page 1, rather than trusting the code."""
    try:
        raw = s6.pdf(co_id, filing["filename"])
    except Exception as e:                                   # noqa: BLE001
        return f"(fetch failed: {type(e).__name__})"
    if not raw:
        return "(no pdf)"
    try:
        import fitz
        # s6.pdf() returns a PATH, not bytes. fitz.open(stream=Path) raises
        # TypeError, which is why the first full run identified nothing at all:
        # 24 codes found, 24 "(unreadable: TypeError)".
        doc = fitz.open(str(raw)) if isinstance(raw, Path) else \
            fitz.open(stream=raw, filetype="pdf")
        head = " ".join(doc[i].get_text() for i in range(min(3, doc.page_count)))
    except Exception as e:                                   # noqa: BLE001
        return f"(unreadable: {type(e).__name__})"
    m = NAME.search(re.sub(r"\s+", "", head))
    return m.group(1) if m else "(name not found on first pages)"


def say(*a):
    """Print and FLUSH.

    The first run of this probe found a live candidate, wrote the result into
    a buffer, and was killed at the job ceiling before Python flushed it. The
    only line that survived was an incidental stderr warning. A probe whose
    findings die with the process is worse than no probe: it costs the run and
    reports nothing.
    """
    print(*a, flush=True)


def main():
    cands = sys.argv[1:] or CANDIDATES
    s6.purge()
    say(f"phase 1: index sweep, {len(cands)} codes, ROC {SWEEP_YEAR}\n")
    # Two phases, because identification is the slow half. A hit costs a
    # multi-megabyte statement download; doing that inline meant the sweep had
    # not finished its first pass when the job ran out of time. The index pass
    # alone answers "which codes exist", which is most of the question.
    hits = {}
    for co in cands:
        rows, err = s6.index(co, SWEEP_YEAR)
        if err:
            say(f"  {co}: {err}")
            continue
        if rows:
            hits[co] = rows
            say(f"  {co}: {len(rows)} filings  e.g. {rows[0]['filename']}")
    say(f"\nphase 1 done: {len(hits)} of {len(cands)} codes have filings"
        f" -> {sorted(hits)}\n")
    if not hits:
        say("no candidate returned filings. If 2888 is among the codes tried "
            "and returned nothing, the pre-2026 Shin Kong Life does not file "
            "on MOPS under the holding company either, and that is itself the "
            "finding.")
        return 0

    say("phase 2: read each filer's own name off page 1")
    found = []
    for co, rows in hits.items():
        who = identify(co, rows[0])
        say(f"  {co}: {who}")
        found.append((co, len(rows), who))

    say(f"\n{'co_id':<8}{'filings':>8}  filer")
    for co, n, who in found:
        mark = "  <-- SHIN KONG" if "新光" in who else ""
        say(f"{co:<8}{n:>8}  {who}{mark}")
    sk = [c for c, _, w in found if "新光" in w]
    if sk:
        say(f"\nPRE-2026 SHIN KONG LIFE FILES UNDER: {', '.join(sk)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
