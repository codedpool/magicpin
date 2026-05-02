"""
Out-of-scope (curveball) detector.

If the merchant asks something off-topic (GST filing, legal advice, real estate,
etc.) we politely decline + redirect back to the original trigger. Uses a fast
8b-instant classifier rather than regex (off-topic content is too varied).
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import logger
from llm.groq_client import get_groq
from llm.routes import Purpose


CLASSIFY_SYSTEM = """\
You decide whether a merchant's reply is ON-TOPIC for a Vera conversation about
local-commerce growth (Google Business Profile, customer engagement, offers,
performance, recall reminders, festival/event prep, research digests).

ON-TOPIC examples: questions about offers, listings, customers, photos, posts,
performance numbers, the trigger Vera sent, "what should I do next", "draft it
for me", etc.

OFF-TOPIC examples: GST filing, income tax, legal advice, real-estate help,
unrelated personal questions, jokes, weather (unless it's a festival/heatwave
that ties back to the trigger), recipe/cooking, "how's your day".

Reply ONLY with this JSON object:
{ "on_topic": <true|false>, "reason": "<one short phrase>" }
"""


async def classify_on_topic(message: str, original_trigger_kind: str | None = None) -> tuple[bool, str]:
    """Use LLM CLASSIFY to decide on-topic. Cheap (8b-instant)."""
    if not message:
        return True, "empty message — pass through"

    user_msg = (
        f"Original conversation trigger kind: {original_trigger_kind or 'unknown'}\n"
        f"Merchant's reply: {message!r}\n\n"
        "Classify."
    )

    try:
        groq = get_groq()
        raw = await groq.complete(
            Purpose.CLASSIFY,
            prompt=user_msg,
            system=CLASSIFY_SYSTEM,
            json_mode=True,
            temperature=0.0,
            max_tokens=80,
        )
        parsed = json.loads(raw)
        return bool(parsed.get("on_topic", True)), str(parsed.get("reason", ""))[:200]
    except Exception as e:  # noqa: BLE001 — never crash on classifier failure
        logger.warning("out_of_scope.classify_failed", extra={"exc": str(e)[:200]})
        return True, "classifier error — defaulting to on-topic"


def redirect(message: str, original_trigger_kind: str | None = None) -> dict[str, Any]:
    """Polite redirect back to the original trigger when off-topic."""
    topic_phrase = (
        original_trigger_kind.replace("_", " ") if original_trigger_kind else "your growth"
    )
    return {
        "action": "send",
        "body": (
            f"That's outside what I can help with directly — your CA / accountant "
            f"can. Coming back to {topic_phrase}: want me to pick up where we left off?"
        ),
        "cta": "binary_yes_no",
        "rationale": f"Merchant went off-topic; declining politely + redirecting to {topic_phrase}.",
    }
