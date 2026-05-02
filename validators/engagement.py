"""
Engagement-strength validator.

Most-missed rubric dimension. Catches bodies that are technically valid but
generic — no specific number, no peer comparison, no locality, no derived
count, no question, no binary CTA, etc. If a body has fewer than 2 of these
anchors, it's a weak engagement candidate and we re-DRAFT.

This validator does NOT block on every weakness — it's permissive. Blocks only
when the body lacks ALL of the strong-engagement signals.
"""

from __future__ import annotations

import re
from typing import Any

# Patterns that indicate a STRONG engagement anchor
NUMBER_RE = re.compile(r"\b\d{2,}\b")  # 2+ digit number
CURRENCY_RE = re.compile(r"₹\s*\d+")
PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
QUESTION_RE = re.compile(r"\?")
PEER_RE = re.compile(r"\b(peer|metro|locality|nearby|in your area|Sector|locality)\b", re.IGNORECASE)
SPECIFIC_TIME_RE = re.compile(r"\b\d+\s*(?:min|sec|hour|day|week|month)s?\b", re.IGNORECASE)
NAMED_SOURCE_RE = re.compile(
    r"\b(JIDA|IJDR|JADA|DCI|FSSAI|Practo|Dental Tribune|Dentsply|Google|GBP|"
    r"Swiggy|Zomato|WhatsApp|Insta|Instagram|Kaleyra|Reuters)\b",
    re.IGNORECASE,
)
SOCIAL_PROOF_RE = re.compile(
    r"\b(\d+\s+(?:dentists|salons|gyms|pharmacies|restaurants|merchants|customers|members|patients)|"
    r"\d+\s+people|\d+%\s+of\s+(?:your|other)|"
    r"average|median|peer|locality|metro\s+avg)\b",
    re.IGNORECASE,
)
ASKING_RE = re.compile(
    r"\b(what(?:'s| is| has been)|which|how (?:are|do|is|much|many)|"
    r"who(?:'s| is)|when (?:are|is|do|did))\b",
    re.IGNORECASE,
)
LOSS_AVERSION_RE = re.compile(
    r"\b(missed|missing|losing|losing out|before this|window closes|"
    r"running out|stock\s*out|expired?|deadline|capped|capping)\b",
    re.IGNORECASE,
)
EFFORT_EXT_RE = re.compile(
    r"\b((?:I'?ll|I will) draft|(?:I'?ve|I have) drafted|just (?:say|reply)|"
    r"5-min|90-sec|live in \d+\s*min|on it|drafting now|ready in \d+\s*sec)\b",
    re.IGNORECASE,
)
BINARY_CTA_RE = re.compile(
    r"\b(reply\s+(?:yes|no|stop|y/n|1|confirm|go)|reply\s+\d|y/n|YES/NO)\b",
    re.IGNORECASE,
)


def count_anchors(body: str) -> dict[str, bool]:
    """Return a dict of which engagement anchors are present in the body."""
    if not body:
        return {}
    return {
        "number": bool(NUMBER_RE.search(body)),
        "currency": bool(CURRENCY_RE.search(body)),
        "percent": bool(PERCENT_RE.search(body)),
        "question": bool(QUESTION_RE.search(body)),
        "peer_or_locality": bool(PEER_RE.search(body)),
        "specific_time": bool(SPECIFIC_TIME_RE.search(body)),
        "named_source": bool(NAMED_SOURCE_RE.search(body)),
        "social_proof": bool(SOCIAL_PROOF_RE.search(body)),
        "asking": bool(ASKING_RE.search(body)),
        "loss_aversion": bool(LOSS_AVERSION_RE.search(body)),
        "effort_ext": bool(EFFORT_EXT_RE.search(body)),
        "binary_cta": bool(BINARY_CTA_RE.search(body)),
    }


def check(
    body: str,
    *,
    plan: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    """
    Returns (passed, error, suggested_fix, modified_body).

    Permissive — only fails if the body has NO strong-engagement anchors at all.
    Bodies with at least 2 anchors pass. Bodies with 1 anchor pass with a note.
    """
    if not body:
        return True, None, None, body

    anchors = count_anchors(body)
    present = [k for k, v in anchors.items() if v]
    n = len(present)

    # Permissive — only fail bodies with truly weak engagement
    if n == 0:
        return (
            False,
            "Body has zero engagement anchors (no number, no question, no source, "
            "no peer comparison, no specific time, no asking, no loss aversion, "
            "no effort externalization, no binary CTA).",
            "Add AT LEAST one strong engagement anchor: a specific number "
            "(₹X / N% / N count), a peer/locality reference, a question to "
            "the merchant, or a binary CTA. Without any anchor the body is "
            "generic and will score 5 or below on engagement_compulsion.",
            body,
        )

    # Pass with optional advisory note for weak (1 anchor) bodies
    if n == 1:
        return (
            True,
            None,
            f"engagement_weak_only_{present[0]}: consider adding a peer/locality/asking lever",
            body,
        )

    return True, None, None, body
