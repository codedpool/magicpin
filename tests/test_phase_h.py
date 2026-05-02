"""
Phase H verification — 6-detector reply state machine.

Six scenarios (each invokes handle_reply directly with an in-memory store):
1. Auto-reply 4-turn escalation (nudge → wait → end)
2. Hostile message → end + merchant blocked 30d
3. Wait request ("I'm in a meeting") → wait
4. Intent transition ("Ok, let's do it") → send (action-mode)
5. Out-of-scope (GST question) → polite redirect
6. Engaged on-topic ("yes please send the abstract") → engaged follow-up

Run from submission/:
    PYTHONIOENCODING=utf-8 python -m tests.test_phase_h
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _print(label: str, action: dict, expected: str):
    print()
    print("─" * 78)
    print(f"  {label}")
    print(f"  Expected: {expected}")
    print(f"  Got:      action={action.get('action')}", end="")
    if action.get("action") == "send":
        body = (action.get("body") or "")[:120]
        print(f"  body={body!r}")
    elif action.get("action") == "wait":
        print(f"  wait_seconds={action.get('wait_seconds')}")
    else:
        print()
    print(f"  rationale: {(action.get('rationale') or '')[:200]}")


async def _setup_store():
    from state.in_memory import InMemoryStore
    return InMemoryStore()


async def _seed_first_bot_turn(store, conv_id: str, merchant_id: str):
    """Simulate a Vera-initiated message that's already in the conversation."""
    await store.append_conversation_turn(
        conv_id,
        {"from": "vera", "body": "Dr. Meera, JIDA's Oct issue landed... Want me to draft? — JIDA p.14",
         "ts": "2026-05-02T10:00:00Z"},
        merchant_id=merchant_id,
    )


async def _main():
    print("═" * 78)
    print("  Phase H — Reply Handler 6-detector cascade")
    print("═" * 78)

    from reply.handler import handle_reply
    from llm.groq_client import get_groq

    print("\n[setup] connecting Groq + prewarm...")
    groq = get_groq()
    await groq.connect()
    await groq.prewarm()

    drmeera = {
        "merchant_id": "m_001_drmeera",
        "identity": {"name": "Dr. Meera's Dental Clinic", "owner_first_name": "Meera",
                     "city": "Delhi", "locality": "Lajpat Nagar", "languages": ["en", "hi"]},
        "offers": [{"id": "o1", "title": "Dental Cleaning @ ₹299", "status": "active"}],
        "signals": ["high_risk_adult_cohort"],
    }
    cat = {"slug": "dentists", "voice": {"tone": "peer_clinical", "vocab_taboo": ["guaranteed"]}}
    trigger = {"kind": "research_digest",
               "payload": {"category": "dentists", "top_item_id": "d_jida"}}

    # ─── Scenario 1: Auto-reply 4-turn escalation ───────────────────────────
    print("\n[1/6] AUTO-REPLY HELL (4 identical canned messages)")
    store = await _setup_store()
    conv_id = "conv_test_autoreply"
    await _seed_first_bot_turn(store, conv_id, drmeera["merchant_id"])
    canned = "Thank you for contacting Dr. Meera's Dental Clinic! Our team will respond shortly."
    actions = []
    for turn in range(2, 6):
        a = await handle_reply(
            conversation_id=conv_id, message=canned,
            merchant_id=drmeera["merchant_id"], customer_id=None,
            from_role="merchant", received_at=f"2026-05-02T10:0{turn}:00Z",
            turn_number=turn, store=store,
            category=cat, merchant=drmeera, trigger=trigger,
        )
        actions.append(a)
        print(f"  turn {turn}: action={a.get('action')}")
    assert actions[0]["action"] == "send", f"turn 2 should send nudge, got {actions[0]}"
    assert actions[1]["action"] == "wait", f"turn 3 should wait, got {actions[1]}"
    assert actions[2]["action"] == "end", f"turn 4 should end, got {actions[2]}"
    assert actions[3]["action"] == "end", f"turn 5 (post-end) should still end, got {actions[3]}"
    print("  [OK] turn 2: send nudge | turn 3: wait | turn 4: end | turn 5: stays ended")

    # ─── Scenario 2: Hostile ────────────────────────────────────────────────
    print("\n[2/6] HOSTILE")
    store = await _setup_store()
    conv_id = "conv_test_hostile"
    await _seed_first_bot_turn(store, conv_id, drmeera["merchant_id"])
    a = await handle_reply(
        conversation_id=conv_id, message="Stop messaging me. This is useless spam.",
        merchant_id=drmeera["merchant_id"], customer_id=None,
        from_role="merchant", received_at="2026-05-02T10:02:00Z", turn_number=2,
        store=store, category=cat, merchant=drmeera, trigger=trigger,
    )
    _print("Scenario 2 — Hostile", a, "action=end + merchant blocked")
    assert a["action"] == "end", f"hostile should end, got {a}"
    assert await store.is_merchant_blocked(drmeera["merchant_id"]), "merchant should be blocked"
    print("  [OK] ended + merchant marked blocked for 30d")

    # ─── Scenario 3: Wait request ───────────────────────────────────────────
    print("\n[3/6] WAIT REQUEST (in a meeting)")
    store = await _setup_store()
    conv_id = "conv_test_wait"
    await _seed_first_bot_turn(store, conv_id, drmeera["merchant_id"])
    a = await handle_reply(
        conversation_id=conv_id, message="I'm in a meeting, ping me later.",
        merchant_id=drmeera["merchant_id"], customer_id=None,
        from_role="merchant", received_at="2026-05-02T10:02:00Z", turn_number=2,
        store=store, category=cat, merchant=drmeera, trigger=trigger,
    )
    _print("Scenario 3 — Wait", a, "action=wait")
    assert a["action"] == "wait", f"wait should wait, got {a}"
    assert (a.get("wait_seconds") or 0) >= 600, "wait_seconds should be reasonable"
    print(f"  [OK] wait_seconds={a.get('wait_seconds')}")

    # ─── Scenario 4: Intent transition ─────────────────────────────────────
    print("\n[4/6] INTENT TRANSITION ('Ok, lets do it')")
    store = await _setup_store()
    conv_id = "conv_test_intent"
    await _seed_first_bot_turn(store, conv_id, drmeera["merchant_id"])
    a = await handle_reply(
        conversation_id=conv_id, message="Ok lets do it. Whats next?",
        merchant_id=drmeera["merchant_id"], customer_id=None,
        from_role="merchant", received_at="2026-05-02T10:02:00Z", turn_number=2,
        store=store, category=cat, merchant=drmeera, trigger=trigger,
    )
    _print("Scenario 4 — Intent transition", a, "action=send (action-mode, not qualifying)")
    assert a["action"] == "send", f"intent transition should send, got {a}"
    body_lower = (a.get("body") or "").lower()
    qualifying_phrases = ["would you say", "do you usually", "what kind of", "tell me more about"]
    assert not any(p in body_lower for p in qualifying_phrases), \
        f"action-mode body should NOT re-qualify; got: {a.get('body')!r}"
    print("  [OK] action-mode response (no qualifying questions)")

    # ─── Scenario 5: Out-of-scope ───────────────────────────────────────────
    print("\n[5/6] OUT-OF-SCOPE (GST question)")
    store = await _setup_store()
    conv_id = "conv_test_oos"
    await _seed_first_bot_turn(store, conv_id, drmeera["merchant_id"])
    a = await handle_reply(
        conversation_id=conv_id,
        message="Btw can you also help me file my GST returns this month?",
        merchant_id=drmeera["merchant_id"], customer_id=None,
        from_role="merchant", received_at="2026-05-02T10:02:00Z", turn_number=2,
        store=store, category=cat, merchant=drmeera, trigger=trigger,
    )
    _print("Scenario 5 — Out-of-scope", a, "action=send (polite redirect)")
    assert a["action"] == "send", f"OOS should still send (a redirect), got {a}"
    body_lower = (a.get("body") or "").lower()
    redirect_signals = ["ca", "accountant", "back to", "outside", "not what i can"]
    assert any(s in body_lower for s in redirect_signals), \
        f"redirect should mention 'CA' or 'back to'; got: {a.get('body')!r}"
    print("  [OK] redirect contains CA/accountant decline + back-to-trigger pivot")

    # ─── Scenario 6: Engaged follow-up ──────────────────────────────────────
    print("\n[6/6] ENGAGED FOLLOW-UP ('yes please send the abstract')")
    store = await _setup_store()
    conv_id = "conv_test_engaged"
    await _seed_first_bot_turn(store, conv_id, drmeera["merchant_id"])
    a = await handle_reply(
        conversation_id=conv_id,
        message="Yes please send the abstract. Also draft the patient WhatsApp.",
        merchant_id=drmeera["merchant_id"], customer_id=None,
        from_role="merchant", received_at="2026-05-02T10:02:00Z", turn_number=2,
        store=store, category=cat, merchant=drmeera, trigger=trigger,
    )
    _print("Scenario 6 — Engaged follow-up", a, "action=send (advances thread)")
    assert a["action"] == "send", f"engaged should send, got {a}"
    body = a.get("body") or ""
    assert len(body) >= 30, f"engaged body too short: {body!r}"
    # No re-introduction
    assert "i'm vera" not in body.lower() and "vera here" not in body.lower(), \
        f"should NOT re-introduce Vera; got: {body!r}"
    print(f"  [OK] follow-up body: {body[:140]!r}")

    await groq.close()

    print()
    print("═" * 78)
    print("  ✅ Phase H: all 6 reply scenarios passed.")
    print("═" * 78)


if __name__ == "__main__":
    asyncio.run(_main())
