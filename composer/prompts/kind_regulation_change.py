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
- Source + deadline from trigger.payload IF PRESENT — never invent.
- If payload is sparse (placeholder generated trigger), anchor on
  category.regulatory_authorities[0] (e.g. "DCI" / "FSSAI" / "CDSCO")
  as a generic source-cite, recommend a generic "audit your operations
  before the next compliance cycle", and offer to draft the SOP update.
  Do NOT invent specific dates, dose numbers, or circular IDs.
- If you cannot quote a peer-cost number from contexts, drop the
  "₹X-Y" range entirely rather than fabricate.

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Reply YES — vendor quotes / SOP draft in 10 min."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = (
    "decision_quality (recommend a SPECIFIC action) + specificity "
    "(source + deadline + cost range) + reciprocity (one help offer) + "
    "single binary CTA. NEVER stack CTAs — multi-CTA caps engagement at 1/10."
)

DEFAULT_CTA_SHAPE = "binary_yes_no"
