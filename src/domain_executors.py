"""
Domain Executors — each task type gets the right tool.

Coding   → CodeExecutor    (write + run + fix Python)
Research → ResearchExecutor (web search + extract + synthesize)
Analysis → AnalysisExecutor (compute, chart, process data)
Writing  → WritingExecutor  (generate documents, reports)
Planning → PlanningExecutor (structured plans, roadmaps)
General  → GeneralExecutor  (LLM reasoning for everything else)

The agent auto-routes tasks to the right executor based on domain.
Every executor produces real output — no simulation.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExecutionResult:
    success: bool
    steps: int = 0
    errors: list[str] = field(default_factory=list)
    output_summary: str = ""
    raw_output: str = ""
    exit_code: int = 0
    attempts: int = 1
    artifacts: list[str] = field(default_factory=list)  # paths to created files


class DomainExecutor(ABC):
    """Abstract executor for a specific task domain."""

    @abstractmethod
    def execute(self, goal: str, strategy_desc: str = "", domain: str = "general") -> ExecutionResult:
        ...


# ── Coding Executor ───────────────────────────────────────────

class CodingExecutor(DomainExecutor):
    """Write → run → fix Python code. Up to 3 retries on failure."""

    def __init__(self, timeout: int = 120, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    def execute(self, goal: str, strategy_desc: str = "", domain: str = "coding") -> ExecutionResult:
        strategy = f"\nStrategy: {strategy_desc}" if strategy_desc else ""

        code, errors = self._generate(goal, strategy)
        if errors:
            return ExecutionResult(False, errors=errors)

        for attempt in range(1, self.max_retries + 1):
            result = self._run(code)
            result.attempts = attempt
            if result.success:
                return result
            if attempt < self.max_retries:
                code, gen_err = self._generate(goal, strategy, "\n".join(result.errors[-3:]))
                if gen_err:
                    result.errors.extend(gen_err)
                    return result

        result.errors.append(f"Failed after {self.max_retries} attempts")
        return result

    def _generate(self, goal: str, strategy: str, error: str | None = None) -> tuple[str, list[str]]:
        from src.llm import get_llm
        llm = get_llm(max_tokens=1500)
        if error:
            prompt = f"Code FAILED with:\n{error}\n\nTask: {goal}{strategy}\n\nWrite FIXED Python. Only code, no markdown."
        else:
            prompt = f"Write Python script. Task: {goal}{strategy}\n\nRunnable with python3. Print 'SUCCESS: <summary>' at end. Only code, no markdown."
        try:
            resp = llm.invoke(prompt)
            code = str(resp.content).strip()
            if code.startswith("```"):
                code = "\n".join(code.split("\n")[1:])
            if code.endswith("```"):
                code = "\n".join(code.split("\n")[:-1])
            return code.strip(), []
        except Exception as e:
            return "", [str(e)]

    def _run(self, code: str) -> ExecutionResult:
        tmp = tempfile.mkdtemp(prefix="evagent-")
        path = os.path.join(tmp, "task.py")
        try:
            with open(path, "w") as f:
                f.write(code)
            proc = subprocess.run(["python3", path], capture_output=True, text=True, timeout=self.timeout, cwd=tmp)
            out = proc.stdout + proc.stderr
            ok = proc.returncode == 0
            errors = [] if ok else [l for l in proc.stderr.split("\n") if l.strip()][-3:]
            errors.append(f"exit={proc.returncode}")
            summary = ""
            for line in proc.stdout.split("\n"):
                if "SUCCESS:" in line.lower():
                    summary = line.strip()
                    break
            if not summary:
                lines = [l for l in proc.stdout.split("\n") if l.strip() and not l.startswith("#")]
                summary = lines[-1] if lines else out[:100]
            return ExecutionResult(ok, len([l for l in out.split("\n") if l.strip()]), errors, summary, out, proc.returncode, artifacts=[path])
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, errors=["timeout"])
        except Exception as e:
            return ExecutionResult(False, errors=[str(e)])
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)


# ── Research Executor ─────────────────────────────────────────

class ResearchExecutor(DomainExecutor):
    """Web search → fetch pages → LLM synthesis → structured findings.

    Uses real HTTP calls (httpx) to search and fetch content.
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def execute(self, goal: str, strategy_desc: str = "", domain: str = "research") -> ExecutionResult:
        from src.llm import get_llm
        import urllib.request
        import urllib.error

        llm = get_llm(max_tokens=1200)
        errors = []
        findings = []

        # Step 1: Generate search queries from goal
        try:
            resp = llm.invoke(
                f"Task: {goal}\n\nGenerate 2 Google search queries to research this. "
                f"Return JSON: {{\"queries\": [\"query1\", \"query2\"]}}"
            )
            data = json.loads(str(resp.content))
            queries = data.get("queries", [goal])
        except Exception:
            queries = [goal]

        # Step 2: Execute searches (DuckDuckGo HTML, no API key needed)
        for q in queries[:2]:
            try:
                url = f"https://html.duckduckgo.com/html/?q={urllib.request.quote(q)}"
                req = urllib.request.Request(url, headers={"User-Agent": "SelfEvolvingAgent/1.0"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                # Extract snippets (simple regex for DuckDuckGo HTML)
                import re
                snippets = re.findall(r'class="result__snippet">(.*?)</a>', html, re.DOTALL)
                findings.extend(s[:300].strip() for s in snippets[:3])
            except Exception as e:
                errors.append(f"search failed for '{q[:40]}': {e}")

        # Step 3: Synthesize
        if findings:
            ctx = "\n".join(f"- {f}" for f in findings[:6])
            try:
                resp = llm.invoke(
                    f"Research task: {goal}\n\nSources:\n{ctx}\n\n"
                    f"Synthesize a concise answer (3-5 sentences). Return JSON: {{\"answer\": \"...\", \"sources\": N}}"
                )
                data = json.loads(str(resp.content))
                summary = data.get("answer", "")
                steps = len(findings) + 1
            except Exception:
                summary = "\n".join(findings[:3])
                steps = len(findings)
        else:
            summary = "No sources found."
            steps = 0

        return ExecutionResult(
            success=len(findings) > 0,
            steps=steps,
            errors=errors,
            output_summary=summary,
            raw_output="\n".join(findings),
        )


# ── Analysis Executor ─────────────────────────────────────────

class AnalysisExecutor(DomainExecutor):
    """Data processing, computation, statistics — runs real Python."""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def execute(self, goal: str, strategy_desc: str = "", domain: str = "analysis") -> ExecutionResult:
        # Delegate to CodingExecutor but with data-science context
        coder = CodingExecutor(timeout=self.timeout, max_retries=2)
        enhanced_goal = f"{goal}\n\nUse only Python stdlib (no external packages unless specified). Print results clearly."
        result = coder.execute(enhanced_goal, strategy_desc, "analysis")
        result.steps = max(result.steps, 1)
        return result


# ── Writing Executor ──────────────────────────────────────────

class WritingExecutor(DomainExecutor):
    """Generates structured documents: reports, articles, plans.

    Saves output as .md files in an artifacts directory.
    """

    def __init__(self, output_dir: str = "~/.self-evolving-agent/artifacts"):
        self.output_dir = Path(os.path.expanduser(output_dir))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, goal: str, strategy_desc: str = "", domain: str = "writing") -> ExecutionResult:
        from src.llm import get_llm

        llm = get_llm(max_tokens=2000)
        strategy = f"\nApproach: {strategy_desc}" if strategy_desc else ""

        prompt = (
            f"Write a structured document for this task:\n\n{goal}{strategy}\n\n"
            f"Format as Markdown with headings, bullet points, and clear sections.\n"
            f"Title should be the first # heading. Be thorough but concise."
        )

        try:
            resp = llm.invoke(prompt)
            content = str(resp.content).strip()
        except Exception as e:
            return ExecutionResult(False, errors=[str(e)])

        # Save artifact
        slug = goal.lower().replace(" ", "-")[:40]
        fname = f"{slug}.md"
        fpath = self.output_dir / fname
        fpath.write_text(content)

        # Extract title for summary
        title = goal[:80]
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        return ExecutionResult(
            success=True,
            steps=1,
            output_summary=f"Document: {title}",
            raw_output=content[:500],
            artifacts=[str(fpath)],
        )


# ── Planning Executor ─────────────────────────────────────────

class PlanningExecutor(DomainExecutor):
    """Creates structured plans with phases, tasks, estimates."""

    def execute(self, goal: str, strategy_desc: str = "", domain: str = "planning") -> ExecutionResult:
        from src.llm import get_llm

        llm = get_llm(max_tokens=1500)

        prompt = (
            f"Create a structured plan for: {goal}\n\n"
            f"Return JSON with:\n"
            f'{{"title": "...", "phases": [{{"name": "...", "tasks": ["..."], "estimate": "..."}}], '
            f'"total_estimate": "...", "risks": ["..."]}}'
        )

        try:
            resp = llm.invoke(prompt)
            plan = json.loads(str(resp.content))
            phases_n = len(plan.get("phases", []))
            tasks_n = sum(len(p.get("tasks", [])) for p in plan.get("phases", []))
            summary = f"Plan: {plan.get('title', goal[:60])} — {phases_n} phases, {tasks_n} tasks, est. {plan.get('total_estimate', 'unknown')}"
            return ExecutionResult(
                success=True,
                steps=phases_n,
                output_summary=summary,
                raw_output=json.dumps(plan, indent=2),
            )
        except Exception:
            return ExecutionResult(False, errors=["plan_generation_failed"])


# ── General Executor ──────────────────────────────────────────

class GeneralExecutor(DomainExecutor):
    """LLM-powered reasoning for any task that doesn't fit other domains."""

    def execute(self, goal: str, strategy_desc: str = "", domain: str = "general") -> ExecutionResult:
        from src.llm import get_llm

        llm = get_llm(max_tokens=1000)
        strategy = f"\nApproach: {strategy_desc}" if strategy_desc else ""

        try:
            resp = llm.invoke(
                f"Complete this task: {goal}{strategy}\n\n"
                f"Be direct and concise. If the task requires code, write it. "
                f"If it requires reasoning, explain step by step."
            )
            output = str(resp.content).strip()
            return ExecutionResult(
                success=True,
                steps=1,
                output_summary=output[:200],
                raw_output=output,
            )
        except Exception as e:
            return ExecutionResult(False, errors=[str(e)])


# ── Domain Router ─────────────────────────────────────────────

DOMAIN_EXECUTORS = {
    "coding": CodingExecutor,
    "debugging": CodingExecutor,
    "deployment": CodingExecutor,
    "refactoring": CodingExecutor,
    "research": ResearchExecutor,
    "analysis": AnalysisExecutor,
    "data_science": AnalysisExecutor,
    "writing": WritingExecutor,
    "planning": PlanningExecutor,
    "general": GeneralExecutor,
}


def get_domain_executor(domain: str = "general") -> DomainExecutor:
    """Get the right executor for a task domain."""
    cls = DOMAIN_EXECUTORS.get(domain, GeneralExecutor)
    return cls()
