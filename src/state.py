"""
Self-Evolving Agent — State Models
Based on: APEX (arXiv:2605.21240), EvoDS (arXiv:2606.03841), SOLAR (arXiv:2605.20189)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ── Core domain models ───────────────────────────────────────

class Experience(BaseModel):
    """One completed task run — the raw material of evolution."""
    session_id: str
    goal: str
    domain: str = ""               # coding, debugging, research, deployment, ...
    tool_calls: int = 0
    errors: list[str] = Field(default_factory=list)
    result: str = ""               # success | partial | failure
    key_pattern: str = ""          # what worked (test_before_fix, read_then_write...)
    timestamp: datetime = Field(default_factory=datetime.now)


class Skill(BaseModel):
    """A reusable procedure extracted from successful experience."""
    name: str
    triggers: list[str] = Field(default_factory=list)   # when to use
    steps: list[str] = Field(default_factory=list)       # numbered instructions
    pitfalls: list[str] = Field(default_factory=list)    # what went wrong, fixed
    success_rate: float = 1.0
    use_count: int = 0
    last_used: datetime = Field(default_factory=datetime.now)
    source_session: str = ""       # session_id where this was extracted


class PolicyResult(BaseModel):
    """Outcome of one strategy variant in a policy-exploration run."""
    strategy_id: str               # "A", "B", "C"
    strategy_desc: str
    success: bool
    steps: int
    errors: list[str] = Field(default_factory=list)
    output_summary: str = ""


class TournamentResult(BaseModel):
    """Multi-agent tournament outcome."""
    task: str
    variants: list[PolicyResult]
    winner: str                   # strategy_id
    reason: str


# ── LangGraph State ───────────────────────────────────────────

class EvolutionState(TypedDict):
    """The full state that flows through the evolution graph."""
    # Conversation messages (LangGraph convention)
    messages: Annotated[list, add_messages]

    # Collected experience
    experiences: list[dict]       # serialised Experience
    new_experiences_count: int

    # Skills
    skills: list[dict]            # serialised Skill
    extracted_skills: list[dict]  # fresh extractions this cycle
    degraded_skills: list[dict]   # flagged by anti-forgetting

    # Policy exploration
    policy_variants: list[dict]   # PolicyResult[]
    variant_index: int             # which variant is currently running
    best_policy: dict | None

    # Tournament
    tournament_results: dict | None

    # Control flow
    cycle: int                    # which evolution cycle
    phase: str                    # collect | extract | explore | evaluate | assimilate | done
    human_approval_required: bool
    human_decision: str           # approve | reject | modify

    # Metrics
    total_skills_created: int
    total_improvements: int

    # Errors
    error: str | None


# ── Node names (for graph building) ───────────────────────────

class Nodes:
    COLLECT = "collect_experience"
    EXTRACT = "extract_skills"
    EXPLORE = "explore_policies"
    EVALUATE = "evaluate_results"
    ASSIMILATE = "assimilate_best"
    HUMAN = "human_review"


# ── Constants ─────────────────────────────────────────────────

# Domains we recognise
DOMAINS = ["coding", "debugging", "research", "deployment", "data_science", "writing", "refactoring"]
