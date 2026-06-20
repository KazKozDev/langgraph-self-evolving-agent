# Self-Evolving Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![LangGraph](https://img.shields.io/badge/langgraph-1.2+-green.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

An autonomous self-evolving LLM agent built on **LangGraph**. The agent collects experience from completed tasks, extracts reusable skills, explores alternative strategies, evaluates outcomes, and assimilates the best patterns — forming a closed evolutionary loop.

> Built on research from 9 arXiv papers (2026) on self-evolving LLM agents — APEX, EvoDS, SOLAR, ANCHOR, PEAM, AEL, SimWorld Studio, and more.

## Architecture

```
           ┌──────────────────────────────────┐
           │        collect_experience         │
           │   scan sessions → store outcomes   │
           └──────────────┬───────────────────┘
                          │ phase=extract
           ┌──────────────▼───────────────────┐
           │         extract_skills            │
           │   LLM distills successful runs    │
           │   into reusable Skill objects     │
           └──────────────┬───────────────────┘
                          │ phase=explore
           ┌──────────────▼───────────────────┐
           │       explore_policies            │
           │   design 2 strategy variants      │
           │   for a suboptimal task           │
           └──────────────┬───────────────────┘
                          │ phase=run_variant
           ┌──────────────▼───────────────────┐
           │  run_variant (×2, sequential)     │
           │  simulate each strategy via LLM   │
           │  track: success, steps, errors    │
           └──────────────┬───────────────────┘
                          │ phase=evaluate
           ┌──────────────▼───────────────────┐
           │       evaluate_results            │
           │  compare variants, pick winner    │
           │  LLM-as-judge quality scoring     │
           │  detect degraded skills           │
           └──────────────┬───────────────────┘
                          │
                    ┌─────┴─────┐
                    │ risky?    │
                    ▼           ▼
           ┌───────────┐  ┌──────────────┐
           │human_review│  │assimilate_best│
           │ (interrupt)│  │ save winning  │
           └─────┬─────┘  │ strategy as   │
                 │        │ skill         │
                 └───┬────┴──────────────┘
                     │ phase=done → END
```

## Quick Start

```bash
git clone https://github.com/YOU/self-evolving-agent.git
cd self-evolving-agent

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Mock mode — no API key needed
EVOLUTION_MOCK=true python demo.py
```

**With a real LLM** (OpenAI-compatible API):

```bash
OPENAI_API_KEY=*** OPENAI_BASE_URL=https://api.deepseek.com \
  EVOLUTION_MODEL=deepseek-chat python demo.py
```

## Demo Output

```
============================================================
  Self-Evolving Agent — Demo Run
============================================================
Seeded 3 experiences.

Graph: 8 nodes, running one evolution cycle...

------------------------------------------------------------
RESULTS
------------------------------------------------------------
Phase: done
Experiences: 3
Skills extracted: 1
  → debug-a-fastapi-endpoint-retur: 3 steps, 2 pitfalls
Policy variants tested: 2
Best: B — Fast iteration (4 steps vs 7 for methodical)
  Success: True, Quality: 8/10
Human approval: not required ✓

Skills in store: 2
  • debug-a-fastapi-endpoint-retur (rate=1.0)
  • strategy-b (rate=0.7)
============================================================
  Demo complete.
============================================================
```

## Project Structure

```
src/
  state.py         EvolutionState (TypedDict) + Pydantic models
  graph.py         LangGraph StateGraph — 8 nodes, phase-based router
  llm.py           LLM client (real API + mock mode)
  nodes/
    collect.py     collect_experience
    extract.py     extract_skills
    explore.py     explore_policies + run_variant
    evaluate.py    evaluate_results + degradation detection
    assimilate.py  assimilate_best → persistent store
    human.py       human_review (interrupt gate)
  memory/
    store.py       JSON-backed persistent skill/experience store
demo.py            One-cycle demo with seeded experiences
```

## Research Basis

| Paper | Mechanism | In This Code |
|-------|-----------|--------------|
| **APEX** (2605.21240) | Policy exploration | `explore_policies` + `run_variant` |
| **EvoDS** (2606.03841) | Skill extraction | `extract_skills` — LLM-driven distillation |
| **SOLAR** (2605.20189) | Lifelong learning | Cyclic graph design |
| **ANCHOR** (2606.06114) | Human-in-the-loop | `human_review` interrupt node |
| **PEAM** (2605.27762) | Experience absorption | `assimilate_best` — persistent skill store |
| **Forgetting** (2605.09315) | Anti-degradation | Degradation detection in `evaluate_results` |
| **AEL** (2604.21725) | Open-ended adaptation | Strategy variant fan-out |
| **SimWorld** (2605.09423) | Self-testing | Policy variants simulate task execution |
| **EDA Tools** (2604.15082) | Multi-agent | Architecture ready for parallel execution |

## Key LangGraph Features

- **StateGraph** with typed `EvolutionState`
- **Conditional edges** — phase-based central router
- **MemorySaver** checkpointer — enables `interrupt` + state persistence
- **Pydantic models** — `Experience`, `Skill`, `PolicyResult`, `TournamentResult`
- **Mock LLM** — fast local testing without API calls

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Roadmap

- [ ] Real sub-agent spawning (delegate_task / subprocess)
- [ ] LangSmith tracing for graph visualization
- [ ] Multi-profile tournament mode (parallel agent competition)
- [ ] Web dashboard for evolution metrics

## License

MIT
