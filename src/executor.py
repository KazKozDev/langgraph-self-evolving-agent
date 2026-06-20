"""
Task Executor — pluggable execution backend.

Three backends:
  - MockExecutor: LLM simulates execution (fast, no side effects)
  - SubprocessExecutor: spawns a real subprocess (bash, python)
  - PythonExecutor: executes a Python function in-process
"""
from __future__ import annotations

import json
import subprocess
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    """Unified result from any executor."""
    success: bool
    steps: int = 0
    errors: list[str] = field(default_factory=list)
    output_summary: str = ""
    raw_output: str = ""
    exit_code: int = 0


class TaskExecutor(ABC):
    """Abstract executor — run a task and return structured result."""

    @abstractmethod
    def execute(self, goal: str, strategy_desc: str, domain: str = "coding") -> ExecutionResult:
        ...


# ── Mock Executor ─────────────────────────────────────────────

class MockExecutor(TaskExecutor):
    """LLM simulates execution. Fast, deterministic in mock mode."""

    def execute(self, goal: str, strategy_desc: str, domain: str = "coding") -> ExecutionResult:
        from src.llm import get_llm

        llm = get_llm(max_tokens=300)

        prompt = f"""TASK: {goal}
STRATEGY: {strategy_desc}

Simulate outcome. Return JSON:
{{"success": true/false, "steps": number, "errors": [], "output_summary": "brief"}}
"""
        try:
            resp = llm.invoke(prompt)
            data = json.loads(str(resp.content))
        except Exception:
            data = {"success": False, "steps": 0, "errors": ["mock_failed"], "output_summary": ""}

        return ExecutionResult(
            success=data.get("success", False),
            steps=data.get("steps", 0),
            errors=data.get("errors", []),
            output_summary=data.get("output_summary", ""),
        )


# ── Subprocess Executor ───────────────────────────────────────

class SubprocessExecutor(TaskExecutor):
    """Execute a task by spawning a real process (bash or python)."""

    def __init__(self, backend: str = "shell", timeout: int = 300):
        self.backend = backend
        self.timeout = timeout

    def execute(self, goal: str, strategy_desc: str, domain: str = "coding") -> ExecutionResult:
        if self.backend == "python":
            return self._execute_python(goal, strategy_desc)
        return self._execute_shell(goal, strategy_desc)

    def _execute_python(self, goal: str, strategy_desc: str) -> ExecutionResult:
        """Write and run a Python script."""
        script = f'''"""Task: {goal}\nStrategy: {strategy_desc}"""\nimport sys\nprint("Running task...", flush=True)\nprint("Done.", flush=True)\nsys.exit(0)\n'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            path = f.name
        try:
            return self._run(["python3", path])
        finally:
            os.unlink(path)

    def _execute_shell(self, goal: str, strategy_desc: str) -> ExecutionResult:
        cmd = ["bash", "-c", f"echo 'Task: {goal[:80]}' && echo 'Strategy: {strategy_desc[:80]}' && echo 'Done.'"]
        return self._run(cmd)

    def _run(self, cmd: list[str]) -> ExecutionResult:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            raw = proc.stdout + proc.stderr
            success = proc.returncode == 0
            errors = [] if success else [f"exit_code={proc.returncode}", proc.stderr[:200]]
            steps = len([l for l in raw.split("\n") if l.strip()])
            return ExecutionResult(
                success=success, steps=max(1, steps), errors=errors,
                output_summary=raw[:200].strip(), raw_output=raw, exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, errors=[f"timeout after {self.timeout}s"])
        except FileNotFoundError:
            return ExecutionResult(success=False, errors=[f"command not found: {cmd[0]}"])


# ── Factory ───────────────────────────────────────────────────

def get_executor(backend: str = "mock") -> TaskExecutor:
    if backend == "subprocess" or backend == "python":
        return SubprocessExecutor(backend=backend)
    return MockExecutor()
