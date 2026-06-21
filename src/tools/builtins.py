"""
Built-in tools — capabilities the agent ships with (vs. ones it writes itself).

File access is confined to a workspace directory (AGENT_WORKSPACE, default
./agent_workspace). Paths that escape the workspace are rejected, so generated
code can read/write project-style files without touching the rest of the disk.

These are importable from generated code as:
    from src.tools.builtins import read_file, write_file, list_dir
"""
from __future__ import annotations

import os
from pathlib import Path


def workspace() -> Path:
    """The sandbox root for file tools (auto-created)."""
    root = Path(os.getenv("AGENT_WORKSPACE", "agent_workspace")).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe(path: str) -> Path:
    """Resolve `path` inside the workspace, rejecting traversal escapes."""
    root = workspace()
    target = (root / path).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"path escapes workspace: {path}")
    return target


def read_file(path: str) -> str:
    """Read and return the text of a file inside the workspace."""
    return _safe(path).read_text()


def write_file(path: str, content: str) -> str:
    """Write text to a file inside the workspace (creating dirs). Returns its path."""
    target = _safe(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return str(target)


def list_dir(path: str = ".") -> list[str]:
    """List entry names under a workspace directory."""
    target = _safe(path)
    if not target.exists():
        return []
    return sorted(p.name for p in target.iterdir())


# Catalog metadata for prompt injection / `--list-tools`.
BUILTIN_TOOLS = [
    {"signature": "read_file(path)", "description": "Read a text file in the workspace"},
    {"signature": "write_file(path, content)", "description": "Write a text file in the workspace"},
    {"signature": "list_dir(path='.')", "description": "List files in a workspace directory"},
]
