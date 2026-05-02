"""
Wait-request detector.

If merchant says "later", "tomorrow", "in a meeting", "busy", we back off
gracefully rather than pestering. Default wait = 1 hour; "tomorrow" = 24h.
"""

from __future__ import annotations

import re


# (regex, default wait_seconds)
WAIT_PATTERNS: list[tuple[str, int]] = [
    (r"\btomorrow\b", 86400),
    (r"\bnext\s+week\b", 604800),
    (r"\bin\s+(\d+)\s+hours?\b", 3600),  # "in 2 hours"
    (r"\bin\s+a\s+(few|couple\s+of)\s+hours?\b", 7200),
    (r"\b(later|after\s+a\s+while|after\s+sometime)\b", 7200),
    (r"\b(busy|in\s+a\s+meeting|on\s+a\s+call)\b", 3600),
    (r"\bcall\s+(you|me)\s+back\b", 3600),
    (r"\bping\s+me\s+(later|tomorrow)\b", 3600),
    # Hindi/code-mix
    (r"\bbaad\s+mein\b", 7200),               # "later"
    (r"\bkal\b", 86400),                      # "tomorrow"
    (r"\babhi\s+busy\b", 3600),               # "busy now"
    (r"\bmeeting\s+mein\b", 3600),            # "in meeting"
    (r"\bphir\s+baat\s+karenge\b", 7200),     # "we'll talk later"
]

_PAT_RE = [(re.compile(pat, re.IGNORECASE), secs) for pat, secs in WAIT_PATTERNS]


def detect(message: str) -> int | None:
    """Return wait_seconds if a wait request is detected; else None."""
    if not message:
        return None
    for pat, secs in _PAT_RE:
        m = pat.search(message)
        if m:
            # If pattern captured digits ("in 3 hours"), use them
            try:
                grp = m.group(1)
                if grp and grp.isdigit():
                    return int(grp) * 3600
            except (IndexError, ValueError):
                pass
            return secs
    return None


def action(seconds: int) -> dict:
    return {
        "action": "wait",
        "wait_seconds": seconds,
        "rationale": f"Merchant signaled busy / asked to wait. Backing off {seconds}s.",
    }
