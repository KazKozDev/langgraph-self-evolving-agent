"""
Session Source — pluggable backend for reading task experience.

Two backends:
  - MockSessionSource: reads from in-memory store (demo/testing)
  - FileSessionSource: reads from a JSON-lines file
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SessionRecord:
    """One session/task extracted from a source."""
    session_id: str
    goal: str
    domain: str = ""
    tool_calls: int = 0
    errors: list[str] = field(default_factory=list)
    result: str = ""
    key_pattern: str = ""
    timestamp: str = ""


class SessionSource(ABC):
    """Abstract source of task experience."""

    @abstractmethod
    def fetch_recent(self, limit: int = 20) -> list[SessionRecord]:
        ...

    def to_dicts(self, records: list[SessionRecord]) -> list[dict]:
        return [
            {
                "session_id": r.session_id,
                "goal": r.goal,
                "domain": r.domain,
                "tool_calls": r.tool_calls,
                "errors": r.errors,
                "result": r.result,
                "key_pattern": r.key_pattern,
            }
            for r in records
        ]


# ── Mock Session Source ───────────────────────────────────────

class MockSessionSource(SessionSource):
    """Reads from the in-memory store."""

    def fetch_recent(self, limit: int = 20) -> list[SessionRecord]:
        from src.memory.store import get_store
        store = get_store()
        return [
            SessionRecord(
                session_id=e.get("session_id", ""),
                goal=e.get("goal", ""),
                domain=e.get("domain", ""),
                tool_calls=e.get("tool_calls", 0),
                errors=e.get("errors", []),
                result=e.get("result", ""),
                key_pattern=e.get("key_pattern", ""),
            )
            for e in store.recent_experiences(limit)
        ]


# ── File Session Source ───────────────────────────────────────

class FileSessionSource(SessionSource):
    """Reads sessions from a JSON-lines file.

    Format (one JSON object per line):
    {"session_id": "...", "goal": "...", "domain": "...", "tool_calls": 5, ...}
    """

    def __init__(self, path: str = "~/.self-evolving-agent/sessions.jsonl"):
        self.path = os.path.expanduser(path)

    def fetch_recent(self, limit: int = 20) -> list[SessionRecord]:
        if not os.path.exists(self.path):
            return []

        records = []
        with open(self.path) as f:
            for line in f:
                if len(records) >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(SessionRecord(
                        session_id=data.get("session_id", ""),
                        goal=data.get("goal", ""),
                        domain=data.get("domain", ""),
                        tool_calls=data.get("tool_calls", 0),
                        errors=data.get("errors", []),
                        result=data.get("result", ""),
                        key_pattern=data.get("key_pattern", ""),
                        timestamp=data.get("timestamp", ""),
                    ))
                except json.JSONDecodeError:
                    continue
        return records


# ── Factory ───────────────────────────────────────────────────

def get_session_source(backend: str = "mock", **kwargs) -> SessionSource:
    if backend == "file":
        return FileSessionSource(path=kwargs.get("path", "~/.self-evolving-agent/sessions.jsonl"))
    return MockSessionSource()
