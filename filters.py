"""
Junk filters for feed generation — ads, cross-posted subscribe/follow spam,
and other posts with no editorial value.

These patterns are STARTING EXAMPLES, tuned for a German-language Telegram
scene. Edit AD_PATTERNS / PROMO_PATTERNS for your own channels and language.
"""

import re

AD_PATTERNS = [
    re.compile(r"kopp-verlag\.de", re.IGNORECASE),
    re.compile(r"otpcytokenid", re.IGNORECASE),
    re.compile(r"\b(jetzt bestellen|hier bestellen|jetzt kaufen|hier kaufen)\b", re.IGNORECASE),
    re.compile(r"€\s*\d+[.,]\d+\s*(statt|anstatt|instead of|instead)", re.IGNORECASE),
    re.compile(r"(gratis versand|kostenloser versand|free shipping|versandkostenfrei).*europa", re.IGNORECASE),
]

PROMO_PATTERNS = [
    re.compile(r"\bjetzt abonnieren\b", re.IGNORECASE),
    re.compile(r"\bkanal folgen\b", re.IGNORECASE),
    re.compile(r"\b(backup|reserve|ausweich).*kanal\b", re.IGNORECASE),
    re.compile(r"find more on the @\w+ channel", re.IGNORECASE),
    re.compile(r"folgt uns (auch |mal )?(auf|bei)\b", re.IGNORECASE),
    re.compile(r"\bunser (neuer |backup |reserve )?kanal\b", re.IGNORECASE),
]


def is_junk(text: str) -> bool:
    return any(p.search(text) for p in AD_PATTERNS) or any(p.search(text) for p in PROMO_PATTERNS)
