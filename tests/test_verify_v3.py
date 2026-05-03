"""
Verify-after-fab-fix v3: uses brand-new merchant IDs that haven't been touched
in this session, so the 4h cadence guard doesn't block.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

import httpx
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
BASE_URL = "https://magicpin-5z8k.onrender.com"


def number_search(body: str, haystack: str) -> tuple[list[str], list[str]]:
    nums = re.findall(r"\b\d{2,}(?:[,.]\d+)?\b", body)
    haystack_nodots = haystack.replace(",", "")
    grounded, suspicious = [], []
    for n in set(nums):
        normalized = n.replace(",", "").rstrip(".0").lstrip("0") or "0"
        if normalized in haystack_nodots or n in haystack:
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


def clone_with_new_id(payload: dict, new_id: str, id_field: str) -> dict:
    p = deepcopy(payload)
    p[id_field] = new_id
    return p


async def main():
    cat_dent = json.load(open(DATASET_DIR / "categories" / "dentists.json", encoding="utf-8"))
    cat_salons = json.load(open(DATASET_DIR / "categories" / "salons.json", encoding="utf-8"))
    merchants = json.load(open(DATASET_DIR / "merchants_seed.json", encoding="utf-8"))["merchants"]
    triggers = json.load(open(DATASET_DIR / "triggers_seed.json", encoding="utf-8"))["triggers"]
    drmeera = next(m for m in merchants if m["merchant_id"] == "m_001_drmeera_dentist_delhi")
    studio11 = next(m for m in merchants if m["merchant_id"] == "m_003_studio11_salon_hyderabad")
    research = next(t for t in triggers if t["id"] == "trg_001_research_digest_dentists")
    curious = next(t for t in triggers if t["id"] == "trg_008_curious_ask_studio11")

    # Clone with brand-new IDs to bypass cadence guard
    drmeera_v2 = clone_with_new_id(drmeera, "m_v3_drmeera_dent_test", "merchant_id")
    studio11_v2 = clone_with_new_id(studio11, "m_v3_studio11_salon_test", "merchant_id")
    research_v2 = deepcopy(research)
    research_v2["id"] = "trg_v3_research_test"
    research_v2["merchant_id"] = "m_v3_drmeera_dent_test"
    research_v2["suppression_key"] = "verify_v3:research:dentists:fresh"
    curious_v2 = deepcopy(curious)
    curious_v2["id"] = "trg_v3_curious_test"
    curious_v2["merchant_id"] = "m_v3_studio11_salon_test"
    curious_v2["suppression_key"] = "verify_v3:curious:studio11:fresh"

    print("═" * 80)
    print("  Verify-v3 — fabrication-fix on FRESH merchant IDs (no cadence)")
    print("═" * 80)

    async with httpx.AsyncClient(timeout=60) as client:
        for scope, cid, payload in [
            ("category", "dentists", cat_dent),
            ("category", "salons", cat_salons),
            ("merchant", "m_v3_drmeera_dent_test", drmeera_v2),
            ("merchant", "m_v3_studio11_salon_test", studio11_v2),
            ("trigger", "trg_v3_research_test", research_v2),
            ("trigger", "trg_v3_curious_test", curious_v2),
        ]:
            r = await client.post(f"{BASE_URL}/v1/context", json={
                "scope": scope, "context_id": cid, "version": 100,
                "payload": payload, "delivered_at": "2026-05-02T10:00:00Z",
            })
            print(f"  pushed {scope}/{cid}: {r.status_code} accepted={r.json().get('accepted')}")

        haystack_dent = flatten(cat_dent) + " " + flatten(drmeera_v2) + " " + flatten(research_v2)
        haystack_salons = flatten(cat_salons) + " " + flatten(studio11_v2) + " " + flatten(curious_v2)

        for label, trg_id, haystack in [
            ("research_digest", "trg_v3_research_test", haystack_dent),
            ("curious_ask", "trg_v3_curious_test", haystack_salons),
        ]:
            print()
            print("─" * 80)
            print(f"  {label}")
            print("─" * 80)
            r = await client.post(f"{BASE_URL}/v1/tick", json={
                "now": "2026-05-02T11:30:00+05:30",
                "available_triggers": [trg_id],
            })
            actions = r.json().get("actions", []) if r.status_code == 200 else []
            if not actions:
                print("  [NO ACTION]")
                continue
            a = actions[0]
            body = a.get("body", "")
            rationale = a.get("rationale", "")
            grounded, suspicious = number_search(body, haystack)
            print(f"  body: {body[:400]!r}")
            print()
            print(f"  rationale: {rationale}")
            print()
            print(f"  numbers grounded:    {grounded}")
            print(f"  numbers suspicious:  {suspicious}")
            if not suspicious:
                print(f"  ✅ no fabricated numbers")
            else:
                print(f"  ⚠️  potentially-fabricated numbers")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
