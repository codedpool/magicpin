"""
URL validator — strips URLs that don't trace back to a context field.

Per challenge site: "include links only when they add real value." We allow
URLs that appear in a context field (e.g. merchant.identity.website) and strip
fabricated ones (e.g. fake.com or generic landing pages).
"""

from __future__ import annotations

import re
from typing import Any

# Match http(s)://... and bare www. URLs
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+\b", re.IGNORECASE)


def _flatten_context_strings(*contexts: dict[str, Any] | None) -> str:
    """Concatenate every string value found in the provided contexts."""
    parts: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    for ctx in contexts:
        if ctx:
            _walk(ctx)
    return " ".join(parts)


def check(
    body: str,
    *,
    category: dict[str, Any] | None = None,
    merchant: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
    customer: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    """
    Returns (passed, error, suggested_fix, modified_body).

    Strips URLs not traceable to a context field. If any URL is stripped, we
    still consider it "passed" but return the modified body. Only flagged if
    the body becomes empty/meaningless after stripping.
    """
    urls = _URL_RE.findall(body or "")
    if not urls:
        return True, None, None, body

    haystack = _flatten_context_strings(category, merchant, trigger, customer)
    new_body = body
    stripped: list[str] = []

    for url in set(urls):
        # Normalize the URL for substring search (without trailing punctuation)
        clean = url.rstrip(".,;:!?")
        # Trace: does the URL (or its domain) appear anywhere in contexts?
        domain = (
            clean.lower()
            .removeprefix("https://")
            .removeprefix("http://")
            .removeprefix("www.")
            .split("/")[0]
        )
        if domain and domain in haystack.lower():
            continue  # traceable — keep
        # Strip it (with surrounding spaces collapsed)
        new_body = re.sub(re.escape(url), "", new_body)
        new_body = re.sub(r"\s{2,}", " ", new_body).strip()
        stripped.append(url)

    if not stripped:
        return True, None, None, body

    if len(new_body) < 20:
        # Body became too short after stripping — fail and ask for re-DRAFT
        return (
            False,
            f"Body collapsed after stripping fabricated URL(s): {stripped}",
            "Do not include URLs that are not present in the contexts. Re-draft without URLs.",
            new_body,
        )

    return True, None, f"Stripped fabricated URL(s): {stripped}", new_body
