"""
kind_seasonal_perf_dip — merchant-facing: dip is expected/seasonal (Case
Study 7). Anxiety-pre-empt + reframe.
"""

from __future__ import annotations

KIND_NAME = "seasonal_perf_dip"

KIND_FRAMING = """\
TRIGGER KIND: seasonal_perf_dip (Case Study 7 — gym example)

# FRAMING (Case Study 7)
1. Lead with the SPECIFIC dip: "your views are down {delta_pct}% this week"
   (from trigger.payload.delta_pct).
2. ANXIETY PRE-EMPT IMMEDIATELY: "but I want to flag this is the normal
   {season_note} (every {category} sees -25 to -35% in this window)" —
   uses trigger.payload.season_note + category.peer_stats.
3. REFRAME — pivot to OPPORTUNITY: "Action: skip ad spend now, save for
   {high_conversion_window} when conversion is 2x."
4. Specific next move with merchant.customer_aggregate (e.g. "focus
   retention on your {N} active members").
5. RECIPROCITY: "Want me to draft a {summer attendance challenge / off-
   season retention email}?" Single open CTA.

# VOICE — operator-coach. Pragmatic, NOT alarmist.
- "ad spend" / "conversion" / "retention" — operator vocab.
- NO "fight the dip!" / hype.

# HARD CONSTRAINTS
- Use trigger.payload.delta_pct + season_note + is_expected_seasonal.
- Customer count from merchant.customer_aggregate.
- ONE CTA.
"""

LEVER_HINT = "anxiety_preemption + reframe + specificity + reciprocity"

DEFAULT_CTA_SHAPE = "open_ended"
