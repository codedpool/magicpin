"""
kind_trial_followup — customer-facing: customer did a trial visit (gym /
salon / yoga). Vera follows up on behalf of merchant with next step.
"""

from __future__ import annotations

KIND_NAME = "trial_followup"

KIND_FRAMING = """\
TRIGGER KIND: trial_followup (customer attended a trial — yoga / gym / salon)

This is a CUSTOMER-facing message. send_as = merchant_on_behalf.

# FRAMING
1. Open: "Hi {name}, {owner_name} from {merchant_name} here. Hope you
   enjoyed the trial on {trial_date}."
2. Reference what they did (trigger.payload notes) + a SPECIFIC next-session
   slot from trigger.payload.next_session_options.
3. Soft commitment: no pressure on package; just confirm the next session
   to keep momentum.
4. Multi-choice slot CTA: "Reply 1 for {slot1}, 2 for {slot2}, or tell us
   a time."

# VOICE — warm + welcoming. NO sales-pressure.
- Customer hasn't committed yet; one good experience > one bad upsell.

# HARD CONSTRAINTS
- Use trigger.payload.trial_date + .next_session_options exactly.
- ONE CTA — multi-choice slot or open-ended.
"""

LEVER_HINT = "warmth + specificity (trial_date + slot) + low_friction. HONOR LANGUAGE_PREF — if 'hi-en mix', mix in 2-4 Hindi words ('apke liye', 'jab time mile', 'theek hai'). Pure English when language_pref says hi-en mix loses 2 points."

DEFAULT_CTA_SHAPE = "multi_choice_slot"
