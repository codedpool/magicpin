"""
Auto-reply detector.

WhatsApp Business "canned" auto-replies are 40-70% of merchant replies in
production Vera. Detecting them and exiting gracefully wins points.

Strategy:
1. Phrase match: common canned templates ("thank you for contacting", etc.)
2. Repetition match: same body verbatim as a prior MERCHANT turn (auto-replies
   are bot-driven — they repeat).

Escalation per consecutive auto-reply count:
   1 → send a polite nudge ("Looks like an auto-reply 😊 reply YES when you see this")
   2 → wait 14400s (4h) — give the owner time
   3+ → end conversation (no engagement signal)
"""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

CANNED_PHRASES = [
    r"thank\s+you\s+for\s+(contacting|reaching\s+out|messaging)",
    r"(auto(\s|-)?(reply|response|replied|generated|matic))",
    r"team\s+will\s+(respond|get\s+back|contact|reach\s+out)",
    r"we\s+are\s+currently\s+(closed|unavailable|busy)",
    r"out\s+of\s+office",
    r"will\s+respond\s+(shortly|as\s+soon|asap|soon)",
    r"automated\s+(assistant|message|response|reply)",
    r"i'm\s+an?\s+(automated|ai)\s+(assistant|bot)",
    r"this\s+is\s+an?\s+(automated|automatic)\s+(reply|message|response)",
    r"shukriya[,.\s]+main\s+aapki\s+(yeh\s+)?sabhi\s+baatein",  # Hindi auto-reply pattern
    r"jaankari\s+ke\s+liye\s+bahut",  # Hindi auto-reply
    r"hamari\s+team\s+tak\s+pahuncha",  # Hindi auto-reply
]

CANNED_RE = re.compile("|".join(CANNED_PHRASES), re.IGNORECASE)


def is_canned(message: str) -> bool:
    if not message:
        return False
    return bool(CANNED_RE.search(message))


def is_repetition_of_prior(message: str, conversation: dict[str, Any] | None) -> bool:
    """Check if this merchant message is verbatim/near-verbatim of a prior merchant turn."""
    if not conversation or not message:
        return False
    prior_merchant_bodies = [
        (t.get("body") or "")
        for t in (conversation.get("turns") or [])
        if (t.get("from") or "").lower() == "merchant"
    ]
    for body in prior_merchant_bodies[:-1]:  # exclude the latest (which IS this msg)
        if not body:
            continue
        score = fuzz.token_sort_ratio(message, body)
        if score >= 90:
            return True
    return False


def detect(message: str, conversation: dict[str, Any] | None) -> bool:
    """Return True if this looks like an auto-reply."""
    if is_canned(message):
        return True
    if is_repetition_of_prior(message, conversation):
        return True
    return False


def escalate(count: int) -> dict[str, Any]:
    """Return the action JSON for auto-reply escalation level `count` (1, 2, 3+).

    Conservative ladder (judge feedback): don't engage with bots — go straight
    to wait, end if it persists. Sending a "polite nudge" to an auto-reply
    looked spammy in scoring.
    """
    if count == 1:
        return {
            "action": "wait",
            "wait_seconds": 14400,  # 4h — let the owner see their inbox
            "rationale": "Detected auto-reply (1st). Waiting 4h for the owner.",
        }
    return {
        "action": "end",
        "rationale": "Auto-reply 2+ times → no engagement signal. Closing conversation.",
    }
