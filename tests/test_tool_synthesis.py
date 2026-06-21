"""Tests for the self-extension loop: synthesize → verify → register → reuse."""
import os
import tempfile

os.environ["EVOLUTION_MOCK"] = "true"

import src.memory.store as mem_module
from src.memory.store import MemoryStore
from src.tools import registry
from src.tool_synthesis import synthesize_tool


def _setup(td):
    """Isolated store + tools dir so tests never touch the real toolbox."""
    store = MemoryStore(path=f"{td}/mem.json")
    mem_module._store = store
    os.environ["TOOLS_DIR"] = f"{td}/tools"
    return store


class TestSynthesis:
    def test_synthesize_writes_and_registers(self):
        with tempfile.TemporaryDirectory() as td:
            store = _setup(td)
            meta = synthesize_tool("Keep a value within bounds", "coding", store)
            assert meta is not None
            assert meta["name"] == "clamp"
            # File written to the tools dir
            assert os.path.exists(os.path.join(f"{td}/tools", "clamp.py"))
            # Registered in the store
            assert store.get_tool("clamp") is not None

    def test_synthesized_tool_actually_runs(self):
        with tempfile.TemporaryDirectory() as td:
            _setup(td)
            synthesize_tool("Keep a value within bounds", "coding")
            fn = registry.load_tool("clamp")
            assert callable(fn)
            assert fn(5, 0, 10) == 5
            assert fn(-3, 0, 10) == 0
            assert fn(99, 0, 10) == 10

    def test_not_regenerated_if_exists(self):
        with tempfile.TemporaryDirectory() as td:
            store = _setup(td)
            first = synthesize_tool("Keep a value within bounds", "coding", store)
            second = synthesize_tool("Keep a value within bounds", "coding", store)
            assert first["name"] == second["name"]
            assert len(store.get_tools()) == 1  # no duplicate

    def test_failed_verification_is_discarded(self):
        with tempfile.TemporaryDirectory() as td:
            store = _setup(td)
            # A tool whose test fails must never be registered.
            registry.register_tool  # ensure import side effects fine
            from src import tool_synthesis
            ok = tool_synthesis._verify(
                "broken",
                "def broken(x):\n    return x + 1\n",
                "from broken import broken\nassert broken(1) == 999\n",
            )
            assert ok[0] is False
            assert store.get_tools() == []


class TestRegistry:
    def test_catalog_and_use_tracking(self):
        with tempfile.TemporaryDirectory() as td:
            store = _setup(td)
            registry.register_tool("dub", "def dub(x):\n    return x*2\n",
                                   "double a number", "dub(x)", store)
            cat = registry.tool_catalog(store)
            assert "dub(x)" in cat and "double a number" in cat

            store.record_tool_use("dub", success=False)
            assert store.get_tool("dub")["success_rate"] < 1.0
            assert store.get_tool("dub")["use_count"] == 1
