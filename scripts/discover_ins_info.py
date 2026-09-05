#!/usr/bin/env python3
"""Map the Insurance Bureau's disclosure portal through the Taiwan relay.

The portal is reachable only from Taiwan (decisions 4.13), and neither this
sandbox nor a GitHub runner can call the relay and the portal directly in the
same place — the sandbox's proxy refuses `*.run.app`. So exploration runs on
the runner, where both are reachable, and reports back through the repository:
`.github/workflows/discover-ins-info.yml` runs this and commits the result to
`reports/ins_info_map.json`.

That indirection is the whole design. Reading a page, deciding what to follow,
and reading the next one is a loop that normally happens interactively; here
each turn of it costs a workflow run, so the script does as much as possible
per pass — fetching every candidate, extracting the links and query shapes
from each, and reporting enough structure to choose the next targets without
guessing.

Candidates live in `config/ins_info_targets.tsv` so the next pass is a data
change rather than a code change.
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
TARGETS = ROOT / "config" / "ins_info_targets.tsv"
OUT = ROOT / "reports" / "ins_info_map.json"
UA = "Mozilla/5.0 (compatible; TLFX/1.0)"


def via_relay(url, timeout=120):
    base = os.environ.get("TAIWAN_RELAY_URL", "").strip()
    token = os.environ.get("TAIWAN_RELAY_TOKEN", "").strip()
    if not base or not token:
        raise RuntimeError("relay not configured")
    req = urllib.request.Request(
        base.rstrip("/") + "/fetch?url=" + urllib.parse.quote(url, safe=""),
        headers={"User-Agent": UA, "X-Relay-Token": token})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def decode(body):
    """The portal is a Big5 ASP.NET site; some endpoints answer UTF-8 JSON."""
    for enc in ("utf-8", "big5", "cp950"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", "replace")


def summarise(url, text, ctype):
    """Extract what the next pass would need to choose targets."""
    info = {}
    stripped = text.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            data = json.loads(text)
            info["kind"] = "json"
            if isinstance(data, list):
                info["records"] = len(data)
                if data and isinstance(data[0], dict):
                    info["fields"] = list(data[0].keys())
                    info["first_record"] = data[0]
            return info
        except json.JSONDecodeError:
            pass
    info["kind"] = "html" if "<" in text[:400] else "other"
    # links, keeping the query shape which is what identifies a report endpoint
    links = sorted({urllib.parse.urljoin(url, h) for h in
                    re.findall(r'(?:href|action|src)="([^"]+\.aspx[^"]*)"', text, re.I)})
    info["aspx_links"] = links[:80]
    info["aspx_link_count"] = len(links)
    # the portal identifies companies by UID and reports by a table code
    info["uids"] = sorted({m for m in re.findall(r'UID=([A-Za-z0-9]+)', text)})[:60]
    info["table_codes"] = sorted({m for m in re.findall(r'\b(0\d{7})\b', text)})[:60]
    # form controls reveal how a report is parameterised (year, quarter, firm)
    info["select_names"] = sorted({m for m in re.findall(r'<select[^>]*name="([^"]+)"', text, re.I)})[:40]
    titles = re.findall(r"<title>(.*?)</title>", text, re.I | re.S)
    info["title"] = titles[0].strip()[:120] if titles else None
    return info


def main():
    if not TARGETS.exists():
        raise SystemExit(f"missing {TARGETS.relative_to(ROOT)}")
    rows = []
    for line in TARGETS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            note, _, url = line.partition("\t")
            rows.append((note.strip(), url.strip() or note.strip()))

    report = {"run_at": dt.datetime.now(dt.timezone.utc).isoformat(), "targets": []}
    ok = 0
    for note, url in rows:
        entry = {"note": note, "url": url}
        try:
            status, ctype, body = via_relay(url)
            text = decode(body)
            entry.update(status=status, content_type=ctype, bytes=len(body),
                         **summarise(url, text, ctype))
            ok += 1
            print(f"OK   {status} {len(body):>8,}b  {note}")
        except Exception as e:
            entry.update(error=f"{type(e).__name__}: {e}")
            print(f"FAIL              {note}: {e}")
        report["targets"].append(entry)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{ok}/{len(rows)} reachable -> {OUT.relative_to(ROOT)}")
    # A discovery pass that reaches nothing is a failure worth surfacing; one
    # that reaches some targets and not others is information, not an error.
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
