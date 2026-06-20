"""
explore_policies + run_variant — design and test strategy variants.

Uses pluggable TaskExecutor (mock, subprocess, delegate_task).
Inspired by APEX policy exploration.
"""
from __future__ import annotations

import os

from src.state import EvolutionState


def _get_executor():
    """Lazy-load the configured executor."""
    backend = os.getenv("EXECUTOR_BACKEND", "mock")
    from src.executor import get_executor
    return get_executor(backend)


def explore_policies(state: EvolutionState) -> dict:
    """Design 2 strategy variants for a recent task."""
    experiences = state.get("experiences", [])

    # Pick a task to explore
    failures = [e for e in experiences if e.get("result") in ("failure", "partial")]
    suboptimal = [e for e in experiences if e.get("result") == "success" and e.get("tool_calls", 0) > 5]
    candidates = failures + suboptimal

    if not candidates and experiences:
        candidates = [experiences[0]]

    if not candidates:
        return {"policy_variants": [], "phase": "evaluate"}

    target = candidates[0]

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
    """Execute the current strategy variant via the configured executor."""
    variants = state.get("policy_variants", [])
    idx = state.get("variant_index", 0)

    if idx >= len(variants):
        return {"phase": "evaluate"}

    variant = variants[idx]

    # Execute the task with the given strategy
    executor = _get_executor()
    result = executor.execute(
        goal=variant.get("task_goal", ""),
        strategy_desc=variant.get("strategy_desc", ""),
        domain=variant.get("domain", "coding"),
    )

    variant_result = {
        "strategy_id": variant["strategy_id"],
        "strategy_desc": variant["strategy_desc"],
        "success": result.success,
        "steps": result.steps,
        "errors": result.errors,
        "output_summary": result.output_summary,
        "raw_output": result.raw_output,
    }

    accumulated = list(variants)
    accumulated[idx] = variant_result

    next_idx = idx + 1
    return {
        "policy_variants": accumulated,
        "variant_index": next_idx,
        "phase": "run_variant" if next_idx < len(variants) else "evaluate",
    }
