"""
Phase I + J verification — tick pipeline + adversarial robustness.

Phase I tests:
1. Single trigger → 1 action (happy path)
2. 5 triggers all for same merchant → 1 action (cadence/dedup)
3. Suppressed trigger → 0 actions
4. Blocked merchant → 0 actions
5. Expired trigger → 0 actions
6. Empty available_triggers → 0 actions

Phase J tests (adversarial robustness):
7. Trigger with novel kind → kind_default produces output
8. Trigger missing payload → graceful pass (no crash)
9. Trigger missing merchant_id → 0 actions, no crash
10. Merchant context never pushed for this id → 0 actions
11. Pathological body (very long string in payload) → no crash, validators apply

Run from submission/:
    PYTHONIOENCODING=utf-8 python -m tests.test_phase_ij
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = REPO_ROOT / "dataset"


def _load_seeds():
    cat = json.load(open(DATASET_DIR / "categories" / "dentists.json", encoding="utf-8"))
    merchants = json.load(open(DATASET_DIR / "merchants_seed.json", encoding="utf-8"))["merchants"]
    triggers = json.load(open(DATASET_DIR / "triggers_seed.json", encoding="utf-8"))["triggers"]
    return cat, merchants, triggers


async def _push_baseline(store, cat, merchants, triggers, trigger_ids: list[str]):
    """Push category, merchant, and selected trigger contexts."""
    await store.put_context("category", cat["slug"], 1, cat, "2026-05-02T00:00:00Z")
    for m in merchants:
        if m["category_slug"] == cat["slug"]:
            await store.put_context("merchant", m["merchant_id"], 1, m, "2026-05-02T00:00:00Z")
    for trg_id in trigger_ids:
        trg = next((t for t in triggers if t["id"] == trg_id), None)
        if trg:
            await store.put_context("trigger", trg["id"], 1, trg, "2026-05-02T00:00:00Z")


async def _main():
    print("═" * 78)
    print("  Phase I+J — Tick Pipeline + Adversarial Robustness")
    print("═" * 78)

    from llm.groq_client import get_groq
    from state.in_memory import InMemoryStore
    from pipeline.tick_loop import run_tick

    print("\n[setup] connecting Groq + prewarm...")
    groq = get_groq()
    await groq.connect()
    await groq.prewarm()

    cat, merchants, triggers = _load_seeds()

    # ─── 1. Happy path: single trigger → 1 action ──────────────────────────
    print("\n[1/11] happy path: single research_digest trigger")
    store = InMemoryStore()
    await _push_baseline(store, cat, merchants, triggers,
                         ["trg_001_research_digest_dentists"])
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=["trg_001_research_digest_dentists"],
        store=store,
    )
    assert len(actions) == 1, f"expected 1 action, got {len(actions)}: {actions}"
    assert actions[0]["merchant_id"] == "m_001_drmeera_dentist_delhi"
    assert actions[0]["conversation_id"].startswith("conv_"), f"conv_id: {actions[0]['conversation_id']}"
    assert "JIDA" in actions[0]["body"] or "jida" in actions[0]["body"].lower()
    print(f"  [OK] action shipped: conv_id={actions[0]['conversation_id']}, suppression={actions[0]['suppression_key']}")

    # ─── 2. Same merchant 5 triggers → 1 action (dedup) ─────────────────────
    print("\n[2/11] dedup: 5 triggers same merchant → 1 action")
    store = InMemoryStore()
    same_merchant_trigs = [
        "trg_001_research_digest_dentists",
        "trg_002_compliance_dci_radiograph",
        "trg_022_cde_webinar_dentists",
        "trg_023_competitor_opened_dentist",
    ]
    await _push_baseline(store, cat, merchants, triggers, same_merchant_trigs)
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=same_merchant_trigs,
        store=store,
    )
    assert len(actions) == 1, f"dedup should yield 1, got {len(actions)}"
    print(f"  [OK] 1 action / merchant per tick")

    # ─── 3. Suppressed trigger → 0 ──────────────────────────────────────────
    print("\n[3/11] suppressed trigger → 0 actions")
    store = InMemoryStore()
    await _push_baseline(store, cat, merchants, triggers,
                         ["trg_001_research_digest_dentists"])
    await store.mark_suppression(
        "m_001_drmeera_dentist_delhi",
        "research:dentists:2026-W17",
        ttl_days=7,
    )
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=["trg_001_research_digest_dentists"],
        store=store,
    )
    assert len(actions) == 0, f"suppressed trigger should be skipped: {actions}"
    print("  [OK] suppression honored")

    # ─── 4. Blocked merchant → 0 ────────────────────────────────────────────
    print("\n[4/11] blocked merchant → 0 actions")
    store = InMemoryStore()
    await _push_baseline(store, cat, merchants, triggers,
                         ["trg_001_research_digest_dentists"])
    await store.mark_merchant_blocked("m_001_drmeera_dentist_delhi", reason="test", ttl_days=30)
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=["trg_001_research_digest_dentists"],
        store=store,
    )
    assert len(actions) == 0, f"blocked merchant should be skipped: {actions}"
    print("  [OK] merchant block honored")

    # ─── 5. Expired trigger → 0 ─────────────────────────────────────────────
    print("\n[5/11] expired trigger → 0 actions")
    store = InMemoryStore()
    expired_trg = next(t for t in triggers if t["id"] == "trg_001_research_digest_dentists").copy()
    expired_trg["expires_at"] = "2020-01-01T00:00:00Z"  # in the past
    await store.put_context("category", cat["slug"], 1, cat, "2026-05-02T00:00:00Z")
    drmeera = next(m for m in merchants if m["merchant_id"] == "m_001_drmeera_dentist_delhi")
    await store.put_context("merchant", drmeera["merchant_id"], 1, drmeera, "2026-05-02T00:00:00Z")
    await store.put_context("trigger", expired_trg["id"], 1, expired_trg, "2026-05-02T00:00:00Z")
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=[expired_trg["id"]],
        store=store,
    )
    assert len(actions) == 0, f"expired trigger should be skipped: {actions}"
    print("  [OK] expired triggers filtered")

    # ─── 6. Empty available_triggers ───────────────────────────────────────
    print("\n[6/11] empty available_triggers → 0 actions")
    store = InMemoryStore()
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=[],
        store=store,
    )
    assert actions == [], f"empty input should give []: {actions}"
    print("  [OK] empty input -> []")

    # ─── 7. Novel kind → kind_default ───────────────────────────────────────
    print("\n[7/11] novel kind 'mystery_signal' → kind_default produces output")
    store = InMemoryStore()
    await store.put_context("category", cat["slug"], 1, cat, "2026-05-02T00:00:00Z")
    drmeera = next(m for m in merchants if m["merchant_id"] == "m_001_drmeera_dentist_delhi")
    await store.put_context("merchant", drmeera["merchant_id"], 1, drmeera, "2026-05-02T00:00:00Z")
    novel_trg = {
        "id": "trg_999_novel_unknown",
        "scope": "merchant",
        "kind": "mystery_signal_invented_by_judge",
        "source": "external",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "payload": {"observation": "Patient reviews mention wait-time 5x this week",
                    "suggested_action": "consider scheduling buffer"},
        "urgency": 2,
        "suppression_key": "novel:m_001:2026-W18",
        "expires_at": "2026-12-31T00:00:00Z",
    }
    await store.put_context("trigger", novel_trg["id"], 1, novel_trg, "2026-05-02T00:00:00Z")
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=[novel_trg["id"]],
        store=store,
    )
    assert len(actions) == 1, f"novel kind should still produce action via kind_default: {actions}"
    body = actions[0]["body"]
    assert len(body) > 30, f"body too short: {body!r}"
    print(f"  [OK] novel kind handled: {body[:120]!r}")

    # ─── 8. Missing payload → graceful ──────────────────────────────────────
    print("\n[8/11] trigger with empty payload → graceful")
    store = InMemoryStore()
    await store.put_context("category", cat["slug"], 1, cat, "2026-05-02T00:00:00Z")
    await store.put_context("merchant", drmeera["merchant_id"], 1, drmeera, "2026-05-02T00:00:00Z")
    sparse_trg = {
        "id": "trg_sparse",
        "scope": "merchant",
        "kind": "perf_dip",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "payload": {},  # empty
        "suppression_key": "sparse:m_001",
    }
    await store.put_context("trigger", sparse_trg["id"], 1, sparse_trg, "2026-05-02T00:00:00Z")
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=[sparse_trg["id"]],
        store=store,
    )
    # Either 0 or 1 — both acceptable. Critical: NO CRASH.
    print(f"  [OK] no crash; actions returned: {len(actions)}")

    # ─── 9. Missing merchant_id → 0, no crash ───────────────────────────────
    print("\n[9/11] trigger missing merchant_id → 0 actions, no crash")
    store = InMemoryStore()
    await store.put_context("category", cat["slug"], 1, cat, "2026-05-02T00:00:00Z")
    bad_trg = {
        "id": "trg_no_mid",
        "scope": "merchant",
        "kind": "research_digest",
        # no merchant_id
        "payload": {},
        "suppression_key": "bad:no_mid",
    }
    await store.put_context("trigger", bad_trg["id"], 1, bad_trg, "2026-05-02T00:00:00Z")
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=[bad_trg["id"]],
        store=store,
    )
    assert len(actions) == 0, f"trigger with no merchant_id should be skipped: {actions}"
    print("  [OK] no crash, gracefully skipped")

    # ─── 10. Merchant context not pushed → 0 ────────────────────────────────
    print("\n[10/11] merchant_id references unpushed merchant → 0 actions")
    store = InMemoryStore()
    await store.put_context("category", cat["slug"], 1, cat, "2026-05-02T00:00:00Z")
    orphan_trg = {
        "id": "trg_orphan",
        "scope": "merchant",
        "kind": "research_digest",
        "merchant_id": "m_999_never_pushed",
        "payload": {"top_item_id": "d_x"},
        "suppression_key": "orphan",
    }
    await store.put_context("trigger", orphan_trg["id"], 1, orphan_trg, "2026-05-02T00:00:00Z")
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=[orphan_trg["id"]],
        store=store,
    )
    assert len(actions) == 0, f"orphan merchant should yield 0: {actions}"
    print("  [OK] no crash, 0 actions")

    # ─── 11. Pathological payload (very long string) ────────────────────────
    print("\n[11/11] pathological 5K-char string in payload → no crash")
    store = InMemoryStore()
    await store.put_context("category", cat["slug"], 1, cat, "2026-05-02T00:00:00Z")
    await store.put_context("merchant", drmeera["merchant_id"], 1, drmeera, "2026-05-02T00:00:00Z")
    huge_trg = {
        "id": "trg_huge",
        "scope": "merchant",
        "kind": "research_digest",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "payload": {"giant_field": "X" * 5000, "other": "ok"},
        "suppression_key": "huge:m_001",
    }
    await store.put_context("trigger", huge_trg["id"], 1, huge_trg, "2026-05-02T00:00:00Z")
    actions = await run_tick(
        now_iso="2026-05-02T10:00:00Z",
        available_triggers=[huge_trg["id"]],
        store=store,
    )
    # The compose may succeed or refuse — both are acceptable. Critical: NO CRASH.
    print(f"  [OK] no crash; actions: {len(actions)}")

    await groq.close()

    print()
    print("═" * 78)
    print("  ✅ Phase I+J: tick pipeline + adversarial robustness verified.")
    print("═" * 78)


if __name__ == "__main__":
    asyncio.run(_main())
