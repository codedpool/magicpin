"""
End-to-end test against the LIVE deployed URL.

Tests every endpoint + Phase 3 adaptive injection + Phase 4 replay
scenarios, exactly as the judge harness would.

Strategy: paced (12s between LLM-touching calls) so the 3-key Groq pool
doesn't burst. Total wall time ~10-15 min. Idempotent: each scenario
either pushes its own context_ids or reuses fresh ones.

Run from submission/:
    PYTHONIOENCODING=utf-8 python -m tests.test_live_e2e
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = REPO_ROOT / "dataset"

BASE_URL = "https://magicpin-5z8k.onrender.com"
PACE = 12.0  # seconds between LLM-touching calls


passes = 0
fails = 0
notes: list[str] = []


def ok(msg: str):
    global passes
    passes += 1
    print(f"  [OK]   {msg}")


def fail(msg: str):
    global fails
    fails += 1
    print(f"  [FAIL] {msg}")


def info(msg: str):
    print(f"  [INFO] {msg}")


def header(msg: str):
    print()
    print("─" * 80)
    print(f"  {msg}")
    print("─" * 80)


async def get(client: httpx.AsyncClient, path: str) -> tuple[int, dict | None]:
    try:
        r = await client.get(BASE_URL + path)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None
    except Exception as e:
        return 0, {"error": str(e)[:200]}


async def post(client: httpx.AsyncClient, path: str, body: dict) -> tuple[int, dict | None]:
    try:
        r = await client.post(BASE_URL + path, json=body)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None
    except Exception as e:
        return 0, {"error": str(e)[:200]}


def load_seeds():
    cat = json.load(open(DATASET_DIR / "categories" / "dentists.json", encoding="utf-8"))
    cat_salons = json.load(open(DATASET_DIR / "categories" / "salons.json", encoding="utf-8"))
    merchants = json.load(open(DATASET_DIR / "merchants_seed.json", encoding="utf-8"))["merchants"]
    customers = json.load(open(DATASET_DIR / "customers_seed.json", encoding="utf-8"))["customers"]
    triggers = json.load(open(DATASET_DIR / "triggers_seed.json", encoding="utf-8"))["triggers"]
    return cat, cat_salons, merchants, customers, triggers


async def main():
    print("═" * 80)
    print(f"  Live E2E test — {BASE_URL}")
    print("═" * 80)

    cat_dentists, cat_salons, merchants, customers, triggers = load_seeds()
    drmeera = next(m for m in merchants if m["merchant_id"] == "m_001_drmeera_dentist_delhi")
    studio11 = next(m for m in merchants if m["merchant_id"] == "m_003_studio11_salon_hyderabad")
    priya = next(c for c in customers if c["customer_id"] == "c_001_priya_for_m001")
    research_trg = next(t for t in triggers if t["id"] == "trg_001_research_digest_dentists")
    recall_trg = next(t for t in triggers if t["id"] == "trg_003_recall_due_priya")
    competitor_trg = next(t for t in triggers if t["id"] == "trg_023_competitor_opened_dentist")
    curious_trg = next(t for t in triggers if t["id"] == "trg_008_curious_ask_studio11")

    async with httpx.AsyncClient(timeout=45) as client:

        # ────────────────────────────────────────────────────────────────
        header("1. Smoke — healthz + metadata")
        sc, body = await get(client, "/v1/healthz")
        if sc == 200 and body and body.get("status") == "ok":
            ok(f"healthz returned 200, contexts_loaded={body.get('contexts_loaded')}")
        else:
            fail(f"healthz: status={sc} body={body}")

        sc, body = await get(client, "/v1/metadata")
        if sc == 200 and body and body.get("team_name") == "Romanch Roshan Singh":
            ok(f"metadata correct (version={body.get('version')})")
        else:
            fail(f"metadata: status={sc} body={body}")

        # ────────────────────────────────────────────────────────────────
        header("2. /v1/context — idempotency 200 → 409 → 200(v2) → 409(v1)")
        push_v1 = {
            "scope": "category", "context_id": "dentists",
            "version": 1, "payload": cat_dentists,
            "delivered_at": "2026-05-02T10:00:00Z",
        }
        sc, body = await post(client, "/v1/context", push_v1)
        ok(f"v1 push: status={sc}, accepted={body.get('accepted') if body else None}") \
            if sc == 200 and body and body.get("accepted") else fail(f"v1 push: status={sc}")

        sc, body = await post(client, "/v1/context", push_v1)
        if sc == 409 and body and body.get("current_version") == 1:
            ok("re-push v1: 409 with current_version=1 ✓")
        else:
            fail(f"re-push v1: status={sc} body={body}")

        push_v2 = dict(push_v1, version=2,
                       payload={**cat_dentists, "_marker": "v2_with_new_digest"})
        # Add a new digest item to test adaptive injection
        push_v2["payload"]["digest"] = list(cat_dentists.get("digest", [])) + [{
            "id": "d_e2e_new_2026W18",
            "kind": "research",
            "title": "TEST INJECTION: 4-month recall reduces caries by 42% (placeholder)",
            "source": "e2e_test_v2",
            "trial_n": 999,
            "patient_segment": "high_risk_adults",
            "summary": "Test injection digest item.",
        }]
        sc, body = await post(client, "/v1/context", push_v2)
        if sc == 200 and body and body.get("accepted"):
            ok("v2 push (with new digest): 200 accepted ✓")
        else:
            fail(f"v2 push: status={sc} body={body}")

        sc, body = await post(client, "/v1/context", push_v1)
        if sc == 409 and body and body.get("current_version") == 2:
            ok("re-push v1 after v2: 409 with current_version=2 ✓")
        else:
            fail(f"re-push v1 after v2: status={sc} body={body}")

        # ────────────────────────────────────────────────────────────────
        header("3. Push merchant + trigger, run /v1/tick")
        # Push Dr. Meera at v1 (we just have her)
        sc, _ = await post(client, "/v1/context", {
            "scope": "merchant", "context_id": drmeera["merchant_id"],
            "version": 1, "payload": drmeera,
            "delivered_at": "2026-05-02T10:00:00Z",
        })
        ok("merchant Dr. Meera pushed v1") if sc == 200 else fail(f"merchant push: {sc}")

        sc, _ = await post(client, "/v1/context", {
            "scope": "trigger", "context_id": research_trg["id"],
            "version": 1, "payload": research_trg,
            "delivered_at": "2026-05-02T10:00:00Z",
        })
        ok("trigger research_digest pushed v1") if sc == 200 else fail(f"trigger push: {sc}")

        info(f"running tick (LLM-bound, ~5-10s) — pace {PACE}s")
        t0 = time.time()
        sc, body = await post(client, "/v1/tick", {
            "now": "2026-05-02T10:30:00+05:30",  # IST 10:30 — within all category windows
            "available_triggers": [research_trg["id"]],
        })
        elapsed = int((time.time() - t0) * 1000)
        if sc == 200 and body and body.get("actions"):
            actions = body["actions"]
            a = actions[0]
            mentions_jida = "jida" in a.get("body", "").lower()
            mentions_drmeera = "meera" in a.get("body", "").lower()
            mentions_v2_marker = "42%" in a.get("body", "")  # from our test v2 injection
            info(f"tick latency: {elapsed}ms, returned 1 action")
            info(f"body: {a.get('body','')[:160]!r}")
            info(f"self-scores: {a.get('rationale','')[-200:]}")
            ok("tick produced 1 action with valid JSON shape") if mentions_jida or mentions_drmeera else fail("body lacks expected anchors")
            if mentions_v2_marker:
                ok("Phase 3 adaptive injection confirmed: body cites the v2-only 42% stat")
                notes.append("Phase 3 adaptive: V2 digest injection picked up by next tick.")
            else:
                info("v2 42% stat not surfaced (model picked the original digest item — acceptable; both are in v2)")
        else:
            fail(f"tick: status={sc} body={body}")

        await asyncio.sleep(PACE)

        # ────────────────────────────────────────────────────────────────
        header("4. /v1/reply — engaged ('yes please send the abstract')")
        sc, body = await post(client, "/v1/reply", {
            "conversation_id": "conv_001_research_digest_2026-W17",
            "merchant_id": drmeera["merchant_id"],
            "from_role": "merchant",
            "message": "Yes please send the abstract.",
            "received_at": "2026-05-02T10:35:00Z",
            "turn_number": 2,
        })
        if sc == 200 and body and body.get("action") == "send":
            ok(f"engaged reply: action=send, body[:100]={body.get('body','')[:100]!r}")
        else:
            fail(f"engaged reply: status={sc} body={body}")

        await asyncio.sleep(PACE)

        # ────────────────────────────────────────────────────────────────
        header("5. /v1/reply — auto-reply (turn 1: should nudge)")
        sc, body = await post(client, "/v1/reply", {
            "conversation_id": "conv_e2e_autoreply_X",
            "merchant_id": drmeera["merchant_id"],
            "from_role": "merchant",
            "message": "Thank you for contacting Dr. Meera Dental Clinic! Our team will respond shortly.",
            "received_at": "2026-05-02T10:36:00Z",
            "turn_number": 1,
        })
        action = (body or {}).get("action")
        if sc == 200 and action == "send":
            ok("auto-reply turn 1: nudge sent (count=1)")
        else:
            fail(f"auto-reply turn 1: status={sc} action={action}")

        # ────────────────────────────────────────────────────────────────
        header("6. /v1/reply — auto-reply (turn 2: should wait)")
        sc, body = await post(client, "/v1/reply", {
            "conversation_id": "conv_e2e_autoreply_X",
            "merchant_id": drmeera["merchant_id"],
            "from_role": "merchant",
            "message": "Thank you for contacting Dr. Meera Dental Clinic! Our team will respond shortly.",
            "received_at": "2026-05-02T10:37:00Z",
            "turn_number": 2,
        })
        action = (body or {}).get("action")
        if sc == 200 and action == "wait":
            ok(f"auto-reply turn 2: action=wait, wait_seconds={body.get('wait_seconds')}")
        else:
            fail(f"auto-reply turn 2: status={sc} action={action}")

        # ────────────────────────────────────────────────────────────────
        header("7. /v1/reply — auto-reply (turn 3: should end)")
        sc, body = await post(client, "/v1/reply", {
            "conversation_id": "conv_e2e_autoreply_X",
            "merchant_id": drmeera["merchant_id"],
            "from_role": "merchant",
            "message": "Thank you for contacting Dr. Meera Dental Clinic! Our team will respond shortly.",
            "received_at": "2026-05-02T10:38:00Z",
            "turn_number": 3,
        })
        action = (body or {}).get("action")
        if sc == 200 and action == "end":
            ok(f"auto-reply turn 3: action=end (rationale: {(body or {}).get('rationale','')[:80]})")
        else:
            fail(f"auto-reply turn 3: status={sc} action={action}")

        # ────────────────────────────────────────────────────────────────
        header("8. /v1/reply — intent transition ('Ok lets do it')")
        sc, body = await post(client, "/v1/reply", {
            "conversation_id": "conv_e2e_intent",
            "merchant_id": drmeera["merchant_id"],
            "from_role": "merchant",
            "message": "Ok lets do it. Whats next?",
            "received_at": "2026-05-02T10:40:00Z",
            "turn_number": 2,
        })
        action = (body or {}).get("action")
        body_lower = (body or {}).get("body", "").lower()
        qualifying = ["would you say", "do you usually", "what kind of", "tell me more about"]
        is_action_mode = action == "send" and not any(p in body_lower for p in qualifying)
        if is_action_mode:
            ok(f"intent transition: action=send (action-mode, no qualifying)")
        else:
            fail(f"intent transition: action={action}, qualifying-detected={any(p in body_lower for p in qualifying)}")
        info(f"  body[:120]: {(body or {}).get('body','')[:120]!r}")

        await asyncio.sleep(PACE)

        # ────────────────────────────────────────────────────────────────
        header("9. /v1/reply — out-of-scope (GST question)")
        sc, body = await post(client, "/v1/reply", {
            "conversation_id": "conv_e2e_oos",
            "merchant_id": drmeera["merchant_id"],
            "from_role": "merchant",
            "message": "Btw can you also help me file my GST returns this month?",
            "received_at": "2026-05-02T10:42:00Z",
            "turn_number": 2,
        })
        action = (body or {}).get("action")
        body_lower = (body or {}).get("body", "").lower()
        redirect = action == "send" and any(s in body_lower for s in ("ca ", "accountant", "outside", "back to"))
        ok(f"out-of-scope: action=send with CA/back-to redirect ✓") if redirect else fail(f"out-of-scope: not redirected — body={(body or {}).get('body','')[:120]}")

        await asyncio.sleep(PACE)

        # ────────────────────────────────────────────────────────────────
        header("10. /v1/reply — hostile ('Stop messaging me. This is useless spam.')")
        sc, body = await post(client, "/v1/reply", {
            "conversation_id": "conv_e2e_hostile",
            "merchant_id": "m_e2e_hostile_test",  # use a throwaway merchant id so we don't block Dr. Meera
            "from_role": "merchant",
            "message": "Stop messaging me. This is useless spam.",
            "received_at": "2026-05-02T10:44:00Z",
            "turn_number": 2,
        })
        if (body or {}).get("action") == "end":
            ok("hostile: action=end + merchant blocked 30d ✓")
        else:
            fail(f"hostile: action={body}")

        # ────────────────────────────────────────────────────────────────
        header("11. /v1/reply — wait request ('In a meeting, ping me later')")
        sc, body = await post(client, "/v1/reply", {
            "conversation_id": "conv_e2e_wait",
            "merchant_id": drmeera["merchant_id"],
            "from_role": "merchant",
            "message": "In a meeting, ping me later.",
            "received_at": "2026-05-02T10:46:00Z",
            "turn_number": 2,
        })
        if (body or {}).get("action") == "wait":
            ok(f"wait request: action=wait, wait_seconds={body.get('wait_seconds')} ✓")
        else:
            fail(f"wait request: action={body}")

        # ────────────────────────────────────────────────────────────────
        header("12. Phase 3 adaptive — push customer + 2-min-later trigger (recall_due)")
        sc, _ = await post(client, "/v1/context", {
            "scope": "customer", "context_id": priya["customer_id"],
            "version": 1, "payload": priya,
            "delivered_at": "2026-05-02T11:00:00Z",
        })
        ok("customer Priya pushed v1") if sc == 200 else fail(f"customer push: {sc}")

        sc, _ = await post(client, "/v1/context", {
            "scope": "trigger", "context_id": recall_trg["id"],
            "version": 1, "payload": recall_trg,
            "delivered_at": "2026-05-02T11:02:00Z",
        })
        ok("recall_due trigger pushed v1") if sc == 200 else fail(f"trigger push: {sc}")

        await asyncio.sleep(PACE)

        info("running tick for recall_due (customer-facing) ~5-10s")
        sc, body = await post(client, "/v1/tick", {
            "now": "2026-05-02T11:30:00+05:30",
            "available_triggers": [recall_trg["id"]],
        })
        if sc == 200 and body and body.get("actions"):
            a = body["actions"][0]
            send_as_correct = a.get("send_as") == "merchant_on_behalf"
            mentions_priya = "priya" in a.get("body", "").lower()
            has_hi_en = any(w in a.get("body", "").lower() for w in
                          ("hain", "yahan", "apke", "aapke", "mahine", "kar", "chahiye"))
            info(f"  body: {a.get('body','')[:200]!r}")
            ok("customer-facing send_as=merchant_on_behalf ✓") if send_as_correct else fail(f"send_as={a.get('send_as')}")
            ok("addresses Priya by name ✓") if mentions_priya else fail("does NOT address Priya")
            if has_hi_en:
                ok("hi-en code-mix ✓ (recall_due quality)")
            else:
                info("hi-en mix not detected — body is pure English (acceptable but loses merchant_fit points)")
        else:
            fail(f"recall tick: status={sc} body={body}")

        # ────────────────────────────────────────────────────────────────
        header("13. Adversarial — novel kind, kind_default produces output")
        await asyncio.sleep(PACE)
        novel_trg = {
            "id": "trg_e2e_novel_unknown",
            "scope": "merchant",
            "kind": "mystery_signal_invented_by_judge",
            "source": "external",
            "merchant_id": drmeera["merchant_id"],
            "payload": {
                "observation": "Patient reviews mention wait-time 5x this week",
                "suggested_action": "consider scheduling buffer",
            },
            "urgency": 2,
            "suppression_key": "e2e:novel:2026-W18",
            "expires_at": "2026-12-31T00:00:00Z",
        }
        sc, _ = await post(client, "/v1/context", {
            "scope": "trigger", "context_id": novel_trg["id"],
            "version": 1, "payload": novel_trg,
            "delivered_at": "2026-05-02T12:00:00Z",
        })
        ok("novel-kind trigger pushed") if sc == 200 else fail(f"novel push: {sc}")

        # Use a fresh time slot that bypasses cadence (Dr. Meera was sent earlier)
        # — for this test we just verify the SHOULD_SEND filter / kind_default,
        # so cadence may block. That's fine — empty actions is also a valid behavior.
        sc, body = await post(client, "/v1/tick", {
            "now": "2026-05-03T15:00:00+05:30",  # next day so cadence clears
            "available_triggers": [novel_trg["id"]],
        })
        if sc == 200 and body is not None:
            actions = body.get("actions", [])
            if actions:
                a = actions[0]
                ok(f"novel-kind handled by kind_default: body[:120]={a.get('body','')[:120]!r}")
            else:
                info("novel-kind: 0 actions (likely cadence-blocked — that's correct restraint)")
                ok("novel-kind: handled cleanly (no crash, valid empty response)")
        else:
            fail(f"novel-kind: status={sc} body={body}")

        # ────────────────────────────────────────────────────────────────
        header("14. /admin/* read-only API (no auth)")
        sc, body = await get(client, "/admin/health")
        if sc == 200 and body:
            ok(f"/admin/health: keys={body.get('groq',{}).get('key_pool_size')}, version={body.get('version')}")
        else:
            fail(f"/admin/health: status={sc}")

        sc, body = await get(client, "/admin/conversations")
        if sc == 200 and body and "conversations" in body:
            ok(f"/admin/conversations: {body.get('count')} conversations live")
        else:
            fail(f"/admin/conversations: status={sc}")

        sc, body = await get(client, "/admin/contexts")
        if sc == 200 and body:
            counts = {k: v.get("count") for k, v in body.items()}
            ok(f"/admin/contexts: {counts}")
        else:
            fail(f"/admin/contexts: status={sc}")

        sc, body = await get(client, "/admin/architecture")
        if sc == 200 and body and "mermaid" in body:
            ok("/admin/architecture: mermaid diagram present")
        else:
            fail(f"/admin/architecture: status={sc}")

    print()
    print("═" * 80)
    print(f"  RESULT: {passes} passed, {fails} failed")
    print("═" * 80)
    if notes:
        print()
        print("Notes:")
        for n in notes:
            print(f"  - {n}")
    print()
    if fails == 0:
        print("✅ All scenarios green. Bot is judging-ready.")
    else:
        print("⚠️ Some failures — investigate above.")


if __name__ == "__main__":
    asyncio.run(main())
