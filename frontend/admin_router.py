"""
/admin/* read-only endpoints powering the Vera Console dashboard.

PUBLIC by design: these endpoints are read-only (GET only) and expose only
synthetic challenge data. Anyone visiting the public URL can open the
dashboard. The /v1/* judge endpoints are entirely separate and unaffected.

If we ever needed to gate this (e.g., for real merchant data post-challenge),
add HTTPBasic via core.settings.ADMIN_PASSWORD.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from core.settings import settings


router = APIRouter(prefix="/admin", tags=["admin-readonly"])


def _get_store():
    """Defer the import so circular imports stay clean."""
    from bot import store
    return store


# ─── Conversations ──────────────────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations() -> dict[str, Any]:
    store = _get_store()
    if hasattr(store, "all_conversations"):
        convs = await store.all_conversations()
    elif hasattr(store, "memory"):
        convs = await store.memory.all_conversations()
    else:
        convs = []
    summary = []
    for c in convs:
        turns = c.get("turns") or []
        summary.append({
            "conversation_id": c.get("conversation_id"),
            "merchant_id": c.get("merchant_id"),
            "customer_id": c.get("customer_id"),
            "trigger_id": c.get("trigger_id"),
            "send_as": c.get("send_as"),
            "turn_count": len(turns),
            "auto_reply_count": c.get("auto_reply_count", 0),
            "ended": bool(c.get("ended")),
            "end_reason": c.get("end_reason"),
            "last_bot_body_preview": (c.get("last_bot_body") or "")[:120],
            "updated_at": c.get("updated_at"),
        })
    summary.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"count": len(summary), "conversations": summary}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, Any]:
    store = _get_store()
    conv = await store.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return conv


# ─── Contexts ───────────────────────────────────────────────────────────────

@router.get("/contexts")
async def list_contexts() -> dict[str, Any]:
    store = _get_store()
    summary = {}
    for scope in ("category", "merchant", "customer", "trigger"):
        items = await store.all_contexts(scope)
        ids = []
        for p in items:
            cid = (
                p.get("slug")
                or p.get("merchant_id")
                or p.get("customer_id")
                or p.get("id")
                or "?"
            )
            ids.append(cid)
        summary[scope] = {"count": len(items), "ids": ids[:200]}
    return summary


@router.get("/contexts/{scope}/{context_id}")
async def get_context(scope: str, context_id: str) -> dict[str, Any]:
    store = _get_store()
    payload = await store.get_context(scope, context_id)
    if not payload:
        raise HTTPException(status_code=404, detail="context_not_found")
    return {"scope": scope, "context_id": context_id, "payload": payload}


# ─── Suppressions / blocked ─────────────────────────────────────────────────

@router.get("/suppressions")
async def list_suppressions() -> dict[str, Any]:
    store = _get_store()
    if hasattr(store, "memory"):
        sup = store.memory._suppressions
        blk = store.memory._blocked
    else:
        sup = getattr(store, "_suppressions", {})
        blk = getattr(store, "_blocked", {})

    return {
        "suppressions": [
            {"merchant_id": k[0], "suppression_key": k[1], "expires_at": v.isoformat()}
            for k, v in sup.items()
        ],
        "blocked_merchants": [
            {"merchant_id": k, "expires_at": v.isoformat()}
            for k, v in blk.items()
        ],
    }


# ─── Health (extended) ──────────────────────────────────────────────────────

@router.get("/health")
async def extended_health() -> dict[str, Any]:
    import time as _t
    from bot import START_TS
    store = _get_store()

    counts = {
        scope: await store.context_count(scope)
        for scope in ("category", "merchant", "customer", "trigger")
    }
    if hasattr(store, "all_conversations"):
        convs = await store.all_conversations()
    elif hasattr(store, "memory"):
        convs = await store.memory.all_conversations()
    else:
        convs = []
    active_convs = sum(1 for c in convs if not c.get("ended"))
    ended_convs = sum(1 for c in convs if c.get("ended"))

    from llm.groq_client import get_groq
    groq = get_groq()
    key_pool_size = len(groq._keys) if groq._keys else 0

    return {
        "status": "ok",
        "uptime_seconds": int(_t.time() - START_TS),
        "contexts_loaded": counts,
        "conversations": {"active": active_convs, "ended": ended_convs, "total": len(convs)},
        "groq": {
            "key_pool_size": key_pool_size,
            "models_routed": [
                "llama-3.3-70b-versatile",
                "openai/gpt-oss-120b",
                "llama-3.1-8b-instant",
                "qwen/qwen3-32b",
            ],
        },
        "supabase_enabled": settings.SUPABASE_ENABLED,
        "version": settings.BOT_VERSION,
    }


# ─── Architecture (static text — for the dashboard's last tab) ──────────────

@router.get("/architecture")
async def architecture() -> dict[str, str]:
    return {
        "mermaid": """flowchart TD
  Judge[Judge Harness] -->|POST /v1/context| Bot
  Judge -->|POST /v1/tick| Bot
  Judge -->|POST /v1/reply| Bot
  Bot[FastAPI Bot] -->|read fresh per tick| Memory[InMemoryStore]
  Memory <-->|write-through| Supabase[(Supabase Postgres)]
  Bot -->|compose| Composer
  Composer --> PLAN[Stage 1: PLAN<br/>llama-3.1-8b]
  Composer --> DRAFT[Stage 2: DRAFT<br/>llama-3.3-70b]
  Composer --> VALIDATE[Stage 3: VALIDATE<br/>8 validators]
  Composer --> SCORE[Stage 4: SELF-SCORE<br/>llama-3.1-8b]
  Composer --> REFINE[Stage 5: REFINE<br/>gpt-oss-120b]
  Bot -->|reply| ReplyMachine[6-detector cascade]
  ReplyMachine --> Sentiment[sentiment fade-out]
  ReplyMachine --> AutoReply[auto-reply hell]
  ReplyMachine --> Hostile[hostile + block]
  ReplyMachine --> Wait[wait request]
  ReplyMachine --> Intent[intent transition]
  ReplyMachine --> OOS[out-of-scope]
  ReplyMachine --> FollowUp[engaged follow-up<br/>qwen3-32b]
  Bot -.->|check| Cadence[should_send: cadence/sup./blocked/<br/>24h-cap/long-silence/best-time]
""",
        "model_routing": "DRAFT→llama-3.3-70b | REFINE→gpt-oss-120b | PLAN/SCORE/CLASSIFY→llama-3.1-8b | REPLY→qwen3-32b",
        "version": settings.BOT_VERSION,
    }
