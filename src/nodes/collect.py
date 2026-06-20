"""
collect_experience node — load experiences for processing.
Inspired by EvoDS experience collection.
"""
from __future__ import annotations

from src.memory.store import get_store
from src.state import EvolutionState


def collect_experience(state: EvolutionState) -> dict:
    """Load recent experiences from the persistent store.

    Experiences should already have 'domain' and 'key_pattern' set
    (from seed data or prior classification).
    """
    store = get_store()

    # If experiences were injected via state, merge into store
    if injected := state.get("experiences"):
        for exp in injected:
            if isinstance(exp, dict):
                store.add_experience(exp)

    experiences = store.recent_experiences(20)
    return {
        "experiences": experiences,
        "new_experiences_count": len(experiences),
        "phase": "extract",
    }
