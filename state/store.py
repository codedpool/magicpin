"""
StateStore protocol — the contract every store implementation honors.

Phase B: InMemoryStore (sole implementation, fast).
Phase C: SupabaseStore (durable) + WriteThroughStore (composes Memory + Supabase).

Reads always go to memory. Writes go to memory synchronously, then async to Supabase.
"""

from __future__ import annotations

from typing import Any, Protocol


class StateStore(Protocol):
    """Async interface for context + conversation + suppression state."""

    # ─── contexts ────────────────────────────────────────────────────────────
    async def put_context(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        delivered_at: str,
    ) -> tuple[bool, int | None]:
        """
        Returns (accepted, current_version):
            accepted=True  → stored (new or higher version)
            accepted=False → stale_version, current_version is the existing one
        """
        ...

    async def get_context(self, scope: str, context_id: str) -> dict[str, Any] | None:
        """Return latest payload for (scope, context_id) or None if absent."""
        ...

    async def all_contexts(self, scope: str) -> list[dict[str, Any]]:
        """Return all payloads for a scope. Used by /healthz counts and rehydrate."""
        ...

    async def context_count(self, scope: str) -> int:
        """Count of stored contexts in a scope."""
        ...

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
        """Append a turn. Creates conversation row if absent."""
        ...

    async def get_conversation(
        self, conversation_id: str
    ) -> dict[str, Any] | None:
        """Return conversation state including turns + counters + ended flag."""
        ...

    async def mark_conversation_ended(
        self, conversation_id: str, reason: str
    ) -> None:
        ...

    async def increment_auto_reply_count(self, conversation_id: str) -> int:
        """Increments and returns the new count."""
        ...

    async def set_last_bot_body(self, conversation_id: str, body: str) -> None:
        ...

    # ─── suppression ─────────────────────────────────────────────────────────
    async def mark_suppression(
        self,
        merchant_id: str,
        suppression_key: str,
        ttl_days: int,
        trigger_id: str | None = None,
    ) -> None:
        ...

    async def is_suppressed(
        self, merchant_id: str, suppression_key: str
    ) -> bool:
        ...

    # ─── blocked merchants ───────────────────────────────────────────────────
    async def mark_merchant_blocked(
        self, merchant_id: str, reason: str, ttl_days: int
    ) -> None:
        ...

    async def is_merchant_blocked(self, merchant_id: str) -> bool:
        ...

    # ─── lifecycle ───────────────────────────────────────────────────────────
    async def startup(self) -> None:
        """Called once at app startup. Phase C: rehydrate from Supabase."""
        ...

    async def shutdown(self) -> None:
        """Called once at app shutdown. Phase C: close pools."""
        ...
