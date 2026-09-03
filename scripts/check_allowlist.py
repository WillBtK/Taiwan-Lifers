#!/usr/bin/env python3
"""Probe one URL per allowlisted host and record the result.

Stage 0 deliverable (README section 7). Reads `config/allowlist.tsv`, fetches
each probe URL, and writes a JSON report to `reports/` plus a Markdown
summary to stdout.

Exit codes:
    0  every tier-1 host reachable
    1  at least one tier-1 host unreachable
    2  configuration error

Tier-2 and tier-3 failures are reported but do not fail the run: they are
needed at Stage 3 and later, and several are known to block automated
access (MOPS is JavaScript-rendered and rate-limited).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tlfx.provenance import Provenance, RunLog, ca_bundle_for, sha256_hex, ua_for, utc_now  # noqa: E402

import requests  # noqa: E402

CONFIG = ROOT / "config" / "allowlist.tsv"
REPORT_DIR = ROOT / "reports"
TIMEOUT = 20
WORKERS = 4
TRANSPORT_RETRIES = 2


def load_probes(path: Path) -> list[dict]:
    if not path.exists():
        print(f"missing config: {path}", file=sys.stderr)
        raise SystemExit(2)
    probes = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) < 3:
            print(f"malformed line {lineno}: {raw!r}", file=sys.stderr)
            raise SystemExit(2)
        host, tier, url = parts[0].strip(), parts[1].strip(), parts[2].strip()
        expect = parts[3].strip() if len(parts) > 3 else ""
        note = parts[4].strip() if len(parts) > 4 else ""
        probes.append(
            {
                "host": host,
                "tier": int(tier),
                "url": url,
                # Some endpoints are reachable but answer non-2xx by design
                # (the FRED API returns 400 without a key). `expect` names the
                # status that counts as success for those.
                "expect": int(expect) if expect else None,
                "note": note,
            }
        )
    return probes


def probe(entry: dict, timeout: int, transport_retries: int = TRANSPORT_RETRIES) -> dict:
    """Probe one URL.

    Transport failures (connection reset, tunnel closed, read timeout) are
    retried: in a proxied sandbox they are frequently the egress path rather
    than the source, and a single attempt cannot tell a blocked host from a
    flaky one. HTTP status codes are never retried — a 403 is an answer.
    """
    url = entry["url"]
    result = dict(entry)
    last_exc: Exception | None = None
    for attempt in range(transport_retries + 1):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": ua_for(url), "Accept": "*/*"},
                timeout=timeout,
                stream=True,
                verify=ca_bundle_for(url),
            )
            body = resp.raw.read(65536, decode_content=True) or b""
            result.update(
                {
                    "status": resp.status_code,
                    "ok": (
                        resp.status_code == entry["expect"]
                        if entry.get("expect")
                        else 200 <= resp.status_code < 400
                    ),
                    "final_url": resp.url,
                    "redirected": resp.url.rstrip("/") != url.rstrip("/"),
                    "content_type": resp.headers.get("content-type", ""),
                    "bytes_sampled": len(body),
                    "sha256_prefix": sha256_hex(body)[:16],
                    "elapsed_s": round(resp.elapsed.total_seconds(), 3),
                    "attempts": attempt + 1,
                    "error": None,
                }
            )
            return result
        except requests.RequestException as exc:
            last_exc = exc
    result.update(
        {
            "status": None,
            "ok": False,
            "final_url": None,
            "redirected": None,
            "content_type": "",
            "bytes_sampled": 0,
            "sha256_prefix": None,
            "elapsed_s": None,
            "attempts": transport_retries + 1,
            "error": f"{type(last_exc).__name__}: {last_exc}"[:300],
        }
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", type=int, default=3, help="probe tiers <= this (default 3)")
    ap.add_argument("--timeout", type=int, default=TIMEOUT)
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--workers", type=int, default=WORKERS, help="concurrent probes")
    args = ap.parse_args()

    probes = [p for p in load_probes(args.config) if p["tier"] <= args.tier]
    log = RunLog(stage="0-allowlist")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda e: probe(e, args.timeout), probes))
    for res in results:
        log.record_source(
            Provenance(
                source_url=res["url"],
                source_doc=f"allowlist probe: {res['host']}",
                retrieved_at=utc_now(),
                content_sha256=res["sha256_prefix"],
                http_status=res["status"],
                note=res["note"],
            ),
            ok=res["ok"],
            note=res["error"],
        )
        flag = "ok " if res["ok"] else "FAIL"
        print(f"{flag} t{res['tier']} {str(res['status']):>4}  {res['host']:<34} {res['url'][:72]}")

    REPORT_DIR.mkdir(exist_ok=True)
    report = {"summary": log.summary(), "results": results}
    out = REPORT_DIR / f"allowlist_{date.today():%Y%m%d}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    by_tier: dict[int, list[dict]] = {}
    for r in results:
        by_tier.setdefault(r["tier"], []).append(r)
    print("\n| Tier | Reachable | Probed |\n|---|---|---|")
    for tier in sorted(by_tier):
        rs = by_tier[tier]
        print(f"| {tier} | {sum(1 for r in rs if r['ok'])} | {len(rs)} |")
    print(f"\nreport: {out.relative_to(ROOT)}")

    tier1_failures = [r for r in results if r["tier"] == 1 and not r["ok"]]
    if tier1_failures:
        print("\ntier-1 hosts unreachable:", file=sys.stderr)
        for r in tier1_failures:
            print(f"  {r['host']}  {r['url']}  {r['error'] or r['status']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
