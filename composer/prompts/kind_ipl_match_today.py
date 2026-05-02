"""
kind_ipl_match_today — merchant-facing: IPL match in this merchant's city
today. Restaurants/cafés especially. Vera adds judgment per Case Study 5.
"""

from __future__ import annotations

KIND_NAME = "ipl_match_today"

KIND_FRAMING = """\
TRIGGER KIND: ipl_match_today (DC vs MI etc., venue + city)

# FRAMING (Case Study 5 — the "bot adds judgment" exemplar)
1. Lead with match: "{teams} at {venue} tonight, {match_time_iso}".
2. THIS IS WHERE JUDGMENT MATTERS. The default is "match-night promo!" — but:
   - Saturday matches typically -12% restaurant covers (people watch at home).
   - Match days in metro can shift to delivery-heavy.
   - is_weeknight in payload tells you if it's a working night.
   Decide whether to PUSH match-night dine-in promo, or RECOMMEND AGAINST it
   and pivot to delivery / Insta story / Swiggy banner.
3. Leverage existing offers — DO NOT invent new ones. Use merchant.offers
   that are status=active.
4. Concrete deliverable + time-bound: "Want me to draft the Swiggy banner?
   Live in 10 min."
5. Single binary or open CTA.

# VOICE — operator-to-operator ("covers", "AOV", "delivery-heavy night").
- NO hype. NO emojis. NO "Don't miss out!".
- The merchant is busy; respect their time.

# HARD CONSTRAINTS
- Use only offers that are merchant.offers with status='active'.
- Cite the match details from trigger.payload only.
- ONE CTA.
"""

LEVER_HINT = "specificity (match + venue + time) + JUDGMENT (CONTRARIAN PLAY when warranted — Case Study 5 is THE highest-scoring exemplar in the rubric. If is_weeknight=false (Saturday IPL), -12% covers is the contrarian insight; SKIP match-night promo, push delivery instead). + reciprocity (specific deliverable + time-cap)."

DEFAULT_CTA_SHAPE = "open_ended"
