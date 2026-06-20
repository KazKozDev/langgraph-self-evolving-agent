"""Tests for the pluggable executor."""
import os
import sys

os.environ["EVOLUTION_MOCK"] = "true"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.executor import MockExecutor, SubprocessExecutor, ExecutionResult


class TestMockExecutor:
    def test_execute_returns_result(self):
        executor = MockExecutor()
        result = executor.execute("Debug FastAPI", "Methodical", "debugging")
        assert isinstance(result, ExecutionResult)
        assert isinstance(result.success, bool)
        assert result.steps > 0

    def test_methodical_vs_fast(self):
        executor = MockExecutor()
        r1 = executor.execute("Write tests", "Methodical: plan first, step by step", "coding")
        r2 = executor.execute("Write tests", "Fast iteration: code fast, refine later", "coding")
        # Methodical typically takes more steps in mock mode (7 vs 4)
        assert r1.steps >= r2.steps


class TestSubprocessExecutor:
    def test_shell_succeeds(self):
        executor = SubprocessExecutor(backend="shell", timeout=5)
        result = executor.execute("Echo hello", "Use echo", "shell")
        assert result.success
        assert "Done" in result.output_summary

    def test_python_succeeds(self):
        executor = SubprocessExecutor(backend="python", timeout=5)
        result = executor.execute("Print done", "Use print", "coding")
        assert result.success
        assert "Done" in result.output_summary

    def test_timeout_handled(self):
        executor = SubprocessExecutor(backend="shell", timeout=1)
        result = executor.execute("Sleep", "sleep 999", "shell")
        assert isinstance(result, ExecutionResult)
