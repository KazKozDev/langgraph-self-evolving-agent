"""Demo runner — shows the self-evolving agent in action."""
from __future__ import annotations

from src.graph import get_graph
from src.memory.store import get_store


def seed_experiences():
    """Seed the store with 3 sample experiences."""
    store = get_store()
    samples = [
        {
            "session_id": "demo-001",
            "goal": "Debug a FastAPI endpoint returning 500 on POST /users",
            "domain": "debugging",
            "tool_calls": 5,
            "errors": ["'User' object has no attribute 'email'", "missing await"],
            "result": "success",
            "key_pattern": "add_logging_first",
        },
        {
            "session_id": "demo-002",
            "goal": "Create a CI/CD pipeline with GitHub Actions for a Python project",
            "domain": "deployment",
            "tool_calls": 8,
            "errors": ["Invalid workflow syntax", "secrets not accessible"],
            "result": "success",
            "key_pattern": "validate_schema_before_push",
        },
        {
            "session_id": "demo-003",
            "goal": "Write unit tests for an async payment processing module",
            "domain": "coding",
            "tool_calls": 12,
            "errors": ["mock not configured", "missing pytest-asyncio", "race condition"],
            "result": "partial",
            "key_pattern": "",
        },
    ]
    for exp in samples:
        store.add_experience(exp)
    print(f"Seeded {len(samples)} experiences.")


def run_demo():
    """Run one evolution cycle."""
    print("=" * 60)
    print("  Self-Evolving Agent — Demo Run")
    print("=" * 60)

    seed_experiences()

    graph = get_graph()
    print(f"\nGraph: {len(graph.nodes)} nodes, running one evolution cycle...\n")

    initial = {
        "messages": [],
        "experiences": [],
        "new_experiences_count": 0,
        "skills": [],
        "extracted_skills": [],
        "degraded_skills": [],
        "policy_variants": [],
        "best_policy": None,
        "tournament_results": None,
        "cycle": 0,
        "phase": "collect",
        "human_approval_required": False,
        "human_decision": "",
        "total_skills_created": 0,
        "total_improvements": 0,
        "error": None,
        "variant_index": 0,
    }

    config = {"configurable": {"thread_id": "demo-1"}}

    try:
        final = graph.invoke(initial, config)

        print("-" * 60)
        print("RESULTS")
        print("-" * 60)
        print(f"Phase: {final.get('phase')}")
        print(f"Experiences: {final.get('new_experiences_count', 0)}")
        print(f"Skills extracted: {len(final.get('extracted_skills', []))}")
        for sk in final.get("extracted_skills", []):
            print(f"  → {sk.get('name')}: {len(sk.get('steps', []))} steps, {len(sk.get('pitfalls', []))} pitfalls")
        print(f"Policy variants tested: {len(final.get('policy_variants', []))}")
        if final.get("best_policy"):
            bp = final["best_policy"]
            print(f"Best: {bp.get('strategy_id')} — {bp.get('desc', bp.get('strategy_desc', ''))}")
            print(f"  Success: {bp.get('success')}, Steps: {bp.get('steps')}, Quality: {bp.get('quality_score', '?')}/10")
        print(f"Human approval: {'required ⚠️' if final.get('human_approval_required') else 'not required ✓'}")

        store = get_store()
        skills = store.get_skills()
        print(f"\nSkills in store: {len(skills)}")
        for sk in skills:
            print(f"  • {sk['name']} (rate={sk.get('success_rate', 1.0)})")

    except Exception as e:
        print(f"\n  Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("  Demo complete.")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
