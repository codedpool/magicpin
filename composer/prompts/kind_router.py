"""
kind_router — maps trigger.kind to the right prompt module.

Phase E ships kind_default + research_digest + recall_due. Phase K expands to
all 24 known kinds. Unknown kinds always fall back to kind_default — which is
the strongest generic prompt, not a fallback.
"""

from __future__ import annotations

from typing import Any

from composer.prompts import (
    kind_chronic_refill_due,
    kind_default,
    kind_recall_due,
    kind_research_digest,
)


# Maps trigger.kind → prompt module
_REGISTRY: dict[str, Any] = {
    "research_digest": kind_research_digest,
    "recall_due": kind_recall_due,
    "chronic_refill_due": kind_chronic_refill_due,
    # Phase K (later) populates the rest:
    # "perf_dip", "perf_spike", "renewal_due", "festival_upcoming",
    # "curious_ask_due", "ipl_match_today", "review_theme_emerged",
    # "milestone_reached", "competitor_opened", "supply_alert",
    # "gbp_unverified", "regulation_change", "cde_opportunity",
    # "dormant_with_vera", "customer_lapsed_hard", "trial_followup",
    # "wedding_package_followup", "active_planning_intent",
    # "seasonal_perf_dip", "category_seasonal", "winback_eligible",
    # ... but kind_default already handles all of these competently.
}


def route(kind: str) -> Any:
    """Return the prompt module for `kind` or kind_default if unknown."""
    return _REGISTRY.get(kind, kind_default)


def is_hand_tuned(kind: str) -> bool:
    """True if this kind has a hand-tuned prompt (not default)."""
    return kind in _REGISTRY
