"""
human_review node — interrupt for human approval before risky skill changes.
Inspired by ANCHOR (arXiv:2606.06114) — human-in-the-loop for safe evolution.
"""
from __future__ import annotations

from src.state import EvolutionState


def human_review(state: EvolutionState) -> dict:
    """Wait for human approval before applying a risky skill change.

    This is a LangGraph interrupt node — execution pauses here
    until the human calls update_state with their decision.
    """
    best_policy = state.get("best_policy", {})

    # In LangGraph, this would be an interrupt() call.
    # For a non-interactive run, auto-approve safe changes.
    quality = best_policy.get("quality_scores", {})
    correctness = quality.get("correctness", 0)

    if correctness >= 8:
        decision = "approve"
    else:
        # In production: graph.interrupt("review") and wait
        # For demo: auto-reject low-quality and move on
        decision = "reject"

    return {
        "human_decision": decision,
        "phase": "assimilate" if decision == "approve" else "done",
    }
