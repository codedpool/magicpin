"""
kind_gbp_unverified — merchant-facing: their Google Business Profile is
unverified, capping discoverability. Vera frames as concrete uplift.
"""

from __future__ import annotations

KIND_NAME = "gbp_unverified"

KIND_FRAMING = """\
TRIGGER KIND: gbp_unverified (Google Business Profile not verified yet)

# FRAMING
1. Lead with the constraint: "your Google Business Profile is unverified,
   which caps how often you appear in local searches."
2. Cite the uplift: "verifying typically lifts visibility ~30%
   (trigger.payload.estimated_uplift_pct)."
3. State the path: "Verification = 5-min postcard request OR a 2-min
   phone call from Google" (use trigger.payload.verification_path).
4. RECIPROCITY: "Want me to walk you through the steps?" Single CTA.

# VOICE — operator-helper, NO marketing-speak. NO "boost your business!".
# HARD CONSTRAINTS
- Cite estimated_uplift_pct only if present in trigger.payload.
- ONE CTA.
"""

LEVER_HINT = "specificity (uplift % + concrete steps) + effort_externalization + reciprocity"

DEFAULT_CTA_SHAPE = "binary_yes_no"
