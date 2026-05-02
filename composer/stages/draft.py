"""
Stage 2 — DRAFT.

The big-model call that writes the actual message. Builds the prompt from:
- system_base (global voice + anti-patterns + lever priorities)
- kind-specific framing (research_digest / recall_due / default)
- the PLAN output (selected_facts + levers + voice_notes + language + cta_shape)
- the 4 contexts + interpreted signals + retrieved digest item
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import logger
from llm.groq_client import get_groq
from llm.routes import Purpose

from composer.prompts import kind_router
from composer.prompts.system_base import SYSTEM_BASE


DRAFT_USER_TEMPLATE = """\
{kind_framing}

=== LEVER HINT FOR THIS KIND (production Vera's biggest misses get 1.5× weight) ===
{lever_hint}

=== PLAN (from PLAN stage — use these as your anchors) ===
selected_facts: {selected_facts}
compulsion_levers: {compulsion_levers}
voice_notes: {voice_notes}
language: {language}
cta_shape: {cta_shape}
send_as: {send_as}

=== CATEGORY ({category_slug}) ===
voice: {voice}
peer_stats: {peer_stats}
{patient_content_sample}

=== MERCHANT ===
identity: {identity}
subscription: {subscription}
performance (30d): {performance}
active_offers: {active_offers}
expired_offers (do NOT use): {expired_offers}
customer_aggregate: {customer_aggregate}
signals (interpreted): {signals_interpreted}
recent conversation history (last 5 turns): {history}
review_themes: {review_themes}

=== TRIGGER ===
kind: {kind}
source: {source}
urgency: {urgency}
payload: {trigger_payload}
{digest_item_block}

=== CUSTOMER ===
{customer_block}

Now produce the JSON output described in the system message.
"""


async def draft(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None,
    plan_dict: dict[str, Any],
    interpreted_signals: list[str],
    digest_item: dict[str, Any] | None,
    feedback: str | None = None,
    *,
    variant_id: str | None = None,
) -> dict[str, Any]:
    """
    Run the DRAFT stage. Returns dict with body + rationale + variant_id.
    Falls back to safe defaults on parse error so the pipeline still ships SOMETHING.

    `feedback` is appended on re-DRAFT (when validators rejected the first attempt).
    `variant_id` selects an A/B prompt variant from system_base.SYSTEM_BASE_VARIANTS.
       None (default) → 'standard'.
    """
    kind = trigger.get("kind", "default")
    kind_module = kind_router.route(kind)
    # Use replace (not format) so curly-braced examples in framing text don't break.
    kind_framing = kind_module.KIND_FRAMING.replace("{kind}", kind)
    # Inject the kind-specific lever hint so DRAFT actually uses the priorities
    # the kind module declares (without this, only PLAN sees them).
    lever_hint = getattr(kind_module, "LEVER_HINT", "")

    # Split offers into active/expired so the prompt explicitly knows what's usable
    offers = (merchant or {}).get("offers") or []
    active_offers = [o for o in offers if (o.get("status") or "").lower() == "active"]
    expired_offers = [o for o in offers if (o.get("status") or "").lower() != "active"]

    # Sample patient/customer content library so prompts that need it can reference real items
    if (category or {}).get("patient_content_library"):
        sample_lib = (
            "patient_content_library (sample of 2):\n  "
            + "\n  ".join(
                f"- id={i.get('id')} title={i.get('title')!r}"
                for i in category["patient_content_library"][:2]
            )
        )
    else:
        sample_lib = ""

    if customer:
        customer_block = (
            f"identity: {customer.get('identity')}\n"
            f"relationship: {customer.get('relationship')}\n"
            f"state: {customer.get('state')}\n"
            f"preferences: {customer.get('preferences')}\n"
            f"consent: {customer.get('consent')}"
        )
    else:
        customer_block = "(none — this is a merchant-facing message; do NOT address a customer)"

    digest_block = ""
    if digest_item:
        digest_block = (
            f"\n=== RETRIEVED DIGEST ITEM (resolved from trigger.payload.top_item_id) ===\n"
            f"  title: {digest_item.get('title')}\n"
            f"  source: {digest_item.get('source')}\n"
            f"  trial_n: {digest_item.get('trial_n')}\n"
            f"  patient_segment: {digest_item.get('patient_segment')}\n"
            f"  summary: {digest_item.get('summary')}\n"
            f"  actionable: {digest_item.get('actionable')}\n"
            f"  date: {digest_item.get('date')}\n"
        )

    user_msg = DRAFT_USER_TEMPLATE.format(
        kind_framing=kind_framing,
        lever_hint=lever_hint or "(no kind-specific hint — defer to PLAN)",
        selected_facts=plan_dict.get("selected_facts", []),
        compulsion_levers=plan_dict.get("compulsion_levers", []),
        voice_notes=plan_dict.get("voice_notes", ""),
        language=plan_dict.get("language", "en"),
        cta_shape=plan_dict.get("cta_shape", "open_ended"),
        send_as=plan_dict.get("send_as", "vera"),
        category_slug=(category or {}).get("slug", "?"),
        voice=(category or {}).get("voice", {}),
        peer_stats=(category or {}).get("peer_stats", {}),
        patient_content_sample=sample_lib,
        identity=(merchant or {}).get("identity", {}),
        subscription=(merchant or {}).get("subscription", {}),
        performance=(merchant or {}).get("performance", {}),
        active_offers=[o.get("title") for o in active_offers],
        expired_offers=[o.get("title") for o in expired_offers],
        customer_aggregate=(merchant or {}).get("customer_aggregate", {}),
        signals_interpreted=interpreted_signals,
        history=[
            {"from": h.get("from"), "body": (h.get("body") or "")[:160], "engagement": h.get("engagement")}
            for h in ((merchant or {}).get("conversation_history") or [])[-5:]
        ],
        review_themes=(merchant or {}).get("review_themes", []),
        kind=kind,
        source=trigger.get("source"),
        urgency=trigger.get("urgency"),
        trigger_payload=trigger.get("payload", {}),
        digest_item_block=digest_block,
        customer_block=customer_block,
    )

    if feedback:
        user_msg += f"\n\n=== FEEDBACK FROM PREVIOUS ATTEMPT ===\n{feedback}\n"

    # Resolve A/B variant — falls back to 'standard' if variant_id is unknown/None
    resolved_variant_id, system_prompt = get_variant(variant_id)

    groq = get_groq()
    raw = await groq.complete(
        Purpose.DRAFT,
        prompt=user_msg,
        system=system_prompt,
        json_mode=True,
        temperature=0.0,
    )

    try:
        parsed = json.loads(raw)
        body = (parsed.get("body") or "").strip()
        rationale = (parsed.get("rationale") or "").strip()
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("draft.malformed_json", extra={"raw": raw[:300], "exc": str(e)})
        body = raw.strip()
        rationale = "(rationale missing — JSON parse failed)"

    return {
        "body": body,
        "rationale": rationale,
        "model": "llama-3.3-70b-versatile",
        "variant_id": resolved_variant_id,
        "raw_response": raw,
    }
