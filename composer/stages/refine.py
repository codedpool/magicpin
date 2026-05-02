"""
Stage 5 — REFINE.

If SELF-SCORE finds any dimension < 7, run a second-pass DRAFT on a different
model (gpt-oss-120b, contrasting style) with explicit guidance about the
weakness. Re-validate + re-score. Ship whichever scored higher (best-of-2).
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import logger
from llm.groq_client import get_groq
from llm.routes import Purpose

from composer.prompts.system_base import SYSTEM_BASE


REFINE_USER_TEMPLATE = """\
This message scored below the bar in SELF-SCORE. Produce a STRONGER version.

=== ORIGINAL DRAFT ===
{original_body}

=== ORIGINAL SELF-SCORES ===
decision_quality: {decision_quality}
specificity: {specificity}
category_fit: {category_fit}
merchant_fit: {merchant_fit}
engagement_compulsion: {engagement_compulsion}

=== WEAKEST DIMENSION ===
{weakest_dimension}: {weakness}

=== TARGETED IMPROVEMENT ===
{suggested_improvement}

=== CONTEXT REMINDER ===
category.slug: {cat_slug}
category.voice.tone: {voice_tone}
category.voice.vocab_taboo: {vocab_taboo}
merchant: {mer_short}
trigger: {trigger_kind} payload={trigger_payload}
plan.language: {plan_language}
plan.cta_shape: {plan_cta_shape}
plan.send_as: {plan_send_as}
plan.compulsion_levers: {plan_levers}
{customer_block}

=== INSTRUCTIONS ===
1. KEEP what worked: voice match, length, lever choice if it scored well.
2. FIX the weakest dimension specifically — apply the targeted improvement.
3. DO NOT fabricate any new claim — only use facts from the contexts.
4. Honor plan.language (if hi-en mix, include natural Hindi tokens).
5. Honor plan.cta_shape exactly.
6. Output ONLY this JSON (no commentary):

{{
  "body": "<the improved message>",
  "rationale": "<one short sentence on what you changed and why>"
}}
"""


async def refine(
    original_body: str,
    scores: dict[str, Any],
    plan_dict: dict[str, Any],
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Run a single refine pass. Returns {body, rationale}."""

    voice = (category or {}).get("voice", {}) or {}
    identity = (merchant or {}).get("identity", {}) or {}

    if customer:
        customer_block = (
            f"customer.identity: {customer.get('identity')}\n"
            f"customer.state: {customer.get('state')}\n"
            f"customer.preferences: {customer.get('preferences')}"
        )
    else:
        customer_block = "(merchant-facing — no customer context)"

    user_msg = REFINE_USER_TEMPLATE.format(
        original_body=original_body,
        decision_quality=scores.get("decision_quality"),
        specificity=scores.get("specificity"),
        category_fit=scores.get("category_fit"),
        merchant_fit=scores.get("merchant_fit"),
        engagement_compulsion=scores.get("engagement_compulsion"),
        weakest_dimension=scores.get("weakest_dimension"),
        weakness=scores.get("weakness"),
        suggested_improvement=scores.get("suggested_improvement"),
        cat_slug=(category or {}).get("slug"),
        voice_tone=voice.get("tone"),
        vocab_taboo=voice.get("vocab_taboo"),
        mer_short={
            "name": identity.get("name"),
            "owner": identity.get("owner_first_name"),
            "locality": identity.get("locality"),
            "performance": (merchant or {}).get("performance", {}),
            "signals": (merchant or {}).get("signals", []),
            "active_offers": [
                o.get("title")
                for o in (merchant or {}).get("offers", [])
                if (o.get("status") or "").lower() == "active"
            ],
        },
        trigger_kind=trigger.get("kind"),
        trigger_payload=trigger.get("payload"),
        plan_language=plan_dict.get("language"),
        plan_cta_shape=plan_dict.get("cta_shape"),
        plan_send_as=plan_dict.get("send_as"),
        plan_levers=plan_dict.get("compulsion_levers"),
        customer_block=customer_block,
    )

    groq = get_groq()
    raw = await groq.complete(
        Purpose.REFINE,
        prompt=user_msg,
        system=SYSTEM_BASE,
        json_mode=True,
        temperature=0.3,
    )

    try:
        parsed = json.loads(raw)
        return {
            "body": (parsed.get("body") or "").strip(),
            "rationale": (parsed.get("rationale") or "").strip(),
        }
    except json.JSONDecodeError as e:
        logger.warning("refine.malformed_json", extra={"raw": raw[:300], "exc": str(e)})
        return {"body": "", "rationale": f"refine JSON parse failed: {e}"}
