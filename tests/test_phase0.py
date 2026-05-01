"""
Phase 0 verification — ensures environment + Supabase are healthy before Phase A.

Run from submission/ root:
    python -m tests.test_phase0
or with pytest:
    pytest tests/test_phase0.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env from submission/ root
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


REQUIRED_ENV_VARS = [
    "GROQ_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_DB_HOST",
    "SUPABASE_DB_PORT",
    "SUPABASE_DB_USER",
    "SUPABASE_DB_PASSWORD",
    "SUPABASE_DB_NAME",
    "SUPABASE_SERVICE_KEY",
    "ADMIN_PASSWORD",
    "BOT_TEAM_NAME",
    "BOT_VERSION",
]

EXPECTED_TABLES = ["contexts", "conversations", "suppressions", "blocked_merchants"]


def test_env_file_exists():
    assert ENV_PATH.exists(), f".env not found at {ENV_PATH}"


def test_required_env_vars_present():
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    assert not missing, f"Missing env vars: {missing}"


def test_groq_key_format():
    key = os.getenv("GROQ_API_KEY", "")
    assert key.startswith("gsk_"), "GROQ_API_KEY should start with 'gsk_'"
    assert len(key) > 20, "GROQ_API_KEY looks too short"


def test_supabase_service_key_format():
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    assert key.startswith("eyJ"), "SUPABASE_SERVICE_KEY should be a JWT (starts with 'eyJ')"
    assert key.count(".") == 2, "SUPABASE_SERVICE_KEY should have 3 JWT segments"


@pytest.mark.asyncio
async def test_supabase_postgres_connection():
    """Connect to Supabase Postgres and run SELECT 1."""
    import asyncpg

    conn = await asyncpg.connect(
        host=os.getenv("SUPABASE_DB_HOST"),
        port=int(os.getenv("SUPABASE_DB_PORT", "5432")),
        user=os.getenv("SUPABASE_DB_USER"),
        password=os.getenv("SUPABASE_DB_PASSWORD"),
        database=os.getenv("SUPABASE_DB_NAME"),
        ssl="require",
        timeout=10,
    )
    try:
        result = await conn.fetchval("SELECT 1")
        assert result == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_all_4_tables_exist():
    """Verify all 4 expected tables exist in the public schema."""
    import asyncpg

    conn = await asyncpg.connect(
        host=os.getenv("SUPABASE_DB_HOST"),
        port=int(os.getenv("SUPABASE_DB_PORT", "5432")),
        user=os.getenv("SUPABASE_DB_USER"),
        password=os.getenv("SUPABASE_DB_PASSWORD"),
        database=os.getenv("SUPABASE_DB_NAME"),
        ssl="require",
        timeout=10,
    )
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY($1::text[])",
            EXPECTED_TABLES,
        )
        found = {r["table_name"] for r in rows}
        missing = set(EXPECTED_TABLES) - found
        assert not missing, f"Missing tables: {missing}"
    finally:
        await conn.close()


# ─── manual run (non-pytest) ─────────────────────────────────────────────────

async def _main():
    print(f"Loading .env from: {ENV_PATH}")
    print(f"  exists: {ENV_PATH.exists()}")
    print()

    print("Required env vars:")
    for v in REQUIRED_ENV_VARS:
        val = os.getenv(v)
        status = "✓ SET" if val else "✗ MISSING"
        # mask sensitive values
        display = "<set>" if val and any(s in v for s in ("KEY", "PASSWORD")) else (val or "")
        print(f"  {status:10} {v} = {display}")
    print()

    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        print(f"FAIL — missing env vars: {missing}")
        sys.exit(1)

    print("Testing Supabase Postgres connection...")
    try:
        import asyncpg

        conn = await asyncpg.connect(
            host=os.getenv("SUPABASE_DB_HOST"),
            port=int(os.getenv("SUPABASE_DB_PORT", "5432")),
            user=os.getenv("SUPABASE_DB_USER"),
            password=os.getenv("SUPABASE_DB_PASSWORD"),
            database=os.getenv("SUPABASE_DB_NAME"),
            ssl="require",
            timeout=10,
        )
        result = await conn.fetchval("SELECT 1")
        print(f"  ✓ SELECT 1 → {result}")

        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY($1::text[])",
            EXPECTED_TABLES,
        )
        found = sorted({r["table_name"] for r in rows})
        print(f"  ✓ Tables found: {found}")
        missing_tables = set(EXPECTED_TABLES) - set(found)
        if missing_tables:
            print(f"  ✗ Missing tables: {missing_tables}")
            sys.exit(1)

        await conn.close()
        print()
        print("✅ Phase 0 environment verified — all checks passed.")
    except Exception as e:
        print(f"  ✗ Postgres connection failed: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
