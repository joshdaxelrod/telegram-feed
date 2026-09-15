"""
Loads your channel list and exposes it for scraping.

The channel list is a CSV you provide (default: channels.csv, gitignored
since it's your own research target list — see channels.example.csv for
the format). Each row is a Telegram handle, plus an optional "tier" label
you define yourself (e.g. "core", "watch") if you want to group channels
for --tier filtering later. Leave the tier column out entirely, or leave
individual cells blank, if you don't need that yet — a channel with no
tier just won't match any --tier filter.
"""

import csv
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent / "channels.csv"


def load_channels(path: Path | None = None) -> list[tuple[str, str]]:
    """Returns (handle, tier) pairs from the channel list CSV."""
    path = path or REGISTRY_PATH
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            (row["handle"].strip(), (row.get("tier") or "").strip())
            for row in reader
            if row.get("handle", "").strip()
        ]


def get_all_monitored(channels: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    """Returns (handle, tier) for all channels you monitor."""
    return channels if channels is not None else load_channels()


def get_tiers(channels: list[tuple[str, str]] | None = None) -> list[str]:
    """Distinct tier labels present in the channel list, sorted."""
    monitored = get_all_monitored(channels)
    return sorted({tier for _, tier in monitored})


if __name__ == "__main__":
    monitored = get_all_monitored()
    print(f"Total channels: {len(monitored)}")
    for tier in get_tiers(monitored):
        n = sum(1 for _, t in monitored if t == tier)
        print(f"  {tier}: {n}")
