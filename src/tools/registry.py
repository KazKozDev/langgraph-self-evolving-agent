"""
Tool registry — the agent's self-written, reusable capabilities.

Generated tools are Python files in TOOLS_DIR (default
~/.self-evolving-agent/tools), one function per file, the function named
exactly after the tool. Metadata (description, signature, success_rate,
use_count) lives in the persistent memory store.

This is the second evolution loop: the agent doesn't just learn *which
strategy* works, it grows *new capabilities* it can call on future tasks.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Callable

from src.memory.store import get_store


def tools_dir() -> Path:
    """Directory where synthesized tool modules are stored (auto-created)."""
    path = Path(os.getenv("TOOLS_DIR", "~/.self-evolving-agent/tools")).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_on_path():
    d = str(tools_dir())
    if d not in sys.path:
        sys.path.insert(0, d)


def register_tool(name: str, code: str, description: str, signature: str, store=None) -> dict:
    """Write a tool module to disk and record its metadata."""
    store = store or get_store()
    (tools_dir() / f"{name}.py").write_text(code)
    meta = {
        "name": name,
        "description": description,
        "signature": signature or f"{name}(...)",
        "file": str(tools_dir() / f"{name}.py"),
        "success_rate": 1.0,
        "use_count": 0,
    }
    store.save_tool(meta)
    return meta


def list_tools(store=None) -> list[dict]:
    return (store or get_store()).get_tools()


def load_tool(name: str) -> Callable | None:
    """Import and return the callable for a registered tool, or None."""
    _ensure_on_path()
    path = tools_dir() / f"{name}.py"
    if not path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, name, None)
    except Exception:
        return None


def builtin_tools() -> list[dict]:
    """Tools the agent ships with (file access, etc.)."""
    try:
        from src.tools.builtins import BUILTIN_TOOLS
        return list(BUILTIN_TOOLS)
    except Exception:
        return []


def tool_catalog(store=None) -> str:
    """Human/LLM-readable list of available tools for prompt injection."""
    sections = []

    builtins = builtin_tools()
    if builtins:
        lines = [f"- {t['signature']} — {t['description']}" for t in builtins]
        sections.append(
            "Built-in tools (import: `from src.tools.builtins import "
            + ", ".join(t["signature"].split("(")[0] for t in builtins)
            + "`):\n" + "\n".join(lines)
        )

    tools = list_tools(store)
    if tools:
        lines = [
            f"- {t['signature']} — {t.get('description', '')} "
            f"(import: `from {t['name']} import {t['name']}`)"
            for t in tools
        ]
        sections.append("Self-written tools you may reuse:\n" + "\n".join(lines))

    return "\n\n".join(sections)
