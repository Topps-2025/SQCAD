"""G-2: locate the G4 trichotomy branch on REAL agent traces.

Ports the `46-` constructive protocol (LifecycleBench) onto LongMemEval-S /
LoCoMo chronological streams.  For each candidate memory row we run a forced
keep / forced archive paired intervention and measure

    Delta(m) = V^K(m) - V^A(m)

over the *future* task suffix, then group rows into score fibers of each
baseline surface.  A fiber holding two rows whose Delta have opposite sign
(both beyond TAU_TOL) is a witness that the surface is lifecycle-INCOMPLETE
on natural tasks -- the `future-lossy` branch of G4.

Honesty constraints (any violation makes the witness worthless):
  1. Every score is computed from DECISION-TIME VISIBLE features only.  No
     surface may read `needed_ids` of future tasks, or the future suffix.
     `46-` gave trivium future demand; here demand is PAST demand only.
  2. Archive is NOT assumed zero-information: the archive branch keeps the
     row retrievable at a probe cost, it is only removed from the workspace
     candidate pool.
  3. Fibers use exact equality after rounding (conservative, reproducible).
  4. Caps are logged, never silent.

Negative result is a valid closure: if every surface has zero opposite-sign
fibers, the real systems are future-null / lifecycle-complete on these tasks
and the paper keeps the constructive-possibility framing (plan section 5.4).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqcad.lifecycle_bench.frozen import (
    GAMMA, PROBE_BUDGET_PER_TASK, PROBE_THRESHOLD, TAU_TOL,
)
from sqcad.trace_grounded_runner import (  # noqa: E402
    Trace, TraceMsg, TraceTask, bm25_scores, by_id, load_locomo,
    load_longmemeval_s,
)

TASK_VALUE = 10.0
PROBE_COST = 1.0
STORAGE_RATE = 0.01
EXPOSURE_UNIT = 0.05


@dataclass(frozen=True)
class TraceView:
    """Decision-time visible features of one memory row. No future access."""
    msg_id: str
    tokens: Tuple[str, ...]
    text: str
    storage_tokens: int
    age: int                    # rows seen after it, at decision time
    past_mentions: int          # past tasks whose query overlapped it
    past_demand: float          # discounted past demand (NOT future)
    past_relevance: float       # mean overlap with past queries
    local_relevance: float      # overlap with the decision-point query
    bm25_at_decision: float
    mean_pool_relevance: float
    scope: str
    decision_scope: str


def _ov(a: Sequence[str], b: Sequence[str]) -> int:
    return len(set(a) & set(b))


def build_trace_view(msg: TraceMsg, msgs: Sequence[TraceMsg],
                     past: Sequence[TraceTask], decision: TraceTask,
                     bm25: Mapping[str, float]) -> TraceView:
    q = decision.query_tokens
    mentions = 0
    demand = 0.0
    rels: List[float] = []
    for k, t in enumerate(reversed(past)):
        o = _ov(msg.tokens, t.query_tokens)
        rels.append(o / max(len(set(t.query_tokens)), 1))
        if o >= 2:
            mentions += 1
            demand += GAMMA ** k
    pool = [_ov(m.tokens, q) / max(len(set(q)), 1) for m in msgs]
    idx = [m.msg_id for m in msgs].index(msg.msg_id)
    return TraceView(
        msg_id=msg.msg_id,
        tokens=msg.tokens,
        text=msg.content,
        storage_tokens=len(msg.tokens),
        age=len(msgs) - 1 - idx,
        past_mentions=mentions,
        past_demand=demand,
        past_relevance=(sum(rels) / len(rels)) if rels else 0.0,
        local_relevance=_ov(msg.tokens, q) / max(len(set(q)), 1),
        bm25_at_decision=float(bm25.get(msg.msg_id, 0.0)),
        mean_pool_relevance=(sum(pool) / len(pool)) if pool else 0.0,
        scope=msg.session_id,
        decision_scope=decision.scope,
    )


# --------------------------------------------------------------------------
# Baseline score surfaces.  Each reads ONLY TraceView (decision-time visible).
# Names mirror the fidelity tiers of 47-/48-: these are transported surfaces,
# not reproductions of the published systems.
# --------------------------------------------------------------------------

def _simplemem_lexical(v: TraceView) -> float:
    return float(v.local_relevance)


def _recency(v: TraceView) -> float:
    return float(GAMMA ** v.age)


def _bm25(v: TraceView) -> float:
    return float(v.bm25_at_decision)


def _memory_worth(v: TraceView) -> float:
    return float(v.past_demand * v.local_relevance
                 - STORAGE_RATE * v.storage_tokens)


def _fademem(v: TraceView) -> float:
    return float(v.local_relevance * (GAMMA ** v.age))


def _demem(v: TraceView) -> float:
    return float(1.0 if v.local_relevance > v.mean_pool_relevance else 0.0)


def _cmi_local(v: TraceView) -> float:
    return float(v.local_relevance - v.mean_pool_relevance)


def _trivium_past(v: TraceView) -> float:
    """Demand-weighted, but PAST demand only -- the honest online version."""
    return float(v.past_demand)


def _govmem_access(v: TraceView) -> float:
    return float(v.past_mentions)


SURFACES: Tuple[Tuple[str, str, Callable[[TraceView], float]], ...] = (
    ("simplemem_lexical", "official-code surface (lexical retrieval only)",
     _simplemem_lexical),
    ("recency", "simple control", _recency),
    ("bm25", "simple control", _bm25),
    ("memory_worth", "MW-shaped associational proxy", _memory_worth),
    ("fademem", "paper-mechanism proxy", _fademem),
    ("demem", "decision-distinction heuristic", _demem),
    ("cmi_local", "query-local causal-effect control", _cmi_local),
    ("trivium_past", "demand-weighted control (past demand only)",
     _trivium_past),
    ("govmem_access", "access-time coverage control (NOT GovMem)",
     _govmem_access),
)


# --------------------------------------------------------------------------
# Forced keep / forced archive paired intervention on the real future suffix
# --------------------------------------------------------------------------

def _rank(pool: Sequence[TraceMsg], task: TraceTask,
          budget: int) -> List[TraceMsg]:
    sc = bm25_scores(pool, task.query_tokens)
    return sorted(pool, key=lambda m: (-sc.get(m.msg_id, 0.0), m.msg_id))[:budget]


def _rollout(msgs: Sequence[TraceMsg], future: Sequence[TraceTask],
             target: str, keep: bool, budget: int) -> Tuple[float, List[Dict]]:
    """Value of the future suffix under forced keep/archive of `target`.

    keep=True : target stays in the workspace candidate pool.
    keep=False: target is archived -- still RETRIEVABLE, but only by paying
                PROBE_COST, and it no longer occupies a workspace slot.
                Archive is NOT zero-information (plan section 5.3 item 4).
    """
    tgt = next((m for m in msgs if m.msg_id == target), None)
    pool = [m for m in msgs if keep or m.msg_id != target]
    value = 0.0
    logs: List[Dict] = []
    for slot, task in enumerate(future):
        ws = _rank(pool, task, budget)
        ws_ids = [m.msg_id for m in ws]
        need = set(task.needed_ids)
        probe = 0.0
        restored = False
        if not keep and tgt is not None and PROBE_BUDGET_PER_TASK > 0:
            # world.py:250-274 -- archived rows are reachable only through a
            # BUDGETED, THRESHOLDED probe whose cost is paid even when wasted.
            # No guaranteed recovery: the probe must also out-score the weakest
            # workspace occupant to earn a slot.
            if _ov(tgt.tokens, task.query_tokens) >= PROBE_THRESHOLD:
                probe = PROBE_COST
                sc = bm25_scores(msgs, task.query_tokens)
                floor = min((sc.get(i, 0.0) for i in ws_ids), default=0.0)
                if sc.get(target, 0.0) > floor:
                    restored = True
                    ws_ids = ws_ids[:-1] + [target] if ws_ids else [target]
        hit = len(need & set(ws_ids))
        cov = hit / max(len(need), 1)
        exposure = EXPOSURE_UNIT * len(ws_ids)
        storage = STORAGE_RATE * sum(len(m.tokens) for m in pool)
        step = TASK_VALUE * cov - exposure - storage - probe
        value += (GAMMA ** slot) * step
        logs.append({"slot": slot, "task_id": task.task_id,
                     "coverage": round(cov, 6),
                     "target_in_workspace": target in ws_ids,
                     "target_needed": target in need,
                     "probe": probe, "restored": restored,
                     "storage": round(storage, 6),
                     "retrieval": round(TASK_VALUE * cov - exposure - probe, 6),
                     "fingerprint": tuple(ws_ids)})
    return value, logs


def paired_delta(msgs: Sequence[TraceMsg], future: Sequence[TraceTask],
                 target: str, budget: int) -> Dict[str, object]:
    vk, lk = _rollout(msgs, future, target, True, budget)
    va, la = _rollout(msgs, future, target, False, budget)
    differing = [a["slot"] for a, b in zip(lk, la)
                 if (a["fingerprint"], a["probe"]) != (b["fingerprint"], b["probe"])]
    # Storage-neutral component: archiving mechanically removes the row's
    # storage tokens from the pool, a constant discount that is independent of
    # whether the row was ever USEFUL.  Reporting Delta alone would let that
    # discount decide every sign.  delta_retrieval isolates the lifecycle
    # question -- did dropping the row cost future task value?
    rk = sum((GAMMA ** i) * r["retrieval"] for i, r in enumerate(lk))
    ra = sum((GAMMA ** i) * r["retrieval"] for i, r in enumerate(la))
    return {
        "delta": vk - va,
        "delta_retrieval": rk - ra,
        "value_keep": vk,
        "value_archive": va,
        "n_probes_paid": sum(1 for r in la if r["probe"] > 0),
        "n_probes_restored": sum(1 for r in la if r["restored"]),
        "kernel_changed": bool(differing),
        "differing_slots": differing,
        "value_relevant": abs(vk - va) > TAU_TOL,
        "n_future_needing_target": sum(
            1 for t in future if target in set(t.needed_ids)),
    }


def fiber_summary(rows: Sequence[Mapping[str, object]], digits: int,
                  key: str = "delta") -> Dict[str, object]:
    """Group rows by exact rounded score; find opposite-sign Delta pairs.

    `key` selects the paired contrast: "delta" (full value, includes the
    mechanical storage discount) or "delta_retrieval" (storage-neutral).
    """
    fibers: Dict[float, List[Mapping[str, object]]] = defaultdict(list)
    for r in rows:
        fibers[round(float(r["score"]), digits)].append(r)

    def rel(m: Mapping[str, object]) -> bool:
        return abs(float(m[key])) > TAU_TOL

    witnesses: List[Dict[str, object]] = []
    for score, members in fibers.items():
        pos = [m for m in members if float(m[key]) > TAU_TOL and rel(m)]
        neg = [m for m in members if float(m[key]) < -TAU_TOL and rel(m)]
        if not pos or not neg:
            continue
        hi = max(pos, key=lambda m: float(m[key]))
        lo = min(neg, key=lambda m: float(m[key]))
        gap = float(hi[key]) - float(lo[key])
        witnesses.append({
            "score": score, "fiber_size": len(members),
            "epsilon_lc_witness": round(gap, 6),
            "regret_lower_bound": round(gap / 4.0, 6),
            "keep_row": {"msg_id": hi["msg_id"], "trace": hi["trace_id"],
                         "delta": round(float(hi[key]), 6)},
            "archive_row": {"msg_id": lo["msg_id"], "trace": lo["trace_id"],
                            "delta": round(float(lo[key]), 6)},
        })
    witnesses.sort(key=lambda w: -float(w["epsilon_lc_witness"]))
    kernel_changed = sum(1 for r in rows if r["kernel_changed"])
    relevant = sum(1 for r in rows if rel(r))
    deltas = [float(r[key]) for r in rows]
    n_pos = sum(1 for d in deltas if d > TAU_TOL)
    n_neg = sum(1 for d in deltas if d < -TAU_TOL)
    return {
        "contrast": key,
        "delta_sign": {
            "n_keep_better": n_pos, "n_archive_better": n_neg,
            "n_within_tau": len(deltas) - n_pos - n_neg,
            "min": round(min(deltas), 6) if deltas else 0.0,
            "max": round(max(deltas), 6) if deltas else 0.0,
        },
        "n_rows": len(rows),
        "n_fibers": len(fibers),
        "n_nontrivial_fibers": sum(1 for f in fibers.values() if len(f) > 1),
        "n_kernel_changed": kernel_changed,
        "kernel_change_rate": round(kernel_changed / max(len(rows), 1), 4),
        "n_value_relevant": relevant,
        "value_relevant_rate": round(relevant / max(len(rows), 1), 4),
        "n_opposite_sign_fibers": len(witnesses),
        "epsilon_lc": witnesses[0]["epsilon_lc_witness"] if witnesses else 0.0,
        "branch": ("future-lossy" if witnesses
                   else ("lifecycle-complete-or-future-null"
                         if kernel_changed else "future-null")),
        # Fiber starvation: a witness needs TWO rows in one fiber, so a score
        # fine enough to separate every row cannot be contradicted by
        # construction.  Reporting such a surface as lifecycle-complete is a
        # false negative of the same kind as the zero-row artifact below, so the
        # coverage denominator travels with the verdict.
        "fiber_coverage": {
            "n_singleton_fibers": len(fibers) - sum(
                1 for f in fibers.values() if len(f) > 1),
            "n_rows_in_nontrivial_fibers": sum(
                len(f) for f in fibers.values() if len(f) > 1),
            "testable_fraction": round(
                sum(len(f) for f in fibers.values() if len(f) > 1)
                / max(len(rows), 1), 4),
            "fiber_starved": bool(
                not witnesses
                and sum(len(f) for f in fibers.values() if len(f) > 1)
                < 0.2 * max(len(rows), 1)),
        },
        # Witness thinness: how many DISTINCT rows can play each side.  If the
        # archive side is a single row across all surfaces, the branch verdict
        # rests on one episode and must be reported as such, not as a rate.
        "witness_support": {
            "n_distinct_keep_rows": len({m["msg_id"] for m in rows
                                         if float(m[key]) > TAU_TOL and rel(m)}),
            "n_distinct_archive_rows": len({m["msg_id"] for m in rows
                                            if float(m[key]) < -TAU_TOL
                                            and rel(m)}),
            "archive_side_rows": sorted({
                m["msg_id"] for m in rows
                if float(m[key]) < -TAU_TOL and rel(m)})[:8],
        },
        "top_witnesses": witnesses[:3],
    }


def audit_trace_rows(trace: Trace, budget: int, max_candidates: int,
                     min_future: int) -> List[Dict[str, object]]:
    """Paired intervention over candidate rows at a mid-stream decision point."""
    msgs, tasks = list(trace.msgs), list(trace.tasks)
    if len(tasks) < min_future + 1:
        return []
    cut = max(1, len(tasks) // 3)
    past, decision, future = tasks[:cut], tasks[cut], tasks[cut:]
    if len(future) < min_future:
        return []

    # Candidates: rows some future task needs, plus top-BM25 distractors.
    needed = {mid for t in future for mid in t.needed_ids}
    bm25 = bm25_scores(msgs, decision.query_tokens)
    by = by_id(trace)
    cands = [by[m] for m in sorted(needed) if m in by]
    extra = sorted((m for m in msgs if m.msg_id not in needed),
                   key=lambda m: (-bm25.get(m.msg_id, 0.0), m.msg_id))
    cands += extra[:max(0, max_candidates - len(cands))]
    cands = cands[:max_candidates]

    rows: List[Dict[str, object]] = []
    for m in cands:
        pr = paired_delta(msgs, future, m.msg_id, budget)
        view = build_trace_view(m, msgs, past, decision, bm25)
        for name, _lvl, fn in SURFACES:
            rows.append({
                "trace_id": trace.sample_id, "msg_id": m.msg_id,
                "surface": name, "score": float(fn(view)), **pr,
            })
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True, choices=["longmemeval_s", "locomo"])
    p.add_argument("--path", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--budget", type=int, default=12)
    p.add_argument("--max-candidates", type=int, default=14)
    p.add_argument("--min-future", type=int, default=3)
    p.add_argument("--score-digits", type=int, default=8)
    a = p.parse_args()

    loader = load_longmemeval_s if a.dataset == "longmemeval_s" else load_locomo
    traces = loader(a.path, limit=a.limit)
    print(f"loaded {len(traces)} traces from {a.dataset}", flush=True)

    all_rows: List[Dict[str, object]] = []
    skipped = 0
    for i, tr in enumerate(traces, 1):
        r = audit_trace_rows(tr, a.budget, a.max_candidates, a.min_future)
        if not r:
            skipped += 1
        all_rows.extend(r)
        print(f"  [{i}/{len(traces)}] {tr.sample_id}: {len(r)//len(SURFACES)} "
              f"candidates, {len(tr.tasks)} tasks", flush=True)

    per_surface: Dict[str, object] = {}
    per_surface_full: Dict[str, object] = {}
    for name, level, _fn in SURFACES:
        rows = [r for r in all_rows if r["surface"] == name]
        # PRIMARY contrast is storage-neutral: the full-value Delta carries a
        # mechanical archive discount (the row's tokens leave the store) that
        # would decide every sign regardless of lifecycle value.
        s = fiber_summary(rows, a.score_digits, key="delta_retrieval")
        s["evidence_level"] = level
        per_surface[name] = s
        per_surface_full[name] = fiber_summary(rows, a.score_digits,
                                               key="delta")

    lossy = [n for n, s in per_surface.items() if s["branch"] == "future-lossy"]
    # A surface with no witness AND almost no non-singleton fiber has not been
    # shown complete -- it has been shown untestable at this candidate cap.
    # Keeping the two apart is what stops the negative branch from being
    # claimed on a score that is merely too fine-grained to have fibers.
    starved = [n for n, s in per_surface.items()
               if s["fiber_coverage"]["fiber_starved"]]
    undetermined = [n for n, s in per_surface.items()
                    if s["branch"] != "future-lossy" and n not in starved]

    # A zero-row artifact is NOT a negative result: it means the dataset has no
    # multi-task chronological suffix, so the protocol never ran.  LongMemEval-S
    # carries exactly one question per trace, so every trace is skipped by
    # `min_future`.  Reporting this as "no witness" would be a false negative.
    inapplicable = not all_rows
    if inapplicable:
        verdict = ("PROTOCOL INAPPLICABLE to this dataset: every trace was "
                   "skipped for having fewer than min_future future tasks, so "
                   "no paired intervention was performed.  This is a scope "
                   "limit, NOT evidence about the G4 branch.")
    elif lossy:
        verdict = (
            f"future-lossy witnesses found on real traces for {len(lossy)}/"
            f"{len(SURFACES)} surfaces"
            + (f"; {len(starved)} surface(s) FIBER-STARVED (untestable at this "
               f"candidate cap, NOT shown complete): {', '.join(starved)}"
               if starved else "")
            + (f"; {len(undetermined)} surface(s) no witness on a testable "
               f"fiber population: {', '.join(undetermined)}"
               if undetermined else ""))
    elif starved and not undetermined:
        verdict = ("NO surface testable: every surface is fiber-starved at this "
                   "candidate cap, so the protocol produced no evidence about "
                   "the G4 branch either way.  Raise --max-candidates.")
    else:
        verdict = ("NO opposite-sign witness on real traces -- "
                   "constructive-possibility framing retained (plan 5.4)")

    out = {
        "gate": "G-2",
        "dataset": a.dataset,
        "protocol_applicable": not inapplicable,
        "protocol": "forced keep/archive paired intervention on real traces; "
                    "46- protocol ported off LifecycleBench",
        "honesty_notes": [
            "all surfaces read decision-time-visible features only",
            "archive keeps the row retrievable at PROBE_COST (not zero-information)",
            "fibers are exact equality after rounding to score_digits",
            "trivium uses PAST demand only (future demand would leak the label)",
            "probes are BUDGETED (PROBE_BUDGET_PER_TASK), THRESHOLDED "
            "(PROBE_THRESHOLD) and charged even when wasted; an archived row "
            "is NOT guaranteed recovery -- it must out-score the weakest "
            "workspace occupant (mirrors world.py:250-274)",
            "PRIMARY contrast is delta_retrieval (storage-neutral). The "
            "full-value delta is reported alongside but is confounded by the "
            "mechanical storage discount archiving always receives.",
            "a surface with no witness is reported as FIBER-STARVED, not as "
            "lifecycle-complete, when under 20% of its rows share a fiber with "
            "any other row: a witness needs two rows in one fiber, so a "
            "near-injective score cannot be contradicted by construction",
            "witness support is reported as DISTINCT archive-side rows, not as "
            "a rate: raising --max-candidates has been observed to flip a "
            "surface from no-witness to future-lossy, so a zero at a low cap "
            "bounds the search, not the branch",
        ],
        "caps": {"traces_requested": a.limit, "traces_loaded": len(traces),
                 "traces_skipped_too_few_tasks": skipped,
                 "max_candidates_per_trace": a.max_candidates,
                 "workspace_budget": a.budget, "min_future_tasks": a.min_future},
        "params": {"gamma": GAMMA, "tau_tol": TAU_TOL, "task_value": TASK_VALUE,
                   "probe_cost": PROBE_COST, "storage_rate": STORAGE_RATE,
                   "exposure_unit": EXPOSURE_UNIT},
        "n_rows_total": len(all_rows),
        "primary_contrast": "delta_retrieval",
        "per_surface": per_surface,
        "per_surface_full_value_delta": per_surface_full,
        "surfaces_future_lossy": lossy,
        "surfaces_fiber_starved": starved,
        "surfaces_no_witness_but_testable": undetermined,
        "verdict": verdict,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(json.dumps({"verdict": out["verdict"],
                      "surfaces_future_lossy": lossy,
                      "per_surface": {k: {"branch": v["branch"],
                                          "eps_lc": v["epsilon_lc"],
                                          "opp_fibers": v["n_opposite_sign_fibers"],
                                          "kernel_rate": v["kernel_change_rate"]}
                                      for k, v in per_surface.items()}},
                     ensure_ascii=False, indent=2))
    print(f"wrote {a.output}")


if __name__ == "__main__":
    main()
