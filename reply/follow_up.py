"""
Engaged follow-up composer.

When the merchant's reply is on-topic + engaged (not auto-reply, not hostile,
not a wait, not off-topic), we compose a follow-up message using:
- the conversation history so far (to avoid repetition + maintain thread)
- the original trigger context (so we honor "why we started talking")
- the merchant context (for personalization)

Action mode: when intent.detect() found a commitment marker, the prompt
explicitly switches to "deliver concrete next step" mode, not "ask another
qualifying question".
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.logging import logger
from llm.groq_client import get_groq
from llm.routes import Purpose
from validators import validate_pipeline


REPLY_SYSTEM = """\
You are Vera continuing a WhatsApp conversation with a merchant.

# CRITICAL CONTEXT
You are NOT starting a new conversation. The merchant has just replied. Read
the conversation history before writing — your job is to ADVANCE the thread,
not restart it.

# RULES
- Do NOT re-introduce yourself ("I'm Vera again", "Vera here"). They know.
- Do NOT repeat content from prior bot turns verbatim or near-verbatim.
- Match the language the merchant has been using in the conversation.
- If `mode` is "action": the merchant committed (yes / let's do it). Deliver
  the concrete NEXT STEP — no more qualifying questions. Cite specific numbers,
  send specific artifacts, propose a specific time. End with a binary confirm.
- If `mode` is "engaged": continue the thread naturally. Honor any specific
  ask from the merchant ("send me the abstract", "draft the patient post" etc.).
- ONE clear CTA at the end. Binary preferred.

# OUTPUT FORMAT
Return ONLY this JSON:
{
  "body": "<the WhatsApp follow-up reply>",
  "rationale": "<one short sentence on what you delivered>"
}
"""


REPLY_USER_TEMPLATE = """\
=== MODE ===
{mode}   ({mode_explanation})

=== ORIGINAL TRIGGER ===
kind: {trigger_kind}
payload: {trigger_payload}

=== MERCHANT ===
identity: {identity}
locality: {locality}
languages: {languages}
active_offers: {active_offers}
signals: {signals}

=== CONVERSATION HISTORY (oldest → newest, last 8 turns) ===
{history}

=== MERCHANT'S LATEST REPLY ===
{latest}

Compose the follow-up now.
"""


async def compose_follow_up(
    message: str,
    conversation: dict[str, Any],
    merchant: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
    customer: dict[str, Any] | None = None,
    category: dict[str, Any] | None = None,
    *,
    action_mode: bool = False,
) -> dict[str, Any]:
    """
    Compose an engaged follow-up. Returns:
      {"action": "send", "body": ..., "cta": ..., "rationale": ...}
      or {"action": "wait", ...} on transient compose failure.
    """
    identity = ((merchant or {}).get("identity") or {})

    history_lines = []
    for t in (conversation.get("turns") or [])[-8:]:
        who = t.get("from") or "?"
        body = (t.get("body") or "").replace("\n", " ")
        history_lines.append(f"  [{who}]: {body[:240]}")
    history_str = "\n".join(history_lines) or "  (none)"

    user_msg = REPLY_USER_TEMPLATE.format(
        mode="action" if action_mode else "engaged",
        mode_explanation=(
            "Merchant committed — deliver the concrete next step, no more qualifying"
            if action_mode
            else "Merchant on-topic — advance the thread naturally"
        ),
        trigger_kind=(trigger or {}).get("kind", "unknown"),
        trigger_payload=(trigger or {}).get("payload", {}),
        identity=identity,
        locality=identity.get("locality"),
        languages=identity.get("languages"),
        active_offers=[
            o.get("title")
            for o in (merchant or {}).get("offers", [])
            if (o.get("status") or "").lower() == "active"
        ],
        signals=(merchant or {}).get("signals", []),
        history=history_str,
        latest=message,
    )

    try:
        groq = get_groq()
        raw = await groq.complete(
            Purpose.REPLY,
            prompt=user_msg,
            system=REPLY_SYSTEM,
            json_mode=True,
            temperature=0.3,
        )
        parsed = json.loads(raw)
        body = (parsed.get("body") or "").strip()
        rationale = (parsed.get("rationale") or "").strip()
    except Exception as e:  # noqa: BLE001 — best-effort; fall back to wait
        logger.warning("follow_up.compose_failed", extra={"exc": str(e)[:200]})
        return {
            "action": "wait",
            "wait_seconds": 600,
            "rationale": f"Follow-up compose error ({type(e).__name__}); waiting 10m to retry.",
        }

    if not body or len(body) < 15:
        return {
            "action": "wait",
            "wait_seconds": 600,
            "rationale": "Follow-up produced empty body; waiting 10m.",
        }

    # Run validators on the follow-up too
    validation = validate_pipeline(
        body,
        plan={"language": _infer_language(merchant, customer), "cta_shape": "open_ended",
              "send_as": "vera"},
        category=category,
        merchant=merchant,
        trigger=trigger,
        customer=customer,
        conversation_history=conversation.get("turns") or [],
    )
    if not validation.passed:
        logger.info(
            "follow_up.validator_failed",
            extra={"validator": validation.failed_validator, "error": validation.error},
        )
        # Don't refuse — ship a sanitized body if url_strip etc., else generic safe nudge
        body = validation.body or _safe_fallback_body(action_mode)

    return {
        "action": "send",
        "body": body,
        "cta": _infer_cta_shape(body),
        "rationale": rationale or ("Action-mode delivery" if action_mode else "Engaged follow-up"),
    }


def _infer_language(merchant: dict[str, Any] | None, customer: dict[str, Any] | None) -> str:
    if customer:
        pref = (customer.get("identity") or {}).get("language_pref")
        if pref:
            return pref
    langs = ((merchant or {}).get("identity") or {}).get("languages") or ["en"]
    if "hi" in langs:
        return "hi-en mix"
    if "te" in langs:
        return "te-en mix"
    if "kn" in langs:
        return "kn-en mix"
    return "en"


def _infer_cta_shape(body: str) -> str:
    if re.search(r"\breply\s+1\b", body, re.IGNORECASE) and re.search(r"\b2\b", body):
        return "multi_choice_slot"
    if re.search(r"\breply\s+(yes|no|stop)\b", body, re.IGNORECASE):
        return "binary_yes_no"
    if "?" in body:
        return "open_ended"
    return "open_ended"


def _safe_fallback_body(action_mode: bool) -> str:
    if action_mode:
        return "On it — drafting the next step now. Reply CONFIRM to proceed or HOLD if you need a moment."
    return "Got it — let me know one more detail and I'll move on it."
