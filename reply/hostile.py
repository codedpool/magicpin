"""
Hostile / opt-out detector.

If a merchant says "stop", "not interested", "spam", "useless", or expresses
explicit frustration, end gracefully + block the merchant for 30 days so future
ticks don't try to re-engage.
"""

from __future__ import annotations

import re

# Strong opt-out / hostility signals — high precision, no LLM verify needed
HOSTILE_PATTERNS = [
    r"\bstop\s+(messaging|sending|texting|contacting|spamming)\b",
    r"\bdon'?t\s+(message|text|send|contact)\s+me\b",
    r"\bleave\s+me\s+alone\b",
    r"\bnot\s+interested\b",
    r"\bunsubscribe\b",
    r"\bremove\s+me\b",
    r"\bbothering\s+me\b",
    r"\b(useless|garbage|spam|waste\s+of\s+time)\b",
    r"\bf(\*+|uck)\s*(off|you)\b",
    r"\bquit\s+(spamming|messaging)\b",
    r"\bplease\s+stop\b",
    r"\bblock\s+me\b",
    # Hindi/code-mix hostility
    r"\bband\s+karo\b",                 # "stop"
    r"\bmessage\s+mat\s+karo\b",        # "don't message"
    r"\bpareshaan\s+mat\s+karo\b",      # "don't bother"
    r"\bdimaag\s+mat\s+kha[oa]?o?\b",   # frustration
]

HOSTILE_RE = re.compile("|".join(HOSTILE_PATTERNS), re.IGNORECASE)


def detect(message: str) -> bool:
    if not message:
        return False
    return bool(HOSTILE_RE.search(message))


def action() -> dict:
    return {
        "action": "end",
        "rationale": (
            "Merchant explicitly opted out / hostile. Closing conversation "
            "and blocking this merchant for 30 days."
        ),
    }


def soft_apology() -> dict:
    """Acceptable alternative: one-line apology + opt-out path, then end."""
    return {
        "action": "send",
        "body": "Apologies — I won't message again. If anything changes, just reply with 'Hi' anytime. 🙏",
        "cta": "none",
        "rationale": "Soft graceful exit on hostility — single-line apology, then close.",
    }
