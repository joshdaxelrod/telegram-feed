"""
Traces a claim or message across the monitored channel network.

Given a search term, finds all matching messages in the database sorted
chronologically — showing which channels picked it up, when, and in what order.

Usage:
    python trace.py "Döpfner Zionist"
    python trace.py "mask mandate" --hours 168
    python trace.py "Hantavirus" --hours 72 --tier watch
"""

import argparse
from datetime import datetime, timedelta, timezone

from db import get_conn


def trace(query: str, hours: int = 168, tier: str | None = None) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    tier_clause = "AND tier = :tier" if tier else ""

    terms = query.split()
    like_clauses = " AND ".join(f"text LIKE :term{i}" for i in range(len(terms)))
    params = {"since": since, "tier": tier}
    for i, term in enumerate(terms):
        params[f"term{i}"] = f"%{term}%"

    sql = f"""
        SELECT channel, tier, message_id, date, text, views
        FROM messages
        WHERE date >= :since
          AND text != ''
          {tier_clause}
          AND {like_clauses}
        ORDER BY date ASC
    """

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]


def print_trace(query: str, hours: int = 168, tier: str | None = None):
    results = trace(query, hours=hours, tier=tier)

    if not results:
        print(f"\nNo messages found matching '{query}' in the last {hours}h.")
        return

    print(f"\n=== Trace: '{query}' — {len(results)} matches over last {hours}h ===\n")

    first_date = datetime.fromisoformat(results[0]["date"])
    for r in results:
        msg_date = datetime.fromisoformat(r["date"])
        hours_after = (msg_date - first_date).total_seconds() / 3600
        offset = f"+{hours_after:.1f}h" if hours_after > 0 else "first"

        date_str = r["date"][:16].replace("T", " ")
        snippet = (r["text"] or "").replace("\n", " ")[:160]
        post_url = f"https://t.me/{r['channel']}/{r['message_id']}"

        print(f"[{offset:>8}]  [{r['tier']}] @{r['channel']}  {date_str} UTC")
        print(f"           views={r['views']}")
        print(f"           {snippet}")
        print(f"           {post_url}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trace a claim across the channel network")
    parser.add_argument("query", help="Search terms (space-separated, all must match)")
    parser.add_argument("--hours", type=int, default=168)
    parser.add_argument("--tier")
    args = parser.parse_args()

    print_trace(args.query, hours=args.hours, tier=args.tier)
