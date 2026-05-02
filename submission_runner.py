"""
submission_runner.py — produces submission.jsonl from the canonical 30 pairs.

Reads from ../expanded/ (output of dataset/generate_dataset.py):
    expanded/test_pairs.json
    expanded/categories/{slug}.json
    expanded/merchants/{merchant_id}.json
    expanded/customers/{customer_id}.json
    expanded/triggers/{trigger_id}.json

For each test pair:
  1. Load contexts
  2. Call compose() (offline — no HTTP)
  3. Write JSONL line:
        {"test_id": "T01", "body": "...", "cta": "...", "send_as": "...",
         "suppression_key": "...", "rationale": "..."}

Determinism: temperature=0 for DRAFT and SELF-SCORE per challenge brief §7.

Run from submission/:
    PYTHONIOENCODING=utf-8 python submission_runner.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPANDED_DIR = REPO_ROOT / "expanded"


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def _run_one(test_id: str, merchant_id: str, trigger_id: str, customer_id: str | None):
    from composer.compose import compose

    # Load trigger
    try:
        trigger = _load_json(EXPANDED_DIR / "triggers" / f"{trigger_id}.json")
    except FileNotFoundError:
        return {"test_id": test_id, "error": f"trigger not found: {trigger_id}"}

    # Load merchant
    try:
        merchant = _load_json(EXPANDED_DIR / "merchants" / f"{merchant_id}.json")
    except FileNotFoundError:
        return {"test_id": test_id, "error": f"merchant not found: {merchant_id}"}

    # Load category
    cat_slug = merchant.get("category_slug")
    if not cat_slug:
        return {"test_id": test_id, "error": f"merchant has no category_slug: {merchant_id}"}
    try:
        category = _load_json(EXPANDED_DIR / "categories" / f"{cat_slug}.json")
    except FileNotFoundError:
        return {"test_id": test_id, "error": f"category not found: {cat_slug}"}

    # Load customer (optional)
    customer = None
    if customer_id:
        try:
            customer = _load_json(EXPANDED_DIR / "customers" / f"{customer_id}.json")
        except FileNotFoundError:
            customer = None  # graceful — challenge brief allows missing

    # Compose
    try:
        msg = await compose(category, merchant, trigger, customer)
    except Exception as e:  # noqa: BLE001
        return {"test_id": test_id, "error": f"compose exception: {type(e).__name__}: {e}"}

    if msg is None:
        return {
            "test_id": test_id,
            "body": "",
            "cta": "none",
            "send_as": "vera",
            "suppression_key": trigger.get("suppression_key", ""),
            "rationale": "compose() returned None (refused to send)",
        }

    return {
        "test_id": test_id,
        "body": msg.body,
        "cta": msg.cta,
        "send_as": msg.send_as,
        "suppression_key": msg.suppression_key,
        "rationale": msg.rationale,
        "self_scores": msg.self_scores,
        "template_name": msg.template_name,
        "template_params": msg.template_params,
    }


async def _main(out_path: Path, parallel: bool = False):
    if not EXPANDED_DIR.exists():
        print(f"❌ {EXPANDED_DIR} not found. Run: python dataset/generate_dataset.py --seed-dir dataset --out expanded")
        sys.exit(1)

    pairs_file = EXPANDED_DIR / "test_pairs.json"
    pairs = _load_json(pairs_file).get("pairs", [])
    print(f"Loaded {len(pairs)} canonical test pairs from {pairs_file}")

    from llm.groq_client import get_groq

    groq = get_groq()
    await groq.connect()
    await groq.prewarm()
    print()

    results = []
    if parallel:
        # Parallel — faster but may hit Groq RPM
        sem = asyncio.Semaphore(3)

        async def _wrap(p):
            async with sem:
                t0 = time.time()
                r = await _run_one(
                    p["test_id"], p["merchant_id"], p["trigger_id"], p.get("customer_id")
                )
                r["latency_ms"] = int((time.time() - t0) * 1000)
                return r

        results = await asyncio.gather(*[_wrap(p) for p in pairs])
    else:
        # Sequential — safer for Groq TPM
        for p in pairs:
            t0 = time.time()
            r = await _run_one(
                p["test_id"], p["merchant_id"], p["trigger_id"], p.get("customer_id")
            )
            r["latency_ms"] = int((time.time() - t0) * 1000)
            status = "OK" if r.get("body") else "ERR" if r.get("error") else "REFUSED"
            print(f"  [{status:7}] {p['test_id']:5} {r.get('latency_ms', 0)}ms  "
                  f"score={sum((r.get('self_scores') or {}).values())}/50  "
                  f"body[:80]={r.get('body', r.get('error', ''))[:80]!r}")
            results.append(r)
            # Pause between pairs to avoid Groq TPM bursts. With 2-key round-robin
            # (effective 2× TPM), 10s sleep = 6 pairs/min — under combined caps.
            await asyncio.sleep(10.0)

    await groq.close()

    # Write JSONL — strip internal fields not in the official schema
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            line = {
                "test_id": r["test_id"],
                "body": r.get("body", ""),
                "cta": r.get("cta", "none"),
                "send_as": r.get("send_as", "vera"),
                "suppression_key": r.get("suppression_key", ""),
                "rationale": r.get("rationale", ""),
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    # Summary
    n = len(results)
    n_ok = sum(1 for r in results if r.get("body"))
    n_err = sum(1 for r in results if r.get("error"))
    n_refused = n - n_ok - n_err
    scores = [sum((r.get("self_scores") or {}).values()) for r in results if r.get("body")]
    avg = sum(scores) / len(scores) if scores else 0

    print()
    print("=" * 78)
    print(f"  SUBMISSION SUMMARY: {n} pairs")
    print(f"    shipped:  {n_ok}")
    print(f"    refused:  {n_refused}")
    print(f"    error:    {n_err}")
    print(f"    avg self-score: {avg:.1f}/50  ({avg*2:.0f}%)")
    print(f"  Wrote {out_path}")
    print("=" * 78)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="submission.jsonl",
                        help="Output JSONL path (relative to submission/)")
    parser.add_argument("--parallel", action="store_true",
                        help="Run in parallel (concurrency=3). Default: sequential.")
    args = parser.parse_args()
    out_path = Path(__file__).parent / args.out
    asyncio.run(_main(out_path, parallel=args.parallel))
