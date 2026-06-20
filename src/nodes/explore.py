"""
explore_policies + run_variant — design and test strategy variants.

Supports two modes:
  - Sequential (default): run variants one at a time
  - Parallel (PARALLEL_EXPLORE=true): run all variants simultaneously via ThreadPoolExecutor
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.state import EvolutionState

def _get_executor(domain: str = "general"):
    """Get the right executor for this domain."""
    backend = os.getenv("EXECUTOR_BACKEND", "auto")
    if backend == "mock":
        from src.executor import MockExecutor
        return MockExecutor()
    if backend == "subprocess":
        from src.executor import SubprocessExecutor
        return SubprocessExecutor(backend="shell")
    # Default: domain-based routing
    from src.domain_executors import get_domain_executor
    return get_domain_executor(domain)


def explore_policies(state: EvolutionState) -> dict:
    """Design 2 strategy variants for a recent task."""
    experiences = state.get("experiences", [])

    failures = [e for e in experiences if e.get("result") in ("failure", "partial")]
    suboptimal = [e for e in experiences if e.get("result") == "success" and e.get("tool_calls", 0) > 5]
    candidates = failures + suboptimal

    if not candidates and experiences:
        candidates = [experiences[0]]
    if not candidates:
        return {"policy_variants": [], "phase": "evaluate"}

    target = candidates[0]

    strategies = [
        {"id": "A", "desc": "Methodical: plan first, implement step-by-step, test after each step"},
        {"id": "B", "desc": "Fast iteration: code a minimal working version, then refine and add tests"},
    ]

    variants = []
    for s in strategies:
        variants.append({
            "strategy_id": s["id"],
            "strategy_desc": s["desc"],
            "task_goal": target.get("goal", ""),
            "domain": target.get("domain", "coding"),
        })

    parallel = os.getenv("PARALLEL_EXPLORE", "").lower() in ("1", "true", "yes")

    return {
        "policy_variants": variants,
        "variant_index": -1 if parallel else 0,  # -1 = run all at once
        "phase": "run_variant",
    }


def run_variant(state: EvolutionState) -> dict:
    """Execute variants — sequentially or in parallel."""
    variants = state.get("policy_variants", [])
    idx = state.get("variant_index", 0)

    # Parallel mode: run all at once
    if idx == -1:
        return _run_all_parallel(variants)

    # Sequential mode: run one at a time
    if idx >= len(variants):
        return {"phase": "evaluate"}

    variant = variants[idx]

    # Execute with domain-specific executor
    domain = variant.get("domain", "coding")
    executor = _get_executor(domain)
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


def _run_all_parallel(variants: list[dict]) -> dict:
    """Execute all variants in parallel via ThreadPoolExecutor."""
    executor = _get_executor()
    results = []

    def run_one(variant: dict) -> dict:
        r = executor.execute(
            goal=variant.get("task_goal", ""),
            strategy_desc=variant.get("strategy_desc", ""),
            domain=variant.get("domain", "coding"),
        )
        return {
            "strategy_id": variant["strategy_id"],
            "strategy_desc": variant["strategy_desc"],
            "success": r.success,
            "steps": r.steps,
            "errors": r.errors,
            "output_summary": r.output_summary,
            "raw_output": r.raw_output,
        }

    with ThreadPoolExecutor(max_workers=len(variants)) as pool:
        futures = {pool.submit(run_one, v): v for v in variants}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                v = futures[future]
                results.append({
                    "strategy_id": v["strategy_id"],
                    "strategy_desc": v["strategy_desc"],
                    "success": False,
                    "steps": 0,
                    "errors": [str(e)],
                    "output_summary": "",
                })

    return {
        "policy_variants": results,
        "variant_index": len(variants),
        "phase": "evaluate",
    }
