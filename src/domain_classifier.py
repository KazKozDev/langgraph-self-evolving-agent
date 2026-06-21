"""
Domain classifier — infer a task's domain from its text, so the user doesn't
have to specify --domain. The chosen domain routes the task to the right
executor (coding → write/run code, research → web search, etc.).
"""
from __future__ import annotations

from src.json_parser import parse_json
from src.llm import get_llm

VALID_DOMAINS = {
    "coding", "debugging", "deployment", "refactoring",
    "research", "analysis", "data_science", "writing", "planning", "general",
}


def classify_domain(goal: str, default: str = "coding") -> str:
    """Return the best-matching domain for a task goal (LLM-classified)."""
    goal = (goal or "").strip()
    if not goal:
        return default

    prompt = (
        "Classify the task into one of these domains: "
        + ", ".join(sorted(VALID_DOMAINS)) + ".\n"
        f"TASK: {goal}\n"
        'Return JSON: {"domain": "<one domain>"}'
    )
    try:
        data = parse_json(str(get_llm(max_tokens=60).invoke(prompt).content))
        domain = str(data.get("domain", "")).lower().strip() if isinstance(data, dict) else ""
        return domain if domain in VALID_DOMAINS else default
    except Exception:
        return default
