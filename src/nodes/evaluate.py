"""
evaluate_results node — compare variants, pick winner, detect degradation.
Inspired by APEX selection + Forgetting paper (arXiv:2605.09315).
"""
from __future__ import annotations

import json

from src.llm import get_llm
from src.memory.store import get_store
from src.state import EvolutionState


def evaluate_results(state: EvolutionState) -> dict:
    """Evaluate policy variants and detect skill degradation."""
    store = get_store()
    variants = state.get("policy_variants", [])
    skills = state.get("skills", [])

    best_policy = None
    degraded_skills = []

    # ── Policy evaluation ──────────────────────────────────────
    if variants:
        def score(v: dict) -> float:
            s = 100 if v.get("success") else 0
            s += max(0, 20 - v.get("steps", 0))
            s += max(0, 10 - len(v.get("errors", [])) * 3)
            return s

        variants.sort(key=score, reverse=True)
        best_policy = variants[0]

        # Quick LLM quality check on the winner's output
        if best_policy.get("output_summary"):
            llm = get_llm(max_tokens=150)
            try:
                resp = llm.invoke(
                    f"Rate this output 1-10 for correctness+quality: \"{best_policy['output_summary']}\"."
                    f" Return JSON: {{\"score\": N}}"
                )
                from src.json_parser import parse_json
                q = parse_json(str(resp.content))
                best_policy["quality_score"] = q.get("score", 7)
            except Exception:
                best_policy["quality_score"] = 7

            best_policy["suggest_skill_update"] = best_policy.get("quality_score", 7) >= 7

    # ── Degradation detection ──────────────────────────────────
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=7)
    for sk in skills:
        last_used = sk.get("last_used", "")
        if last_used:
            try:
                if datetime.fromisoformat(last_used) < cutoff and sk.get("success_rate", 1.0) < 0.8:
                    degraded_skills.append(sk)
            except (ValueError, TypeError):
                pass

    requires_approval = (
        best_policy is not None
        and best_policy.get("suggest_skill_update")
        and best_policy.get("quality_score", 10) < 8
    )

    return {
        "best_policy": best_policy,
        "degraded_skills": degraded_skills,
        "human_approval_required": requires_approval,
        "phase": "human" if requires_approval else "assimilate",
    }
