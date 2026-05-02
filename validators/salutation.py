"""
Salutation validator — first send must use owner's first name (or customer's
name for customer-facing). Subsequent sends must NOT re-introduce Vera.
"""

from __future__ import annotations

import re
from typing import Any


_VERA_REINTRO_PATTERNS = [
    r"\bI(?:'|’)?m\s+vera\b",
    r"\bvera\s+here\b",
    r"\bthis\s+is\s+vera\b",
    r"\bvera\s+from\s+magicpin\b",
    r"\bhi[,!.\s]+i(?:'|’)?m\s+vera",
    r"\bnamaste[,!.\s]+main\s+vera",
    r"\bvera\s+se\s+bol",
]


def check(
    body: str,
    *,
    plan: dict[str, Any] | None = None,
    merchant: dict[str, Any] | None = None,
    customer: dict[str, Any] | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    if not body:
        return True, None, None, body

    is_first_turn = not (conversation_history or [])
    body_lower = body.lower()
    send_as = (plan or {}).get("send_as", "vera")

    if is_first_turn:
        # Customer-facing first message: must address customer by name
        if send_as == "merchant_on_behalf" and customer:
            customer_name = ((customer.get("identity") or {}).get("name") or "").strip()
            if customer_name and customer_name.lower() not in body_lower:
                return (
                    False,
                    f"Customer-facing first message must address the customer by name "
                    f"(expected '{customer_name}').",
                    f"Open with 'Hi {customer_name}, ...' or '{customer_name}, ...'",
                    body,
                )
            return True, None, None, body

        # Merchant-facing first message: should use owner_first_name when available
        owner = ((merchant or {}).get("identity") or {}).get("owner_first_name")
        if owner and owner.lower() not in body_lower:
            # Soft check — warn but pass if "Dr." prefix or merchant_name is used
            merchant_name = ((merchant or {}).get("identity") or {}).get("name", "")
            short = merchant_name.split(" ")[0] if merchant_name else ""
            if short and short.lower() not in body_lower:
                return (
                    False,
                    f"First merchant message should use owner first name (expected '{owner}').",
                    f"Open with 'Dr. {owner},' or '{owner},' (avoid generic 'Hi there').",
                    body,
                )
        return True, None, None, body

    # Subsequent turns — must NOT re-introduce Vera
    for pat in _VERA_REINTRO_PATTERNS:
        if re.search(pat, body_lower):
            return (
                False,
                "Body re-introduces Vera in a subsequent turn (anti-pattern).",
                "Drop any 'I'm Vera' / 'Vera here' / 'this is Vera' phrasing — the merchant "
                "already knows who's texting them.",
                body,
            )
    return True, None, None, body
