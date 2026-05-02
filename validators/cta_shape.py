"""
CTA-shape validator — enforces a single, well-formed call-to-action that
matches the cta_shape declared by the PLAN stage.

Shapes:
- binary_yes_no    → exactly one binary prompt, ends with "?"
- multi_choice_slot → "Reply 1 ... 2 ..." pattern (acceptable for booking)
- open_ended       → ends with a question mark
- none             → no question, no "Reply" — pure information
"""

from __future__ import annotations

import re
from typing import Any


# Detect "?" outside of inline questions (rough heuristic — count question marks
# in the LAST sentence to avoid false positives on rhetorical questions earlier).
def _question_count_overall(body: str) -> int:
    return body.count("?")


def _has_question_anywhere(body: str) -> bool:
    """Body has at least one question mark (case-study #1 ends with source after the question)."""
    return "?" in body


def _ends_with_question(body: str) -> bool:
    s = body.strip()
    return s.endswith("?")


def _multi_cta_detected(body: str) -> bool:
    """Detect multiple CTAs.
    - Case studies have ≤ 1 question mark; >1 → multiple asks.
    - "Reply YES for X, NO for Y, MAYBE for Z" pattern (3+ word-based alternatives).
    """
    # Rule 1: more than one question mark anywhere → multi-CTA
    if body.count("?") > 1:
        return True
    # Rule 2: 3+ "<word> for <word>" alternatives (the YES/NO/MAYBE pattern)
    alt_matches = re.findall(r"\b[a-z]+\s+for\s+[a-z]+\b", body, re.IGNORECASE)
    if len(alt_matches) >= 3:
        return True
    # Rule 3: multiple "Reply X" patterns with distinct alternatives
    reply_matches = re.findall(r"\breply\s+([a-z0-9]{1,})\b", body, re.IGNORECASE)
    distinct = {m.lower() for m in reply_matches}
    # Multi-choice slot ("Reply 1", "Reply 2") is acceptable — handled by is_multi_choice_slot.
    # Word-based replies (Reply YES, Reply NO ...) — if 3+ distinct words, multi-CTA.
    word_replies = {m for m in distinct if not m.isdigit()}
    if len(word_replies) >= 3:
        return True
    return False


def _is_multi_choice_slot(body: str) -> bool:
    return bool(re.search(r"\breply\s+1\b.*\b2\b", body, re.IGNORECASE | re.DOTALL))


def _is_binary_yes_no(body: str) -> bool:
    s = body.lower()
    if re.search(r"\breply\s+(yes|no|stop|y|n)\b", s):
        return True
    if re.search(r"\b(yes|no|y/n)\??\s*$", s.strip()):
        return True
    if re.search(r"\bsay\s+(go|yes|no)\b", s):
        return True
    if re.search(r"\bconfirm\b.*\?\s*$", s.strip()):
        return True
    return False


def check(
    body: str,
    *,
    plan: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    if not body:
        return True, None, None, body

    shape = ((plan or {}).get("cta_shape") or "open_ended").lower()

    # Multi-CTA stacking is always a fail
    if _multi_cta_detected(body):
        return (
            False,
            "Multiple CTAs detected — collapse to ONE binary or open-ended ask.",
            "Keep only the single most important next step at the end of the message. "
            "Drop secondary or alternative asks.",
            body,
        )

    if shape == "none":
        if _question_count_overall(body) > 0:
            return (
                False,
                "cta_shape=none but body contains a question.",
                "Drop the question — this is a pure-information message; no CTA needed.",
                body,
            )
        return True, None, None, body

    if shape == "binary_yes_no":
        if _is_binary_yes_no(body):
            return True, None, None, body
        return (
            False,
            "Expected binary YES/NO CTA but body doesn't end with one.",
            "End the message with a single binary ask: 'Reply YES to proceed' "
            "or '... Confirm?'. Avoid open-ended phrasing.",
            body,
        )

    if shape == "multi_choice_slot":
        if _is_multi_choice_slot(body):
            return True, None, None, body
        return (
            False,
            "Expected multi-choice slot CTA (Reply 1 / 2 ...) but not present.",
            "End with: 'Reply 1 for <slot1>, 2 for <slot2>, or tell us a time that works.'",
            body,
        )

    if shape == "open_ended":
        # Permissive: any clear next-step indicator passes. Case studies use
        # questions, low-friction commits, multi-choice prompts, or "or tell us".
        if _has_question_anywhere(body):
            return True, None, None, body
        if _is_multi_choice_slot(body) or _is_binary_yes_no(body):
            return True, None, None, body
        permissive_patterns = [
            r"\bwant me to\b",
            r"\bI(?:'|’)?ll\b",
            r"\bjust (?:say|reply|confirm)\b",
            r"\b(\d+)[ -]?min(?:ute)?s?\b",
            r"\blet me know\b",
            r"\bor tell (?:us|me)\b",
            r"\breply\b",
            r"\bcall (?:us|me)\b",
        ]
        if any(re.search(p, body, re.IGNORECASE) for p in permissive_patterns):
            return True, None, None, body
        return (
            False,
            "Expected open-ended question or low-friction commit but body has neither.",
            "Add a question (e.g. 'Want me to draft it?') OR a low-friction commit "
            "(e.g. 'I'll draft it — just reply Yes', '5-min setup', 'Reply 1 / 2 / or tell us').",
            body,
        )

    # Unknown shape — pass through
    return True, None, None, body
