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
from fastapi.exceptions import RequestValidationError
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
from llm.groq_client import get_groq
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
    groq = get_groq()
    await groq.connect()
    try:
        await groq.prewarm()
    except Exception as e:  # noqa: BLE001 — prewarm failure is non-fatal
        logger.warning("vera.prewarm_failed_nonfatal", extra={"exc_type": type(e).__name__})
    yield
    logger.info("vera.shutdown")
    await groq.close()
    await store.shutdown()


app = FastAPI(
    title="Vera Bot",
    version=settings.BOT_VERSION,
    description="magicpin AI Challenge — merchant engagement composer",
    lifespan=lifespan,
)


# ─── exception handler: return our schema on Pydantic validation errors ─────
# Testing brief §2.1 expects 400 with {accepted: false, reason, details} on
# malformed /v1/context. Default FastAPI returns 422 with {detail:[...]}.
# Map validation errors to our schema for /v1/context; 422 elsewhere is fine.

@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    path = request.url.path
    errs = exc.errors()
    summary = "; ".join(
        f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg', '')}"
        for e in errs[:3]
    )
    if path == "/v1/context":
        return JSONResponse(
            status_code=400,
            content={
                "accepted": False,
                "reason": "validation_error",
                "details": summary[:500],
            },
        )
    # Default: keep FastAPI's 422 shape but include our reason field
    return JSONResponse(
        status_code=422,
        content={"detail": errs, "reason": "validation_error", "summary": summary[:500]},
    )


# ─── middleware: enforce 500KB payload cap (testing brief §5) + per-request
#                  log + safe default on uncaught exceptions ────────────────

MAX_PAYLOAD_BYTES = 500 * 1024  # 500 KB per testing brief §5


@app.middleware("http")
async def payload_size_guard(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_PAYLOAD_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "accepted": False,
                            "reason": "payload_too_large",
                            "details": f"max {MAX_PAYLOAD_BYTES} bytes",
                        },
                    )
            except ValueError:
                pass
    return await call_next(request)


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

@app.api_route("/v1/healthz", methods=["GET", "HEAD"], response_model=HealthzResponse)
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


@app.api_route("/v1/metadata", methods=["GET", "HEAD"], response_model=MetadataResponse)
async def metadata() -> MetadataResponse:
    return MetadataResponse(
        team_name=settings.BOT_TEAM_NAME,
        team_members=[settings.BOT_TEAM_NAME],  # name(s), not email
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
    Phase I: real tick pipeline. Filter triggers via should_send, parallel
    compose(), assemble actions, persist conversations + suppressions.
    Hard 25s deadline; returns whatever finished.
    """
    logger.info(
        "tick.received",
        extra={
            "now": body.now,
            "trigger_count": len(body.available_triggers),
        },
    )
    from pipeline.tick_loop import run_tick

    actions = await run_tick(
        now_iso=body.now,
        available_triggers=body.available_triggers,
        store=store,
    )

    # Validate each action conforms to TickAction (drop malformed defensively)
    from core.models import TickAction

    valid: list[TickAction] = []
    for a in actions:
        try:
            valid.append(TickAction(**a))
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "tick.action_validation_failed",
                extra={"trigger_id": a.get("trigger_id"), "exc": str(e)[:200]},
            )
    return TickResponse(actions=valid)


@app.post("/v1/reply")
async def reply(body: ReplyBody) -> Any:
    """
    Phase H: 6-detector reply state machine.
    Returns one of: send / wait / end.
    """
    logger.info(
        "reply.received",
        extra={
            "conversation_id": body.conversation_id,
            "turn_number": body.turn_number,
            "from_role": body.from_role,
        },
    )

    # Look up the original trigger via conversation.trigger_id so the reply
    # handler (and follow-up composer) has the full original context.
    conversation_payload = await store.get_conversation(body.conversation_id)
    trigger_payload = None
    resolved_merchant_id = body.merchant_id or (conversation_payload or {}).get("merchant_id")
    resolved_customer_id = body.customer_id or (conversation_payload or {}).get("customer_id")
    if conversation_payload and conversation_payload.get("trigger_id"):
        trigger_payload = await store.get_context("trigger", conversation_payload["trigger_id"])

    # Look up merchant/category/customer contexts (None if not pushed yet)
    merchant_payload = None
    customer_payload = None
    category_payload = None
    if resolved_merchant_id:
        merchant_payload = await store.get_context("merchant", resolved_merchant_id)
        if merchant_payload:
            cat_slug = merchant_payload.get("category_slug")
            if cat_slug:
                category_payload = await store.get_context("category", cat_slug)
    if resolved_customer_id:
        customer_payload = await store.get_context("customer", resolved_customer_id)

    from reply.handler import handle_reply

    return await handle_reply(
        conversation_id=body.conversation_id,
        message=body.message,
        merchant_id=resolved_merchant_id,
        customer_id=resolved_customer_id,
        from_role=body.from_role,
        received_at=body.received_at or _utc_iso_now(),
        turn_number=body.turn_number,
        store=store,
        category=category_payload,
        merchant=merchant_payload,
        customer=customer_payload,
        trigger=trigger_payload,
    )


# ─── root: friendly placeholder until Vera Console (Phase O) ─────────────────

@app.api_route("/", methods=["GET", "HEAD"])
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
