"""
conversation_handlers.py — multi-turn tiebreaker entrypoint.

Per challenge-brief §7.4, this exports a `respond()` function the judge can
call offline (no HTTP) to evaluate multi-turn capability.

    from conversation_handlers import respond

    next_action = await respond(state, merchant_message)

Where `state` is a conversation-state dict like:
    {
      "conversation_id": "conv_xxx",
      "merchant_id": "m_001_drmeera_dentist_delhi",
      "customer_id": null,
      "category": {...},   # optional — full CategoryContext
      "merchant": {...},   # optional — full MerchantContext
      "customer": {...},   # optional
      "trigger": {...},    # the original trigger that started the conversation
      "turns": [
        {"from": "vera", "body": "...", "ts": "..."},
        {"from": "merchant", "body": "...", "ts": "..."},
        ...
      ],
      "auto_reply_count": 0,
      "ended": false
    }

Returns the same shape as POST /v1/reply:
  {"action": "send", "body": "...", "cta": "...", "rationale": "..."}
  {"action": "wait", "wait_seconds": 1800, "rationale": "..."}
  {"action": "end", "rationale": "..."}
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure imports resolve when called from any directory
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parent))


class _OfflineStore:
    """Minimal in-memory store wrapping a conversation-state dict.
    Provides the methods reply.handler.handle_reply expects."""

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.state.setdefault("turns", [])
        self.state.setdefault("auto_reply_count", 0)
        self.state.setdefault("ended", False)
        self.state.setdefault("end_reason", None)
        self.state.setdefault("last_bot_body", None)
        self.state.setdefault("send_as", "vera")
        self._blocked: dict[str, datetime] = {}

    async def append_conversation_turn(self, conversation_id, turn, **kwargs):
        self.state["turns"].append(turn)

    async def get_conversation(self, conversation_id):
        return dict(self.state)

    async def mark_conversation_ended(self, conversation_id, reason):
        self.state["ended"] = True
        self.state["end_reason"] = reason

    async def increment_auto_reply_count(self, conversation_id):
        self.state["auto_reply_count"] = (self.state.get("auto_reply_count") or 0) + 1
        return self.state["auto_reply_count"]

    async def set_last_bot_body(self, conversation_id, body):
        self.state["last_bot_body"] = body

    async def mark_merchant_blocked(self, merchant_id, reason, ttl_days):
        from datetime import timedelta
        self._blocked[merchant_id] = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    async def is_merchant_blocked(self, merchant_id):
        from datetime import datetime as dt
        exp = self._blocked.get(merchant_id)
        if exp is None:
            return False
        return exp > dt.now(timezone.utc)

    async def all_conversations(self):
        return [dict(self.state)]


_groq_started = False


async def _ensure_groq():
    global _groq_started
    if _groq_started:
        return
    from llm.groq_client import get_groq
    g = get_groq()
    await g.connect()
    _groq_started = True


async def respond(state: dict[str, Any], merchant_message: str) -> dict[str, Any]:
    """
    Given conversation_state + the merchant's latest message, produce the next
    action: send / wait / end. See module docstring for state shape.
    """
    await _ensure_groq()

    from reply.handler import handle_reply

    store = _OfflineStore(state)
    return await handle_reply(
        conversation_id=state.get("conversation_id", "conv_offline"),
        message=merchant_message,
        merchant_id=state.get("merchant_id"),
        customer_id=state.get("customer_id"),
        from_role=state.get("from_role", "merchant"),
        received_at=state.get("received_at") or datetime.now(timezone.utc).isoformat(),
        turn_number=len(state.get("turns", [])) + 1,
        store=store,
        category=state.get("category"),
        merchant=state.get("merchant"),
        customer=state.get("customer"),
        trigger=state.get("trigger"),
    )


def respond_sync(state: dict[str, Any], merchant_message: str) -> dict[str, Any]:
    """Synchronous wrapper for graders that don't want to await."""
    return asyncio.run(respond(state, merchant_message))


__all__ = ["respond", "respond_sync"]
