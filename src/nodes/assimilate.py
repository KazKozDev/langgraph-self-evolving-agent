"""
assimilate_best node — absorb winning strategies into system prompt / skill store.
Inspired by PEAM (arXiv:2605.27762) — experience internalisation.
"""
from __future__ import annotations

from src.memory.store import get_store
from src.state import EvolutionState


def assimilate_best(state: EvolutionState) -> dict:
    """Absorb the best policy and extracted skills into persistent memory.

    This is the final processing node — it writes the winning strategy
    as an updated skill and increments metrics.
    """
    store = get_store()
    best_policy = state.get("best_policy")
    extracted_skills = state.get("extracted_skills", [])

    updates = []

    # ── Assimilate extracted skills ────────────────────────────
    for sk in extracted_skills:
        # Already saved during extraction; just log
        updates.append(f"skill_created: {sk.get('name')}")

    # ── Assimilate best policy as skill improvement ────────────
    if best_policy and best_policy.get("suggest_skill_update"):
        # Create a meta-skill: "prefer this strategy pattern"
        strategy_skill = {
            "name": f"strategy-{best_policy.get('strategy_id', 'X').lower()}",
            "triggers": [f"When approaching a task similar to the one this strategy won on"],
            "steps": [
                f"Use strategy pattern: {best_policy.get('strategy_desc', '')}",
                "Verify the approach fits the specific task before applying",
            ],
            "pitfalls": [
                f"Strategy won with {best_policy.get('steps', '?')} steps; may need adaptation",
            ],
            "success_rate": best_policy.get("quality_scores", {}).get("correctness", 7) / 10,
            "use_count": 0,
            "domain": "",
        }
        store.save_skill(strategy_skill)
        updates.append(f"strategy_skill_created: {strategy_skill['name']}")
        store.increment_metric("total_improvements")

    # ── Handle degraded skills ──────────────────────────────────
    degraded = state.get("degraded_skills", [])
    for sk in degraded:
        # Lower success rate to trigger retraining
        store.update_success_rate(sk["name"], False)
        updates.append(f"degraded_flagged: {sk['name']}")

    # ── Update metrics ──────────────────────────────────────────
    cycle = state.get("cycle", 0) + 1
    store.set_metric("last_cycle", cycle)
    store.set_metric("total_skills", len(store.get_skills()))

    return {
        "phase": "done",
        "cycle": cycle,
        "error": None,
    }
