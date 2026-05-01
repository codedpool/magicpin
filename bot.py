"""
Vera Bot — magicpin AI Challenge

FastAPI entrypoint. Exposes the 5 endpoints required by the judge harness:
    GET  /v1/healthz   — liveness + context counts
    GET  /v1/metadata  — team identity
    POST /v1/context   — versioned, idempotent context push
    POST /v1/tick      — periodic wake-up; bot returns proactive actions
    POST /v1/reply     — handle merchant/customer reply

Phase A+B: endpoints wired with InMemoryStore + idempotency on /v1/context.
Phase C+ adds Supabase persistence behind a write-through layer.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.logging import logger
from core.models import (
    ContextCounts,
    ContextPushAccepted,
    ContextPushBody,
    ContextPushRejected,
    HealthzResponse,
    MetadataResponse,
    ReplyBody,
    ReplyWait,
    TickBody,
    TickResponse,
)
from core.settings import settings
from state.in_memory import InMemoryStore
from state.write_through import WriteThroughStore

# ─── globals ─────────────────────────────────────────────────────────────────

START_TS = time.time()

# Write-through to Supabase when enabled (default Phase C+); otherwise pure in-memory.
store = WriteThroughStore() if settings.SUPABASE_ENABLED else InMemoryStore()


# ─── lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "vera.startup",
        extra={
            "version": settings.BOT_VERSION,
            "team": settings.BOT_TEAM_NAME,
            "supabase_enabled": settings.SUPABASE_ENABLED,
        },
    )
    await store.startup()
    yield
    logger.info("vera.shutdown")
    await store.shutdown()


app = FastAPI(
    title="Vera Bot",
    version=settings.BOT_VERSION,
    description="magicpin AI Challenge — merchant engagement composer",
    lifespan=lifespan,
)


# ─── middleware: per-request log + safe default on uncaught exceptions ───────

@app.middleware("http")
async def log_and_guard(request: Request, call_next):
    t0 = time.time()
    path = request.url.path
    try:
        response = await call_next(request)
        latency_ms = int((time.time() - t0) * 1000)
        logger.info(
            "http.request",
            extra={
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response
    except Exception as e:  # noqa: BLE001 — never crash on judge input
        latency_ms = int((time.time() - t0) * 1000)
        logger.exception(
            "http.unhandled_exception",
            extra={
                "method": request.method,
                "path": path,
                "latency_ms": latency_ms,
                "exc_type": type(e).__name__,
            },
        )
        return JSONResponse(
            status_code=500,
            content={"accepted": False, "reason": "internal_error", "details": str(e)[:200]},
        )


# ─── helpers ─────────────────────────────────────────────────────────────────

def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ─── endpoints ───────────────────────────────────────────────────────────────

@app.get("/v1/healthz", response_model=HealthzResponse)
async def healthz() -> HealthzResponse:
    counts = ContextCounts(
        category=await store.context_count("category"),
        merchant=await store.context_count("merchant"),
        customer=await store.context_count("customer"),
        trigger=await store.context_count("trigger"),
    )
    return HealthzResponse(
        status="ok",
        uptime_seconds=int(time.time() - START_TS),
        contexts_loaded=counts,
    )


@app.get("/v1/metadata", response_model=MetadataResponse)
async def metadata() -> MetadataResponse:
    return MetadataResponse(
        team_name=settings.BOT_TEAM_NAME,
        team_members=[settings.BOT_CONTACT_EMAIL or "Solo"],
        model="groq-llama-3.3-70b + groq-gpt-oss-120b + groq-llama-3.1-8b + groq-qwen3-32b",
        approach=(
            "Multi-stage composer (PLAN→DRAFT→VALIDATE→SELF-SCORE→REFINE) "
            "with kind-dispatched prompts, multi-model routing across Groq buckets, "
            "Supabase write-through state, and 6-detector reply state machine."
        ),
        contact_email=settings.BOT_CONTACT_EMAIL,
        version=settings.BOT_VERSION,
        submitted_at=_utc_iso_now(),
    )


@app.post("/v1/context")
async def push_context(body: ContextPushBody) -> Any:
    accepted, current_version = await store.put_context(
        scope=body.scope,
        context_id=body.context_id,
        version=body.version,
        payload=body.payload,
        delivered_at=body.delivered_at,
    )

    if accepted:
        ack = ContextPushAccepted(
            ack_id=f"ack_{body.scope}_{body.context_id}_v{body.version}",
            stored_at=_utc_iso_now(),
        )
        logger.info(
            "context.stored",
            extra={
                "scope": body.scope,
                "context_id": body.context_id,
                "version": body.version,
            },
        )
        return ack

    rejected = ContextPushRejected(
        reason="stale_version",
        current_version=current_version,
    )
    logger.info(
        "context.rejected_stale",
        extra={
            "scope": body.scope,
            "context_id": body.context_id,
            "incoming_version": body.version,
            "current_version": current_version,
        },
    )
    return JSONResponse(status_code=409, content=rejected.model_dump())


@app.post("/v1/tick", response_model=TickResponse)
async def tick(body: TickBody) -> TickResponse:
    """
    Phase A+B: stub — returns empty actions list.
    Phase E+ will compose actions from available_triggers.
    """
    logger.info(
        "tick.received",
        extra={
            "now": body.now,
            "trigger_count": len(body.available_triggers),
        },
    )
    return TickResponse(actions=[])


@app.post("/v1/reply")
async def reply(body: ReplyBody) -> Any:
    """
    Phase A+B: stub — returns wait 60s.
    Phase H wires the 6-detector reply state machine.
    """
    logger.info(
        "reply.received",
        extra={
            "conversation_id": body.conversation_id,
            "turn_number": body.turn_number,
            "from_role": body.from_role,
        },
    )
    return ReplyWait(
        wait_seconds=60,
        rationale="Phase A+B stub — reply handler wired in Phase H",
    )


# ─── root: friendly placeholder until Vera Console (Phase O) ─────────────────

@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "Vera Bot",
        "version": settings.BOT_VERSION,
        "status": "online",
        "endpoints": [
            "GET /v1/healthz",
            "GET /v1/metadata",
            "POST /v1/context",
            "POST /v1/tick",
            "POST /v1/reply",
        ],
        "note": "Vera Console dashboard ships in Phase O.",
    }
