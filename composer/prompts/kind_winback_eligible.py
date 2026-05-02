"""
kind_winback_eligible — merchant-facing: their subscription expired, they
saw a perf dip, AND lapsed_customers > 0. Vera proposes winback campaign.
"""

from __future__ import annotations

KIND_NAME = "winback_eligible"

KIND_FRAMING = """\
TRIGGER KIND: winback_eligible (subscription lapsed + perf dip + lapsed customers)

# FRAMING
1. Diagnostic: "Since your subscription expired {days_since_expiry} days ago,
   {perf_dip_pct}% drop and {lapsed_customers_added_since_expiry} customers
   went lapsed."
2. Reframe as OPPORTUNITY — winback campaign is highest ROI.
3. Concrete proposal: "Reactivate Pro for ₹{plan_price} and I'll auto-trigger
   a winback push for the {N} lapsed customers — typically converts 8-12%."
4. Binary CTA — "Reply YES to reactivate" / "Reply HOLD to pause".

# VOICE — operator-coach. Diagnostic + opportunity, not guilt.
# HARD CONSTRAINTS
- Cite trigger.payload.days_since_expiry + .perf_dip_pct +
  .lapsed_customers_added_since_expiry exactly.
- 8-12% conversion typical is industry-standard, OK to cite.
- ONE binary CTA.
"""

LEVER_HINT = "diagnostic_specificity + opportunity_framing + binary_commit"

DEFAULT_CTA_SHAPE = "binary_yes_no"
