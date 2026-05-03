"""
kind_chronic_refill_due — customer-facing pharmacy refill reminder.

Pattern: pharmacy texts a chronic patient (or their family member) before
their molecules run out. Like recall_due but tuned for medications:
- molecule list (e.g. metformin/atorvastatin/telmisartan)
- exact stock-runs-out date
- saved delivery address
- sometimes addressed to the family member (son/grandfather pattern)

send_as MUST be "merchant_on_behalf".
"""

from __future__ import annotations

KIND_NAME = "chronic_refill_due"

KIND_FRAMING = """\
TRIGGER KIND: chronic_refill_due (customer-facing — pharmacy refill reminder)

This is a CUSTOMER-facing message. send_as = merchant_on_behalf.

# VOICE — trustworthy + precise (pharmacy category)
- Respectful, specific, no hype, no medical claims.
- Salute with the customer name (or family member if customer is a senior whose
  son/daughter handles WhatsApp — check customer.identity.name).
- Identify the pharmacy by name + locality.
- NEVER introduce Vera. The customer perceives this as the pharmacy texting them.

# LANGUAGE — STRICT
HONOR customer.identity.language_pref:
  - "hi-en mix" → mix in 2-4 Hindi words ("Sharma ji ki dawai", "khatam hone wali hai")
  - "te-en mix" / "kn-en mix" / "mr-en mix" → use the relevant native tokens
  - For SENIORS or family-member channels (son's number), use "namaste" / "namaskar" salutations
  - Default English if no preference

# CTA SHAPE — multi_choice_slot OR binary
The LAST sentence MUST be one of:
  - "Reply CONFIRM to dispatch by <time>, or call us if dosage changed."
  - "Reply 1 for home delivery, 2 to pick up, or call us for any change."
NO trailing question mark unless it's the only CTA.

# RICH CUSTOMER FIELDS — use these aggressively
- customer.identity.senior_citizen=true → use "Namaste" + "ji" suffix
  ("Sharma ji ki..."); convey respect.
- customer.preferences.channel == "whatsapp_via_son" → write the message
  AS IF addressing the son ("Sharma ji ki dawai..." not "your dawai..."),
  the son is the recipient managing his father's refill.
- customer.relationship.chronic_conditions (e.g. ["diabetes_t2", "hypertension"])
  → reference these once for context, never as a diagnosis.
- customer.relationship.lifetime_value > 10000 → reference "loyal customer"
  framing if appropriate (don't be transactional).
- customer.consent.scope MUST include "refill_reminders" or "delivery_notifications"
  for this message to be sent — if not, treat as opted-out.

# STRUCTURE
1. Salutation: "Namaste — <pharmacy> <locality> yahan" / "Namaskar, <pharmacy> here"
2. Subject: name the patient (Sharma ji / Mr. Sharma / Ramesh) + their molecules
   from trigger.payload.molecule_list (metformin, atorvastatin, telmisartan)
   IF PRESENT. If payload is sparse (placeholder), use customer.relationship
   .chronic_conditions to infer the molecule class generically
   ("aapki monthly diabetes + BP medicines").
3. Run-out date: "<DATE> ko khatam hongi" / "stock runs out <DATE>"
   — use trigger.payload.runs_out_date if present, else "this week"/"by month-end".
4. Same dose / same brand pack ready (don't change without doctor consult)
5. Apply senior_discount or any merchant active offer if applicable;
   show total price + savings transparently. Skip price entirely if
   active_offers don't include a relevant senior/refill offer.
6. Free delivery to saved address (from customer.preferences.delivery_address)
   if eligible
7. Multi-choice or binary CTA per above

# HARD CONSTRAINTS
- NEVER substitute molecules without doctor approval.
- NEVER use "guaranteed" / "completely cure" / "miracle".
- NEVER invent prices — use only what's in merchant active_offers.
- NEVER invent specific molecule names if payload is sparse — use a
  generic phrasing ("monthly diabetes + BP medicines").

# EXEMPLAR (for hi-en mix; paraphrase the *shape*, do NOT reuse exact numbers)
"Namaste — <pharmacy> <locality> yahan. <Patient> ji ki <N> monthly
dawai (<molecule list from trigger>) <date> ko khatam hongi.
Same dose, same brand pack ready hai. <Discount label if eligible> applied —
total ₹<computed>. Free home delivery to saved address by <time>.
Reply CONFIRM to dispatch, or call us if any change in dosage."
"""

LEVER_HINT = "trustworthiness + specificity (molecules + date + savings) + low-friction CTA"

DEFAULT_CTA_SHAPE = "binary_yes_no"
