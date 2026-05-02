"""
kind_router — maps trigger.kind to the right prompt module.

Phase E ships kind_default + research_digest + recall_due. Phase K expands to
all 24 known kinds. Unknown kinds always fall back to kind_default — which is
the strongest generic prompt, not a fallback.
"""

from __future__ import annotations

from typing import Any

from composer.prompts import (
    kind_active_planning_intent,
    kind_appointment_tomorrow,
    kind_category_seasonal,
    kind_cde_opportunity,
    kind_chronic_refill_due,
    kind_competitor_opened,
    kind_curious_ask_due,
    kind_customer_lapsed_hard,
    kind_customer_lapsed_soft,
    kind_default,
    kind_dormant_with_vera,
    kind_festival_upcoming,
    kind_gbp_unverified,
    kind_ipl_match_today,
    kind_milestone_reached,
    kind_perf_dip,
    kind_perf_spike,
    kind_recall_due,
    kind_regulation_change,
    kind_renewal_due,
    kind_research_digest,
    kind_review_theme_emerged,
    kind_seasonal_perf_dip,
    kind_supply_alert,
    kind_trial_followup,
    kind_wedding_package_followup,
    kind_winback_eligible,
)


# Maps trigger.kind → prompt module. Unknown kinds → kind_default (which is
# a strong generic prompt, not a fallback stub).
_REGISTRY: dict[str, Any] = {
    "research_digest": kind_research_digest,
    "recall_due": kind_recall_due,
    "chronic_refill_due": kind_chronic_refill_due,
    "perf_dip": kind_perf_dip,
    "perf_spike": kind_perf_spike,
    "seasonal_perf_dip": kind_seasonal_perf_dip,
    "renewal_due": kind_renewal_due,
    "festival_upcoming": kind_festival_upcoming,
    "curious_ask_due": kind_curious_ask_due,
    "ipl_match_today": kind_ipl_match_today,
    "review_theme_emerged": kind_review_theme_emerged,
    "milestone_reached": kind_milestone_reached,
    "competitor_opened": kind_competitor_opened,
    "supply_alert": kind_supply_alert,
    "gbp_unverified": kind_gbp_unverified,
    "regulation_change": kind_regulation_change,
    "cde_opportunity": kind_cde_opportunity,
    "dormant_with_vera": kind_dormant_with_vera,
    "customer_lapsed_hard": kind_customer_lapsed_hard,
    "customer_lapsed_soft": kind_customer_lapsed_soft,
    "trial_followup": kind_trial_followup,
    "wedding_package_followup": kind_wedding_package_followup,
    "active_planning_intent": kind_active_planning_intent,
    "category_seasonal": kind_category_seasonal,
    "winback_eligible": kind_winback_eligible,
    "appointment_tomorrow": kind_appointment_tomorrow,
}


def route(kind: str) -> Any:
    """Return the prompt module for `kind` or kind_default if unknown."""
    return _REGISTRY.get(kind, kind_default)


def is_hand_tuned(kind: str) -> bool:
    """True if this kind has a hand-tuned prompt (not default)."""
    return kind in _REGISTRY
