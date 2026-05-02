"""
Taboo validator — fails if body contains any token in category.voice.vocab_taboo.
"""

from __future__ import annotations

import re
from typing import Any


def check(
    body: str,
    *,
    category: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    if not body or not category:
        return True, None, None, body

    taboo = (category.get("voice") or {}).get("vocab_taboo") or []
    if not taboo:
        return True, None, None, body

    body_lower = body.lower()
    hits: list[str] = []
    for term in taboo:
        if not isinstance(term, str) or not term.strip():
            continue
        # Use case-insensitive substring match for short terms; word-boundary for longer
        if len(term) <= 5:
            if re.search(rf"\b{re.escape(term.lower())}\b", body_lower):
                hits.append(term)
        else:
            if term.lower() in body_lower:
                hits.append(term)

    if hits:
        return (
            False,
            f"Body contains taboo term(s) for this category: {hits}",
            f"Remove these forbidden words: {hits}. They violate category voice rules.",
            body,
        )
    return True, None, None, body
