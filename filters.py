"""
Junk filters for feed generation — ads, cross-posted subscribe/follow spam,
and other posts with no editorial value.

These patterns are STARTING EXAMPLES in English. Edit AD_PATTERNS /
PROMO_PATTERNS for your own channels and language — see the README's
"Customizing for your channels" section for how.
"""

import re

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


def is_junk(text: str) -> bool:
    return any(p.search(text) for p in AD_PATTERNS) or any(p.search(text) for p in PROMO_PATTERNS)
