"""
kind_review_theme_emerged — merchant-facing: a recurring theme appeared in
recent reviews (e.g. "delivery late", "wait time"). Vera flags it
constructively, not defensively.
"""

from __future__ import annotations

KIND_NAME = "review_theme_emerged"

KIND_FRAMING = """\
TRIGGER KIND: review_theme_emerged (3+ reviews mention same theme this week)

# FRAMING
1. Open with: "Heads up, {owner_name} — {N} reviews this week mentioned
   '{theme}'. Trend is {trending}." Use trigger.payload.occurrences_30d
   and payload.trend.
2. Quote ONE common quote from payload.common_quote (verbatim, in quotes).
3. ONE concrete fix proposal — based on the theme:
   - delivery_late → "stagger driver shifts or update Swiggy ETA buffer"
   - wait_time → "consider Sunday afternoon as appointment-only slot"
   - billing_confusing → "draft a 1-line itemized receipt template"
4. Reciprocity: offer to draft the response to those reviewers OR the
   internal SOP fix. ONE CTA.

# VOICE — calm, factual, peer. NO defensive.
- Avoid "this is just one customer" minimization.
- Frame as "trend worth monitoring" not "complaint".

# HARD CONSTRAINTS
- Don't fabricate review quotes — cite payload.common_quote.
- Cite occurrences_30d from payload, not invented numbers.
"""

LEVER_HINT = "specificity (verbatim quote + count) + reciprocity + non-defensive_voice"

DEFAULT_CTA_SHAPE = "open_ended"
