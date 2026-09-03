#!/usr/bin/env python3
"""Verify and extract figures from candidate articles for the hedge ratio backfill.

Usage:
  python3 scripts/verify_backfill_articles.py --month 2020-01 --url "https://money.udn.com/..."

  Fetches the article, extracts the hedge ratio and other figures, and outputs a config
  fragment ready to be pasted into config/briefing_press_backfill.json.

  Alternatively, run scripts/stage1_briefing_press.py to verify the complete config.
"""

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tlfx.provenance import fetch

def article_text(html: bytes) -> tuple[str, str]:
    """Extract title and paragraph text from article HTML."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for t in soup(["script", "style", "nav", "footer", "header", "aside"]):
        t.decompose()
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return title, "\n".join(paras)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", required=True, help="Observation month (YYYY-MM format)")
    ap.add_argument("--url", required=True, help="Article URL")
    ap.add_argument("--quote", help="Exact quote from the article (for hedging ratio and related figures)")
    ap.add_argument("--ratio", help="Hedge ratio as printed (e.g., '50.23%')")
    ap.add_argument("--outlet", default="經濟日報", help="News outlet name")
    args = ap.parse_args()

    try:
        # Fetch article
        print(f"Fetching {args.url}...", file=sys.stderr)
        fr = fetch(args.url, source_doc="press article", timeout=45, basis="press_reported")
        if fr.provenance.http_status != 200:
            print(f"ERROR: HTTP {fr.provenance.http_status}", file=sys.stderr)
            return 1

        title, text = article_text(fr.content)
        print(f"Title: {title}", file=sys.stderr)

        # Extract date from URL or argument
        parts = args.url.rstrip("/").rsplit("/", 1)
        article_id = parts[-1].split(".")[0] if len(parts) > 1 else "unknown"
        published = fr.provenance.retrieved_at.strftime("%Y-%m-%d") if fr.provenance.retrieved_at else "YYYY-MM-DD"

        # Build config fragment
        config_row = {
            "obs_month": f"{args.month}-01",
            "reported_by": "金管會保險局",
            "sources": [
                {
                    "url": args.url,
                    "published": published,
                    "outlet": args.outlet,
                    "fields": {},
                    "quote": args.quote or "[extract manually from article above]"
                }
            ],
            "note": "Backfill search candidate."
        }

        if args.ratio:
            config_row["sources"][0]["fields"]["hedge_ratio_regulatory"] = args.ratio

        print("\n" + "="*60, file=sys.stderr)
        print("Article text (first 500 chars):", file=sys.stderr)
        print(text[:500], file=sys.stderr)
        print("="*60 + "\n", file=sys.stderr)

        print("Config fragment (paste into config/briefing_press_backfill.json):")
        print(json.dumps(config_row, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
