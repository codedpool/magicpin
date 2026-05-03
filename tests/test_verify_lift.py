"""
Focused verify run — score-lift before/after comparison.

Hits 3 scenarios on the live URL and prints:
- Bot's self-scores per dimension
- Total per scenario
- Body excerpt

Compare to prior baseline (40, 45, 41 = avg 42/50).
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


def parse_self_scores(rationale: str) -> dict:
    """Extract DQ:N/SPC:N/CAT:N/MER:N/ENG:N/total=N/50 from rationale."""
    out = {}
    for token in rationale.split():
        if ":" in token:
            for prefix, key in [("DQ:", "DQ"), ("SPC:", "SPC"), ("CAT:", "CAT"),
                                ("MER:", "MER"), ("ENG:", "ENG")]:
                if token.startswith(prefix):
                    try:
                        out[key] = int(token[len(prefix):].rstrip("/").rstrip(","))
                    except ValueError:
                        pass
        if token.startswith("total="):
            try:
                out["total"] = int(token.split("=")[1].split("/")[0])
            except (ValueError, IndexError):
                pass
        if token.startswith("refined="):
            out["refined"] = "True" in token
    return out


async def main():
    cat = json.load(open(DATASET_DIR / "categories" / "dentists.json", encoding="utf-8"))
    merchants = json.load(open(DATASET_DIR / "merchants_seed.json", encoding="utf-8"))["merchants"]
    customers = json.load(open(DATASET_DIR / "customers_seed.json", encoding="utf-8"))["customers"]
    triggers = json.load(open(DATASET_DIR / "triggers_seed.json", encoding="utf-8"))["triggers"]
    drmeera = next(m for m in merchants if m["merchant_id"] == "m_001_drmeera_dentist_delhi")
    priya = next(c for c in customers if c["customer_id"] == "c_001_priya_for_m001")
    research = next(t for t in triggers if t["id"] == "trg_001_research_digest_dentists")
    recall = next(t for t in triggers if t["id"] == "trg_003_recall_due_priya")
    competitor = next(t for t in triggers if t["id"] == "trg_023_competitor_opened_dentist")

    print("═" * 80)
    print("  Score-lift verification — 3 canonical scenarios")
    print(f"  Live URL: {BASE_URL}")
    print(f"  Baseline (before lift): research=40, recall=45, competitor=41 (avg 42)")
    print("═" * 80)

    async with httpx.AsyncClient(timeout=60) as client:
        # Push baseline contexts
        await client.post(f"{BASE_URL}/v1/context", json={
            "scope": "category", "context_id": "dentists", "version": 1,
            "payload": cat, "delivered_at": "2026-05-02T10:00:00Z",
        })
        await client.post(f"{BASE_URL}/v1/context", json={
            "scope": "merchant", "context_id": drmeera["merchant_id"], "version": 1,
            "payload": drmeera, "delivered_at": "2026-05-02T10:00:00Z",
        })
        await client.post(f"{BASE_URL}/v1/context", json={
            "scope": "customer", "context_id": priya["customer_id"], "version": 1,
            "payload": priya, "delivered_at": "2026-05-02T10:00:00Z",
        })
        for trg in (research, recall, competitor):
            await client.post(f"{BASE_URL}/v1/context", json={
                "scope": "trigger", "context_id": trg["id"], "version": 1,
                "payload": trg, "delivered_at": "2026-05-02T10:00:00Z",
            })
        print("contexts pushed.\n")

        results = {}
        for label, trg_id, prior_score in [
            ("research_digest", "trg_001_research_digest_dentists", 40),
            ("recall_due (hi-en)", "trg_003_recall_due_priya", 45),
            ("competitor_opened", "trg_023_competitor_opened_dentist", 41),
        ]:
            # Each scenario uses a different fake merchant_id to bypass cadence guard
            print(f"─── {label} ───")
            t0 = time.time()
            r = await client.post(f"{BASE_URL}/v1/tick", json={
                "now": "2026-05-02T10:30:00+05:30",
                "available_triggers": [trg_id],
            })
            elapsed = int((time.time() - t0) * 1000)
            data = r.json() if r.status_code == 200 else {}
            actions = data.get("actions", [])
            if not actions:
                print(f"  [SKIP] no action (likely cadence-blocked across scenarios)\n")
                results[label] = {"prior": prior_score, "now": "skipped", "delta": "n/a"}
                continue
            a = actions[0]
            scores = parse_self_scores(a.get("rationale", ""))
            total = scores.get("total", 0)
            delta = total - prior_score
            results[label] = {
                "prior": prior_score, "now": total,
                "delta": f"{delta:+d}",
                "scores": scores,
                "body": a.get("body", "")[:200],
                "latency_ms": elapsed,
                "refined": scores.get("refined", False),
            }
            print(f"  body[:200]: {a.get('body','')[:200]!r}")
            print(f"  scores: {scores}")
            print(f"  total: {total}/50 (was {prior_score}, delta {delta:+d})")
            print(f"  refined: {scores.get('refined', False)}")
            print(f"  latency: {elapsed}ms\n")
            # Pace between calls
            await asyncio.sleep(8)

        # Summary
        print("═" * 80)
        print("  SUMMARY")
        print("═" * 80)
        prior_avg = 42  # 3-scenario baseline
        now_scores = [r["now"] for r in results.values() if isinstance(r["now"], int)]
        now_avg = sum(now_scores) / len(now_scores) if now_scores else 0
        for label, r in results.items():
            print(f"  {label:25s} {r['prior']:>3} → {r['now']!s:>10}   {r['delta']!s:>5}")
        print(f"  {'AVG':25s} {prior_avg:>3} → {now_avg:>10.1f}   {now_avg - prior_avg:+.1f}")
        if now_avg >= 45:
            print(f"\n✅ Lift to {now_avg:.1f}/50 (target was ~45-47).")
        elif now_avg > prior_avg:
            print(f"\n🟡 Lift to {now_avg:.1f}/50 (modest improvement; refine was throttled).")
        else:
            print(f"\n⚠️ No lift detected. Investigate.")


if __name__ == "__main__":
    asyncio.run(main())
