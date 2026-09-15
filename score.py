"""
Virality scoring and feed queries.

Virality score = views. Views are the only reliable per-post signal
available from public web scraping — Telegram's t.me/s/ preview doesn't
expose a forward count (an earlier version of this tool tried scraping one;
it was present on well under 1% of messages and absent from every channel
checked live, so it was dropped rather than shown as if it meant something).
channel_count (cross-channel duplication) is captured and displayed as
context but not used in ranking.

Three feed queries:
- get_top_messages     — globally most-viewed posts ("popular" feed)
- get_random_messages  — a random sample, for serendipitous browsing
- get_spotlight_messages — each channel's own top post(s), interleaved,
  so smaller channels surface alongside the biggest ones
"""

import random
from datetime import datetime, timedelta, timezone

from db import get_conn
from filters import is_junk


def virality_score(views: int) -> float:
    return float(views)


def _fetch_window(conn, since: str, tier: str | None) -> list[dict]:
    tier_clause = "AND tier = :tier" if tier else ""
    query = f"""
        SELECT channel, tier, message_id, date, text, views, media_type
        FROM messages
        WHERE date >= :since
          AND text != ''
          {tier_clause}
    """
    rows = conn.execute(query, {"since": since, "tier": tier}).fetchall()
    return [dict(r) for r in rows if not is_junk(r["text"] or "")]


def get_top_messages(
    hours: int = 24,
    tier: str | None = None,
    limit: int = 50,
    max_per_channel: int = 5,
) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    with get_conn() as conn:
        candidates = _fetch_window(conn, since, tier)

    candidates.sort(key=lambda r: r["views"], reverse=True)

    # Deduplicate by text content — same claim carried by multiple channels
    # collapses into one result; channel_count tracks the amplification signal.
    seen: dict[str, dict] = {}
    channel_counts: dict[str, int] = {}

    for r in candidates:
        key = r["text"].strip()[:200]
        if key not in seen:
            channel_count = channel_counts.get(r["channel"], 0)
            if channel_count >= max_per_channel:
                continue
            r["channel_count"] = 1
            seen[key] = r
            channel_counts[r["channel"]] = channel_count + 1
        else:
            seen[key]["channel_count"] += 1

    for r in seen.values():
        r["virality_score"] = virality_score(r["views"])

    results = sorted(seen.values(), key=lambda x: x["virality_score"], reverse=True)
    return results[:limit]


def get_random_messages(
    hours: int = 24,
    tier: str | None = None,
    limit: int = 30,
    seed: int | None = None,
) -> list[dict]:
    """A random sample of messages from the window — for browsing outside
    whatever the popularity ranking happens to surface."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    with get_conn() as conn:
        candidates = _fetch_window(conn, since, tier)

    rng = random.Random(seed)
    rng.shuffle(candidates)

    for r in candidates:
        r["virality_score"] = virality_score(r["views"])
        r["channel_count"] = 1

    return candidates[:limit]


def get_spotlight_messages(
    hours: int = 24,
    tier: str | None = None,
    per_channel: int = 1,
    limit: int | None = 100,
    seed: int | None = None,
) -> list[dict]:
    """Each channel's own top `per_channel` post(s) by views, interleaved
    across channels in a shuffled order — so a small channel's best post
    shows up next to a giant channel's best post, instead of the feed
    being dominated by whichever channels are biggest."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    with get_conn() as conn:
        candidates = _fetch_window(conn, since, tier)

    by_channel: dict[str, list[dict]] = {}
    for r in candidates:
        by_channel.setdefault(r["channel"], []).append(r)

    for msgs in by_channel.values():
        msgs.sort(key=lambda m: m["views"], reverse=True)

    channel_order = list(by_channel.keys())
    random.Random(seed).shuffle(channel_order)

    interleaved = []
    for rank in range(per_channel):
        for channel in channel_order:
            msgs = by_channel[channel]
            if rank < len(msgs):
                r = msgs[rank]
                r["virality_score"] = virality_score(r["views"])
                r["channel_count"] = 1
                interleaved.append(r)

    return interleaved[:limit] if limit else interleaved


def get_keyword_messages(
    keywords: list[str],
    exclude: list[str] | None = None,
    hours: int = 168,
    tier: str | None = None,
    limit: int = 100,
) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    tier_clause = "AND tier = :tier" if tier else ""
    kw_clause = " OR ".join(f"LOWER(text) LIKE :kw{i}" for i in range(len(keywords)))
    exc_clause = " AND ".join(f"LOWER(text) NOT LIKE :ex{i}" for i in range(len(exclude or [])))
    exc_clause = f"AND ({exc_clause})" if exc_clause else ""
    params = {"since": since, "tier": tier}
    for i, kw in enumerate(keywords):
        params[f"kw{i}"] = f"%{kw.lower()}%"
    for i, ex in enumerate(exclude or []):
        params[f"ex{i}"] = f"%{ex.lower()}%"

    query = f"""
        SELECT channel, tier, message_id, date, text, views, media_type
        FROM messages
        WHERE date >= :since
          AND text != ''
          {tier_clause}
          AND ({kw_clause})
          {exc_clause}
        ORDER BY views DESC
        LIMIT :limit
    """
    params["limit"] = limit * 3  # over-fetch since junk filtering happens after the query

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        if is_junk(r["text"] or ""):
            continue
        r["virality_score"] = virality_score(r["views"])
        r["channel_count"] = 1
        results.append(r)
        if len(results) >= limit:
            break
    return results


def print_digest(hours: int = 24, tier: str | None = None, top_n: int = 20):
    messages = get_top_messages(hours=hours, tier=tier, limit=top_n * 2)[:top_n]

    label = tier or "all tiers"
    print(f"\n=== Top {top_n} viral messages — last {hours}h ({label}) ===\n")

    for i, msg in enumerate(messages, 1):
        date = msg["date"][:16].replace("T", " ")
        snippet = (msg["text"] or "")[:200].replace("\n", " ")
        print(
            f"{i:2}. [{msg['tier']}] @{msg['channel']} | {date}\n"
            f"    views={msg['views']}  score={msg['virality_score']:.0f}\n"
            f"    {snippet}\n"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--tier")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    print_digest(hours=args.hours, tier=args.tier, top_n=args.top)
