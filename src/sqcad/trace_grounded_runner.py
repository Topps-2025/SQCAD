"""Gate 2.1 — instrumented mechanism-incidence audit on real traces.

Real evidence streams: LongMemEval S (500 samples, 23,867 haystack sessions,
6 question types) and LoCoMo (10 conversations with turn-level ground truth).
Everything here is offline and deterministic (no model endpoints): candidate
generation, exposure propensity/position/workspace budget, co-exposure,
adoption proxy (ground-truth needed memories), action/outcome/cost, scope,
archive/restore/rollback.

Mechanism incidence measured (per trace, median across traces):

1. hitchhiker        - never-needed memory co-exposed with a needed one
2. stale version     - knowledge-update: pre-update memory needed at task time
                       while a newer (distractor) version is in the workspace
3. rare protective   - needed memories from the low-frequency session tail and
                       whether they survive exposure
4. scope shift       - needed memory outside the recent workspace window
5. co-memory competition - workspace density around a needed memory and the
                       rate at which needed memories land in tail positions

The adoption proxy is the benchmark's own ground truth: LongMemEval
answer_session_ids / LoCoMo evidence dia_ids mark which memories a task
needs.  This is what an LLM's "did the agent use the right memory" check
would confirm; we read it directly from the frozen files instead of paying
an API.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List, Sequence, Tuple

TOKEN_RE = re.compile(r"[a-z0-9']+")


def clean_tokens(text: str) -> Tuple[str, ...]:
    return tuple(TOKEN_RE.findall(text.lower()))


@dataclass(frozen=True)
class TraceMsg:
    msg_id: str            # f"{sample}:{session}:{turn}"
    session_id: str
    date: str
    date_idx: int          # chronological ordinal within the sample
    role: str
    content: str
    tokens: Tuple[str, ...]


@dataclass(frozen=True)
class TraceTask:
    task_id: str
    question: str
    query_tokens: Tuple[str, ...]
    needed_ids: Tuple[str, ...]   # ground-truth needed msg ids
    scope: str                    # question_type (LongMemEval) / category (LoCoMo)
    date: str


@dataclass(frozen=True)
class Trace:
    sample_id: str
    msgs: Tuple[TraceMsg, ...]
    tasks: Tuple[TraceTask, ...]


def by_id(trace: Trace) -> Dict[str, TraceMsg]:
    return {m.msg_id: m for m in trace.msgs}


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------

def load_longmemeval_s(path: Path | str, limit: int | None = None) -> List[Trace]:
    """LongMemEval S: 500 samples; haystack sessions carry {role, content}
    turns; each QA pair lists its answer session ids (the needed memories)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    traces: List[Trace] = []
    for sample in data:
        msgs: List[TraceMsg] = []
        session_ids = sample["haystack_session_ids"]
        for s_idx, (sid, date, turns) in enumerate(zip(
                session_ids, sample["haystack_dates"],
                sample["haystack_sessions"])):
            for t_idx, turn in enumerate(turns):
                if not isinstance(turn, dict) or "content" not in turn:
                    continue
                text = str(turn["content"])
                msgs.append(TraceMsg(
                    msg_id=f"{sample['question_id']}:{sid}:{t_idx}",
                    session_id=sid,
                    date=str(date),
                    date_idx=len(msgs),
                    role=str(turn.get("role", "user")),
                    content=text,
                    tokens=clean_tokens(text),
                ))
        # LongMemEval S: each sample is one QA pair (question / answer /
        # answer_session_ids), not a qa_pairs list.
        sessions = sample["haystack_sessions"]
        sid_index = {sid: i for i, sid in enumerate(session_ids)}
        needed: List[str] = []
        for sid in sample.get("answer_session_ids", []):
            i = sid_index.get(sid)
            if i is None:
                continue
            for t_idx, turn in enumerate(sessions[i]):
                if isinstance(turn, dict) and "content" in turn:
                    needed.append(f"{sample['question_id']}:{sid}:{t_idx}")
        tasks = [TraceTask(
            task_id=f"{sample['question_id']}:q0",
            question=str(sample.get("question", "")),
            query_tokens=clean_tokens(str(sample.get("question", ""))),
            needed_ids=tuple(needed),
            scope=str(sample.get("question_type", "unknown")),
            date=str(sample.get("question_date", "")),
        )]
        traces.append(Trace(sample_id=sample["question_id"],
                            msgs=tuple(msgs), tasks=tuple(tasks)))
        if limit is not None and len(traces) >= limit:
            break
    return traces


def load_locomo(path: Path | str, limit: int | None = None) -> List[Trace]:
    """LoCoMo: conversation dict with session_N blocks; QA evidence is a list
    of dia_ids -> turn-level ground truth."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    traces: List[Trace] = []
    for sample in data:
        msgs: List[TraceMsg] = []
        conv = sample["conversation"]
        for key, value in conv.items():
            if not re.fullmatch(r"session_\d+", key) or not isinstance(value, list):
                continue
            for turn in value:
                if not isinstance(turn, dict):
                    continue
                dia_id = str(turn.get("dia_id", f"{key}:{len(msgs)}"))
                msgs.append(TraceMsg(
                    msg_id=dia_id,
                    session_id=key,
                    date=str(conv.get(f"{key}_date_time", "")),
                    date_idx=len(msgs),
                    role=str(turn.get("speaker", "user")),
                    content=str(turn.get("text", "")),
                    tokens=clean_tokens(str(turn.get("text", ""))),
                ))
        by = {m.msg_id for m in msgs}
        tasks: List[TraceTask] = []
        for q_idx, qa in enumerate(sample.get("qa", [])):
            needed = tuple(d for d in qa.get("evidence", []) if d in by)
            tasks.append(TraceTask(
                task_id=f"{sample['sample_id']}:q{q_idx}",
                question=str(qa.get("question", "")),
                query_tokens=clean_tokens(str(qa.get("question", ""))),
                needed_ids=needed,
                scope=str(qa.get("category", "unknown")),
                date="",
            ))
        traces.append(Trace(sample_id=str(sample["sample_id"]),
                            msgs=tuple(msgs), tasks=tuple(tasks)))
        if limit is not None and len(traces) >= limit:
            break
    return traces


# ---------------------------------------------------------------------------
# scoring / exposure engines (deterministic, no model calls)
# ---------------------------------------------------------------------------

def recency_scores(msgs: Sequence[TraceMsg]) -> Dict[str, float]:
    """Newer messages score higher (later date_idx -> larger score)."""
    return {m.msg_id: float(m.date_idx) for m in msgs}


def decay_scores(msgs: Sequence[TraceMsg], half_life: float = 60.0) -> Dict[str, float]:
    """Exposure-refreshed decay (dynamic engine: re-exposure re-admits)."""
    scores: Dict[str, float] = {}
    refresh: Dict[str, int] = {}
    for m in msgs:
        age = m.date_idx - refresh.get(m.msg_id, 0)
        scores[m.msg_id] = 1.0 / (1.0 + age / half_life)
        refresh[m.msg_id] = m.date_idx
    return scores


def bm25_scores(msgs: Sequence[TraceMsg],
                query_tokens: Sequence[str]) -> Dict[str, float]:
    """BM25 with the official LongMemEval parameters (K1=1.5, B=0.75)."""
    if not query_tokens:
        return {m.msg_id: 0.0 for m in msgs}
    df: Dict[str, int] = {}
    lens: List[int] = []
    for m in msgs:
        lens.append(len(m.tokens))
        for t in set(m.tokens):
            df[t] = df.get(t, 0) + 1
    avgdl = mean(lens) if lens else 1.0
    n = max(len(msgs), 1)
    scores: Dict[str, float] = {}
    for m in msgs:
        tf: Dict[str, int] = {}
        for t in m.tokens:
            tf[t] = tf.get(t, 0) + 1
        dl = max(len(m.tokens), 1)
        s = 0.0
        for t in query_tokens:
            if t not in tf:
                continue
            f = tf[t]
            idf = math.log(1.0 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
            s += idf * (f * (1.5 + 1.0)) / (f + 1.5 * (1.0 - 0.75 + 0.75 * dl / avgdl))
        scores[m.msg_id] = s
    return scores


def engine_workspaces(trace: Trace, budget: int = 12,
                      engine: str = "recency") -> Dict[str, Tuple[Tuple[str, ...], Dict[str, int]]]:
    """For every task: the workspace the engine would expose at task time.
    Returns {task_id: (exposed_ids, position_by_id)}."""
    if engine == "bm25":
        out: Dict[str, Tuple[Tuple[str, ...], Dict[str, int]]] = {}
        for t in trace.tasks:
            scores = bm25_scores(trace.msgs, t.query_tokens)
            ranking = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:budget]
            positions = {mid: i for i, (mid, _) in enumerate(ranking)}
            out[t.task_id] = (tuple(mid for mid, _ in ranking), positions)
        return out
    if engine == "recency":
        scores = recency_scores(trace.msgs)
    elif engine == "decay":
        scores = decay_scores(trace.msgs)
    else:
        raise KeyError(engine)
    out = {}
    for t in trace.tasks:
        ranking = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:budget]
        positions = {mid: i for i, (mid, _) in enumerate(ranking)}
        out[t.task_id] = (tuple(mid for mid, _ in ranking), positions)
    return out


# ---------------------------------------------------------------------------
# instruments + mechanism incidence (per trace)
# ---------------------------------------------------------------------------

@dataclass
class TraceAudit:
    trace_id: str
    n_msgs: int
    n_tasks: int
    budget: int
    engine: str
    rows: List[Dict]                              # per-task decision log
    exposed: Dict[str, int]                       # msg_id -> tasks exposed
    positions: Dict[str, List[int]]               # msg_id -> positions
    needed: Dict[str, int]                        # msg_id -> tasks needing it
    archived: Tuple[str, ...]
    metrics: Dict[str, float]


def _archive_decision(msgs: Sequence[TraceMsg], engine: str,
                      budget: int) -> Tuple[str, ...]:
    """Write-time archive: keep top-budget by the engine's score; the rest are
    archived (then possibly restored by exposure). Retrieval engines have no
    persistence governance -> nothing archived."""
    if engine == "bm25":
        return ()
    if engine == "recency":
        scores = recency_scores(msgs)
    else:
        scores = decay_scores(msgs)
    ranking = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:budget]
    keep = {mid for mid, _ in ranking}
    return tuple(m.msg_id for m in msgs if m.msg_id not in keep)


def audit_trace(trace: Trace, budget: int = 12, engine: str = "recency") -> TraceAudit:
    by = by_id(trace)
    workspaces = engine_workspaces(trace, budget, engine)
    archived = _archive_decision(trace.msgs, engine, budget)
    archived_set = set(archived)

    needed: Counter = Counter()
    for t in trace.tasks:
        for mid in t.needed_ids:
            needed[mid] += 1
    ever_needed = {mid for mid, c in needed.items() if c > 0}

    exposed: Counter = Counter()
    positions: Dict[str, List[int]] = defaultdict(list)
    rows: List[Dict] = []

    for t in trace.tasks:
        exposed_ids, pos = workspaces[t.task_id]
        for mid in exposed_ids:
            exposed[mid] += 1
            positions[mid].append(pos[mid])
        hit = any(mid in exposed_ids for mid in t.needed_ids)
        stale = [mid for mid in exposed_ids if needed[mid] == 0]
        tokens = sum(len(by[mid].tokens) for mid in exposed_ids if mid in by)
        rows.append({
            "task_id": t.task_id,
            "scope": t.scope,
            "needed_ids": list(t.needed_ids),
            "exposed_ids": list(exposed_ids),
            "hit": int(hit),
            "stale_exposed": stale,
            "tokens": tokens,
            "decision": ("keep" if hit else
                         "restore_needed" if any(
                             mid in archived_set for mid in t.needed_ids)
                         else "expose"),
        })

    # co-exposure sets (per exposed memory, the workspace it rode in on)
    co_exposed: Dict[str, List[Tuple[str, ...]]] = defaultdict(list)
    for t in trace.tasks:
        exposed_ids = workspaces[t.task_id][0]
        for mid in exposed_ids:
            co_exposed[mid].append(exposed_ids)

    metrics: Dict[str, float] = {}

    # 1. hitchhiker: never-needed but co-exposed with a needed message
    co_with_needed = set()
    for mid, sets in co_exposed.items():
        if mid in ever_needed:
            continue
        for ws in sets:
            if any(n in ws for n in ever_needed):
                co_with_needed.add(mid)
                break
    hitchhiker_pool = {mid for mid in co_exposed if mid not in ever_needed}
    metrics["hitchhiker_rate"] = (
        len(co_with_needed) / len(hitchhiker_pool)) if hitchhiker_pool else 0.0

    # 2. stale version: needed-old exposed rate + newer distractor exposure
    metrics["needed_exposed_rate"] = (
        sum(1 for mid in ever_needed if exposed[mid] > 0) / len(ever_needed)
        if ever_needed else 0.0)
    upd = [t for t in trace.tasks if t.scope == "knowledge-update"]
    if upd:
        needed_sids = {mid.split(":")[1] for t in upd for mid in t.needed_ids}
        distractor_exposed = distractor_pool = 0
        for t in upd:
            needed_sid_t = {mid.split(":")[1] for mid in t.needed_ids}
            for mid in workspaces[t.task_id][0]:
                sid = mid.split(":")[1]
                if sid in needed_sids or sid in needed_sid_t:
                    continue
                m = by.get(mid)
                if m is None:
                    continue
                m_tokens = set(m.tokens)
                if len(m_tokens) < 3:
                    continue
                for nid in t.needed_ids:
                    n = by.get(nid)
                    if n is None or n.session_id == m.session_id:
                        continue
                    if len(m_tokens & set(n.tokens)) >= 3 and m.date_idx > n.date_idx:
                        distractor_pool += 1
                        distractor_exposed += 1
                        break
        metrics["stale_version_distractor_rate"] = (
            distractor_exposed / distractor_pool) if distractor_pool else 0.0
        old_pool = sum(len(t.needed_ids) for t in upd)
        old_exposed = sum(1 for t in upd for mid in t.needed_ids
                          if exposed[mid] > 0)
        metrics["stale_version_needed_old_rate"] = (
            old_exposed / old_pool) if old_pool else 0.0
    else:
        metrics["stale_version_distractor_rate"] = 0.0
        metrics["stale_version_needed_old_rate"] = 0.0

    # 3. rare protective memory: needed from the low-frequency session tail
    sess_freq: Counter = Counter(m.session_id for m in trace.msgs)
    if sess_freq and len(sess_freq) >= 4:
        q1 = statistics.quantiles(sorted(sess_freq.values()), n=4)[0]
    else:
        q1 = 0
    rare_needed = {mid for mid in ever_needed
                   if sess_freq[by[mid].session_id] <= q1}
    metrics["rare_protective_rate"] = (
        len(rare_needed) / len(ever_needed)) if ever_needed else 0.0
    metrics["rare_protective_exposed_rate"] = (
        sum(1 for mid in rare_needed if exposed[mid] > 0) / len(rare_needed)
        if rare_needed else 0.0)

    # 4. scope shift: needed memory whose temporal scope lies beyond the
    #    sample's recent support (oldest quartile of the timeline)
    scope_shift = 0
    needed_total = sum(len(t.needed_ids) for t in trace.tasks)
    dates = sorted(m.date_idx for m in trace.msgs)
    if len(dates) >= 4:
        q1 = statistics.quantiles(dates, n=4)[0]
    else:
        q1 = 0
    for t in trace.tasks:
        for mid in t.needed_ids:
            m = by.get(mid)
            if m is not None and m.date_idx <= q1:
                scope_shift += 1
    metrics["scope_shift_rate"] = (
        scope_shift / needed_total) if needed_total else 0.0

    # 5. co-memory competition: density + tail-position rate of needed memories
    density: List[int] = []
    tail = 0
    for t in trace.tasks:
        ws, pos = workspaces[t.task_id]
        for mid in t.needed_ids:
            if mid in pos:
                density.append(len(ws))
                if pos[mid] >= max(1, budget // 2):
                    tail += 1
    metrics["co_exposure_density"] = (
        statistics.mean(density)) if density else 0.0
    metrics["needed_tail_position_rate"] = (
        tail / len(density)) if density else 0.0

    # archive/restore/rollback
    metrics["archive_error_rate"] = (
        sum(1 for mid in ever_needed if mid in archived_set) / len(ever_needed)
        if ever_needed else 0.0)
    restored = sum(1 for t in trace.tasks
                   for mid in t.needed_ids if mid in archived_set)
    metrics["restore_events_per_task"] = (
        restored / len(trace.tasks)) if trace.tasks else 0.0
    metrics["task_hit_rate"] = (
        sum(r["hit"] for r in rows) / len(rows)) if rows else 0.0

    return TraceAudit(
        trace_id=trace.sample_id,
        n_msgs=len(trace.msgs),
        n_tasks=len(trace.tasks),
        budget=budget,
        engine=engine,
        rows=rows,
        exposed=dict(exposed),
        positions=dict(positions),
        needed=dict(needed),
        archived=archived,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------

METRIC_NAMES = (
    "hitchhiker_rate", "needed_exposed_rate", "stale_version_distractor_rate",
    "stale_version_needed_old_rate", "rare_protective_rate",
    "rare_protective_exposed_rate", "scope_shift_rate", "co_exposure_density",
    "needed_tail_position_rate", "archive_error_rate",
    "restore_events_per_task", "task_hit_rate",
)


def aggregate(audits: Sequence[TraceAudit]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for name in METRIC_NAMES:
        values = [a.metrics[name] for a in audits]
        if len(values) >= 4:
            q = statistics.quantiles(values, n=4)
            q25, q75 = q[0], q[2]
        else:
            q25 = q75 = 0.0
        out[name] = {
            "median": statistics.median(values),
            "mean": statistics.mean(values),
            "q25": q25,
            "q75": q75,
            "n": float(len(values)),
        }
    return out


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
    parser.add_argument("--engine", choices=("recency", "decay", "bm25"),
                        default="bm25",
                        help="primary engine is bm25 (the official protocol's "
                             "retrieval layer); recency/decay are the "
                             "no-retrieval contrast rows")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path("results/mechanism_audit.json"))
    args = parser.parse_args()

    datasets: List[Tuple[str, List[Trace]]] = [
        ("longmemeval_s", load_longmemeval_s(args.longmemeval, args.limit)),
        ("locomo", load_locomo(args.locomo, args.limit)),
    ]
    result: Dict = {"config": {
        "budget": args.budget, "engine": args.engine,
        "longmemeval": str(args.longmemeval), "locomo": str(args.locomo),
        "limit": args.limit,
    }}
    for name, traces in datasets:
        if not traces:
            continue
        audits = [audit_trace(t, args.budget, args.engine) for t in traces]
        result[name] = {"n_traces": len(audits), "metrics": aggregate(audits)}
        print(f"== {name} ({len(audits)} traces) ==")
        for k, v in result[name]["metrics"].items():
            print(f"  {k:32s} median={v['median']:.3f} "
                  f"[{v['q25']:.3f},{v['q75']:.3f}] mean={v['mean']:.3f}")
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")


if __name__ == "__main__":
    main()
