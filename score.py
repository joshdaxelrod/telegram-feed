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
import re
from datetime import datetime, timedelta, timezone

from db import get_conn
from filters import is_junk


def virality_score(views: int) -> float:
    return float(views)


def _fetch_window(conn, since: str) -> list[dict]:
    query = """
        SELECT channel, message_id, date, text, views, media_type
        FROM messages
        WHERE date >= :since
          AND text != ''
    """
    rows = conn.execute(query, {"since": since}).fetchall()
    return [dict(r) for r in rows if not is_junk(r["text"] or "")]


# --- Cross-channel deduplication -------------------------------------------
#
# Copies of the same post rarely match character for character: each channel
# appends its own signature ("Folgt uns auf Telegram…", "Im Kanal @X gibt es
# mehr"), line breaks differ, and some copies are cut off with "…". So posts
# are compared on a normalized "content key" instead of raw text.

# A line a channel repeats on at least this many of its own (different)
# posts is treated as that channel's signature, not content.
SIGNATURE_MIN_POSTS = 3
# How far back to look when learning each channel's signature lines.
SIGNATURE_LOOKBACK_HOURS = 168
# Longer lines are always content: signatures are short, and a channel
# repeating a long paragraph is repeating a claim, not signing off.
SIGNATURE_MAX_LINE_CHARS = 100
# Below this many characters of real content, posts only merge on an exact
# match, and get no "N channels" badge — two-word captions would otherwise
# "match" loosely across dozens of channels.
MIN_DEDUP_CHARS = 30
SHORT_GROUP_PREFIX = "short:"
# Content keys are compared on this many leading characters.
DEDUP_KEY_CHARS = 200

_URL_RE = re.compile(r"https?://\S+|\bt\.me/\S+|\bwww\.\S+", re.IGNORECASE)
_HANDLE_RE = re.compile(r"@\w+")
_NON_WORD_RE = re.compile(r"[\W_]+")
_OUTSIDE_LINK_RE = re.compile(r"https?://(?!t\.me/)\S+", re.IGNORECASE)
_TRUNCATED_RE = re.compile(r"(…|\.\.\.)\s*$")


def _normalize(text: str) -> str:
    """Lowercase, drop links/@handles/emoji/punctuation, collapse whitespace."""
    text = _URL_RE.sub(" ", text.lower())
    text = _HANDLE_RE.sub(" ", text)
    return _NON_WORD_RE.sub(" ", text).strip()


def _signature_lines(rows: list[dict]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Per channel: (1) the normalized lines it repeats across
    SIGNATURE_MIN_POSTS+ different posts, and (2) short texts it posts
    verbatim that often (e.g. an image caption like "Im Kanal @X gibt es
    mehr" on every picture). A longer post reposted counts once, so a
    channel repeating a claim doesn't turn that claim into a "signature"."""
    post_counts: dict[tuple[str, str], int] = {}
    line_posts: dict[tuple[str, str], int] = {}
    for r in rows:
        text = r["text"] or ""
        post_key = (r["channel"], _normalize(text))
        post_counts[post_key] = post_counts.get(post_key, 0) + 1
        if post_counts[post_key] > 1:
            continue
        for line in {_normalize(l) for l in text.splitlines()}:
            if line and len(line) <= SIGNATURE_MAX_LINE_CHARS:
                key = (r["channel"], line)
                line_posts[key] = line_posts.get(key, 0) + 1

    signatures: dict[str, set[str]] = {}
    for (channel, line), n in line_posts.items():
        if n >= SIGNATURE_MIN_POSTS:
            signatures.setdefault(channel, set()).add(line)
    fillers: dict[str, set[str]] = {}
    for (channel, text), n in post_counts.items():
        if n >= SIGNATURE_MIN_POSTS and 0 < len(text) < MIN_DEDUP_CHARS:
            fillers.setdefault(channel, set()).add(text)
    return signatures, fillers


def _content_key(text: str, signature: set[str]) -> tuple[str, bool]:
    """(normalized text minus the channel's signature lines, whether
    anything was stripped as signature)."""
    kept, stripped = [], False
    for line in text.splitlines():
        norm = _normalize(line)
        if not norm:
            continue
        if norm in signature:
            stripped = True
            continue
        kept.append(norm)
    return " ".join(kept), stripped


def _annotate_content_keys(conn, candidates: list[dict], since: str) -> list[dict]:
    """Sets r["_key"] (content key) and r["_truncated"] on each candidate, and
    drops posts that are nothing but the channel's signature or filler."""
    lookback = (
        datetime.now(timezone.utc) - timedelta(hours=SIGNATURE_LOOKBACK_HOURS)
    ).isoformat()
    history = conn.execute(
        "SELECT channel, text FROM messages WHERE date >= ? AND text != ''",
        (min(lookback, since),),
    ).fetchall()
    signatures, fillers = _signature_lines([dict(r) for r in history])

    kept = []
    for r in candidates:
        text = r["text"] or ""
        key, stripped = _content_key(text, signatures.get(r["channel"], set()))
        # A link to an outside article is content even with no text around it.
        if not _OUTSIDE_LINK_RE.search(text):
            if stripped and not key:
                continue  # signature-only post
            if _normalize(text) in fillers.get(r["channel"], ()):
                continue  # short text the channel posts over and over
        r["_key"] = key
        r["_truncated"] = bool(_TRUNCATED_RE.search(text.strip()))
        kept.append(r)
    return kept


def _group_keys(candidates: list[dict]) -> list[str | None]:
    """The dedup group for each candidate (None = never merge). A post cut
    off with "…" joins the group of a longer post its text is a prefix of."""
    full_keys = [r["_key"] for r in candidates if not r["_truncated"]]
    groups = []
    for r in candidates:
        key = r["_key"]
        if not key:
            groups.append(None)
            continue
        if len(key) < MIN_DEDUP_CHARS:
            # Exact matches only — and see get_top_messages: no badge,
            # since a shared two-word caption doesn't mean a shared post.
            groups.append(SHORT_GROUP_PREFIX + key)
            continue
        if r["_truncated"] and len(key) < DEDUP_KEY_CHARS:
            # The last word may be cut mid-word, which still prefix-matches.
            longer = next((k for k in full_keys if len(k) > len(key) and k.startswith(key)), None)
            if longer:
                key = longer
        groups.append(key[:DEDUP_KEY_CHARS])
    return groups


def get_top_messages(
    hours: int = 24,
    limit: int = 50,
    max_per_channel: int = 5,
) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    with get_conn() as conn:
        candidates = _fetch_window(conn, since)
        candidates = _annotate_content_keys(conn, candidates, since)

    candidates.sort(key=lambda r: r["views"], reverse=True)

    # Deduplicate by content — the same claim carried by multiple channels
    # collapses into one result; channel_count is how many distinct
    # channels carried it (the amplification signal).
    seen: dict[str, dict] = {}
    channels_by_group: dict[str, set[str]] = {}
    results = []
    per_channel: dict[str, int] = {}

    for r, group in zip(candidates, _group_keys(candidates)):
        if group is not None and group in seen:
            channels_by_group[group].add(r["channel"])
            continue
        if per_channel.get(r["channel"], 0) >= max_per_channel:
            continue
        per_channel[r["channel"]] = per_channel.get(r["channel"], 0) + 1
        results.append(r)
        if group is not None:
            seen[group] = r
            channels_by_group[group] = {r["channel"]}

    for r in results:
        r["virality_score"] = virality_score(r["views"])
        r["channel_count"] = 1
    for group, r in seen.items():
        if not group.startswith(SHORT_GROUP_PREFIX):
            r["channel_count"] = len(channels_by_group[group])
    for r in candidates:
        r.pop("_key", None)
        r.pop("_truncated", None)

    results.sort(key=lambda x: x["virality_score"], reverse=True)
    return results[:limit]


def get_random_messages(
    hours: int = 24,
    limit: int = 30,
    seed: int | None = None,
) -> list[dict]:
    """A random sample of messages from the window — for browsing outside
    whatever the popularity ranking happens to surface."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    with get_conn() as conn:
        candidates = _fetch_window(conn, since)

    rng = random.Random(seed)
    rng.shuffle(candidates)

    for r in candidates:
        r["virality_score"] = virality_score(r["views"])
        r["channel_count"] = 1

    return candidates[:limit]


def get_spotlight_messages(
    hours: int = 24,
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
        candidates = _fetch_window(conn, since)

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
    limit: int = 100,
    match_all: bool = False,
) -> list[dict]:
    """match_all=False (default): any keyword matches (for --keywords on the
    CLI, where each item is an independent term). match_all=True: every
    keyword must be present somewhere in the text, not necessarily
    adjacent — use this for a trending bigram like "chrupalla souveränes",
    since the two words were adjacent in the *filtered* token stream that
    built the term, not necessarily in the original text (a stopword
    could well have sat between them)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    joiner = " AND " if match_all else " OR "
    kw_clause = joiner.join(f"ULOWER(text) LIKE :kw{i}" for i in range(len(keywords)))
    exc_clause = " AND ".join(f"ULOWER(text) NOT LIKE :ex{i}" for i in range(len(exclude or [])))
    exc_clause = f"AND ({exc_clause})" if exc_clause else ""
    params = {"since": since}
    for i, kw in enumerate(keywords):
        params[f"kw{i}"] = f"%{kw.lower()}%"
    for i, ex in enumerate(exclude or []):
        params[f"ex{i}"] = f"%{ex.lower()}%"

    query = f"""
        SELECT channel, message_id, date, text, views, media_type
        FROM messages
        WHERE date >= :since
          AND text != ''
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


def get_messages_by_keys(keys: set[tuple[str, int]], limit: int = 50) -> list[dict]:
    """The given (channel, message_id) posts, most-viewed first — for a
    trending term's detail page, so it shows exactly the posts behind the
    term instead of a fuzzy keyword search."""
    if not keys:
        return []
    with get_conn() as conn:
        conn.execute("CREATE TEMP TABLE wanted (channel TEXT, message_id INTEGER)")
        conn.executemany("INSERT INTO wanted VALUES (?, ?)", keys)
        rows = conn.execute("""
            SELECT m.channel, m.message_id, m.date, m.text, m.views, m.media_type
            FROM messages m JOIN wanted w
              ON m.channel = w.channel AND m.message_id = w.message_id
            ORDER BY m.views DESC
            LIMIT ?
        """, (limit,)).fetchall()
    results = []
    for row in rows:
        r = dict(row)
        r["virality_score"] = virality_score(r["views"])
        r["channel_count"] = 1
        results.append(r)
    return results


def print_digest(hours: int = 24, top_n: int = 20):
    messages = get_top_messages(hours=hours, limit=top_n * 2)[:top_n]

    print(f"\n=== Top {top_n} viral messages — last {hours}h ===\n")

    for i, msg in enumerate(messages, 1):
        date = msg["date"][:16].replace("T", " ")
        snippet = (msg["text"] or "")[:200].replace("\n", " ")
        print(
            f"{i:2}. @{msg['channel']} | {date}\n"
            f"    views={msg['views']}  score={msg['virality_score']:.0f}\n"
            f"    {snippet}\n"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    print_digest(hours=args.hours, top_n=args.top)
