"""
kind_default — used when trigger.kind has no hand-tuned prompt.

This is the strongest generic prompt — judges may invent novel kinds during
the live window, and this prompt must produce case-study-quality output for
ANY structurally-valid trigger.payload.
"""

from __future__ import annotations

KIND_NAME = "default"

KIND_FRAMING = """\
TRIGGER KIND: {kind} (no hand-tuned framing — reason from contexts)

# RULE 1 — DECISION-FIRST PHRASING (highest-weighted dimension)
The FIRST sentence MUST contain a SPECIFIC merchant-action recommendation.
Don't lead with the fact / stat / regulation. Lead with what they should DO.
Example transforms:
  ✗ "Your CTR dropped 12% this week" (stat-first, Decision Quality 3/10)
  ✓ "Suresh — pause Sat ad spend and refresh top-3 photos this week. CTR
     dropped 12%, and Saturdays in this category run -12% covers anyway."

# RULE 2 — INFER FROM SLUG / URGENCY / PAYLOAD
- trigger.kind slug families:
   *_dip = anxiety-pre-empt + reframe + recommend ONE move
   *_spike = momentum + double-down on the working channel
   *_due = reminder + the next concrete step
   *_alert = urgency + reciprocity (full workflow offer)
   *_planning = drafted artifact + binary commit
   *_followup = continuity + low-friction next step
- trigger.urgency 1-5: 5 = direct ("act before Y"), 1 = curious-ask
- trigger.payload — read every key. Numbers/dates/named entities are GOLD.
- merchant.signals — sharpen the recommendation with these.
- category.voice + peer_stats — set the tone.

# RULE 3 — ENGAGEMENT (the biggest gap in production Vera)
Single binary CTA. NEVER stack ("Reply YES to X and Y" caps engagement at 1/10).
Pick ONE help offer that resolves the WHOLE next step in low-friction language:
  ✓ "Want me to draft the X? Reply YES — live in 5 min."
  ✓ "What's the most-asked service this week? 1-line reply is enough."
"""

# kind_default leans on the levers production Vera most under-uses
# (challenge brief §10). Decision-first added because that's the rubric leader.
LEVER_HINT = (
    "decision_quality (lead with merchant-action) + asking_the_merchant + "
    "specificity (numbers + dates + sources from contexts) + single binary CTA. "
    "NEVER stack CTAs."
)

# Default CTA shape for kind_default
DEFAULT_CTA_SHAPE = "open_ended"
