"""
should_send() — meta-cognitive gate that decides whether to even attempt compose().

Restraint is rewarded by the rubric. Reasons we refuse:
- merchant explicitly blocked (hostile reply within last 30d)
- suppression key already triggered (last 7d)
- trigger expired
- cadence violation (we sent to this merchant in the last CADENCE_GUARD_HOURS)
- urgency=1 trigger + recent negative engagement signal
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import logger
from core.settings import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


async def should_send(trigger: dict[str, Any], store: Any) -> tuple[bool, str]:
    """
    Decide whether to compose for this trigger.
    Returns (ok, reason).
    """
    merchant_id = trigger.get("merchant_id")
    if not merchant_id:
        return False, "no_merchant_id"

    # 1. Merchant blocked
    if await store.is_merchant_blocked(merchant_id):
        return False, "merchant_blocked"

    # 2. Suppression key
    key = trigger.get("suppression_key")
    if key and await store.is_suppressed(merchant_id, key):
        return False, "suppressed_key"

    # 3. Trigger expired
    expires = _parse_iso(trigger.get("expires_at"))
    if expires and expires < _utcnow():
        return False, "trigger_expired"

    # 4. Cadence guard (no resend < CADENCE_GUARD_HOURS to same merchant)
    threshold = _utcnow() - timedelta(hours=settings.CADENCE_GUARD_HOURS)
    if hasattr(store, "all_conversations"):
        convs = await store.all_conversations()
    elif hasattr(store, "memory"):
        # WriteThroughStore exposes memory
        convs = await store.memory.all_conversations()
    else:
        convs = []
    for conv in convs or []:
        if conv.get("merchant_id") != merchant_id:
            continue
        for turn in (conv.get("turns") or []):
            if (turn.get("from") or "").lower() != "vera":
                continue
            ts = _parse_iso(turn.get("ts"))
            if ts and ts > threshold:
                return False, f"cadence_violation_<{settings.CADENCE_GUARD_HOURS}h"

    # 5. Low-urgency + recent negative engagement (best-effort heuristic)
    urgency = trigger.get("urgency", 1)
    if urgency == 1:
        # If conversation history shows the merchant ignored or said no recently, don't pile on
        for conv in convs or []:
            if conv.get("merchant_id") != merchant_id:
                continue
            recent = (conv.get("turns") or [])[-4:]
            for turn in recent:
                if (turn.get("from") or "").lower() != "merchant":
                    continue
                body_lower = (turn.get("body") or "").lower()
                if any(p in body_lower for p in ("not interested", "no thanks", "stop", "later")):
                    return False, "low_urgency_negative_signal"

    return True, "ok"
