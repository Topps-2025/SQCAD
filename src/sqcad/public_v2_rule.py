"""Public-contract row for the Theorem-5 rule (sqcad_v2, 32- round 1 fix,
L2 external validity).

ICLR-challenge round-1 finding (experiments track): "L2 evaluates the
pre-fix degenerate rule; the proposed (v2) rule has no public-data results."
This module runs the three-decision rule through the IDENTICAL public
contract (frozen reader, BUDGET=12, chronological mask, extractive reader,
official LoCoMo scorer), without modifying any frozen code.

Public certificate (event-based, mirroring the L3 reference_certificate
semantics with only public observables, zero new thresholds):

  NEGATIVE     mid in updaters        -- superseded by a visible update
                                        event (L3: "event targets the fid")
  UNRESOLVED   mid in newest          -- versioned fact family, crossing/
                                        conflict state (L3: version/lineage
                                        conflict)
  POSITIVE     else                   -- identified, no negative signal
                                        (L3: "adopted, no negative signal")

Rule (Theorem 5): authorize keep iff the certificate is strictly positive;
NEGATIVE and UNRESOLVED (crossing interval) are refused: deferred-archive at
write time, re-admissible only through the paid probe/restore channel at QA
time (the frozen follow-on, unchanged).  The write-time gate is the ONLY
difference from the frozen _sqcad_engine; everything downstream (eviction,
probe, restore, candidate guard, fallback, exposure ranking) is copied
verbatim from the frozen implementation so that any difference in the row
attributes to the admission gate.

Honest expectations: on public traces most messages carry no version/
correction evidence, so the rule admits most items -- the row quantifies the
certificate's refusal behavior where update/version evidence exists, and it
makes the store certificate-governed rather than score-eviction-governed.

Run:  PYTHONPATH=src python -m sqcad.public_v2_rule \
        --longmemeval <path> --locomo <path> \
        --qa-out-dir results/locomo_qa_v2 --output \
        results/public_v2_rule.json
Then official LoCoMo F1 (frozen scorer):
  python tools/run_locomo_official_scorer_portable.py \
        --eval-file datasets/locomo_eval/evaluation.py \
        --pred-dir results/locomo_qa_v2 \
        --out results/locomo_official_qa_v2.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from .public_unified_contract import (
    ATTENUATION, BUDGET, CONFLICT_BONUS, CONFLICT_OVERLAP, PolicyResult,
    PROBE_BUDGET_PER_TASK, RARE_FLOOR, _load, _qa_meta_by_task,
    _storage_tokens, aggregate, bm25_scores, evaluate_trace,
    mask_lme_chronological, needed_free, run_policy, significance,
    trace_features, write_locomo_qa_files,
)
from .trace_grounded_runner import Trace, TraceMsg, TraceTask


def certificate(mid: str, feats) -> str:
    """Public event-based certificate (see module docstring)."""
    if mid in feats.updaters:
        return "NEGATIVE"
    if mid in feats.newest:
        return "UNRESOLVED"
    return "POSITIVE"


def _v2_engine(msgs: Sequence[TraceMsg], tasks: Sequence[TraceTask],
               feats) -> PolicyResult:
    """Faithful variant of the frozen _sqcad_engine (reference config) with
    the write-time admission gate changed to the Theorem-5 rule: keep only
    on a strictly positive certificate, else deferred-archive."""
    by = feats.by
    toks = feats.toks
    freq = feats.freq
    rare = feats.rare
    updaters, newest = feats.updaters, feats.newest
    lineage = feats.lineage
    base = feats.base

    retained: List[str] = []
    archived: List[str] = []
    rows: List[Dict] = []
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}

    def score(mid: str) -> float:
        s = base[mid]
        if by[mid].session_id in rare:
            s += RARE_FLOOR
        if mid in updaters:
            s += CONFLICT_BONUS
        return s

    def conflicted_unresolved(mid: str) -> bool:
        return mid in newest and newest[mid] in retained

    def evict() -> None:
        """Frozen eviction (verbatim): archive the weakest item; unresolved
        version pairs are split only when nothing else can be evicted."""
        candidates = [mid for mid in retained
                      if not conflicted_unresolved(mid)]
        forced = not candidates
        if forced:
            candidates = list(retained)
        victim = min(candidates, key=lambda mid: (score(mid), mid))
        to_archive = [victim]
        to_archive += [mid for mid in retained if mid != victim
                       and by[mid].session_id == by[victim].session_id]
        for v in to_archive:
            if v not in retained:
                continue
            retained.remove(v)
            archived.append(v)
            lifecycle["archives"] += 1
            rows.append({"mid": v, "action": "archive",
                         "qualification": ("forced_pair" if forced
                                           else "identified"),
                         "reason": "budget_forced" if forced else "budget"})
            for mid in list(retained):
                if lineage.get(mid) == v:
                    retained.remove(mid)
                    archived.append(mid)
                    lifecycle["archives"] += 1
                    rows.append({"mid": mid, "action": "archive",
                                 "qualification": "orphan",
                                 "reason": "source_archived"})

    # ---- write time: Theorem-5 admission gate (THE v2 difference) ----
    for m in msgs:
        if m.msg_id in retained:
            continue
        cert = certificate(m.msg_id, feats)
        if cert != "POSITIVE":
            # refuse to commit on a non-positive certificate: deferred
            # archive at write time; the paid probe/restore channel at QA
            # time is the only re-admission path (frozen follow-on below).
            archived.append(m.msg_id)
            lifecycle["archives"] += 1
            rows.append({"mid": m.msg_id, "action": "archive",
                         "qualification": "refused",
                         "reason": f"cert_{cert}"})
            continue
        retained.append(m.msg_id)
        rows.append({"mid": m.msg_id, "action": "keep",
                     "qualification": "identified", "reason": "write"})
        while len(retained) > BUDGET:
            evict()

    # ---- QA time (frozen follow-on, verbatim) ----
    workspaces: Dict[str, Tuple[str, ...]] = {}
    for t in tasks:
        q = set(t.query_tokens)
        overlap = {mid: len(toks[mid] & q) for mid in toks}
        pool = list(retained)

        probe_ids: List[str] = []
        if archived:
            cand = [mid for mid in archived if overlap[mid] >= CONFLICT_OVERLAP]
            cand_ranked = sorted(cand, key=lambda mid: (-overlap[mid], mid))
            probe_ids = cand_ranked[:PROBE_BUDGET_PER_TASK]
            for mid in probe_ids:
                lifecycle["probes"] += 1
                rows.append({"mid": mid, "action": "probe",
                             "qualification": "probed",
                             "reason": "query_overlap"})

        # note: the reference "sqcad" config has candidate_guard=False, so
        # no coverage-guard block here -- the v2 row differs from the
        # frozen sqcad row ONLY in the write-time admission gate.

        while len(pool) < BUDGET and archived:
            fill = max(archived, key=lambda mid: (overlap[mid], mid))
            archived.remove(fill)
            pool.append(fill)
            lifecycle["fallbacks"] += 1
            rows.append({"mid": fill, "action": "fallback",
                         "qualification": "silent_fill",
                         "reason": "short_workspace"})

        pool_exposure = list(dict.fromkeys(pool + probe_ids))
        q_scores = bm25_scores([by[mid] for mid in pool_exposure],
                               t.query_tokens)
        eff = {mid: q_scores[mid] * (ATTENUATION if mid in updaters else 1.0)
               for mid in pool_exposure}
        ranked = sorted(pool_exposure, key=lambda mid: (-eff[mid], mid))
        exposed = ranked[:BUDGET]
        workspaces[t.task_id] = tuple(exposed)

        if probe_ids:
            for mid in probe_ids:
                admit = mid in exposed
                if admit and mid not in retained:
                    retained.append(mid)
                    if mid in archived:
                        archived.remove(mid)
                    lifecycle["restores"] += 1
                    rows.append({"mid": mid, "action": "restore",
                                 "qualification": "restored",
                                 "reason": "earned_slot"})
                    while len(retained) > BUDGET:
                        evict()

    return PolicyResult(policy="sqcad_v2", workspaces=workspaces,
                        storage_ids=tuple(retained),
                        storage_tokens=_storage_tokens(msgs, retained),
                        lifecycle=lifecycle, rows=rows)


def run_v2_policy(policy: str, trace: Trace) -> PolicyResult:
    """Dispatch for the v2 public family."""
    tasks = needed_free(trace.tasks)
    feats = trace_features(trace.msgs)
    return _v2_engine(trace.msgs, tasks, feats)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--longmemeval", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/"
                                     "LongMemEval/longmemeval_s_cleaned.json"))
    parser.add_argument("--locomo", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/"
                                     "LoCoMo/locomo10.json"))
    parser.add_argument("--datasets", default="longmemeval_s,locomo")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path,
                        default=Path("results/public_v2_rule.json"))
    parser.add_argument("--qa-out-dir", type=Path, default=None)
    args = parser.parse_args()

    policies = ("sqcad_v2", "sqcad", "bm25")
    result: Dict[str, Any] = {
        "config": {
            "note": ("Theorem-5 rule on the public contract (32- round 1): "
                     "keep iff strictly positive certificate, else "
                     "deferred-archive; write-time gate only, frozen "
                     "follow-on verbatim; frozen sqcad/bm25 rows are the "
                     "references"),
            "budget": BUDGET, "conflict_overlap": CONFLICT_OVERLAP,
            "policies": list(policies),
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
            feats = trace_features(masked.msgs)
            visible_ids = {m.msg_id for m in masked.msgs}
            for pol in policies:
                if pol == "sqcad_v2":
                    res = _v2_engine(masked.msgs, needed_free(masked.tasks),
                                     feats)
                else:
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

        pairs = [("sqcad_v2", "sqcad"), ("sqcad_v2", "bm25")]
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
            print(f"  {pol:12s} hit={agg['hit_rate']['mean']:.3f} "
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
