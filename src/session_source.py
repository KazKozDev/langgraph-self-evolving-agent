"""
Session Source — pluggable backend for reading task experience.

Four backends:
  - MockSessionSource: in-memory store (demo/testing)
  - FileSessionSource: JSON-lines file
  - SQLiteSessionSource: any SQLite DB with a sessions table
  - WatchSessionSource: watches a directory for new JSON files in real-time
"""
from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


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


# ── Mock ──────────────────────────────────────────────────────

class MockSessionSource(SessionSource):
    """Reads from the in-memory store."""

    def fetch_recent(self, limit: int = 20) -> list[SessionRecord]:
        from src.memory.store import get_store
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
            for e in get_store().recent_experiences(limit)
        ]


# ── File (JSONL) ──────────────────────────────────────────────

class FileSessionSource(SessionSource):
    """Reads sessions from a JSON-lines file."""

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


# ── SQLite ─────────────────────────────────────────────────────

class SQLiteSessionSource(SessionSource):
    """Reads sessions from any SQLite database.

    Generic schema — adaptable via column_mapping.
    Default expects: sessions(id, title, created_at, ...)
    """

    def __init__(
        self,
        db_path: str = "~/.self-evolving-agent/sessions.db",
        table: str = "sessions",
        column_mapping: dict | None = None,
    ):
        self.db_path = os.path.expanduser(db_path)
        self.table = table
        self.mapping = column_mapping or {
            "session_id": "id",
            "goal": "title",
            "timestamp": "created_at",
        }

    def fetch_recent(self, limit: int = 20) -> list[SessionRecord]:
        if not os.path.exists(self.db_path):
            return []

        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            cols = ", ".join(set(self.mapping.values()))
            order_col = self.mapping.get("timestamp", "rowid")
            query = f"SELECT {cols} FROM {self.table} ORDER BY {order_col} DESC LIMIT ?"

            cursor = conn.execute(query, (limit,))
            records = []
            for row in cursor:
                data = dict(row)
                records.append(SessionRecord(
                    session_id=str(data.get(self.mapping.get("session_id", "id"), "")),
                    goal=str(data.get(self.mapping.get("goal", "title"), "") or ""),
                    domain=self._classify(str(data.get(self.mapping.get("goal", "title"), "") or "")),
                    tool_calls=data.get("tool_calls", 0),
                    errors=[],
                    result="unknown",
                    key_pattern="",
                    timestamp=str(data.get(self.mapping.get("timestamp", "created_at"), "")),
                ))
            conn.close()
            return records
        except Exception:
            return []

    def _classify(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["debug", "error", "fix", "bug"]): return "debugging"
        if any(k in t for k in ["deploy", "ci/cd", "docker", "pipeline"]): return "deployment"
        if any(k in t for k in ["test", "pytest"]): return "coding"
        if any(k in t for k in ["research", "compare"]): return "research"
        if any(k in t for k in ["refactor", "clean"]): return "refactoring"
        return "coding"


# ── Watch (directory watcher) ──────────────────────────────────

class WatchSessionSource(SessionSource):
    """Watches a directory for new .json session files in real-time.

    Each file: {"session_id": "...", "goal": "...", ...}
    Files are deleted after reading (consumed).
    """

    def __init__(self, watch_dir: str = "~/.self-evolving-agent/incoming/"):
        self.watch_dir = Path(os.path.expanduser(watch_dir))
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()

    def fetch_recent(self, limit: int = 20) -> list[SessionRecord]:
        records = []
        files = sorted(self.watch_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

        for fp in files:
            if len(records) >= limit:
                break
            try:
                data = json.loads(fp.read_text())
                sid = data.get("session_id", fp.stem)
                if sid in self._seen:
                    continue
                self._seen.add(sid)
                records.append(SessionRecord(
                    session_id=sid,
                    goal=data.get("goal", ""),
                    domain=data.get("domain", ""),
                    tool_calls=data.get("tool_calls", 0),
                    errors=data.get("errors", []),
                    result=data.get("result", ""),
                    key_pattern=data.get("key_pattern", ""),
                    timestamp=str(fp.stat().st_mtime),
                ))
                fp.unlink()  # consume
            except (json.JSONDecodeError, OSError):
                continue

        return records


# ── Factory ───────────────────────────────────────────────────

def get_session_source(backend: str = "mock", **kwargs) -> SessionSource:
    if backend == "file":
        return FileSessionSource(path=kwargs.get("path", "~/.self-evolving-agent/sessions.jsonl"))
    if backend == "sqlite":
        return SQLiteSessionSource(
            db_path=kwargs.get("db_path", "~/.self-evolving-agent/sessions.db"),
            table=kwargs.get("table", "sessions"),
        )
    if backend == "watch":
        return WatchSessionSource(watch_dir=kwargs.get("watch_dir", "~/.self-evolving-agent/incoming/"))
    return MockSessionSource()
