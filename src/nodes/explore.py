"""
explore_policies + run_variant — design and test strategy variants.
Inspired by APEX policy exploration. Sequential execution, 2 variants.
"""
from __future__ import annotations

import json

from src.llm import get_llm
from src.memory.store import get_store
from src.state import EvolutionState


def explore_policies(state: EvolutionState) -> dict:
    """Design 2 strategy variants for a recent task.

    Stores variants in state. A conditional edge then routes to
    run_variant for each one sequentially.
    """
    experiences = state.get("experiences", [])

    # Pick a task to explore
    failures = [e for e in experiences if e.get("result") in ("failure", "partial")]
    suboptimal = [e for e in experiences if e.get("result") == "success" and e.get("tool_calls", 0) > 5]
    candidates = failures + suboptimal

    if not candidates and experiences:
        candidates = [experiences[0]]  # fallback

    if not candidates:
        return {"policy_variants": [], "phase": "evaluate"}

    target = candidates[0]

    # 2 contrasting strategies (no LLM call — fast and deterministic)
    strategies = [
        {"id": "A", "desc": f"Methodical: plan first, implement step-by-step, test after each step"},
        {"id": "B", "desc": f"Fast iteration: code a minimal working version, then refine and add tests"},
    ]

    variants = []
    for s in strategies:
        variants.append({
            "strategy_id": s["id"],
            "strategy_desc": s["desc"],
            "task_goal": target.get("goal", ""),
            "domain": target.get("domain", "coding"),
        })

    return {
        "policy_variants": variants,
        "variant_index": 0,
        "phase": "run_variant",
    }


def run_variant(state: EvolutionState) -> dict:
    """Execute the current strategy variant and simulate the outcome via LLM."""
    variants = state.get("policy_variants", [])
    idx = state.get("variant_index", 0)

    if idx >= len(variants):
        return {"phase": "evaluate"}

    variant = variants[idx]

    llm = get_llm(max_tokens=300)
    prompt = f"""TASK: {variant.get('task_goal')}
STRATEGY: {variant.get('strategy_desc')}

Simulate outcome. Return JSON:
{{"success": true/false, "steps": number, "errors": [], "output_summary": "brief"}}
"""

    try:
        resp = llm.invoke(prompt)
        result = json.loads(str(resp.content))
    except Exception:
        result = {"success": False, "steps": 0, "errors": ["sim_fail"], "output_summary": ""}

    variant_result = {
        "strategy_id": variant["strategy_id"],
        "strategy_desc": variant["strategy_desc"],
        "success": result.get("success", False),
        "steps": result.get("steps", 0),
        "errors": result.get("errors", []),
        "output_summary": result.get("output_summary", ""),
    }

    accumulated = list(variants)  # copy
    accumulated[idx] = variant_result

    next_idx = idx + 1
    return {
        "policy_variants": accumulated,
        "variant_index": next_idx,
        "phase": "run_variant" if next_idx < len(variants) else "evaluate",
    }
