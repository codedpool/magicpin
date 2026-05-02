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
- Days_until from trigger.payload, not invented.
- Don't push promotional/hype tone for clinical categories.
- ONE CTA.
"""

LEVER_HINT = "specificity (festival + days) + reciprocity + category fit"

DEFAULT_CTA_SHAPE = "open_ended"
