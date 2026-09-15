"""
Audits monitored channels against the database.

Usage:
    python audit_channels.py              # summary + dead channel list
    python audit_channels.py --prune      # remove dead channels from channels.csv
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

    counts = {row["channel"]: row["msg_count"] for row in rows}

    dead = []       # in our list, never scraped a message
    low = []        # in our list, fewer than min_msgs
    active = []     # in our list, at least min_msgs messages

    for handle in monitored:
        n = counts.get(handle, 0)
        if n == 0:
            dead.append((handle, n))
        elif n < min_msgs:
            low.append((handle, n))
        else:
            active.append((handle, n))

    return {
        "monitored": len(monitored),
        "dead": dead,
        "low": low,
        "active": active,
        "counts": counts,
    }


def print_report(result: dict, min_msgs: int):
    monitored = result["monitored"]
    dead = result["dead"]
    low = result["low"]
    active = result["active"]

    print(f"\n=== Channel Audit ===")
    print(f"Total monitored : {monitored}")
    print(f"Active (≥{min_msgs} msgs) : {len(active)}")
    print(f"Low (<{min_msgs} msgs)   : {len(low)}")
    print(f"Dead (0 msgs)   : {len(dead)}")
    print()

    if dead:
        print(f"--- Dead channels ({len(dead)}) — private, deleted, or wrong handle ---")
        print("  " + ", ".join(f"@{h}" for h, _ in dead))
        print()

    if low and min_msgs > 1:
        print(f"--- Low-activity channels (<{min_msgs} msgs) ---")
        for handle, n in sorted(low, key=lambda x: x[1]):
            print(f"  @{handle}: {n} message(s)")
        print()


def prune(dead: list):
    dead_handles = {h for h, _ in dead}
    remaining = [h for h in load_channels() if h not in dead_handles]

    with REGISTRY_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["handle"])
        writer.writerows([[h] for h in remaining])

    print(f"Pruned {len(dead_handles)} dead channels from {REGISTRY_PATH.name} ({len(remaining)} remain).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-msgs", type=int, default=1,
                        help="Flag channels with fewer than this many messages (default 1)")
    parser.add_argument("--prune", action="store_true",
                        help="Remove dead channels (0 messages) from channels.csv")
    args = parser.parse_args()

    result = audit(min_msgs=args.min_msgs)
    print_report(result, min_msgs=args.min_msgs)

    if args.prune:
        if not result["dead"]:
            print("Nothing to prune.")
        else:
            confirm = input(f"Remove {len(result['dead'])} dead channels from channels.csv? [y/N] ")
            if confirm.lower() == "y":
                prune(result["dead"])
            else:
                print("Aborted.")
    else:
        if result["dead"]:
            print("Run with --prune to remove dead channels from channels.csv.")
