"""
Fabrication guard — every number/percentage/currency/year/source citation
the body asserts MUST trace to a context field. If we can't find it, flag.

Strategy: collect all string values from contexts, then for each claim
extracted from the body, check substring presence. Permissive on tiny
numbers (0-9) which are too generic to flag.
"""

from __future__ import annotations

import re
from typing import Any

# Patterns we extract as factual claims to verify
_CLAIM_PATTERNS = {
    "currency": re.compile(r"₹\s*([\d,]+(?:\.\d+)?)"),
    "percentage": re.compile(r"\b([\d]+(?:\.\d+)?)\s*%"),
    "page_ref": re.compile(r"\bp\.?\s*(\d+)", re.IGNORECASE),
    "year": re.compile(r"\b(19|20)(\d{2})\b"),
    # 2+ digit numbers (skip single digits — too generic)
    "number": re.compile(r"\b(\d{2,}(?:[,.]\d+)?)\b"),
}

# Specific journals/councils whose mention should trace to context (otherwise
# we can't tell a fabricated citation from a real one). Generic platform names
# (Google, WhatsApp, Insta, Swiggy) are universal in this domain — don't flag.
KNOWN_JOURNAL_HINTS = (
    "JIDA", "IJDR", "JADA",
    "DCI", "Dental Council of India",
    "Practo",
    "Dental Tribune", "Dental Tribune India",
    "Dentsply", "IPS e.max",
)


def _flatten_context_strings(*contexts: dict[str, Any] | None) -> str:
    """Concatenate every string and number value found in the provided contexts."""
    parts: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, (int, float)):
            parts.append(str(node))
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    for ctx in contexts:
        if ctx:
            _walk(ctx)
    return " ".join(parts).lower()


def _normalize_number(s: str) -> str:
    """Strip thousands separators for substring match: '2,100' → '2100'."""
    return s.replace(",", "").rstrip(".0").lstrip("0") or "0"


def _claim_in_haystack(claim_value: str, haystack: str) -> bool:
    """Match the claim several ways to avoid false positives:
    - exact substring
    - normalized number
    - close numerical match (within 2%) for percentages and counts
    """
    haystack = haystack.lower()
    raw = claim_value.lower()
    if raw in haystack:
        return True

    norm = _normalize_number(claim_value)
    if norm and norm in haystack.replace(",", ""):
        return True

    # Try fuzzy numerical: parse to float, scan all numbers in haystack,
    # accept if within 2% relative or absolute distance ≤ 1
    try:
        v = float(_normalize_number(claim_value))
    except (ValueError, TypeError):
        return False
    for m in re.finditer(r"\d+(?:[.,]\d+)?", haystack):
        try:
            other = float(m.group(0).replace(",", ""))
        except ValueError:
            continue
        if v == 0 or other == 0:
            if abs(v - other) <= 1:
                return True
            continue
        if abs(v - other) / max(abs(v), abs(other)) < 0.02:
            return True
    return False


def check(
    body: str,
    *,
    category: dict[str, Any] | None = None,
    merchant: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
    customer: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    if not body:
        return True, None, None, body

    haystack = _flatten_context_strings(category, merchant, trigger, customer)
    fabricated: list[str] = []

    # 1. Currency claims
    for match in _CLAIM_PATTERNS["currency"].findall(body):
        if not _claim_in_haystack(match, haystack):
            fabricated.append(f"₹{match}")

    # 2. Percentages — also accept the decimal equivalent (e.g. body "2.1%" vs ctx 0.021)
    for match in _CLAIM_PATTERNS["percentage"].findall(body):
        if _claim_in_haystack(match, haystack):
            continue
        try:
            pct = float(match)
            decimal_eq = pct / 100
            # Try several string forms of the decimal
            forms = [
                f"{decimal_eq:.4f}".rstrip("0").rstrip("."),
                f"{decimal_eq:.3f}".rstrip("0").rstrip("."),
                f"{decimal_eq}",
            ]
            if any(_claim_in_haystack(f, haystack) for f in forms if f):
                continue
        except (ValueError, TypeError):
            pass
        fabricated.append(f"{match}%")

    # 3. Page references (e.g. p.14)
    for match in _CLAIM_PATTERNS["page_ref"].findall(body):
        if f"p.{match}" not in haystack and f"p {match}" not in haystack and f"page {match}" not in haystack:
            fabricated.append(f"p.{match}")

    # 4. Years (only flag if context has years and this one is missing)
    body_years = ["".join(t) for t in _CLAIM_PATTERNS["year"].findall(body)]
    haystack_has_years = bool(re.search(r"\b(?:19|20)\d{2}\b", haystack))
    for y in body_years:
        if haystack_has_years and y not in haystack:
            fabricated.append(y)

    # 5. Multi-digit numbers (skip in-range matches)
    for match in _CLAIM_PATTERNS["number"].findall(body):
        # skip if already counted (currency/percentage/page/year branches above
        # may have already covered it)
        if f"₹{match}" in fabricated or f"{match}%" in fabricated or f"p.{match}" in fabricated:
            continue
        try:
            num = int(match.replace(",", "").split(".")[0])
        except ValueError:
            continue
        # skip ultra-common small numbers (already permissive: skipped <10 by regex)
        if num < 10:
            continue
        if not _claim_in_haystack(match, haystack):
            fabricated.append(match)

    # 6. Known-journal/source hints — if mentioned, must be in haystack
    for hint in KNOWN_JOURNAL_HINTS:
        if hint.lower() in body.lower() and hint.lower() not in haystack:
            fabricated.append(hint)

    if not fabricated:
        return True, None, None, body

    # De-dupe + cap
    seen = set()
    uniq = [x for x in fabricated if not (x in seen or seen.add(x))][:8]

    return (
        False,
        f"Possibly fabricated claims (not found in contexts): {uniq}",
        "Remove or replace these claims with values from the contexts. Do NOT invent "
        "numbers, prices, percentages, page references, journal names, or sources. If "
        "you don't have a precise number, omit it rather than estimate.",
        body,
    )
