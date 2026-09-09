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
CANDIDATES = ["2888"] + [str(c) for c in range(5840, 5890)
                         if c not in (5846, 5865, 5873, 5874)]
# Years chosen so the entity is unambiguously the OLD Shin Kong Life: well
# before the 2025 group merger and the 2026-01-01 rename.
YEARS = [112, 110]
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
        doc = fitz.open(stream=raw, filetype="pdf")
        head = " ".join(doc[i].get_text() for i in range(min(3, doc.page_count)))
    except Exception as e:                                   # noqa: BLE001
        return f"(unreadable: {type(e).__name__})"
    m = NAME.search(re.sub(r"\s+", "", head))
    return m.group(1) if m else "(name not found on first pages)"


def main():
    cands = sys.argv[1:] or CANDIDATES
    s6.purge()
    print(f"probing {len(cands)} candidate codes over ROC {YEARS}\n")
    found = []
    for co in cands:
        hits = []
        for y in YEARS:
            rows, err = s6.index(co, y)
            if err:
                print(f"  {co} ROC{y}: {err}")
                continue
            if rows:
                hits += rows
        if not hits:
            continue
        who = identify(co, hits[0])
        print(f"  {co}: {len(hits)} filings   filer = {who}")
        found.append((co, len(hits), who))
    print()
    if not found:
        print("no candidate returned filings. The pre-2026 Shin Kong Life may "
              "not file on MOPS under any code of its own, in which case the "
              "holding company's consolidated statements are the only route "
              "and 2888 returning nothing would itself be the finding.")
        return 0
    print(f"{'co_id':<8}{'filings':>8}  filer")
    for co, n, who in found:
        mark = "  <-- SHIN KONG" if ("新光" in who) else ""
        print(f"{co:<8}{n:>8}  {who}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
