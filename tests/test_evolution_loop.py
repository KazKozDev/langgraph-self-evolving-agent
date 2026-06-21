"""Tests for the closed evolution loop: strategy memory + explore/exploit."""
import os
import tempfile

os.environ["EVOLUTION_MOCK"] = "true"

import src.memory.store as mem_module
from src.memory.store import MemoryStore, _strategy_key
from src.nodes.evaluate import evaluate_results
from src.nodes.explore import explore_policies


def _temp_store(td):
    store = MemoryStore(path=f"{td}/mem.json")
    mem_module._store = store
    return store


class TestStrategyMemory:
    def test_key_is_stable(self):
        a = _strategy_key("Methodical: plan, then implement")
        b = _strategy_key("Methodical: plan, then implement")
        assert a == b and a != ""

    def test_record_accumulates(self):
        with tempfile.TemporaryDirectory() as td:
            store = _temp_store(td)
            store.record_strategy("Fast iteration", "coding", success=True, won=True)
            store.record_strategy("Fast iteration", "coding", success=True)
            strat = store.get_strategies("coding")[0]
            assert strat["plays"] == 2
            assert strat["wins"] == 1
            assert strat["success_rate"] > 0.5  # EMA pulled up by two successes

    def test_failure_lowers_rate(self):
        with tempfile.TemporaryDirectory() as td:
            store = _temp_store(td)
            store.record_strategy("Risky approach", "coding", success=False)
            assert store.get_strategies("coding")[0]["success_rate"] < 0.5

    def test_domain_filter(self):
        with tempfile.TemporaryDirectory() as td:
            store = _temp_store(td)
            store.record_strategy("Coding way", "coding", success=True)
            store.record_strategy("Research way", "research", success=True)
            assert len(store.get_strategies("coding")) == 1
            assert len(store.get_strategies()) == 2  # no filter → all


class TestExploreExploit:
    def _exp(self):
        return [{
            "session_id": "s1", "goal": "Build a parser", "domain": "coding",
            "tool_calls": 8, "errors": [], "result": "success", "key_pattern": "",
        }]

    def test_explore_generates_two_variants(self):
        with tempfile.TemporaryDirectory() as td:
            _temp_store(td)
            out = explore_policies({"experiences": self._exp()})
            assert len(out["policy_variants"]) == 2
            # Fresh store → both are freshly explored, none proven yet.
            assert all(v["origin"] == "explore" for v in out["policy_variants"])

    def test_proven_champion_is_reentered(self):
        with tempfile.TemporaryDirectory() as td:
            store = _temp_store(td)
            # Seed a strong, proven coding strategy.
            for _ in range(3):
                store.record_strategy("Champion: TDD all the way", "coding", success=True, won=True)
            out = explore_policies({"experiences": self._exp()})
            origins = {v["origin"] for v in out["policy_variants"]}
            assert "exploit" in origins  # champion re-entered
            exploit = next(v for v in out["policy_variants"] if v["origin"] == "exploit")
            assert exploit["strategy_desc"] == "Champion: TDD all the way"


class TestEvaluateClosesLoop:
    def test_winner_recorded_to_memory(self):
        with tempfile.TemporaryDirectory() as td:
            store = _temp_store(td)
            variants = [
                {"strategy_id": "A", "strategy_desc": "Plan first", "domain": "coding",
                 "success": True, "steps": 4, "errors": [], "output_summary": "ok"},
                {"strategy_id": "B", "strategy_desc": "Prototype fast", "domain": "coding",
                 "success": True, "steps": 9, "errors": [], "output_summary": "ok"},
            ]
            out = evaluate_results({"policy_variants": variants, "skills": []})
            assert out["best_policy"] is not None
            # Both variants now have a track record in strategy memory.
            recorded = {s["desc"]: s for s in store.get_strategies("coding")}
            assert "Plan first" in recorded and "Prototype fast" in recorded
            assert recorded[out["best_policy"]["strategy_desc"]]["wins"] == 1
