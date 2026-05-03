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
You are a HARSH internal QA scorer for Vera. You grade like the production
judge LLM that recently rated our top-self-scored messages 2-3/10 on
Decision Quality and 1/10 on Engagement. Calibration: where we used to
give 8s, the real judge gave 2s. Match the real judge.

Anchor scale (use these as ceilings, not floors):
  10 = textbook perfect; could not improve.
  8  = strong, very few weaknesses.
  6  = solid in some dims, weak in others.
  4  = obvious failures present.
  2  = the dimension is essentially unaddressed.

# DIMENSIONS + EXPLICIT PENALTY CAPS

1. decision_quality — does the FIRST sentence make a SPECIFIC merchant-action
   recommendation? Does the bot pick the strongest signal for THIS moment?
   Hard caps:
   - Lead sentence parrots a regulation/fact instead of recommending action: ≤ 3
   - Generic "consider X" or "you might want to" hedging: ≤ 4
   - Lead with stat/metric instead of action: ≤ 5
   - No clear recommendation anywhere in the body: ≤ 2
   - Contrarian recommendation (skip the obvious play, with reasoning): +1 to 9-10

2. specificity — verifiable facts: numbers, prices, dates, named sources,
   localities, peer comparisons. ALL must trace to contexts.
   Hard caps:
   - Generic offer ("X% off"): ≤ 3
   - Service+price combo ("Haircut @ ₹99"): ≥ 7
   - Source citation ("JIDA Oct 2026 p.14"): ≥ 8
   - Any fabricated number caught (% / count not in contexts): ≤ 2

3. category_fit — voice + vocabulary match category (clinical/peer/operator/coach).
   Hard caps:
   - Promotional/hype voice for clinical (dentist/pharmacy): ≤ 3
   - Vocab taboo word (from category.voice.vocab_taboo): ≤ 3
   - Right register but slightly off-vocab: 6-7

4. merchant_fit — owner name, real metrics, real offers, language preference.
   Hard caps:
   - Generic "Hi" / "Hi there" instead of owner_first_name: ≤ 5
   - English-only when language_pref includes hi/te/kn/mr/ta: ≤ 4
   - Uses NUMBERS from THIS merchant's performance: +1 to 8-10
   - Re-introduces self in subsequent turn ("I'm Vera again"): ≤ 4

5. engagement_compulsion — would the merchant ACTUALLY reply?
   ★★★ ENGAGEMENT IS THE WORST-SCORED DIMENSION HISTORICALLY. Be very harsh. ★★★
   Hard caps:
   - STACKED CTAs ("Reply YES to X and Y", "Reply YES for confirm AND audit"): ≤ 1
   - Multi-CTA ("Reply 1 / Reply 2 / Reply 3"): ≤ 3 (multi-choice slot OK at 6)
   - No clear next-step / open-ended question without low-friction commit: ≤ 4
   - Long body, buried CTA: ≤ 4
   - Single binary commit ("Reply YES — I'll have X in 5 min"): ≥ 7
   - Asking-the-merchant question + reciprocity: ≥ 8
   - Clear loss-aversion or curiosity hook + binary CTA: ≥ 8

# CRITICAL: if you give any dimension ≥ 8, you must be able to point to a
# specific phrase in the body that earns the score. Be honest. Don't inflate.

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
