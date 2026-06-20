"""
assimilate_best node — absorb winning strategies into skill store.
Optionally exports to GitHub when GITHUB_REPO_PATH is set.

Inspired by PEAM (arXiv:2605.27762) — experience internalisation.
"""
from __future__ import annotations

import os

from src.memory.store import get_store
from src.state import EvolutionState


def _maybe_export(skills: list[dict]):
    """Export skills to GitHub if configured."""
    if os.getenv("GITHUB_REPO_PATH"):
        try:
            from src.github_exporter import GitHubExporter
            exporter = GitHubExporter()
            result = exporter.export_all(skills)
            if result["exported"] > 0:
                print(f"  📤 GitHub: exported {result['exported']} skills", flush=True)
        except Exception:
            pass  # GitHub export is optional


def assimilate_best(state: EvolutionState) -> dict:
    """Absorb the best policy and extracted skills into persistent memory."""
    store = get_store()
    best_policy = state.get("best_policy")
    extracted_skills = state.get("extracted_skills", [])
    new_skills = []

    # ── Assimilate extracted skills ────────────────────────────
    for sk in extracted_skills:
        new_skills.append(sk)

    # ── Assimilate best policy as skill ────────────────────────
    if best_policy and best_policy.get("suggest_skill_update"):
        quality = best_policy.get("quality_score", 7)
        strategy_skill = {
            "name": f"strategy-{best_policy.get('strategy_id', 'X').lower()}",
            "triggers": ["When approaching a similar task"],
            "steps": [
                f"Use: {best_policy.get('strategy_desc', '')}",
                "Verify the approach fits the specific task",
            ],
            "pitfalls": [f"Won with {best_policy.get('steps', '?')} steps; may need adaptation"],
            "success_rate": quality / 10,
            "use_count": 0,
            "domain": "",
        }
        store.save_skill(strategy_skill)
        new_skills.append(strategy_skill)
        store.increment_metric("total_improvements")

    # ── Handle degraded skills ─────────────────────────────────
    for sk in state.get("degraded_skills", []):
        store.update_success_rate(sk["name"], False)

    # ── Export to GitHub (optional) ────────────────────────────
    if new_skills:
        _maybe_export(new_skills)

    # ── Update metrics ─────────────────────────────────────────
    cycle = state.get("cycle", 0) + 1
    store.set_metric("last_cycle", cycle)
    store.set_metric("total_skills", len(store.get_skills()))

    return {"phase": "done", "cycle": cycle, "error": None}
