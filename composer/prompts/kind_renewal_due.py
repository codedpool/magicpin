"""
kind_renewal_due — merchant-facing: their magicpin subscription expires soon.
Vera reminds with a concrete value receipt, not just "renew now".
"""

from __future__ import annotations

KIND_NAME = "renewal_due"

KIND_FRAMING = """\
TRIGGER KIND: renewal_due (subscription expires in N days)

# FRAMING — value-receipt first, then the ask
1. Lead with VALUE this cycle: cite specific numbers from merchant.performance
   over the last 30d (views, calls, leads). NOT "you got benefit", but
   "this cycle: 2,410 views, 18 calls, 9 leads".
2. State renewal: "your Pro plan renews in {days_remaining} days at
   ₹{renewal_amount}".
3. Frame as continuity, not pressure. "Want me to set the renewal up so
   nothing breaks?" — preferred over "renew today!".
4. Binary CTA: "Reply YES to renew" / "Reply HOLD if you want to pause".

# VOICE — operator-to-operator. NO panic. NO "limited time".
# HARD CONSTRAINTS
- Cite ONLY numbers from merchant.performance and merchant.subscription.
- ONE CTA. Binary preferred.
"""

LEVER_HINT = "specificity (real numbers) + effort_externalization + binary CTA"

DEFAULT_CTA_SHAPE = "binary_yes_no"
