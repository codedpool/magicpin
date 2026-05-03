"""
kind_category_seasonal — merchant-facing: a seasonal demand shift hit the
category (e.g. summer ORS demand +40%). Vera flags + recommends shelf action.
"""

from __future__ import annotations

KIND_NAME = "category_seasonal"

KIND_FRAMING = """\
TRIGGER KIND: category_seasonal (e.g. summer ORS +40% / cold-cough -60%)

# FRAMING
1. Lead with the season-name + concrete demand shifts. Use trigger.payload.trends
   exactly (e.g. "ORS_demand_+40, sunscreen_demand_+38, antifungal_+45,
   cold_cough_-60").
2. Top 2-3 movers — NO need to enumerate all.
3. Concrete action: "shelf_action_recommended". Recommend stocking the
   risers + clearing slow movers.
4. Reciprocity: "Want me to draft a 3-bullet supplier note?" or
   "shelf-rotation checklist?". ONE CTA.

# VOICE — operator-helper. Specific. NO "amazing season ahead!".
# HARD CONSTRAINTS
- Use trigger.payload.trends exactly — NEVER invent percentage moves.
- ONE CTA.

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Reply YES — shelf-action + customer broadcast ready in 10 min."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = "specificity (concrete percentage moves) + reciprocity + actionable"

DEFAULT_CTA_SHAPE = "open_ended"
