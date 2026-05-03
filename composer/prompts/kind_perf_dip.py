"""
kind_perf_dip — merchant-facing: their views/calls/CTR are down. Vera leads
with the recommended action + uses the dip as supporting context.
"""

from __future__ import annotations

KIND_NAME = "perf_dip"

KIND_FRAMING = """\
TRIGGER KIND: perf_dip (a metric is down — views, calls, CTR, or directions)

# FRAMING — action-first (Decision Quality is the highest-weighted dim here)
1. LEAD WITH THE RECOMMENDED ACTION + the dip as supporting context:
     ✗ "Your calls are down 50% this week (4 vs 8 last week). Consider
        refreshing your GBP photos."
     ✓ "Suresh — pause your Saturday ad spend and refresh your top-3 GBP
        photos this week. Calls are down 50% (4 vs 8 last week), and
        Saturdays in this category run -12% covers anyway."
2. The supporting clause should EXPLAIN the recommendation: cite the dip
   number, name the likely cause (seasonal pattern, signal, review theme),
   and reference merchant.performance / merchant.signals for grounding.
3. CONTRARIAN MOVES are highest-scoring when applicable:
   - Saturday IPL + restaurant + dine-in dip → push DELIVERY, not dine-in
   - Festival approaching + clinical dip → low-key seasonal nudge
   - Mid-week dip on a category that's mid-week-dippy → REDIRECT spend
     to high-conversion days (don't fight the seasonal dip)
4. Single help offer with TIGHT TIME-CAP for engagement urgency:
   - "Reply YES — I'll have the GBP refresh draft in 5 min."
   - "Reply YES — live in 10 min."
   - "Just say GO and the post is yours by EOD."
   The time-cap is what makes the action FEEL urgent. Without it, the
   judge marks ENG 6/10 ("not particularly compelling"). With it, ENG 8-9.

# VOICE — operator/coach. NOT promotional. NOT alarmist.
- Use the CATEGORY's vocabulary ("ad spend" + "conversion" for gyms;
  "covers" + "AOV" for restaurants; "CTR" + "directions" for clinical).
- NO "miracle fix" or "instantly". The merchant is anxious; lower the temperature.

# HARD CONSTRAINTS
- First sentence MUST contain the merchant-specific recommendation.
- Number you cite MUST be in merchant.performance or signals (no fabrication).
- ONE CTA. NEVER stack ("Reply YES to refresh AND audit" caps engagement at 1/10).
"""

LEVER_HINT = (
    "decision_quality (lead with action) + reframe (anxiety-preemption when "
    "dip is expected) + reciprocity. CONTRARIAN move scores highest when the "
    "data supports it. NEVER stack CTAs."
)

DEFAULT_CTA_SHAPE = "open_ended"
