"""
Audits monitored channels against the database.

Usage:
    python audit_channels.py              # summary + dead/unreachable channel lists
    python audit_channels.py --prune      # remove dead/unreachable channels from channels.csv
    python audit_channels.py --min-msgs 3 # flag channels with fewer than 3 messages
"""

import argparse
import csv

from channels import get_all_monitored, load_channels, REGISTRY_PATH
from db import get_conn


def audit(min_msgs: int = 1) -> dict:
    monitored = get_all_monitored()

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT channel, COUNT(*) as msg_count FROM messages GROUP BY channel"
        ).fetchall()
        status_rows = conn.execute("SELECT channel, found FROM channel_status").fetchall()

    counts = {row["channel"]: row["msg_count"] for row in rows}
    # A channel only ends up here once it's actually been scraped since this
    # check existed. No entry means "we don't know yet" — not evidence of a
    # problem, so it's treated the same as a channel that's still fine.
    reachable = {row["channel"]: bool(row["found"]) for row in status_rows}

    dead = []          # never produced a single message, ever
    low = []            # in our list, fewer than min_msgs total
    unreachable = []    # has history, but the most recent scrape found it gone
    active = []

    for handle in monitored:
        n = counts.get(handle, 0)
        if n == 0:
            dead.append((handle, n))
        elif n < min_msgs:
            low.append((handle, n))
        elif handle in reachable and not reachable[handle]:
            unreachable.append((handle, n))
        else:
            active.append((handle, n))

    return {
        "monitored": len(monitored),
        "dead": dead,
        "low": low,
        "unreachable": unreachable,
        "active": active,
        "counts": counts,
    }


def print_report(result: dict, min_msgs: int):
    monitored = result["monitored"]
    dead = result["dead"]
    low = result["low"]
    unreachable = result["unreachable"]
    active = result["active"]

    print(f"\n=== Channel Audit ===")
    print(f"Total monitored          : {monitored}")
    print(f"Active                   : {len(active)}")
    print(f"Low (<{min_msgs} msgs total)     : {len(low)}")
    print(f"Unreachable (gone/private) : {len(unreachable)}")
    print(f"Dead (0 msgs ever)       : {len(dead)}")
    print()

    if dead:
        print(f"--- Dead channels ({len(dead)}) — never produced a single message ---")
        print("  " + ", ".join(f"@{h}" for h, _ in dead))
        print()

    if unreachable:
        print(f"--- Unreachable channels ({len(unreachable)}) — have history, but the")
        print(f"    most recent scrape found the page gone (private, deleted, or renamed) ---")
        print("  " + ", ".join(f"@{h}" for h, _ in unreachable))
        print()

    if low and min_msgs > 1:
        print(f"--- Low-activity channels (<{min_msgs} msgs) ---")
        for handle, n in sorted(low, key=lambda x: x[1]):
            print(f"  @{handle}: {n} message(s)")
        print()


def prune(handles_to_remove: list):
    remove = {h for h, _ in handles_to_remove}
    remaining = [h for h in load_channels() if h not in remove]

    with REGISTRY_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["handle"])
        writer.writerows([[h] for h in remaining])

    print(f"Pruned {len(remove)} channels from {REGISTRY_PATH.name} ({len(remaining)} remain).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-msgs", type=int, default=1,
                        help="Flag channels with fewer than this many messages (default 1)")
    parser.add_argument("--prune", action="store_true",
                        help="Remove dead and unreachable channels from channels.csv")
    args = parser.parse_args()

    result = audit(min_msgs=args.min_msgs)
    print_report(result, min_msgs=args.min_msgs)

    to_remove = result["dead"] + result["unreachable"]

    if args.prune:
        if not to_remove:
            print("Nothing to prune.")
        else:
            confirm = input(f"Remove {len(to_remove)} dead/unreachable channels from channels.csv? [y/N] ")
            if confirm.lower() == "y":
                prune(to_remove)
            else:
                print("Aborted.")
    else:
        if to_remove:
            print("Run with --prune to remove dead/unreachable channels from channels.csv.")
