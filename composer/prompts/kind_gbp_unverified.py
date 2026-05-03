"""
kind_gbp_unverified — merchant-facing: their Google Business Profile is
unverified. Vera leads with the verification action + the uplift as support.
"""

from __future__ import annotations

KIND_NAME = "gbp_unverified"

KIND_FRAMING = """\
TRIGGER KIND: gbp_unverified (Google Business Profile not verified yet)

# FRAMING — action-first (Decision Quality is the rubric leader)
1. LEAD with the recommended action + the uplift as supporting data:
     ✗ "Your GBP is unverified, which caps visibility. Verifying typically
        lifts visibility ~30%. Want me to walk you through the steps?"
     ✓ "Vikas — request the GBP postcard verification today (5-min form,
        Google mails it in 3-5 days). Your unverified profile is capping
        discoverability ~30% per typical Sector-8 GBP uplift, and your
        720 monthly views could be 940+."
2. SUPPORTING CLAUSE: cite trigger.payload.estimated_uplift_pct + the
   merchant's current views/calls so the projection is concrete.
3. ONE help offer: "Want me to send the postcard request link + a 2-line
   how-to in WhatsApp?" Single binary close.

# VOICE — operator-helper, NO marketing-speak. NO "boost your business!".
# HARD CONSTRAINTS
- First sentence MUST contain the verification action recommendation.
- Cite estimated_uplift_pct only if present in trigger.payload.
- Cite merchant.performance.views as the baseline for projections.
- ONE CTA. NEVER stack ("Reply YES to start verification AND audit your photos"
  caps engagement at 1/10).
"""

LEVER_HINT = (
    "decision_quality (lead with verification action) + specificity (uplift "
    "% + concrete projection from merchant's own views) + effort_externalization "
    "(\"5-min form\") + reciprocity (send the link + how-to)."
)

DEFAULT_CTA_SHAPE = "binary_yes_no"
