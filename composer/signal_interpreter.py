"""
Signal interpreter — converts raw merchant signals into composer-ready hints.

Raw signals are terse codes (`stale_posts:22d`, `ctr_below_peer_median`,
`high_risk_adult_cohort`). We translate them into natural-language hints with
peer benchmarks pulled from the category's peer_stats. The DRAFT prompt then
sees both the raw code AND the interpreted hint, freeing the LLM to focus on
framing rather than translation.
"""

from __future__ import annotations

import re
from typing import Any


# Match e.g. "stale_posts:22d", "perf_dip:7d", "lapsed:90d"
_DURATION_SIGNAL = re.compile(r"^([a-z_]+):(\d+)d$")


def interpret_signals(
    signals: list[str],
    merchant: dict[str, Any],
    category: dict[str, Any] | None = None,
) -> list[str]:
    """Convert raw signals to plain-English hints. Unknown signals pass through."""
    hints: list[str] = []
    peer_stats = (category or {}).get("peer_stats", {}) or {}
    perf = (merchant or {}).get("performance", {}) or {}

    for sig in signals or []:
        sig = (sig or "").strip()
        if not sig:
            continue

        m = _DURATION_SIGNAL.match(sig)
        if m:
            kind, days = m.group(1), int(m.group(2))
            hint = _interpret_duration_signal(kind, days, peer_stats)
            hints.append(hint)
            continue

        if sig == "ctr_below_peer_median":
            ctr = perf.get("ctr")
            peer_ctr = peer_stats.get("avg_ctr")
            if ctr is not None and peer_ctr:
                hints.append(
                    f"CTR {ctr*100:.1f}% vs peer median {peer_ctr*100:.1f}% "
                    f"({(ctr-peer_ctr)/peer_ctr*100:+.0f}% gap)"
                )
            else:
                hints.append("CTR is below peer median for this category")
            continue

        if sig == "above_peer_median_calls":
            calls = perf.get("calls")
            peer_calls = peer_stats.get("avg_calls_30d")
            if calls is not None and peer_calls:
                hints.append(
                    f"Calls {calls} vs peer median {peer_calls} "
                    f"({(calls-peer_calls)/peer_calls*100:+.0f}% above)"
                )
            else:
                hints.append("Calls volume is above peer median")
            continue

        if sig == "high_risk_adult_cohort":
            count = (
                merchant.get("customer_aggregate", {}) or {}
            ).get("high_risk_adult_count")
            if count:
                hints.append(f"{count} high-risk adult patients in roster")
            else:
                hints.append("Has a high-risk adult patient cohort")
            continue

        if sig == "engaged_in_last_48h":
            hints.append("Merchant replied to Vera in the last 48h (warm)")
            continue

        if sig == "no_active_offers":
            hints.append("No active offers right now — opportunity to add one")
            continue

        if sig == "high_engagement":
            hints.append("Merchant engagement is high recently")
            continue

        if sig == "growing_views_7d":
            d = (perf.get("delta_7d") or {}).get("views_pct")
            if d is not None:
                hints.append(f"Views growing {d*100:+.0f}% week-over-week")
            else:
                hints.append("Views growing this week")
            continue

        if sig == "perf_dip_severe":
            d = (perf.get("delta_7d") or {}).get("calls_pct")
            if d is not None:
                hints.append(f"Calls down {d*100:+.0f}% week-over-week (severe dip)")
            else:
                hints.append("Severe performance dip recently")
            continue

        if sig == "renewal_due_soon":
            days = (merchant.get("subscription") or {}).get("days_remaining")
            if days is not None:
                hints.append(f"Subscription renews in {days} days")
            else:
                hints.append("Subscription renewal due soon")
            continue

        if sig == "unverified_gbp":
            hints.append("Google Business Profile is unverified")
            continue

        # Fallback: pass through with light prettification
        hints.append(sig.replace("_", " ").replace(":", " "))

    return hints


def _interpret_duration_signal(kind: str, days: int, peer_stats: dict[str, Any]) -> str:
    if kind == "stale_posts":
        peer = peer_stats.get("avg_post_freq_days")
        if peer:
            return f"Last GBP post was {days} days ago (peer cadence ~{peer}d)"
        return f"Last GBP post was {days} days ago"
    if kind == "dormant_with_vera":
        return f"No merchant message to Vera in {days} days"
    if kind == "perf_dip":
        return f"Performance dip began {days} days ago"
    if kind == "lapsed":
        return f"Last visit was {days} days ago"
    return f"{kind.replace('_', ' ')} for {days} days"
