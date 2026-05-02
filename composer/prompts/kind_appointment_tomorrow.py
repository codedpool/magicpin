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
1. Open: "Hi {name}, reminder — you have {service} at {merchant_name},
   {locality} tomorrow at {time}." Use customer.relationship +
   trigger.payload.
2. CATEGORY-CORRECT prep instructions:
   - Dental → "skip food 1h before X-rays if scheduled"
   - Salon → "come with hair washed if you're getting a haircut"
   - Gym → "bring water + ID for trial day"
   - Pharmacy → "bring prescription"
3. Confirm/reschedule CTA: "Reply CONFIRM to confirm, or RESCHEDULE if you
   need a new time."

# VOICE — warm + helpful. HONOR language_pref.
# HARD CONSTRAINTS
- All times/services from customer.relationship + trigger.payload.
- ONE CTA — binary CONFIRM/RESCHEDULE.
"""

LEVER_HINT = "specificity (date + service) + helpful_prep_step + binary_commit"

DEFAULT_CTA_SHAPE = "binary_yes_no"
