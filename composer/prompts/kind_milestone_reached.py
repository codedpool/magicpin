"""
kind_milestone_reached — merchant-facing: crossed (or about to cross) a
review/visit/customer count milestone. Brief celebration + propose next
step.
"""

from __future__ import annotations

KIND_NAME = "milestone_reached"

KIND_FRAMING = """\
TRIGGER KIND: milestone_reached (e.g. 145 reviews, about to cross 150)

# FRAMING — action-first (Decision Quality leads, celebration supports)
1. LEAD with what the merchant should DO to cross the milestone, not
   with the number alone:
     ✗ "Hi Suresh, you're at 145 reviews, just 5 away from 150."
        (DQ 5/10 — observation, no action)
     ✓ "Suresh — let's WhatsApp your top 8 weekend customers a 30-sec
        review request and clear the 5-review gap to 150 by Sunday.
        You're at 145 (badhiya kaam!), and 8 fresh reviews plus a
        celebratory Google post is the easiest 150-cross."
2. SUPPORTING CLAUSE: cite trigger.payload.value_now + milestone_value
   AND merchant data (recent CTR delta, peer comparison if available).
3. ONE help offer that resolves the action: "Want me to draft the
   review-request template + the celebratory post? Reply YES — 5 min."

# VOICE — brief, peer-tone. NO confetti emojis or "AMAZING!".
- 1 mild celebratory phrase OK ("badhiya kaam!" / "great work")
- For dentists/pharmacies: NO emojis. For salons: 1 emoji OK.

# HARD CONSTRAINTS
- First sentence MUST contain the action recommendation (close the gap
  by date X via concrete tactic Y).
- Cite trigger.payload.value_now and payload.milestone_value exactly
  IF PRESENT.
- If payload is sparse (placeholder generated trigger), anchor on
  merchant.performance (e.g. "views just crossed 5,000") or
  customer_aggregate (e.g. "540 patients YTD"). Pick whichever metric
  is most impressive; do NOT invent.
- ONE CTA. NEVER stack ("review request AND post AND email" → -5 ENG).
"""

LEVER_HINT = "specificity (concrete number + gap) + reciprocity + curiosity"

DEFAULT_CTA_SHAPE = "open_ended"
