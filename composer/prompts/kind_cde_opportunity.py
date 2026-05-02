"""
kind_cde_opportunity — merchant-facing: continuing-education event for
this category (webinar, workshop). Brief surface, low pressure.
"""

from __future__ import annotations

KIND_NAME = "cde_opportunity"

KIND_FRAMING = """\
TRIGGER KIND: cde_opportunity (CDE webinar / workshop / conference)

# FRAMING
1. Source + date: "{org} webinar tomorrow ({date_local}, {credits} credits)".
2. Topic: surface from category.digest (trigger.payload.digest_item_id).
3. Cost: "free for members; ₹{fee} for non-members".
4. Brief, no pressure — "Worth checking? Link in your inbox already." or
   single open ask "Want me to send the link?".

# VOICE — peer-clinical, brief.
# HARD CONSTRAINTS
- Cite digest_item details exactly.
- ONE CTA. Pressure-low.
"""

LEVER_HINT = "specificity (org + date + credits) + reciprocity"

DEFAULT_CTA_SHAPE = "open_ended"
