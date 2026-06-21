"""
LLM client — thin wrapper for OpenAI-compatible APIs.

Providers (pick via EVOLUTION_PROVIDER or the demo.py --provider flag):
  - mock    : deterministic, no network — EVOLUTION_MOCK=true
  - openai  : any OpenAI-compatible API — OPENAI_API_KEY (+ OPENAI_BASE_URL)
  - ollama  : local Ollama — http://localhost:11434/v1, no key needed
  - auto    : mock if EVOLUTION_MOCK, else openai if a key is set,
              else ollama if it's reachable, else mock (default)

Model: EVOLUTION_MODEL (or provider default).
"""
from __future__ import annotations

import json
import os
import socket
import sys
import urllib.request

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "gemma4:26b-mlx"


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

        # Domain classification — light keyword routing so mock feels real.
        if "classify the task into one of these domains" in prompt.lower():
            g = prompt.split("TASK:")[-1].lower()
            if any(w in g for w in ("research", "search", "find", "compare", "investigate", "look up")):
                d = "research"
            elif any(w in g for w in ("write", "essay", "readme", "article", "blog", "document", "letter")):
                d = "writing"
            elif any(w in g for w in ("plan", "roadmap", "schedule", "strategy")):
                d = "planning"
            elif any(w in g for w in ("analyze", "analyse", "statistics", "data", "chart", "compute average")):
                d = "analysis"
            else:
                d = "coding"
            return _FakeResponse(json.dumps({"domain": d}))

        # Tool synthesis — return a small, genuinely-working tool + test.
        if "extending your own toolbox" in prompt.lower():
            return _FakeResponse(json.dumps({
                "name": "clamp",
                "description": "Clamp a number into the [lo, hi] range",
                "signature": "clamp(x, lo, hi)",
                "code": "def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n",
                "test": "from clamp import clamp\n"
                        "assert clamp(5, 0, 10) == 5\n"
                        "assert clamp(-3, 0, 10) == 0\n"
                        "assert clamp(99, 0, 10) == 10\n",
            }))

        # Comparative judge — must be checked before the "strategy variants"
        # branch below, since the judge prompt also mentions that phrase.
        if '"winner"' in prompt or "pick the single best" in prompt.lower():
            return _FakeResponse(json.dumps({
                "winner": "A",
                "reason": "Best balance of success and fewer steps",
                "quality": 8,
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

        if "you are a helpful assistant" in prompt.lower():
            return _FakeResponse(
                "I'm a self-evolving agent (mock mode). Run me with --provider "
                "ollama for real answers. I learn strategies and write my own tools."
            )

        if "hello" in prompt.lower():
            return _FakeResponse("Hello")

        return _FakeResponse(json.dumps({"success": True, "steps": 3, "errors": [], "output_summary": "done"}))


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


def _use_mock() -> bool:
    return os.getenv("EVOLUTION_MOCK", "").lower() in ("1", "true", "yes")


def ollama_reachable(timeout: float = 0.3) -> bool:
    """Quick TCP check: is an Ollama server listening locally?"""
    host, port = "localhost", 11434
    base = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    # Parse host:port out of a base_url like http://host:port/v1
    try:
        netloc = base.split("//", 1)[-1].split("/", 1)[0]
        host = netloc.split(":")[0] or host
        if ":" in netloc:
            port = int(netloc.split(":")[1])
    except (ValueError, IndexError):
        pass
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def list_ollama_models() -> list[str]:
    """Return the names of models installed in the local Ollama (incl. *-mlx)."""
    base = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    root = base.rsplit("/v1", 1)[0].rstrip("/")
    try:
        with urllib.request.urlopen(f"{root}/api/tags", timeout=2.0) as resp:
            data = json.load(resp)
        names = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        return sorted(names)
    except Exception:
        return []


def resolve_provider() -> str:
    """Resolve the effective provider name (mock | openai | ollama)."""
    provider = os.getenv("EVOLUTION_PROVIDER", "auto").lower()
    if _use_mock():
        return "mock"
    if provider in ("mock", "openai", "ollama"):
        return provider
    # auto
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if ollama_reachable():
        return "ollama"
    return "mock"


_warned_no_key = False


def get_llm(
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2000,
):
    """Return a configured LLM instance for the resolved provider.

    Falls back to the mock if nothing usable is configured, so the evolution
    loop degrades gracefully (e.g. real subprocess execution + simulated
    planning) instead of crashing on ChatOpenAI construction.
    """
    provider = resolve_provider()

    if provider == "mock":
        return MockLLM()

    if provider == "ollama":
        return ChatOpenAI(
            model=model or os.getenv("EVOLUTION_MODEL") or DEFAULT_OLLAMA_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            api_key=SecretStr("ollama"),  # Ollama ignores it but the client requires one
        )

    # openai-compatible
    if not os.getenv("OPENAI_API_KEY"):
        global _warned_no_key
        if not _warned_no_key:
            print("⚠  No OPENAI_API_KEY set — falling back to mock LLM for "
                  "planning/judging. Set a key or use --provider ollama.", file=sys.stderr)
            _warned_no_key = True
        return MockLLM()

    return ChatOpenAI(
        model=model or os.getenv("EVOLUTION_MODEL", "gpt-4o-mini"),
        temperature=temperature,
        max_tokens=max_tokens,
        base_url=os.getenv("OPENAI_BASE_URL"),
    )


def stream_llm(prompt: str, model: str | None = None,
               temperature: float = 0.3, max_tokens: int = 800):
    """Yield response chunks as they arrive (token streaming).

    Real providers stream via the OpenAI-compatible API; the mock yields its
    canned answer word-by-word so the UX is identical everywhere.
    """
    llm = get_llm(model=model, temperature=temperature, max_tokens=max_tokens)
    if isinstance(llm, MockLLM):
        text = str(llm.invoke(prompt).content)
        for word in text.split(" "):
            yield word + " "
        return
    try:
        for chunk in llm.stream(prompt):
            piece = getattr(chunk, "content", "")
            if piece:
                yield str(piece)
    except Exception as e:
        yield f"(stream failed: {e})"
