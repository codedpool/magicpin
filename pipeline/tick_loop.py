"""
Tick loop — implements POST /v1/tick.

For each available trigger:
  1. Look it up in the context store (must have been pushed earlier)
  2. Filter via should_send() (cadence, suppression, blocked, expired)
  3. Cap to one action per merchant per tick (per testing brief)
  4. Cap total actions at 20 (per testing brief)
  5. Parallel compose() via asyncio.gather with semaphore=TICK_CONCURRENCY
  6. Hard 25s deadline; on timeout return whatever's done
  7. Mark suppression key + persist outbound turn to conversation for each ship
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from core.logging import logger
from core.settings import settings
from composer.compose import compose

from pipeline.should_send import should_send


MAX_ACTIONS_PER_TICK = 20  # per testing brief §5


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_conv_id(merchant_id: str, trigger: dict[str, Any], customer_id: str | None) -> str:
    """Decodable conv_id format: conv_<merchant_short>_<kind>_<date> (case studies #8)."""
    short = merchant_id.split("_")[1] if "_" in merchant_id else merchant_id[:10]
    kind = trigger.get("kind", "default")
    payload = trigger.get("payload") or {}
    suppression = trigger.get("suppression_key", "") or ""
    # Try to extract a week/date marker for stability across same-trigger ticks
    week_marker = ""
    for token in suppression.split(":"):
        if token.startswith("2026-W") or token.count("-") == 2:
            week_marker = token
            break
    if not week_marker:
        week_marker = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if customer_id:
        # Customer-facing — include customer short id
        cust_short = customer_id.split("_")[1] if "_" in customer_id else customer_id[:10]
        return f"conv_{cust_short}_{kind}_{week_marker}"
    return f"conv_{short}_{kind}_{week_marker}"


async def run_tick(
    *,
    now_iso: str,
    available_triggers: list[str],
    store: Any,
    deadline_seconds: int | None = None,
) -> list[dict[str, Any]]:
    """Process one /v1/tick. Returns the actions[] list."""
    deadline_seconds = deadline_seconds or settings.TICK_DEADLINE_SECONDS
    hard_deadline = time.time() + deadline_seconds

    if not available_triggers:
        return []

    # 1. Resolve triggers + filter via should_send
    filtered: list[dict[str, Any]] = []
    skip_reasons: dict[str, int] = {}
    for trg_id in available_triggers:
        trigger = await store.get_context("trigger", trg_id)
        if not trigger:
            skip_reasons["not_found"] = skip_reasons.get("not_found", 0) + 1
            continue
        ok, reason = await should_send(trigger, store)
        if not ok:
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            continue
        filtered.append(trigger)

    # 2. Dedupe — one per merchant per tick (testing brief §6)
    seen_merchants: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for trg in filtered:
        mid = trg.get("merchant_id") or ""
        if mid in seen_merchants:
            skip_reasons["merchant_already_in_tick"] = skip_reasons.get("merchant_already_in_tick", 0) + 1
            continue
        seen_merchants.add(mid)
        deduped.append(trg)

    # 3. Cap to MAX_ACTIONS_PER_TICK
    if len(deduped) > MAX_ACTIONS_PER_TICK:
        skip_reasons["over_action_cap"] = len(deduped) - MAX_ACTIONS_PER_TICK
        deduped = deduped[:MAX_ACTIONS_PER_TICK]

    logger.info(
        "tick.filtered",
        extra={
            "incoming": len(available_triggers),
            "after_filter": len(deduped),
            "skip_reasons": skip_reasons,
        },
    )

    if not deduped:
        return []

    # 4. Parallel compose with semaphore + hard deadline
    sem = asyncio.Semaphore(settings.TICK_CONCURRENCY)

    async def _one(trigger: dict[str, Any]) -> dict[str, Any] | None:
        time_left = hard_deadline - time.time()
        if time_left <= 1:
            logger.info("tick.deadline_skip", extra={"trigger_id": trigger.get("id")})
            return None
        async with sem:
            try:
                action = await asyncio.wait_for(
                    _compose_to_action(trigger, store),
                    timeout=max(1.0, hard_deadline - time.time()),
                )
                return action
            except asyncio.TimeoutError:
                logger.warning("tick.compose_timeout", extra={"trigger_id": trigger.get("id")})
                return None
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "tick.compose_exception",
                    extra={"trigger_id": trigger.get("id"), "exc_type": type(e).__name__},
                )
                return None

    results = await asyncio.gather(*[_one(t) for t in deduped], return_exceptions=False)
    actions = [a for a in results if a is not None]

    # 5. For each shipped action: mark suppression + persist outbound turn
    for action in actions:
        try:
            mid = action.get("merchant_id") or ""
            sup_key = action.get("suppression_key") or ""
            if mid and sup_key:
                await store.mark_suppression(
                    mid, sup_key,
                    ttl_days=settings.SUPPRESSION_TTL_DAYS,
                    trigger_id=action.get("trigger_id"),
                )

            await store.append_conversation_turn(
                action["conversation_id"],
                {
                    "from": "vera" if action.get("send_as") != "merchant_on_behalf" else "merchant_on_behalf",
                    "body": action.get("body"),
                    "cta": action.get("cta"),
                    "ts": _utc_iso(),
                    "trigger_id": action.get("trigger_id"),
                    "rationale": action.get("rationale"),
                },
                merchant_id=mid,
                customer_id=action.get("customer_id"),
                trigger_id=action.get("trigger_id"),
                send_as=action.get("send_as", "vera"),
            )
            await store.set_last_bot_body(action["conversation_id"], action.get("body") or "")
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "tick.post_send_persist_failed",
                extra={"trigger_id": action.get("trigger_id"), "exc_type": type(e).__name__},
            )

    logger.info(
        "tick.shipped",
        extra={"count": len(actions), "elapsed_ms": int((time.time() - (hard_deadline - deadline_seconds)) * 1000)},
    )
    return actions


async def _compose_to_action(trigger: dict[str, Any], store: Any) -> dict[str, Any] | None:
    """Resolve contexts + run compose() + assemble TickAction-shaped dict."""
    merchant_id = trigger.get("merchant_id")
    customer_id = trigger.get("customer_id")

    if not merchant_id:
        return None
    merchant = await store.get_context("merchant", merchant_id)
    if not merchant:
        logger.info("tick.merchant_not_found", extra={"merchant_id": merchant_id})
        return None

    cat_slug = merchant.get("category_slug") or (merchant.get("identity") or {}).get("category_slug")
    if not cat_slug:
        logger.info("tick.no_category_slug", extra={"merchant_id": merchant_id})
        return None
    category = await store.get_context("category", cat_slug)
    if not category:
        logger.info("tick.category_not_found", extra={"slug": cat_slug})
        return None

    customer = None
    if customer_id:
        customer = await store.get_context("customer", customer_id)

    # Build conv_id FIRST so we can look up bot's own prior sends in this
    # conversation (cross-tick repetition guard, anti-pattern §10 of brief).
    conv_id = _build_conv_id(merchant_id, trigger, customer_id)
    prior_conv = await store.get_conversation(conv_id) or {}
    prior_turns = prior_conv.get("turns") or []
    merchant_history = (merchant or {}).get("conversation_history") or []
    combined_history = list(merchant_history) + list(prior_turns)

    msg = await compose(
        category, merchant, trigger, customer,
        conversation_history=combined_history,
    )
    if msg is None:
        return None

    return {
        "conversation_id": conv_id,
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "send_as": msg.send_as,
        "trigger_id": trigger.get("id"),
        "template_name": msg.template_name,
        "template_params": msg.template_params,
        "body": msg.body,
        "cta": msg.cta,
        "suppression_key": msg.suppression_key or trigger.get("suppression_key", ""),
        "rationale": msg.rationale,
    }
