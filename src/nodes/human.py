"""
human_review node — interrupt for human approval before risky changes.
Inspired by ANCHOR (arXiv:2606.06114).

Uses LangGraph interrupt() for real human-in-the-loop.
When running non-interactively, auto-approves safe changes (quality >= 8).
"""
from __future__ import annotations

from src.state import EvolutionState


def human_review(state: EvolutionState) -> dict:
    """Wait for human approval on risky skill changes.

    In interactive mode (graph.interrupt available): pauses and waits.
    In non-interactive/demo mode: auto-approve if quality >= 8, else reject.
    """
    best_policy = state.get("best_policy", {}) or {}
    quality = best_policy.get("quality_score", 7)
    strategy_desc = best_policy.get("strategy_desc", "unknown")
    output = best_policy.get("output_summary", "")

    try:
        # Try real LangGraph interrupt — pauses execution,
        # user calls update_state with their decision.
        from langgraph.types import interrupt

        decision = interrupt(
            f"Strategy '{strategy_desc}' scored {quality}/10.\n"
            f"Output: {output}\n"
            f"Apply this as a new skill? (approve/reject)"
        )
        return {
            "human_decision": decision if decision in ("approve", "reject") else "reject",
            "phase": "assimilate" if decision == "approve" else "done",
        }

    except (ImportError, Exception):
        # Non-interactive fallback: auto-approve safe changes
        if quality >= 8:
            decision = "approve"
        else:
            decision = "reject"

        return {
            "human_decision": decision,
            "phase": "assimilate" if decision == "approve" else "done",
        }
