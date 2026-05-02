"""
redo_empty.py — re-runs ONLY the test pairs that have empty bodies in
submission.jsonl. Uses 30s inter-pair pacing to ride through Groq RPM/TPM
rate-limits cleanly.

This is non-destructive: it preserves all OK rows and only retries empties.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)
sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPANDED_DIR = REPO_ROOT / "expanded"
JSONL = Path(__file__).resolve().parent / "submission.jsonl"


def _load_jsonl():
    rows = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _save_jsonl(rows):
    with open(JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


async def _main():
    from submission_runner import _run_one
    from llm.groq_client import get_groq

    pairs = json.load(open(EXPANDED_DIR / "test_pairs.json", encoding="utf-8"))["pairs"]
    pair_by_id = {p["test_id"]: p for p in pairs}

    rows = _load_jsonl()
    empties = [r for r in rows if not r.get("body")]
    oks = [r for r in rows if r.get("body")]
    print(f"Loaded {len(rows)} rows: {len(oks)} OK, {len(empties)} empty")

    if not empties:
        print("Nothing to redo.")
        return

    groq = get_groq()
    await groq.connect()
    await groq.prewarm()
    print()

    redone = []
    for i, r in enumerate(empties, 1):
        tid = r["test_id"]
        p = pair_by_id.get(tid)
        if not p:
            print(f"  [{i}/{len(empties)}] {tid}: pair not in test_pairs.json — skipping")
            redone.append(r)
            continue

        print(f"  [{i}/{len(empties)}] redoing {tid}...")
        new = await _run_one(tid, p["merchant_id"], p["trigger_id"], p.get("customer_id"))
        if new.get("body"):
            print(f"    OK score={sum((new.get('self_scores') or {}).values())}/50  "
                  f"body[:80]={new['body'][:80]!r}")
        elif new.get("error"):
            print(f"    ERR {new['error'][:120]}")
        else:
            print(f"    REFUSED")
        # Always strip extra fields
        clean = {
            "test_id": new["test_id"],
            "body": new.get("body", ""),
            "cta": new.get("cta", "none"),
            "send_as": new.get("send_as", "vera"),
            "suppression_key": new.get("suppression_key", ""),
            "rationale": new.get("rationale", ""),
        }
        redone.append(clean if clean["body"] else r)  # don't overwrite with another empty
        # Long pause to let Groq RPM/TPM clear between pairs
        if i < len(empties):
            await asyncio.sleep(30.0)

    await groq.close()

    # Reassemble: OK rows + redone empties (preserves test_id ordering)
    redone_by_id = {r["test_id"]: r for r in redone}
    final = []
    for r in rows:
        if r.get("body"):
            final.append(r)
        else:
            final.append(redone_by_id.get(r["test_id"], r))

    _save_jsonl(final)
    n_ok = sum(1 for r in final if r.get("body"))
    print()
    print(f"Wrote {JSONL} — {n_ok}/{len(final)} have bodies.")


if __name__ == "__main__":
    asyncio.run(_main())
