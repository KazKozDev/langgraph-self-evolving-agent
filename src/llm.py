"""
LLM client — thin wrapper for OpenAI-compatible APIs.

Supports:
  - Real API: set OPENAI_API_KEY + OPENAI_BASE_URL
  - Mock mode: set EVOLUTION_MOCK=true for fast local testing without API

Default model: gpt-4o-mini (or whatever EVOLUTION_MODEL is set to).
"""
from __future__ import annotations

import json
import os

from langchain_openai import ChatOpenAI


class MockLLM:
    """Deterministic mock for testing without API calls."""

    def invoke(self, prompt: str):
        # Return plausible JSON based on prompt keywords
        if "skill" in prompt.lower() and "GOAL" in prompt:
            goal = prompt.split("GOAL:")[1].split("\n")[0].strip() if "GOAL:" in prompt else "task"
            name = goal.lower().replace(" ", "-")[:30]
            return _FakeResponse(json.dumps({
                "name": name,
                "triggers": [f"When asked to {goal[:40]}"],
                "steps": ["Identify the root cause", "Apply the fix incrementally", "Verify with tests"],
                "pitfalls": ["Skipping error logs", "Changing too many things at once"],
            }))

        if "TASK:" in prompt and "STRATEGY:" in prompt:
            is_methodical = "plan first" in prompt.lower() or "methodical" in prompt.lower()
            return _FakeResponse(json.dumps({
                "success": True,
                "steps": 7 if is_methodical else 4,
                "errors": [],
                "output_summary": "Task completed successfully with working code and tests."
            }))

        if "score" in prompt.lower() or "Rate this" in prompt:
            return _FakeResponse(json.dumps({"score": 8}))

        if "domain" in prompt.lower() and "key_pattern" in prompt.lower():
            return _FakeResponse(json.dumps({"domain": "debugging", "key_pattern": "incremental_fix"}))

        if "strategy variants" in prompt.lower() or "Design 3" in prompt or "Design 2" in prompt:
            return _FakeResponse(json.dumps([
                {"id": "A", "desc": "Methodical: plan → implement → test → refactor"},
                {"id": "B", "desc": "Prototype-first: code fast → test → fix"},
                {"id": "C", "desc": "Tool-maximal: parallelize, use all available tools"},
            ]))

        if "hello" in prompt.lower():
            return _FakeResponse("Hello")

        return _FakeResponse(json.dumps({"success": True, "steps": 3, "errors": [], "output_summary": "done"}))


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


def _use_mock() -> bool:
    return os.getenv("EVOLUTION_MOCK", "").lower() in ("1", "true", "yes")


def get_llm(
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2000,
):
    """Return a configured LLM instance (real API or mock)."""
    if _use_mock():
        return MockLLM()

    return ChatOpenAI(
        model=model or os.getenv("EVOLUTION_MODEL", "gpt-4o-mini"),
        temperature=temperature,
        max_tokens=max_tokens,
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
