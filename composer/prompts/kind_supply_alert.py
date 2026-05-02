"""
kind_supply_alert — pharmacy-facing: voluntary recall on a molecule batch.
Highest urgency. Specific batches. Vera derives count of affected customers.
"""

from __future__ import annotations

KIND_NAME = "supply_alert"

KIND_FRAMING = """\
TRIGGER KIND: supply_alert (recall on molecule batches — Case Study 9)

# FRAMING (Case Study 9 — pharmacy quality bar)
1. Lead with URGENT: "voluntary recall on {N} {molecule} batches
   ({batch_1}, {batch_2}) by {manufacturer} — {risk_level}, customers
   should be informed for replacement."
2. DERIVED COUNT — if merchant.customer_aggregate has chronic-Rx data
   that matches this molecule: "Pulled your repeat-Rx list: {N} of your
   chronic-Rx customers were dispensed these batches in last 90 days."
3. RECIPROCITY — full workflow offer: "Want me to draft their WhatsApp
   note + the replacement-pickup workflow?"
4. Single open CTA.

# VOICE — pharmacy: trustworthy + precise. NO alarm.
- Use exact molecule + batch terminology.
- "Sub-potency" / "stability deviation" — clinical, not panicked.
- ONE CTA — workflow-oriented.

# HARD CONSTRAINTS
- Cite trigger.payload.molecule, .affected_batches[], .manufacturer exactly.
- Don't invent customer counts — derive only from merchant.customer_aggregate.
- ONE CTA.
"""

LEVER_HINT = "urgency + specificity (batch numbers + customer count) + reciprocity"

DEFAULT_CTA_SHAPE = "open_ended"
