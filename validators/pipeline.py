"""
Validation pipeline — runs each validator in order. First failure short-circuits.

Order matters:
1. length        (cheap, fail-fast)
2. url_strip     (modifies body)
3. taboos        (cheap)
4. salutation    (cheap)
5. cta_shape     (cheap)
6. language      (cheap)
7. repetition    (medium — Levenshtein)
8. fabrication   (most expensive — only worth running on otherwise-clean bodies)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from validators import (
    cta_shape,
    fabrication,
    language,
    length,
    repetition,
    salutation,
    taboos,
    url_strip,
)


@dataclass
class ValidationResult:
    passed: bool
    error: str | None
    suggested_fix: str | None
    body: str
    failed_validator: str | None = None
    notes: list[str] | None = None


# Each validator must expose `check(body, **ctx) -> (passed, error, fix, body)`.
_PIPELINE: list[tuple[str, Callable[..., tuple[bool, str | None, str | None, str]]]] = [
    ("length", length.check),
    ("url_strip", url_strip.check),
    ("taboos", taboos.check),
    ("salutation", salutation.check),
    ("cta_shape", cta_shape.check),
    ("language", language.check),
    ("repetition", repetition.check),
    ("fabrication", fabrication.check),
]


def validate_pipeline(
    body: str,
    *,
    plan: dict[str, Any] | None = None,
    category: dict[str, Any] | None = None,
    merchant: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
    customer: dict[str, Any] | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
) -> ValidationResult:
    notes: list[str] = []
    current_body = body

    for name, validator in _PIPELINE:
        passed, err, fix, new_body = validator(
            current_body,
            plan=plan,
            category=category,
            merchant=merchant,
            trigger=trigger,
            customer=customer,
            conversation_history=conversation_history,
        )
        if new_body and new_body != current_body:
            current_body = new_body
            notes.append(f"{name}_modified_body")
        if not passed:
            return ValidationResult(
                passed=False,
                error=err,
                suggested_fix=fix,
                body=current_body,
                failed_validator=name,
                notes=notes,
            )
        if fix:  # validator passed but emitted advisory note
            notes.append(f"{name}_note: {fix}")

    return ValidationResult(
        passed=True,
        error=None,
        suggested_fix=None,
        body=current_body,
        failed_validator=None,
        notes=notes,
    )
