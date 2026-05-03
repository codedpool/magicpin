"""
kind_supply_alert — pharmacy-facing: voluntary recall on a molecule batch.
Highest urgency. Vera leads with the action the pharmacy must take.
"""

from __future__ import annotations

KIND_NAME = "supply_alert"

KIND_FRAMING = """\
TRIGGER KIND: supply_alert (recall on molecule batches — Case Study 9)

# FRAMING — action-first (pharmacy quality bar)
1. LEAD with the merchant ACTION, then the recall as supporting fact:
     ✗ "Voluntary recall on 2 atorvastatin batches by Mfr Z. {N} customers
        affected. Want me to draft the workflow?"
     ✓ "Ramesh — flag {N} of your chronic-Rx customers for replacement
        before this week is out (atorvastatin batches AT2024-1102 +
        AT2024-1108 by Mfr Z, sub-potency recall)."
2. DERIVED COUNT (highest-scoring move) — if merchant.customer_aggregate
   has chronic-Rx data matching this molecule, cite the count from THEIR
   data. Never invent.
3. ONE help offer that resolves the WHOLE workflow (low-friction):
   "Want me to draft the WhatsApp note + pickup-workflow now?"
4. Single binary close: "Reply YES — I'll have it ready in 5 min."

# VOICE — pharmacy: trustworthy + precise. NO alarm.
- Use exact molecule + batch terminology.
- "Sub-potency" / "stability deviation" — clinical, not panicked.

# HARD CONSTRAINTS
- First sentence MUST contain the recommended pharmacist action (flag X
  customers / pull Y units / pause dispensing of Z).
- Cite trigger.payload.molecule, .affected_batches[], .manufacturer exactly
  IF PRESENT in payload.
- If payload is sparse (e.g. {"placeholder": true} from generated triggers),
  anchor on merchant.customer_aggregate.chronic_rx (count) and a generic
  recall phrasing ("a molecule batch recall affecting some chronic-Rx
  customers"); do NOT invent batch numbers, manufacturer names, or
  molecule names. Recommend the merchant pull their list to verify.
- Don't invent customer counts — derive only from merchant.customer_aggregate.
- ONE CTA. NEVER stack ("draft note AND audit inventory AND..." → -5 ENG).
"""

LEVER_HINT = (
    "decision_quality (lead with pharmacist action) + specificity (batch numbers + "
    "derived customer count) + reciprocity (full workflow offer) + single binary CTA."
)

DEFAULT_CTA_SHAPE = "open_ended"
