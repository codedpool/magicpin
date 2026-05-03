"""
WriteThroughStore — composes InMemoryStore (fast read path) + SupabaseStore (durable path).

Reads always serve from memory (sub-ms).
Writes hit memory synchronously, then schedule a non-blocking Supabase upsert.
On startup, rehydrate memory from Supabase (<1s for typical state size).

Resilient by design: if a Supabase write fails, log it and keep going. Memory is
the source of truth for the live request path; Supabase is for restart recovery.
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.logging import logger
from state.in_memory import InMemoryStore
from state.supabase import SupabaseStore


class WriteThroughStore:
    """Memory cache + Supabase backing. Conforms to StateStore protocol."""

    def __init__(self) -> None:
        self.memory = InMemoryStore()
        self.supabase = SupabaseStore()
        # Track in-flight async tasks so we can wait on shutdown
        self._inflight: set[asyncio.Task] = set()

    # ─── lifecycle ───────────────────────────────────────────────────────────

    async def startup(self) -> None:
        """Open Supabase pool, rehydrate in-memory from durable state."""
        await self.supabase.connect()
        await self._rehydrate()

    async def shutdown(self) -> None:
        """Wait for in-flight writes, close Supabase pool."""
        if self._inflight:
            logger.info("write_through.draining_inflight", extra={"count": len(self._inflight)})
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._inflight, return_exceptions=True),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("write_through.drain_timeout", extra={"left": len(self._inflight)})
        await self.supabase.close()

    async def _rehydrate(self) -> None:
        """Load all durable state into memory."""
        try:
            ctx_rows = await self.supabase.fetch_all_contexts()
            await self.memory.bulk_load_contexts(ctx_rows)

            conv_rows = await self.supabase.fetch_all_conversations()
            await self.memory.bulk_load_conversations(conv_rows)

            sup_rows = await self.supabase.fetch_active_suppressions()
            await self.memory.bulk_load_suppressions(sup_rows)

            blk_rows = await self.supabase.fetch_active_blocks()
            await self.memory.bulk_load_blocks(blk_rows)

            logger.info(
                "write_through.rehydrated",
                extra={
                    "contexts": len(ctx_rows),
                    "conversations": len(conv_rows),
                    "suppressions": len(sup_rows),
                    "blocks": len(blk_rows),
                },
            )
        except Exception as e:  # noqa: BLE001 — never crash startup
            logger.exception("write_through.rehydrate_failed", extra={"exc_type": type(e).__name__})

    # ─── async-fire-and-forget helper ────────────────────────────────────────

    def _fire(self, coro) -> None:
        """Schedule a Supabase write as a background task; log failures, never raise."""
        async def _wrapped():
            try:
                await coro
            except Exception as e:  # noqa: BLE001
                logger.exception("write_through.async_write_failed", extra={"exc_type": type(e).__name__})

        task = asyncio.create_task(_wrapped())
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)

    # ─── contexts ────────────────────────────────────────────────────────────

    async def put_context(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        delivered_at: str,
    ) -> tuple[bool, int | None]:
        accepted, current = await self.memory.put_context(
            scope, context_id, version, payload, delivered_at
        )
        if accepted:
            self._fire(self.supabase.upsert_context(
                scope, context_id, version, payload, delivered_at
            ))
        return accepted, current

    async def get_context(self, scope: str, context_id: str) -> dict[str, Any] | None:
        return await self.memory.get_context(scope, context_id)

    async def all_contexts(self, scope: str) -> list[dict[str, Any]]:
        return await self.memory.all_contexts(scope)

    async def context_count(self, scope: str) -> int:
        return await self.memory.context_count(scope)

    # ─── conversations ───────────────────────────────────────────────────────

    async def append_conversation_turn(
        self,
        conversation_id: str,
        turn: dict[str, Any],
        merchant_id: str | None = None,
        customer_id: str | None = None,
        trigger_id: str | None = None,
        send_as: str = "vera",
    ) -> None:
        await self.memory.append_conversation_turn(
            conversation_id, turn, merchant_id, customer_id, trigger_id, send_as
        )
        conv = await self.memory.get_conversation(conversation_id)
        if conv:
            self._fire(self.supabase.upsert_conversation(
                conversation_id=conv["conversation_id"],
                merchant_id=conv.get("merchant_id"),
                customer_id=conv.get("customer_id"),
                trigger_id=conv.get("trigger_id"),
                send_as=conv.get("send_as", "vera"),
                turns=conv.get("turns", []),
                auto_reply_count=conv.get("auto_reply_count", 0),
                last_bot_body=conv.get("last_bot_body"),
                ended=bool(conv.get("ended")),
                end_reason=conv.get("end_reason"),
            ))

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        return await self.memory.get_conversation(conversation_id)

    async def mark_conversation_ended(self, conversation_id: str, reason: str) -> None:
        await self.memory.mark_conversation_ended(conversation_id, reason)
        conv = await self.memory.get_conversation(conversation_id)
        if conv:
            self._fire(self.supabase.upsert_conversation(
                conversation_id=conv["conversation_id"],
                merchant_id=conv.get("merchant_id"),
                customer_id=conv.get("customer_id"),
                trigger_id=conv.get("trigger_id"),
                send_as=conv.get("send_as", "vera"),
                turns=conv.get("turns", []),
                auto_reply_count=conv.get("auto_reply_count", 0),
                last_bot_body=conv.get("last_bot_body"),
                ended=bool(conv.get("ended")),
                end_reason=conv.get("end_reason"),
            ))

    async def increment_auto_reply_count(self, conversation_id: str) -> int:
        new_count = await self.memory.increment_auto_reply_count(conversation_id)
        conv = await self.memory.get_conversation(conversation_id)
        if conv:
            self._fire(self.supabase.upsert_conversation(
                conversation_id=conv["conversation_id"],
                merchant_id=conv.get("merchant_id"),
                customer_id=conv.get("customer_id"),
                trigger_id=conv.get("trigger_id"),
                send_as=conv.get("send_as", "vera"),
                turns=conv.get("turns", []),
                auto_reply_count=conv.get("auto_reply_count", 0),
                last_bot_body=conv.get("last_bot_body"),
                ended=bool(conv.get("ended")),
                end_reason=conv.get("end_reason"),
            ))
        return new_count

    async def merchant_auto_reply_total(self, merchant_id: str) -> int:
        return await self.memory.merchant_auto_reply_total(merchant_id)

    async def set_last_bot_body(self, conversation_id: str, body: str) -> None:
        await self.memory.set_last_bot_body(conversation_id, body)
        conv = await self.memory.get_conversation(conversation_id)
        if conv:
            self._fire(self.supabase.upsert_conversation(
                conversation_id=conv["conversation_id"],
                merchant_id=conv.get("merchant_id"),
                customer_id=conv.get("customer_id"),
                trigger_id=conv.get("trigger_id"),
                send_as=conv.get("send_as", "vera"),
                turns=conv.get("turns", []),
                auto_reply_count=conv.get("auto_reply_count", 0),
                last_bot_body=conv.get("last_bot_body"),
                ended=bool(conv.get("ended")),
                end_reason=conv.get("end_reason"),
            ))

    # ─── suppression ─────────────────────────────────────────────────────────

    async def mark_suppression(
        self,
        merchant_id: str,
        suppression_key: str,
        ttl_days: int,
        trigger_id: str | None = None,
    ) -> None:
        await self.memory.mark_suppression(merchant_id, suppression_key, ttl_days, trigger_id)
        self._fire(self.supabase.upsert_suppression(
            merchant_id, suppression_key, ttl_days, trigger_id
        ))

    async def is_suppressed(self, merchant_id: str, suppression_key: str) -> bool:
        return await self.memory.is_suppressed(merchant_id, suppression_key)

    # ─── blocked merchants ───────────────────────────────────────────────────

    async def mark_merchant_blocked(self, merchant_id: str, reason: str, ttl_days: int) -> None:
        await self.memory.mark_merchant_blocked(merchant_id, reason, ttl_days)
        self._fire(self.supabase.upsert_blocked_merchant(merchant_id, reason, ttl_days))

    async def is_merchant_blocked(self, merchant_id: str) -> bool:
        return await self.memory.is_merchant_blocked(merchant_id)
