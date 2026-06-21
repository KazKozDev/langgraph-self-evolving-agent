"""
extract_skills node — extract reusable skills from successful experiences.
Inspired by EvoDS skill learning mechanism.
"""
from __future__ import annotations

import json

from src.llm import get_llm
from src.memory.store import get_store
from src.state import EvolutionState


def extract_skills(state: EvolutionState) -> dict:
    """Extract one reusable skill from the best successful experience.

    Uses LLM to generate a structured Skill from raw experience data.
    """
    store = get_store()
    experiences = state.get("experiences", [])

    # Pick the best candidate: successful, non-trivial, not yet captured
    candidates = [
        e for e in experiences
        if e.get("result") == "success" and e.get("tool_calls", 0) >= 3
    ]
    if not candidates:
        return {"extracted_skills": [], "phase": "explore"}

    # Only extract ONE skill per cycle (faster, less noise)
    exp = candidates[0]

    # Check if already captured
    existing = store.get_skill(exp.get("key_pattern", ""))
    if existing:
        return {"extracted_skills": [], "skills": store.get_skills(), "phase": "explore"}

    llm = get_llm(max_tokens=500)
    prompt = f"""Extract ONE reusable skill from this successful task. Be concise.

GOAL: {exp.get('goal', '')}
DOMAIN: {exp.get('domain', '')}
KEY PATTERN: {exp.get('key_pattern', '')}
ERRORS OVERCOME: {exp.get('errors', [])}

Return JSON: {{"name": "short-slug", "triggers": ["when to use"], "steps": ["step 1", "step 2", "step 3"], "pitfalls": ["gotcha"]}}
Use 2-4 steps max. Be specific.
"""
    try:
        resp = llm.invoke(prompt)
        from src.json_parser import parse_json
        skill_data = parse_json(str(resp.content))
        skill = {
            "name": skill_data.get("name", f"skill-{len(store.get_skills())}"),
            "triggers": skill_data.get("triggers", []),
            "steps": skill_data.get("steps", []),
            "pitfalls": skill_data.get("pitfalls", []),
            "success_rate": 1.0,
            "use_count": 0,
            "source_session": exp.get("session_id", ""),
            "domain": exp.get("domain", ""),
        }
        store.save_skill(skill)
        store.increment_metric("total_skills_created")
        return {
            "extracted_skills": [skill],
            "skills": store.get_skills(),
            "phase": "explore",
        }
    except Exception:
        return {"extracted_skills": [], "skills": store.get_skills(), "phase": "explore"}
