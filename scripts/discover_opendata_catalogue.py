#!/usr/bin/env python3
"""Discover which hosts actually serve Taiwan's insurance open data.

data.gov.tw's front-end `list` endpoint ignores every filter parameter tried
(`search_count` stays at the full 53,111 regardless), so an agency's datasets
cannot be enumerated directly. The workable route is keyword `dropdown` for
candidate ids, then `detail` per id for the resource urls, which is what this
does. Slow by construction (one request per dataset) and worth re-running only
when the question is "has a new source appeared", not routinely.

Its purpose is to answer a specific question cheaply the next time it comes
up: is there a reachable host carrying what ins-info carries? The answer as of
2026-09-05 is no (decisions 4.14), and the evidence is the output — TII's
firm-level tables are business volume only.

Writes config/tii_tables.tsv (the TableID catalogue, which cannot be guessed)
and prints the host distribution.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "config" / "tii_tables.tsv"
TERMS = ["壽險", "人身保險", "保險業", "產險", "資金運用", "責任準備金",
         "保費", "保險", "外匯", "投資", "清償能力", "資本"]
UA = "Mozilla/5.0 (compatible; TLFX/1.0)"


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main():
    ids = {}
    for t in TERMS:
        url = ("https://data.gov.tw/api/front/dataset/dropdown?list_type=published&qs="
               + urllib.parse.quote(t))
        try:
            for x in get(url).get("payload", []):
                i = x.get("id") or x.get("nid")
                if i:
                    ids[str(i)] = x.get("title") or x.get("name") or ""
        except Exception as e:
            print(f"search failed {t}: {e}", file=sys.stderr)
    print(f"candidate datasets: {len(ids)}")

    hosts, tii = {}, []
    for n, (i, title) in enumerate(sorted(ids.items()), 1):
        try:
            d = get(f"https://data.gov.tw/api/front/dataset/detail?nid={i}")["payload"]
        except Exception:
            continue
        for r in d.get("resources", []):
            u = r.get("url") or ""
            h = urllib.parse.urlparse(u).netloc.lower()
            if h:
                hosts[h] = hosts.get(h, 0) + 1
            if "tii.org.tw" in h:
                m = re.search(r"TableID=([A-Za-z0-9]+)", u)
                tii.append((m.group(1) if m else "?", i, title.strip()))
        if n % 200 == 0:
            print(f"  ...{n}/{len(ids)}", file=sys.stderr)
        time.sleep(0.05)

    rows = sorted(set(tii))
    header = [
        "# TII open-data tables reachable at "
        "openapi.tii.org.tw/TIIOpenData/API/CSV_EXPORT?TableID=<id>",
        "# Discovered by scripts/discover_opendata_catalogue.py (decisions 4.14).",
        "# TableIDs cannot be guessed (I17 and I172 both answer 'table not find!');",
        "# they come only from a data.gov.tw dataset's resource url. FIRM-LEVEL tables",
        "# here are business volume only (公司別 = by company: premiums, contracts).",
        "# Nothing on this host carries firm balance sheets or firm fund utilisation,",
        "# which is why the ins-info dependency survives.",
        "table_id\tdata_gov_nid\ttitle_zh\tfirm_level",
    ]
    body = [f"{t}\t{i}\t{ttl}\t{'yes' if ('公司別' in ttl or '按公司' in ttl) else 'no'}"
            for t, i, ttl in rows]
    OUT.write_text("\n".join(header + body) + "\n", encoding="utf-8")

    print("\nresource hosts (top 20):")
    for h, c in sorted(hosts.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {c:>5}  {h}")
    print(f"\nTII tables: {len(rows)} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
