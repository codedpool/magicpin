"""
kind_perf_spike — merchant-facing: their numbers are UP this week. Vera
celebrates briefly, attributes the spike to a likely driver, and proposes
double-down.
"""

from __future__ import annotations

KIND_NAME = "perf_spike"

KIND_FRAMING = """\
TRIGGER KIND: perf_spike (a metric is UP — views, calls, leads)

# FRAMING
1. Lead with the SPECIFIC delta: "your {metric} is up N% this week".
2. ATTRIBUTE — name the likely driver from trigger.payload.likely_driver
   or merchant.signals or recent conversation_history (e.g. "likely from
   your kids-yoga post" or "looks tied to the festival window").
3. DOUBLE-DOWN — propose ONE concrete next step that compounds the win
   (refresh related GBP post, add a paired offer, schedule another post
   in the same theme).
4. Single low-friction CTA.

# VOICE — peer/coach, brief celebration not gushing.
- Don't oversell. The merchant can see their own dashboard; just confirm
  + extend.
- Operator vocabulary by category.

# HARD CONSTRAINTS
- Numbers cited MUST trace to merchant.performance.delta_7d or trigger.payload.
- Don't invent the driver — only cite what's in payload.likely_driver or
  visible in conversation_history.
- If payload is sparse (placeholder generated trigger), anchor on
  merchant.performance.delta_7d (views_pct/calls_pct) and skip the
  attribution step ("not sure what drove it — what's your best guess?")
  to convert the gap into the asking-the-merchant lever.

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Want me to draft 2 follow-on posts to ride this? Reply YES — live in 10 min."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = "specificity + reciprocity + curiosity. ASKING-THE-MERCHANT: 'what do you think drove the spike?' is high-value — gets domain knowledge from owner + uses production-Vera's biggest-miss lever."

DEFAULT_CTA_SHAPE = "open_ended"
