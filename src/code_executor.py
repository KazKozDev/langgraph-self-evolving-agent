"""
Code Executor — actually writes, runs, and fixes Python code.

Flow:
  1. LLM generates code for the task
  2. Runs it in subprocess with timeout
  3. On failure: feeds error back to LLM, retries (up to 3 attempts)
  4. Returns ExecutionResult with real stdout, stderr, exit code

This is how the agent genuinely executes tasks — not simulated.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
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
    attempts: int = 1
    code: str = ""


class CodeExecutor:
    """Generates, runs, and fixes Python code for a task.

    Uses LLM for code generation and error fixing.
    Runs code in an isolated temp directory via subprocess.
    """

    def __init__(
        self,
        timeout: int = 120,
        max_retries: int = 3,
        venv_python: str | None = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.python = venv_python or os.getenv("EXECUTOR_PYTHON", "python3")

    def execute(self, goal: str, strategy_desc: str = "", domain: str = "coding") -> ExecutionResult:
        """Execute a task: generate code, run it, fix if needed."""
        strategy_hint = f"\nStrategy: {strategy_desc}" if strategy_desc else ""

        # ── Attempt 1: generate code ──────────────────────────
        code, errors = self._generate_code(goal, strategy_hint, previous_error=None)
        if errors:
            return ExecutionResult(
                success=False, steps=1, errors=errors,
                output_summary="Code generation failed",
            )

        # ── Run + retry loop ──────────────────────────────────
        for attempt in range(1, self.max_retries + 1):
            result = self._run_code(code)
            result.attempts = attempt
            result.code = code

            if result.success:
                return result

            if attempt < self.max_retries:
                # Fix: feed error back to LLM
                error_text = "\n".join(result.errors[-3:])  # last 3 errors
                code, gen_errors = self._generate_code(goal, strategy_hint, previous_error=error_text)
                if gen_errors:
                    result.errors.extend(gen_errors)
                    return result

        result.errors.append(f"Failed after {self.max_retries} attempts")
        return result

    # ── Internal ─────────────────────────────────────────────

    def _generate_code(self, goal: str, strategy_hint: str = "", previous_error: str | None = None) -> tuple[str, list[str]]:
        """Ask LLM to generate Python code for the task."""
        from src.llm import get_llm

        llm = get_llm(max_tokens=1500)

        if previous_error:
            prompt = f"""The following Python code FAILED with this error:

{previous_error}

Original task: {goal}{strategy_hint}

Write a FIXED version. Complete, runnable Python script. Print a clear success message at the end.
Return ONLY the Python code, no markdown fences, no explanations.
"""
        else:
            prompt = f"""Write a complete, runnable Python script for this task:

{goal}{strategy_hint}

Rules:
- Must run with `python3 script.py` and exit 0 on success
- Print clear progress messages
- Handle errors gracefully
- Print "SUCCESS: <summary>" at the end
- Keep it under 100 lines

Return ONLY the Python code, no markdown fences, no explanations.
"""
        try:
            resp = llm.invoke(prompt)
            code = str(resp.content).strip()
            # Strip markdown fences if present
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            return code.strip(), []
        except Exception as e:
            return "", [f"LLM generation failed: {e}"]

    def _run_code(self, code: str) -> ExecutionResult:
        """Save code to temp file and execute it."""
        tmpdir = tempfile.mkdtemp(prefix="evagent-")
        script_path = os.path.join(tmpdir, "task.py")

        try:
            with open(script_path, "w") as f:
                f.write(code)

            proc = subprocess.run(
                [self.python, script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=tmpdir,
            )

            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
            success = exit_code == 0

            errors = []
            if not success:
                if stderr:
                    errors.extend(stderr.strip().split("\n")[-5:])
                errors.append(f"exit_code={exit_code}")

            # Extract summary: look for "SUCCESS:" or last meaningful line
            summary = ""
            for line in stdout.split("\n"):
                if "SUCCESS:" in line or "success:" in line.lower():
                    summary = line.strip()
                    break
            if not summary:
                lines = [l for l in stdout.split("\n") if l.strip() and not l.startswith("#")]
                summary = lines[-1] if lines else stdout[:100]

            steps = len([l for l in stdout.split("\n") if l.strip()])

            return ExecutionResult(
                success=success,
                steps=max(1, steps),
                errors=errors,
                output_summary=summary,
                raw_output=stdout + stderr,
                exit_code=exit_code,
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                errors=[f"Timeout after {self.timeout}s"],
                output_summary="Code took too long",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                errors=[str(e)],
                output_summary="Execution failed",
            )
        finally:
            # Cleanup temp dir
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
