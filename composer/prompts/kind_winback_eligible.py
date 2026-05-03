"""
kind_winback_eligible — merchant-facing: their subscription expired, they
saw a perf dip, AND lapsed_customers > 0. Vera proposes winback campaign.
"""

from __future__ import annotations

KIND_NAME = "winback_eligible"

KIND_FRAMING = """\
TRIGGER KIND: winback_eligible (subscription lapsed + perf dip + lapsed customers)

# FRAMING — action-first, CATEGORY-VOICED (most-missed)
1. LEAD with the merchant-specific action recommendation in CATEGORY VOICE.
   The category dictates the tone:
     - Salons (warm-practical): "Anita, let's run a quick winback —
        WhatsApp the 14 ladies who haven't booked since Aug a free
        haircut + ₹500 service combo this week."
     - Restaurants (operator-to-operator): "Suresh, let's reactivate Pro
        and push a Tue-Thu BOGO to the 22 dine-in regulars who haven't
        ordered in 60d. Expected return: 12-18 covers."
     - Gyms (coach-grade): "Karan, reactivate Pro and pull a free-trial
        comeback challenge for the 18 lapsed members. 2-week window
        beats one-time discount on retention."
     - Dentists/pharmacies (clinical-peer): "Dr. Asha, reactivate Pro
        and run a 6-month-cleaning recall for the 28 patients who
        haven't visited since Sep. Expected return: 8-12 bookings."
2. SUPPORTING CLAUSE: cite the 3 numbers from payload exactly:
   days_since_expiry, perf_dip_pct, lapsed_customers_added_since_expiry.
3. ONE help offer + binary close: "Reply YES — I'll set up the campaign
   in 10 min" / "Reply HOLD if you want to wait."

# VOICE — STRICT to merchant.category_slug.
- This kind has had the WORST category_fit historically because it
  defaulted to a generic SaaS "subscription lapsed" voice that ignored
  category. Always speak as a peer in the merchant's category.

# HARD CONSTRAINTS
- First sentence MUST be in category voice (vocab_allowed) AND contain
  the merchant action.
- Cite trigger.payload.days_since_expiry + .perf_dip_pct +
  .lapsed_customers_added_since_expiry exactly IF PRESENT.
- 8-12% conversion typical is industry-standard, OK to cite as range.
- ONE binary CTA. NEVER stack.
"""

LEVER_HINT = (
    "decision_quality (lead with category-voiced action) + diagnostic_"
    "specificity (3 numbers from payload) + opportunity_framing + "
    "single_binary_commit. CATEGORY voice is the rubric leader for "
    "this kind — generic SaaS voice caps category_fit at 5."
)

DEFAULT_CTA_SHAPE = "binary_yes_no"
