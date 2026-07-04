"""
Composer verification — deterministic validators + single-pass compose().

`test_validators_unit` (collected by pytest, no network) checks the validator
pipeline still catches URLs / taboos / fabrication / etc.

The `_main` script (run manually, needs a dataset/ dir + Groq key) composes 3
real scenarios and asserts the single-pass contract: a non-empty, jargon-free
body with a valid cta/send_as. (The old self-score + refine loop was removed —
see composer/compose.py — so there are no self_scores to assert on.)

Run from submission/:
    PYTHONIOENCODING=utf-8 python -m tests.test_phase_fg
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
    customers = json.load(open(DATASET_DIR / "customers_seed.json", encoding="utf-8"))["customers"]
    triggers = json.load(open(DATASET_DIR / "triggers_seed.json", encoding="utf-8"))["triggers"]

    by = lambda lst, k, v: next(x for x in lst if x.get(k) == v)
    drmeera = by(merchants, "merchant_id", "m_001_drmeera_dentist_delhi")
    priya = by(customers, "customer_id", "c_001_priya_for_m001")
    research = by(triggers, "id", "trg_001_research_digest_dentists")
    recall = by(triggers, "id", "trg_003_recall_due_priya")
    competitor = by(triggers, "id", "trg_023_competitor_opened_dentist")
    return cat, drmeera, priya, research, recall, competitor


def _print_msg(label: str, msg, target: str):
    print()
    print("=" * 78)
    print(f"  {label}")
    print(f"  Target: {target}")
    print("=" * 78)
    if msg is None:
        print("  RESULT: compose() refused to send (returned None)")
        return
    print(f"  send_as:         {msg.send_as}")
    print(f"  cta:             {msg.cta}")
    print(f"  template_name:   {msg.template_name}")
    print(f"  body_len:        {len(msg.body or '')} chars")
    print()
    print("  ─── BODY ──────────────────────────────────────────────────────────────────")
    for line in (msg.body or "").split("\n"):
        print(f"  {line}")
    print("  ───────────────────────────────────────────────────────────────────────────")
    print()
    print(f"  rationale: {msg.rationale[:400]}")


# ─── Synthetic validator unit tests ─────────────────────────────────────────

def test_validators_unit():
    print("\n[unit-tests] validators")
    from validators import validate_pipeline

    cat = {
        "slug": "dentists",
        "voice": {"tone": "peer_clinical", "vocab_taboo": ["guaranteed", "miracle"]},
        "peer_stats": {"avg_ctr": 0.030, "avg_review_count": 62},
    }
    mer = {
        "merchant_id": "m_x",
        "identity": {"name": "Dr. X Clinic", "owner_first_name": "X", "languages": ["en"]},
        "performance": {"ctr": 0.021},
    }
    trg = {"kind": "research_digest", "payload": {}}
    plan = {"language": "en", "cta_shape": "open_ended", "send_as": "vera"}

    # 1. URL strip
    body = "Hi Dr. X, check https://fake-spam.example.com for details. Want me to draft? "
    r = validate_pipeline(body, plan=plan, category=cat, merchant=mer, trigger=trg)
    assert "fake-spam" not in r.body, "URL not stripped"
    print("  [OK] url_strip removes fabricated URL")

    # 2. Taboo
    body = "Hi Dr. X, this is guaranteed to work. Want me to draft? "
    r = validate_pipeline(body, plan=plan, category=cat, merchant=mer, trigger=trg)
    assert not r.passed and r.failed_validator == "taboos", f"taboo not caught: {r}"
    print("  [OK] taboos rejects 'guaranteed'")

    # 3. Length
    body = "ok"
    r = validate_pipeline(body, plan=plan, category=cat, merchant=mer, trigger=trg)
    assert not r.passed and r.failed_validator == "length", f"length not caught: {r}"
    print("  [OK] length rejects too-short body")

    # 4. CTA shape mismatch
    body = "Dr. X, your CTR is 2.1% — below peer median. Just an FYI."
    plan_b = {"language": "en", "cta_shape": "binary_yes_no", "send_as": "vera"}
    r = validate_pipeline(body, plan=plan_b, category=cat, merchant=mer, trigger=trg)
    assert not r.passed and r.failed_validator == "cta_shape", f"cta not caught: {r}"
    print("  [OK] cta_shape rejects missing binary CTA")

    # 5. Multi-CTA
    body = "Dr. X, want me to A? Or B? Reply YES for X, NO for Y, MAYBE for Z."
    r = validate_pipeline(body, plan=plan, category=cat, merchant=mer, trigger=trg)
    assert not r.passed and r.failed_validator == "cta_shape", f"multi-CTA not caught: {r}"
    print("  [OK] cta_shape rejects multi-CTA")

    # 6. Language (hi-en mix required)
    plan_hi = {"language": "hi-en mix", "cta_shape": "open_ended", "send_as": "vera"}
    body = "Hi Dr. X, your CTR is 2.1% versus peer median 3.0%. Want me to draft? "
    r = validate_pipeline(body, plan=plan_hi, category=cat, merchant=mer, trigger=trg)
    assert not r.passed and r.failed_validator == "language", f"language not caught: {r}"
    print("  [OK] language rejects pure-English body when hi-en mix required")

    body_hi = "Hi Dr. X, apke CTR 2.1% hai (peer 3.0%). Kya main draft kar du? "
    r = validate_pipeline(body_hi, plan=plan_hi, category=cat, merchant=mer, trigger=trg)
    assert r.passed, f"hi-en mix should pass: {r}"
    print("  [OK] language accepts hi-en mix body")

    # 7. Repetition
    body = "Same body verbatim. Want me to draft? "
    history = [{"from": "vera", "body": "Same body verbatim. Want me to draft? "}]
    r = validate_pipeline(body, plan=plan, category=cat, merchant=mer, trigger=trg,
                          conversation_history=history)
    assert not r.passed and r.failed_validator == "repetition", f"rep not caught: {r}"
    print("  [OK] repetition rejects duplicate body")

    # 8. Fabrication (₹999 not in any context)
    body = "Dr. X, special promo ₹999 for cleaning. Want me to draft? "
    r = validate_pipeline(body, plan=plan, category=cat, merchant=mer, trigger=trg)
    assert not r.passed and r.failed_validator == "fabrication", f"fab not caught: {r}"
    print("  [OK] fabrication catches invented ₹999")

    # 9. Salutation (first turn must use owner)
    body = "Hi there! Just a quick check on this week's profile updates. Want me to draft a post? "
    r = validate_pipeline(body, plan=plan, category=cat, merchant=mer, trigger=trg)
    assert not r.passed and r.failed_validator == "salutation", f"salutation not caught: {r}"
    print("  [OK] salutation rejects 'Hi there' first message")

    # 10. Vera re-intro on subsequent turn
    body = "Hi, I'm Vera again from magicpin — just circling back on this thread. Want me to draft a follow-up? "
    history = [{"from": "vera", "body": "Hi Dr. X, intro msg."}]
    r = validate_pipeline(body, plan=plan, category=cat, merchant=mer, trigger=trg,
                          conversation_history=history)
    assert not r.passed and r.failed_validator == "salutation", f"re-intro not caught: {r}"
    print("  [OK] salutation rejects 'I'm Vera' on subsequent turn")

    print("[unit-tests] all 10 validator cases pass")


async def _main():
    print("─── Phase F+G: validators + self-score + refine ───")

    # 1. Run synthetic validator unit tests first
    test_validators_unit()

    # 2. Run E2E composer tests
    from composer.compose import compose
    from llm.groq_client import get_groq

    print("\n[setup] Connect Groq + prewarm...")
    groq = get_groq()
    await groq.connect()
    await groq.prewarm()

    cat, drmeera, priya, research, recall, competitor = _load_seeds()

    print("\n[scenario 1] Dr. Meera + research_digest...")
    msg1 = await compose(category=cat, merchant=drmeera, trigger=research)
    _print_msg(
        "Scenario 1 — Dr. Meera + research_digest",
        msg1,
        "Case Study 1 (50/50): JIDA cite + 38% + 124-cohort + reciprocity + open CTA",
    )

    print("\n[scenario 2] Priya + recall_due (hi-en mix)...")
    msg2 = await compose(category=cat, merchant=drmeera, trigger=recall, customer=priya)
    _print_msg(
        "Scenario 2 — Priya + recall_due (customer-facing, hi-en mix)",
        msg2,
        "Case Study 2 (49/50): warm + name + hi-en mix + slots + ₹299 + multi-choice CTA",
    )

    print("\n[scenario 3] competitor_opened (UNSEEN KIND)...")
    msg3 = await compose(category=cat, merchant=drmeera, trigger=competitor)
    _print_msg(
        "Scenario 3 — competitor_opened (UNSEEN KIND, kind_default)",
        msg3,
        "Default-kind handler: peer-tone + competitor specificity + binary CTA",
    )

    await groq.close()

    # Summary — assert the single-pass contract (structure, not self-scores).
    from validators import internal_jargon
    msgs = [msg1, msg2, msg3]
    print("\n─── composer summary ───")
    all_ok = True
    for i, m in enumerate(msgs, 1):
        if m is None:
            print(f"  Scenario {i}: REFUSED (returned None)")
            all_ok = False
            continue
        body = m.body or ""
        jargon_ok, jargon_err, _, _ = internal_jargon.check(body)
        checks = {
            "non_empty": len(body) >= 30,
            "valid_cta": m.cta in ("binary_yes_no", "open_ended", "multi_choice_slot", "none"),
            "valid_send_as": m.send_as in ("vera", "merchant_on_behalf"),
            "no_jargon": jargon_ok,
        }
        status = "OK" if all(checks.values()) else "FAIL " + str([k for k, v in checks.items() if not v])
        all_ok = all_ok and all(checks.values())
        print(f"  Scenario {i}: {status}  (cta={m.cta}, send_as={m.send_as}, {len(body)} chars)")

    print("\n  ✅ single-pass contract met." if all_ok else "\n  ⚠️ contract violation — investigate.")


if __name__ == "__main__":
    asyncio.run(_main())
