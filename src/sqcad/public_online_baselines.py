"""Strict-online variants of the transductive proxy baselines (33- report,
doc 28- leak audit; 30- R1 L2 supplement).

The frozen ``memory_worth`` / ``causal_item`` rows batch-score over the
FULL QA sequence of a trace before any workspace is produced
(public_unified_contract.py:472-478, :792-810): counters and exposure
contrasts see every query including future ones, and one static top-BUDGET
set is shared across all tasks.  On LoCoMo (10 conversations, ~1986 QAs)
this is future-query leakage; the repo's own audit flags it as transductive
(doc 28-:260, 268, 349, 434).

These engines reproduce the same observable signals but update state
sequentially in frozen QA order: the retention set for task t uses only
counters/effects from tasks 1..t-1, and task t's query is consumed only
after the decision.  New policy names are added alongside the frozen rows
(never overwritten):

  memory_worth_online -- MW-shaped Beta(1,1) posterior over PRIOR lexical
                         query-overlap events.  The paper's episode
                         success/failure and actual-retrieval conditioning
                         are unavailable, so this is not an MW reproduction.
  causal_item_online  -- naive observational exposure contrast over PRIOR
                         QAs only (support failure -> base score).  This is
                         an estimand control, not CMI's no/with/perturbed
                         LLM intervention pipeline.
  demem_online        -- decision-distinction heuristic
                         |posterior - mean posterior|.  It is not DeMem's
                         certified-conflict partition learner.
  trivium_online      -- demand-weighted semantic control
                         (1 + prior lexical hits) x base score.  It has no
                         persistent causal log, posterior-regret ledger, or
                         budgeted causal-probe policy.
  govmem_online       -- prior-query coverage control.  GovMem is a
                         write-time promote/reject/needs-review policy, so
                         this access-time row is not transportable GovMem.

The transductive batch-score references (demem / trivium / govmem) are
computed in this file as well (full-QA counters -> one shared top-BUDGET
retention set), matching the frozen memory_worth/causal_item convention
(public_unified_contract.py:472-478, :792-810) without touching the frozen
file; the online-vs-transductive gap is the future-query-leakage bound
(33-: 31- sec. 5.4).

Cold-start semantics: on LongMemEval-S (exactly 1 task per sample) the
priors at t-1 are the uninformative (0,0) counters, so the row reports the
honest cold-start behavior of each heuristic.  On LoCoMo the first QA is
cold-start and later QAs use strictly prior evidence.

Run:  PYTHONPATH=src python -m sqcad.public_online_baselines \
        --longmemeval <path> --locomo <path> \
        --qa-out-dir results/locomo_qa_online --output \
        results/public_online_baselines.json
Then official LoCoMo F1 (frozen scorer, unchanged):
  python tools/run_locomo_official_scorer.py \
        --pred-dir results/locomo_qa_online --out results/locomo_official_qa_online.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .public_unified_contract import (
    BUDGET, CONFLICT_OVERLAP, PolicyResult, _base_scores, _load,
    _qa_meta_by_task, _storage_tokens, aggregate, bm25_scores,
    evaluate_trace, mask_lme_chronological, needed_free, significance,
    trace_features, write_locomo_qa_files,
)
from .trace_grounded_runner import Trace, TraceMsg, TraceTask

ONLINE_POLICIES = ("memory_worth_online", "causal_item_online",
                   "demem_online", "trivium_online", "govmem_online")
COMPARE_POLICIES = ("memory_worth", "causal_item", "demem", "trivium",
                    "govmem", "bm25", "sqcad")


# ---------------------------------------------------------------------------
# strict-online engines
# ---------------------------------------------------------------------------

def _posterior_mean(counters: Dict[str, Tuple[int, int]]) -> Dict[str, float]:
    """Beta(1,1) posterior mean, the frozen memory_worth signal."""
    return {mid: (h + 1.0) / (h + n + 2.0)
            for mid, (h, n) in counters.items()}


def _posterior_deviation(
        counters: Dict[str, Tuple[int, int]]) -> Dict[str, float]:
    """Internal decision-distinction heuristic, not the DeMem learner."""
    post = _posterior_mean(counters)
    mu = statistics.mean(post.values()) if post else 0.0
    return {mid: abs(p - mu) for mid, p in post.items()}


def _episodic_demand(
        counters: Dict[str, Tuple[int, int]],
        base: Dict[str, float]) -> Dict[str, float]:
    """Demand-weighted semantic control, not a Trivium causal controller."""
    return {mid: (1.0 + counters[mid][0]) * base.get(mid, 0.0)
            for mid in counters}


def _coverage_loss(
        counters: Dict[str, Tuple[int, int]],
        base: Dict[str, float]) -> Dict[str, float]:
    """Access-time coverage control; GovMem itself is write-time."""
    return {mid: counters[mid][0] + 1e-6 * base.get(mid, 0.0)
            for mid in counters}


def _online_ratio_engine(msgs: Sequence[TraceMsg], tasks: Sequence[TraceTask],
                         policy: str,
                         score: Callable[[Dict[str, Tuple[int, int]],
                                          Dict[str, float]],
                                         Dict[str, float]]
                         ) -> PolicyResult:
    """Generic strict-online engine: retention for task t uses only QA
    evidence from tasks strictly before t (frozen QA order), scored by the
    injected signal; task t's query is consumed after its decision."""
    toks = {m.msg_id: set(m.tokens) for m in msgs}
    base = _base_scores(msgs)
    counters: Dict[str, Tuple[int, int]] = {m.msg_id: (0, 0) for m in msgs}
    out: Dict[str, Tuple[str, ...]] = {}
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}
    retained: Tuple[str, ...] = ()
    for t in tasks:
        sc = score(counters, base)
        ranked = sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))
        new_retained = tuple(mid for mid, _ in ranked[:BUDGET])
        for mid in new_retained:
            if mid not in retained:
                lifecycle["restores"] += 1
        for mid in retained:
            if mid not in new_retained:
                lifecycle["archives"] += 1
        retained = new_retained
        out[t.task_id] = retained
        # consume task t's query only AFTER its retention decision
        q = set(t.query_tokens)
        for m in msgs:
            hit = int(len(toks[m.msg_id] & q) >= CONFLICT_OVERLAP)
            h, n = counters[m.msg_id]
            counters[m.msg_id] = (h + hit, n + (1 - hit))
    return PolicyResult(
        policy=policy, workspaces=out, storage_ids=retained,
        storage_tokens=_storage_tokens(msgs, retained), lifecycle=lifecycle)


def _batch_score_engine(msgs: Sequence[TraceMsg], tasks: Sequence[TraceTask],
                        policy: str,
                        score: Callable[[Dict[str, Tuple[int, int]],
                                         Dict[str, float]],
                                        Dict[str, float]]
                        ) -> PolicyResult:
    """Transductive reference for the proxy family (33- convention, frozen
    file untouched): one pass over the FULL QA sequence accumulates the
    counters, one static top-BUDGET retention set is shared by every task
    (the frozen memory_worth/causal_item structure)."""
    toks = {m.msg_id: set(m.tokens) for m in msgs}
    base = _base_scores(msgs)
    counters: Dict[str, Tuple[int, int]] = {m.msg_id: (0, 0) for m in msgs}
    for t in tasks:
        q = set(t.query_tokens)
        for m in msgs:
            hit = int(len(toks[m.msg_id] & q) >= CONFLICT_OVERLAP)
            h, n = counters[m.msg_id]
            counters[m.msg_id] = (h + hit, n + (1 - hit))
    sc = score(counters, base)
    ranked = sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))
    retained = tuple(mid for mid, _ in ranked[:BUDGET])
    out = {t.task_id: retained for t in tasks}
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}
    return PolicyResult(
        policy=policy, workspaces=out, storage_ids=retained,
        storage_tokens=_storage_tokens(msgs, retained), lifecycle=lifecycle)


def _online_causal_engine(msgs: Sequence[TraceMsg],
                          tasks: Sequence[TraceTask],
                          policy: str) -> PolicyResult:
    """causal_item_online: naive exposure contrast over PRIOR tasks only
    (same observable proxy, no future queries)."""
    toks = {m.msg_id: set(m.tokens) for m in msgs}
    exposed_val: Dict[str, List[float]] = defaultdict(list)
    unexposed_val: Dict[str, List[float]] = defaultdict(list)
    base = _base_scores(msgs)
    out: Dict[str, Tuple[str, ...]] = {}
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}
    retained: Tuple[str, ...] = ()
    for t in tasks:
        effect: Dict[str, float] = {}
        for m in msgs:
            if exposed_val[m.msg_id] and unexposed_val[m.msg_id]:
                effect[m.msg_id] = (
                    statistics.mean(exposed_val[m.msg_id])
                    - statistics.mean(unexposed_val[m.msg_id]))
            else:
                effect[m.msg_id] = base[m.msg_id]
        ranked = sorted(effect.items(), key=lambda kv: (-kv[1], kv[0]))
        new_retained = tuple(mid for mid, _ in ranked[:BUDGET])
        for mid in new_retained:
            if mid not in retained:
                lifecycle["restores"] += 1
        for mid in retained:
            if mid not in new_retained:
                lifecycle["archives"] += 1
        retained = new_retained
        out[t.task_id] = retained
        # consume task t's query AFTER its retention decision
        scores = bm25_scores(msgs, t.query_tokens)
        top = set(sorted(scores, key=lambda mid: (-scores[mid], mid))[:BUDGET])
        q = set(t.query_tokens)
        for m in msgs:
            v = float(len(toks[m.msg_id] & q) >= CONFLICT_OVERLAP)
            (exposed_val if m.msg_id in top
             else unexposed_val)[m.msg_id].append(v)
    return PolicyResult(
        policy=policy, workspaces=out, storage_ids=retained,
        storage_tokens=_storage_tokens(msgs, retained), lifecycle=lifecycle)


_ONLINE_SCORES = {
    "memory_worth_online": lambda c, b: _posterior_mean(c),
    "demem_online": lambda c, b: _posterior_deviation(c),
    "trivium_online": _episodic_demand,
    "govmem_online": _coverage_loss,
}
_BATCH_SCORES = {
    "memory_worth": lambda c, b: _posterior_mean(c),
    "demem": lambda c, b: _posterior_deviation(c),
    "trivium": _episodic_demand,
    "govmem": _coverage_loss,
}


def run_online_policy(policy: str, trace: Trace) -> Optional[PolicyResult]:
    """Dispatch for the online family (needed_free keeps the same gold-free
    contract as the frozen run_policy)."""
    tasks = needed_free(trace.tasks)
    if policy in _ONLINE_SCORES:
        return _online_ratio_engine(trace.msgs, tasks, policy,
                                    _ONLINE_SCORES[policy])
    if policy == "causal_item_online":
        return _online_causal_engine(trace.msgs, tasks, policy)
    return None


def run_batch_proxy_policy(policy: str, trace: Trace) -> Optional[PolicyResult]:
    """Transductive proxy references computed in this file (full-QA
    counters -> one shared retention set; frozen rows unchanged)."""
    if policy in _BATCH_SCORES:
        return _batch_score_engine(trace.msgs, needed_free(trace.tasks),
                                   policy, _BATCH_SCORES[policy])
    return None


# ---------------------------------------------------------------------------
# CLI (contract-shaped output)
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--longmemeval", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/"
                                     "LongMemEval/longmemeval_s_cleaned.json"))
    parser.add_argument("--locomo", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/"
                                     "LoCoMo/locomo10.json"))
    parser.add_argument("--policies",
                        default=",".join(ONLINE_POLICIES + COMPARE_POLICIES))
    parser.add_argument("--datasets", default="longmemeval_s,locomo")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path,
                        default=Path("results/public_online_baselines.json"))
    parser.add_argument("--qa-out-dir", type=Path, default=None)
    args = parser.parse_args()

    policies = [p.strip() for p in args.policies.split(",") if p.strip()]
    result: Dict[str, Any] = {
        "config": {
            "note": ("strict-online supplement (33-): retention for task t "
                     "uses only tasks strictly before t in frozen QA order; "
                     "the frozen memory_worth/causal_item rows are the "
                     "transductive references"),
            "budget": BUDGET, "conflict_overlap": CONFLICT_OVERLAP,
            "policies": policies,
            "chronological_mask": True,
            "qa_reader": "extractive sentence reader (no generation model)",
        },
        "datasets": {},
    }

    want = {d.strip() for d in args.datasets.split(",") if d.strip()}
    for name, path in (("longmemeval_s", args.longmemeval),
                       ("locomo", args.locomo)):
        if name not in want:
            continue
        traces = _load(name, path, args.limit)
        if not traces:
            continue
        qa_meta = _qa_meta_by_task(name, path)
        ds_out: Dict[str, Any] = {
            "n_traces": len(traces), "mask": {}, "policies": {},
            "significance": {},
        }
        evals: Dict[str, List[Dict]] = {}
        qa_pairs: List[Tuple[Trace, PolicyResult]] = []
        for trace in traces:
            masked, meta = (mask_lme_chronological(trace)
                            if name == "longmemeval_s" else (trace, {}))
            for key, val in meta.items():
                ds_out["mask"][key] = ds_out["mask"].get(key, 0) + val
            feats = trace_features(masked.msgs)  # shared, once per trace
            visible_ids = {m.msg_id for m in masked.msgs}
            for pol in policies:
                if pol in ONLINE_POLICIES:
                    res = run_online_policy(pol, masked)
                elif pol in _BATCH_SCORES:
                    # demem/trivium/govmem transductive references are
                    # computed here (frozen file untouched); the frozen
                    # memory_worth/causal_item rows stay on run_policy.
                    res = run_batch_proxy_policy(pol, masked)
                else:
                    from .public_unified_contract import run_policy
                    res = run_policy(pol, masked, feats=feats)
                if res is None:
                    continue
                evals.setdefault(pol, []).append(
                    evaluate_trace(res, masked, visible_ids))
                if name == "locomo" and args.qa_out_dir:
                    qa_pairs.append((masked, res))
        if name == "locomo" and args.qa_out_dir and qa_pairs:
            write_locomo_qa_files(qa_pairs, qa_meta, Path(args.qa_out_dir))

        for pol in policies:
            if pol in evals:
                ds_out["policies"][pol] = aggregate(pol, evals[pol])
            else:
                ds_out["policies"][pol] = {"policy": pol, "skipped": True}

        pairs: List[Tuple[str, str]] = []
        for pol in ONLINE_POLICIES:
            base_name = pol.removesuffix("_online")
            if base_name in evals:
                pairs.append((pol, base_name))
            for base in ("bm25", "sqcad"):
                if pol in evals and base in evals:
                    pairs.append((pol, base))
        for metric in ("hit_rate", "recall_mean", "tokens_mean",
                       "storage_tokens"):
            ds_out["significance"][metric] = significance(evals, metric,
                                                          pairs)
        result["datasets"][name] = ds_out
        print(f"== {name} ==")
        for pol in policies:
            if pol not in evals:
                continue
            agg = ds_out["policies"][pol]
            print(f"  {pol:24s} hit={agg['hit_rate']['mean']:.3f} "
                  f"recall={agg['recall_mean']['mean']:.3f} "
                  f"tok={agg['tokens_mean']['mean']:.1f} "
                  f"store={agg['storage_tokens']['mean']:.0f} "
                  f"P/R/A={agg['lifecycle_mean']['probes']:.1f}/"
                  f"{agg['lifecycle_mean']['restores']:.1f}/"
                  f"{agg['lifecycle_mean']['archives']:.1f}")

    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
