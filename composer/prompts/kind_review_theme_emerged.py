"""
kind_review_theme_emerged — merchant-facing: a recurring theme appeared in
recent reviews (e.g. "delivery late", "wait time"). Vera flags it
constructively, not defensively.
"""

from __future__ import annotations

KIND_NAME = "review_theme_emerged"

KIND_FRAMING = """\
TRIGGER KIND: review_theme_emerged (3+ reviews mention same theme this week)

# FRAMING — action-first (Decision Quality is the top lift target here)
1. LEAD with the merchant-specific fix recommendation, not the heads-up:
     ✗ "Heads up, Suresh — 4 reviews mentioned 'wait-time'." (DQ 5/10)
     ✓ "Suresh — add a Sunday-afternoon staffer or shift to appointment-
        only Sun 1-4pm. 4 reviews this week flagged wait-time
        ('took 50 mins for a 15 min ride')." (DQ 9/10)
2. Cite the EXACT theme + count + verbatim quote from
   trigger.payload.common_quote. Always wrap the quote in single quotes.
3. The fix proposal must match the theme:
   - wait_time → "Sunday-afternoon appointment-only block" / "stagger
     stylist shifts" (depends on category)
   - delivery_late → "update Swiggy ETA buffer to N min" / "stagger
     driver shifts"
   - billing_confusing → "draft a 1-line itemized receipt template"
   - service_quality → "shadow your top stylist for an hour with newer
     team — quick calibration"
4. ONE help offer + binary close: "Want me to draft the response to
   those 4 reviewers + the internal SOP note? Reply YES — 5 min."

# WHEN PAYLOAD IS SPARSE
If trigger.payload is just {"placeholder": true}, fall back to
merchant.review_themes (which has theme + sentiment + occurrences_30d
+ common_quote per theme). Pick the highest-occurrence negative theme.
NEVER invent a theme or a quote.

# VOICE — calm, factual, peer-operator. NO defensive.
- Avoid "this is just one customer" minimization.
- Frame as "trend worth fixing" not "complaint".

# HARD CONSTRAINTS
- First sentence MUST contain the recommended fix.
- Don't fabricate review quotes — cite payload.common_quote OR
  merchant.review_themes[].common_quote.
- Cite occurrences_30d from payload, not invented numbers.
- ONE CTA. NEVER stack ("draft response AND draft SOP AND audit X").
"""

LEVER_HINT = (
    "decision_quality (lead with merchant fix) + specificity (verbatim "
    "quote + count) + reciprocity (\"want me to draft both?\") + "
    "non-defensive_voice. NEVER stack CTAs."
)

DEFAULT_CTA_SHAPE = "open_ended"
