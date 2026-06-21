"""
evaluate_results node — compare variants, pick winner, detect degradation.
Inspired by APEX selection + Forgetting paper (arXiv:2605.09315).

This node closes the evolution loop: every variant's outcome is written back
into strategy memory (store.record_strategy), so the winner this cycle becomes
the proven "champion" that explore_policies re-enters next cycle. Selection is
a deterministic heuristic first, with an LLM-as-judge that arbitrates only when
the top two are within a hair of each other — and gives the reason/quality.
"""
from __future__ import annotations

from src.json_parser import parse_json
from src.llm import get_llm
from src.memory.store import get_store
from src.state import EvolutionState


def _heuristic_score(v: dict) -> float:
    s = 100 if v.get("success") else 0
    s += max(0, 20 - v.get("steps", 0))
    s += max(0, 10 - len(v.get("errors", [])) * 3)
    return s


def _judge(variants: list[dict]) -> dict:
    """LLM-as-judge: compare variants head-to-head. Returns {winner, reason, quality}."""
    lines = "\n".join(
        f'{v.get("strategy_id")}: {v.get("strategy_desc", "")} '
        f'| success={v.get("success")} steps={v.get("steps")} errors={len(v.get("errors", []))} '
        f'| {str(v.get("output_summary", ""))[:120]}'
        for v in variants
    )
    prompt = (
        "Compare these strategy variants and pick the single best one for "
        "correctness and efficiency.\n"
        f"{lines}\n\n"
        'Return JSON: {"winner": "<id>", "reason": "<short why>", "quality": <1-10>}'
    )
    try:
        parsed = parse_json(str(get_llm(max_tokens=200).invoke(prompt).content))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def evaluate_results(state: EvolutionState) -> dict:
    """Evaluate policy variants, pick a winner, and feed outcomes back to memory."""
    store = get_store()
    variants = state.get("policy_variants", [])
    skills = state.get("skills", [])

    best_policy = None
    degraded_skills = []

    # ── Policy evaluation ──────────────────────────────────────
    if variants:
        variants.sort(key=_heuristic_score, reverse=True)
        best_policy = variants[0]

        # LLM-as-judge: comparative reasoning + quality, and a tie-break when
        # the heuristic can't separate the top two.
        if len(variants) >= 2:
            verdict = _judge(variants[:3])
            chosen = next(
                (v for v in variants if str(v.get("strategy_id")) == str(verdict.get("winner"))),
                None,
            )
            margin = _heuristic_score(variants[0]) - _heuristic_score(variants[1])
            if chosen is not None and margin <= 5:
                best_policy = chosen
            best_policy["judge_reason"] = verdict.get("reason", "")
            best_policy["quality_score"] = verdict.get("quality", 7)
        else:
            best_policy["quality_score"] = 7

        best_policy["suggest_skill_update"] = best_policy.get("quality_score", 7) >= 7

        # ── Close the loop: record every variant's outcome ─────
        # The winner gets a `won` mark; over cycles this lifts proven
        # strategies' success_rate so explore_policies re-enters them.
        for v in variants:
            store.record_strategy(
                desc=v.get("strategy_desc", ""),
                domain=v.get("domain", ""),
                success=bool(v.get("success")),
                won=(v is best_policy),
            )

    # ── Degradation detection ──────────────────────────────────
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=7)
    for sk in skills:
        last_used = sk.get("last_used", "")
        if last_used:
            try:
                if datetime.fromisoformat(last_used) < cutoff and sk.get("success_rate", 1.0) < 0.8:
                    degraded_skills.append(sk)
            except (ValueError, TypeError):
                pass

    requires_approval = (
        best_policy is not None
        and best_policy.get("suggest_skill_update")
        and best_policy.get("quality_score", 10) < 8
    )

    return {
        "best_policy": best_policy,
        "degraded_skills": degraded_skills,
        "human_approval_required": requires_approval,
        "phase": "human" if requires_approval else "assimilate",
    }
