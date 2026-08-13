"""Gate 2.2 + 2.3 — trace-grounded semi-synthetic benchmark.

Real dialogues/candidates/timelines (LongMemEval S + LoCoMo) + controlled
injection of the five mechanisms the reviewer names:

  hitchhiker          - never-needed memory co-exposed with a needed one
  stale version       - pre-update memory needed while a newer version is
                        preferred by the engine
  rare protective     - rare/old protective memory demoted out of reach
  scope shift         - task scope beyond the recorded support
  co-memory competition - workspace crowding around needed memories

For each condition (control + 5 injections) we run REPEATED RANDOMIZATION
COUNTERFACTUALS on the real traces: per memory, R rounds of a randomized
protocol draw (always-in vs always-out regimen) produce the protocol-path
lifecycle estimator V_RCT (the Stage-1-validated truth proxy), while the
engine's natural exposure gives the observational estimator V_obs a naive
deployment would compute from its own logs.  Per-mechanism we then report
how often the observational estimator makes a CONFIDENT SIGN ERROR against
the protocol truth, and how often support failure forces unresolved.

Gate 2.3: the external benchmark's retrieval layer (official LongMemEval
BM25 parameters K1=1.5/B=0.75) runs end-to-end on the real data; the QA
layer is not reproduced offline (needs model endpoints) and is labeled as
such.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from .trace_grounded_runner import (
    Trace, TraceMsg, TraceTask,
    bm25_scores, by_id, clean_tokens,
    engine_workspaces, load_longmemeval_s, load_locomo,
)

# fixed contract (same evaluator semantics as Gate 1, plus the lifecycle
# discount and cost coefficients the review requires)
GAMMA = 0.99
LAMBDA_TOK = 0.001
RHO_DILUTION = 0.35


# ---------------------------------------------------------------------------
# injections — each returns (trace', label, affected task ids)
# ---------------------------------------------------------------------------

def _clone_msg(m: TraceMsg, msg_id: str, date_idx: int) -> TraceMsg:
    return TraceMsg(msg_id=msg_id, session_id=m.session_id, date=m.date,
                    date_idx=date_idx, role=m.role, content=m.content,
                    tokens=m.tokens)


def inject_hitchhiker(trace: Trace, rate: float = 0.5,
                      seed: int = 0) -> Trace:
    """Add never-needed distractors whose tokens overlap the task queries, so
    the retrieval engine brings them in next to needed memories."""
    rng = random.Random(seed)
    msgs = list(trace.msgs)
    needed = {mid for t in trace.tasks for mid in t.needed_ids}
    for t in trace.tasks:
        if rng.random() >= rate:
            continue
        if not t.query_tokens:
            continue
        q = set(t.query_tokens)
        for i in range(2):  # two distractors per selected task
            # distractors quote the query vocabulary but are never needed
            content = " ".join(sorted(q)) + f" unrelated filler note {i}"
            mid = f"{trace.sample_id}:hitch:{t.task_id}:{i}"
            msgs.append(TraceMsg(
                msg_id=mid, session_id="hitchhiker",
                date=str(len(msgs)), date_idx=len(msgs), role="user",
                content=content, tokens=clean_tokens(content)))
    return Trace(sample_id=trace.sample_id, msgs=tuple(msgs),
                 tasks=trace.tasks)


def inject_stale_version(trace: Trace, seed: int = 0) -> Trace:
    """For each task: add a newer version of a needed memory (same entity
    tokens + update marker, later date) so the engine prefers the update
    while the old version stays needed."""
    msgs = list(trace.msgs)
    by = {m.msg_id: m for m in msgs}
    new_tasks: List[TraceTask] = []
    next_idx = len(msgs)
    for t in trace.tasks:
        new_needed = list(t.needed_ids)
        for mid in t.needed_ids:
            m = by.get(mid)
            if m is None:
                continue
            upd_id = f"{t.task_id}:update:{mid}"
            content = m.content + " UPDATE: this is the newer version."
            msgs.append(TraceMsg(
                msg_id=upd_id, session_id=m.session_id + "_v2",
                date=str(next_idx), date_idx=next_idx, role=m.role,
                content=content,
                tokens=clean_tokens(content)))
            next_idx += 1
            new_needed.append(upd_id)  # old stays needed; new one is distractor
        new_tasks.append(TraceTask(
            task_id=t.task_id, question=t.question,
            query_tokens=t.query_tokens, needed_ids=tuple(new_needed),
            scope=t.scope, date=t.date))
    return Trace(sample_id=trace.sample_id, msgs=tuple(msgs),
                 tasks=tuple(new_tasks))


def inject_rare_protective(trace: Trace, demote_to: int = 0,
                           seed: int = 0) -> Trace:
    """Move needed memories to the very front of the timeline (rare/old):
    retrieval can still find them, recency-based persistence cannot."""
    rng = random.Random(seed)
    msgs = list(trace.msgs)
    needed = {mid for t in trace.tasks for mid in t.needed_ids}
    order = [i for i, m in enumerate(msgs) if m.msg_id not in needed]
    rng.shuffle(order)
    # demote half the needed memories to the oldest block, before everything
    demoted = [i for i, m in enumerate(msgs)
               if m.msg_id in needed and rng.random() < 0.5]
    for i, idx in enumerate(demoted):
        msgs[idx] = _clone_msg(msgs[idx], msgs[idx].msg_id, demote_to + i)
    # reindex date_idx chronologically
    msgs.sort(key=lambda m: m.date_idx)
    msgs = [TraceMsg(msg_id=m.msg_id, session_id=m.session_id, date=m.date,
                     date_idx=i, role=m.role, content=m.content, tokens=m.tokens)
            for i, m in enumerate(msgs)]
    return Trace(sample_id=trace.sample_id, msgs=tuple(msgs),
                 tasks=trace.tasks)


def inject_scope_shift(trace: Trace, seed: int = 0) -> Trace:
    """Remove the needed memories' session from the recorded support while
    keeping the query: the task scope lies beyond what the system recorded."""
    rng = random.Random(seed)
    by = by_id(trace)
    kept_msgs: List[TraceMsg] = []
    new_tasks: List[TraceTask] = []
    for t in trace.tasks:
        if rng.random() < 0.5:
            # drop the needed session entirely from the recorded stream
            drop_sids = {by[mid].session_id for mid in t.needed_ids if mid in by}
            keep = [m for m in trace.msgs if m.session_id not in drop_sids]
            if len(keep) == len(trace.msgs):
                keep = list(trace.msgs)
            kept_msgs = keep
            new_tasks.append(TraceTask(
                task_id=t.task_id, question=t.question,
                query_tokens=t.query_tokens, needed_ids=(),
                scope=t.scope, date=t.date))
        else:
            kept_msgs = list(trace.msgs)
            new_tasks.append(t)
    kept_msgs.sort(key=lambda m: m.date_idx)
    kept_msgs = [TraceMsg(msg_id=m.msg_id, session_id=m.session_id,
                          date=m.date, date_idx=i, role=m.role,
                          content=m.content, tokens=m.tokens)
                 for i, m in enumerate(kept_msgs)]
    return Trace(sample_id=trace.sample_id, msgs=tuple(kept_msgs),
                 tasks=tuple(new_tasks))


def inject_co_memory_competition(trace: Trace, budget_scale: float = 0.5,
                                 seed: int = 0) -> Tuple[Trace, float]:
    """Halve the workspace budget (crowding): same stream, smaller workspace.
    Returns (trace', effective budget scale) — the crowding enters through
    the workspace constraint, not the stream."""
    return trace, budget_scale


def inject(trace: Trace, name: str) -> Tuple[Trace, float]:
    """Apply injection `name`; returns (trace', budget_scale)."""
    if name == "control":
        return trace, 1.0
    if name == "hitchhiker":
        return inject_hitchhiker(trace, 0.5, 11), 1.0
    if name == "stale_version":
        return inject_stale_version(trace), 1.0
    if name == "rare_protective":
        return inject_rare_protective(trace, 0, 13), 1.0
    if name == "scope_shift":
        return inject_scope_shift(trace), 1.0
    if name == "co_memory_competition":
        return inject_co_memory_competition(trace, 0.5)
    raise KeyError(name)


INJECTIONS = ("control", "hitchhiker", "stale_version", "rare_protective",
              "scope_shift", "co_memory_competition")


# ---------------------------------------------------------------------------
# lifecycle value + randomized counterfactuals
# ---------------------------------------------------------------------------

def _dilution(exposed_ids: Sequence[str], needed_set: set) -> float:
    if not exposed_ids:
        return 0.0
    return sum(1 for mid in exposed_ids if mid not in needed_set) / len(exposed_ids)


def episodic_value(exposed_ids: Sequence[str], needed_ids: Sequence[str],
                   token_counts: Dict[str, int], gamma: float = GAMMA,
                   lam: float = LAMBDA_TOK,
                   rho: float = RHO_DILUTION) -> float:
    """Discounted utility of a single exposure episode (the Gate-4 cost
    contract in miniature: utility - lambda*tokens - rho*dilution)."""
    if not exposed_ids:
        return 0.0
    hit = 1.0 if any(mid in needed_ids for mid in exposed_ids) else 0.0
    dil = _dilution(exposed_ids, set(needed_ids))
    tok = sum(token_counts.get(mid, 0) for mid in exposed_ids)
    return hit - rho * dil - lam * tok


def run_counterfactuals(trace: Trace, budget: int = 12,
                        engine: str = "bm25", rounds: int = 16,
                        max_tasks: int = 100, seed: int = 0,
                        memory_cap: int = 8,
                        budget_scale: float = 1.0) -> Dict:
    """Per memory m in the mechanism-relevant set, on a (possibly injected)
    real trace:

    V_RCT(m) = mean over R rounds of [V(always-in) - V(always-out)] where each
    round RE-RANDOMIZES the co-exposed workspace (repeated randomization
    counterfactual; the Stage-1 protocol-path estimator applied to real
    traces).  CI from the round distribution.
    V_obs(m) = the observational contrast a deployment would compute from its
    own logs: mean per-task value over tasks where the engine exposed m minus
    the engine's value over tasks where it did not.
    """
    rng = random.Random(seed)
    effective_budget = max(1, int(budget * budget_scale))
    engine_ws = engine_workspaces(trace, effective_budget, engine)
    token_counts = {m.msg_id: len(m.tokens) for m in trace.msgs}
    pool = [m.msg_id for m in trace.msgs]
    tasks = list(trace.tasks)[:max_tasks]
    needed_by_task = [set(t.needed_ids) for t in tasks]
    all_needed = {mid for t in tasks for mid in t.needed_ids}

    # mechanism-relevant memory set: needed + co-exposed hitchhikers
    relevant: List[str] = []
    for mid in all_needed:
        if mid not in relevant:
            relevant.append(mid)
    for i, t in enumerate(tasks):
        for mid in engine_ws[t.task_id][0]:
            if mid not in all_needed and mid not in relevant:
                relevant.append(mid)
        if len(relevant) >= memory_cap:
            break
    relevant = relevant[:memory_cap]

    engine_sets = {t.task_id: set(engine_ws[t.task_id][0]) for t in tasks}
    results: Dict[str, Dict] = {}
    for mid in relevant:
        # ---- protocol path: R rounds x 2 regimens, re-randomized each round
        in_vals: List[float] = []
        out_vals: List[float] = []
        others = [p for p in pool if p != mid]
        for _ in range(rounds):
            ws_in = rng.sample(pool, min(effective_budget, len(pool)))
            ws_out = rng.sample(others, min(effective_budget, len(others)))
            if mid not in ws_in:
                ws_in = ws_in[:-1] + [mid]
            v_in = sum(
                episodic_value(ws_in, needed_by_task[i], token_counts)
                * (GAMMA ** i) for i, t in enumerate(tasks))
            v_out = sum(
                episodic_value(ws_out, needed_by_task[i], token_counts)
                * (GAMMA ** i) for i, t in enumerate(tasks))
            in_vals.append(v_in)
            out_vals.append(v_out)
        v_rct = statistics.mean(in_vals) - statistics.mean(out_vals)
        if rounds > 1:
            se = math.hypot(
                statistics.stdev(in_vals) / rounds ** 0.5,
                statistics.stdev(out_vals) / rounds ** 0.5)
        else:
            se = 0.0
        # ---- observational path: the engine's natural exposure contrast
        obs_in: List[float] = []
        obs_out: List[float] = []
        for i, t in enumerate(tasks):
            ws = engine_sets[t.task_id]
            v_ep = episodic_value(list(ws), needed_by_task[i],
                                  token_counts) * (GAMMA ** i)
            if mid in ws:
                obs_in.append(v_ep)
            else:
                obs_out.append(v_ep)
        support = len(obs_in)
        if support > 0 and len(obs_out) > 0:
            v_obs = statistics.mean(obs_in) - statistics.mean(obs_out)
            obs_se = math.hypot(
                statistics.pstdev(obs_in) / max(len(obs_in) ** 0.5, 1e-9),
                statistics.pstdev(obs_out) / max(len(obs_out) ** 0.5, 1e-9))
        else:
            v_obs = float("nan")          # support failure -> unresolved
            obs_se = float("nan")
        results[mid] = {
            "needed": int(mid in all_needed),
            "support_n": support,
            "v_rct": v_rct,
            "se_rct": se,
            "v_obs": v_obs,
            "se_obs": obs_se,
        }
    return results


# ---------------------------------------------------------------------------
# per-mechanism aggregation
# ---------------------------------------------------------------------------

def summarize_condition(results: Dict[str, Dict]) -> Dict[str, float]:
    """Sign errors of the observational estimate against the protocol truth,
    restricted to memories whose truth is not MC noise; support failures are
    'unresolved' (no confident decision), not errors."""
    n = len(results)
    n_needed = sum(1 for r in results.values() if r["needed"])
    n_support = sum(1 for r in results.values() if r["support_n"] > 0)
    n_nonzero = sum(1 for r in results.values()
                    if abs(r["v_rct"]) > 1.96 * r["se_rct"])
    confident_errors = 0
    confident_errors_nonzero = 0
    sign_errors = 0
    for r in results.values():
        if r["support_n"] == 0 or math.isnan(r["v_obs"]):
            continue
        if r["v_obs"] * r["v_rct"] < 0:
            sign_errors += 1
        if abs(r["v_obs"]) > 1.96 * r["se_obs"] and r["v_obs"] * r["v_rct"] < 0:
            confident_errors += 1
            if abs(r["v_rct"]) > 1.96 * r["se_rct"]:
                confident_errors_nonzero += 1
    return {
        "n_memories": float(n),
        "n_needed": float(n_needed),
        "n_support": float(n_support),
        "n_nonzero_truth": float(n_nonzero),
        "support_failure_rate": 1.0 - (n_support / n if n else 0.0),
        "sign_error_rate": sign_errors / n_support if n_support else 0.0,
        "confident_error_rate": confident_errors / n_support if n_support else 0.0,
        "confident_error_rate_on_nonzero_truth": (
            confident_errors_nonzero / n_nonzero) if n_nonzero else 0.0,
    }


# ---------------------------------------------------------------------------
# Gate 2.3 — external benchmark retrieval layer, end-to-end on real data
# ---------------------------------------------------------------------------

def run_retrieval_layer(traces: Sequence[Trace], k: int = 12,
                        random_baseline_seed: int = 0) -> Dict[str, float]:
    """Official-protocol BM25 top-k vs the benchmark's ground truth:
    recall@k of needed memories, plus no-retrieval and random controls."""
    rng = random.Random(random_baseline_seed)
    bm25_recall = []
    recency_recall = []
    random_recall = []
    for trace in traces:
        ws = engine_workspaces(trace, k, "bm25")
        for t in trace.tasks:
            needed = set(t.needed_ids)
            if not needed:
                continue
            bm25_set = set(ws[t.task_id][0])
            bm25_recall.append(len(bm25_set & needed) / len(needed))
            recent = [m.msg_id for m in trace.msgs[-k:]]
            recency_recall.append(len(set(recent) & needed) / len(needed))
            rand = [m.msg_id for m in rng.sample(trace.msgs, min(k, len(trace.msgs)))]
            random_recall.append(len(set(rand) & needed) / len(needed))
    return {
        "bm25_recall_at_k": statistics.mean(bm25_recall) if bm25_recall else 0.0,
        "recency_recall_at_k": statistics.mean(recency_recall) if recency_recall else 0.0,
        "random_recall_at_k": statistics.mean(random_recall) if random_recall else 0.0,
        "n_tasks": float(len(bm25_recall)),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--longmemeval", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/LongMemEval/longmemeval_s_cleaned.json"))
    parser.add_argument("--locomo", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/LoCoMo/locomo10.json"))
    parser.add_argument("--budget", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=16)
    parser.add_argument("--traces-per-dataset", type=int, default=40)
    parser.add_argument("--output", type=Path,
                        default=Path("results/trace_semisynthetic.json"))
    args = parser.parse_args()

    # Lifecycle substrate: LoCoMo (longitudinal: 199 QA over 10-day timelines).
    # LongMemEval S is the incidence + retrieval substrate; its samples are
    # SINGLE-query, so lifecycle value over a task sequence is degenerate
    # there (a benchmark-granularity finding, not a measurement).
    lo = load_locomo(args.locomo)
    lme = load_longmemeval_s(args.longmemeval)

    conditions = list(INJECTIONS)
    # Exposure engine per condition: rare-protective is a PERSISTENCE-layer
    # mechanism (2.1: LoCoMo rare-needed exposure 0.927 under BM25 vs 0.026
    # under decay), so that leg runs under the decay engine; the rest run
    # under the retrieval engine.
    ENGINE_BY_CONDITION = {
        "control": "bm25", "hitchhiker": "bm25", "stale_version": "bm25",
        "rare_protective": "decay", "scope_shift": "bm25",
        "co_memory_competition": "bm25",
    }
    result: Dict = {"config": {
        "budget": args.budget, "rounds": args.rounds,
        "gamma": GAMMA, "lambda_tok": LAMBDA_TOK, "rho_dilution": RHO_DILUTION,
        "engine_by_condition": ENGINE_BY_CONDITION,
    }, "conditions": {"locomo": {}}, "retrieval_layer": {}, "notes": {
        "longmemeval_s": "single-query samples: used for mechanism incidence "
                         "(trace_grounded_runner) and the retrieval layer; "
                         "lifecycle counterfactuals require a task sequence "
                         "(LoCoMo supplies it).",
        "rare_protective_engine": "runs under the decay persistence engine: "
                                  "the mechanism is recency/persistence-bound "
                                  "(BM25 is recency-blind, see incidence "
                                  "table); decay is the honest stressor.",
    }}
    for cond_name in conditions:
        engine = ENGINE_BY_CONDITION[cond_name]
        per_trace: List[Dict] = []
        for t in lo:
            mutated, budget_scale = inject(t, cond_name)
            per_trace.append(run_counterfactuals(
                mutated, args.budget, engine, args.rounds, seed=0,
                budget_scale=budget_scale))
        sums = summarize_condition(
            {f"{i}:{mid}": r for i, tr in enumerate(per_trace)
             for mid, r in tr.items()})
        result["conditions"]["locomo"][cond_name] = sums
        print(f"locomo {cond_name:24s} "
              f"support_fail={sums['support_failure_rate']:.3f} "
              f"sign_err={sums['sign_error_rate']:.3f} "
              f"conf_err={sums['confident_error_rate']:.3f} "
              f"conf_err_nonzero={sums['confident_error_rate_on_nonzero_truth']:.3f} "
              f"(n={int(sums['n_memories'])}, n_nonzero={int(sums['n_nonzero_truth'])})")
    for ds_name, traces in (("longmemeval_s", lme), ("locomo", lo)):
        result["retrieval_layer"][ds_name] = run_retrieval_layer(traces)
        r = result["retrieval_layer"][ds_name]
        print(f"{ds_name:14s} retrieval: bm25={r['bm25_recall_at_k']:.3f} "
              f"recency={r['recency_recall_at_k']:.3f} "
              f"random={r['random_recall_at_k']:.3f} (n={int(r['n_tasks'])})")
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")


if __name__ == "__main__":
    main()
