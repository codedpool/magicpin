"""
Intent-transition detector.

Production Vera's #2 documented bug: when a merchant says "yes I want to join"
or "let's do it", the bot keeps qualifying instead of switching to action.
We detect commitment markers and route to an action-mode follow-up so the bot
delivers the next concrete step, not another qualifying question.
"""

from __future__ import annotations

import re


# High-confidence commitment markers (regex, case-insensitive)
COMMITMENT_PATTERNS = [
    # English
    r"\b(yes|yep|yeah|yup)\b\s*[!.,]?\s*(please|do|go)?",
    r"\b(ok|okay)\b\s*[!.,]?\s*(do|go|sounds|let'?s)",
    r"\blet'?s\s+(do|go|start|try|begin)\s+(it|this|that)?",
    r"\bgo\s+ahead\b",
    r"\b(do|please\s+do)\s+it\b",
    r"\bcarry\s+on\b",
    r"\bproceed\b",
    r"\bconfirm(ed)?\b",
    r"\bsounds\s+(good|great|fine|right)\b",
    r"\bplease\s+(send|share|do|draft|prepare|create)\b",
    r"\bsend\s+(me|the|it|abstract|details|info)\b",
    r"\bi\s*(?:'|’)m?\s+in\b",
    # Hindi/code-mix
    r"\bhaan(ji)?\b",                                  # "yes"
    r"\bkar\s+(do|dijiye|denge)\b",                    # "do it"
    r"\bbhej\s+(do|dijiye|denge)\b",                   # "send it"
    r"\bchaliye\b",                                    # "let's go"
    r"\bteek\s+hai\b|\btheek\s+hai\b|\bsahi\s+hai\b",  # "ok"
    r"\bhojaye(ga)?\b",                                # "let it happen"
    r"\bjudna\s+hai\b|\bjudrna\s+hai\b",               # "want to join" — Pattern D in brief
]

COMMITMENT_RE = re.compile("|".join(COMMITMENT_PATTERNS), re.IGNORECASE)


def detect(message: str) -> bool:
    if not message:
        return False
    # Filter out cases where commitment marker is inside a question
    # ("is it ok if I ask...?") — quick heuristic.
    stripped = message.strip()
    if stripped.endswith("?") and len(stripped) < 80:
        return False
    return bool(COMMITMENT_RE.search(message))
