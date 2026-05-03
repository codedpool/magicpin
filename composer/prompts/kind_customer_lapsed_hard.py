"""
kind_customer_lapsed_hard — customer-facing: customer hasn't visited in
6mo+. Sent on behalf of merchant. NO-shame warmth.
"""

from __future__ import annotations

KIND_NAME = "customer_lapsed_hard"

KIND_FRAMING = """\
TRIGGER KIND: customer_lapsed_hard (Case Study 8 — gym-style lapse winback)

This is a CUSTOMER-facing message. send_as = merchant_on_behalf.

# VOICE — warm-operator. NO shame. NO "we miss you!" guilt-trip.
- Salute customer by name. Identify merchant + locality.
- "Happens to most customers at some point, no judgment" — explicit
  no-shame normalization.
- HONOR customer.identity.language_pref STRICTLY (hi-en mix etc.).

# FRAMING (Case Study 8)
1. Open: "Hi {customer_name} 👋 {owner_name} from {merchant_name} here."
2. Days/weeks: "It's been about {days_since_last_visit / 7} weeks".
3. NO-shame normalization: "happens to most members at some point, no judgment".
4. NEW SPECIFIC OFFERING tuned to their PAST goal (from
   trigger.payload.previous_focus) — e.g. "we've added a Tue/Thu HIIT class
   that fits weight-loss goals" if previous_focus was weight_loss.
5. Concrete trial: "Want me to hold a free trial spot for you next Tue,
   30 Apr? Reply YES — no commitment, no auto-charge."

# HARD CONSTRAINTS
- Use trigger.payload.previous_focus + .days_since_last_visit only.
- Match to a real new offering — use merchant.offers (active).
- ONE CTA. "no commitment, no auto-charge" line should appear when offering free trial.

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Reply YES — free trial slot held + no auto-charge confirmed in 30 sec."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = "warmth + no_judgment_framing + tailored_to_past_goal + low_friction_trial + 'no commitment, no auto-charge' phrasing (Case Study 8 winner — removes 2 barriers in one line). HONOR LANGUAGE_PREF strictly."

DEFAULT_CTA_SHAPE = "binary_yes_no"
