"""
kind_recall_due — customer-facing reminder sent on behalf of the merchant.

Pattern (paraphrased from Case Study 2):
- Warm salutation with customer name + clinic name (NOT Vera)
- Specific recall window (e.g. "5 months since your last visit")
- Concrete slot offer using slots from trigger.payload.available_slots
- Real catalog price + bonus value (from merchant offers)
- Multi-choice slot CTA (acceptable for booking flows) OR binary if 1 slot

send_as MUST be "merchant_on_behalf" (sent from merchant's WA number, not Vera's).
"""

from __future__ import annotations

KIND_NAME = "recall_due"

KIND_FRAMING = """\
TRIGGER KIND: recall_due (customer-facing — sent on behalf of the merchant to their customer)

This is a CUSTOMER-facing message. send_as = merchant_on_behalf. Voice changes:
- WARM, not promotional, not Vera-clinical. Empathy + pragmatism.
- Salute with the CUSTOMER name (customer.identity.name).
- Identify the merchant by name + locality ("Dr. Meera's clinic, Lajpat Nagar").
- NEVER introduce Vera — the customer must perceive it as the merchant texting them.
- Honor customer.identity.language_pref (e.g. "hi-en mix" → natural Hindi-English).
- Use customer.preferences (preferred_slots) to pick the right slot offering.
- If state=lapsed_soft, soft re-engagement; if state=lapsed_hard, no-shame warmth.

Framing:
1. Open with: "Hi <customer-name>, <merchant-name> here" + appropriate emoji (🦷 dental, 💇 salon, 🍕 food)
2. Recall window: "It's been N months since your last visit" (use exact N from relationship.last_visit)
3. Concrete slot offer: 2 slots from trigger.payload.available_slots, formatted natural
4. Price + bonus from merchant active_offers (real ₹ value, never invent)
5. Multi-choice CTA: "Reply 1 for <slot1>, 2 for <slot2>, or tell us a time that works"

Hard constraints:
- NO medical claims for dentists/pharmacies. NO "cure", "guaranteed".
- NO multi-step decision trees. ONE clear CTA last sentence.
"""

LEVER_HINT = "warmth + specificity (real slots + real price) + low-friction multi-choice"

DEFAULT_CTA_SHAPE = "multi_choice_slot"
