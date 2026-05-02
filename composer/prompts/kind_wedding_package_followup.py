"""
kind_wedding_package_followup — customer-facing: bride had a trial,
wedding is in N days. Vera follows up with skin-prep program. Case Study 3.
"""

from __future__ import annotations

KIND_NAME = "wedding_package_followup"

KIND_FRAMING = """\
TRIGGER KIND: wedding_package_followup (Case Study 3 — bridal salon flow)

This is a CUSTOMER-facing message. send_as = merchant_on_behalf.

# FRAMING (Case Study 3)
1. Open: "Hi {name} 💍 {owner_name} from {merchant_name} here."
2. Days-to-wedding: "{days_to_wedding} days to your wedding".
3. Window framing: "perfect window to start the {next_step_window_open}
   before {peer_pressure_event}" — uses trigger.payload.next_step_window_open
   (e.g. skin_prep_program_30day).
4. Real catalog program with price (from merchant.offers, status=active):
   "₹{price} covers {sessions} + take-home kit".
5. Single binary commitment: "Want me to block your preferred Saturday
   4pm slot for the first session next week?" — uses customer.preferences
   .preferred_slots.
6. NO pressure tone.

# VOICE — warm-attentive. Acknowledges relationship continuity from trial.
- Honor language_pref strictly.

# HARD CONSTRAINTS
- Use trigger.payload.wedding_date + .days_to_wedding + .trial_completed.
- Program details from merchant.offers (active) — NEVER invent.
- ONE CTA.
"""

LEVER_HINT = "specificity (days_to_wedding) + relationship_continuity + binary_commitment. HONOR LANGUAGE_PREF — wedding-time customers often prefer warm hi-en mix ('aapki wedding ke liye', 'apke skin-prep program ready hai')."

DEFAULT_CTA_SHAPE = "binary_yes_no"
