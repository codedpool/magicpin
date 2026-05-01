"""
Tiny retrieval helpers — look up the digest item / offer / content
referenced by a trigger.payload, so the composer prompt has the actual
content (not just an id) to anchor on.
"""

from __future__ import annotations

from typing import Any


def find_digest_item(category: dict[str, Any], item_id: str | None) -> dict[str, Any] | None:
    """Look up a digest item by id from the category's digest list."""
    if not item_id or not category:
        return None
    for item in category.get("digest", []) or []:
        if item.get("id") == item_id:
            return item
    return None


def find_offer(merchant: dict[str, Any], offer_id: str | None) -> dict[str, Any] | None:
    if not offer_id or not merchant:
        return None
    for off in merchant.get("offers", []) or []:
        if off.get("id") == offer_id:
            return off
    return None


def find_active_offers(merchant: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        off for off in (merchant.get("offers") or [])
        if (off.get("status") or "").lower() == "active"
    ]


def find_content_item(category: dict[str, Any], item_id: str | None) -> dict[str, Any] | None:
    if not item_id or not category:
        return None
    for item in category.get("patient_content_library", []) or []:
        if item.get("id") == item_id:
            return item
    return None
