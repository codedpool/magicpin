"""Length validator — warns at 600 chars, hard-fails at 1200."""

from __future__ import annotations

from typing import Any


WARN_AT = 600
HARD_FAIL_AT = 1200
MIN_CHARS = 30


def check(
    body: str,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    n = len(body or "")
    if n < MIN_CHARS:
        return (
            False,
            f"Body too short ({n} chars).",
            "Re-draft with substantive content — at least one anchor fact and one CTA.",
            body,
        )
    if n > HARD_FAIL_AT:
        return (
            False,
            f"Body too long ({n} chars > {HARD_FAIL_AT} hard cap).",
            "Tighten ruthlessly. Keep one anchor fact, one lever, one CTA. Drop preambles.",
            body,
        )
    return True, None, None, body
