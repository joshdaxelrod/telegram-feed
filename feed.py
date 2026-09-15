"""
Generates browsable HTML feeds of scraped Telegram posts, plus matching CSVs.

Four feed types:
    popular   — globally most-viewed posts right now
    random    — a random sample, for serendipitous browsing
    spotlight — each channel's own top post(s), interleaved, so smaller
                channels surface alongside the biggest ones
    trending  — words/phrases spreading across many channels right now,
                relative to their normal baseline rate (see trends.py)

Each HTML page has a nav bar linking to the other feeds and a live search
box that filters the cards already on the page (client-side, no server
needed). For searching further back than what's rendered on a given page,
use trace.py against the full database instead.

Usage:
    python feed.py                       # last 24h, all four feeds, opens trending.html
    python feed.py --mode random --hours 48
    python feed.py --mode trending --min-channels 3
    python feed.py --keywords impfung corona --exclude satire
    python feed.py --no-open              # write files without opening a browser
"""

import argparse
import csv
import re
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from score import get_top_messages, get_random_messages, get_spotlight_messages, get_keyword_messages
from trends import get_trending_terms

DATA_DIR = Path(__file__).parent / "data"

NAV_MODES = ["trending", "popular", "random", "spotlight"]
FEED_TITLES = {
    "popular": "Popular",
    "random": "Random",
    "spotlight": "Spotlight",
    "trending": "Trending",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monitoring Feed — {title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f0f2f5;
    color: #1a1a1a;
    padding: 24px 16px;
  }}
  header {{
    max-width: 720px;
    margin: 0 auto 16px;
  }}
  header h1 {{
    font-size: 20px;
    font-weight: 700;
    color: #1a1a1a;
  }}
  header p {{
    font-size: 13px;
    color: #666;
    margin-top: 4px;
  }}
  header h1 {{ display: flex; align-items: center; gap: 8px; }}
  .help {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #e4e6ea;
    color: #666;
    font-size: 12px;
    font-weight: 700;
    cursor: help;
    position: relative;
    flex-shrink: 0;
  }}
  .help .tooltip {{
    visibility: hidden;
    opacity: 0;
    position: absolute;
    top: 130%;
    left: 0;
    background: #1a1a1a;
    color: #fff;
    font-size: 12px;
    font-weight: 400;
    line-height: 1.5;
    padding: 10px 12px;
    border-radius: 8px;
    width: 260px;
    max-width: calc(100vw - 48px);
    transition: opacity 0.15s;
    z-index: 10;
  }}
  .help .tooltip b {{ font-weight: 700; }}
  .help:hover .tooltip, .help.open .tooltip {{ visibility: visible; opacity: 1; }}
  nav {{
    max-width: 720px;
    margin: 0 auto 16px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}
  nav a {{
    font-size: 13px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 20px;
    background: #fff;
    color: #1877f2;
    text-decoration: none;
    border: 1px solid #e4e6ea;
  }}
  nav a.active {{
    background: #1877f2;
    color: #fff;
    border-color: #1877f2;
  }}
  .search-bar {{
    max-width: 720px;
    margin: 0 auto 20px;
  }}
  .search-bar input {{
    width: 100%;
    font-size: 14px;
    padding: 10px 14px;
    border-radius: 10px;
    border: 1px solid #e4e6ea;
    background: #fff;
  }}
  .search-count {{
    font-size: 12px;
    color: #999;
    margin-top: 6px;
  }}
  .feed {{
    max-width: 720px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .card, .term-card {{
    background: #fff;
    border-radius: 12px;
    padding: 16px 20px;
    border: 1px solid #e4e6ea;
  }}
  .card-header, .term-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }}
  .rank {{
    font-size: 13px;
    font-weight: 700;
    color: #999;
    min-width: 28px;
  }}
  .channel {{
    font-weight: 700;
    font-size: 15px;
    color: #050505;
    text-decoration: none;
  }}
  .channel:hover {{ text-decoration: underline; }}
  .date {{
    font-size: 12px;
    color: #999;
    margin-left: auto;
  }}
  .text {{
    font-size: 14px;
    line-height: 1.6;
    color: #1a1a1a;
    white-space: pre-wrap;
    word-break: break-word;
    margin-bottom: 12px;
  }}
  .meta {{
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: #666;
    border-top: 1px solid #f0f2f5;
    padding-top: 10px;
    flex-wrap: wrap;
  }}
  .meta span {{ display: flex; align-items: center; gap: 4px; }}
  .score {{ font-weight: 700; color: #1877f2; }}
  .amplified {{ font-weight: 700; color: #e65100; }}
  .term-name {{
    font-weight: 700;
    font-size: 15px;
    color: #050505;
  }}
  .spike-badge {{ font-weight: 700; color: #1877f2; }}
  .term-meta {{
    font-size: 12px;
    color: #999;
    margin-left: auto;
  }}
  .examples {{
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }}
  .example {{
    font-size: 13px;
    line-height: 1.5;
    color: #444;
  }}
  .view-all {{
    font-size: 12px;
    color: #1877f2;
    text-decoration: none;
    border-top: 1px solid #f0f2f5;
    padding-top: 10px;
    display: block;
  }}
  .back-link {{
    max-width: 720px;
    margin: 0 auto 12px;
  }}
  .back-link a {{ font-size: 13px; color: #1877f2; text-decoration: none; }}
  .empty {{
    max-width: 720px;
    margin: 40px auto;
    text-align: center;
    color: #999;
    font-size: 14px;
  }}
</style>
</head>
<body>
<header>
  <h1>Monitoring Feed — {title} {help}</h1>
  <p>{subtitle}</p>
</header>
<nav>{nav}</nav>
{back_link}
<div class="search-bar">
  <input type="text" id="search" placeholder="Filter...">
  <div class="search-count" id="search-count"></div>
</div>
<div class="feed" id="feed">
{cards}
</div>
<script>
  const input = document.getElementById("search");
  const cards = Array.from(document.querySelectorAll(".card, .term-card"));
  const countEl = document.getElementById("search-count");

  function applyFilter() {{
    const q = input.value.trim().toLowerCase();
    let visible = 0;
    for (const card of cards) {{
      const match = !q || card.dataset.search.includes(q);
      card.hidden = !match;
      if (match) visible++;
    }}
    countEl.textContent = q ? `${{visible}} of ${{cards.length}} match` : "";
  }}

  input.addEventListener("input", applyFilter);

  document.querySelectorAll(".help").forEach((h) => {{
    h.addEventListener("click", (e) => {{
      e.stopPropagation();
      document.querySelectorAll(".help.open").forEach((other) => {{
        if (other !== h) other.classList.remove("open");
      }});
      h.classList.toggle("open");
    }});
  }});
  document.addEventListener("click", () => {{
    document.querySelectorAll(".help.open").forEach((h) => h.classList.remove("open"));
  }});
</script>
</body>
</html>"""

CARD_TEMPLATE = """  <div class="card" data-search="{search_key}">
    <div class="card-header">
      <span class="rank">#{rank}</span>
      <a class="channel" href="https://t.me/{channel}" target="_blank">@{channel}</a>
      <span class="date">{date}</span>
    </div>
    <div class="text">{text}</div>
    <div class="meta">
      <span class="score">&#128065; {views} views</span>
      {amplified_badge}
      <a href="https://t.me/{channel}/{message_id}" target="_blank" style="margin-left:auto;font-size:12px;color:#1877f2;text-decoration:none;">view post &#8599;</a>
    </div>
  </div>"""

TERM_CARD_TEMPLATE = """  <div class="term-card" data-search="{search_key}">
    <div class="term-header">
      <span class="rank">#{rank}</span>
      <span class="term-name">&#8220;{term}&#8221;</span>
      <span class="spike-badge">&#9650; {score}x vs {baseline_label} baseline</span>
      <span class="term-meta">{channel_count} channels &middot; {recent_count} mentions</span>
    </div>
    <div class="examples">
{examples}
    </div>
    <a class="view-all" href="{detail_href}">view all matching posts &#8594;</a>
  </div>"""

EXAMPLE_TEMPLATE = '      <div class="example"><b>@{channel}</b> {text}</div>'


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _slugify(term: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")
    return slug or f"term_{abs(hash(term)) % 10000}"


NAV_DESCRIPTIONS = {
    "trending": "Terms spreading across many channels right now, relative to their normal rate.",
    "popular": "Most-viewed posts right now, deduplicated across channels.",
    "random": "A random sample, for browsing outside what's already popular.",
    "spotlight": "Each channel's own best post, so small channels aren't buried by big ones.",
}


def _build_nav(active: str) -> str:
    links = []
    for m in NAV_MODES:
        cls = ' class="active"' if m == active else ""
        links.append(f'<a href="{m}.html"{cls}>{FEED_TITLES[m]}</a>')
    return "".join(links)


def _format_period(hours: int) -> str:
    if hours % 24 == 0:
        days = hours // 24
        return "1-day" if days == 1 else f"{days}-day"
    return f"{hours}h"


def _help_html(active: str, baseline_hours: int | None = None) -> str:
    tooltip = NAV_DESCRIPTIONS[active]
    if active == "trending":
        tooltip += (
            " It only counts if the term appears on several different channels — "
            "one post copied to a couple of channels doesn't count as a real trend."
        )
    return f'<span class="help" tabindex="0">?<span class="tooltip">{tooltip}</span></span>'


def _render_cards(
    messages: list[dict], title: str, subtitle: str, nav_active: str, back_link: str = "",
    baseline_hours: int | None = None,
) -> str:
    cards = []
    for i, msg in enumerate(messages, 1):
        date = msg["date"][:16].replace("T", " ") + " UTC"
        text = _escape((msg["text"] or "").strip())
        channel_count = msg.get("channel_count", 1)
        amplified_badge = (
            f'<span class="amplified">&#128225; {channel_count} channels</span>'
            if channel_count > 1 else ""
        )
        search_key = _escape(f"{msg['channel']} {msg['text'] or ''}".lower())
        cards.append(CARD_TEMPLATE.format(
            rank=i,
            channel=_escape(msg["channel"]),
            date=date,
            text=text,
            views=msg["views"],
            message_id=msg["message_id"],
            amplified_badge=amplified_badge,
            search_key=search_key,
        ))

    body = "\n".join(cards) if cards else ""
    html = HTML_TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        nav=_build_nav(nav_active),
        back_link=back_link,
        cards=body,
        help=_help_html(nav_active, baseline_hours=baseline_hours),
    )
    if not cards:
        html = html.replace(
            '<div class="feed" id="feed">\n\n</div>',
            '<div class="feed" id="feed"></div><p class="empty">No posts found for this window.</p>',
        )
    return html


def _render_terms(terms: list[dict], subtitle: str, baseline_hours: int | None = None) -> str:
    baseline_label = _format_period(baseline_hours or 168)
    rows = []
    for i, t in enumerate(terms, 1):
        examples = "\n".join(
            EXAMPLE_TEMPLATE.format(
                channel=_escape(ex["channel"]),
                text=_escape((ex["text"] or "").replace("\n", " ").strip()[:160]),
            )
            for ex in t["examples"]
        )
        search_key = _escape(t["term"].lower())
        rows.append(TERM_CARD_TEMPLATE.format(
            rank=i,
            term=_escape(t["term"]),
            score=f"{t['score']:.1f}",
            baseline_label=baseline_label,
            channel_count=t["channel_count"],
            recent_count=t["recent_count"],
            examples=examples,
            detail_href=t["detail_href"],
            search_key=search_key,
        ))

    body = "\n".join(rows) if rows else ""
    html = HTML_TEMPLATE.format(
        title="Trending",
        subtitle=subtitle,
        nav=_build_nav("trending"),
        back_link="",
        cards=body,
        help=_help_html("trending", baseline_hours=baseline_hours),
    )
    if not rows:
        html = html.replace(
            '<div class="feed" id="feed">\n\n</div>',
            '<div class="feed" id="feed"></div><p class="empty">Nothing met the trending threshold for this window. Try lowering --min-channels.</p>',
        )
    return html


def _write_csv(path: Path, messages: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "rank", "channel", "date", "text",
            "views", "virality_score", "channel_count", "url",
        ])
        writer.writeheader()
        for i, msg in enumerate(messages, 1):
            writer.writerow({
                "rank": i,
                "channel": msg["channel"],
                "date": msg["date"][:16].replace("T", " ") + " UTC",
                "text": (msg["text"] or "").strip(),
                "views": msg["views"],
                "virality_score": round(msg["virality_score"], 1),
                "channel_count": msg.get("channel_count", 1),
                "url": f"https://t.me/{msg['channel']}/{msg['message_id']}",
            })


def build_feed(
    mode: str,
    hours: int = 24,
    limit: int = 100,
    per_channel: int = 1,
    keywords: list[str] | None = None,
    exclude: list[str] | None = None,
    seed: int | None = None,
) -> Path:
    label = None
    if keywords:
        messages = get_keyword_messages(keywords=keywords, exclude=exclude, hours=hours, limit=limit)
        label = ", ".join(keywords)
    elif mode == "random":
        messages = get_random_messages(hours=hours, limit=limit, seed=seed)
    elif mode == "spotlight":
        messages = get_spotlight_messages(hours=hours, per_channel=per_channel, limit=limit, seed=seed)
    else:
        messages = get_top_messages(hours=hours, limit=limit)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subtitle = f"{len(messages)} posts &middot; last {hours}h"
    if label:
        subtitle += f" &middot; {label}"
    subtitle += f" &middot; generated {generated}"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    html_path = DATA_DIR / f"{mode}.html"
    csv_path = DATA_DIR / f"{mode}.csv"

    html = _render_cards(messages, title=FEED_TITLES[mode], subtitle=subtitle, nav_active=mode)
    html_path.write_text(html, encoding="utf-8")
    _write_csv(csv_path, messages)

    return html_path


def build_trending_feed(
    hours: int = 24,
    baseline_hours: int = 168,
    top_n: int = 20,
    min_recent_count: int = 3,
    min_channels: int = 5,
    detail_limit: int = 50,
) -> Path:
    terms = get_trending_terms(
        recent_hours=hours, baseline_hours=baseline_hours,
        top_n=top_n, min_recent_count=min_recent_count, min_channels=min_channels,
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    back_link = '<div class="back-link"><a href="trending.html">&#8592; back to trending</a></div>'

    # Clear last run's term detail pages so terms no longer trending don't
    # linger as orphaned files.
    for stale in DATA_DIR.glob("trending_*.html"):
        stale.unlink()
    for stale in DATA_DIR.glob("trending_*.csv"):
        stale.unlink()

    for t in terms:
        slug = _slugify(t["term"])
        detail_path = DATA_DIR / f"trending_{slug}.html"
        detail_messages = get_keyword_messages(keywords=[t["term"]], hours=hours, limit=detail_limit)
        detail_subtitle = (
            f"{len(detail_messages)} posts matching &#8220;{_escape(t['term'])}&#8221; "
            f"&middot; last {hours}h &middot; generated {generated}"
        )
        detail_html = _render_cards(
            detail_messages, title=f"“{t['term']}”", subtitle=detail_subtitle,
            nav_active="trending", back_link=back_link, baseline_hours=baseline_hours,
        )
        detail_path.write_text(detail_html, encoding="utf-8")
        _write_csv(DATA_DIR / f"trending_{slug}.csv", detail_messages)
        t["detail_href"] = detail_path.name

    subtitle = f"{len(terms)} trending terms &middot; last {hours}h vs {baseline_hours}h baseline &middot; generated {generated}"
    index_path = DATA_DIR / "trending.html"
    index_path.write_text(_render_terms(terms, subtitle=subtitle, baseline_hours=baseline_hours), encoding="utf-8")

    with (DATA_DIR / "trending.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "term", "score", "recent_count", "channel_count", "baseline_count"])
        writer.writeheader()
        for i, t in enumerate(terms, 1):
            writer.writerow({
                "rank": i, "term": t["term"], "score": round(t["score"], 1),
                "recent_count": t["recent_count"], "channel_count": t["channel_count"],
                "baseline_count": t["baseline_count"],
            })

    return index_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate browsable HTML feeds of scraped posts")
    parser.add_argument("--mode", choices=["popular", "random", "spotlight", "trending", "all"], default="all")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--per-channel", type=int, default=1, help="Posts per channel in the spotlight feed")
    parser.add_argument("--seed", type=int, help="Random seed, for a reproducible random/spotlight feed")
    parser.add_argument("--keywords", nargs="+", help="Filter by keywords (OR logic, any match included)")
    parser.add_argument("--exclude", nargs="+", help="Exclude posts containing these terms")
    parser.add_argument("--baseline-hours", type=int, default=168, help="Trending: baseline window to compare against")
    parser.add_argument("--min-channels", type=int, default=5, help="Trending: minimum distinct channels a term must appear on")
    parser.add_argument("--min-count", type=int, default=3, help="Trending: minimum mentions in the recent window")
    parser.add_argument("--no-open", action="store_true", help="Write files without opening a browser")
    args = parser.parse_args()

    modes = NAV_MODES if args.mode == "all" else [args.mode]

    first_path = None
    for mode in modes:
        if mode == "trending":
            path = build_trending_feed(
                hours=args.hours, baseline_hours=args.baseline_hours,
                min_recent_count=args.min_count, min_channels=args.min_channels,
            )
        else:
            path = build_feed(
                mode, hours=args.hours, limit=args.limit,
                per_channel=args.per_channel, keywords=args.keywords,
                exclude=args.exclude, seed=args.seed,
            )
        first_path = first_path or path
        print(f"{mode}: {path}")

    if not args.no_open:
        webbrowser.open(first_path.as_uri())
