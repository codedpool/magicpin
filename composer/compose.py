"""
compose() — single-pass message composer.

One aligned LLM call per message, scored directly against the real judge's
5-dimension rubric (specificity · category_fit · merchant_fit · trigger_relevance
· engagement). No PLAN / SELF-SCORE / REFINE loop — those optimized an internal
proxy rubric that diverged from the real judge and made messages longer, pushier,
and multi-CTA. This path stays close to what the judge actually rewards: one
concrete fact, one clear low-friction ask, category-correct voice.

Kept from the old pipeline: the cheap deterministic guards that prevent judge
penalties (URL fabrication, internal-jargon leaks). Dropped: the LLM stages and
the opinionated CTA/time-cap/action-lead validators.

Public surface unchanged: compose(...) -> ComposedMessage | None, plus
choose_variant() and COMPOSER_VERSION for backward compat.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.logging import logger
from core.models import ComposedMessage

from llm.groq_client import get_groq
from llm.routes import Purpose
from validators import internal_jargon, url_strip


COMPOSER_VERSION = "0.6.0-single-pass"


# ── System prompt — maps 1:1 onto the real judge rubric ──────────────────────
SYSTEM_PROMPT = """\
You are Vera, magicpin's AI assistant for Indian local-commerce merchants. You
write short WhatsApp messages that a busy owner will actually read and reply to.

Every message is graded 0-10 on five dimensions:
1. SPECIFICITY — cite real numbers, dates, prices, or named sources FROM THE
   CONTEXT. "Dental Cleaning @ ₹299" beats "20% off". A cited source
   ("DCI circular dated 2026-11-04", "JIDA Oct 2026") scores highest.
2. CATEGORY FIT — match the category voice:
   dentists / pharmacies = clinical, precise, peer-to-peer (use "Dr."), no hype;
   salons = warm, practical; restaurants = operator-to-operator;
   gyms = coaching, motivational.
3. MERCHANT FIT — use the owner's first name, reference their real performance
   data, and honor language preference (Hindi-English code-mix when "hi" is in
   their languages / the customer's language_pref).
4. TRIGGER RELEVANCE — make the reason-for-now unmistakable and use the trigger
   payload. Not a generic nudge.
5. ENGAGEMENT — would they reply? One clear, low-friction ask.

HARD RULES:
- Use ONLY facts present in the provided context. Never invent a number, source,
  competitor, offer, or date. Fabrication is penalized.
- Never expose internal jargon to the merchant (trigger "kind" names, ids,
  "suppression key", "payload", "urgency", "compulsion lever", etc.).
- Lead with the hook. No "I hope you're doing well", no re-introducing yourself
  after the first message.
- Keep it to 2-4 short sentences. One idea, one ask.
- Exactly ONE call to action. Do NOT stack asks or offer 3+ options. Use:
    "yes_stop"    → a single yes/no question ("Want me to draft it?")
    "open_ended"  → one open question ("What's your most-asked service this week?")
    "none"        → pure info / reminder, no ask
- For clinical categories the compulsion comes from the specific FACT, not from
  adjectives, hype, or artificial urgency.
- Customer-facing messages (recall, lapsed, appointment, refill, trial follow-up)
  are written AS THE MERCHANT to the customer: send_as = "merchant_on_behalf".
  Merchant-facing coaching messages: send_as = "vera".

Return ONLY this JSON object, no markdown:
{"body": "<message>", "cta": "yes_stop"|"open_ended"|"none",
 "send_as": "vera"|"merchant_on_behalf", "rationale": "<one sentence>"}"""


# ── Per-kind framing — short, like a colleague's note. Default is strong so
#    novel kinds the judge invents still compose well. ──────────────────────
KIND_INSTRUCTIONS: dict[str, str] = {
    "research_digest": (
        "Lead with the specific finding (trial size, % effect, source name + date). "
        "Tie it to this merchant's patient/customer cohort. Offer to pull the abstract "
        "or draft a patient-education note. cta open_ended or yes_stop."
    ),
    "recall_due": (
        "Customer recall is due — write AS THE MERCHANT to the customer. Use the "
        "customer's name, the specific service due and how long since last visit, and "
        "offer the real slots if the payload has them. Match language_pref. send_as "
        "merchant_on_behalf."
    ),
    "chronic_refill_due": (
        "Pharmacy chronic-med refill likely due — write AS THE MERCHANT. Name the "
        "molecules if given; give the approximate refill window (don't fabricate an exact "
        "date). Offer doorstep delivery. send_as merchant_on_behalf."
    ),
    "perf_dip": (
        "A metric dropped. Name the exact metric and delta from the payload/performance. "
        "Be empathetic, not alarmist. Offer ONE concrete fix (activate an offer, update the "
        "profile, refresh a post). cta yes_stop."
    ),
    "seasonal_perf_dip": (
        "A dip that's part of a normal seasonal pattern. Reassure it's expected, then give "
        "one concrete action for the window. cta yes_stop."
    ),
    "perf_spike": (
        "Views/calls went up. Celebrate in one line, then pivot to one specific action to "
        "capitalize on the momentum. cta yes_stop."
    ),
    "milestone_reached": (
        "Merchant crossed a meaningful number — name it exactly. Suggest the next milestone "
        "and one action that gets them there. cta yes_stop or none."
    ),
    "competitor_opened": (
        "A competitor opened nearby. Loss-aversion, gently. Suggest ONE differentiator "
        "action (add photos, activate an offer, gather reviews). Only name the competitor if "
        "it's in the context. cta yes_stop."
    ),
    "festival_upcoming": (
        "A festival/season is coming — use its name and date. Offer to draft a themed post "
        "or campaign. Celebratory but peer-level; low-key for clinical categories. cta yes_stop."
    ),
    "curious_ask_due": (
        "Weekly curiosity ask. Ask the merchant ONE genuine business question about their "
        "shop this week. No pressure, no offer — just open a conversation. cta open_ended."
    ),
    "dormant_with_vera": (
        "Merchant has gone quiet. Re-engage with curiosity — ask about their business or "
        "flag one fresh signal. Low pressure. cta open_ended."
    ),
    "review_theme_emerged": (
        "A review theme surfaced — name it explicitly with its count/quote if given. Offer to "
        "help address it (draft a reply, update the description). cta yes_stop."
    ),
    "renewal_due": (
        "Subscription expiring — say how many days are left and what they'd lose. Offer to "
        "handle the renewal. cta yes_stop."
    ),
    "gbp_unverified": (
        "Google Business Profile unverified — quantify the visibility lift from verifying if "
        "given. Offer to walk them through the steps. cta yes_stop."
    ),
    "regulation_change": (
        "A regulation changed — cite the authority + date explicitly and the concrete change "
        "and deadline. Recommend the specific action to comply. Offer to draft the SOP/audit "
        "step. cta yes_stop."
    ),
    "supply_alert": (
        "A supply/recall alert — cite the batch/source. If merchant data lets you derive who's "
        "affected, do so (e.g. 'X of your chronic-Rx customers'). Offer the workflow. cta yes_stop."
    ),
    "ipl_match_today": (
        "A match is on tonight. If the data says the obvious play is wrong for THIS merchant, "
        "recommend against it (e.g. push delivery, not dine-in). Concrete and specific. cta yes_stop."
    ),
    "cde_opportunity": (
        "A CME/CDE webinar is relevant. Give the topic, date, and value in one line. Low "
        "pressure. cta yes_stop or open_ended."
    ),
    "customer_lapsed_soft": (
        "A customer drifted — warm re-engagement AS THE MERCHANT. Name the last service and "
        "how long ago; offer one real incentive from the merchant's active offers. send_as "
        "merchant_on_behalf. cta yes_stop."
    ),
    "customer_lapsed_hard": (
        "A long-lapsed customer — no shame, no pressure. Acknowledge the gap warmly, offer one "
        "concrete reason to return. send_as merchant_on_behalf. cta yes_stop."
    ),
    "winback_eligible": (
        "Customer is win-back eligible — diagnose gently and offer one specific hook. cta yes_stop."
    ),
    "trial_followup": (
        "Customer just tried the merchant — satisfaction check AS THE MERCHANT. Ask if they'd "
        "book again; mention a relevant offer. send_as merchant_on_behalf. cta yes_stop."
    ),
    "wedding_package_followup": (
        "Bridal flow — reference the wedding window/date if given and continuity from any past "
        "trial. Offer to hold the next slot. send_as merchant_on_behalf. cta yes_stop."
    ),
    "appointment_tomorrow": (
        "Appointment reminder AS THE MERCHANT. Include the time, what to expect, and any prep. "
        "Match language_pref. send_as merchant_on_behalf. cta yes_stop or none."
    ),
    "active_planning_intent": (
        "Merchant is actively planning something — deliver a concrete starter (a drafted offer / "
        "tiered pricing) they can edit. Offer to take the next step. cta yes_stop."
    ),
    "category_seasonal": (
        "A category-wide demand shift — name the concrete movers (up/down %) and the one shelf/"
        "menu action to take. cta yes_stop or open_ended."
    ),
}

DEFAULT_KIND_INSTRUCTION = (
    "Compose a relevant, specific, compelling WhatsApp message for this trigger. "
    "Anchor on ONE concrete fact from the contexts, match the category voice, and end "
    "with a single low-friction ask."
)


# ── Reference resolution — surface the exact fact a trigger points at ────────
_CATALOG_BUCKETS = (
    "digest",
    "patient_content_library",
    "offer_catalog",
    "seasonal_beats",
    "trend_signals",
)


def _iter_catalog_items(category: dict[str, Any]):
    for bucket in _CATALOG_BUCKETS:
        for item in category.get(bucket, []) or []:
            if isinstance(item, dict):
                yield bucket, item


def _resolve_trigger_refs(
    category: dict[str, Any], merchant: dict[str, Any], trigger: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Resolve the ids a trigger references (payload.top_item_id, offer ids, …)
    into their full objects, so the message can cite the exact number/source and
    slimming never drops the anchor fact."""
    payload = trigger.get("payload", {}) or {}
    ref_ids: set[str] = set()
    for key, val in payload.items():
        if not ("id" in key.lower() or key in ("top_item", "item", "content", "offer")):
            continue
        if isinstance(val, str):
            ref_ids.add(val)
        elif isinstance(val, list):
            ref_ids.update(v for v in val if isinstance(v, str))

    resolved: dict[str, list[dict[str, Any]]] = {}
    if ref_ids:
        for bucket, item in _iter_catalog_items(category or {}):
            if item.get("id") in ref_ids:
                resolved.setdefault(bucket, []).append(item)
        for offer in (merchant or {}).get("offers", []) or []:
            if isinstance(offer, dict) and offer.get("id") in ref_ids:
                resolved.setdefault("merchant_offer", []).append(offer)
    return resolved


def _slim_category(cat: dict[str, Any]) -> dict[str, Any]:
    cat = cat or {}
    return {
        "slug": cat.get("slug"),
        "voice": cat.get("voice"),
        "peer_stats": cat.get("peer_stats"),
        "offer_catalog": (cat.get("offer_catalog") or [])[:5],
        "seasonal_beats": (cat.get("seasonal_beats") or [])[:3],
        "trend_signals": (cat.get("trend_signals") or [])[:3],
        "regulatory_authorities": cat.get("regulatory_authorities"),
        "professional_journals": cat.get("professional_journals"),
    }


def _slim_merchant(m: dict[str, Any]) -> dict[str, Any]:
    m = m or {}
    offers = m.get("offers") or []
    return {
        "identity": m.get("identity"),
        "subscription": m.get("subscription"),
        "performance": m.get("performance"),
        "active_offers": [o for o in offers if (o.get("status") or "").lower() == "active"][:5],
        "customer_aggregate": m.get("customer_aggregate"),
        "signals": m.get("signals"),
        "review_themes": m.get("review_themes"),
    }


def _lang_note(merchant: dict[str, Any] | None, customer: dict[str, Any] | None) -> str:
    if customer:
        pref = ((customer.get("identity") or {}).get("language_pref") or "").lower()
        if pref:
            return pref
    langs = ((merchant or {}).get("identity") or {}).get("languages") or ["en"]
    for code, label in (("hi", "hi-en mix"), ("te", "te-en mix"),
                        ("kn", "kn-en mix"), ("mr", "mr-en mix"), ("ta", "ta-en mix")):
        if code in langs:
            return label
    return "en"


def _build_user_prompt(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None,
    conversation_history: list[dict[str, Any]] | None,
    feedback: str | None,
) -> str:
    kind = trigger.get("kind", "")
    instr = KIND_INSTRUCTIONS.get(kind, DEFAULT_KIND_INSTRUCTION)
    resolved = _resolve_trigger_refs(category, merchant, trigger)
    lang = _lang_note(merchant, customer)

    parts = [f"WHAT JUST HAPPENED: {instr}", "", f"LANGUAGE: write in {lang}."]

    if resolved:
        parts += [
            "",
            "PRIMARY FACT TO ANCHOR ON (the trigger references this exact item — "
            "cite its concrete numbers/source; do not anchor on anything else):",
            json.dumps(resolved, ensure_ascii=False, indent=2),
        ]

    parts += [
        "",
        "CATEGORY CONTEXT:",
        json.dumps(_slim_category(category), ensure_ascii=False, indent=2),
        "",
        "MERCHANT CONTEXT:",
        json.dumps(_slim_merchant(merchant), ensure_ascii=False, indent=2),
        "",
        "TRIGGER PAYLOAD:",
        json.dumps(trigger.get("payload", {}), ensure_ascii=False, indent=2),
    ]

    if customer:
        parts += [
            "",
            "CUSTOMER CONTEXT (this message goes to this customer, as the merchant):",
            json.dumps(
                {
                    "identity": customer.get("identity"),
                    "relationship": customer.get("relationship"),
                    "state": customer.get("state"),
                    "preferences": customer.get("preferences"),
                },
                ensure_ascii=False,
                indent=2,
            ),
        ]

    if conversation_history:
        parts += ["", "CONVERSATION SO FAR (do not repeat any earlier line):"]
        for turn in conversation_history[-5:]:
            role = (turn.get("from") or turn.get("from_role") or "?").upper()
            msg = turn.get("body") or turn.get("msg") or turn.get("message") or ""
            parts.append(f"  [{role}]: {msg[:160]}")

    if feedback:
        parts += ["", f"FIX BEFORE RESENDING: {feedback}"]

    parts += ["", "Compose the message now. Respond ONLY with the JSON object."]
    return "\n".join(parts)


# ── Tolerant JSON extraction (models sometimes wrap the object in prose) ─────
def _extract_json(raw: str) -> dict[str, Any] | None:
    raw = re.sub(r"```(?:json)?", "", raw or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(raw[start : i + 1])
                        return obj if isinstance(obj, dict) else None
                    except json.JSONDecodeError:
                        break
        start = raw.find("{", start + 1)
    return None


# WhatsApp doesn't render GFM **bold** / *italic* — strip so the merchant
# doesn't see literal asterisks.
_MD_BOLD = re.compile(r"\*{2}([^*\n]+?)\*{2}")
_MD_ITALIC = re.compile(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])")


def _clean_body(body: str) -> str:
    body = _MD_BOLD.sub(r"\1", body or "")
    body = _MD_ITALIC.sub(r"\1", body)
    return body.strip()


def _context_aware_fallback(
    trigger: dict[str, Any],
    merchant: dict[str, Any] | None,
    customer: dict[str, Any] | None,
) -> tuple[str, str, str]:
    """Last resort when the LLM is unreachable/unparseable. Still names the
    merchant + reason instead of a generic canned line (which scores ~0)."""
    name = ((merchant or {}).get("identity", {}) or {}).get("owner_first_name") or ""
    if not name:
        full = ((merchant or {}).get("identity", {}) or {}).get("name", "")
        name = full.split()[0] if full else "there"
    send_as = "merchant_on_behalf" if customer else "vera"
    if _lang_note(merchant, customer) != "en":
        body = f"{name}, ek quick update tha aapke liye. Kya main details bhej doon?"
    else:
        body = f"{name}, quick one — there's something relevant for you. Want the details?"
    return body, "yes_stop", send_as


async def compose(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None = None,
    *,
    conversation_history: list[dict[str, Any]] | None = None,
) -> ComposedMessage | None:
    """Compose one message from the 4 contexts with a single aligned LLM call.

    Returns a ComposedMessage, or None only if we truly can't produce a body.
    """
    kind = trigger.get("kind", "default")
    if conversation_history is None:
        conversation_history = (merchant or {}).get("conversation_history") or []

    groq = get_groq()
    feedback: str | None = None
    body = ""
    cta_raw = "open_ended"
    send_as = "merchant_on_behalf" if customer else "vera"
    rationale = ""

    # One draft; at most one re-draft if a cheap guard flags a leak.
    for attempt in range(2):
        user_prompt = _build_user_prompt(
            category or {}, merchant or {}, trigger or {}, customer,
            conversation_history, feedback,
        )
        try:
            raw = await groq.complete(
                Purpose.DRAFT,
                prompt=user_prompt,
                system=SYSTEM_PROMPT,
                json_mode=True,
                temperature=0.0,
            )
        except Exception as e:  # noqa: BLE001 — degrade, never crash a tick
            logger.warning(
                "compose.llm_error",
                extra={"kind": kind, "attempt": attempt, "exc_type": type(e).__name__, "exc": str(e)[:200]},
            )
            body, cta_raw, send_as = _context_aware_fallback(trigger, merchant, customer)
            rationale = "Context-aware fallback — LLM unavailable."
            break

        parsed = _extract_json(raw)
        if not isinstance(parsed, dict) or not (parsed.get("body") or "").strip():
            if attempt == 0:
                feedback = "Return a single valid JSON object with a non-empty 'body'."
                continue
            body, cta_raw, send_as = _context_aware_fallback(trigger, merchant, customer)
            rationale = "Context-aware fallback — unparseable LLM output."
            break

        body = _clean_body(parsed.get("body", ""))
        cta_raw = (parsed.get("cta") or "open_ended").strip()
        cand_send_as = (parsed.get("send_as") or "").strip()
        send_as = cand_send_as if cand_send_as in ("vera", "merchant_on_behalf") else send_as
        rationale = (parsed.get("rationale") or "").strip()

        # Cheap deterministic guards (penalty prevention only) ───────────────
        _kw = dict(plan=None, category=category, merchant=merchant,
                   trigger=trigger, customer=customer,
                   conversation_history=conversation_history)
        _, _, _, body = url_strip.check(body, **_kw)  # strips non-context URLs
        jargon_ok, jargon_err, _, _ = internal_jargon.check(body, **_kw)
        if not jargon_ok and attempt == 0:
            feedback = f"Remove internal jargon exposed to the merchant: {jargon_err}"
            continue
        break

    if not body:
        return None

    return ComposedMessage(
        body=body,
        cta=_normalize_cta(cta_raw),
        send_as=send_as,  # type: ignore[arg-type]
        suppression_key=trigger.get("suppression_key") or _derive_suppression_key(trigger),
        rationale=rationale or f"{kind.replace('_', ' ').capitalize()} — anchored on the trigger's concrete fact.",
        template_name=_template_name(send_as, kind),
        template_params=_split_for_template(body),
        composer_version=COMPOSER_VERSION,
        self_scores={},
    )


# ── Backward-compat shim (A/B registry is retired; always 'standard') ────────
def choose_variant(merchant: dict[str, Any] | None, trigger: dict[str, Any] | None) -> str:
    return "standard"


# ── helpers ──────────────────────────────────────────────────────────────────
def _normalize_cta(shape: str) -> str:
    mapping = {
        "yes_stop": "binary_yes_no",
        "binary_yes_no": "binary_yes_no",
        "binary_confirm_cancel": "binary_yes_no",
        "open_ended": "open_ended",
        "multi_choice_slot": "multi_choice_slot",
        "none": "none",
    }
    return mapping.get((shape or "").strip(), "open_ended")


def _template_name(send_as: str, kind: str) -> str:
    prefix = "merchant" if send_as == "merchant_on_behalf" else "vera"
    return f"{prefix}_{kind}_v1"


def _split_for_template(body: str) -> list[str]:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", (body or "").strip()) if s.strip()]
    if not sentences:
        return [body, "", ""]
    if len(sentences) == 1:
        return [sentences[0], "", ""]
    if len(sentences) == 2:
        return [sentences[0], sentences[1], ""]
    return [sentences[0], sentences[1], " ".join(sentences[2:])]


def _derive_suppression_key(trigger: dict[str, Any]) -> str:
    parts = [
        trigger.get("kind", "unknown"),
        trigger.get("merchant_id") or trigger.get("customer_id") or "any",
        trigger.get("id", ""),
    ]
    return ":".join(p for p in parts if p)
