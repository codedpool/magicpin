"""
Verify-after-fab-fix: test 2 scenarios on the live URL with version=99
contexts so it doesn't matter whether Render's already redeployed.

Tests:
1. research_digest (Dr. Meera) — should still nail Case Study 1 anchors
2. curious_ask (Lakshmi/Studio11) — should ASK the merchant cleanly,
   NOT invent social-proof numbers (the bug we just fixed)
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
BASE_URL = "https://magicpin-5z8k.onrender.com"


def number_search(body: str, contexts_haystack: str) -> tuple[list[str], list[str]]:
    """Return (grounded, suspicious) numbers from the body."""
    nums = re.findall(r"\b\d{2,}(?:[,.]\d+)?\b", body)
    haystack_nodots = contexts_haystack.replace(",", "")
    grounded, suspicious = [], []
    for n in set(nums):
        normalized = n.replace(",", "").rstrip(".0").lstrip("0") or "0"
        if normalized in haystack_nodots or n in contexts_haystack:
            grounded.append(n)
        else:
            try:
                v = float(normalized)
                ok = False
                for m in re.finditer(r"\d+(?:[.,]\d+)?", haystack_nodots):
                    other = float(m.group().replace(",", ""))
                    if v == 0 or other == 0:
                        if abs(v - other) <= 1:
                            ok = True
                            break
                    elif abs(v - other) / max(v, other) < 0.02:
                        ok = True
                        break
                (grounded if ok else suspicious).append(n)
            except ValueError:
                suspicious.append(n)
    return sorted(grounded), sorted(suspicious)


def flatten(o):
    if isinstance(o, str):
        return o
    if isinstance(o, (int, float, bool)):
        return str(o)
    if isinstance(o, dict):
        return " ".join(flatten(v) for v in o.values())
    if isinstance(o, list):
        return " ".join(flatten(x) for x in o)
    return ""


async def main():
    cat_dent = json.load(open(DATASET_DIR / "categories" / "dentists.json", encoding="utf-8"))
    cat_salons = json.load(open(DATASET_DIR / "categories" / "salons.json", encoding="utf-8"))
    merchants = json.load(open(DATASET_DIR / "merchants_seed.json", encoding="utf-8"))["merchants"]
    triggers = json.load(open(DATASET_DIR / "triggers_seed.json", encoding="utf-8"))["triggers"]
    drmeera = next(m for m in merchants if m["merchant_id"] == "m_001_drmeera_dentist_delhi")
    studio11 = next(m for m in merchants if m["merchant_id"] == "m_003_studio11_salon_hyderabad")
    research = next(t for t in triggers if t["id"] == "trg_001_research_digest_dentists")
    curious = next(t for t in triggers if t["id"] == "trg_008_curious_ask_studio11")

    print("═" * 80)
    print("  Verify run — fabrication-fix patch")
    print("  Live URL: " + BASE_URL)
    print("═" * 80)

    async with httpx.AsyncClient(timeout=60) as client:
        # Force-replace via version=99
        for scope, cid, payload in [
            ("category", "dentists", cat_dent),
            ("category", "salons", cat_salons),
            ("merchant", drmeera["merchant_id"], drmeera),
            ("merchant", studio11["merchant_id"], studio11),
            ("trigger", research["id"], research),
            ("trigger", curious["id"], curious),
        ]:
            r = await client.post(f"{BASE_URL}/v1/context", json={
                "scope": scope, "context_id": cid, "version": 99,
                "payload": payload, "delivered_at": "2026-05-02T10:00:00Z",
            })
            print(f"  pushed {scope}/{cid}: status={r.status_code} accepted={r.json().get('accepted')}")

        # Build haystacks for fabrication audit
        haystack_dent = flatten(cat_dent) + " " + flatten(drmeera) + " " + flatten(research)
        haystack_salons = flatten(cat_salons) + " " + flatten(studio11) + " " + flatten(curious)

        for label, trg_id, haystack in [
            ("research_digest (Dr. Meera)", research["id"], haystack_dent),
            ("curious_ask (Lakshmi)", curious["id"], haystack_salons),
        ]:
            print()
            print("─" * 80)
            print(f"  {label}")
            print("─" * 80)

            # Different now-time per scenario so cadence guard sees them as different
            now_iso = "2026-05-02T11:30:00+05:30" if label.startswith("research") else "2026-05-02T13:00:00+05:30"
            r = await client.post(f"{BASE_URL}/v1/tick", json={
                "now": now_iso,
                "available_triggers": [trg_id],
            })
            actions = r.json().get("actions", []) if r.status_code == 200 else []
            if not actions:
                print("  [SKIP] no actions (cadence-blocked or refused)")
                continue
            a = actions[0]
            body = a.get("body", "")
            rationale = a.get("rationale", "")
            grounded, suspicious = number_search(body, haystack)
            print(f"  body[:300]: {body[:300]!r}")
            print()
            print(f"  rationale: {rationale}")
            print()
            print(f"  numbers grounded:    {grounded}")
            print(f"  numbers suspicious:  {suspicious}")
            if not suspicious:
                print(f"  ✅ no fabricated numbers")
            else:
                print(f"  ⚠️  potentially-fabricated numbers in body")
            await asyncio.sleep(8)

        print()
        print("═" * 80)


if __name__ == "__main__":
    asyncio.run(main())
