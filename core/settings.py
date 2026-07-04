"""
Centralized settings loaded from .env.

Usage:
    from core.settings import settings
    print(settings.GROQ_API_KEY)

All env vars are validated at import time via Pydantic.
Missing required vars raise a clear error before the app starts.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from submission/ root (one level up from core/)
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


class Settings(BaseSettings):
    """All runtime config. Validated at startup."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── LLM ─────────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = Field(..., description="Groq API key (gsk_*)")
    GROQ_API_KEY_BACKUP: str = Field("", description="Optional 2nd Groq key (round-robin)")
    GROQ_API_KEY_TERTIARY: str = Field("", description="Optional 3rd Groq key (round-robin)")
    GROQ_API_KEY_QUATERNARY: str = Field("", description="Optional 4th Groq key (round-robin)")
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # ─── Supabase (only required when SUPABASE_ENABLED=True) ─────────────────
    # Default to "" so the bot boots in-memory-only with just a Groq key (local
    # dev + judge-facing runs don't need Postgres). Production sets these in the
    # Render env and flips SUPABASE_ENABLED=True.
    SUPABASE_URL: str = ""
    SUPABASE_DB_HOST: str = ""
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_USER: str = ""
    SUPABASE_DB_PASSWORD: str = ""
    SUPABASE_DB_NAME: str = "postgres"
    SUPABASE_SERVICE_KEY: str = ""

    # ─── Admin ───────────────────────────────────────────────────────────────
    ADMIN_PASSWORD: str = "changeme"

    # ─── Bot identity ────────────────────────────────────────────────────────
    BOT_TEAM_NAME: str = "Romanch Roshan Singh"
    BOT_VERSION: str = "1.0.0"
    # Static submission timestamp — set when the bot is built/submitted.
    # The judge uses this to pin the version; should NOT be the live clock.
    BOT_SUBMITTED_AT: str = "2026-05-02T10:00:00Z"
    BOT_CONTACT_EMAIL: str = "romanchroshansingh@gmail.com"

    # ─── Runtime tuning ──────────────────────────────────────────────────────
    TICK_DEADLINE_SECONDS: int = 25
    REPLY_DEADLINE_SECONDS: int = 20
    TICK_CONCURRENCY: int = 8
    # Lowered 4→1 after judging feedback: when the harness fires multiple
    # distinct triggers (different kinds, same merchant) within minutes,
    # blocking everything after the first cost us trigger coverage.
    # High-urgency (≥3) triggers bypass this entirely — see should_send.
    CADENCE_GUARD_HOURS: int = 1
    # Max sends to one merchant within a rolling 24h window (Phase 5 — multi-
    # turn cadence). Default 3 (challenge brief §12.3 extra credit).
    MAX_SENDS_PER_MERCHANT_PER_24H: int = 3
    # If we sent to the merchant N hours ago and they have NOT replied since,
    # treat as long-silence and wait longer before pushing another send.
    LONG_SILENCE_BACKOFF_HOURS: int = 12
    SUPPRESSION_TTL_DAYS: int = 7
    BLOCK_TTL_DAYS: int = 30

    # ─── Logging ─────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Enable Supabase persistence layer (Phase C). Phase A+B runs in-memory only.
    SUPABASE_ENABLED: bool = False


settings = Settings()  # type: ignore[call-arg]  # pydantic-settings loads from env
