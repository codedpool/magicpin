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
You decide whether a merchant's reply is ON-TOPIC for a Vera conversation.
Vera helps with growth/operations: GBP, customer engagement, offers,
performance, recall reminders, festival/event prep, research digests, AND
operational/compliance questions that trace to the active trigger.

★ STRONG BIAS TOWARD ON-TOPIC. False off-topic classification (rejecting
a legitimate help request) is far worse than a false on-topic — Vera should
attempt to help unless the topic is CLEARLY unrelated to the merchant's
business operations.

ON-TOPIC (always):
- Anything about offers, listings, customers, photos, posts, performance.
- ANY question/help-request whose subject matter overlaps the active
  trigger. Examples:
    * trigger=regulation_change about X-ray dose + merchant says
      "need help auditing my X-ray setup" → ON-TOPIC. Equipment audit
      directly relates to the regulation Vera just flagged.
    * trigger=supply_alert about a recalled drug + merchant says
      "what's the replacement workflow?" → ON-TOPIC.
    * trigger=competitor_opened + merchant says "what should I price at?"
      → ON-TOPIC.
- Equipment / clinical-process / operational questions for the merchant's
  own business (X-ray unit upgrade, fryer maintenance, stylist scheduling,
  inventory management, SOP writing) → ON-TOPIC. These ARE the merchant's
  operations.
- Requests for vendor recommendations, quotes, or workflow templates
  → ON-TOPIC.

OFF-TOPIC (only when clearly unrelated to running their business):
- GST/income-tax filing (financial accounting outside Vera's scope)
- Legal advice (litigation, contracts, IP)
- Real-estate / personal property
- Recipe/cooking advice (unrelated to running a restaurant)
- "How's your day" / personal chitchat / jokes / weather chat
- Adjacent businesses they don't run

When in doubt, classify ON-TOPIC. Vera saying "I'll help" and providing
an attempt is always better than a false redirect.

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
    """Polite redirect back to the original trigger when off-topic.

    Picks a context-appropriate "the right person to ask" instead of always
    saying "your CA". X-ray / clinical questions should never be redirected
    to an accountant — that was a confusing miss in the first judging round.
    """
    topic_phrase = (
        original_trigger_kind.replace("_", " ") if original_trigger_kind else "your growth"
    )
    msg_lower = (message or "").lower()
    # Pick a topical specialist based on what the merchant actually asked.
    if any(t in msg_lower for t in ("gst", "tax", "income tax", "tds", "filing", "audit firm", "ca ", "accountant")):
        specialist = "your CA / accountant"
    elif any(t in msg_lower for t in ("legal", "court", "lawsuit", "contract", "advocate", "lawyer")):
        specialist = "a lawyer / legal advisor"
    elif any(t in msg_lower for t in ("rent", "lease", "real estate", "property", "broker")):
        specialist = "a property advisor"
    elif any(t in msg_lower for t in ("recipe", "cooking", "menu design", "chef")):
        specialist = "a culinary consultant"
    else:
        specialist = "a specialist"
    return {
        "action": "send",
        "body": (
            f"That's outside what I can help with directly — {specialist} would be a "
            f"better fit. Coming back to {topic_phrase}: want me to pick up where we left off?"
        ),
        "cta": "binary_yes_no",
        "rationale": f"Off-topic ({specialist} domain); declining politely + redirecting to {topic_phrase}.",
    }
