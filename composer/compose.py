"""
compose() — top-level entrypoint of the message-generation pipeline.

Phase E ships PLAN → DRAFT → assemble. Phase G adds VALIDATE → SELF-SCORE → REFINE.

Returns a ComposedMessage with body, cta, send_as, suppression_key, rationale,
template_name, template_params — ready to be turned into a /v1/tick action.
"""

from __future__ import annotations

import re
from typing import Any

from core.logging import logger
from core.models import ComposedMessage

from composer.prompts import kind_router
from composer.retrieve import find_digest_item
from composer.signal_interpreter import interpret_signals
from composer.stages.draft import draft as draft_stage
from composer.stages.plan import plan as plan_stage


COMPOSER_VERSION = "0.2.0-phase-DE"


async def compose(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None = None,
) -> ComposedMessage | None:
    """
    Compose a single message from the 4 contexts.

    Returns ComposedMessage on success, or None if the pipeline decides this
    trigger isn't worth sending (restraint is rewarded).
    """
    kind = trigger.get("kind", "default")
    kind_module = kind_router.route(kind)
    is_hand_tuned = kind_router.is_hand_tuned(kind)

    # ─── Resolve external context references ────────────────────────────────
    raw_signals = (merchant or {}).get("signals", []) or []
    interpreted = interpret_signals(raw_signals, merchant or {}, category or {})

    digest_item = None
    payload = trigger.get("payload") or {}
    top_item_id = payload.get("top_item_id") or payload.get("digest_item_id")
    if top_item_id and category:
        digest_item = find_digest_item(category, top_item_id)

    # ─── Stage 1: PLAN ──────────────────────────────────────────────────────
    plan_dict = await plan_stage(
        category=category or {},
        merchant=merchant or {},
        trigger=trigger or {},
        customer=customer,
        interpreted_signals=interpreted,
        digest_item=digest_item,
        is_hand_tuned=is_hand_tuned,
    )

    if not plan_dict.get("should_send", True):
        logger.info(
            "compose.refused",
            extra={
                "kind": kind,
                "merchant_id": (merchant or {}).get("merchant_id"),
                "trigger_id": (trigger or {}).get("id"),
                "reason": plan_dict.get("skip_reason"),
            },
        )
        return None

    # ─── Stage 2: DRAFT ─────────────────────────────────────────────────────
    draft_dict = await draft_stage(
        category=category or {},
        merchant=merchant or {},
        trigger=trigger or {},
        customer=customer,
        plan_dict=plan_dict,
        interpreted_signals=interpreted,
        digest_item=digest_item,
    )

    body = draft_dict["body"]
    if not body or len(body) < 5:
        logger.warning("compose.empty_body", extra={"kind": kind})
        return None

    # ─── Stage 6: ASSEMBLE ──────────────────────────────────────────────────
    rationale = (
        f"kind={kind} levers={plan_dict.get('compulsion_levers')} "
        f"language={plan_dict.get('language')} "
        f"draft_rationale={draft_dict.get('rationale')!r} "
        f"composer_version={COMPOSER_VERSION}"
    )

    return ComposedMessage(
        body=body,
        cta=_normalize_cta(plan_dict.get("cta_shape", "open_ended")),
        send_as=plan_dict.get("send_as", "vera"),
        suppression_key=trigger.get("suppression_key") or _derive_suppression_key(trigger),
        rationale=rationale,
        template_name=_template_name(plan_dict.get("send_as", "vera"), kind),
        template_params=_split_for_template(body),
        composer_version=COMPOSER_VERSION,
        self_scores={},  # populated in Phase G
    )


# ─── helpers ────────────────────────────────────────────────────────────────

def _normalize_cta(shape: str) -> str:
    """Canonical CTA strings the assembler emits."""
    mapping = {
        "open_ended": "open_ended",
        "binary_yes_no": "binary_yes_no",
        "multi_choice_slot": "multi_choice_slot",
        "binary_confirm_cancel": "binary_yes_no",
        "none": "none",
    }
    return mapping.get(shape, "open_ended")


def _template_name(send_as: str, kind: str) -> str:
    if send_as == "merchant_on_behalf":
        return f"merchant_{kind}_v1"
    return f"vera_{kind}_v1"


def _split_for_template(body: str) -> list[str]:
    """Split body into 3 chunks for {{1}}/{{2}}/{{3}} placeholders.
    Heuristic: split on sentence boundaries; pad to 3."""
    sentences = re.split(r"(?<=[.!?])\s+", body.strip())
    sentences = [s for s in sentences if s.strip()]
    if not sentences:
        return [body, "", ""]
    if len(sentences) == 1:
        return [sentences[0], "", ""]
    if len(sentences) == 2:
        return [sentences[0], sentences[1], ""]
    third = " ".join(sentences[2:])
    return [sentences[0], sentences[1], third]


def _derive_suppression_key(trigger: dict[str, Any]) -> str:
    """Build a default suppression_key when the trigger doesn't carry one."""
    parts = [
        trigger.get("kind", "unknown"),
        trigger.get("merchant_id") or trigger.get("customer_id") or "any",
        trigger.get("id", ""),
    ]
    return ":".join(p for p in parts if p)
