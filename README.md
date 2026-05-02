# Vera Bot — magicpin AI Challenge Submission

A merchant-engagement composer that grounds every output in the context it receives. Built for the 5-dimension rubric, the 3-day live judging window, and the fresh post-submission scenarios the judge will inject.

**Live URL**: `https://magicpin-5z8k.onrender.com/`
**Repo**: `https://github.com/codedpool/magicpin`
**Submitter**: Romanch Roshan Singh (solo)

---

## Approach (3 lines)

- **6-stage composer**: PLAN → DRAFT → VALIDATE (8 guards) → SELF-SCORE (5-dim rubric) → REFINE (best-of-2) → ASSEMBLE. Restraint is rewarded — `compose()` can return `None` to refuse a send.
- **Multi-key, multi-model Groq routing** across 4 free-tier buckets with 3 round-robin keys. Combined headroom ≈ 96K TPM, 51K RPD. Automatic 429 fallback to a different model + key combination.
- **Adversarial-by-default**: `kind_default` is the *strongest* generic prompt (not a fallback) for novel kinds the judge invents. Pydantic `extra="allow"` everywhere; every dict access via `.get()`; every LLM call is wrapped in try/except with conservative-default fallbacks; full Supabase write-through so the 3-day judging window survives Render restarts.

---

## Architecture

```
                                ┌──────────────────┐
                                │  Judge Harness   │
                                └────────┬─────────┘
                                         │ HTTPS
                                         ▼
              ┌─────────────────── /v1/healthz, /v1/metadata ────────────────────┐
              ├─────────────────── POST /v1/context (idempotent) ────────────────┤
              ├─────────────────── POST /v1/tick (≤20 actions, 25s budget) ─────┤
              └─────────────────── POST /v1/reply (send/wait/end) ──────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
        ┌──────────┐              ┌──────────┐              ┌──────────┐
        │ Composer │              │  Reply   │              │ Pipeline │
        │ pipeline │              │ machine  │              │+gates+   │
        │ 6 stages │              │ 6detect. │              │ scheduler│
        └────┬─────┘              └────┬─────┘              └────┬─────┘
             │                         │                         │
             └──────────┐  ┌───────────┘                         │
                        ▼  ▼                                     │
                  ┌──────────────────┐                           │
                  │  StateStore      │◀──────────────────────────┘
                  │  (write-through) │
                  └────────┬─────────┘
              ┌────────────┴────────────┐
              ▼                         ▼
        ┌───────────┐             ┌───────────┐
        │ InMemory  │ writes ────▶│ Supabase  │
        │  (read    │             │ Postgres  │
        │   path)   │ rehydrate ◀─│ (durable) │
        └───────────┘             └───────────┘
```

Same deployed URL also serves the **Vera Console** dashboard at `/` (read-only inspector — open in any browser).

---

## Endpoints (judge surface)

| Method | Path | Purpose |
|---|---|---|
| GET / HEAD | `/v1/healthz` | Liveness + context counts. ≥3 consecutive failures = disqualify. |
| GET / HEAD | `/v1/metadata` | Team identity + model list + approach. |
| POST | `/v1/context` | Versioned, idempotent push. 200 on accept, 409 on stale_version, 400 on malformed (per testing brief §2.1). |
| POST | `/v1/tick` | Proactive sends. ≤20 actions/tick. Hard 25s deadline (5s buffer under 30s judge budget). |
| POST | `/v1/reply` | Merchant/customer reply. Returns `send` / `wait` / `end`. |
| GET | `/` | Vera Console (public read-only dashboard). |
| GET | `/admin/*` | Read-only API for the dashboard. |

---

## Composer pipeline (6 stages)

| Stage | Model | Purpose |
|---|---|---|
| 1. PLAN | `llama-3.1-8b-instant` (JSON mode, T=0) | Pick selected_facts + 1-2 compulsion levers + voice notes + language + cta_shape + send_as. Can flag `should_send=false` to refuse. |
| 2. DRAFT | `llama-3.3-70b-versatile` (JSON mode, T=0) | Write the body using a kind-dispatched prompt. 24 hand-tuned + `kind_default` for novel kinds. |
| 3. VALIDATE | Python (deterministic) | 8 guards run cheapest-first: length → url_strip → taboos → salutation → cta_shape → language → repetition → fabrication. Re-DRAFT once on first failure; refuse on second. |
| 4. SELF-SCORE | `llama-3.1-8b-instant` (JSON mode, T=0) | Score 5 rubric dimensions 0-10 + identify weakness. |
| 5. REFINE | `openai/gpt-oss-120b` (JSON mode, T=0.3) | If `min_dim < 7`, second pass on contrasting model. Re-validate + re-score. Ship best-of-2 by total. |
| 6. ASSEMBLE | Python | Build TickAction with decodable conv_id, suppression_key, template_name + params, rationale (incl. self_scores + composer_version). |

---

## Compulsion levers (priority weighted)

Per challenge brief §10, **production Vera under-uses social proof (#3) and asking-the-merchant (#7)**. Both get **1.5× weight** in PLAN. The DRAFT prompt explicitly receives the kind-specific `LEVER_HINT` so weighting actually reaches the LLM.

---

## Anti-pattern guards

Every body the judge sees has been through these deterministic Python checks (no LLM):

| Validator | What it catches |
|---|---|
| `url_strip` | Strips URLs not traceable to a context field (e.g. fabricated `fake.com`). Preserves `merchant.identity.website` etc. |
| `length` | Warns >600, hard fails >1200, rejects <30 chars. |
| `taboos` | Scans against `category.voice.vocab_taboo` (e.g. "guaranteed", "miracle", "100% safe"). |
| `salutation` | First send must use owner first name. Subsequent sends must NOT re-introduce Vera. |
| `cta_shape` | Enforces `plan.cta_shape`. Multi-CTA detection (>1 question marks, ≥3 alternatives, multiple "Reply X" word patterns). |
| `language` | Script + token detection for hi/te/kn/mr/ta-en mix. Re-DRAFTs if `language_pref="hi-en mix"` produces pure English. |
| `repetition` | rapidfuzz ≥85% similarity to any prior bot turn — **including cross-tick** (reads `store.get_conversation` at tick time). |
| `fabrication` | Every number / ₹ / % / page-ref / year / known-source-acronym must trace to a context field. Handles percentage↔decimal equivalence (`2.1%` ↔ `0.021`). |

---

## Reply state machine (6-detector cascade)

`POST /v1/reply` runs detectors cheapest-first; first match wins:

| Detector | Action |
|---|---|
| 1. **Auto-reply** (regex of canned phrases EN+HI + repetition) | 1× nudge → 2× wait 4h → 3+× end |
| 2. **Hostile** (regex EN + Hindi: "band karo", "pareshaan mat karo" etc.) | end + block merchant 30d |
| 3. **Wait request** ("in a meeting", "tomorrow", "kal", "baad mein") | wait the parsed/default duration |
| 3.5. **Sentiment fade-out** | 2× drifting/negative consecutive → 12h wait; 3× → graceful end |
| 4. **Intent transition** (commit markers EN+HI: "haan ji", "kar do", "judna hai") | switch to ACTION-mode follow-up — no more qualifying questions |
| 5. **Out-of-scope** (LLM CLASSIFY for off-topic e.g. GST) | polite redirect to original trigger |
| 6. **Engaged follow-up** (default) | qwen3-32b composer with full conversation history; mid-conversation language switch detected |

---

## should_send() meta-cognitive gate (8 rules)

Before any compose, `pipeline/should_send.py` checks:

1. Merchant blocked (hostile reply within last 30d) → no
2. Suppression key already triggered (last 7d) → no
3. Trigger expired → no
4. Last send to merchant <4h ago → no
5. Already 3 sends to this merchant in last 24h → no
6. Last send >12h ago + no merchant reply since → no (long-silence)
7. urgency=1 + recent negative engagement → no
8. urgency≤2 + outside best-time window → no (option C — see below)

**Restraint is rewarded.** The bot returns empty `actions: []` rather than push when none of the available triggers pass these gates.

---

## Best-time-to-text (option C — category default + learned override)

Default IST windows per category:

| Category | Window |
|---|---|
| dentists | 09:00 – 18:00 |
| restaurants | 11:00 – 22:00 |
| salons | 10:00 – 20:00 |
| gyms | 06:00 – 22:00 |
| pharmacies | 08:00 – 22:00 |
| (default) | 09:00 – 21:00 |

Once a merchant has replied at ≥2 distinct hours, the bot switches to ±2 hours around the median reply hour (their actual active window). **Only enforced for urgency ≤ 2** so time-sensitive sends (perf dips, supply alerts, regulation changes) always go through.

---

## Multi-model routing (Groq)

| Stage | Primary | Free RPM | Free TPM | Free RPD | Why |
|---|---|---:|---:|---:|---|
| DRAFT | `llama-3.3-70b-versatile` | 30 | 12K | 1,000 | Best free composition quality |
| REFINE | `openai/gpt-oss-120b` | 30 | 8K | 1,000 | Separate bucket; contrasting style |
| PLAN / SELF-SCORE / CLASSIFY | `llama-3.1-8b-instant` | 30 | 6K | **14,400** | Cheap, abundant |
| REPLY | `qwen/qwen3-32b` | **60** | 6K | 1,000 | Highest RPM bucket |

**3 round-robin API keys**: each request alternates across `GROQ_API_KEY`, `GROQ_API_KEY_BACKUP`, `GROQ_API_KEY_TERTIARY`. On 429: try the same model on every other key, then the fallback model on every key, then a 15s backoff. Combined headroom ≈ **96K TPM, 51K RPD**.

---

## Phase 3 adaptive context injection — verified safe

The judge mid-test bumps versions / pushes new contexts. Every `/v1/tick` and `/v1/reply` re-fetches all 4 contexts from the store (`pipeline/tick_loop.py:189-205`). **Zero cached snapshots.** Atomic version replace under lock in `state/in_memory.py:put_context`. All 4 scenarios — new digest items, updated performance, new triggers, new customer + 2-min-later trigger — are picked up automatically.

---

## State persistence

In-memory cache (sub-ms reads) write-through to Supabase Postgres (durable). `WriteThroughStore.startup()` rehydrates on every boot in <1s. Survives Render free-tier restarts during the 3-day judging window without losing a single context, conversation, suppression, or block.

---

## Vera Console at `/`

Public read-only dashboard (no auth — synthetic data, GET-only endpoints). Tabs:

- **Live conversations** — real-time list with status, turn count, last bot body
- **Trace** — click any conversation → full turn-by-turn with sentiment labels, rationale, self-scores
- **Contexts** — browse all loaded categories / merchants / customers / triggers; click any to see full payload
- **Suppressions** — active suppression keys + blocked merchants
- **Architecture** — Mermaid diagram of the full pipeline

---

## Kind library (24 hand-tuned + 1 default)

| Kind | Pattern | Customer-facing? |
|---|---|---|
| `research_digest` | Source citation + cohort match (Case Study 1) | no |
| `recall_due` | Case Study 2 — hi-en mix recall reminder | yes |
| `chronic_refill_due` | Pharmacy refill with molecule list + saved address | yes |
| `perf_dip` / `seasonal_perf_dip` | Anxiety pre-empt + reframe (Case Study 7) | no |
| `perf_spike` | Brief celebrate + double-down | no |
| `renewal_due` | Value-receipt before the ask | no |
| `festival_upcoming` | Category-correct festival play | no |
| `curious_ask_due` | Ask the merchant — production Vera's biggest miss (Case Study 4) | no |
| `ipl_match_today` | Contrarian recommendation when data warrants (Case Study 5) | no |
| `review_theme_emerged` | Non-defensive trend flagging | no |
| `milestone_reached` | Brief celebration + concrete next step | no |
| `competitor_opened` | Calm operator + defensive move | no |
| `supply_alert` | Pharmacy recall (Case Study 9) | no |
| `gbp_unverified` | Uplift % + concrete steps | no |
| `regulation_change` | Source citation + audit step + deadline | no |
| `cde_opportunity` | Low-pressure CDE webinar surface | no |
| `dormant_with_vera` | Value-first re-engagement | no |
| `customer_lapsed_hard` / `customer_lapsed_soft` | No-shame warmth (Case Study 8) | yes |
| `trial_followup` | Momentum-keeper after a trial | yes |
| `wedding_package_followup` | Bridal flow (Case Study 3) | yes |
| `active_planning_intent` | Drafted artifact (Case Study 6) | no |
| `category_seasonal` | Concrete demand shifts + shelf action | no |
| `winback_eligible` | Diagnostic + opportunity framing | no |
| `appointment_tomorrow` | Reminder + prep instructions + binary confirm | yes |
| `kind_default` | **Strong generic for novel kinds the judge invents** | both |

---

## Submission artifacts

- `bot.py` — FastAPI entrypoint (5 endpoints + `/` + `/admin/*`)
- `submission.jsonl` — **30/30 with bodies**, avg ≈ 40/50 self-score; produced by `submission_runner.py` from the canonical 30 (merchant, trigger) pairs
- `conversation_handlers.py` — exports `respond(state, message)` + `respond_sync()` for the offline tiebreaker per challenge brief §7.4
- `tests/` — 6 e2e test files covering Phases 0, A+B, C, D+E, F+G, H, I+J
- `sql/init.sql` — Supabase schema (4 tables + cleanup function)
- `render.yaml`, `Procfile`, `runtime.txt` — Render deployment config
- `deploy/render_setup.md` — full step-by-step deployment runbook
- `frontend/dashboard.html` + `frontend/admin_router.py` — Vera Console

---

## Tradeoffs

- **Sequential dataset run** for `submission.jsonl` (10s pause between pairs) — avoids Groq TPM bursts at the cost of ~3 min total runtime.
- **Render free + Supabase write-through** vs paid VM. Trade: cold-start risk during 3-day window, mitigated by UptimeRobot 5-min ping + state rehydration on boot (<1s).
- **No fully-implemented multi-arm A/B for prompt versions**. We log `composer_version` in every rationale; A/B framework would be future work.
- **Best-time-to-text "learned" mode requires ≥2 reply timestamps** before it activates. Cold-start uses category defaults.

---

## What more context would help

- **Merchant lifetime value & churn risk** — would let me prioritize which suppression-key to refresh sooner.
- **Per-merchant historical reply-latency curve** — bootstraps best-time-to-text without the ≥2-reply cold start.
- **Customer wedding-date / reservation-date** as a separate trigger-payload field — would tighten wedding/recall framing.
- **Per-conversation sentiment confidence threshold** — currently a flat 2-of-2 trigger; tunable would help adapt to merchant tone variability.

---

## Local self-test

```bash
cd submission
source .venv/Scripts/activate          # or .venv/bin/activate on Linux/Mac
uvicorn bot:app --host 0.0.0.0 --port 8080 --reload

# In another terminal:
python -m tests.test_phase_de   # composer e2e (Groq calls)
python -m tests.test_phase_fg   # validators + self-score + refine
python -m tests.test_phase_h    # 6-detector reply cascade
python -m tests.test_phase_ij   # tick pipeline + adversarial robustness
python submission_runner.py     # produce submission.jsonl
```

---

Solo submission · Romanch Roshan Singh · `romanchroshansingh@gmail.com`
