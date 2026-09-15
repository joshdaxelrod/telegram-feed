"""
Scrapes the last 24 hours of messages from monitored Telegram channels
via the public web interface (t.me/s/channel). No API credentials needed.

Usage:
    python scraper.py              # scrape all channels
    python scraper.py --tier core  # scrape only channels tagged "core"
    python scraper.py --limit 10   # test with 10 channels
"""

import logging
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Optional

import requests
from bs4 import BeautifulSoup

from channels import get_all_monitored
from db import get_conn, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

LOOKBACK_HOURS = 24  # default; overridden by --hours CLI arg
WORKERS = 10
MAX_PAGES_PER_CHANNEL = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _parse_count(text: str) -> int:
    if not text:
        return 0
    text = text.strip().replace(" ", "").replace(",", "")
    try:
        if text.endswith("K"):
            return int(float(text[:-1]) * 1_000)
        if text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        return int(text)
    except (ValueError, TypeError):
        return 0


def _media_type(msg) -> Optional[str]:
    if msg.select_one(".tgme_widget_message_photo"):
        return "photo"
    if msg.select_one(".tgme_widget_message_video_player"):
        return "video"
    if msg.select_one(".tgme_widget_message_document"):
        return "document"
    return None


def scrape_channel(handle: str, tier: str, since: datetime, conn: sqlite3.Connection):
    scraped_at = datetime.now(timezone.utc).isoformat()
    count = 0
    url = f"https://t.me/s/{handle}"

    for _ in range(MAX_PAGES_PER_CHANNEL):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as e:
            log.error(f"  {handle}: request error — {e}")
            break

        if resp.status_code != 200:
            log.warning(f"  {handle}: HTTP {resp.status_code} — skipping")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        messages = soup.select(".tgme_widget_message")

        if not messages:
            log.warning(f"  {handle}: no messages (private or empty)")
            break

        oldest_id = None
        all_old = True

        for msg in messages:
            data_post = msg.get("data-post", "")
            id_match = re.search(r"/(\d+)$", data_post)
            if not id_match:
                continue
            message_id = int(id_match.group(1))
            if oldest_id is None or message_id < oldest_id:
                oldest_id = message_id

            time_el = msg.select_one("time[datetime]")
            if not time_el:
                continue
            try:
                msg_date = datetime.fromisoformat(time_el["datetime"])
                if msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                continue

            if msg_date >= since:
                all_old = False
            if msg_date < since:
                continue

            text_el = msg.select_one(".tgme_widget_message_text")
            text = text_el.get_text(separator="\n").strip() if text_el else ""

            views_el = msg.select_one(".tgme_widget_message_views")
            views = _parse_count(views_el.get_text() if views_el else "")

            is_forward = 1 if msg.select_one(".tgme_widget_message_forwarded") else 0

            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO messages
                        (channel, tier, message_id, date, text, views,
                         is_forward, media_type, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        handle, tier, message_id, msg_date.isoformat(),
                        text, views, is_forward,
                        _media_type(msg), scraped_at,
                    ),
                )
                count += 1
            except sqlite3.IntegrityError:
                pass

        conn.commit()

        if all_old or oldest_id is None:
            break

        url = f"https://t.me/s/{handle}?before={oldest_id}"
        sleep(0.5)

    log.info(f"  {handle}: {count} new messages")


def _worker(args):
    handle, tier, since = args
    conn = get_conn()
    try:
        scrape_channel(handle, tier, since, conn)
    finally:
        conn.close()
    return handle


def run(tier_filter=None, limit=None, hours=LOOKBACK_HOURS):
    init_db()
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    channels = get_all_monitored()
    if tier_filter:
        channels = [(h, t) for h, t in channels if t == tier_filter]
    if limit:
        channels = channels[:limit]

    log.info(f"Scraping {len(channels)} channels via web (last {hours}h, {WORKERS} workers)")

    tasks = [(handle, tier, since) for handle, tier in channels]
    total = len(tasks)
    done = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(_worker, t): t[0] for t in tasks}
        for future in as_completed(futures):
            done += 1
            handle = futures[future]
            try:
                future.result()
            except Exception as e:
                log.error(f"  {handle}: unhandled error — {e}")
            if done % 50 == 0 or done == total:
                log.info(f"Progress: {done}/{total} channels done")

    log.info("Done.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=LOOKBACK_HOURS)
    parser.add_argument("--tier", help="Only scrape channels with this tier label from channels.csv")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    run(tier_filter=args.tier, limit=args.limit, hours=args.hours)
