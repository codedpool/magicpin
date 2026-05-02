"""
Best-time-to-text — option C: category-default window + learned override.

When deciding whether to send a low-urgency trigger to a merchant, also
check whether "now" (simulated time from /v1/tick body.now) is within a
sensible business-hours window for that merchant's category.

Strategy:
A. Category-default IST window (e.g. dentists 9-18, restaurants 11-22).
B. Once we have ≥2 historical reply timestamps from this merchant, narrow
   to ±2 hours around the median reply hour (their actual active window).
C. Combine: A is the cold-start; B overrides once we have data.

Only enforced for urgency ≤ 2. Higher-urgency triggers (perf_dip,
renewal_due, supply_alert, regulation_change, active_planning_intent)
always send regardless of time.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


# IST timezone (UTC+5:30) — Indian merchants
IST = timezone(timedelta(hours=5, minutes=30))


# (start_hour_inclusive, end_hour_exclusive) in local IST 24h time
CATEGORY_WINDOWS: dict[str, tuple[int, int]] = {
    "dentists":    (9, 18),   # clinical office hours
    "restaurants": (11, 22),  # lunch + dinner peak
    "salons":      (10, 20),  # operating hours
    "gyms":        (6, 22),   # early morning + evening
    "pharmacies":  (8, 22),   # long hours
}
# Default for unknown categories — broad business hours
DEFAULT_WINDOW: tuple[int, int] = (9, 21)


# Only check best-time for these urgency levels (low-priority sends).
# Urgency 3+ (performance dips, renewals, supply alerts, regulation
# changes, active planning) always sends regardless of time.
ENFORCE_FOR_URGENCY_AT_OR_BELOW: int = 2


# Need ≥ this many historical merchant reply hours before we trust the
# learned override (option B kicks in).
MIN_LEARNED_DATA_POINTS: int = 2


def parse_to_ist_hour(now_iso: str | None) -> int | None:
    """Parse now_iso (any TZ) → IST hour (0-23). None if unparseable."""
    if not now_iso:
        return None
    try:
        s = now_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).hour


def get_merchant_reply_hours(
    conversations: list[dict[str, Any]], merchant_id: str
) -> list[int]:
    """Collect IST hours-of-day at which this merchant has REPLIED in the past."""
    hours: list[int] = []
    for conv in conversations or []:
        if conv.get("merchant_id") != merchant_id:
            continue
        for turn in (conv.get("turns") or []):
            if (turn.get("from") or "").lower() != "merchant":
                continue
            ts_str = turn.get("ts")
            if not ts_str:
                continue
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                hours.append(dt.astimezone(IST).hour)
            except (ValueError, TypeError):
                continue
    return hours


def median(values: list[int]) -> int:
    if not values:
        return 12
    s = sorted(values)
    return s[len(s) // 2]


def is_within_best_window(
    now_iso: str | None,
    category_slug: str | None,
    learned_reply_hours: list[int] | None = None,
) -> tuple[bool, str]:
    """
    Returns (within_window, reason_string).
    If now_iso unparseable, returns (True, "no_now") — don't block.
    """
    hour = parse_to_ist_hour(now_iso)
    if hour is None:
        return True, "no_parseable_now"

    # B: learned override
    if learned_reply_hours and len(learned_reply_hours) >= MIN_LEARNED_DATA_POINTS:
        center = median(learned_reply_hours)
        # Allow ±2 hours, with wraparound (e.g. center=23 allows 21,22,23,0,1)
        for offset in range(-2, 3):
            candidate = (center + offset) % 24
            if hour == candidate:
                return True, f"learned_window_center={center}_hit"
        return False, f"outside_learned_window_center={center}_now={hour}"

    # A: category-default
    start, end = CATEGORY_WINDOWS.get(category_slug or "", DEFAULT_WINDOW)
    if start <= hour < end:
        return True, f"category_window_{start}-{end}_hit"
    return False, f"outside_category_window_{start}-{end}_now={hour}"


def should_check_best_time(trigger: dict[str, Any]) -> bool:
    """Only enforce best-time for low-urgency triggers."""
    urgency = trigger.get("urgency", 1)
    try:
        return int(urgency) <= ENFORCE_FOR_URGENCY_AT_OR_BELOW
    except (ValueError, TypeError):
        return True
