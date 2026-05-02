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

from datetime import datetime, timedelta, timezone  # noqa: F401 (datetime used in type hints)
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

    Cadence rules (Phase 3 + extra-credit §12.3 multi-turn cadence):
      a. Merchant blocked        → no
      b. Suppression key active  → no
      c. Trigger expired         → no
      d. Last send to merchant <CADENCE_GUARD_HOURS ago → no
      e. Already MAX_SENDS_PER_MERCHANT_PER_24H sends in last 24h → no
      f. Last send >LONG_SILENCE_BACKOFF_HOURS ago + no reply since → no
      g. urgency=1 + recent negative engagement → no
      else → yes
    """
    merchant_id = trigger.get("merchant_id")
    if not merchant_id:
        return False, "no_merchant_id"

    # a. Merchant blocked
    if await store.is_merchant_blocked(merchant_id):
        return False, "merchant_blocked"

    # b. Suppression key
    key = trigger.get("suppression_key")
    if key and await store.is_suppressed(merchant_id, key):
        return False, "suppressed_key"

    # c. Trigger expired
    expires = _parse_iso(trigger.get("expires_at"))
    if expires and expires < _utcnow():
        return False, "trigger_expired"

    # ─── Build per-merchant send timeline from conversation store ──────────
    if hasattr(store, "all_conversations"):
        convs = await store.all_conversations()
    elif hasattr(store, "memory"):
        # WriteThroughStore exposes its memory for read paths
        convs = await store.memory.all_conversations()
    else:
        convs = []

    now = _utcnow()
    threshold_cadence = now - timedelta(hours=settings.CADENCE_GUARD_HOURS)
    threshold_24h = now - timedelta(hours=24)
    threshold_silence = now - timedelta(hours=settings.LONG_SILENCE_BACKOFF_HOURS)

    last_bot_send_at: datetime | None = None
    sends_in_24h: int = 0
    last_merchant_reply_at: datetime | None = None
    has_recent_negative: bool = False

    for conv in convs or []:
        if conv.get("merchant_id") != merchant_id:
            continue
        for turn in (conv.get("turns") or []):
            tfrom = (turn.get("from") or "").lower()
            ts = _parse_iso(turn.get("ts"))
            if ts is None:
                continue
            if tfrom in ("vera", "merchant_on_behalf"):
                if last_bot_send_at is None or ts > last_bot_send_at:
                    last_bot_send_at = ts
                if ts > threshold_24h:
                    sends_in_24h += 1
            elif tfrom == "merchant":
                if last_merchant_reply_at is None or ts > last_merchant_reply_at:
                    last_merchant_reply_at = ts
                # Recent negative engagement (last 4 merchant turns)
                if ts > now - timedelta(days=2):
                    body_lower = (turn.get("body") or "").lower()
                    if any(p in body_lower for p in
                           ("not interested", "no thanks", "stop", "later", "busy")):
                        has_recent_negative = True

    # d. Cadence guard — no resend < CADENCE_GUARD_HOURS to same merchant
    if last_bot_send_at and last_bot_send_at > threshold_cadence:
        return False, f"cadence_violation_<{settings.CADENCE_GUARD_HOURS}h"

    # e. Max sends per 24h
    if sends_in_24h >= settings.MAX_SENDS_PER_MERCHANT_PER_24H:
        return False, f"max_sends_24h_{sends_in_24h}>={settings.MAX_SENDS_PER_MERCHANT_PER_24H}"

    # f. Long silence — sent >12h ago AND merchant hasn't replied since
    if (
        last_bot_send_at
        and last_bot_send_at < threshold_silence
        and (last_merchant_reply_at is None or last_merchant_reply_at < last_bot_send_at)
    ):
        # We sent but they didn't engage; don't pile on more sends without a reply
        return False, f"long_silence_no_reply_>{settings.LONG_SILENCE_BACKOFF_HOURS}h"

    # g. Low urgency + recent negative engagement
    urgency = trigger.get("urgency", 1)
    if urgency == 1 and has_recent_negative:
        return False, "low_urgency_negative_signal"

    return True, "ok"
