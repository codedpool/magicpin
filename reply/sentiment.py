"""
Per-conversation sentiment classifier.

After every merchant reply that isn't already classified as auto-reply /
hostile / wait, run a fast sentiment classifier and track the trend on
the conversation. If the merchant's tone drifts negative or disengaged
for 2+ consecutive turns, back off proactively — the merchant hasn't
said "stop" but they're signaling fade-out, and we don't want to push.

Classes:
- engaged       — interested, asking questions, positive cues
- neutral       — short factual replies, no emotion either way
- drifting      — minimal effort, "ok thanks", losing interest
- negative      — frustrated/curt but not yet a hard opt-out
- unclear       — ambiguous (default fallback)

Cheap classifier — uses 8b-instant via CLASSIFY purpose. Wrapped in
try/except so transient LLM errors return 'unclear' rather than crashing.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.logging import logger
from llm.groq_client import get_groq
from llm.routes import Purpose


SENTIMENT_LABELS = ("engaged", "neutral", "drifting", "negative", "unclear")


CLASSIFY_SYSTEM = """\
You classify the SENTIMENT of a merchant's reply in a Vera business-growth
conversation. Pick exactly ONE label:

- engaged   — they asked a follow-up, said "yes please", offered details, showed interest
- neutral   — short factual reply ("ok", "noted", "send it") with no emotion
- drifting  — minimal effort, losing interest ("k", "later", "maybe", "thanks bye")
- negative  — frustrated, curt, or showing irritation but not explicitly opting out
              (a clear "stop / not interested / spam" should already be caught upstream — only flag negative if it's softer)
- unclear   — too ambiguous to call

Return ONLY this JSON:
{ "sentiment": "<label>", "reason": "<one short phrase>" }
"""


# Cheap regex prefilters — avoid LLM call for obvious cases
_ENGAGED_REGEX = re.compile(
    r"\b(yes please|sure|please send|please share|please draft|let'?s|sounds good|"
    r"go ahead|do it|tell me more|interesting|haan ji|kar do|bhej do)\b",
    re.IGNORECASE,
)
_DRIFTING_REGEX = re.compile(
    r"^\s*(k|kk|ok|okay|hmm|cool|alright|noted|maybe|later|thanks bye|bye|tata)\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def cheap_classify(message: str) -> str | None:
    """Fast regex prefilter. Returns label or None if not confident."""
    if not message or not message.strip():
        return "unclear"
    stripped = message.strip()
    # Drifting: very short ack-only replies
    if len(stripped) <= 12 and _DRIFTING_REGEX.match(stripped):
        return "drifting"
    # Engaged: has clear interest signal
    if _ENGAGED_REGEX.search(message):
        return "engaged"
    return None


async def classify_sentiment(
    message: str, conversation: dict[str, Any] | None = None
) -> str:
    """
    Classify the merchant's latest message sentiment. Returns one of
    SENTIMENT_LABELS. On any error, returns 'unclear' (never raises).
    """
    if not message:
        return "unclear"

    cheap = cheap_classify(message)
    if cheap is not None:
        return cheap

    # LLM call only for ambiguous cases
    try:
        groq = get_groq()
        recent_history = ""
        if conversation:
            recent = (conversation.get("turns") or [])[-3:]
            recent_history = "\n".join(
                f"  [{t.get('from')}]: {(t.get('body') or '')[:160]}"
                for t in recent
            )
        prompt = (
            f"Recent conversation (oldest → newest):\n{recent_history or '(empty)'}\n\n"
            f"Latest merchant reply: {message!r}\n\nClassify."
        )
        raw = await groq.complete(
            Purpose.CLASSIFY,
            prompt=prompt,
            system=CLASSIFY_SYSTEM,
            json_mode=True,
            temperature=0.0,
            max_tokens=80,
        )
        parsed = json.loads(raw)
        label = (parsed.get("sentiment") or "unclear").lower().strip()
        if label not in SENTIMENT_LABELS:
            return "unclear"
        return label
    except Exception as e:  # noqa: BLE001
        logger.warning("sentiment.classify_failed", extra={"exc": str(e)[:200]})
        return "unclear"


def should_back_off(turns: list[dict[str, Any]]) -> tuple[bool, str]:
    """
    Inspect the conversation's turn history. If the last 2 merchant
    sentiments are 'drifting' or 'negative' (in any combination), suggest
    backing off. Returns (back_off, reason).
    """
    if not turns:
        return False, ""
    merchant_sentiments = [
        t.get("sentiment")
        for t in turns
        if (t.get("from") or "").lower() == "merchant" and t.get("sentiment")
    ]
    if len(merchant_sentiments) < 2:
        return False, ""
    last_two = merchant_sentiments[-2:]
    fade_signals = {"drifting", "negative"}
    if all(s in fade_signals for s in last_two):
        return True, f"sentiment_trend={last_two}"
    return False, ""
