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

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Reply YES — webinar link + calendar block in your WhatsApp in 30 sec."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = "specificity (org + date + credits) + reciprocity"

DEFAULT_CTA_SHAPE = "open_ended"
