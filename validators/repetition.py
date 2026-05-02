"""
Repetition validator — fails if the body is too similar to a prior bot turn
in the same conversation. Levenshtein-based via rapidfuzz.
"""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz


SIMILARITY_THRESHOLD = 85  # 0-100, higher = stricter
MIN_BODY_LEN_TO_CHECK = 30  # very short messages can be repetitive incidentally


def check(
    body: str,
    *,
    conversation_history: list[dict[str, Any]] | None = None,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    if not body or len(body) < MIN_BODY_LEN_TO_CHECK or not conversation_history:
        return True, None, None, body

    prior_bot_bodies = [
        (turn.get("body") or "")
        for turn in conversation_history
        if (turn.get("from") or "").lower() in ("vera", "bot", "merchant_on_behalf")
        and turn.get("body")
    ]
    if not prior_bot_bodies:
        return True, None, None, body

    best_idx = -1
    best_score = 0.0
    for i, prior in enumerate(prior_bot_bodies):
        score = fuzz.token_set_ratio(body, prior)
        if score > best_score:
            best_score = score
            best_idx = i

    if best_score >= SIMILARITY_THRESHOLD:
        return (
            False,
            f"Body is {best_score:.0f}% similar to a prior turn (#{best_idx}); avoid repetition.",
            "Produce a fresh angle. Do not repeat the same hook, the same numbers, "
            "or the same call-to-action used in any prior bot turn in this conversation.",
            body,
        )
    return True, None, None, body
