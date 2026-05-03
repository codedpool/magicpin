"""
kind_customer_lapsed_soft — customer-facing: 3-6 months since last visit.
Like _hard but less effort + softer tone (they may just be busy).
"""

from __future__ import annotations

KIND_NAME = "customer_lapsed_soft"

KIND_FRAMING = """\
TRIGGER KIND: customer_lapsed_soft (3-6mo since last visit — same merchant)

This is a CUSTOMER-facing message. send_as = merchant_on_behalf.

# VOICE — warm + casual. Less effortful than lapsed_hard.
- Salute by name, identify merchant briefly.
- HONOR customer.identity.language_pref.

# FRAMING — soft check-in
1. Open: "Hi {name}, {merchant_name} here {emoji}."
2. Window: "It's been ~{months} months — just a quick check-in."
3. ONE soft ask — recall reminder OR a current relevant offer the customer
   would value. Reference services_received from relationship if applicable.
4. Open CTA — "Want to book a {service}?" or "Reply if you'd like to come back."

# HARD CONSTRAINTS
- Use customer.relationship.last_visit + .services_received.
- Use merchant.offers (status=active) for any price.
- ONE CTA.

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Reply YES — your slot blocked + reminder set in 30 sec."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = "warmth + low_friction + relationship_continuity. HONOR LANGUAGE_PREF — hi-en mix means natural Hindi tokens ('apke liye', 'theek hai', 'jab time mile'). Pure English when hi-en is preferred = -2 merchant_fit."

DEFAULT_CTA_SHAPE = "open_ended"
