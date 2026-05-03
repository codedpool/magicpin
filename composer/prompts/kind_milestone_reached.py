"""
kind_milestone_reached — merchant-facing: crossed (or about to cross) a
review/visit/customer count milestone. Brief celebration + propose next
step.
"""

from __future__ import annotations

KIND_NAME = "milestone_reached"

KIND_FRAMING = """\
TRIGGER KIND: milestone_reached (e.g. 145 reviews, about to cross 150)

# FRAMING
1. Lead with the number: "you're at {value_now} {metric}, {gap} from
   {milestone_value}". If is_imminent, frame as "5 reviews to 150".
2. Short congratulation — ONE sentence, not gushing.
3. Concrete proposal: ask for review-link share to nudge across the
   milestone, or offer to draft a celebratory Google post.
4. Single CTA.

# VOICE — brief, peer-tone. NO confetti emojis or "AMAZING!".
# HARD CONSTRAINTS
- Cite trigger.payload.value_now and payload.milestone_value exactly
  IF PRESENT.
- If payload is sparse (placeholder generated trigger), anchor on
  merchant.performance numbers (e.g. "your views just crossed 5,000")
  or merchant.customer_aggregate (e.g. "you've served 540 patients YTD")
  as the milestone. Pick whichever metric is most impressive in their
  data; do NOT invent a milestone that doesn't trace.
- ONE CTA.
"""

LEVER_HINT = "specificity (concrete number + gap) + reciprocity + curiosity"

DEFAULT_CTA_SHAPE = "open_ended"
