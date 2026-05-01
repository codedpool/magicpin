"""
Stage 1 — PLAN.

Lightweight LLM call (8b-instant, JSON mode) that picks:
- selected_facts: 5-8 anchorable facts from contexts
- compulsion_levers: 1-2 from the 8-lever taxonomy (priority weighted)
- voice_notes: clinical/peer/coach/operator/warm
- language: en | hi-en mix | te-en mix | ...
- cta_shape: open_ended | binary_yes_no | multi_choice_slot | none
- send_as: vera | merchant_on_behalf

The plan is fed into DRAFT so the bigger model can focus on writing.
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import logger
from llm.groq_client import get_groq
from llm.routes import Purpose


PLAN_SYSTEM = """\
You are the PLAN stage of the Vera composer. Read the contexts and output a
plan the DRAFT stage will use to write the message. NO commentary, NO markdown.
Return ONLY this JSON object:

{
  "selected_facts": ["fact 1", "fact 2", ...],          // 3-8 strings, each a verifiable fact pulled from the contexts
  "compulsion_levers": ["social_proof", "specificity"], // 1-2 of: social_proof, asking_the_merchant, specificity, loss_aversion, effort_externalization, curiosity, reciprocity, single_binary_commit
  "voice_notes": "peer-clinical with source citation",  // one short phrase
  "language": "en",                                     // "en", "hi-en mix", "te-en mix", "kn-en mix", "mr-en mix"
  "cta_shape": "open_ended",                            // "open_ended", "binary_yes_no", "multi_choice_slot", "none"
  "send_as": "vera",                                    // "vera" (merchant-facing) or "merchant_on_behalf" (customer-facing)
  "should_send": true,                                  // false = refuse to send (restraint is rewarded)
  "skip_reason": ""                                     // if should_send=false, one short reason
}

LEVER PRIORITY (for picking compulsion_levers):
- social_proof + asking_the_merchant get 1.5× weight (production Vera's biggest misses)
- specificity is required to score ≥9 on the specificity dimension
- single_binary_commit is the default CTA family for action triggers
- if customer context is provided, send_as=merchant_on_behalf

LANGUAGE: choose based on merchant.identity.languages (or customer.identity.language_pref
if customer is given). Default "en" if missing.

REFUSE TO SEND when:
- The trigger is too generic to anchor on a specific fact in contexts
- Merchant signals indicate "do not send" (e.g. blocked, hostile recent reply)
- Trigger has expired (use the available context to judge)
"""


PLAN_USER_TEMPLATE = """\
KIND: {kind} ({hand_tuned})
SEND_AS_HINT: {send_as_hint}

=== CATEGORY ({category_slug}) ===
voice.tone: {voice_tone}
voice.vocab_allowed (sample): {vocab_allowed}
voice.vocab_taboo: {vocab_taboo}
peer_stats: {peer_stats}
seasonal_beats (sample): {seasonal_beats}

=== MERCHANT ===
identity: name={merchant_name}, owner_first_name={owner_first_name}, locality={locality}, city={city}, languages={languages}, verified={verified}
performance (30d): {performance}
active_offers: {active_offers}
customer_aggregate: {customer_aggregate}
signals (raw): {signals_raw}
signals (interpreted): {signals_interpreted}
recent conversation history (last 3 turns): {history}

=== TRIGGER ===
kind: {kind}
source: {source}
urgency: {urgency}
payload: {trigger_payload}
suppression_key: {suppression_key}
expires_at: {expires_at}
{digest_item_block}

=== CUSTOMER ===
{customer_block}

Output the JSON plan now.
"""


async def plan(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None,
    interpreted_signals: list[str],
    digest_item: dict[str, Any] | None,
    is_hand_tuned: bool,
) -> dict[str, Any]:
    """Run the PLAN stage. Returns parsed dict — falls back to safe defaults on error."""

    voice = (category or {}).get("voice", {}) or {}
    identity = (merchant or {}).get("identity", {}) or {}

    # Build the digest_item block conditionally
    if digest_item:
        digest_block = (
            f"\n=== RETRIEVED DIGEST ITEM (resolved from trigger.payload) ===\n"
            f"id: {digest_item.get('id')}\n"
            f"kind: {digest_item.get('kind')}\n"
            f"title: {digest_item.get('title')}\n"
            f"source: {digest_item.get('source')}\n"
            f"trial_n: {digest_item.get('trial_n')}\n"
            f"patient_segment: {digest_item.get('patient_segment')}\n"
            f"summary: {digest_item.get('summary')}\n"
            f"actionable: {digest_item.get('actionable')}\n"
        )
    else:
        digest_block = ""

    if customer:
        customer_block = (
            f"name: {(customer.get('identity') or {}).get('name')}\n"
            f"language_pref: {(customer.get('identity') or {}).get('language_pref')}\n"
            f"state: {customer.get('state')}\n"
            f"relationship: {customer.get('relationship')}\n"
            f"preferences: {customer.get('preferences')}\n"
            f"consent: {customer.get('consent')}"
        )
        send_as_hint = "merchant_on_behalf (customer-facing)"
    else:
        customer_block = "(none — merchant-facing message)"
        send_as_hint = "vera (merchant-facing)"

    user_msg = PLAN_USER_TEMPLATE.format(
        kind=trigger.get("kind", "unknown"),
        hand_tuned="hand-tuned" if is_hand_tuned else "default — reason from contexts",
        send_as_hint=send_as_hint,
        category_slug=(category or {}).get("slug", "?"),
        voice_tone=voice.get("tone", "?"),
        vocab_allowed=(voice.get("vocab_allowed") or [])[:10],
        vocab_taboo=voice.get("vocab_taboo") or [],
        peer_stats=(category or {}).get("peer_stats", {}),
        seasonal_beats=(category or {}).get("seasonal_beats", [])[:3],
        merchant_name=identity.get("name", "?"),
        owner_first_name=identity.get("owner_first_name"),
        locality=identity.get("locality", "?"),
        city=identity.get("city", "?"),
        languages=identity.get("languages") or ["en"],
        verified=identity.get("verified"),
        performance=(merchant or {}).get("performance", {}),
        active_offers=[
            o.get("title") for o in (merchant or {}).get("offers", [])
            if (o.get("status") or "").lower() == "active"
        ],
        customer_aggregate=(merchant or {}).get("customer_aggregate", {}),
        signals_raw=(merchant or {}).get("signals", []),
        signals_interpreted=interpreted_signals,
        history=[
            {"from": h.get("from"), "body": (h.get("body") or "")[:120]}
            for h in ((merchant or {}).get("conversation_history") or [])[-3:]
        ],
        source=trigger.get("source"),
        urgency=trigger.get("urgency"),
        trigger_payload=trigger.get("payload", {}),
        suppression_key=trigger.get("suppression_key"),
        expires_at=trigger.get("expires_at"),
        digest_item_block=digest_block,
        customer_block=customer_block,
    )

    groq = get_groq()
    raw = await groq.complete(
        Purpose.PLAN,
        prompt=user_msg,
        system=PLAN_SYSTEM,
        json_mode=True,
        temperature=0.0,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("plan.malformed_json", extra={"raw": raw[:300], "exc": str(e)})
        parsed = {}

    # Normalize / set defaults
    return {
        "selected_facts": parsed.get("selected_facts") or [],
        "compulsion_levers": parsed.get("compulsion_levers") or ["specificity"],
        "voice_notes": parsed.get("voice_notes") or voice.get("tone", "peer"),
        "language": parsed.get("language") or _default_language(merchant, customer),
        "cta_shape": parsed.get("cta_shape") or "open_ended",
        "send_as": parsed.get("send_as") or ("merchant_on_behalf" if customer else "vera"),
        "should_send": parsed.get("should_send", True),
        "skip_reason": parsed.get("skip_reason") or "",
    }


def _default_language(merchant: dict[str, Any], customer: dict[str, Any] | None) -> str:
    if customer:
        pref = (customer.get("identity") or {}).get("language_pref")
        if pref:
            return pref
    langs = ((merchant or {}).get("identity") or {}).get("languages") or ["en"]
    if "hi" in langs:
        return "hi-en mix"
    if "te" in langs:
        return "te-en mix"
    if "kn" in langs:
        return "kn-en mix"
    if "mr" in langs:
        return "mr-en mix"
    return "en"
