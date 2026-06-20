"""
Memory store — persistent JSON-backed skill & experience database.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class MemoryStore:
    """Simple JSON-file-backed persistent store for skills, experiences, and metrics."""

    def __init__(self, path: str = "~/.self-evolving-agent/memory.json"):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {"skills": {}, "experiences": [], "metrics": {}, "tournaments": []}

    def _save(self):
        self.path.write_text(json.dumps(self.data, indent=2, default=str))

    # ── Skills ────────────────────────────────────────────────

    def get_skills(self) -> list[dict]:
        return list(self.data["skills"].values())

    def get_skill(self, name: str) -> dict | None:
        return self.data["skills"].get(name)

    def save_skill(self, skill: dict):
        """Create or update a skill."""
        skill["updated_at"] = datetime.now().isoformat()
        self.data["skills"][skill["name"]] = skill
        self._save()

    def increment_skill_use(self, name: str):
        if name in self.data["skills"]:
            self.data["skills"][name]["use_count"] = self.data["skills"][name].get("use_count", 0) + 1
            self.data["skills"][name]["last_used"] = datetime.now().isoformat()
            self._save()

    def update_success_rate(self, name: str, success: bool):
        if name in self.data["skills"]:
            sk = self.data["skills"][name]
            old = sk.get("success_rate", 1.0)
            # Exponential moving average
            sk["success_rate"] = round(old * 0.9 + (1.0 if success else 0.0) * 0.1, 3)
            self._save()

    # ── Experiences ───────────────────────────────────────────

    def add_experience(self, exp: dict):
        self.data["experiences"].append(exp)
        # Keep last 1000
        if len(self.data["experiences"]) > 1000:
            self.data["experiences"] = self.data["experiences"][-1000:]
        self._save()

    def recent_experiences(self, n: int = 20) -> list[dict]:
        return self.data["experiences"][-n:]

    # ── Metrics ───────────────────────────────────────────────

    def get_metric(self, key: str, default: Any = 0) -> Any:
        return self.data["metrics"].get(key, default)

    def set_metric(self, key: str, value: Any):
        self.data["metrics"][key] = value
        self._save()

    def increment_metric(self, key: str):
        self.data["metrics"][key] = self.data["metrics"].get(key, 0) + 1
        self._save()


# Singleton
_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
