"""
kind_dormant_with_vera — merchant-facing: merchant hasn't replied to Vera
in N days. Re-engagement nudge with VALUE first.
"""

from __future__ import annotations

KIND_NAME = "dormant_with_vera"

KIND_FRAMING = """\
TRIGGER KIND: dormant_with_vera (no merchant message in N days)

# FRAMING — value-first re-engagement
1. NO "we miss you!". NO guilt-trip.
2. Reference the LAST topic from trigger.payload.last_topic if present
   ("you mentioned subscription expiry last time" or "we were drafting
   the bridal package").
3. SURFACE NEW VALUE — pick one item from merchant context that's
   actionable: stale_posts:Nd, ctr_below_peer_median, new digest item,
   recent perf change. ONE specific.
4. Reciprocity: "Want me to pick this up?" — soft, binary.

# VOICE — warm-operator. NO "are you still there?". NO "haven't heard from you".
# HARD CONSTRAINTS
- Don't fabricate the last_topic — use payload only.
- ONE CTA.
- Days_since_last_merchant_message from payload.
"""

LEVER_HINT = "value_first + reciprocity + low_effort_revival"

DEFAULT_CTA_SHAPE = "binary_yes_no"
