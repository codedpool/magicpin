"""
Stage 4 — SELF-SCORE.

Internal LLM judge using the same 5-dim rubric as the official judge.
Returns 0-10 per dimension + a single 'weakness' string + an improvement
suggestion that REFINE will use if min_dim < 7.
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import logger
from llm.groq_client import get_groq
from llm.routes import Purpose


SELF_SCORE_SYSTEM = """\
You are an internal QA scorer for the Vera composer. You grade a single
composed message using the official 5-dimension rubric (each 0-10).

Be STRICT. 5 = average. 7+ = good. 9+ = excellent. 10 = the message could
not score higher under any reasonable judge.

Dimensions:
1. decision_quality      — does the message pick the strongest signal for THIS moment?
                           combines trigger + merchant state + category fit before writing.
2. specificity           — verifiable facts: numbers, prices, dates, source citations from contexts.
3. category_fit          — voice + vocabulary match the business type (clinical/peer/operator/coach).
4. merchant_fit          — owner name, real metrics, real offers, language preference honored.
5. engagement_compulsion — would the merchant reply? clear lever + low-friction next action.

Output ONLY this JSON (no commentary, no markdown):
{
  "decision_quality": <int 0-10>,
  "specificity": <int 0-10>,
  "category_fit": <int 0-10>,
  "merchant_fit": <int 0-10>,
  "engagement_compulsion": <int 0-10>,
  "weakest_dimension": "<one dim name from above>",
  "weakness": "<one short sentence: what specifically is weak>",
  "suggested_improvement": "<one sentence: what to add or change to lift the score>"
}
"""


SELF_SCORE_USER_TEMPLATE = """\
=== MESSAGE TO SCORE ===
{body}

=== CONTEXT (truncated) ===
category.slug: {cat_slug}
category.voice.tone: {voice_tone}
merchant.identity.name: {mer_name}
merchant.identity.owner_first_name: {owner}
merchant.identity.locality: {locality}
merchant.identity.languages: {languages}
merchant.performance: {performance}
merchant.signals: {signals}
merchant.active_offers: {active_offers}
trigger.kind: {trigger_kind}
trigger.payload: {trigger_payload}
customer.identity.name: {customer_name}
customer.identity.language_pref: {customer_lang}

Score now.
"""


async def self_score(
    body: str,
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not body:
        return _zero_scores("empty body")

    voice = (category or {}).get("voice", {}) or {}
    identity = (merchant or {}).get("identity", {}) or {}
    cust_id = (customer or {}).get("identity", {}) or {}

    user_msg = SELF_SCORE_USER_TEMPLATE.format(
        body=body,
        cat_slug=(category or {}).get("slug", "?"),
        voice_tone=voice.get("tone", "?"),
        mer_name=identity.get("name", "?"),
        owner=identity.get("owner_first_name"),
        locality=identity.get("locality", "?"),
        languages=identity.get("languages", []),
        performance=(merchant or {}).get("performance", {}),
        signals=(merchant or {}).get("signals", []),
        active_offers=[
            o.get("title")
            for o in (merchant or {}).get("offers", [])
            if (o.get("status") or "").lower() == "active"
        ],
        trigger_kind=trigger.get("kind"),
        trigger_payload=trigger.get("payload", {}),
        customer_name=cust_id.get("name"),
        customer_lang=cust_id.get("language_pref"),
    )

    groq = get_groq()
    raw = await groq.complete(
        Purpose.SELF_SCORE,
        prompt=user_msg,
        system=SELF_SCORE_SYSTEM,
        json_mode=True,
        temperature=0.0,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("self_score.malformed_json", extra={"raw": raw[:300], "exc": str(e)})
        return _zero_scores("self_score JSON parse failed")

    return {
        "decision_quality": _clamp(parsed.get("decision_quality")),
        "specificity": _clamp(parsed.get("specificity")),
        "category_fit": _clamp(parsed.get("category_fit")),
        "merchant_fit": _clamp(parsed.get("merchant_fit")),
        "engagement_compulsion": _clamp(parsed.get("engagement_compulsion")),
        "weakest_dimension": parsed.get("weakest_dimension") or "",
        "weakness": parsed.get("weakness") or "",
        "suggested_improvement": parsed.get("suggested_improvement") or "",
    }


def _clamp(v: Any, lo: int = 0, hi: int = 10) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return 5


def _zero_scores(weakness: str) -> dict[str, Any]:
    return {
        "decision_quality": 0,
        "specificity": 0,
        "category_fit": 0,
        "merchant_fit": 0,
        "engagement_compulsion": 0,
        "weakest_dimension": "all",
        "weakness": weakness,
        "suggested_improvement": "",
    }


def total(scores: dict[str, Any]) -> int:
    return sum(int(scores.get(d, 0)) for d in (
        "decision_quality", "specificity", "category_fit", "merchant_fit", "engagement_compulsion"
    ))


def min_dim(scores: dict[str, Any]) -> int:
    return min(
        int(scores.get(d, 0)) for d in (
            "decision_quality", "specificity", "category_fit", "merchant_fit", "engagement_compulsion"
        )
    )
