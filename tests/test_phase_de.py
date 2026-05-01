"""
Phase D+E verification — Groq client + composer PLAN→DRAFT pipeline.

Runs compose() end-to-end against three real seed scenarios and prints output
for subjective quality evaluation:

1. MERCHANT-FACING — Dr. Meera + research_digest (Case Study 1 target)
2. CUSTOMER-FACING — Dr. Meera + Priya + recall_due (Case Study 2 target)
3. UNSEEN KIND — Dr. Meera + competitor_opened (default-kind handler test)

Run from submission/:
    PYTHONIOENCODING=utf-8 python -m tests.test_phase_de
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

    by_id = lambda lst, key, val: next(x for x in lst if x.get(key) == val)
    drmeera = by_id(merchants, "merchant_id", "m_001_drmeera_dentist_delhi")
    priya = by_id(customers, "customer_id", "c_001_priya_for_m001")
    research_trg = by_id(triggers, "id", "trg_001_research_digest_dentists")
    recall_trg = by_id(triggers, "id", "trg_003_recall_due_priya")
    competitor_trg = by_id(triggers, "id", "trg_023_competitor_opened_dentist")

    return cat, drmeera, priya, research_trg, recall_trg, competitor_trg


def _print_result(label: str, msg, scenario_target: str):
    print()
    print("=" * 78)
    print(f"  {label}")
    print(f"  Target quality: {scenario_target}")
    print("=" * 78)
    if msg is None:
        print("  RESULT: compose() refused to send (returned None)")
        return
    print(f"  send_as:         {msg.send_as}")
    print(f"  cta:             {msg.cta}")
    print(f"  suppression_key: {msg.suppression_key}")
    print(f"  template_name:   {msg.template_name}")
    print()
    print("  ─── BODY ──────────────────────────────────────────────────────────────────")
    for line in (msg.body or "").split("\n"):
        print(f"  {line}")
    print("  ───────────────────────────────────────────────────────────────────────────")
    print()
    print(f"  rationale: {msg.rationale[:300]}")


async def _main():
    print("─── Phase D+E: Groq client + composer PLAN→DRAFT ───")

    from composer.compose import compose
    from llm.groq_client import get_groq

    print("\n[1/4] Connect Groq + prewarm 4 models...")
    groq = get_groq()
    await groq.connect()
    await groq.prewarm()

    print("\n[2/4] Load seed dataset...")
    cat, drmeera, priya, research_trg, recall_trg, competitor_trg = _load_seeds()
    print(f"  category: {cat['slug']}")
    print(f"  merchant: {drmeera['identity']['name']} ({drmeera['identity']['locality']})")
    print(f"  customer: {priya['identity']['name']}")

    print("\n[3/4] Compose 3 scenarios...")

    msg1 = await compose(category=cat, merchant=drmeera, trigger=research_trg)
    _print_result(
        "Scenario 1 — Dr. Meera + research_digest (merchant-facing)",
        msg1,
        "Case Study 1 (50/50): source citation + cohort match + reciprocity + low-friction CTA",
    )

    msg2 = await compose(category=cat, merchant=drmeera, trigger=recall_trg, customer=priya)
    _print_result(
        "Scenario 2 — Priya + recall_due (customer-facing, hi-en mix)",
        msg2,
        "Case Study 2 (49/50): warm + name + hi-en mix + concrete slots + ₹299 + multi-choice CTA",
    )

    msg3 = await compose(category=cat, merchant=drmeera, trigger=competitor_trg)
    _print_result(
        "Scenario 3 — competitor_opened (UNSEEN KIND — kind_default test)",
        msg3,
        "default-kind handler: peer-tone + competitor-aware specificity + binary CTA",
    )

    print("\n[4/4] Closing Groq connection...")
    await groq.close()

    all_ok = all([
        msg1 and len(msg1.body) > 50,
        msg2 and len(msg2.body) > 50 and msg2.send_as == "merchant_on_behalf",
        msg3 and len(msg3.body) > 50,
    ])
    print()
    if all_ok:
        print("✅ Phase D+E: pipeline produced 3 valid messages.")
        print("   Subjectively evaluate above — bodies should match the case-study quality bar.")
    else:
        print("❌ Phase D+E: at least one scenario produced empty/invalid output.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_main())
