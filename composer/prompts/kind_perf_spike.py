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
"""

LEVER_HINT = "specificity + reciprocity + curiosity. ASKING-THE-MERCHANT: 'what do you think drove the spike?' is high-value — gets domain knowledge from owner + uses production-Vera's biggest-miss lever."

DEFAULT_CTA_SHAPE = "open_ended"
