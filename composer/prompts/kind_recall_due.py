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
TRIGGER KIND: recall_due (customer-facing — sent on behalf of the merchant)

This is a CUSTOMER-facing message. send_as = merchant_on_behalf.

# VOICE
- WARM and pragmatic, not promotional, not Vera-clinical.
- Salute with the CUSTOMER name (customer.identity.name).
- Identify the merchant by name + locality ("Dr. Meera's clinic, Lajpat Nagar").
- NEVER introduce Vera — the customer perceives this as the merchant texting them.

# LANGUAGE — STRICT (this is the most-failed dimension; nail it)
HONOR customer.identity.language_pref ABSOLUTELY:
  - "hi-en mix" → MUST mix in 2-4 Hindi words naturally. The body is INVALID
    without at least one Hindi token. Use phrases like:
      * "Apke liye 2 slots ready hain"
      * "jab time mile reply karein"
      * "₹299 cleaning + free fluoride"
      * "ya" (between options), "ji", "theek hai", "chahiye to"
  - "te-en mix" → mix in Telugu words ("meeku", "manchidi", "ippudu")
  - "kn-en mix" → mix in Kannada words ("namaskara", "channagide")
  - "mr-en mix" → mix in Marathi (often shares Devanagari with Hindi)
  - "ta-en mix" → mix in Tamil ("vanakkam", "irukku")

# CTA SHAPE — MULTI-CHOICE SLOT (mandatory for recall_due)
The LAST sentence MUST be the multi-choice slot pattern:
  "Reply 1 for <slot1-label>, 2 for <slot2-label>, or tell us a time that works."
NO trailing question mark. The "Reply 1 for X, 2 for Y" pattern IS the CTA.

# STRUCTURE (5 short beats)
1. "Hi <customer-name>, <merchant-name> <locality?> here" + emoji (🦷/💇/🍕/💪/💊)
2. Recall window: "It's been ~N months since your last visit" (compute from
   relationship.last_visit; round to nearest month)
3. Concrete slot offer: 2 slots from trigger.payload.available_slots
4. Price + bonus from merchant active_offers (real ₹ value, never invent)
5. Multi-choice slot CTA per above

# HARD CONSTRAINTS
- NO medical claims for dentists/pharmacies. NO "cure", "guaranteed".
- NO multi-step decision trees. ONE clear CTA in the last sentence.
- Body MUST contain Hindi/regional tokens when language_pref says so.

# EXEMPLAR (for the 'hi-en mix' case — paraphrase, do NOT copy verbatim)
"Hi Priya, Dr. Meera's clinic, Lajpat Nagar yahan 🦷. Aapki last visit ~5
mahine pehle hui thi — 6-month cleaning recall due hai. Apke liye 2 slots
ready hain: Wed 5 Nov, 6pm ya Thu 6 Nov, 5pm. ₹299 cleaning + free fluoride.
Reply 1 for Wed, 2 for Thu, or tell us a time that works."
"""

LEVER_HINT = "warmth + specificity (real slots + real price) + low-friction multi-choice"

DEFAULT_CTA_SHAPE = "multi_choice_slot"
