"""
Traces a claim or message across the monitored channel network.

Given a search term, finds all matching messages in the database sorted
chronologically — showing which channels picked it up, when, and in what order.
Results are written to data/trace_<term>.html (same look as the feed pages)
and opened in your browser.

Usage:
    python trace.py "election fraud"
    python trace.py "mask mandate" --hours 168
    python trace.py "bird flu" --hours 72
    python trace.py "bird flu" --no-open     # write the page without opening it
"""

import argparse
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import get_conn
from feed import DATA_DIR, HTML_TEMPLATE, _build_nav, _escape, _slugify

TRACE_CARD_TEMPLATE = """  <div class="card" data-search="{search_key}">
    <div class="card-header">
      <span class="rank" style="min-width:56px">{offset}</span>
      <a class="channel" href="https://t.me/{channel}" target="_blank">@{channel}</a>
      <span class="date">{date}</span>
    </div>
    <div class="text">{text}</div>
    <div class="meta">
      <span class="score">&#128065; {views} views</span>
      <a href="https://t.me/{channel}/{message_id}" target="_blank" style="margin-left:auto;font-size:12px;color:#1877f2;text-decoration:none;">view post &#8599;</a>
    </div>
  </div>"""


def trace(query: str, hours: int = 168) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    terms = query.split()
    like_clauses = " AND ".join(f"text LIKE :term{i}" for i in range(len(terms)))
    params = {"since": since}
    for i, term in enumerate(terms):
        params[f"term{i}"] = f"%{term}%"

    sql = f"""
        SELECT channel, message_id, date, text, views
        FROM messages
        WHERE date >= :since
          AND text != ''
          AND {like_clauses}
        ORDER BY date ASC
    """

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]


def _offset_label(msg_date: datetime, first_date: datetime) -> str:
    hours_after = (msg_date - first_date).total_seconds() / 3600
    return f"+{hours_after:.1f}h" if hours_after > 0 else "first"


def write_trace_html(query: str, results: list[dict], hours: int) -> Path:
    first_date = datetime.fromisoformat(results[0]["date"])
    cards = []
    for r in results:
        cards.append(TRACE_CARD_TEMPLATE.format(
            offset=_offset_label(datetime.fromisoformat(r["date"]), first_date),
            channel=_escape(r["channel"]),
            date=r["date"][:16].replace("T", " ") + " UTC",
            text=_escape((r["text"] or "").strip()),
            views=r["views"],
            message_id=r["message_id"],
            search_key=_escape(f"{r['channel']} {r['text'] or ''}".lower()),
        ))

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = HTML_TEMPLATE.format(
        title=f"Trace: &#8220;{_escape(query)}&#8221;",
        subtitle=(
            f"{len(results)} matches, oldest first &middot; last {hours}h "
            f"&middot; generated {generated}"
        ),
        nav=_build_nav(""),
        back_link="",
        notice="",
        cards="\n".join(cards),
        help="",
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"trace_{_slugify(query)}.html"
    path.write_text(html, encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trace a claim across the channel network")
    parser.add_argument("query", help="Search terms (space-separated, all must match)")
    parser.add_argument("--hours", type=int, default=168)
    parser.add_argument("--no-open", action="store_true", help="Write the HTML page without opening a browser")
    args = parser.parse_args()

    results = trace(args.query, hours=args.hours)
    if not results:
        print(f"\nNo messages found matching '{args.query}' in the last {args.hours}h.")
    else:
        path = write_trace_html(args.query, results, hours=args.hours)
        print(f"{len(results)} matches for '{args.query}' → {path}")
        if not args.no_open:
            webbrowser.open(path.as_uri())
