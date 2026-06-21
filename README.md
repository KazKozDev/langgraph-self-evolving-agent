# self-evolving-agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![LangGraph](https://img.shields.io/badge/langgraph-1.2+-green.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-67%20passed-brightgreen.svg)](.)

**A self-improving LLM agent that learns from its own experience, writes and tests its own tools, and measurably gets better at tasks over time — running 100% locally, no API key, on a real LangGraph state machine.** A working take on one of the hardest open problems in agents: *evolution without retraining.*

A small agent that gets a little better every time you use it — without ever touching the model weights.

The weights are frozen. What changes is everything *around* the model: a memory of which strategies have actually worked, a growing box of tools it wrote and tested itself, and a library of distilled skills. You give it a task, it tries a couple of approaches, runs them for real, keeps score, and remembers. Next time something similar shows up, it reaches for what won last time. That's the whole idea.

It runs entirely on your laptop against a local Ollama model. No API key, nothing leaves the machine.

## The one mental model to keep

Most agents start every task from a blank slate. This one doesn't. Concretely, each task goes through a loop:

```
your task
   │
   ▼
 classify domain        ← coding? research? writing? (auto, from the text)
   │
   ▼
 maybe write a tool     ← if a small reusable helper would help, write it + a test,
   │                       run the test, keep it only if it passes
   ▼
 design 2 strategies    ← one fresh idea from the LLM, plus the champion that won
   │                       last time for this kind of task (explore + exploit)
   ▼
 run both for real      ← actually generate + execute code / search the web / etc.
   │
   ▼
 judge → pick a winner  ← heuristic score + an LLM-as-judge
   │
   ▼
 remember everything    ← every strategy's win/loss goes back into memory (EMA),
                          so good ones rise and stale ones fade
```

The punchline: the loop is *not* a fixed script. Strategies are generated and selected from accumulated performance, so the agent's behavior drifts toward what actually works. Watch `/strategies` over a session and you'll see one approach climb to the top and start getting re-picked. That climb is the whole point.

It's built on [LangGraph](https://github.com/langchain-ai/langgraph) — a real `StateGraph`, typed state, conditional edges, a checkpointer, and a `human_review` node that can pause the graph mid-run via `interrupt()`.

## Quickstart

```bash
git clone https://github.com/YOU/self-evolving-agent.git
cd self-evolving-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

You have a local Ollama? Just talk to it:

```bash
python demo.py --chat --provider ollama
```

```
[auto] you ▸ write a function that checks if a number is prime, with tests
  · domain: coding (auto-detected)
  · designing strategies…
  · executing strategy…
  · judging results…
  ▶ Winner: Fast iteration — success=True, output: SUCCESS: prime checker
  Skills: 7 | strategies: 6 | tools: 1
```

No model at all? Everything still runs in a deterministic mock:

```bash
EVOLUTION_MOCK=true python demo.py --chat
```

On a Mac you can also just **double-click `start_chat.command`** — it pops a Terminal, lets you pick a model, and drops you into the chat.

## Talking to it

Inside `--chat`, anything you type is treated as a task and run through the full loop. A few slash-commands let you peek and steer:

```
/ask <question>     just answer me (no machinery, streamed token-by-token)
/domain coding      pin the domain   ·   /domain auto   let it detect again
/tools              the tools it has (built-in + self-written)
/skills             distilled skills
/strategies         strategies with their success_rate / wins / plays
/synth on|off       toggle tool synthesis
/quit
```

You usually don't pass `--domain` — it's inferred from the task text and routed to the matching executor.

## What it can actually do

I want to be honest about where the "for real" stops, because it varies by domain:

| domain | what happens | real? |
|--------|--------------|-------|
| `coding` | writes Python, **runs it**, reads the error, fixes it (up to 3 tries) | yes — you get working code |
| `research` | DuckDuckGo search → reads pages → synthesizes | yes — it hits the internet¹ |
| `analysis` | computes / processes data via code | yes |
| `writing`, `planning` | drafts text / structured plans | yes — model output |
| `general` | plain reasoning | yes, no tools |

¹ Out of the box, `research` uses the built-in DuckDuckGo `search`/`fetch` in `webtools.py`. There's an optional `[research]` extra that swaps in a heavier RAG pipeline (`pip install -e ".[research]"`, pulled from git) — if it's not installed, it just falls back to the basic tools.

It also ships with **built-in file tools** (`read_file`, `write_file`, `list_dir`) confined to a workspace dir (`AGENT_WORKSPACE`, default `./agent_workspace`). Generated code can `import` them. Path traversal out of the workspace is rejected.

And here's the part I like most:

## It writes its own tools

Beyond learning *which strategy* works, the agent can grow *new capabilities*. When a task could use a small reusable helper, the `synthesize_tools` node:

1. asks the model to write the function **plus a test**,
2. runs the test in a throwaway sandbox,
3. saves it **only if the test passes**,
4. registers it (with a `success_rate` that decays if it gets flaky),
5. injects the tool catalog into the executor's prompt and puts the tools dir on `PYTHONPATH` — so the *next* task can just import and reuse it.

```bash
python demo.py --task "constrain a sensor reading to a safe range" --domain coding
#   🔧 synthesized + verified new tool: clamp(x, lo, hi)
python demo.py --list-tools
```

The test is the gate. A tool that can't pass its own test never gets saved, so the toolbox stays trustworthy instead of filling up with plausible-looking garbage.

## Why this is more than a wrapper

The interesting bit is the closed loop, so let me spell out the mechanism:

1. **Strategies are generated, not hardcoded.** Each cycle the model proposes fresh approaches for *this* task, and it's told what's already been tried (with track records) so it doesn't just repeat itself.
2. **Outcomes are written back.** `evaluate_results` records every variant's win/loss into a persistent strategy memory — an exponential moving average per strategy, so recent results matter more.
3. **Winners defend their title.** Next time, the best strategy for that domain re-enters as a "champion" challenger alongside the new ideas. Keep winning → keep getting picked. Start losing → the EMA quietly demotes you. That last part is the anti-forgetting bit.

Same EMA idea applies to skills and tools. Nothing here updates a single weight — it's all memory and selection.

## Run it other ways

```bash
# one task, then exit (full machinery, with live progress)
python demo.py --task "build a CSV parser with tests"

# real bash execution, no model needed (planning falls back to mock)
EXECUTOR_BACKEND=subprocess python demo.py --task "print uptime and disk usage" --domain general

# a hosted OpenAI-compatible API instead of Ollama
OPENAI_API_KEY=*** OPENAI_BASE_URL=https://api.deepseek.com \
  python demo.py --provider openai --model deepseek-chat --task "..."

# background loop: keep evolving off a stream of past sessions
EVOLUTION_MOCK=true python demo.py --loop
```

### Feeding it past experience

The `--loop` mode is the other half of the story: instead of you typing tasks, the agent chews on a stream of *already-completed* sessions, distills skills, and evolves strategies in the background. Where that stream comes from is pluggable (`SESSION_SOURCE`): an in-memory mock, a JSONL file, any SQLite DB, or a watched directory. `submit.py` is the front door for the watched-directory flow:

```bash
python submit.py "Write a REST API for user avatars"
python submit.py --goal "Fix login bug" --domain debugging --result failure
```

Each submission drops a JSON record into `~/.self-evolving-agent/incoming/`, which the watch source picks up on the next cycle.

### Picking a model

```bash
python demo.py --list-models                 # what's installed (MLX builds flagged)
python demo.py --chat --provider ollama --model gemma4:12b-mlx
```

`--model` takes a full name or a substring (`26b-mlx` → `gemma4:26b-mlx`). Omit it on Ollama and you get an interactive picker. The default is `gemma4:26b-mlx`.

> A note on speed: a single task fires *several* sequential model calls (classify → synthesize+test → design 2 strategies → run each → judge → distill). On a 26B model that's easily a couple of minutes. If it feels stuck, it isn't — watch the `·` progress lines. For snappy iteration, use a small model like `llama3.2:3b` or `gemma4:12b-mlx`.

## Watch it learn

```bash
pip install -e ".[dashboard]"
python dashboard.py     # → http://localhost:8080
```

The dashboard has a **learning curve** — average strategy success rate over time — plus live skills, tools, and a button to trigger a cycle. The curve going up is the closest thing to proof that the loop is doing something.

Everything persists in one JSON file under `~/.self-evolving-agent/`, so memory survives restarts. If you point `GITHUB_REPO_PATH` at a repo, evolved skills also get written out as markdown and committed — a human-readable trail of what it learned.

## Where the bodies are buried

So you're not surprised:

- It is **not** an operator of your machine. It can only touch files it writes inside the sandbox, and run code it generates. No "deploy this," no logging into your accounts.
- Each chat message is a *task*, not a conversation turn. Say "hi" and it'll dutifully try to solve "hi" as a task. (Use `/ask` for actual chat.)
- Quality is bounded by a **local** model. Gemma/Qwen are good, but they're not GPT-4. A 3B model will sometimes return junk JSON and fall back to defaults — that's a model-quality issue, not a bug in the loop.
- The sandbox is a subprocess with a timeout, not real isolation. Don't point `coding` at hostile prompts and walk away.

## Layout

This is the whole thing — ~4.7k lines of Python, no hidden magic:

```
src/
  state.py             EvolutionState (typed) + Pydantic models (Experience, Skill, ...)
  graph.py             the LangGraph StateGraph + phase router (8 nodes)
  llm.py               mock | openai | ollama — auto-detect, model listing, streaming
  domain_classifier.py infer the domain from the task text
  json_parser.py       coax JSON out of models that don't quite return JSON
  tool_synthesis.py    write → test → register a new tool
  executor.py          Mock / Subprocess (bash/python) executors
  code_executor.py     generate → run → self-repair Python (the coding workhorse)
  domain_executors.py  per-domain executors: Coding/Research/Analysis/Writing/Planning/General
  webtools.py          DuckDuckGo search() + fetch() — internet for the research executor
  session_source.py    where past experience comes from: mock / file / sqlite / watch
  github_exporter.py   write evolved skills out as markdown + git commit/push
  nodes/               collect · extract · synthesize · explore (+run_variant) · evaluate · human · assimilate
  memory/store.py      one JSON file: skills, experiences, strategies, tools, history, metrics
  tools/
    registry.py        load/list/register self-written tools + build the prompt catalog
    builtins.py        sandboxed file tools (read_file/write_file/list_dir)
demo.py                chat / single task / loop — the thing you actually run
submit.py              push tasks into the agent's queue (for the watch/loop workflow)
dashboard.py           FastAPI dashboard with the learning curve
start_chat.command     double-click launcher (macOS)
tests/                 13 files, mock paths throughout
```

## Tests

```bash
pytest tests/ -v        # 67 passing
```

Everything has a mock path, so the whole suite runs in a few seconds with no model and no network.

## Where the ideas come from

I leaned on a handful of 2026 papers on self-evolving agents. The mapping to code, honestly:

| paper | idea | here |
|-------|------|------|
| [APEX](https://arxiv.org/abs/2605.21240) | explore/exploit over a strategy space | `explore_policies` + strategy memory |
| [EvoDS](https://arxiv.org/abs/2606.03841) | distilling skills from experience | `extract_skills` |
| [SOLAR](https://arxiv.org/abs/2605.20189) | lifelong learning | cyclic graph + `--loop` |
| [ANCHOR](https://arxiv.org/abs/2606.06114) | human-in-the-loop | `human_review` via `interrupt()` |
| [PEAM](https://arxiv.org/abs/2605.27762) | absorbing experience | `assimilate_best` |
| [Forgetting](https://arxiv.org/abs/2605.09315) | anti-degradation | EMA `success_rate` on skills/strategies/tools |
| [AEL](https://arxiv.org/abs/2604.21725) | open-ended adaptation | strategy fan-out |

These are inspirations, not reimplementations — the spirit is faithful, the code is my own and much simpler.

## If you want to actually read them

The papers, in the order I'd read them. Start with APEX — it's the one whose explore/exploit framing maps most directly onto what's in here. The rest are good for the surrounding intuitions (how to distill skills, how to not forget, where the human goes).

- **APEX** — Autonomous Policy Exploration for Self-Evolving LLM Agents · https://arxiv.org/abs/2605.21240
- **EvoDS** — skill distillation from experience · https://arxiv.org/abs/2606.03841
- **SOLAR** — lifelong learning · https://arxiv.org/abs/2605.20189
- **ANCHOR** — human-in-the-loop for agents · https://arxiv.org/abs/2606.06114
- **PEAM** — experience absorption · https://arxiv.org/abs/2605.27762
- **Forgetting** — anti-degradation in evolving agents · https://arxiv.org/abs/2605.09315
- **AEL** — open-ended adaptation · https://arxiv.org/abs/2604.21725

If a link 404s, the arXiv id is right there — paste it into the search box. (And if I've mischaracterized any of these, that's on me, not the authors — read the abstract, not my one-liner.)

## License

MIT. Have fun with it.
