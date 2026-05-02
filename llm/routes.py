"""
Model routing — maps a PURPOSE to the Groq model that should serve it.

Multi-model routing multiplexes free-tier rate-limit buckets (each model has
its own 30 RPM / TPM / RPD bucket). Combined headroom: ~32K TPM, ~120 RPM,
~17K RPD across the four models below.

Per-purpose mapping:
    DRAFT       — best free composition quality (llama-3.3-70b-versatile)
    REFINE      — second pass with a contrasting style (gpt-oss-120b)
    PLAN        — fast classifier for picking facts + levers (llama-3.1-8b-instant)
    SELF_SCORE  — fast 5-dim rubric judge (llama-3.1-8b-instant)
    CLASSIFY    — auto-reply / hostile / intent classifiers (llama-3.1-8b-instant)
    REPLY       — engaged-reply follow-up (qwen3-32b — highest RPM bucket)

Per-purpose fallback (used on 429 / transient errors):
    DRAFT      → REFINE bucket
    REFINE     → DRAFT bucket
    PLAN       → REPLY bucket
    SELF_SCORE → REPLY bucket
    CLASSIFY   → DRAFT bucket
    REPLY      → DRAFT bucket
"""

from __future__ import annotations

from enum import Enum


class Purpose(str, Enum):
    DRAFT = "DRAFT"
    REFINE = "REFINE"
    PLAN = "PLAN"
    SELF_SCORE = "SELF_SCORE"
    CLASSIFY = "CLASSIFY"
    REPLY = "REPLY"


# Primary model per purpose
PRIMARY_MODEL: dict[Purpose, str] = {
    Purpose.DRAFT: "llama-3.3-70b-versatile",
    Purpose.REFINE: "openai/gpt-oss-120b",
    Purpose.PLAN: "llama-3.1-8b-instant",
    Purpose.SELF_SCORE: "llama-3.1-8b-instant",
    Purpose.CLASSIFY: "llama-3.1-8b-instant",
    Purpose.REPLY: "qwen/qwen3-32b",
}

# Fallback model per purpose (used on 429 / transient errors)
FALLBACK_MODEL: dict[Purpose, str] = {
    Purpose.DRAFT: "openai/gpt-oss-120b",
    Purpose.REFINE: "llama-3.3-70b-versatile",
    Purpose.PLAN: "qwen/qwen3-32b",
    Purpose.SELF_SCORE: "qwen/qwen3-32b",
    Purpose.CLASSIFY: "llama-3.3-70b-versatile",
    Purpose.REPLY: "llama-3.3-70b-versatile",
}

# Default temperature per purpose (challenge brief recommends temperature=0 for
# determinism on DRAFT + SELF_SCORE; mild variation on REFINE + REPLY breaks
# bad-output loops on retry).
DEFAULT_TEMPERATURE: dict[Purpose, float] = {
    Purpose.DRAFT: 0.0,
    Purpose.REFINE: 0.3,
    Purpose.PLAN: 0.0,
    Purpose.SELF_SCORE: 0.0,
    Purpose.CLASSIFY: 0.0,
    Purpose.REPLY: 0.3,
}


# Maximum output tokens per purpose. DRAFT/REFINE bumped to 1600 because
# gpt-oss-120b is a reasoning model that consumes hidden CoT tokens before
# the visible JSON — at 800 it ran out mid-document on heavy prompts.
DEFAULT_MAX_TOKENS: dict[Purpose, int] = {
    Purpose.DRAFT: 1600,
    Purpose.REFINE: 1600,
    Purpose.PLAN: 600,
    Purpose.SELF_SCORE: 600,
    Purpose.CLASSIFY: 200,
    Purpose.REPLY: 600,
}


# All distinct primary models — used for pre-warming at startup
ALL_MODELS = sorted(set(PRIMARY_MODEL.values()))
