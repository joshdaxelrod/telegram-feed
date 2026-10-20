"""
Applies a corroboration threshold to data/snowball_candidates.csv (the
output of snowball_channels.py): candidates forwarded from by enough of
your channels get added to channels.csv automatically, and the rest are
shown one at a time so you can decide by hand.

Optionally takes a plain-text file of handles to always skip (one per
line, '#' comments allowed) — e.g. for channels you know don't fit your
beat regardless of how corroborated they are.

Usage:
    python3 review_candidates.py                        # threshold 5, review the rest
    python3 review_candidates.py --threshold 3
    python3 review_candidates.py --exclude-file exclude.local.txt
    python3 review_candidates.py --no-interactive        # only auto-add, skip the review
"""

import argparse
import csv
from pathlib import Path

CANDIDATES_PATH = Path(__file__).parent / "data" / "snowball_candidates.csv"
CHANNELS_PATH = Path(__file__).parent / "channels.csv"


def _load_exclude(path: str | None) -> set[str]:
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


def run(threshold: int, exclude_file: str | None, interactive: bool):
    if not CANDIDATES_PATH.exists():
        print(f"No {CANDIDATES_PATH} found — run snowball_channels.py first.")
        return

    excluded = _load_exclude(exclude_file)
    known = _existing_handles()

    with CANDIDATES_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    added, skipped_excluded, to_review = [], [], []
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
            to_review.append(r)

    print(f"Added {len(added)} channels at >= {threshold} sources: {', '.join(added) or '(none)'}")
    if skipped_excluded:
        print(f"Skipped {len(skipped_excluded)} excluded handles: {', '.join(skipped_excluded)}")

    if not to_review:
        return
    if not interactive:
        print(f"{len(to_review)} more below the threshold — rerun without --no-interactive to review them.")
        return

    print(f"\n{len(to_review)} below the threshold — reviewing one at a time "
          f"(Enter or n = skip, y = add, q = stop reviewing):")
    for r in to_review:
        handle = r["handle"]
        prompt = (
            f"  {handle}  ({r['your_channels_forwarding_from_it']} sources, "
            f"{r['times_forwarded']} forwards, via {r['forwarded_by']}) > "
        )
        choice = input(prompt).strip().lower()
        if choice == "q":
            break
        if choice == "y":
            _append_channel(handle)
            print(f"    added {handle}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review and add snowball candidates to channels.csv")
    parser.add_argument("--threshold", type=int, default=5, help="Auto-add at this many sources or more (default 5)")
    parser.add_argument("--exclude-file", help="Plain-text file of handles to always skip, one per line")
    parser.add_argument("--no-interactive", action="store_true", help="Only auto-add; skip the one-by-one review")
    args = parser.parse_args()
    run(args.threshold, args.exclude_file, interactive=not args.no_interactive)
