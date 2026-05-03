"""
kind_research_digest — Vera surfaces this week's digest item to the merchant.

Pattern (paraphrased from Case Study 1):
- Source citation FIRST (credibility)
- Specific stat anchor (trial N + effect size)
- Cohort match (why this matters for THIS merchant — derived from customer_aggregate)
- Reciprocity ("Want me to draft a patient-ed WhatsApp?")
- Open-ended CTA — soft commitment

The digest item is fetched from category.digest by id (in trigger.payload.top_item_id).
"""

from __future__ import annotations

KIND_NAME = "research_digest"

KIND_FRAMING = """\
TRIGGER KIND: research_digest (a fresh research/CDE/compliance/trend item dropped this week)

# FRAMING — merchant-cohort-first (Pattern A — gold standard 50/50)
1. Lead with the merchant's NAME + the COHORT MATCH this research speaks to.
   The cohort match is what separates "newsletter-style" (low score) from
   "your X patients should care about this" (high score).
     ✗ "JIDA Oct issue landed. A new trial..." (newsletter — DQ 5/10)
     ✓ "Dr. Meera, JIDA's Oct issue has one item relevant to your
        high-risk adult patients" (cohort-specific — DQ 9/10)
   Pull the cohort from merchant.customer_aggregate (e.g.
   high_risk_adult_count=124) or merchant.signals (e.g.
   "high_risk_adult_cohort").
2. State the SPECIFIC stat from digest_item: trial_n + effect_size + segment.
3. Reciprocity: offer to do work — pull the abstract, draft a patient-ed
   WhatsApp / Google post.
4. ONE open-ended CTA. Single binary close.
5. End with the source citation in dash-prefixed form:
   " — JIDA Oct 2026 p.14" (or whatever digest_item.source is).

# WHEN PAYLOAD IS SPARSE
If trigger.payload is just {"placeholder": true}, anchor on:
- category.professional_journals (cite a generic "your weekly journal scan")
- merchant.signals (use whatever cohort signal is set)
- offer the patient-ed draft as the reciprocity hook
NEVER invent a specific journal volume / page / trial-N if not in contexts.

# VOICE
Peer-clinical, source-cited. NO promotional tone. NO overclaim.
For dentists / pharmacies: USE "Dr." prefix per category.voice.salutation_examples.

# CTA — must include a time-cap (system_base TIME-CAP RULE)
End the body with a single binary CTA that includes a tight time-cap.
For this kind, a strong example:
  "Reply YES — I'll have the abstract + patient-ed draft in your WhatsApp within 5 min."
Other formats: "Reply YES — N min." / "live in 10 min." / "by EOD" /
"in your WhatsApp in 30 sec". WITHOUT a time-cap, ENG caps at 6.
"""

LEVER_HINT = (
    "specificity (source + trial size + effect %) + cohort_match (the merchant's "
    "OWN customer segment) + reciprocity (\"want me to pull it?\") + curiosity. "
    "Lead with cohort match, NOT with the source name — newsletter-style openers "
    "score DQ 4-5; cohort-specific openers score DQ 9-10."
)

DEFAULT_CTA_SHAPE = "open_ended"
