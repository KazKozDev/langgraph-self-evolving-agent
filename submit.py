#!/usr/bin/env python3
"""
Task submission CLI — feed tasks to the self-evolving agent.

Usage:
  python submit.py "Write a REST API for user avatars"
  python submit.py --goal "Fix login bug" --domain debugging --errors "null pointer" --result failure
  python submit.py --evolve "Research async ORMs"
  python submit.py --watch   (read tasks from stdin, one per line)

After submission, the agent processes the task and extracts a skill if successful.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

INCOMING_DIR = Path(os.path.expanduser("~/.self-evolving-agent/incoming/"))
INCOMING_DIR.mkdir(parents=True, exist_ok=True)


def submit_task(
    goal: str,
    domain: str = "coding",
    errors: list[str] | None = None,
    result: str = "success",
    tool_calls: int = 5,
    key_pattern: str = "",
) -> str:
    """Submit a task to the incoming directory (WatchSessionSource picks it up)."""
    session_id = f"sub-{int(time.time())}"
    data = {
        "session_id": session_id,
        "goal": goal,
        "domain": domain,
        "tool_calls": tool_calls,
        "errors": errors or [],
        "result": result,
        "key_pattern": key_pattern,
    }
    filepath = INCOMING_DIR / f"{session_id}.json"
    filepath.write_text(json.dumps(data, ensure_ascii=False))
    return session_id


def submit_and_evolve(goal: str, domain: str = "coding") -> dict:
    """Submit a task AND immediately run one evolution cycle."""
    sid = submit_task(goal, domain, result="success")

    # Run one cycle
    os.environ.setdefault("SESSION_SOURCE", "watch")
    os.environ.setdefault("EVOLUTION_MOCK", "true")

    from src.graph import get_graph
    from src.memory.store import get_store

    graph = get_graph()
    initial = {
        "messages": [], "experiences": [], "new_experiences_count": 0,
        "skills": [], "extracted_skills": [], "degraded_skills": [],
        "policy_variants": [], "variant_index": 0, "best_policy": None,
        "tournament_results": None, "cycle": 0, "phase": "collect",
        "human_approval_required": False, "human_decision": "",
        "total_skills_created": 0, "total_improvements": 0, "error": None,
    }
    config = {"configurable": {"thread_id": f"submit-{sid}"}}
    final = graph.invoke(initial, config)

    return {
        "session_id": sid,
        "phase": final.get("phase"),
        "skills_created": [s.get("name") for s in final.get("extracted_skills", [])],
        "best_strategy": (final.get("best_policy") or {}).get("strategy_id"),
    }


def watch_mode():
    """Read tasks from stdin, one JSON or plain-text line at a time."""
    print("📥 Watching stdin for tasks (one per line, Ctrl+D to stop)...")
    print("   Format: plain text = goal, or JSON with goal/domain/errors/result")
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            data = json.loads(line)
            goal = data.get("goal", line)
            domain = data.get("domain", "coding")
            errors = data.get("errors", [])
            result = data.get("result", "success")
        except json.JSONDecodeError:
            goal = line
            domain = "coding"
            errors = []
            result = "success"

        sid = submit_task(goal, domain, errors, result)
        print(f"  ✅ {sid}: {goal[:70]}")


def main():
    parser = argparse.ArgumentParser(description="Submit tasks to the self-evolving agent")
    parser.add_argument("goal", nargs="?", help="Task description")
    parser.add_argument("--domain", default="coding", help="Task domain")
    parser.add_argument("--errors", nargs="*", default=[], help="Errors encountered")
    parser.add_argument("--result", default="success", choices=["success", "failure", "partial"])
    parser.add_argument("--tool-calls", type=int, default=5)
    parser.add_argument("--evolve", action="store_true", help="Run evolution cycle after submit")
    parser.add_argument("--execute", action="store_true", help="Actually execute the task (CodeExecutor)")
    parser.add_argument("--watch", action="store_true", help="Read tasks from stdin")

    args = parser.parse_args()

    if args.watch:
        watch_mode()
        return

    if not args.goal:
        parser.print_help()
        return

    if args.evolve:
        print(f"🚀 Submitting + evolving: {args.goal[:60]}...")
        if args.execute:
            os.environ["EXECUTOR_BACKEND"] = "code"
        result = submit_and_evolve(args.goal, args.domain)
        print(f"   Session: {result['session_id']}")
        print(f"   Skills:  {result['skills_created'] or 'none extracted'}")
        if result['best_strategy']:
            print(f"   Best:    strategy {result['best_strategy']}")
    else:
        sid = submit_task(args.goal, args.domain, args.errors, args.result, args.tool_calls)
        print(f"📝 Submitted: {sid}")
        print(f"   Goal:   {args.goal[:60]}")
        print(f"   Domain: {args.domain}")
        print(f"   Result: {args.result}")
        print(f"\n   Agent will pick it up on next cycle (SESSION_SOURCE=watch).")


if __name__ == "__main__":
    main()
