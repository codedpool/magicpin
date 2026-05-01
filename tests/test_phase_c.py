"""
Phase C verification — Supabase write-through state survives restart.

Strategy:
1. Start fresh (clean Supabase tables).
2. Push some contexts via the in-process WriteThroughStore.
3. Wait briefly for async writes to complete.
4. Read back from Supabase via a separate SupabaseStore — verify rows present.
5. Construct a fresh WriteThroughStore (simulates restart). Rehydrate. Verify
   memory was repopulated from Supabase.

Run from submission/:
    python -m tests.test_phase_c
or:
    pytest tests/test_phase_c.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

# Ensure we can import submission packages
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def _flush_writes(store, timeout: float = 5.0) -> None:
    """Wait for any in-flight async Supabase writes to finish."""
    deadline = time.monotonic() + timeout
    while store._inflight and time.monotonic() < deadline:
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_write_through_persists_and_rehydrates():
    from state.supabase import SupabaseStore
    from state.write_through import WriteThroughStore

    # ─── 1. Clean Supabase tables ────────────────────────────────────────────
    cleaner = SupabaseStore()
    await cleaner.connect()
    async with cleaner.pool.acquire() as conn:
        await conn.execute("TRUNCATE contexts, conversations, suppressions, blocked_merchants")
    await cleaner.close()

    # ─── 2. First "session" — push state through write-through ──────────────
    store_a = WriteThroughStore()
    await store_a.startup()

    accepted, _ = await store_a.put_context(
        scope="category",
        context_id="phase_c_test_dentists",
        version=1,
        payload={"slug": "dentists", "marker": "phase-c"},
        delivered_at="2026-05-02T12:00:00Z",
    )
    assert accepted

    accepted2, _ = await store_a.put_context(
        scope="merchant",
        context_id="phase_c_test_merchant",
        version=1,
        payload={"merchant_id": "phase_c_test_merchant", "category_slug": "dentists"},
        delivered_at="2026-05-02T12:01:00Z",
    )
    assert accepted2

    await store_a.append_conversation_turn(
        conversation_id="phase_c_conv_1",
        turn={"from": "vera", "body": "test message", "ts": "2026-05-02T12:02:00Z"},
        merchant_id="phase_c_test_merchant",
        send_as="vera",
    )

    await store_a.mark_suppression(
        merchant_id="phase_c_test_merchant",
        suppression_key="phase_c_test_key",
        ttl_days=1,
    )

    await store_a.mark_merchant_blocked(
        merchant_id="phase_c_blocked_merchant",
        reason="test",
        ttl_days=1,
    )

    await _flush_writes(store_a)

    # ─── 3. Independent Supabase check — rows are durably present ───────────
    checker = SupabaseStore()
    await checker.connect()
    ctx_rows = await checker.fetch_all_contexts()
    conv_rows = await checker.fetch_all_conversations()
    sup_rows = await checker.fetch_active_suppressions()
    blk_rows = await checker.fetch_active_blocks()
    await checker.close()

    ctx_ids = {r["context_id"] for r in ctx_rows}
    assert "phase_c_test_dentists" in ctx_ids
    assert "phase_c_test_merchant" in ctx_ids
    assert any(c["conversation_id"] == "phase_c_conv_1" for c in conv_rows)
    assert any(s["suppression_key"] == "phase_c_test_key" for s in sup_rows)
    assert any(b["merchant_id"] == "phase_c_blocked_merchant" for b in blk_rows)

    await store_a.shutdown()

    # ─── 4. Second "session" — fresh store, rehydrate, verify memory ────────
    store_b = WriteThroughStore()
    await store_b.startup()

    cat = await store_b.get_context("category", "phase_c_test_dentists")
    assert cat is not None
    assert cat.get("marker") == "phase-c"

    mer = await store_b.get_context("merchant", "phase_c_test_merchant")
    assert mer is not None

    conv = await store_b.get_conversation("phase_c_conv_1")
    assert conv is not None
    assert len(conv["turns"]) == 1

    is_sup = await store_b.is_suppressed("phase_c_test_merchant", "phase_c_test_key")
    assert is_sup is True

    is_blocked = await store_b.is_merchant_blocked("phase_c_blocked_merchant")
    assert is_blocked is True

    await store_b.shutdown()


# ─── manual run (non-pytest) ─────────────────────────────────────────────────

async def _main():
    print("─── Phase C: Supabase write-through + rehydrate ───")
    from state.supabase import SupabaseStore
    from state.write_through import WriteThroughStore

    print("[1/4] Cleaning Supabase tables...")
    cleaner = SupabaseStore()
    await cleaner.connect()
    async with cleaner.pool.acquire() as conn:
        await conn.execute("TRUNCATE contexts, conversations, suppressions, blocked_merchants")
    await cleaner.close()
    print("  ✓ tables truncated")

    print("[2/4] Session A — pushing state via WriteThroughStore...")
    store_a = WriteThroughStore()
    await store_a.startup()

    await store_a.put_context(
        "category", "phase_c_test_dentists", 1,
        {"slug": "dentists", "marker": "phase-c"},
        "2026-05-02T12:00:00Z",
    )
    await store_a.put_context(
        "merchant", "phase_c_test_merchant", 1,
        {"merchant_id": "phase_c_test_merchant", "category_slug": "dentists"},
        "2026-05-02T12:01:00Z",
    )
    await store_a.append_conversation_turn(
        "phase_c_conv_1",
        {"from": "vera", "body": "test message", "ts": "2026-05-02T12:02:00Z"},
        merchant_id="phase_c_test_merchant",
    )
    await store_a.mark_suppression("phase_c_test_merchant", "phase_c_test_key", 1)
    await store_a.mark_merchant_blocked("phase_c_blocked_merchant", "test", 1)
    await _flush_writes(store_a)
    print(f"  ✓ pushed 2 contexts + 1 conv + 1 suppression + 1 block (in-flight: {len(store_a._inflight)})")

    print("[3/4] Independent Supabase check...")
    checker = SupabaseStore()
    await checker.connect()
    ctx_rows = await checker.fetch_all_contexts()
    conv_rows = await checker.fetch_all_conversations()
    sup_rows = await checker.fetch_active_suppressions()
    blk_rows = await checker.fetch_active_blocks()
    await checker.close()
    print(f"  ✓ Supabase has: {len(ctx_rows)} contexts, {len(conv_rows)} convs, {len(sup_rows)} sups, {len(blk_rows)} blocks")

    await store_a.shutdown()

    print("[4/4] Session B — fresh store, rehydrate from Supabase...")
    store_b = WriteThroughStore()
    await store_b.startup()

    cat = await store_b.get_context("category", "phase_c_test_dentists")
    mer = await store_b.get_context("merchant", "phase_c_test_merchant")
    conv = await store_b.get_conversation("phase_c_conv_1")
    is_sup = await store_b.is_suppressed("phase_c_test_merchant", "phase_c_test_key")
    is_blk = await store_b.is_merchant_blocked("phase_c_blocked_merchant")

    print(f"  rehydrated category: {bool(cat)} (marker={cat.get('marker') if cat else None})")
    print(f"  rehydrated merchant: {bool(mer)}")
    print(f"  rehydrated conversation: {bool(conv)} (turns={len(conv['turns']) if conv else 0})")
    print(f"  rehydrated suppression: {is_sup}")
    print(f"  rehydrated block: {is_blk}")

    await store_b.shutdown()

    all_ok = all([
        cat and cat.get("marker") == "phase-c",
        mer is not None,
        conv and len(conv["turns"]) == 1,
        is_sup,
        is_blk,
    ])
    if all_ok:
        print("\n✅ Phase C: write-through + rehydrate verified.")
    else:
        print("\n❌ Phase C: rehydrate incomplete — investigate.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
