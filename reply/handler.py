"""
Reply handler — orchestrates the 6-detector cascade for /v1/reply.

Order (cheapest → most expensive; first match wins):
  1. Auto-reply  (regex + repetition; counter-based escalation)
  2. Hostile     (regex; end + block 30d)
  3. Wait request (regex; back off)
  4. Intent transition (regex; switch to action-mode follow-up)
  5. Out-of-scope (LLM CLASSIFY; polite redirect)
  6. Engaged follow-up (LLM REPLY; default)

Persists the inbound merchant turn + outbound bot turn to the conversation
store so subsequent calls can build on the history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.logging import logger
from core.settings import settings

from reply import auto_reply, hostile, intent, out_of_scope, wait_request, follow_up


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def handle_reply(
    *,
    conversation_id: str,
    message: str,
    merchant_id: str | None,
    customer_id: str | None,
    from_role: str,
    received_at: str,
    turn_number: int,
    store: Any,
    category: dict[str, Any] | None = None,
    merchant: dict[str, Any] | None = None,
    customer: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Main /v1/reply dispatcher. Returns the action JSON.

    `store` is the WriteThroughStore (or InMemoryStore) — used for conversation
    persistence + suppression updates.
    """
    # ─── 0. Append the inbound merchant turn to the conversation ───────────
    inbound_turn = {
        "from": from_role,
        "body": message,
        "ts": received_at or _utc_iso(),
        "turn_number": turn_number,
    }
    await store.append_conversation_turn(
        conversation_id,
        inbound_turn,
        merchant_id=merchant_id,
        customer_id=customer_id,
    )

    # Pull conversation state AFTER appending the inbound turn
    conversation = await store.get_conversation(conversation_id) or {
        "conversation_id": conversation_id,
        "turns": [inbound_turn],
    }

    # If the conversation was already ended, do not re-engage
    if conversation.get("ended"):
        return {
            "action": "end",
            "rationale": f"Conversation already ended: {conversation.get('end_reason') or 'prior'}.",
        }

    # ─── 1. Auto-reply detection ───────────────────────────────────────────
    if auto_reply.detect(message, conversation):
        new_count = await store.increment_auto_reply_count(conversation_id)
        action = auto_reply.escalate(new_count)
        logger.info(
            "reply.auto_reply_detected",
            extra={"conv_id": conversation_id, "count": new_count, "next_action": action.get("action")},
        )
        await _persist_outbound(store, conversation_id, action, merchant_id, customer_id)
        if action["action"] == "end":
            await store.mark_conversation_ended(conversation_id, "auto_reply_3x")
        return action

    # ─── 2. Hostile / opt-out ──────────────────────────────────────────────
    if hostile.detect(message):
        action = hostile.action()
        logger.info("reply.hostile_detected", extra={"conv_id": conversation_id})
        if merchant_id:
            await store.mark_merchant_blocked(merchant_id, reason="hostile_reply",
                                              ttl_days=settings.BLOCK_TTL_DAYS)
        await store.mark_conversation_ended(conversation_id, "hostile")
        return action

    # ─── 3. Wait request ───────────────────────────────────────────────────
    wait_secs = wait_request.detect(message)
    if wait_secs is not None:
        action = wait_request.action(wait_secs)
        logger.info(
            "reply.wait_requested",
            extra={"conv_id": conversation_id, "wait_seconds": wait_secs},
        )
        return action

    # ─── 4. Intent transition (commitment) ────────────────────────────────
    is_commitment = intent.detect(message)
    if is_commitment:
        logger.info("reply.intent_transition", extra={"conv_id": conversation_id})
        action = await follow_up.compose_follow_up(
            message=message,
            conversation=conversation,
            merchant=merchant,
            trigger=trigger,
            customer=customer,
            category=category,
            action_mode=True,
        )
        await _persist_outbound(store, conversation_id, action, merchant_id, customer_id)
        return action

    # ─── 5. Out-of-scope (LLM classify) ────────────────────────────────────
    on_topic, reason = await out_of_scope.classify_on_topic(
        message,
        original_trigger_kind=(trigger or conversation).get("kind") or conversation.get("trigger_id"),
    )
    if not on_topic:
        action = out_of_scope.redirect(message, (trigger or {}).get("kind"))
        logger.info(
            "reply.out_of_scope",
            extra={"conv_id": conversation_id, "reason": reason},
        )
        await _persist_outbound(store, conversation_id, action, merchant_id, customer_id)
        return action

    # ─── 6. Engaged follow-up (default) ────────────────────────────────────
    action = await follow_up.compose_follow_up(
        message=message,
        conversation=conversation,
        merchant=merchant,
        trigger=trigger,
        customer=customer,
        category=category,
        action_mode=False,
    )
    logger.info("reply.engaged_followup", extra={"conv_id": conversation_id})
    await _persist_outbound(store, conversation_id, action, merchant_id, customer_id)
    return action


async def _persist_outbound(
    store: Any,
    conversation_id: str,
    action: dict[str, Any],
    merchant_id: str | None,
    customer_id: str | None,
) -> None:
    """If the action is a send, persist as a bot turn + update last_bot_body."""
    if action.get("action") != "send":
        return
    body = action.get("body") or ""
    if not body:
        return
    bot_turn = {
        "from": "vera",
        "body": body,
        "cta": action.get("cta"),
        "ts": _utc_iso(),
        "rationale": action.get("rationale"),
    }
    await store.append_conversation_turn(
        conversation_id,
        bot_turn,
        merchant_id=merchant_id,
        customer_id=customer_id,
    )
    await store.set_last_bot_body(conversation_id, body)
