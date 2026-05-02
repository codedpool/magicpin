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
"""

LEVER_HINT = "asking_the_merchant (1.5×) + reciprocity + low_effort"

DEFAULT_CTA_SHAPE = "open_ended"
