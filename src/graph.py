"""
Main LangGraph StateGraph — the Self-Evolving Agent.

Phase-based router. Supports:
  - Sequential variant execution (default)
  - Parallel variant execution (Send API, when PARALLEL_EXPLORE=true)
  - Human-in-the-loop via interrupt()
"""
from __future__ import annotations

import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.nodes.assimilate import assimilate_best
from src.nodes.collect import collect_experience
from src.nodes.evaluate import evaluate_results
from src.nodes.explore import explore_policies, run_variant
from src.nodes.extract import extract_skills
from src.nodes.human import human_review
from src.state import EvolutionState


def _phase_router(state: EvolutionState) -> str:
    """Route to the next node based on the current phase."""
    phase = state.get("phase", "")

    if phase == "run_variant":
        idx = state.get("variant_index", 0)
        total = len(state.get("policy_variants", []))
        if idx < total:
            return "run_variant"
        return "evaluate_results"

    if phase == "evaluate":
        return "evaluate_results"

    if phase == "human":
        return "human_review"

    if phase == "assimilate":
        return "assimilate_best"

    if phase == "done":
        return "__end__"

    node_map = {
        "collect": "collect_experience",
        "extract": "extract_skills",
        "explore": "explore_policies",
    }
    return node_map.get(phase, "collect_experience")


def build_graph() -> StateGraph:
    """Build the self-evolving agent graph.

    Set PARALLEL_EXPLORE=true for Send API parallel variant execution.
    """
    builder = StateGraph(EvolutionState)

    builder.add_node("collect_experience", collect_experience)
    builder.add_node("extract_skills", extract_skills)
    builder.add_node("explore_policies", explore_policies)
    builder.add_node("run_variant", run_variant)
    builder.add_node("evaluate_results", evaluate_results)
    builder.add_node("human_review", human_review)
    builder.add_node("assimilate_best", assimilate_best)

    builder.set_entry_point("collect_experience")

    all_nodes = [
        "collect_experience", "extract_skills", "explore_policies",
        "run_variant", "evaluate_results", "human_review", "assimilate_best",
    ]

    for node in all_nodes:
        route_map = {n: n for n in all_nodes}
        route_map["__end__"] = END
        builder.add_conditional_edges(node, _phase_router, route_map)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


_graph: StateGraph | None = None


def get_graph() -> StateGraph:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
