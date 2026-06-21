"""
explore_policies + run_variant — design and test strategy variants.

Strategies are NOT hardcoded. Each cycle the LLM proposes fresh approaches
tailored to the target task (exploration), while the best strategy proven in
past cycles is re-entered as a challenger (exploitation). This explore/exploit
split is the mechanism from APEX (arXiv:2605.21240): keep discovering new
directions without abandoning what already works.

Supports two modes:
  - Sequential (default): run variants one at a time
  - Parallel (PARALLEL_EXPLORE=true): run all variants simultaneously via ThreadPoolExecutor
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.json_parser import parse_json
from src.llm import get_llm
from src.memory.store import get_store
from src.state import EvolutionState

# Fallback strategies if the LLM returns nothing usable.
_FALLBACK_STRATEGIES = [
    "Methodical: plan first, implement step-by-step, test after each step",
    "Fast iteration: code a minimal working version, then refine and add tests",
    "Tool-maximal: parallelize work and lean on all available tools",
]

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


def _llm_design(goal: str, domain: str, already_tried: list[str], n: int) -> list[str]:
    """Ask the LLM to design `n` distinct strategy variants for this task."""
    if n <= 0:
        return []

    tried_block = ""
    if already_tried:
        tried_block = (
            "Previously tried strategies (propose genuinely different angles, "
            "or improve on the strongest one):\n"
            + "\n".join(f"- {t}" for t in already_tried)
            + "\n\n"
        )

    prompt = (
        f"Design {n} distinct strategy variants to accomplish the task below.\n"
        f"DOMAIN: {domain}\n"
        f"GOAL: {goal}\n\n"
        f"{tried_block}"
        "Each variant is one short imperative sentence describing the approach.\n"
        'Return a JSON list: [{"id": "A", "desc": "..."}]'
    )
    try:
        llm = get_llm(max_tokens=400)
        data = parse_json(str(llm.invoke(prompt).content))
        descs = [d["desc"].strip() for d in data if isinstance(d, dict) and d.get("desc")]
    except Exception:
        descs = []

    # De-duplicate against what we've already tried, preserving order.
    seen = {t.lower() for t in already_tried}
    fresh = []
    for d in descs:
        if d and d.lower() not in seen:
            fresh.append(d)
            seen.add(d.lower())

    # Top up with fallbacks if the LLM under-delivered.
    for fb in _FALLBACK_STRATEGIES:
        if len(fresh) >= n:
            break
        if fb.lower() not in seen:
            fresh.append(fb)
            seen.add(fb.lower())

    return fresh[:n]


def _design_variants(goal: str, domain: str, n: int) -> list[dict]:
    """Build `n` variants: one proven champion (if any) + novel LLM ideas."""
    store = get_store()
    past = store.get_strategies(domain)

    # Exploitation: re-enter the best strategy proven for this domain so a
    # winner from earlier cycles keeps defending its title.
    exploit_threshold = float(os.getenv("EXPLOIT_THRESHOLD", "0.6"))
    proven = sorted(
        past,
        key=lambda s: (s.get("success_rate", 0.0), s.get("plays", 0)),
        reverse=True,
    )
    champion = next(
        (s for s in proven
         if s.get("plays", 0) >= 1 and s.get("success_rate", 0.0) >= exploit_threshold),
        None,
    )

    # Exploration: novel strategies, told what's already been tried.
    novel_needed = n - (1 if champion else 0)
    novel = _llm_design(goal, domain, [s.get("desc", "") for s in proven[:5]], novel_needed)

    variants: list[dict] = []
    if champion:
        variants.append({
            "strategy_id": "P",  # P = proven
            "strategy_desc": champion["desc"],
            "task_goal": goal,
            "domain": domain,
            "origin": "exploit",
        })
    for i, desc in enumerate(novel):
        variants.append({
            "strategy_id": chr(ord("A") + i),
            "strategy_desc": desc,
            "task_goal": goal,
            "domain": domain,
            "origin": "explore",
        })
    return variants[:n]


def explore_policies(state: EvolutionState) -> dict:
    """Design strategy variants for a target task (explore + exploit).

    Target selection:
      - If a live `task_goal` was supplied, attack THAT goal directly.
      - Otherwise mine recent experience for a failure/suboptimal run to improve.
    """
    live_goal = (state.get("task_goal") or "").strip()
    if live_goal:
        target = {"goal": live_goal, "domain": state.get("task_domain") or "coding"}
    else:
        experiences = state.get("experiences", [])
        failures = [e for e in experiences if e.get("result") in ("failure", "partial")]
        suboptimal = [e for e in experiences if e.get("result") == "success" and e.get("tool_calls", 0) > 5]
        candidates = failures + suboptimal
        if not candidates and experiences:
            candidates = [experiences[0]]
        if not candidates:
            return {"policy_variants": [], "phase": "evaluate"}
        target = candidates[0]

    n = max(1, int(os.getenv("EXPLORE_VARIANTS", "2")))
    variants = _design_variants(
        goal=target.get("goal", ""),
        domain=target.get("domain", "coding"),
        n=n,
    )

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
        "domain": domain,
        "origin": variant.get("origin", "explore"),
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
            "domain": variant.get("domain", "coding"),
            "origin": variant.get("origin", "explore"),
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
                    "domain": v.get("domain", "coding"),
                    "origin": v.get("origin", "explore"),
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
