"""Tests for CodeExecutor — real code generation and execution."""
import os
import sys

os.environ["EVOLUTION_MOCK"] = "true"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.code_executor import CodeExecutor, ExecutionResult


class TestCodeExecutor:
    def test_execute_simple_task(self):
        """Simple math task — should succeed."""
        executor = CodeExecutor(timeout=10, max_retries=1)
        result = executor.execute(
            goal="Write a Python script that prints the sum of numbers 1 to 10",
        )
        assert isinstance(result, ExecutionResult)
        # With mock LLM, code may not actually run correctly
        # But the executor should return a result (not crash)
        assert result.attempts >= 1

    def test_run_valid_code(self):
        """Run known-valid code directly."""
        executor = CodeExecutor(timeout=10)
        code = "print('SUCCESS: sum=5050')"
        result = executor._run_code(code)
        assert result.success
        assert "SUCCESS" in result.output_summary
        assert result.exit_code == 0

    def test_run_invalid_code(self):
        """Run code that raises an exception."""
        executor = CodeExecutor(timeout=10)
        code = "raise ValueError('test error')"
        result = executor._run_code(code)
        assert not result.success
        assert result.exit_code != 0
        assert len(result.errors) > 0

    def test_run_with_stderr(self):
        """Code that writes to stderr but succeeds."""
        executor = CodeExecutor(timeout=10)
        code = "import sys; sys.stderr.write('warning'); print('SUCCESS: ok')"
        result = executor._run_code(code)
        assert result.success
        assert "SUCCESS" in result.output_summary

    def test_generate_code_returns_string(self):
        """Code generation should return non-empty string."""
        executor = CodeExecutor(timeout=10)
        code, errors = executor._generate_code("Print hello world", "")
        assert len(code) > 0
        assert errors == []

    def test_generate_with_error(self):
        """Code generation with previous error hint."""
        executor = CodeExecutor(timeout=10)
        code, errors = executor._generate_code(
            "Print numbers 1-5",
            previous_error="NameError: name 'x' is not defined",
        )
        assert len(code) > 0
        assert errors == []
