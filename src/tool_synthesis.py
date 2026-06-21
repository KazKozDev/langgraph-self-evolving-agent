"""
Tool synthesis — the agent writes, *verifies*, and registers its own tools.

Flow:
  1. LLM proposes a small, reusable helper function for the task (+ a test)
  2. The tool and its test run in an isolated subprocess
  3. Only if the test PASSES is the tool registered for future reuse

A tool that can't pass its own test is never saved — verification gates
self-extension, so the toolbox stays trustworthy.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from src.json_parser import parse_json
from src.llm import get_llm
from src.memory.store import get_store
from src.tools.registry import register_tool


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    if not s or s[0].isdigit():
        s = f"tool_{s}"
    return s


def _verify(name: str, code: str, test: str, timeout: int = 30) -> tuple[bool, str]:
    """Run the tool's test in a throwaway dir. Returns (passed, output)."""
    if not test.strip():
        return False, "no test provided"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / f"{name}.py").write_text(code)
        (Path(td) / "_toolcheck.py").write_text(test)
        try:
            proc = subprocess.run(
                [os.getenv("EXECUTOR_PYTHON", "python3"), "_toolcheck.py"],
                cwd=td, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"timeout after {timeout}s"
        except FileNotFoundError as e:
            return False, str(e)
    return proc.returncode == 0, (proc.stdout + proc.stderr)[:400]


def synthesize_tool(goal: str, domain: str = "general", store=None) -> dict | None:
    """Design, verify, and register one reusable tool for this task.

    Returns the tool metadata on success, or None (no tool needed / failed test).
    """
    store = store or get_store()

    prompt = (
        "You are extending your own toolbox. If a small, REUSABLE, general helper "
        "function would help with tasks like the one below, design exactly ONE.\n"
        f"TASK: {goal}\nDOMAIN: {domain}\n\n"
        "Rules:\n"
        "- The function must be self-contained (stdlib only) and generally useful.\n"
        "- The test must import the function from a module named EXACTLY the tool "
        "name and assert on its behaviour.\n"
        "- If no reusable tool makes sense, return {}.\n\n"
        'Return JSON: {"name": "snake_case_name", "description": "one line", '
        '"signature": "name(arg1, arg2)", "code": "def name(...):\\n    ...", '
        '"test": "from name import name\\nassert name(...) == ..."}'
    )

    try:
        data = parse_json(str(get_llm(max_tokens=1200).invoke(prompt).content))
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("name") or not data.get("code"):
        return None

    name = _slug(str(data["name"]))
    if store.get_tool(name):
        return store.get_tool(name)  # already have it — don't regenerate

    code = str(data["code"])
    test = str(data.get("test", ""))
    passed, output = _verify(name, code, test)
    if not passed:
        print(f"  🔧 tool '{name}' failed verification — discarded. {output[:120]}",
              file=sys.stderr)
        return None

    meta = register_tool(
        name=name,
        code=code,
        description=str(data.get("description", "")),
        signature=str(data.get("signature", f"{name}()")),
        store=store,
    )
    print(f"  🔧 synthesized + verified new tool: {meta['signature']}", flush=True)
    return meta
