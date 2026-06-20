# Self-Evolving Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![LangGraph](https://img.shields.io/badge/langgraph-1.2+-green.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-28%20passed-brightgreen.svg)](.)

An autonomous self-evolving LLM agent built on **LangGraph**. The agent collects experience from completed tasks, extracts reusable skills, explores alternative strategies, evaluates outcomes, and assimilates the best patterns — forming a closed evolutionary loop.

> Built on research from 9 arXiv papers (2026): APEX, EvoDS, SOLAR, ANCHOR, PEAM, AEL, SimWorld Studio, and more.

## Architecture

```
           ┌──────────────────────────────────┐
           │        collect_experience         │
           │   load sessions → classify        │
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
           └──────────────┬───────────────────┘
                          │ phase=run_variant
           ┌──────────────▼───────────────────┐
           │  run_variant (×2, sequential)     │
           │  execute each strategy            │
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

# Mock mode — no API key needed, runs instantly
EVOLUTION_MOCK=true python demo.py
```

**With a real LLM** (OpenAI-compatible API):

```bash
OPENAI_API_KEY=*** OPENAI_BASE_URL=https://api.deepseek.com \
  EVOLUTION_MODEL=deepseek-chat python demo.py
```

**Continuous loop:**

```bash
EVOLUTION_MOCK=true python demo.py --loop
# One cycle every 5 minutes. Ctrl+C to stop.
```

**Real subprocess execution:**

```bash
EXECUTOR_BACKEND=subprocess python demo.py
# Strategies run real bash commands instead of simulating
```

**Read sessions from a JSONL file:**

```bash
SESSION_SOURCE=file python demo.py
# Reads from ~/.self-evolving-agent/sessions.jsonl
```

## Demo Output

```
============================================================
  Self-Evolving Agent — Single Cycle
============================================================

────────────────────────────────────────────────────────────
  Cycle 0 complete (0.0s)
────────────────────────────────────────────────────────────
  Phase:          done
  Experiences:    3
  Skills created: 1
    → debug-fastapi-500-error: 3 steps
  Variants:       2
  Best strategy:  B — Fast iteration (4 steps vs 7)
    Success: True, Quality: 8/10
  Human review:   not needed
  Total skills:   2
```

## Project Structure

```
src/
  state.py           EvolutionState (TypedDict) + Pydantic models
  graph.py           LangGraph StateGraph — 8 nodes, phase-based router
  llm.py             LLM client (real API + mock mode)
  executor.py        TaskExecutor: Mock, Subprocess (bash/python)
  session_source.py  SessionSource: Mock, File, SQLite, Watch
  github_exporter.py GitHub auto-commit + push for evolved skills
  nodes/
    collect.py       collect_experience
    extract.py       extract_skills
    explore.py       explore_policies + run_variant (parallel support)
    evaluate.py      evaluate_results + degradation detection
    assimilate.py    assimilate_best → persistent store + GitHub export
    human.py         human_review (LangGraph interrupt)
  memory/
    store.py         JSON-backed persistent skill/experience store
demo.py              Single cycle or continuous loop demo
dashboard.py         FastAPI web dashboard (http://localhost:8080)
```

## Pluggable Backends

### Executors (how tasks are run)

| Backend | Env var | Description |
|---------|---------|-------------|
| `mock` | (default) | LLM simulates execution — fast, no side effects |
| `subprocess` | `EXECUTOR_BACKEND=subprocess` | Real bash commands |
| `python` | `EXECUTOR_BACKEND=python` | Real Python scripts |

### Session Sources (where experience comes from)

| Backend | Env var | Description |
|---------|---------|-------------|
| `mock` | (default) | Seeded in-memory data |
| `file` | `SESSION_SOURCE=file` | JSONL file (`~/.self-evolving-agent/sessions.jsonl`) |
| `sqlite` | `SESSION_SOURCE=sqlite` | Any SQLite DB with sessions table |
| `watch` | `SESSION_SOURCE=watch` | Watches directory for incoming JSON files |

### LLMs

| Mode | Env var | Description |
|------|---------|-------------|
| Mock | `EVOLUTION_MOCK=true` | Deterministic, no API key |
| OpenAI-compatible | `OPENAI_API_KEY` + `OPENAI_BASE_URL` | Any OpenAI-compatible API |

### GitHub Export

Set `GITHUB_REPO_PATH=~/my-skills-repo` to auto-commit evolved skills as Markdown files.

### Web Dashboard

```bash
pip install -e ".[dashboard]"
python dashboard.py
# → http://localhost:8080
```

## Research Basis

| Paper | Mechanism | In This Code |
|-------|-----------|--------------|
| **APEX** (2605.21240) | Policy exploration | `explore_policies` + `run_variant` |
| **EvoDS** (2606.03841) | Skill extraction | `extract_skills` — LLM-driven distillation |
| **SOLAR** (2605.20189) | Lifelong learning | Cyclic graph + continuous loop mode |
| **ANCHOR** (2606.06114) | Human-in-the-loop | `human_review` with `interrupt()` |
| **PEAM** (2605.27762) | Experience absorption | `assimilate_best` — persistent skill store |
| **Forgetting** (2605.09315) | Anti-degradation | Degradation detection in `evaluate_results` |
| **AEL** (2604.21725) | Open-ended adaptation | Strategy variant fan-out |
| **SimWorld** (2605.09423) | Self-testing | Policy variants simulate task execution |
| **EDA Tools** (2604.15082) | Multi-agent | Architecture ready for parallel Send API |

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
# 28 tests, all passing
```

## Key LangGraph Features

- **StateGraph** with typed `EvolutionState`
- **Conditional edges** — phase-based central router
- **MemorySaver** checkpointer — enables `interrupt` + state persistence
- **Pydantic models** — `Experience`, `Skill`, `PolicyResult`
- **Mock LLM** — fast local testing without API calls
- **Pluggable backends** — swap executors and session sources via env vars

## Roadmap

- [x] Mock LLM for fast testing
- [x] Real OpenAI-compatible API support
- [x] Subprocess executor (bash/python)
- [x] SQLite + Watch session sources
- [x] GitHub auto-export of evolved skills
- [x] FastAPI web dashboard
- [x] Continuous loop mode
- [x] Parallel strategy execution
- [x] Human-in-the-loop via LangGraph interrupt
- [ ] LangSmith tracing for graph visualization
- [ ] Streaming output mode

## License

MIT
