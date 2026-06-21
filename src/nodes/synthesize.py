"""
synthesize_tools node — grow the agent's toolbox between extract and explore.

Opt-in via TOOL_SYNTHESIS=true (the --task live mode turns it on). Off by
default so the historical-cycle demo and tests stay deterministic.
"""
from __future__ import annotations

import os

from src.state import EvolutionState


def _enabled() -> bool:
    return os.getenv("TOOL_SYNTHESIS", "").lower() in ("1", "true", "yes")


def synthesize_tools(state: EvolutionState) -> dict:
    """Try to write + verify + register one reusable tool for the target task."""
    if not _enabled():
        return {"phase": "explore"}

    # Prefer the live task; otherwise the freshest experience's goal.
    goal = (state.get("task_goal") or "").strip()
    domain = state.get("task_domain") or "coding"
    if not goal:
        experiences = state.get("experiences", [])
        if experiences:
            goal = experiences[0].get("goal", "")
            domain = experiences[0].get("domain", domain)
    if not goal:
        return {"phase": "explore"}

    try:
        from src.tool_synthesis import synthesize_tool
        meta = synthesize_tool(goal, domain)
    except Exception:
        meta = None

    return {
        "synthesized_tools": [meta] if meta else [],
        "phase": "explore",
    }
