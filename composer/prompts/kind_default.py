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

For this trigger, infer the right framing from:
- trigger.kind itself (the slug tells you the family — e.g. *_dip = anxiety-pre-empt + reframe;
  *_spike = momentum + double-down; *_due = reminder + concrete next step;
  *_alert = urgency + reciprocity; *_planning = drafted artifact + binary commit;
  *_followup = continuity + low-friction next step)
- trigger.urgency (1-5; calibrate tone — 5 = direct, 1 = curious-ask)
- trigger.payload — read every key. Numbers, dates, named entities here are GOLD; use them.
- trigger.source (external: world events the merchant should know;
                  internal: things happening in their account)
- merchant.signals (interpreted hints) — sharpen the message with these
- category.voice + peer_stats — set the tone
"""

# How many compulsion levers to pick — kind_default leans social_proof + asking_merchant
# (production Vera's two biggest misses, per challenge brief §10)
LEVER_HINT = "social_proof + asking_the_merchant + specificity"

# Default CTA shape for kind_default
DEFAULT_CTA_SHAPE = "open_ended"
