"""Tests for the persistent memory store."""
import json
import tempfile
from pathlib import Path

from src.memory.store import MemoryStore


class TestMemoryStore:
    def test_empty_store(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            store = MemoryStore(path=str(path))
            assert store.get_skills() == []
            assert store.recent_experiences() == []

    def test_save_and_get_skill(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            store = MemoryStore(path=str(path))
            store.save_skill({"name": "debug-py", "steps": ["add logs", "check types"]})
            skills = store.get_skills()
            assert len(skills) == 1
            assert skills[0]["name"] == "debug-py"

    def test_update_skill(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            store = MemoryStore(path=str(path))
            store.save_skill({"name": "test", "steps": ["a"]})
            store.save_skill({"name": "test", "steps": ["b"], "updated": True})
            sk = store.get_skill("test")
            assert sk["steps"] == ["b"]
            assert sk["updated"]

    def test_skill_use_counter(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            store = MemoryStore(path=str(path))
            store.save_skill({"name": "test"})
            store.increment_skill_use("test")
            store.increment_skill_use("test")
            sk = store.get_skill("test")
            assert sk["use_count"] == 2

    def test_success_rate_ema(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            store = MemoryStore(path=str(path))
            store.save_skill({"name": "test", "success_rate": 1.0})
            store.update_success_rate("test", False)  # 0.9*1.0 + 0.1*0 = 0.9
            assert store.get_skill("test")["success_rate"] == 0.9

    def test_add_experience(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            store = MemoryStore(path=str(path))
            store.add_experience({"goal": "debug", "result": "success"})
            exps = store.recent_experiences()
            assert len(exps) == 1
            assert exps[0]["goal"] == "debug"

    def test_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            store = MemoryStore(path=str(path))
            assert store.get_metric("total_skills") == 0
            store.increment_metric("total_skills")
            store.increment_metric("total_skills")
            assert store.get_metric("total_skills") == 2

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            store1 = MemoryStore(path=str(path))
            store1.save_skill({"name": "persist-test"})

            # New store instance reads same file
            store2 = MemoryStore(path=str(path))
            skills = store2.get_skills()
            assert len(skills) == 1
            assert skills[0]["name"] == "persist-test"
