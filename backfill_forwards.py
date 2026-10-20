"""
One-time repair for the forward-detection bug fixed in scraper.py.

scraper.py skips any post it's already saved (so a normal re-scrape
doesn't fix old rows' stale is_forward/forwarded_from values). This
re-fetches each channel's current pages and overwrites those two columns
on existing rows too — same page-fetching logic as scraper.py, limited to
the same recent history Telegram's public preview pages show.

Usage:
    python3 backfill_forwards.py              # last 24h, all channels
    python3 backfill_forwards.py --hours 168   # last 7 days
    python3 backfill_forwards.py --limit 10    # test with 10 channels
"""

import argparse
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from time import sleep

import requests
from bs4 import BeautifulSoup

from channels import get_all_monitored
from db import get_conn, init_db
from scraper import HEADERS, MAX_PAGES_PER_CHANNEL, WORKERS, _forwarded_from, _parse_count, _media_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def backfill_channel(handle: str, since, conn) -> int:
    url = f"https://t.me/s/{handle}"
    fixed = 0

    for page_num in range(MAX_PAGES_PER_CHANNEL):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as e:
            log.error(f"  {handle}: request error — {e}")
            break
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        messages = soup.select(".tgme_widget_message")
        if not messages:
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

            forwarded_from = _forwarded_from(msg)
            is_forward = 1 if forwarded_from is not None or msg.select_one(".tgme_widget_message_forwarded_from") else 0

            cur = conn.execute(
                "UPDATE messages SET is_forward = ?, forwarded_from = ? "
                "WHERE channel = ? AND message_id = ?",
                (is_forward, forwarded_from, handle, message_id),
            )
            fixed += cur.rowcount

        conn.commit()

        if all_old or oldest_id is None:
            break

        url = f"https://t.me/s/{handle}?before={oldest_id}"
        sleep(0.5)

    return fixed


def _worker(args):
    handle, since = args
    conn = get_conn()
    try:
        fixed = backfill_channel(handle, since, conn)
    finally:
        conn.close()
    return handle, fixed


def run(limit=None, hours=24):
    init_db()
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    channels = get_all_monitored()
    if limit:
        channels = channels[:limit]

    log.info(f"Backfilling forward data for {len(channels)} channels (last {hours}h, {WORKERS} workers)")

    total_fixed = 0
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(_worker, (h, since)): h for h in channels}
        for future in as_completed(futures):
            done += 1
            handle = futures[future]
            try:
                _, fixed = future.result()
                total_fixed += fixed
            except Exception as e:
                log.error(f"  {handle}: unhandled error — {e}")
            if done % 50 == 0 or done == len(channels):
                log.info(f"Progress: {done}/{len(channels)} channels done")

    log.info(f"Done. {total_fixed} rows updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    run(limit=args.limit, hours=args.hours)
