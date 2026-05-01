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

Framing pattern:
1. State the source that landed (journal name + date or council circular).
2. Anchor on the SPECIFIC stat: trial_n + effect size + patient segment.
3. Connect to THIS merchant's cohort (use merchant.customer_aggregate or signals).
4. Offer to do work: pull the abstract, draft a patient-ed WhatsApp / Google post.
5. Open-ended CTA — soft commitment ("Want me to ...?").

Voice: peer-clinical, source-cited. NO promotional tone. NO overclaim.
End with the source citation in dash-prefixed form: " — JIDA Oct 2026 p.14".
"""

LEVER_HINT = "specificity (source + numbers) + reciprocity + curiosity"

DEFAULT_CTA_SHAPE = "open_ended"
