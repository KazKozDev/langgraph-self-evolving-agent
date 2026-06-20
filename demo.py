"""Demo runner — self-evolving agent on LangGraph.

Usage:
  EVOLUTION_MOCK=true python demo.py              # single cycle, mock LLM
  EVOLUTION_MOCK=true python demo.py --loop       # continuous loop
  SESSION_SOURCE=file python demo.py              # read from JSONL file
  EXECUTOR_BACKEND=subprocess python demo.py      # real subprocess execution
  EXECUTOR_BACKEND=python python demo.py          # real Python execution
"""
from __future__ import annotations

import os
import sys
import time

from src.graph import get_graph
from src.memory.store import get_store


def seed_experiences():
    """Seed sample experiences for demo mode."""
    store = get_store()
    samples = [
        {
            "session_id": "demo-001",
            "goal": "Debug a FastAPI endpoint returning 500 on POST /users",
            "domain": "debugging",
            "tool_calls": 5,
            "errors": ["missing await on async call"],
            "result": "success",
            "key_pattern": "add_logging_first",
        },
        {
            "session_id": "demo-002",
            "goal": "Create a CI/CD pipeline with GitHub Actions",
            "domain": "deployment",
            "tool_calls": 8,
            "errors": ["invalid workflow syntax"],
            "result": "success",
            "key_pattern": "validate_schema_before_push",
        },
        {
            "session_id": "demo-003",
            "goal": "Write unit tests for an async payment module",
            "domain": "coding",
            "tool_calls": 12,
            "errors": ["mock not configured", "race condition"],
            "result": "partial",
            "key_pattern": "",
        },
    ]
    for exp in samples:
        store.add_experience(exp)


def run_one_cycle(cycle_num: int = 0) -> dict:
    """Run one evolution cycle."""
    graph = get_graph()
    initial = {
        "messages": [],
        "experiences": [],
        "new_experiences_count": 0,
        "skills": [],
        "extracted_skills": [],
        "degraded_skills": [],
        "policy_variants": [],
        "variant_index": 0,
        "best_policy": None,
        "tournament_results": None,
        "cycle": cycle_num,
        "phase": "collect",
        "human_approval_required": False,
        "human_decision": "",
        "total_skills_created": 0,
        "total_improvements": 0,
        "error": None,
    }
    config = {"configurable": {"thread_id": f"cycle-{cycle_num}"}}
    return graph.invoke(initial, config)


def print_results(final: dict, cycle_num: int, elapsed: float):
    """Pretty-print cycle results."""
    print(f"\n{'─' * 60}")
    print(f"  Cycle {cycle_num} complete ({elapsed:.1f}s)")
    print(f"{'─' * 60}")
    print(f"  Phase:          {final.get('phase')}")
    print(f"  Experiences:    {final.get('new_experiences_count', 0)}")
    print(f"  Skills created: {len(final.get('extracted_skills', []))}")
    for sk in final.get("extracted_skills", []):
        print(f"    → {sk.get('name')}: {len(sk.get('steps', []))} steps")
    print(f"  Variants:       {len(final.get('policy_variants', []))}")
    if final.get("best_policy"):
        bp = final["best_policy"]
        print(f"  Best strategy:  {bp.get('strategy_id')} — {bp.get('strategy_desc', '')}")
        print(f"    Success: {bp.get('success')}, Steps: {bp.get('steps')}, "
              f"Quality: {bp.get('quality_score', '?')}/10")
    print(f"  Human review:   {'required' if final.get('human_approval_required') else 'not needed'}")
    print(f"  Total skills:   {len(get_store().get_skills())}")


def run_loop(interval: int = 60):
    """Continuous evolution loop."""
    print("=" * 60)
    print("  Self-Evolving Agent — Continuous Loop")
    print(f"  Interval: {interval}s | Ctrl+C to stop")
    print("=" * 60)

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n▶ Cycle {cycle} starting...", flush=True)
            t0 = time.time()
            try:
                final = run_one_cycle(cycle)
                print_results(final, cycle, time.time() - t0)
            except Exception as e:
                print(f"  ✗ Cycle {cycle} failed: {e}", flush=True)
            print(f"\n  Sleeping {interval}s...", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n\n  Stopped after {cycle} cycles.")
        print(f"  Final skill count: {len(get_store().get_skills())}")


def main():
    loop_mode = "--loop" in sys.argv or os.getenv("EVOLUTION_LOOP", "") == "true"
    source = os.getenv("SESSION_SOURCE", "mock")
    executor = os.getenv("EXECUTOR_BACKEND", "mock")

    if source == "mock":
        seed_experiences()
        print("Session source: mock (seeded 3 experiences)")
    else:
        print(f"Session source: {source}")

    print(f"Executor: {executor}")
    print(f"Mode: {'continuous loop' if loop_mode else 'single cycle'}")

    if loop_mode:
        interval = int(os.getenv("EVOLUTION_INTERVAL", "300"))
        run_loop(interval=interval)
    else:
        print("=" * 60)
        print("  Self-Evolving Agent — Single Cycle")
        print("=" * 60)
        t0 = time.time()
        final = run_one_cycle(0)
        print_results(final, 0, time.time() - t0)


if __name__ == "__main__":
    main()
