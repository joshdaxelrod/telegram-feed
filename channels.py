"""
Loads your channel list and exposes it for scraping.

The channel list is a CSV you provide (default: channels.csv, gitignored
since it's your own research target list — see channels.example.csv for
the format): one Telegram handle per row, under a "handle" column.
"""

import csv
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent / "channels.csv"


def load_channels(path: Path | None = None) -> list[str]:
    """Returns the list of handles from the channel list CSV."""
    path = path or REGISTRY_PATH
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            row["handle"].strip()
            for row in reader
            if row.get("handle", "").strip()
        ]


def get_all_monitored(channels: list[str] | None = None) -> list[str]:
    """Returns every handle you monitor."""
    return channels if channels is not None else load_channels()


if __name__ == "__main__":
    monitored = get_all_monitored()
    print(f"Total channels: {len(monitored)}")
