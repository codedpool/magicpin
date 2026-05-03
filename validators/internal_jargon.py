"""
Internal-jargon validator — judge penalizes "exposing internal jargon to merchant" -1
(see judge_simulator.py line 478). Strips template-like field tokens that
sometimes leak from the LLM into the user-visible body.
"""

from __future__ import annotations

import re
from typing import Any


# Patterns that should NEVER appear in a merchant-visible body
_JARGON_PATTERNS = [
    # Field-access notation — "trigger.kind", "merchant.identity.name"
    r"\b(?:trigger|merchant|category|customer|action|payload)\.[a-z_]+(?:\.[a-z_]+)?\b",
    # Variable-style identifiers — "merchant_id=", "self_scores=", "composer_version="
    r"\b[a-z_]+_(?:id|scores?|version|count|key|slug)\s*[=:]\s*[\w\d.\-]+",
    # Template parameter placeholders — "{{1}}", "${name}"
    r"\{\{\s*\d+\s*\}\}",
    r"\$\{[A-Za-z_][A-Za-z0-9_]*\}",
    # Internal stage labels — "PLAN stage", "DRAFT output", "REFINE pass"
    r"\b(?:PLAN|DRAFT|REFINE|VALIDATE|SELF[_-]SCORE|COMPOSE)\s+(?:stage|output|pass|step)\b",
    # Bot-meta — "as an AI", "I am an LLM"
    r"\bas an (?:AI|LLM|assistant)\b",
    r"\bI(?:'m| am) (?:a|an) (?:AI|LLM|chatbot|automated)\b",
    # JSON-like leak — `{"body":` or `"rationale":` appearing in the body
    r'"(?:body|rationale|cta|send_as|suppression_key)"\s*:',
    # Verbose internal levers list — "levers=[...]"
    r"\blevers\s*=\s*\[",
]

_JARGON_RE = re.compile("|".join(_JARGON_PATTERNS), re.IGNORECASE)


def check(
    body: str,
    **_kwargs: Any,
) -> tuple[bool, str | None, str | None, str]:
    if not body:
        return True, None, None, body
    m = _JARGON_RE.search(body)
    if m:
        return (
            False,
            f"Body contains internal jargon: {m.group()!r}",
            "Remove implementation/internal labels (field paths like 'trigger.kind', "
            "stage labels like 'PLAN stage', template placeholders like '{{1}}', "
            "or bot-meta like 'as an AI'). Rephrase as plain merchant-readable text.",
            body,
        )
    return True, None, None, body
