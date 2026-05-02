"""
kind_curious_ask_due — merchant-facing: weekly curiosity question to
trigger engagement. Production Vera under-uses this lever; high priority.
"""

from __future__ import annotations

KIND_NAME = "curious_ask_due"

KIND_FRAMING = """\
TRIGGER KIND: curious_ask_due (weekly cadence — ask the merchant a question)

# FRAMING (Case Study 4 pattern)
1. Brief greeting using owner first name.
2. Ask ONE specific question about THEIR business this week (most-asked
   service, best-selling dish, hardest customer this week, treatment trend
   they're noticing). Pull the question shape from trigger.payload.ask_template
   if present.
3. Reciprocate: offer to turn the answer into a concrete artifact (Google
   post, WhatsApp draft, menu update, social caption).
4. Time-cap the ask: "5-min check" or "1-line reply is enough".

# VOICE — peer-to-peer, casual. NOT formal.
- "Hi {owner_name}!" / "Quick check, {owner_name} —" / "Curious, {owner_name}:"
- This is the lever production Vera most under-uses; lean into it.

# HARD CONSTRAINTS
- ONE question. ONE CTA.
- Don't make assumptions about what they'll say.
- Don't chain multiple asks ("what's popular AND who's your top customer AND...")

# OVERRIDE — IMPORTANT
This kind is the EXCEPTION to the system_base "2-anchors" rule. The whole
point is to ask a question — fabricating peer/percentage/count numbers to
satisfy the rule WILL fail validation. Anchor with:
  - Owner first name (already required)
  - Merchant name + locality (e.g. "Studio11 in Kapra")
  - The week-window framing ("this week", "last 7 days")
That is sufficient — no numeric peer stat needed. NEVER invent percentages
like "121%" or "+45%". If you cannot quote a number from the merchant's
own performance object verbatim, OMIT the number entirely.
"""

LEVER_HINT = "asking_the_merchant (1.5×) + reciprocity + low_effort. THIS IS THE LEVER PRODUCTION VERA MOST UNDER-USES — make the ask CRISP and SPECIFIC, not generic. 'What's been most-asked this week?' beats 'How are things?'."

DEFAULT_CTA_SHAPE = "open_ended"
