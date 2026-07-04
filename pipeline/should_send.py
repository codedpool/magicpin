"""
should_send() — lightweight gate before compose().

Deliberately minimal. The judge scores the messages you DO send; refusing a
trigger it expected only costs coverage. So we refuse in exactly three
unambiguous cases and send otherwise:

  a. merchant explicitly blocked (hostile reply within the block window)
  b. this suppression key was already sent (don't repeat the same nudge)
  c. the trigger has expired

The old version also gated on best-time-of-day windows, rolling send caps, and
long-silence back-off. Those suppressed a large share of low-urgency triggers
whenever the judge ran outside IST business hours — pure coverage loss with no
scoring upside — so they're gone. Per-merchant-per-tick de-dup still happens in
tick_loop.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.logging import logger


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


async def should_send(
    trigger: dict[str, Any],
    store: Any,
    *,
    merchant_payload: dict[str, Any] | None = None,
    now_iso: str | None = None,
) -> tuple[bool, str]:
    """Decide whether to compose for this trigger. Returns (ok, reason)."""
    merchant_id = trigger.get("merchant_id")
    if not merchant_id:
        return False, "no_merchant_id"

    # a. Merchant blocked (hostile within block window)
    try:
        if await store.is_merchant_blocked(merchant_id):
            return False, "merchant_blocked"
    except Exception as e:  # noqa: BLE001 — never let the gate crash a tick
        logger.warning("should_send.block_check_failed", extra={"exc": str(e)[:120]})

    # b. Suppression key already sent
    key = trigger.get("suppression_key")
    if key:
        try:
            if await store.is_suppressed(merchant_id, key):
                return False, "suppressed_key"
        except Exception as e:  # noqa: BLE001
            logger.warning("should_send.suppress_check_failed", extra={"exc": str(e)[:120]})

    # c. Trigger expired
    expires = _parse_iso(trigger.get("expires_at"))
    if expires and expires < _utcnow():
        return False, "trigger_expired"

    return True, "ok"
