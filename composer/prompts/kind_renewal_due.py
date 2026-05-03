"""
kind_renewal_due — merchant-facing: their magicpin subscription expires soon.
Vera reminds with a concrete value receipt, not just "renew now".
"""

from __future__ import annotations

KIND_NAME = "renewal_due"

KIND_FRAMING = """\
TRIGGER KIND: renewal_due (subscription expires in N days)

# FRAMING — action-first, quantified value as support
1. LEAD with the renewal recommendation + concrete value receipt:
     ✗ "Your Pro plan renews in 8 days. This cycle: 2,410 views, 18 calls.
        Want me to set up the renewal?"
     ✓ "Anjali — let me auto-renew your Pro plan before the 30 Apr cutoff.
        This cycle delivered 2,410 views + 18 calls + 9 leads against your
        ₹1,499 fee, and your CTR is up 5% MoM — uninterrupted continuity
        is the easy YES."
2. SUPPORTING CLAUSE: cite specific numbers from merchant.performance
   (views, calls, leads, CTR delta) + merchant.subscription.renewal_amount
   so the merchant SEES the value.
3. ONE help offer + binary close: "Reply YES to auto-renew" /
   "Reply HOLD if you want a 1-week pause".

# VOICE — operator-to-operator. NO panic. NO "limited time".
# HARD CONSTRAINTS
- First sentence MUST contain the auto-renew recommendation.
- Cite ONLY numbers from merchant.performance and merchant.subscription.
- ONE CTA. Binary preferred. NEVER stack ("Reply YES to renew AND ..." → -5).
"""

LEVER_HINT = (
    "decision_quality (lead with auto-renew action) + specificity (real "
    "performance numbers + renewal amount) + effort_externalization (\"let me\"). "
    "NEVER stack CTAs."
)

DEFAULT_CTA_SHAPE = "binary_yes_no"
