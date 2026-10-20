"""
Ranks channels your monitored channels forward from, to help you grow your
channel list (see docs/getting-good-results.md: Finding channels to monitor).

Only counts posts scraped since forward-detection was fixed — run the
scraper again first if you want this to reflect your current channel list.

Usage:
    python3 snowball_channels.py
    python3 snowball_channels.py --min-sources 3
"""

import argparse
import csv
from pathlib import Path

from channels import load_channels
from db import get_conn

OUT_PATH = Path(__file__).parent / "data" / "snowball_candidates.csv"


def find_candidates(min_sources: int) -> list[dict]:
    known = {h.lower() for h in load_channels()}

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT forwarded_from, COUNT(*) as times_forwarded,
                   COUNT(DISTINCT channel) as source_count,
                   GROUP_CONCAT(DISTINCT channel) as sources
            FROM messages
            WHERE forwarded_from IS NOT NULL
            GROUP BY forwarded_from
            ORDER BY source_count DESC, times_forwarded DESC
        """).fetchall()

    candidates = []
    for r in rows:
        if r["forwarded_from"].lower() in known:
            continue
        if r["source_count"] < min_sources:
            continue
        sources = sorted(r["sources"].split(","))
        candidates.append({
            "handle": r["forwarded_from"],
            "your_channels_forwarding_from_it": r["source_count"],
            "times_forwarded": r["times_forwarded"],
            "forwarded_by": ", ".join(sources[:5]) + (" ..." if len(sources) > 5 else ""),
        })
    return candidates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rank channels your channels forward from most")
    parser.add_argument(
        "--min-sources", type=int, default=2,
        help="Only keep channels forwarded from by at least this many of your channels (default 2)",
    )
    args = parser.parse_args()

    candidates = find_candidates(args.min_sources)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = ["handle", "your_channels_forwarding_from_it", "times_forwarded", "forwarded_by"]
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candidates)

    print(f"{len(candidates)} new candidate channels → {OUT_PATH}")
