"""Integration test: full graph run in mock mode."""
import os
import sys
import tempfile

os.environ["EVOLUTION_MOCK"] = "true"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph import build_graph
from src.memory.store import get_store, MemoryStore


def test_graph_completes():
    """Graph should complete without errors in mock mode."""
    # Use temp memory to avoid polluting real store
    import src.memory.store as mem_module
    with tempfile.TemporaryDirectory() as td:
        store = MemoryStore(path=f"{td}/test.json")
        store.add_experience({
            "session_id": "t1",
            "goal": "Debug FastAPI 500",
            "domain": "debugging",
            "tool_calls": 5,
            "errors": ["missing await"],
            "result": "success",
            "key_pattern": "add_logging_first",
        })
        store.add_experience({
            "session_id": "t2",
            "goal": "Write async tests",
            "domain": "coding",
            "tool_calls": 10,
            "errors": ["mock fail"],
            "result": "partial",
            "key_pattern": "",
        })

        # Override global store
        old_store = mem_module._store
        mem_module._store = store

        try:
            graph = build_graph()
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
                "cycle": 0,
                "phase": "collect",
                "human_approval_required": False,
                "human_decision": "",
                "total_skills_created": 0,
                "total_improvements": 0,
                "error": None,
            }
            config = {"configurable": {"thread_id": "test-1"}}
            final = graph.invoke(initial, config)

            assert final["phase"] == "done"
            assert len(final.get("extracted_skills", [])) >= 1
            assert len(final.get("policy_variants", [])) == 2
            assert final.get("best_policy") is not None
        finally:
            mem_module._store = old_store


def test_graph_extracts_skill():
    """A successful experience should produce a skill."""
    import src.memory.store as mem_module
    with tempfile.TemporaryDirectory() as td:
        store = MemoryStore(path=f"{td}/test.json")
        store.add_experience({
            "session_id": "t1",
            "goal": "Create CI/CD pipeline",
            "domain": "deployment",
            "tool_calls": 8,
            "errors": ["invalid syntax"],
            "result": "success",
            "key_pattern": "validate_schema_first",
        })

        old_store = mem_module._store
        mem_module._store = store

        try:
            graph = build_graph()
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
                "cycle": 0,
                "phase": "collect",
                "human_approval_required": False,
                "human_decision": "",
                "total_skills_created": 0,
                "total_improvements": 0,
                "error": None,
            }
            config = {"configurable": {"thread_id": "test-2"}}
            final = graph.invoke(initial, config)

            skills = final.get("extracted_skills", [])
            assert len(skills) >= 1
            skill = skills[0]
            assert "name" in skill
            assert len(skill.get("steps", [])) >= 1
        finally:
            mem_module._store = old_store


def test_graph_handles_empty_experiences():
    """Graph should complete gracefully with no experiences."""
    import src.memory.store as mem_module
    with tempfile.TemporaryDirectory() as td:
        store = MemoryStore(path=f"{td}/test.json")
        # No experiences added

        old_store = mem_module._store
        mem_module._store = store

        try:
            graph = build_graph()
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
                "cycle": 0,
                "phase": "collect",
                "human_approval_required": False,
                "human_decision": "",
                "total_skills_created": 0,
                "total_improvements": 0,
                "error": None,
            }
            config = {"configurable": {"thread_id": "test-3"}}
            final = graph.invoke(initial, config)

            assert final["phase"] == "done"
            # No skills extracted, no policies explored — but graph completed
        finally:
            mem_module._store = old_store
