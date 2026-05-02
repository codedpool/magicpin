"""
kind_regulation_change — merchant-facing: a regulator changed a rule
affecting this category. Vera flags compliance with deadline + concrete
audit step.
"""

from __future__ import annotations

KIND_NAME = "regulation_change"

KIND_FRAMING = """\
TRIGGER KIND: regulation_change (DCI / FSSAI / drug-license rule update)

# FRAMING
1. Source citation FIRST: "{regulator} circular {date}".
2. WHAT CHANGED — specific, factual: "max IOPA dose drops 1.5→1.0 mSv
   effective {deadline_iso}". Use trigger.payload.deadline_iso.
3. WHO IT AFFECTS — qualify: "E-speed film passes; D-speed does not. Digital
   RVG sensors unaffected." Surface from category.digest if available
   (trigger.payload.top_item_id resolves there).
4. CONCRETE AUDIT STEP — "audit your {equipment} before {deadline};
   document E-speed/RVG in your SOPs."
5. Reciprocity: "Want me to draft the SOP language?" / binary YES/NO.

# VOICE — clinical/legal-precise. NO alarm. NO "panic".
# HARD CONSTRAINTS
- Source + deadline cited from trigger.payload, not invented.
- ONE CTA.
"""

LEVER_HINT = "specificity (source + deadline + audit step) + reciprocity + urgency"

DEFAULT_CTA_SHAPE = "binary_yes_no"
