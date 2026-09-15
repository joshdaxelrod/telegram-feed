"""
Junk filters for feed generation — ads, cross-posted subscribe/follow spam,
and other posts with no editorial value.

These patterns are STARTING EXAMPLES in English. Edit AD_PATTERNS /
PROMO_PATTERNS for your own channels and language, or add a personal,
git-ignored filters.local.txt (one phrase per line, matched literally,
case-insensitive) instead — see the README's "Customizing for your
channels" section for how.
"""

import re
from pathlib import Path

LOCAL_FILTERS_PATH = Path(__file__).parent / "filters.local.txt"

AD_PATTERNS = [
    re.compile(r"\b(order now|buy now|shop now|buy today)\b", re.IGNORECASE),
    re.compile(r"\$\s*\d+(\.\d+)?\s*(instead of|was)\b", re.IGNORECASE),
    re.compile(r"\bfree shipping\b", re.IGNORECASE),
    re.compile(r"\buse code\b.{0,20}\bfor \d+% off\b", re.IGNORECASE),
]

PROMO_PATTERNS = [
    re.compile(r"\bsubscribe now\b", re.IGNORECASE),
    re.compile(r"\bfollow (this|our) channel\b", re.IGNORECASE),
    re.compile(r"\b(backup|reserve|alternate) channel\b", re.IGNORECASE),
    re.compile(r"find more on the @\w+ channel", re.IGNORECASE),
    re.compile(r"\bfollow us (also |too )?on\b", re.IGNORECASE),
    re.compile(r"\bour (new |backup |reserve )?channel\b", re.IGNORECASE),
]


def _load_local_patterns() -> list[re.Pattern]:
    if not LOCAL_FILTERS_PATH.exists():
        return []
    patterns = []
    for line in LOCAL_FILTERS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(re.compile(re.escape(line), re.IGNORECASE))
    return patterns


_LOCAL_PATTERNS = _load_local_patterns()


def is_junk(text: str) -> bool:
    if any(p.search(text) for p in AD_PATTERNS) or any(p.search(text) for p in PROMO_PATTERNS):
        return True
    return any(p.search(text) for p in _LOCAL_PATTERNS)
