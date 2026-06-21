"""
Memory store — persistent JSON-backed skill & experience database.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def _strategy_key(desc: str) -> str:
    """Stable, human-readable key for a strategy description.

    Two runs of the *same* strategy must map to the same key so their track
    record (wins / plays / success_rate) accumulates across cycles — this is
    what turns the loop from "try two hardcoded strategies forever" into
    "remember which strategies actually win".
    """
    slug = re.sub(r"[^a-z0-9]+", "-", desc.lower()).strip("-")
    return slug[:60] or "strategy"


class MemoryStore:
    """Simple JSON-file-backed persistent store for skills, experiences, and metrics."""

    def __init__(self, path: str = "~/.self-evolving-agent/memory.json"):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {
            "skills": {}, "experiences": [], "metrics": {},
            "tournaments": [], "strategies": {}, "tools": {}, "history": [],
        }

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

    # ── Strategies (policy memory for the evolution loop) ─────

    def get_strategies(self, domain: str | None = None) -> list[dict]:
        """Return remembered strategies, optionally filtered to a domain.

        Domain-agnostic strategies (empty domain) always match.
        """
        strategies = list(self.data.get("strategies", {}).values())
        if domain:
            strategies = [s for s in strategies if s.get("domain", "") in ("", domain)]
        return strategies

    def record_strategy(self, desc: str, domain: str, success: bool, won: bool = False) -> dict:
        """Record one execution of a strategy and update its running stats.

        success_rate is an exponential moving average so recent outcomes
        weigh more — a strategy that starts winning then degrades will lose
        its lead over time (anti-forgetting). `won` tracks tournament wins.
        """
        if not desc:
            return {}
        strategies = self.data.setdefault("strategies", {})
        key = _strategy_key(desc)
        strat = strategies.get(key) or {
            "key": key,
            "desc": desc,
            "domain": domain,
            "plays": 0,
            "wins": 0,
            "success_rate": 0.5,
        }
        strat["plays"] = strat.get("plays", 0) + 1
        if won:
            strat["wins"] = strat.get("wins", 0) + 1
        old = strat.get("success_rate", 0.5)
        strat["success_rate"] = round(old * 0.7 + (1.0 if success else 0.0) * 0.3, 3)
        strat["last_used"] = datetime.now().isoformat()
        if not strat.get("domain"):
            strat["domain"] = domain
        strategies[key] = strat
        self._save()
        return strat

    # ── Tools (the agent's self-written, reusable capabilities) ─

    def get_tools(self) -> list[dict]:
        return list(self.data.get("tools", {}).values())

    def get_tool(self, name: str) -> dict | None:
        return self.data.get("tools", {}).get(name)

    def save_tool(self, meta: dict):
        """Register or update a synthesized tool's metadata."""
        tools = self.data.setdefault("tools", {})
        meta.setdefault("success_rate", 1.0)
        meta.setdefault("use_count", 0)
        meta["updated_at"] = datetime.now().isoformat()
        tools[meta["name"]] = meta
        self._save()

    def record_tool_use(self, name: str, success: bool):
        """Track a tool invocation; EMA success_rate lets bad tools fade."""
        tools = self.data.setdefault("tools", {})
        if name in tools:
            t = tools[name]
            t["use_count"] = t.get("use_count", 0) + 1
            old = t.get("success_rate", 1.0)
            t["success_rate"] = round(old * 0.8 + (1.0 if success else 0.0) * 0.2, 3)
            t["last_used"] = datetime.now().isoformat()
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

    # ── History (time series for the learning curve) ─────────

    def record_snapshot(self) -> dict:
        """Append a timestamped snapshot of aggregate learning state."""
        strategies = list(self.data.get("strategies", {}).values())
        skills = list(self.data.get("skills", {}).values())
        avg_sr = (
            round(sum(s.get("success_rate", 0.0) for s in strategies) / len(strategies), 3)
            if strategies else 0.0
        )
        snap = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "avg_strategy_success_rate": avg_sr,
            "strategies": len(strategies),
            "skills": len(skills),
            "tools": len(self.data.get("tools", {})),
        }
        history = self.data.setdefault("history", [])
        history.append(snap)
        if len(history) > 500:
            self.data["history"] = history[-500:]
        self._save()
        return snap

    def get_history(self) -> list[dict]:
        return self.data.get("history", [])

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
