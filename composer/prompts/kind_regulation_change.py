"""
kind_regulation_change — merchant-facing: a regulator changed a rule
affecting this category. Vera flags compliance with deadline + concrete
audit step.
"""

from __future__ import annotations

KIND_NAME = "regulation_change"

KIND_FRAMING = """\
TRIGGER KIND: regulation_change (DCI / FSSAI / drug-license rule update)

# FRAMING — operator-to-operator, NOT regulator-voice
1. LEAD WITH WHAT THIS MERCHANT MUST DO. Not "circular X mandates Y" —
   "Dr. Meera, your D-speed X-ray unit needs replacement by Dec 15".
   This is the SPECIFIC merchant action; everything else supports it.
2. SOURCE + KEY NUMBER inline — single short clause: "(DCI 2026-11-04,
   IOPA cap 1.5→1.0 mSv)". One parenthetical, not a paragraph.
3. WHAT'S THE EASY PATH — "RVG digital sensors are exempt; most peers
   upgrade for ~₹15-25K and stay compliant for years". Concrete cost
   range + peer comparison if the data is in contexts.
4. ONE help offer that resolves the ENTIRE problem with low effort:
   "Want me to pull 2 RVG vendor quotes for clinics your size?"
5. Single binary close: "Reply YES" — no stacking, no compound asks.

# VOICE — clinical-peer (one operator to another), not regulatory.
# HARD CONSTRAINTS
- ONE merchant-specific action recommendation in the FIRST sentence.
- NEVER chain CTAs ("Reply YES to X AND confirm Y" = -5 engagement).
- Source + deadline from trigger.payload — never invent.
- If you cannot quote a peer-cost number from contexts, drop the
  "₹X-Y" range entirely rather than fabricate.
"""

LEVER_HINT = (
    "decision_quality (recommend a SPECIFIC action) + specificity "
    "(source + deadline + cost range) + reciprocity (one help offer) + "
    "single binary CTA. NEVER stack CTAs — multi-CTA caps engagement at 1/10."
)

DEFAULT_CTA_SHAPE = "binary_yes_no"
