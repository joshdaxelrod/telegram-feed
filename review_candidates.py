"""
Applies a corroboration threshold to data/snowball_candidates.csv (the
output of snowball_channels.py): candidates forwarded from by enough of
your channels get added to channels.csv automatically. Everything below
the threshold is left in snowball_candidates.csv for you to review
yourself in a spreadsheet, rather than one at a time here.

If a file called exclude.local.txt exists in this folder, handles listed
in it (one per line, '#' comments allowed) are always skipped, regardless
of how corroborated they are — e.g. for channels you know don't fit your
beat. Create it yourself if you want this; works the same way as
filters.local.txt and stopwords.local.txt elsewhere in this tool.

Usage:
    python3 review_candidates.py                     # threshold 5
    python3 review_candidates.py --threshold 3
    python3 review_candidates.py --exclude-file some_other_file.txt
"""

import argparse
import csv
from pathlib import Path

CANDIDATES_PATH = Path(__file__).parent / "data" / "snowball_candidates.csv"
CHANNELS_PATH = Path(__file__).parent / "channels.csv"
DEFAULT_EXCLUDE_PATH = Path(__file__).parent / "exclude.local.txt"


def _load_exclude(path) -> set[str]:
    if not path or not Path(path).exists():
        return set()
    return {
        line.strip().lower()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def _existing_handles() -> set[str]:
    with CHANNELS_PATH.open(encoding="utf-8", newline="") as f:
        return {
            row["handle"].strip().lower()
            for row in csv.DictReader(f)
            if row.get("handle", "").strip()
        }


def _append_channel(handle: str):
    # Match whatever line ending the file already uses (likely CRLF, if it's
    # ever been saved from Excel/Numbers), so appended rows don't mix endings.
    existing = CHANNELS_PATH.read_bytes()
    eol = "\r\n" if b"\r\n" in existing else "\n"
    with CHANNELS_PATH.open("a", encoding="utf-8", newline="") as f:
        f.write(f"{handle}{eol}")


def run(threshold: int, exclude_file: str | None):
    if not CANDIDATES_PATH.exists():
        print(f"No {CANDIDATES_PATH} found — run snowball_channels.py first.")
        return

    excluded = _load_exclude(exclude_file or DEFAULT_EXCLUDE_PATH)
    known = _existing_handles()

    with CANDIDATES_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    added, skipped_excluded, left_over = [], [], 0
    for r in rows:
        handle = r["handle"]
        if handle.lower() in known:
            continue
        if handle.lower() in excluded:
            skipped_excluded.append(handle)
            continue
        if int(r["your_channels_forwarding_from_it"]) >= threshold:
            _append_channel(handle)
            known.add(handle.lower())
            added.append(handle)
        else:
            left_over += 1

    print(f"Added {len(added)} channels at >= {threshold} sources: {', '.join(added) or '(none)'}")
    if skipped_excluded:
        print(f"Skipped {len(skipped_excluded)} excluded handles: {', '.join(skipped_excluded)}")
    if left_over:
        print(f"{left_over} more below the threshold — open {CANDIDATES_PATH} to review those yourself.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add well-corroborated snowball candidates to channels.csv")
    parser.add_argument("--threshold", type=int, default=5, help="Add at this many sources or more (default 5)")
    parser.add_argument(
        "--exclude-file",
        help=f"Handles to always skip, one per line (default: {DEFAULT_EXCLUDE_PATH.name}, if it exists)",
    )
    args = parser.parse_args()
    run(args.threshold, args.exclude_file)
