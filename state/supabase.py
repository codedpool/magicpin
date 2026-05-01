"""
SupabaseStore — durable Postgres backing for state via asyncpg.

Conforms to the StateStore protocol. Reads (used only on rehydrate) are bulk
selects; writes are UPSERTs so re-applied writes are idempotent.

Connection: Session pooler (`aws-1-ap-northeast-1.pooler.supabase.com:5432`)
because Supabase's direct hostname is IPv6-only on free tier.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from core.logging import logger
from core.settings import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s: str | datetime) -> datetime:
    """Parse an ISO 8601 string to an aware datetime. Handles trailing 'Z'."""
    if isinstance(s, datetime):
        if s.tzinfo is None:
            return s.replace(tzinfo=timezone.utc)
        return s
    s = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SupabaseStore:
    """Async Postgres store backing the InMemory cache."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Open the asyncpg pool. Idempotent."""
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(
            host=settings.SUPABASE_DB_HOST,
            port=settings.SUPABASE_DB_PORT,
            user=settings.SUPABASE_DB_USER,
            password=settings.SUPABASE_DB_PASSWORD,
            database=settings.SUPABASE_DB_NAME,
            ssl="require",
            min_size=1,
            max_size=5,
            command_timeout=10,
            init=self._init_connection,
            statement_cache_size=0,  # required for Supabase pooler in transaction mode; harmless in session mode
        )
        logger.info("supabase.pool_opened")

    @staticmethod
    async def _init_connection(conn: asyncpg.Connection) -> None:
        # asyncpg's default jsonb codec returns/accepts strings — we want dicts
        await conn.set_type_codec(
            "jsonb",
            encoder=lambda v: json.dumps(v),
            decoder=lambda v: json.loads(v),
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "json",
            encoder=lambda v: json.dumps(v),
            decoder=lambda v: json.loads(v),
            schema="pg_catalog",
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("supabase.pool_closed")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("SupabaseStore not connected. Call connect() first.")
        return self._pool

    # ─── contexts ────────────────────────────────────────────────────────────

    async def upsert_context(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        delivered_at: str,
    ) -> None:
        """Idempotent upsert. The InMemory store has already validated version."""
        delivered_dt = _parse_iso(delivered_at)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO contexts (scope, context_id, version, payload, delivered_at, updated_at)
                VALUES ($1, $2, $3, $4::jsonb, $5, NOW())
                ON CONFLICT (scope, context_id) DO UPDATE SET
                    version = EXCLUDED.version,
                    payload = EXCLUDED.payload,
                    delivered_at = EXCLUDED.delivered_at,
                    updated_at = NOW()
                WHERE contexts.version < EXCLUDED.version
                """,
                scope, context_id, version, payload, delivered_dt,
            )

    async def fetch_all_contexts(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT scope, context_id, version, payload, delivered_at FROM contexts"
            )
        return [
            {
                "scope": r["scope"],
                "context_id": r["context_id"],
                "version": r["version"],
                "payload": r["payload"],
                "delivered_at": r["delivered_at"].isoformat()
                if hasattr(r["delivered_at"], "isoformat")
                else str(r["delivered_at"]),
            }
            for r in rows
        ]

    # ─── conversations ───────────────────────────────────────────────────────

    async def upsert_conversation(
        self,
        conversation_id: str,
        merchant_id: str | None,
        customer_id: str | None,
        trigger_id: str | None,
        send_as: str,
        turns: list[dict[str, Any]],
        auto_reply_count: int,
        last_bot_body: str | None,
        ended: bool,
        end_reason: str | None,
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (
                    conversation_id, merchant_id, customer_id, trigger_id,
                    send_as, turns, auto_reply_count, last_bot_body, ended, end_reason,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, NOW(), NOW())
                ON CONFLICT (conversation_id) DO UPDATE SET
                    merchant_id = COALESCE(EXCLUDED.merchant_id, conversations.merchant_id),
                    customer_id = COALESCE(EXCLUDED.customer_id, conversations.customer_id),
                    trigger_id = COALESCE(EXCLUDED.trigger_id, conversations.trigger_id),
                    send_as = EXCLUDED.send_as,
                    turns = EXCLUDED.turns,
                    auto_reply_count = EXCLUDED.auto_reply_count,
                    last_bot_body = EXCLUDED.last_bot_body,
                    ended = EXCLUDED.ended,
                    end_reason = EXCLUDED.end_reason,
                    updated_at = NOW()
                """,
                conversation_id, merchant_id, customer_id, trigger_id,
                send_as, turns, auto_reply_count, last_bot_body, ended, end_reason,
            )

    async def fetch_all_conversations(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT conversation_id, merchant_id, customer_id, trigger_id,
                       send_as, turns, auto_reply_count, last_bot_body, ended, end_reason,
                       created_at, updated_at
                FROM conversations
                """
            )
        result = []
        for r in rows:
            result.append({
                "conversation_id": r["conversation_id"],
                "merchant_id": r["merchant_id"],
                "customer_id": r["customer_id"],
                "trigger_id": r["trigger_id"],
                "send_as": r["send_as"],
                "turns": r["turns"] or [],
                "auto_reply_count": r["auto_reply_count"] or 0,
                "last_bot_body": r["last_bot_body"],
                "ended": bool(r["ended"]),
                "end_reason": r["end_reason"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            })
        return result

    # ─── suppressions ────────────────────────────────────────────────────────

    async def upsert_suppression(
        self,
        merchant_id: str,
        suppression_key: str,
        ttl_days: int,
        trigger_id: str | None,
    ) -> None:
        expires = _utcnow() + timedelta(days=ttl_days)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO suppressions (merchant_id, suppression_key, trigger_id, expires_at, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (merchant_id, suppression_key) DO UPDATE SET
                    expires_at = EXCLUDED.expires_at,
                    trigger_id = COALESCE(EXCLUDED.trigger_id, suppressions.trigger_id)
                """,
                merchant_id, suppression_key, trigger_id, expires,
            )

    async def fetch_active_suppressions(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT merchant_id, suppression_key, expires_at FROM suppressions WHERE expires_at > NOW()"
            )
        return [
            {
                "merchant_id": r["merchant_id"],
                "suppression_key": r["suppression_key"],
                "expires_at": r["expires_at"],
            }
            for r in rows
        ]

    # ─── blocked merchants ───────────────────────────────────────────────────

    async def upsert_blocked_merchant(
        self,
        merchant_id: str,
        reason: str,
        ttl_days: int,
    ) -> None:
        expires = _utcnow() + timedelta(days=ttl_days)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO blocked_merchants (merchant_id, reason, expires_at, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (merchant_id) DO UPDATE SET
                    reason = EXCLUDED.reason,
                    expires_at = EXCLUDED.expires_at
                """,
                merchant_id, reason, expires,
            )

    async def fetch_active_blocks(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT merchant_id, reason, expires_at FROM blocked_merchants WHERE expires_at > NOW()"
            )
        return [
            {
                "merchant_id": r["merchant_id"],
                "reason": r["reason"],
                "expires_at": r["expires_at"],
            }
            for r in rows
        ]

    # ─── housekeeping ────────────────────────────────────────────────────────

    async def cleanup_expired(self) -> tuple[int, int]:
        """Delete expired suppressions + blocks. Returns (suppressions, blocks) deleted."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM cleanup_expired_state()")
        return (row["suppressions_deleted"], row["blocks_deleted"]) if row else (0, 0)
