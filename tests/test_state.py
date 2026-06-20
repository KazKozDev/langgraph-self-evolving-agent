"""Tests for state models and domain types."""
import pytest
from src.state import Experience, Skill, PolicyResult, TournamentResult, EvolutionState


class TestExperience:
    def test_create_minimal(self):
        exp = Experience(session_id="s1", goal="test")
        assert exp.session_id == "s1"
        assert exp.goal == "test"
        assert exp.errors == []

    def test_create_full(self):
        exp = Experience(
            session_id="s2",
            goal="Debug endpoint",
            domain="debugging",
            tool_calls=5,
            errors=["missing await"],
            result="success",
            key_pattern="add_logging_first",
        )
        assert exp.tool_calls == 5
        assert len(exp.errors) == 1
        assert exp.result == "success"


class TestSkill:
    def test_create(self):
        sk = Skill(
            name="debug-fastapi",
            triggers=["500 error on POST"],
            steps=["Add logging", "Check types", "Verify async"],
            pitfalls=["Skipping logs"],
        )
        assert sk.success_rate == 1.0
        assert sk.use_count == 0
        assert len(sk.steps) == 3

    def test_defaults(self):
        sk = Skill(name="test-skill")
        assert sk.triggers == []
        assert sk.steps == []
        assert sk.pitfalls == []


class TestPolicyResult:
    def test_create(self):
        pr = PolicyResult(
            strategy_id="A",
            strategy_desc="Methodical",
            success=True,
            steps=4,
            errors=[],
            output_summary="done",
        )
        assert pr.success
        assert pr.steps == 4


class TestTournamentResult:
    def test_create(self):
        variants = [
            PolicyResult(strategy_id="A", strategy_desc="Fast", success=True, steps=3, errors=[], output_summary="ok"),
            PolicyResult(strategy_id="B", strategy_desc="Slow", success=True, steps=8, errors=[], output_summary="ok"),
        ]
        tr = TournamentResult(task="Build API", variants=variants, winner="A", reason="faster")
        assert tr.winner == "A"
        assert len(tr.variants) == 2


class TestEvolutionState:
    def test_initial_state(self):
        state = EvolutionState(
            messages=[],
            experiences=[],
            new_experiences_count=0,
            skills=[],
            extracted_skills=[],
            degraded_skills=[],
            policy_variants=[],
            variant_index=0,
            best_policy=None,
            tournament_results=None,
            cycle=0,
            phase="collect",
            human_approval_required=False,
            human_decision="",
            total_skills_created=0,
            total_improvements=0,
            error=None,
        )
        assert state["phase"] == "collect"
        assert state["cycle"] == 0
        assert state["variant_index"] == 0
