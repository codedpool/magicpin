"""
kind_festival_upcoming — merchant-facing: festival is in N days. Vera
proposes a category-correct festival action, not generic "celebrate!".
"""

from __future__ import annotations

KIND_NAME = "festival_upcoming"

KIND_FRAMING = """\
TRIGGER KIND: festival_upcoming (Diwali / Holi / Eid / Christmas / Pongal etc.)

# FRAMING
1. Lead with festival + days remaining: "Diwali is in 12 days".
2. CATEGORY-CORRECT play. Diwali for:
   - Salons → bridal/family party packages, bookings opening this week
   - Restaurants → corporate gift orders, mithai menus, reservation surge
   - Pharmacies → seasonal demand shifts (cracker injuries, ORS for
     family gatherings)
   - Gyms → "back to fitness in November" — soft retention angle
   - Dentists → wedding-season whitening peak (brief mentions Oct-Dec)
3. Reference category.seasonal_beats if a relevant entry exists.
4. ONE concrete artifact offer ("draft a Google post", "draft a
   WhatsApp broadcast", "schedule the menu").
5. Open CTA.

# HARD CONSTRAINTS
- Festival name + days_until from trigger.payload IF PRESENT.
- If payload is sparse (placeholder generated trigger), use the current
  major upcoming festival from category.seasonal_beats; if no beat
  matches, frame around "the upcoming festival window" generically. Do
  NOT invent a specific festival name or count of days.
- Don't push promotional/hype tone for clinical categories.
- ONE CTA.

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Reply YES — drafted festival post in your WhatsApp in 10 min."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = "specificity (festival + days) + reciprocity + category_fit. CONTRARIAN PLAY when warranted: if merchant data shows the obvious festival promo conflicts with their state (e.g. clinical category + Diwali = NOT a sales push), recommend AGAINST it explicitly."

DEFAULT_CTA_SHAPE = "open_ended"
