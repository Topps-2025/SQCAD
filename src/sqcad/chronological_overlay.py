"""Semi-synthetic chronological overlay on public traces (doc 19-).

The public datasets carry no lifecycle gold (16- section 4), so the
governance-relevant objectives -- false forgetting, harmful retention,
correction absorption, rescue via the paid probe channel -- are measured
here on programmatically injected events over the LoCoMo substrate.
Injection uses ONLY information visible at the injection time point; every
label is programmatic (the dataset's own QA gold + exposure-based criteria),
never human annotation (doc 17 4.0 / 7.1).

Event types (doc 19- section 2):

  E1 version update distractor: a later turn restating a needed turn's text
     plus an update marker (>=3 shared tokens -> version conflict).  The QA
     gold is unchanged; exposing the old version is the hit, exposing the
     update while missing the old is the distractor failure.
  E2 correction event: at t0 an injected FALSE fact F (built from the gold
     answer, programmatically negated); at t1>t0 a correction turn stating
     the gold answer.  Post-correction QAs: exposing F without the evidence
     turn is a harmful exposure; the correction gives a policy the chance to
     absorb the update (E3 has no correction and is the contrast).
  E3 harmful retention: same F without any correction.
  E4 rare-positive protection: no injection; needed turns from low-frequency
     sessions (as in the frozen contract).
  E5 self-obscuring + rescue: no injection; needed turns evicted to the
     archive during the write phase must be rescued by probe/restore/
     fallback at QA time; false forgetting = archived and never re-exposed.

All policies run under the frozen unified contract (16-): same turns, same
budget, same run_policy/evaluate_trace, same paired bootstrap rule.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .public_unified_contract import (
    PolicyResult, aggregate, evaluate_trace, run_policy, significance,
    trace_features,
)
from .trace_grounded_runner import (
    Trace, TraceMsg, TraceTask, by_id, clean_tokens, load_locomo,
)

# pre-registered injection constants (doc 19-)
E1_GAP = 2          # update placed `gap` turns after the needed turn
E2_GAP = 1          # correction placed `gap` turns after the false fact
N_EVENTS_PER_TRACE = 5   # per event type, per conversation
OVERLAY_SEED = 20260814


@dataclass(frozen=True)
class OverlayEvent:
    event_type: str                    # E1..E5
    task_id: str                       # the QA this event targets
    false_id: Optional[str] = None     # E2/E3 injected false fact
    correction_id: Optional[str] = None  # E2 correction turn
    update_id: Optional[str] = None    # E1 update turn
    needed_ids: Tuple[str, ...] = ()   # gold evidence turns (target)


@dataclass
class OverlaidTrace:
    trace: Trace                       # msgs augmented with injections
    events: List[OverlayEvent]
    meta: Dict[str, Any] = field(default_factory=dict)


def _first_sentence(text: str) -> str:
    parts = text.split(". ")
    return parts[0] if parts else text


def _make_false_fact(question: str, answer: str) -> str:
    """Programmatic contradiction: the question's entity claim negated.
    Shares >=3 tokens with the evidence turn by construction (question
    vocabulary)."""
    q_words = clean_tokens(question)
    head = " ".join(q_words[:8]) if len(q_words) >= 8 else question
    return f"{head} -- note: this was NOT {answer}"


def inject_overlay(trace: Trace, n_per_type: int = N_EVENTS_PER_TRACE,
                   seed: int = OVERLAY_SEED) -> OverlaidTrace:
    """Inject E1/E2/E3 events onto a LoCoMo conversation.  Every injected
    turn is placed at a historical time point and uses only content visible
    there (the needed turn's own text / the dataset's gold answer, which is
    'past' knowledge for the stream).  E4/E5 need no injection."""
    rng = random.Random(seed)
    by = by_id(trace)
    msgs = list(trace.msgs)
    events: List[OverlayEvent] = []
    next_idx = len(msgs)

    # candidate QAs: have gold answer text and >=1 locatable evidence turn
    candidates = [t for t in trace.tasks
                  if t.needed_ids and all(mid in by for mid in t.needed_ids)]
    rng.shuffle(candidates)

    def _add(content: str, session: str, target_idx: int) -> str:
        """Append an injected turn with the pre-registered chronological
        placement (target date_idx); the final re-index pass sorts it into
        the timeline exactly at that position."""
        nonlocal next_idx
        mid = f"{trace.sample_id}:overlay:{next_idx}"
        msgs.append(TraceMsg(msg_id=mid, session_id=session,
                             date=str(target_idx), date_idx=target_idx,
                             role="user", content=content,
                             tokens=clean_tokens(content)))
        next_idx += 1
        return mid

    e1 = e2 = e3 = 0
    for i, t in enumerate(candidates):
        # pick the chronologically FIRST needed turn as the event anchor so
        # later injections can follow it on the timeline
        needed_sorted = sorted(t.needed_ids, key=lambda mid: by[mid].date_idx)
        anchor = needed_sorted[0]
        anchor_msg = by[anchor]
        anchor_idx = anchor_msg.date_idx
        tail = len(msgs) - 1

        # round-robin event assignment (one event per QA), with fallback to
        # the next constructible type
        preferred = ("E1", "E2", "E3")[i % 3]
        produced = False
        for etype in (preferred, "E1", "E2", "E3"):
            if produced:
                break
            if etype == "E1" and e1 < n_per_type \
                    and anchor_idx + E1_GAP < tail:
                upd_id = _add(f"{_first_sentence(anchor_msg.content)} "
                              "UPDATE: this is the newer version.",
                              anchor_msg.session_id + "_v2",
                              anchor_idx + E1_GAP)
                events.append(OverlayEvent(event_type="E1",
                                           task_id=t.task_id,
                                           update_id=upd_id,
                                           needed_ids=tuple(needed_sorted)))
                e1 += 1
                produced = True
            elif etype == "E2" and e2 < n_per_type \
                    and anchor_idx + E2_GAP + 1 < tail:
                qa_meta_ans = _qa_answer(trace, t.task_id)
                if qa_meta_ans:
                    false_id = _add(_make_false_fact(t.question, qa_meta_ans),
                                    anchor_msg.session_id + "_v2",
                                    anchor_idx + E2_GAP)
                    corr_id = _add(f"Correction: {qa_meta_ans}",
                                   anchor_msg.session_id + "_v3",
                                   anchor_idx + E2_GAP + 1)
                    events.append(OverlayEvent(
                        event_type="E2", task_id=t.task_id,
                        false_id=false_id, correction_id=corr_id,
                        needed_ids=tuple(needed_sorted)))
                    e2 += 1
                    produced = True
            elif etype == "E3" and e3 < n_per_type \
                    and anchor_idx + E2_GAP < tail:
                qa_meta_ans = _qa_answer(trace, t.task_id)
                if qa_meta_ans:
                    false_id = _add(
                        _make_false_fact(t.question, qa_meta_ans),
                        anchor_msg.session_id + "_v2",
                        anchor_idx + E2_GAP)
                    events.append(OverlayEvent(
                        event_type="E3", task_id=t.task_id,
                        false_id=false_id,
                        needed_ids=tuple(needed_sorted)))
                    e3 += 1
                    produced = True
        if e1 >= n_per_type and e2 >= n_per_type and e3 >= n_per_type:
            break

    # chronological re-index after the insertions (dates stay synthetic
    # ordinals; insertions carry the id order above)
    msgs.sort(key=lambda m: m.date_idx)
    msgs = [TraceMsg(msg_id=m.msg_id, session_id=m.session_id, date=m.date,
                     date_idx=i, role=m.role, content=m.content,
                     tokens=m.tokens) for i, m in enumerate(msgs)]
    # E4/E5: label-based (no stream change).  Rare sessions are computed on
    # the ORIGINAL stream: injected turns create singleton sessions that
    # would pollute the rarity threshold.
    rare = _rare_sessions_of(trace.msgs)
    for t in trace.tasks:
        rare_needed = [mid for mid in t.needed_ids
                       if mid in by and by[mid].session_id in rare]
        if rare_needed:
            events.append(OverlayEvent(event_type="E4", task_id=t.task_id,
                                       needed_ids=tuple(rare_needed)))
    # E5: every QA with locatable evidence is a self-obscuring target
    for t in trace.tasks:
        if t.needed_ids:
            events.append(OverlayEvent(event_type="E5", task_id=t.task_id,
                                       needed_ids=t.needed_ids))

    return OverlaidTrace(
        trace=Trace(sample_id=trace.sample_id, msgs=tuple(msgs),
                    tasks=trace.tasks),
        events=events,
        meta={"n_injected": len(msgs) - len(trace.msgs),
              "seed": seed})


_QA_ANSWER_CACHE: Dict[str, Dict[str, str]] = {}


def set_qa_answers(locomo_path: Path) -> None:
    """task_id -> gold answer text (loaded once from the dataset file; the
    gold never enters any policy)."""
    data = json.loads(Path(locomo_path).read_text(encoding="utf-8"))
    for sample in data:
        for q_idx, qa in enumerate(sample.get("qa", [])):
            _QA_ANSWER_CACHE[f"{sample['sample_id']}:q{q_idx}"] = \
                {"answer": str(qa.get("answer") or ""),
                 "category": qa.get("category")}


def _qa_answer(trace: Trace, task_id: str) -> str:
    return _QA_ANSWER_CACHE.get(task_id, {}).get("answer", "")


def _rare_sessions_of(msgs: Sequence[TraceMsg]) -> set:
    from collections import Counter
    import statistics
    freq = Counter(m.session_id for m in msgs)
    if len(freq) < 4:
        return set()
    q1 = statistics.quantiles(sorted(freq.values()), n=4)[0]
    return {sid for sid, c in freq.items() if c <= q1}


# ---------------------------------------------------------------------------
# overlay evaluation (gold + injection labels used only here)
# ---------------------------------------------------------------------------

def evaluate_overlay(res: PolicyResult, trace: Trace,
                     events: Sequence[OverlayEvent]) -> Dict[str, Any]:
    """Objective per-event metrics from exposure semantics.  The reader is
    not run: harmful exposure is defined as the programmatic criterion
    'the contradicting turn is exposed while no gold evidence turn is'. """
    by = by_id(trace)
    # a task can carry several events (E1 + E4 + E5); evaluate each
    ev_by_task: Dict[str, List[OverlayEvent]] = {}
    for e in events:
        ev_by_task.setdefault(e.task_id, []).append(e)
    out: Dict[str, Dict[str, float]] = {}
    for etype in ("E1", "E2", "E3", "E4", "E5"):
        out[etype] = {"n": 0.0, "hit": 0.0, "harmful": 0.0,
                      "distractor": 0.0, "rescue": 0.0,
                      "false_forgetting": 0.0}
    if res.rows:
        # sqcad records its archive history (restored items re-admitted to
        # the store count as rescued when exposed)
        archived_set = {row["mid"] for row in res.rows
                        if row.get("action") == "archive"}
    else:
        # static policies: not retained == archived
        archived_set = {m.msg_id for m in trace.msgs} - set(res.storage_ids)

    for t in trace.tasks:
        for ev in ev_by_task.get(t.task_id, ()):
            ws = set(res.workspaces.get(t.task_id, ()))
            needed = {mid for mid in ev.needed_ids if mid in by}
            o = out[ev.event_type]
            o["n"] += 1.0
            if needed:
                hit = int(any(mid in ws for mid in needed))
                o["hit"] += hit
                if ev.event_type == "E5":
                    archived_needed = [mid for mid in needed
                                       if mid in archived_set]
                    if archived_needed:
                        if any(mid in ws for mid in archived_needed):
                            o["rescue"] += 1.0
                        else:
                            o["false_forgetting"] += 1.0
            if ev.false_id and ev.false_id in ws and not (ws & needed):
                o["harmful"] += 1.0
            if ev.update_id and ev.update_id in ws and not (ws & needed):
                o["distractor"] += 1.0
    for etype, o in out.items():
        n = o["n"]
        if n:
            for k in ("hit", "harmful", "distractor", "rescue",
                      "false_forgetting"):
                o[k] /= n
    return {"trace_id": trace.sample_id, "events": out}


def aggregate_overlay(policy: str, evals: List[Dict]) -> Dict[str, Any]:
    agg: Dict[str, Any] = {"policy": policy, "n_units": len(evals)}
    for etype in ("E1", "E2", "E3", "E4", "E5"):
        agg[etype] = {
            k: sum(e["events"][etype][k] for e in evals) / len(evals)
            if evals else 0.0
            for k in ("n", "hit", "harmful", "distractor", "rescue",
                      "false_forgetting")}
    return agg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

POLICIES = ("bm25", "recency", "keep_all", "sqcad", "sqcad_no_probe",
            "sqcad_no_restore", "sqcad_no_version_gate", "sqcad_no_fallback",
            "sqcad_no_positive_protection")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locomo", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/"
                                     "LoCoMo/locomo10.json"))
    parser.add_argument("--policies", default=",".join(POLICIES))
    parser.add_argument("--n-per-type", type=int, default=N_EVENTS_PER_TRACE)
    parser.add_argument("--seed", type=int, default=OVERLAY_SEED)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path,
                        default=Path("results/chronological_overlay.json"))
    args = parser.parse_args()

    set_qa_answers(args.locomo)
    traces = load_locomo(args.locomo, args.limit)
    policies = [p.strip() for p in args.policies.split(",") if p.strip()]

    result: Dict[str, Any] = {
        "config": {"n_per_type": args.n_per_type, "seed": args.seed,
                   "e1_gap": E1_GAP, "e2_gap": E2_GAP,
                   "policies": policies,
                   "evaluation": "exposure-semantics objectives; no reader; "
                                 "gold answers used only for F construction "
                                 "and never seen by policies"},
        "traces": {},
        "aggregate": {},
        "significance": {},
    }
    evals: Dict[str, List[Dict]] = {}
    for trace in traces:
        overlaid = inject_overlay(trace, args.n_per_type, args.seed)
        feats = trace_features(overlaid.trace.msgs)
        for pol in policies:
            res = run_policy(pol, overlaid.trace, feats=feats)
            assert res is not None
            evals.setdefault(pol, []).append(
                evaluate_overlay(res, overlaid.trace, overlaid.events))
        result["traces"][trace.sample_id] = {
            "n_injected": overlaid.meta["n_injected"],
            "event_counts": {e: sum(1 for x in overlaid.events
                                    if x.event_type == e)
                             for e in ("E1", "E2", "E3", "E4", "E5")},
        }

    for pol in policies:
        result["aggregate"][pol] = aggregate_overlay(pol, evals[pol])
        a = result["aggregate"][pol]
        print(f"{pol:32s} E1_hit={a['E1']['hit']:.3f} "
              f"E2_harm={a['E2']['harmful']:.3f} "
              f"E3_harm={a['E3']['harmful']:.3f} "
              f"E4_hit={a['E4']['hit']:.3f} "
              f"E5_rescue={a['E5']['rescue']:.3f} "
              f"E5_ff={a['E5']['false_forgetting']:.3f}")

    # significance: sqcad vs bm25/recency/keep_all per event metric
    pairs = [("sqcad", b) for b in ("bm25", "recency", "keep_all")] + \
        [("sqcad", ab) for ab in policies if ab.startswith("sqcad_")]
    for etype in ("E1", "E2", "E3", "E4", "E5"):
        for metric in ("hit", "harmful", "distractor", "rescue"):
            per = {p: [{"value": e["events"][etype][metric]}
                       for e in evals[p]] for p in policies}
            sig = significance(per, "value", pairs)
            for k, v in sig.items():
                v.setdefault("etype", etype)
                v.setdefault("metric", metric)
            result["significance"][f"{etype}:{metric}"] = sig

    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")


if __name__ == "__main__":
    main()
