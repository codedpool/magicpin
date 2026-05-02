"""
Pydantic models for the 4 context types + API request/response shapes.

All context models use `extra="allow"` so unknown payload keys don't crash
parsing — the judge can inject novel fields and we tolerate them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ─── Permissive base — all context schemas inherit from this ─────────────────
# We accept any extra fields the judge invents. We never reject a context for
# having too many keys; we only reject malformed top-level shape.

_PERMISSIVE = ConfigDict(extra="allow", str_strip_whitespace=True)


# ════════════════════════════════════════════════════════════════════════════
# 4 CONTEXT TYPES
# ════════════════════════════════════════════════════════════════════════════

class CategoryContext(BaseModel):
    """Slow-changing knowledge pack per business vertical."""
    model_config = _PERMISSIVE

    slug: str
    voice: dict[str, Any] = Field(default_factory=dict)
    offer_catalog: list[dict[str, Any]] = Field(default_factory=list)
    peer_stats: dict[str, Any] = Field(default_factory=dict)
    digest: list[dict[str, Any]] = Field(default_factory=list)
    patient_content_library: list[dict[str, Any]] = Field(default_factory=list)
    seasonal_beats: list[dict[str, Any]] = Field(default_factory=list)
    trend_signals: list[dict[str, Any]] = Field(default_factory=list)
    display_name: str | None = None


class MerchantContext(BaseModel):
    """Per-business state. Refreshed daily for performance."""
    model_config = _PERMISSIVE

    merchant_id: str
    category_slug: str | None = None
    identity: dict[str, Any] = Field(default_factory=dict)
    subscription: dict[str, Any] = Field(default_factory=dict)
    performance: dict[str, Any] = Field(default_factory=dict)
    offers: list[dict[str, Any]] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    customer_aggregate: dict[str, Any] = Field(default_factory=dict)
    signals: list[str] = Field(default_factory=list)
    review_themes: list[dict[str, Any]] = Field(default_factory=list)


class CustomerContext(BaseModel):
    """Per-customer state with this specific merchant."""
    model_config = _PERMISSIVE

    customer_id: str
    merchant_id: str
    identity: dict[str, Any] = Field(default_factory=dict)
    relationship: dict[str, Any] = Field(default_factory=dict)
    state: str | None = None  # new | active | lapsed_soft | lapsed_hard | churned
    preferences: dict[str, Any] = Field(default_factory=dict)
    consent: dict[str, Any] = Field(default_factory=dict)


class TriggerContext(BaseModel):
    """The event that prompts a message right now."""
    model_config = _PERMISSIVE

    id: str
    scope: str  # merchant | customer
    kind: str
    source: str | None = None  # external | internal
    merchant_id: str | None = None
    customer_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    urgency: int = 1
    suppression_key: str | None = None
    expires_at: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# /v1/context — request/response
# ════════════════════════════════════════════════════════════════════════════

ScopeLiteral = Literal["category", "merchant", "customer", "trigger"]


class ContextPushBody(BaseModel):
    """POST /v1/context body."""
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    scope: ScopeLiteral
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str


class ContextPushAccepted(BaseModel):
    accepted: Literal[True] = True
    ack_id: str
    stored_at: str


class ContextPushRejected(BaseModel):
    accepted: Literal[False] = False
    reason: str
    current_version: int | None = None
    details: str | None = None


# ════════════════════════════════════════════════════════════════════════════
# /v1/tick — request/response
# ════════════════════════════════════════════════════════════════════════════

class TickBody(BaseModel):
    model_config = ConfigDict(extra="allow")
    now: str
    available_triggers: list[str] = Field(default_factory=list)


class TickAction(BaseModel):
    """One outbound action returned by /v1/tick."""
    model_config = ConfigDict(extra="allow")

    conversation_id: str
    merchant_id: str
    customer_id: str | None = None
    send_as: Literal["vera", "merchant_on_behalf"] = "vera"
    trigger_id: str
    template_name: str
    template_params: list[str] = Field(default_factory=list)
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: list[TickAction] = Field(default_factory=list)


# ════════════════════════════════════════════════════════════════════════════
# /v1/reply — request/response
# ════════════════════════════════════════════════════════════════════════════

class ReplyBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    conversation_id: str
    merchant_id: str | None = None
    customer_id: str | None = None
    from_role: Literal["merchant", "customer"] = "merchant"
    message: str
    received_at: str | None = None  # judge may omit per brief §2.3 short example
    turn_number: int = 1


class ReplySend(BaseModel):
    action: Literal["send"] = "send"
    body: str
    cta: str
    rationale: str


class ReplyWait(BaseModel):
    action: Literal["wait"] = "wait"
    wait_seconds: int
    rationale: str


class ReplyEnd(BaseModel):
    action: Literal["end"] = "end"
    rationale: str


# ════════════════════════════════════════════════════════════════════════════
# /v1/healthz — response
# ════════════════════════════════════════════════════════════════════════════

class ContextCounts(BaseModel):
    category: int = 0
    merchant: int = 0
    customer: int = 0
    trigger: int = 0


class HealthzResponse(BaseModel):
    status: Literal["ok"] = "ok"
    uptime_seconds: int
    contexts_loaded: ContextCounts


# ════════════════════════════════════════════════════════════════════════════
# /v1/metadata — response
# ════════════════════════════════════════════════════════════════════════════

class MetadataResponse(BaseModel):
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str


# ════════════════════════════════════════════════════════════════════════════
# Internal types
# ════════════════════════════════════════════════════════════════════════════

class ComposedMessage(BaseModel):
    """Internal output of the composer pipeline (Phase E+G)."""
    model_config = ConfigDict(extra="allow")

    body: str
    cta: str = "open_ended"
    send_as: Literal["vera", "merchant_on_behalf"] = "vera"
    suppression_key: str = ""
    rationale: str = ""
    template_name: str = "vera_default_v1"
    template_params: list[str] = Field(default_factory=list)
    composer_version: str = "0.1.0"
    self_scores: dict[str, int] = Field(default_factory=dict)
