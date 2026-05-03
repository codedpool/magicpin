"""
kind_appointment_tomorrow — customer-facing: customer has an appointment
tomorrow. Reminder with prep instructions if applicable.
"""

from __future__ import annotations

KIND_NAME = "appointment_tomorrow"

KIND_FRAMING = """\
TRIGGER KIND: appointment_tomorrow (booking exists for tomorrow)

This is a CUSTOMER-facing message. send_as = merchant_on_behalf.

# FRAMING
1. Open: "Hi {name}, reminder — you have your appointment at {merchant_name},
   {locality} tomorrow." Use customer.identity.name + merchant.identity.
2. SERVICE / TIME — pick from these sources, in priority order:
   a. trigger.payload.service / .time / .appointment_at if present
   b. customer.relationship.services_received[-1] (most recent service)
      as a likely repeat
   c. If still nothing, use a generic "your appointment" without making
      up a specific time. Ask them to confirm the time you have.
3. CATEGORY-CORRECT prep instructions (skip if it'd require fabricated
   detail like a specific time):
   - Dental → "skip food 1h before X-rays if any are scheduled"
   - Salon → "come with hair washed if you're getting a haircut"
   - Gym → "bring water + ID for trial day"
   - Pharmacy → "bring prescription"
4. Confirm/reschedule CTA: "Reply CONFIRM to confirm, or RESCHEDULE if you
   need a new time."

# VOICE — warm + helpful. HONOR language_pref.
# HARD CONSTRAINTS
- Times/services from customer.relationship + trigger.payload — never invent
  a specific time/service if not present. Better to say "your appointment"
  and ask the customer to confirm than to invent "11 AM Wednesday".
- Markdown bold (**text**) does NOT render on WhatsApp — write plain text.
- ONE CTA — binary CONFIRM/RESCHEDULE.

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Reply CONFIRM to lock the slot, RESCHEDULE for new time — handled in 30 sec."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = "specificity (date + service) + helpful_prep_step + binary_commit. HONOR LANGUAGE_PREF strictly — hi-en mix needs Hindi tokens ('kal aapki appointment hai', 'time pehle confirm karein')."

DEFAULT_CTA_SHAPE = "binary_yes_no"
