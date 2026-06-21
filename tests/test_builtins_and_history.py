"""Tests for built-in file tools (sandboxed) and the learning-curve history."""
import os
import tempfile

import pytest

import src.memory.store as mem_module
from src.memory.store import MemoryStore


class TestBuiltinFileTools:
    def test_write_read_list_within_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["AGENT_WORKSPACE"] = td
            from src.tools import builtins as bt
            bt.write_file("sub/a.txt", "hello")
            assert bt.read_file("sub/a.txt") == "hello"
            assert "a.txt" in bt.list_dir("sub")

    def test_traversal_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["AGENT_WORKSPACE"] = td
            from src.tools import builtins as bt
            with pytest.raises(ValueError):
                bt.read_file("../../../etc/passwd")

    def test_catalog_lists_builtins(self):
        from src.tools.registry import tool_catalog
        cat = tool_catalog()
        assert "read_file" in cat and "write_file" in cat
        assert "from src.tools.builtins import" in cat


class TestHistory:
    def test_snapshot_records_aggregate(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(path=f"{td}/mem.json")
            mem_module._store = store
            store.record_strategy("A solid approach", "coding", success=True, won=True)
            snap = store.record_snapshot()
            assert snap["strategies"] == 1
            assert snap["avg_strategy_success_rate"] > 0.0
            assert len(store.get_history()) == 1

    def test_history_persists(self):
        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/mem.json"
            s1 = MemoryStore(path=path)
            s1.record_snapshot()
            s2 = MemoryStore(path=path)
            assert len(s2.get_history()) == 1
