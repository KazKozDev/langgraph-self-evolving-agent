"""
collect_experience node — load experiences from configured session source.

Inspired by EvoDS experience collection.
Supports: mock (in-memory), hermes (real sessions via CLI/SQLite).
"""
from __future__ import annotations

import os

from src.memory.store import get_store
from src.state import EvolutionState


def _get_session_source():
    """Lazy-load the configured session source."""
    backend = os.getenv("SESSION_SOURCE", "mock")
    from src.session_source import get_session_source
    return get_session_source(backend)


def collect_experience(state: EvolutionState) -> dict:
    """Load recent experiences from the session source.

    Merges injected experiences (from state) with whatever the source provides.
    """
    store = get_store()

    # Merge injected experiences into store
    if injected := state.get("experiences"):
        for exp in injected:
            if isinstance(exp, dict) and exp.get("session_id"):
                store.add_experience(exp)

    # Fetch from configured source
    source = _get_session_source()
    records = source.fetch_recent(limit=20)

    # Convert to dicts and merge into store
    experiences = source.to_dicts(records)
    for exp in experiences:
        store.add_experience(exp)

    # Re-read from store (deduplicated, latest)
    all_experiences = store.recent_experiences(20)

    return {
        "experiences": all_experiences,
        "new_experiences_count": len(all_experiences),
        "phase": "extract",
    }
