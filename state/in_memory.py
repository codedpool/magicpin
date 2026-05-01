"""
InMemoryStore — fast, async-safe context + conversation state.

Used directly in Phase A+B. In Phase C it becomes the read cache behind a
write-through to Supabase. Reads always serve from this store.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryStore:
    """All state in dicts. asyncio-safe via a single lock per concern."""

    def __init__(self) -> None:
        # contexts: {(scope, context_id): {"version": int, "payload": dict, "delivered_at": str}}
        self._contexts: dict[tuple[str, str], dict[str, Any]] = {}
        self._contexts_lock = asyncio.Lock()

        # conversations: {conversation_id: {turns, auto_reply_count, last_bot_body, ended, ...}}
        self._conversations: dict[str, dict[str, Any]] = {}
        self._conversations_lock = asyncio.Lock()

        # suppressions: {(merchant_id, suppression_key): expires_at_datetime}
        self._suppressions: dict[tuple[str, str], datetime] = {}
        self._suppressions_lock = asyncio.Lock()

        # blocked_merchants: {merchant_id: expires_at_datetime}
        self._blocked: dict[str, datetime] = {}
        self._blocked_lock = asyncio.Lock()

    # ─── contexts ────────────────────────────────────────────────────────────

    async def put_context(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        delivered_at: str,
    ) -> tuple[bool, int | None]:
        async with self._contexts_lock:
            key = (scope, context_id)
            existing = self._contexts.get(key)
            if existing is not None and existing["version"] >= version:
                return False, existing["version"]
            self._contexts[key] = {
                "version": version,
                "payload": payload,
                "delivered_at": delivered_at,
                "stored_at": _utcnow().isoformat(),
            }
            return True, version

    async def get_context(self, scope: str, context_id: str) -> dict[str, Any] | None:
        async with self._contexts_lock:
            entry = self._contexts.get((scope, context_id))
            return entry["payload"] if entry else None

    async def get_context_with_version(
        self, scope: str, context_id: str
    ) -> tuple[dict[str, Any], int] | None:
        async with self._contexts_lock:
            entry = self._contexts.get((scope, context_id))
            if entry is None:
                return None
            return entry["payload"], entry["version"]

    async def all_contexts(self, scope: str) -> list[dict[str, Any]]:
        async with self._contexts_lock:
            return [
                e["payload"] for (s, _), e in self._contexts.items() if s == scope
            ]

    async def context_count(self, scope: str) -> int:
        async with self._contexts_lock:
            return sum(1 for (s, _) in self._contexts if s == scope)

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
        async with self._conversations_lock:
            conv = self._conversations.setdefault(
                conversation_id,
                {
                    "conversation_id": conversation_id,
                    "merchant_id": merchant_id,
                    "customer_id": customer_id,
                    "trigger_id": trigger_id,
                    "send_as": send_as,
                    "turns": [],
                    "auto_reply_count": 0,
                    "last_bot_body": None,
                    "ended": False,
                    "end_reason": None,
                    "created_at": _utcnow().isoformat(),
                    "updated_at": _utcnow().isoformat(),
                },
            )
            conv["turns"].append(turn)
            conv["updated_at"] = _utcnow().isoformat()
            # Update bookkeeping if missing fields are now provided.
            for fld, val in (
                ("merchant_id", merchant_id),
                ("customer_id", customer_id),
                ("trigger_id", trigger_id),
            ):
                if val and not conv.get(fld):
                    conv[fld] = val

    async def get_conversation(
        self, conversation_id: str
    ) -> dict[str, Any] | None:
        async with self._conversations_lock:
            conv = self._conversations.get(conversation_id)
            return dict(conv) if conv else None

    async def mark_conversation_ended(
        self, conversation_id: str, reason: str
    ) -> None:
        async with self._conversations_lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                conv["ended"] = True
                conv["end_reason"] = reason
                conv["updated_at"] = _utcnow().isoformat()

    async def increment_auto_reply_count(self, conversation_id: str) -> int:
        async with self._conversations_lock:
            conv = self._conversations.setdefault(
                conversation_id,
                {
                    "conversation_id": conversation_id,
                    "turns": [],
                    "auto_reply_count": 0,
                    "last_bot_body": None,
                    "ended": False,
                    "created_at": _utcnow().isoformat(),
                    "updated_at": _utcnow().isoformat(),
                },
            )
            conv["auto_reply_count"] += 1
            conv["updated_at"] = _utcnow().isoformat()
            return conv["auto_reply_count"]

    async def set_last_bot_body(
        self, conversation_id: str, body: str
    ) -> None:
        async with self._conversations_lock:
            conv = self._conversations.get(conversation_id)
            if conv is not None:
                conv["last_bot_body"] = body
                conv["updated_at"] = _utcnow().isoformat()

    async def all_conversations(self) -> list[dict[str, Any]]:
        async with self._conversations_lock:
            return [dict(c) for c in self._conversations.values()]

    # ─── suppression ─────────────────────────────────────────────────────────

    async def mark_suppression(
        self,
        merchant_id: str,
        suppression_key: str,
        ttl_days: int,
        trigger_id: str | None = None,
    ) -> None:
        expires = _utcnow() + timedelta(days=ttl_days)
        async with self._suppressions_lock:
            self._suppressions[(merchant_id, suppression_key)] = expires

    async def is_suppressed(
        self, merchant_id: str, suppression_key: str
    ) -> bool:
        async with self._suppressions_lock:
            expires = self._suppressions.get((merchant_id, suppression_key))
            if expires is None:
                return False
            if expires < _utcnow():
                self._suppressions.pop((merchant_id, suppression_key), None)
                return False
            return True

    # ─── blocked merchants ───────────────────────────────────────────────────

    async def mark_merchant_blocked(
        self, merchant_id: str, reason: str, ttl_days: int
    ) -> None:
        expires = _utcnow() + timedelta(days=ttl_days)
        async with self._blocked_lock:
            self._blocked[merchant_id] = expires

    async def is_merchant_blocked(self, merchant_id: str) -> bool:
        async with self._blocked_lock:
            expires = self._blocked.get(merchant_id)
            if expires is None:
                return False
            if expires < _utcnow():
                self._blocked.pop(merchant_id, None)
                return False
            return True

    # ─── bulk-load (used by WriteThroughStore.rehydrate) ─────────────────────

    async def bulk_load_contexts(self, rows: list[dict[str, Any]]) -> None:
        """Populate from Supabase rows. Bypasses version check."""
        async with self._contexts_lock:
            for row in rows:
                self._contexts[(row["scope"], row["context_id"])] = {
                    "version": row["version"],
                    "payload": row["payload"],
                    "delivered_at": row["delivered_at"],
                    "stored_at": _utcnow().isoformat(),
                }

    async def bulk_load_conversations(self, rows: list[dict[str, Any]]) -> None:
        async with self._conversations_lock:
            for row in rows:
                self._conversations[row["conversation_id"]] = {
                    "conversation_id": row["conversation_id"],
                    "merchant_id": row.get("merchant_id"),
                    "customer_id": row.get("customer_id"),
                    "trigger_id": row.get("trigger_id"),
                    "send_as": row.get("send_as", "vera"),
                    "turns": row.get("turns") or [],
                    "auto_reply_count": row.get("auto_reply_count") or 0,
                    "last_bot_body": row.get("last_bot_body"),
                    "ended": bool(row.get("ended")),
                    "end_reason": row.get("end_reason"),
                    "created_at": row.get("created_at") or _utcnow().isoformat(),
                    "updated_at": row.get("updated_at") or _utcnow().isoformat(),
                }

    async def bulk_load_suppressions(self, rows: list[dict[str, Any]]) -> None:
        async with self._suppressions_lock:
            for row in rows:
                expires = row["expires_at"]
                if isinstance(expires, str):
                    expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                self._suppressions[(row["merchant_id"], row["suppression_key"])] = expires

    async def bulk_load_blocks(self, rows: list[dict[str, Any]]) -> None:
        async with self._blocked_lock:
            for row in rows:
                expires = row["expires_at"]
                if isinstance(expires, str):
                    expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                self._blocked[row["merchant_id"]] = expires

    # ─── lifecycle ───────────────────────────────────────────────────────────

    async def startup(self) -> None:
        """Phase A+B: nothing to do. Phase C wires Supabase rehydrate via WriteThroughStore."""
        pass

    async def shutdown(self) -> None:
        pass
