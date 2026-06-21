"""Demo runner — self-evolving agent on LangGraph.

Usage:
  EVOLUTION_MOCK=true python demo.py              # single cycle, mock LLM
  EVOLUTION_MOCK=true python demo.py --loop       # continuous loop
  SESSION_SOURCE=file python demo.py              # read from JSONL file
  EXECUTOR_BACKEND=subprocess python demo.py      # real subprocess execution
  EXECUTOR_BACKEND=python python demo.py          # real Python execution

Drive it with ANY live task (runs the full machinery on YOUR goal):
  python demo.py --task "Build a CSV parser with tests" --domain coding
  python demo.py --task "Research the best vector DB for RAG" --domain research

  For REAL execution (not simulated), give it a real LLM, e.g.:
    OPENAI_API_KEY=*** OPENAI_BASE_URL=https://api.deepseek.com \
      EVOLUTION_MODEL=deepseek-chat python demo.py --task "..." --domain coding
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from src.graph import get_graph
from src.memory.store import get_store


def _blank_state(cycle_num: int) -> dict:
    """A fresh EvolutionState with all channels initialised."""
    return {
        "messages": [],
        "experiences": [],
        "new_experiences_count": 0,
        "skills": [],
        "extracted_skills": [],
        "degraded_skills": [],
        "synthesized_tools": [],
        "policy_variants": [],
        "variant_index": 0,
        "best_policy": None,
        "tournament_results": None,
        "task_goal": "",
        "task_domain": "",
        "cycle": cycle_num,
        "phase": "collect",
        "human_approval_required": False,
        "human_decision": "",
        "total_skills_created": 0,
        "total_improvements": 0,
        "error": None,
    }


def seed_experiences():
    """Seed sample experiences for demo mode."""
    store = get_store()
    samples = [
        {
            "session_id": "demo-001",
            "goal": "Debug a FastAPI endpoint returning 500 on POST /users",
            "domain": "debugging",
            "tool_calls": 5,
            "errors": ["missing await on async call"],
            "result": "success",
            "key_pattern": "add_logging_first",
        },
        {
            "session_id": "demo-002",
            "goal": "Create a CI/CD pipeline with GitHub Actions",
            "domain": "deployment",
            "tool_calls": 8,
            "errors": ["invalid workflow syntax"],
            "result": "success",
            "key_pattern": "validate_schema_before_push",
        },
        {
            "session_id": "demo-003",
            "goal": "Write unit tests for an async payment module",
            "domain": "coding",
            "tool_calls": 12,
            "errors": ["mock not configured", "race condition"],
            "result": "partial",
            "key_pattern": "",
        },
    ]
    for exp in samples:
        store.add_experience(exp)


def run_one_cycle(cycle_num: int = 0) -> dict:
    """Run one evolution cycle over historical experience."""
    graph = get_graph()
    initial = _blank_state(cycle_num)
    config = {"configurable": {"thread_id": f"cycle-{cycle_num}"}}
    return graph.invoke(initial, config)


_NODE_LABELS = {
    "collect_experience": "collecting experience",
    "extract_skills": "extracting skills",
    "synthesize_tools": "synthesizing a tool",
    "explore_policies": "designing strategies",
    "run_variant": "executing strategy",
    "evaluate_results": "judging results",
    "human_review": "human review",
    "assimilate_best": "learning",
}


def run_task(goal: str, domain: str = "coding", cycle_num: int = 0,
             progress: bool = False) -> dict:
    """Run the full machinery against a single live task you supply.

    When `progress`, stream node-by-node updates so the user sees live activity
    instead of a silent multi-second wait.
    """
    graph = get_graph()

    # Auto-detect the domain from the task text unless one was pinned.
    if domain in (None, "", "auto"):
        from src.domain_classifier import classify_domain
        domain = classify_domain(goal)
        if progress:
            print(f"  · domain: {domain} (auto-detected)", flush=True)

    initial = _blank_state(cycle_num)
    initial["task_goal"] = goal
    initial["task_domain"] = domain
    config = {"configurable": {"thread_id": f"task-{int(time.time())}"}}

    if not progress:
        return graph.invoke(initial, config)

    # Seed with the input channels (stream yields only node deltas).
    final: dict = {"task_goal": goal, "task_domain": domain}
    last = None
    for update in graph.stream(initial, config):
        for node, delta in update.items():
            if node != last:
                print(f"  · {_NODE_LABELS.get(node, node)}…", flush=True)
                last = node
            if delta:
                final.update(delta)
    return final


def print_results(final: dict, cycle_num: int, elapsed: float):
    """Pretty-print cycle results."""
    print(f"\n{'─' * 60}")
    print(f"  Cycle {cycle_num} complete ({elapsed:.1f}s)")
    print(f"{'─' * 60}")
    print(f"  Phase:          {final.get('phase')}")
    print(f"  Experiences:    {final.get('new_experiences_count', 0)}")
    print(f"  Skills created: {len(final.get('extracted_skills', []))}")
    for sk in final.get("extracted_skills", []):
        print(f"    → {sk.get('name')}: {len(sk.get('steps', []))} steps")
    print(f"  Variants:       {len(final.get('policy_variants', []))}")
    if final.get("best_policy"):
        bp = final["best_policy"]
        print(f"  Best strategy:  {bp.get('strategy_id')} — {bp.get('strategy_desc', '')}")
        print(f"    Success: {bp.get('success')}, Steps: {bp.get('steps')}, "
              f"Quality: {bp.get('quality_score', '?')}/10")
    print(f"  Human review:   {'required' if final.get('human_approval_required') else 'not needed'}")
    print(f"  Total skills:   {len(get_store().get_skills())}")


def print_task_results(final: dict, goal: str, domain: str, elapsed: float):
    """Pretty-print the outcome of a single live task run."""
    print(f"\n{'─' * 60}")
    print(f"  Task complete ({elapsed:.1f}s)")
    print(f"{'─' * 60}")
    print(f"  Goal:    {goal}")
    print(f"  Domain:  {domain}")
    new_tools = final.get("synthesized_tools", [])
    if new_tools:
        print(f"\n  🔧 New tools written this run ({len(new_tools)}):")
        for t in new_tools:
            print(f"    + {t.get('signature')} — {t.get('description', '')}")
    variants = final.get("policy_variants", [])
    print(f"\n  Strategies tried ({len(variants)}):")
    for v in variants:
        tag = "exploit/champion" if v.get("origin") == "exploit" else "explore/new"
        mark = "✓" if v.get("success") else "✗"
        print(f"    [{v.get('strategy_id')}] {mark} ({tag}) {v.get('strategy_desc', '')[:70]}")
    bp = final.get("best_policy")
    if bp:
        print(f"\n  ▶ Winner: [{bp.get('strategy_id')}] {bp.get('strategy_desc', '')}")
        print(f"    success={bp.get('success')} steps={bp.get('steps')} "
              f"quality={bp.get('quality_score', '?')}/10")
        if bp.get("judge_reason"):
            print(f"    judge: {bp['judge_reason']}")
        if bp.get("output_summary"):
            print(f"    output: {str(bp['output_summary'])[:300]}")
        for art in bp.get("artifacts", []):
            print(f"    artifact: {art}")
    print(f"\n  Human review:   {'required' if final.get('human_approval_required') else 'not needed'}")
    store = get_store()
    print(f"  Skills: {len(store.get_skills())} | "
          f"strategies: {len(store.get_strategies())} | "
          f"tools: {len(store.get_tools())}  (see: python demo.py --list-tools)")


_CHAT_HELP = """\
Commands:
  /help                 show this help
  /ask <question>       plain conversational answer (no machinery)
  /domain <name>        pin domain (coding, research, ...) or 'auto' to detect
  /tools                list built-in + self-written tools
  /skills               list learned skills
  /strategies           list remembered strategies (with success_rate)
  /synth on|off         toggle tool synthesis
  /quit                 exit
Anything else is treated as a task: the agent designs strategies, executes,
judges, and learns — memory carries across turns."""


def _ask(question: str, history: list[dict]) -> str:
    """Stream a conversational answer from the LLM, with short rolling context."""
    from src.llm import stream_llm
    convo = "".join(f"User: {h['q']}\nAssistant: {h['a']}\n" for h in history[-4:])
    prompt = (
        "You are a helpful assistant. Answer concisely.\n"
        f"{convo}User: {question}\nAssistant:"
    )
    print("\nagent ▸ ", end="", flush=True)
    parts = []
    for chunk in stream_llm(prompt, max_tokens=600):
        parts.append(chunk)
        print(chunk, end="", flush=True)
    print()
    return "".join(parts).strip()


def _show_memory(kind: str):
    store = get_store()
    if kind == "tools":
        items = store.get_tools()
        if not items:
            print("  (no tools yet)")
        for t in items:
            print(f"  {t['signature']:<30} sr={t.get('success_rate', 1.0):.2f} "
                  f"used={t.get('use_count', 0)} — {t.get('description', '')}")
    elif kind == "skills":
        items = store.get_skills()
        if not items:
            print("  (no skills yet)")
        for s in items:
            print(f"  {s.get('name'):<34} steps={len(s.get('steps', []))} "
                  f"sr={s.get('success_rate', 1.0):.2f}")
    elif kind == "strategies":
        items = sorted(store.get_strategies(), key=lambda s: -s.get("success_rate", 0))
        if not items:
            print("  (no strategies yet)")
        for s in items:
            print(f"  sr={s.get('success_rate', 0):.2f} plays={s.get('plays', 0)} "
                  f"wins={s.get('wins', 0)}  {s.get('desc', '')[:60]}")


def interactive_chat(default_domain: str = "auto"):
    """REPL: chat with the agent — each message runs the full machinery."""
    domain = default_domain
    print("=" * 60)
    print("  Self-Evolving Agent — Interactive Chat")
    print("=" * 60)
    synth = os.getenv("TOOL_SYNTHESIS", "").lower() in ("1", "true", "yes")
    print(f"Domain: {domain}  |  Tool synthesis: {'on' if synth else 'off'}  |  /help for commands")

    ask_history: list[dict] = []
    turn = 0
    while True:
        try:
            line = input(f"\n[{domain}] you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye 👋")
            break
        if not line:
            continue

        if line in ("/quit", "/exit", "quit", "exit"):
            print("bye 👋")
            break
        if line == "/help":
            print(_CHAT_HELP)
            continue
        if line.startswith("/ask"):
            q = line[len("/ask"):].strip()
            if not q:
                print("  usage: /ask <question>")
                continue
            answer = _ask(q, ask_history)  # streams to stdout itself
            ask_history.append({"q": q, "a": answer})
            continue
        if line.startswith("/domain"):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                domain = parts[1].strip()
                print(f"  → domain = {domain}")
            else:
                print(f"  current domain: {domain}")
            continue
        if line in ("/tools", "/skills", "/strategies"):
            _show_memory(line.lstrip("/"))
            continue
        if line.startswith("/synth"):
            val = line.split(maxsplit=1)[-1].strip().lower()
            os.environ["TOOL_SYNTHESIS"] = "true" if val in ("on", "true", "1") else "false"
            print(f"  → tool synthesis = {os.environ['TOOL_SYNTHESIS']}")
            continue
        if line.startswith("/"):
            print(f"  unknown command: {line}  (/help)")
            continue

        # Treat as a task → run the full evolution machinery.
        turn += 1
        t0 = time.time()
        try:
            final = run_task(line, domain=domain, cycle_num=turn, progress=True)
            print_task_results(final, line, final.get("task_domain", domain), time.time() - t0)
        except Exception as e:
            print(f"  ✗ failed: {e}")


def run_loop(interval: int = 60):
    """Continuous evolution loop."""
    print("=" * 60)
    print("  Self-Evolving Agent — Continuous Loop")
    print(f"  Interval: {interval}s | Ctrl+C to stop")
    print("=" * 60)

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n▶ Cycle {cycle} starting...", flush=True)
            t0 = time.time()
            try:
                final = run_one_cycle(cycle)
                print_results(final, cycle, time.time() - t0)
            except Exception as e:
                print(f"  ✗ Cycle {cycle} failed: {e}", flush=True)
            print(f"\n  Sleeping {interval}s...", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n\n  Stopped after {cycle} cycles.")
        print(f"  Final skill count: {len(get_store().get_skills())}")


def _print_ollama_models(models: list[str]):
    if not models:
        print("  (no models found — is Ollama running? try: ollama list)")
        return
    for i, m in enumerate(models, 1):
        tag = "  ← MLX" if m.endswith("-mlx") else ""
        print(f"  {i:2}. {m}{tag}")


def select_ollama_model(preselect: str | None) -> str | None:
    """Resolve --model against installed Ollama models, prompting if needed."""
    from src.llm import DEFAULT_OLLAMA_MODEL, list_ollama_models
    models = list_ollama_models()
    if not models:
        return preselect  # can't list — trust whatever was passed

    # Default = the configured default if installed, else the first model.
    default = DEFAULT_OLLAMA_MODEL if DEFAULT_OLLAMA_MODEL in models else models[0]

    if preselect:
        if preselect in models:
            return preselect
        matches = [m for m in models if preselect.lower() in m.lower()]
        if len(matches) == 1:
            print(f"Model: '{preselect}' → '{matches[0]}'")
            return matches[0]
        if len(matches) > 1:
            print(f"'{preselect}' matches several models:")
            _print_ollama_models(matches)
            models = matches  # narrow the menu
            default = models[0]
        else:
            print(f"⚠  '{preselect}' is not installed.")

    # Interactive pick (or the default when not a TTY).
    if not sys.stdin.isatty():
        print(f"Non-interactive → using '{default}'.")
        return default

    print("\nInstalled Ollama models:")
    _print_ollama_models(models)
    raw = input(f"\nPick a model [number or name, Enter = {default}]: ").strip()
    if not raw:
        return default
    if raw.isdigit() and 1 <= int(raw) <= len(models):
        return models[int(raw) - 1]
    exact = [m for m in models if m == raw] or [m for m in models if raw.lower() in m.lower()]
    if exact:
        return exact[0]
    print(f"⚠  '{raw}' not recognised — using '{default}'.")
    return default


def main():
    parser = argparse.ArgumentParser(description="Self-Evolving Agent on LangGraph")
    parser.add_argument("--task", metavar="GOAL",
                        help="Run the full machinery against this live goal")
    parser.add_argument("--domain", default="auto",
                        help="Task domain: auto (detect from text) | coding | debugging | "
                             "research | writing | analysis | planning | general (default: auto)")
    parser.add_argument("--loop", action="store_true", help="Continuous evolution loop")
    parser.add_argument("--chat", action="store_true",
                        help="Interactive chat REPL — give the agent tasks one by one")
    parser.add_argument("--provider", choices=["auto", "mock", "openai", "ollama"],
                        help="LLM provider (default: auto-detect)")
    parser.add_argument("--model", help="Model name or substring (e.g. gemma4:12b-mlx, llama3.2). "
                                        "For Ollama, prompts from installed models if omitted/ambiguous.")
    parser.add_argument("--base-url", dest="base_url",
                        help="Override API base URL (OpenAI-compatible or Ollama)")
    parser.add_argument("--list-models", action="store_true",
                        help="List installed Ollama models and exit")
    parser.add_argument("--list-tools", action="store_true",
                        help="List the agent's self-written tools and exit")
    parser.add_argument("--no-synth", action="store_true",
                        help="Disable tool synthesis in --task mode")
    args = parser.parse_args()

    # ── Provider selection (CLI overrides env) ─────────────────
    if args.provider:
        os.environ["EVOLUTION_PROVIDER"] = args.provider
        if args.provider == "mock":
            os.environ["EVOLUTION_MOCK"] = "true"
    if args.base_url:
        # Route the override to whichever provider is in play.
        if (args.provider == "ollama") or "11434" in args.base_url:
            os.environ["OLLAMA_BASE_URL"] = args.base_url
        else:
            os.environ["OPENAI_BASE_URL"] = args.base_url

    if args.list_models:
        from src.llm import list_ollama_models
        print("Installed Ollama models:")
        _print_ollama_models(list_ollama_models())
        return

    if args.list_tools:
        from src.tools.registry import builtin_tools, list_tools
        bi = builtin_tools()
        print(f"Built-in tools ({len(bi)}):")
        for t in bi:
            print(f"  {t['signature']:<32} — {t['description']}")
        tools = list_tools()
        print(f"\nSelf-written tools ({len(tools)}):")
        for t in tools:
            print(f"  {t['signature']:<32} sr={t.get('success_rate', 1.0):.2f} "
                  f"used={t.get('use_count', 0)}  — {t.get('description', '')}")
        if not tools:
            print("  (none yet — run a --task to let the agent build some)")
        return

    from src.llm import resolve_provider
    provider = resolve_provider()

    # For Ollama, resolve the model against what's actually installed
    # (interactive menu when omitted or ambiguous). MLX models included.
    if provider == "ollama":
        chosen = select_ollama_model(args.model)
        if chosen:
            os.environ["EVOLUTION_MODEL"] = chosen
    elif args.model:
        os.environ["EVOLUTION_MODEL"] = args.model

    model = os.getenv("EVOLUTION_MODEL", "(provider default)")

    loop_mode = args.loop or os.getenv("EVOLUTION_LOOP", "") == "true"
    source = os.getenv("SESSION_SOURCE", "mock")
    executor = os.getenv("EXECUTOR_BACKEND", "mock")

    # ── Interactive chat mode ──────────────────────────────────
    if args.chat:
        if not args.no_synth and "TOOL_SYNTHESIS" not in os.environ:
            os.environ["TOOL_SYNTHESIS"] = "true"
        print(f"Provider: {provider}  |  Model: {model}  |  "
              f"Executor: {os.getenv('EXECUTOR_BACKEND', 'auto')}")
        if provider == "mock":
            print("⚠  Provider = MOCK → responses are simulated. "
                  "Use --provider ollama or set OPENAI_API_KEY for real answers.")
        interactive_chat(default_domain=args.domain)
        return

    # ── Live task mode ─────────────────────────────────────────
    if args.task:
        backend = os.getenv("EXECUTOR_BACKEND", "auto")
        # Tool synthesis on by default for live tasks (unless --no-synth).
        if not args.no_synth and "TOOL_SYNTHESIS" not in os.environ:
            os.environ["TOOL_SYNTHESIS"] = "true"
        synth_on = os.getenv("TOOL_SYNTHESIS", "").lower() in ("1", "true", "yes")
        print("=" * 60)
        print("  Self-Evolving Agent — Live Task")
        print("=" * 60)
        print(f"Provider: {provider}  |  Model: {model}  |  Executor: {backend}")
        print(f"Tool synthesis: {'on' if synth_on else 'off'}")
        if provider == "mock":
            print("⚠  Provider resolved to MOCK → reasoning/execution is SIMULATED.")
            print("   Use --provider ollama (local) or set OPENAI_API_KEY for real work.")
        t0 = time.time()
        final = run_task(args.task, domain=args.domain, progress=True)
        print_task_results(final, args.task, final.get("task_domain", args.domain), time.time() - t0)
        return

    if source == "mock":
        seed_experiences()
        print("Session source: mock (seeded 3 experiences)")
    else:
        print(f"Session source: {source}")

    print(f"Provider: {provider}  |  Model: {model}")
    print(f"Executor: {executor}")
    print(f"Mode: {'continuous loop' if loop_mode else 'single cycle'}")

    if loop_mode:
        interval = int(os.getenv("EVOLUTION_INTERVAL", "300"))
        run_loop(interval=interval)
    else:
        print("=" * 60)
        print("  Self-Evolving Agent — Single Cycle")
        print("=" * 60)
        t0 = time.time()
        final = run_one_cycle(0)
        print_results(final, 0, time.time() - t0)


if __name__ == "__main__":
    main()
