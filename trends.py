"""
Trending terms: words/phrases spreading across many channels right now,
relative to how often they normally come up — for spotting a narrative
taking off before it shows up as an obviously "popular" post.

STOPWORDS below is a STARTING EXAMPLE in English — edit it for your own
language and channel set, same as filters.py. See the README's
"Customizing for your channels" section for exactly how.

Tune --min-channels to your channel list size: a term only counts as
trending if it appears on at least that many DISTINCT channels in the
recent window (not just that many messages — a single post copy-pasted
to 2-3 channels otherwise reads as an "infinite spike" against a zero
baseline, which is copy-paste amplification, not an organic trend). As a
starting point, try roughly 1-2% of your monitored channel count, and
raise it if results look like noise.

Usage:
    python trends.py                              # last 24h vs last 7 days
    python trends.py --recent-hours 6 --baseline-hours 168 --min-channels 3
    python trends.py --top 10
"""

import argparse
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import get_conn
from filters import is_junk
from score import _normalize

# Personal, git-ignored addition to STOPWORDS below — one word per line.
# Use this instead of editing STOPWORDS directly if you want your own
# language's stopwords locally without changing the file everyone shares.
LOCAL_STOPWORDS_PATH = Path(__file__).parent / "stopwords.local.txt"

STOPWORDS = {
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "he",
    "she", "they", "them", "his", "her", "their", "we", "us", "our", "you",
    "your", "and", "or", "but", "so", "because", "although", "however",
    "also", "then", "than", "in", "on", "at", "to", "of", "for", "with",
    "from", "by", "about", "into", "over", "under", "through", "against",
    "without", "until", "since", "during", "up", "out", "off", "what",
    "who", "where", "when", "why", "how", "which", "whom", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "can", "could", "will", "would", "shall", "should",
    "may", "might", "must", "not", "no", "nor", "https", "http", "com",
    "www", "always", "again", "there", "here",
    "channel", "telegram", "follow", "share", "click", "subscribe",
    "nothing", "today", "yesterday", "tomorrow", "now", "often",
    "sometimes", "never", "time", "week", "weeks", "day", "days", "year",
    "years", "month", "months", "hour", "hours", "minute", "minutes",
    "more", "very", "all", "some", "many", "much", "new", "first", "last",
    "other", "another", "just", "only", "even", "says", "said", "say",
    "according", "national",
}


def _load_stopwords() -> set[str]:
    words = set(STOPWORDS)
    if LOCAL_STOPWORDS_PATH.exists():
        for line in LOCAL_STOPWORDS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                words.add(line.lower())
    return words


_ACTIVE_STOPWORDS = _load_stopwords()

REPOST_WINDOW = timedelta(hours=24)

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}")


def _tokenize(text: str) -> list[str]:
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"@\w+", " ", text)
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    return [t for t in tokens if t not in _ACTIVE_STOPWORDS]


def _terms(text: str) -> set[str]:
    """Unigrams + bigrams present in a message, deduplicated within it so a
    repetitive message can't inflate a term's count on its own."""
    tokens = _tokenize(text)
    bigrams = [" ".join(tokens[i:i + 2]) for i in range(len(tokens) - 1)]
    return set(tokens) | set(bigrams)


def _fetch_range(conn, since: str, until: str) -> list[dict]:
    query = """
        SELECT channel, message_id, date, text
        FROM messages
        WHERE date >= :since AND date < :until
          AND text != ''
    """
    rows = conn.execute(query + " ORDER BY date", {"since": since, "until": until}).fetchall()
    # A channel re-posting the same text within REPOST_WINDOW is one mention,
    # not several. Copies further apart still count: a channel returning to a
    # topic day after day is part of that topic's normal baseline.
    last_kept: dict[tuple[str, str], datetime] = {}
    result = []
    for r in rows:
        text = r["text"] or ""
        if is_junk(text):
            continue
        key = (r["channel"], _normalize(text))
        date = datetime.fromisoformat(r["date"])
        prev = last_kept.get(key)
        if prev is not None and date - prev < REPOST_WINDOW:
            continue
        last_kept[key] = date
        result.append(dict(r))
    return result


def _count_terms(messages: list[dict]) -> Counter:
    counter = Counter()
    for m in messages:
        counter.update(_terms(m["text"] or ""))
    return counter


def diagnose_baseline(
    recent_hours: int = 24,
    baseline_hours: int = 168,
    as_of: datetime | None = None,
    min_ratio: float = 0.1,
) -> str | None:
    """Returns a warning if the baseline window doesn't have enough scraped
    history to make a spike ratio meaningful, else None.

    The whole scoring approach is recent rate vs. baseline rate — if the
    baseline window is nearly empty (a scraping gap, not a real quiet
    period), almost every term looks like an "infinite spike," ordinary
    grammar included, and the scores stop meaning anything."""
    now = as_of or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    recent_since = (now - timedelta(hours=recent_hours)).isoformat()
    baseline_since = (now - timedelta(hours=baseline_hours)).isoformat()
    baseline_span_hours = max(baseline_hours - recent_hours, 1)

    with get_conn() as conn:
        recent_n = len(_fetch_range(conn, recent_since, now_iso))
        baseline_n = len(_fetch_range(conn, baseline_since, recent_since))

    recent_rate = recent_n / recent_hours if recent_hours else 0
    baseline_rate = baseline_n / baseline_span_hours

    if recent_rate > 0 and baseline_rate < recent_rate * min_ratio:
        return (
            f"Only {baseline_n} messages were scraped in the "
            f"{baseline_span_hours:.0f}h before your recent window, versus "
            f"{recent_n} in the recent window itself. Trending compares "
            f"against that earlier period, so with this little history "
            f"behind it, almost anything can look like a fake \"infinite\" "
            f"spike — ordinary grammar included. This usually means there's "
            f"a gap in your scraping history (e.g. this is a new setup, or "
            f"scraping had lapsed before this run). Fix: run "
            f"`python scraper.py --hours {baseline_hours}` once to backfill "
            f"a full baseline period, then go back to your normal, smaller "
            f"scrapes — daily is enough for most channel lists."
        )
    return None


def get_trending_terms(
    recent_hours: int = 24,
    baseline_hours: int = 168,
    top_n: int = 20,
    min_recent_count: int = 3,
    min_channels: int = 5,
    as_of: datetime | None = None,
) -> list[dict]:
    """Score = (recent mention rate) / (baseline mention rate, smoothed).
    Each result's message_keys are the exact (channel, message_id) posts
    behind the term.

    min_channels requires a term to appear on at least that many distinct
    channels in the recent window — without this, a single post
    copy-pasted a few times reads as an "infinite spike" against a zero
    baseline, when it's really just one source, not an organic trend.

    A separate diversity pass then drops terms that are really just word
    fragments of an already-selected term's same underlying post(s) —
    otherwise one viral, wordy post gets sliced into a dozen overlapping
    bigrams that all "trend" together and crowd out everything else."""
    now = as_of or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    recent_since = (now - timedelta(hours=recent_hours)).isoformat()
    baseline_since = (now - timedelta(hours=baseline_hours)).isoformat()
    baseline_span_hours = max(baseline_hours - recent_hours, 1)

    with get_conn() as conn:
        recent_msgs = _fetch_range(conn, recent_since, now_iso)
        baseline_msgs = _fetch_range(conn, baseline_since, recent_since)

    recent_counts = _count_terms(recent_msgs)
    baseline_counts = _count_terms(baseline_msgs)

    channels_per_term: dict[str, set] = {}
    messages_per_term: dict[str, set] = {}
    first_seen: dict[str, str] = {}
    examples: dict[str, list[dict]] = {}
    for m in recent_msgs:
        msg_key = (m["channel"], m["message_id"])
        for term in _terms(m["text"] or ""):
            channels_per_term.setdefault(term, set()).add(m["channel"])
            messages_per_term.setdefault(term, set()).add(msg_key)
            if term not in first_seen or m["date"] < first_seen[term]:
                first_seen[term] = m["date"]
            bucket = examples.setdefault(term, [])
            if len(bucket) < 2 and all(ex["channel"] != m["channel"] for ex in bucket):
                bucket.append(m)

    results = []
    for term, recent_count in recent_counts.items():
        if recent_count < min_recent_count:
            continue
        if len(channels_per_term.get(term, ())) < min_channels:
            continue
        baseline_count = baseline_counts.get(term, 0)

        recent_rate = recent_count / recent_hours
        baseline_rate = (baseline_count + 1) / baseline_span_hours  # +1 smoothing
        score = recent_rate / baseline_rate

        results.append({
            "term": term,
            "recent_count": recent_count,
            "channel_count": len(channels_per_term[term]),
            "baseline_count": baseline_count,
            "score": score,
            # With zero baseline mentions the score is just the mention count
            # rescaled (recent_count × baseline span / recent span), not a
            # meaningful multiplier — show these as "new" instead.
            "is_new": baseline_count == 0,
            # Earliest post in the recent window carrying the term — for a new
            # term, when it first appeared in the scraped channels.
            "first_seen": first_seen[term],
            "examples": examples.get(term, []),
            "_messages": messages_per_term[term],
        })

    # New terms have no ratio to rank by (their score is just the mention
    # count rescaled), so they go first, ordered by how many channels
    # carry them; terms with a baseline follow, ordered by spike ratio.
    results.sort(key=lambda r: (
        r["is_new"],
        r["channel_count"] if r["is_new"] else r["score"],
        r["recent_count"],
    ), reverse=True)

    selected = []
    for r in results:
        overlaps_existing = any(
            len(r["_messages"] & kept["_messages"]) / min(len(r["_messages"]), len(kept["_messages"])) > 0.6
            for kept in selected
        )
        if not overlaps_existing:
            selected.append(r)
        if len(selected) >= top_n:
            break

    for r in selected:
        r["message_keys"] = r.pop("_messages")
    return selected


def format_ago(iso_date: str, now: datetime | None = None) -> str:
    """'14h ago' / '45m ago' for a post date."""
    now = now or datetime.now(timezone.utc)
    minutes = max(int((now - datetime.fromisoformat(iso_date)).total_seconds() // 60), 0)
    return f"{minutes}m ago" if minutes < 60 else f"{round(minutes / 60)}h ago"


def print_trending(
    recent_hours: int = 24,
    baseline_hours: int = 168,
    top_n: int = 20,
    min_recent_count: int = 3,
    min_channels: int = 5,
    as_of: datetime | None = None,
):
    results = get_trending_terms(
        recent_hours=recent_hours, baseline_hours=baseline_hours,
        top_n=top_n, min_recent_count=min_recent_count, min_channels=min_channels,
        as_of=as_of,
    )

    print(f"\n=== Trending terms — last {recent_hours}h vs {baseline_hours}h baseline ===\n")

    warning = diagnose_baseline(recent_hours, baseline_hours, as_of=as_of)
    if warning:
        print(f"⚠️  {warning}\n")

    if not results:
        print(f"Nothing met the threshold (min {min_recent_count} mentions on {min_channels}+ channels).")
        print("Try lowering --min-channels if your channel list is small.")
        return

    for i, r in enumerate(results, 1):
        spike = f"first seen {format_ago(r['first_seen'], as_of)}" if r["is_new"] else f"{r['score']:.1f}x baseline"
        print(f"{i:2}. \"{r['term']}\"  —  {spike}  (recent={r['recent_count']} on {r['channel_count']} channels, baseline={r['baseline_count']})")
        for ex in r["examples"]:
            snippet = (ex["text"] or "").replace("\n", " ")[:120]
            print(f"      @{ex['channel']}: {snippet}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find trending terms across monitored channels")
    parser.add_argument("--recent-hours", type=int, default=24)
    parser.add_argument("--baseline-hours", type=int, default=168)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--min-count", type=int, default=3, help="Minimum mentions in the recent window to qualify")
    parser.add_argument("--min-channels", type=int, default=5, help="Minimum distinct channels a term must appear on")
    args = parser.parse_args()

    print_trending(
        recent_hours=args.recent_hours, baseline_hours=args.baseline_hours,
        top_n=args.top, min_recent_count=args.min_count,
        min_channels=args.min_channels,
    )
