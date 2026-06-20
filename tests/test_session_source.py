"""Tests for session sources."""
import json
import os
import sys
import tempfile

os.environ["EVOLUTION_MOCK"] = "true"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.session_source import MockSessionSource, FileSessionSource, SessionRecord
from src.memory.store import MemoryStore


class TestMockSessionSource:
    def test_fetches_from_store(self):
        import src.memory.store as mem_module
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(path=f"{td}/test.json")
            store.add_experience({
                "session_id": "s1",
                "goal": "Debug endpoint",
                "domain": "debugging",
                "tool_calls": 5,
                "errors": [],
                "result": "success",
                "key_pattern": "test_first",
            })

            old_store = mem_module._store
            mem_module._store = store
            try:
                source = MockSessionSource()
                records = source.fetch_recent(10)
                assert len(records) >= 1
                assert records[0].goal == "Debug endpoint"
            finally:
                mem_module._store = old_store

    def test_to_dicts(self):
        source = MockSessionSource()
        records = [
            SessionRecord(session_id="s1", goal="test", domain="debugging", result="success"),
            SessionRecord(session_id="s2", goal="test2", domain="coding", result="partial"),
        ]
        dicts = source.to_dicts(records)
        assert len(dicts) == 2
        assert dicts[0]["session_id"] == "s1"


class TestFileSessionSource:
    def test_reads_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/sessions.jsonl"
            with open(path, "w") as f:
                f.write(json.dumps({"session_id": "s1", "goal": "Debug", "domain": "debugging", "result": "success"}) + "\n")
                f.write(json.dumps({"session_id": "s2", "goal": "Deploy", "domain": "deployment", "result": "failure"}) + "\n")

            source = FileSessionSource(path=path)
            records = source.fetch_recent(10)
            assert len(records) == 2
            assert records[0].session_id == "s1"
            assert records[1].goal == "Deploy"

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/empty.jsonl"
            source = FileSessionSource(path=path)
            records = source.fetch_recent(10)
            assert records == []

    def test_skips_invalid_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/sessions.jsonl"
            with open(path, "w") as f:
                f.write("not json\n")
                f.write(json.dumps({"session_id": "s1", "goal": "Valid"}) + "\n")

            source = FileSessionSource(path=path)
            records = source.fetch_recent(10)
            assert len(records) == 1
            assert records[0].goal == "Valid"
