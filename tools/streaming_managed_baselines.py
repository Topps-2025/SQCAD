"""Same-budget streaming memory managers on the public contract (round-5
cloud supplement, 34- report; direct answer to the round-3/4 reviewer
finding that the storage-matched baseline is a weak recency-12 store).

Rows (new module only; frozen contract untouched):
  bm25_stream  -- streaming store admitted by ONLINE lexical salience
                  (message self-information under the idf accumulated from
                  messages seen so far -- strictly online, no look-ahead),
                  evicted replace-worst; workspace per task = top-BUDGET
                  of the CURRENT STORE under the frozen bm25_scores.
  dense_stream -- same manager with Qwen3-Embedding-0.6B: salience =
                  online mean cosine similarity of a message to the
                  messages seen so far (msg_sims from the precompute
                  cache), workspace = top-BUDGET of the store under the
                  cached query cos-sims (see
                  tools/precompute_dense_qwen.py --scores-out).

Mechanics (pre-registered, deterministic, no thresholds beyond the
storage-matched token budget -- the governance row's observed store:
1631 LME-S / 1646 LoCoMo, from the frozen public contract artifacts):
  1. message admission (chronological, online): for each message as it
     arrives compute its salience (bm25: online-idf self-information;
     dense: online mean-cos to past messages); admit if the store has
     room, else replace the lowest-salience stored item (ties: oldest
     first).  Items larger than the budget are never stored.
  2. task time (chronological): workspace = top-BUDGET of the CURRENT
     STORE under the frozen scorer (bm25_scores over the full message set
     restricted to the store -- idf identical to the frozen bm25 row;
     dense: cached query cos-sims); after the workspace, relevance
     feedback: un-stored messages ranked by the current query score are
     admitted under the same replace-worst rule (legitimate post-query
     storage; a no-op for one-shot traces, load-bearing for multi-task
     conversations like LoCoMo).
  3. Lifecycle counters: evictions -> archives; re-admission of a
     previously evicted id -> restores.

Reference rows (same frozen runner, recomputed for exact comparability):
  sqcad (governance row), bm25 (index-everything retrieval row).
Zero-diff expectation: recomputed frozen rows must match the frozen
artifacts field-for-field (25- deterministic discipline).

Output: JSON {config, datasets: {longmemeval_s: {...}, locomo: {...}}}
with per-row aggregates + per-trace evals + paired studentized bootstrap
CIs (new rows vs sqcad, n_boot=2000, pre-registered seeds 20260812 /
20260817) and LoCoMo QA files for the frozen official scorer.

Usage (PYTHONPATH=src):
  python tools/streaming_managed_baselines.py \
      --longmemeval <path> --locomo <path> \
      --dense-scores-lme <path> --dense-scores-locomo <path> \
      --qa-out-dir results/locomo_qa_stream \
      --out results/streaming_managed_baselines.json
Then LoCoMo official F1 (frozen upstream scorer):
  python tools/run_locomo_official_scorer_portable.py \
      --eval-file datasets/locomo_eval/evaluation.py \
      --pred-dir results/locomo_qa_stream \
      --out results/locomo_official_qa_stream.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqcad.bootstrap_ci import paired_seed_diff_ci
from sqcad.public_unified_contract import (
    BUDGET, PolicyResult, _qa_meta_by_task, _storage_tokens, aggregate,
    evaluate_trace, mask_lme_chronological, needed_free, run_policy,
    trace_features, write_locomo_qa_files,
)
from sqcad.public_v2_rule import run_v2_policy
from sqcad.trace_grounded_runner import (
    bm25_scores, load_locomo, load_longmemeval_s,
)

N_BOOT = 2000
SEEDS = (20260812, 20260817)
# Storage-matched budget: the governance row's observed persistent store
# (frozen artifacts results/public_unified_contract.json): LME-S 1631
# tokens, LoCoMo 1646 tokens.
BUDGET_TOKENS = {"longmemeval_s": 1631, "locomo": 1646}
METRICS = ("hit_rate", "recall_mean", "tokens_mean")
STREAM_ROWS = ("bm25_stream", "dense_stream",
               "lru_stream", "recency_stream", "hybrid_stream")
# G-6: storage-matched controls sharing the engine, budget and admission rule
# with bm25_stream; only the retention signal differs.  `recency_stream` is
# retained but is NOT independent: it is provably the same policy as
# `lru_stream` under this rank-only eviction rule (see make_recency_salience),
# so the gate reports TWO independent controls, not three.
STORAGE_MATCHED_ROWS = ("lru_stream", "recency_stream", "hybrid_stream")
INDEPENDENT_STORAGE_MATCHED_ROWS = ("lru_stream", "hybrid_stream")


def _admit(store: Dict[str, float], order: Dict[str, int],
           salience: Dict[str, float], sizes: Dict[str, int],
           budget: int, lifecycle: Dict[str, int], ever_evicted: set,
           mid: str) -> None:
    """Admit mid under the replace-worst rule (ties: oldest first)."""
    if sizes[mid] > budget:
        return
    used = sum(sizes[k] for k in store)
    if used + sizes[mid] <= budget:
        store[mid] = salience[mid]
        if mid in ever_evicted:
            lifecycle["restores"] += 1
        else:
            ever_evicted.add(mid)
        return
    worst = min(store, key=lambda k: (salience.get(k, 0.0), -order[k]))
    if salience.get(worst, 0.0) > salience[mid]:
        return
    del store[worst]
    lifecycle["archives"] += 1
    ever_evicted.add(worst)
    store[mid] = salience[mid]
    if mid in ever_evicted:
        lifecycle["restores"] += 1
    else:
        ever_evicted.add(mid)


def stream_engine(msgs: Sequence, tasks: Sequence,
                  salience_fn: Callable[[Sequence, int], Dict[str, float]],
                  task_scorer: Callable[[Sequence, object],
                                        Dict[str, float]],
                  policy: str, budget_tokens: int) -> PolicyResult:
    """Online-salience streaming store with a token budget (module doc).
    salience_fn(msgs, i) -> {mid: salience} for message i given the
    messages seen so far (strictly online).  task_scorer(msgs, task) ->
    {msg_id: score} over the FULL message set (frozen idf / cached dense
    sims); scores restricted to the store for the workspace."""
    sizes = {m.msg_id: len(m.tokens) for m in msgs}
    order = {m.msg_id: i for i, m in enumerate(msgs)}
    store: Dict[str, float] = {}
    sal: Dict[str, float] = {}
    ever_evicted = set()
    ws: Dict[str, Tuple[str, ...]] = {}
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}
    # Salience functions that re-score residents (LRU, recency) declare it, so
    # the engine hands them the live salience map instead of guessing by arity.
    wants_state = bool(getattr(salience_fn, "wants_state", False))
    touch = getattr(salience_fn, "touch", None)

    # 1. message admission (chronological, strictly online)
    for i, m in enumerate(msgs):
        s = salience_fn(msgs, i, sal) if wants_state else salience_fn(msgs, i)
        sal.update(s)
        _admit(store, order, sal, sizes, budget_tokens, lifecycle,
               ever_evicted, m.msg_id)

    # 2. task time (chronological): workspace + query-time feedback
    for t in tasks:
        scores = task_scorer(msgs, t)
        ranked = sorted(((mid, scores.get(mid, 0.0)) for mid in store),
                        key=lambda kv: (-kv[1], kv[0]))
        ws[t.task_id] = tuple(mid for mid, _ in ranked[:BUDGET])
        # Recency-family policies must see a *use* as a refresh, otherwise the
        # eviction order stays arrival order and "LRU" degenerates to FIFO.
        if touch is not None:
            for mid in ws[t.task_id]:
                touch(mid, sal)
        for mid, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])):
            if mid in store:
                continue
            _admit(store, order, sal, sizes, budget_tokens, lifecycle,
                   ever_evicted, mid)

    retained = tuple(store)
    return PolicyResult(
        policy=policy, workspaces=ws, storage_ids=retained,
        storage_tokens=_storage_tokens(msgs, retained),
        lifecycle=lifecycle)


def make_bm25_salience():
    """Incremental online-idf self-information: idf over messages 0..i,
    maintained incrementally (strictly online, O(tokens) per message)."""
    df: Dict[str, int] = {}
    n = 0

    def _s(msgs: Sequence, i: int) -> Dict[str, float]:
        nonlocal n
        m = msgs[i]
        uniq = set(m.tokens)
        for t in uniq:
            df[t] = df.get(t, 0) + 1
        n += 1
        s = 0.0
        for t in uniq:
            s += math.log(1.0 + (n - df.get(t, 0) + 0.5) /
                          (df.get(t, 0) + 0.5))
        return {m.msg_id: s}
    return _s


def bm25_scorer(msgs: Sequence, task: object) -> Dict[str, float]:
    return bm25_scores(msgs, task.query_tokens)


# ---------------------------------------------------------------------------
# G-6 storage-matched controls.  Same engine, same token budget, same
# replace-worst admission -- only the salience signal differs, so any gap is
# attributable to the retention signal and not to a storage advantage.
# ---------------------------------------------------------------------------

def make_lru_salience():
    """True LRU: salience = logical time of last *use*.

    Admission stamps the clock; `touch` re-stamps it whenever the item enters
    a workspace.  Without that second half the eviction order never leaves
    arrival order and this is FIFO wearing an LRU label -- the engine calls
    `touch` at task time for exactly this reason.
    """
    clock = 0

    def _s(msgs: Sequence, i: int, sal: Dict[str, float]) -> Dict[str, float]:
        nonlocal clock
        clock += 1
        return {msgs[i].msg_id: float(clock)}

    def _touch(mid: str, sal: Dict[str, float]) -> None:
        nonlocal clock
        clock += 1
        sal[mid] = float(clock)

    _s.wants_state = True
    _s.touch = _touch
    return _s


def make_recency_salience(half_life: float = 50.0):
    """Exponential time decay over the ONLINE prefix.

    NOT AN INDEPENDENT CONTROL -- kept only to document a measured negative.

    Two successive versions of this row came out byte-identical to
    `lru_stream` on every metric of both datasets, for two different reasons.
    The first scored 2^(-(len(msgs)-1-i)/half_life), reading total stream
    length at admission time: a future leak, and monotone in `i`, so it
    collapsed onto FIFO.  Fixing that (decay the live residents instead, as
    below) did NOT separate the rows, because the eviction rule at `_admit`
    reads only the ARGMIN of (salience, -order) -- never the magnitudes.

    Decaying every resident by a common positive factor is a monotone
    transform of the LRU clock, so it preserves that argmin.  Verified: over
    40 admissions plus interleaved touches, the induced ranking differs at 3
    of 5 touch steps, yet the evicted element is the same at every single
    step.  Graded recency is therefore the SAME POLICY as LRU under a
    rank-only replace-worst rule; it can only differ once it competes against
    a second, non-recency signal, which is exactly `hybrid_stream`.

    G-6 consequently reports TWO independent storage-matched controls
    (`lru_stream`, `hybrid_stream`), not three.  Counting this row as a third
    would pad the control count with a duplicate of the first.
    """
    def _s(msgs: Sequence, i: int, sal: Dict[str, float]) -> Dict[str, float]:
        decay = 2.0 ** (-1.0 / half_life)
        out = {mid: v * decay for mid, v in sal.items()}
        out[msgs[i].msg_id] = 1.0
        return out

    def _touch(mid: str, sal: Dict[str, float]) -> None:
        sal[mid] = 1.0

    _s.wants_state = True
    _s.touch = _touch
    return _s


def make_hybrid_salience(half_life: float = 50.0, w_recency: float = 0.5):
    """Hybrid recency x informativeness: the geometric-style blend of the
    online-idf self-information signal and the recency signal.  This is the
    strongest storage-matched control -- it has both signals the paper's
    mechanism claims to need, at identical storage."""
    bm25_sal = make_bm25_salience()

    # Recency is tracked in a private map so the blend keeps its own decayed
    # component; the returned salience is the blended value the store evicts on.
    rec: Dict[str, float] = {}
    info_of: Dict[str, float] = {}
    decay = 2.0 ** (-1.0 / half_life)

    def _blend(mid: str) -> float:
        return float((1.0 - w_recency) * info_of.get(mid, 0.0)
                     + w_recency * rec.get(mid, 0.0) * 100.0)

    def _s(msgs: Sequence, i: int, sal: Dict[str, float]) -> Dict[str, float]:
        mid = msgs[i].msg_id
        info_of[mid] = bm25_sal(msgs, i).get(mid, 0.0)
        for k in list(rec):
            rec[k] *= decay
        rec[mid] = 1.0
        return {k: _blend(k) for k in rec}

    def _touch(mid: str, sal: Dict[str, float]) -> None:
        rec[mid] = 1.0
        sal[mid] = _blend(mid)

    _s.wants_state = True
    _s.touch = _touch
    return _s


class DenseScores:
    """Cosine scores from a precomputed cache (precompute_dense_qwen.py
    --scores-out): {sample_id: {task_id: {msg_id: score}}} plus
    msg_sims {sample_id: {msg_id: online mean cos to past messages}}."""

    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.scores = data["scores"]
        self.msg_sims = data.get("msg_sims", {})
        self.model = data.get("model", "?")
        self.dataset = data.get("dataset", "?")

    def salience(self, sample_id: str):
        sims = self.msg_sims.get(sample_id, {})

        def _s(msgs: Sequence, i: int) -> Dict[str, float]:
            mid = msgs[i].msg_id
            return {mid: sims.get(mid, 0.0)}
        return _s

    def scorer(self, sample_id: str):
        qs = self.scores[sample_id]

        def _s(msgs: Sequence, task: object) -> Dict[str, float]:
            return dict(qs[task.task_id])
        return _s


def run_dataset(name: str, data_path: Path, dense_scores: Path | None,
                qa_out: Path | None) -> dict:
    traces = (load_longmemeval_s(data_path)
              if name == "longmemeval_s" else load_locomo(data_path))
    budget = BUDGET_TOKENS[name]
    ds = DenseScores(dense_scores) if dense_scores is not None else None
    qa_meta = _qa_meta_by_task(name, data_path)

    per: Dict[str, List[dict]] = {r: [] for r in STREAM_ROWS + ("sqcad", "bm25")}
    qa_pairs: List[Tuple[object, PolicyResult]] = []
    for trace in traces:
        masked, _ = (mask_lme_chronological(trace)
                     if name == "longmemeval_s" else (trace, {}))
        visible_ids = {m.msg_id for m in masked.msgs}
        msgs = list(masked.msgs)
        tasks = needed_free(masked.tasks)
        feats = trace_features(masked.msgs)
        if not tasks:
            continue

        for row in STREAM_ROWS:
            if row == "bm25_stream":
                salience_fn = make_bm25_salience()
                scorer = bm25_scorer
            elif row in STORAGE_MATCHED_ROWS:
                # identical retrieval scorer as bm25_stream, so the ONLY
                # difference is the retention signal (G-6 storage-matched)
                salience_fn = {"lru_stream": make_lru_salience,
                               "recency_stream": make_recency_salience,
                               "hybrid_stream": make_hybrid_salience}[row]()
                scorer = bm25_scorer
            else:
                if ds is None or trace.sample_id not in ds.scores:
                    continue
                salience_fn = ds.salience(trace.sample_id)
                scorer = ds.scorer(trace.sample_id)
            res = stream_engine(msgs, tasks, salience_fn, scorer, row,
                                budget)
            per[row].append(evaluate_trace(res, masked, visible_ids))
            if name == "locomo" and qa_out is not None:
                qa_pairs.append((trace, res))
        for row in ("sqcad", "bm25"):
            res = run_policy(row, masked, feats=feats)
            per[row].append(evaluate_trace(res, masked, visible_ids))
            if name == "locomo" and qa_out is not None:
                qa_pairs.append((trace, res))

    if qa_out is not None and qa_pairs:
        # flat per-policy prediction files (official scorer globs
        # predictions_*.json directly in --pred-dir; frozen pattern of
        # public_v2_rule.py / public_online_baselines.py)
        write_locomo_qa_files(qa_pairs, qa_meta, qa_out)

    out: dict = {"n_traces": len(per["sqcad"]), "rows": {}}
    for row, evals in per.items():
        if not evals:
            continue
        out["rows"][row] = {"aggregate": aggregate(row, evals)}
        for m in METRICS:
            out["rows"][row][m] = [e[m] for e in evals if e[m] is not None]
    # Duplicate-policy audit.  Two rows that agree to the last bit on every
    # metric are the same policy wearing two labels; reporting them as separate
    # storage-matched controls would inflate the control count.  This records
    # the equivalence in the artifact instead of leaving it to a reader.
    out["duplicate_rows"] = []
    names = [r for r in STREAM_ROWS if r in out["rows"]]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            same = []
            for m in METRICS:
                va, vb = out["rows"][a][m], out["rows"][b][m]
                if len(va) == len(vb) and all(
                        x == y for x, y in zip(va, vb)):
                    same.append(m)
            if len(same) == len(METRICS):
                out["duplicate_rows"].append({
                    "rows": [a, b],
                    "note": ("identical on every per-trace value of every "
                             "metric -- same policy, not an independent "
                             "control"),
                })
    out["significance_vs_sqcad"] = {}
    for row in STREAM_ROWS:
        if row not in out["rows"]:
            continue
        entry = {}
        for metric in METRICS:
            ea, eb = out["rows"][row][metric], out["rows"]["sqcad"][metric]
            if len(ea) != len(eb) or len(ea) < 2:
                entry[metric] = {"mean_diff": None, "note": "unit mismatch or n<2"}
                continue
            ent = {}
            for seed in SEEDS:
                ci = paired_seed_diff_ci(ea, eb, n_boot=N_BOOT, seed=seed,
                                         alpha=0.05, method="studentized")
                ci["significant"] = bool(
                    ci.get("ci_low", 0) > 0.0 or ci.get("ci_high", 0) < 0.0)
                ent[str(seed)] = ci
            ent["n_units"] = len(ea)
            ent["mean_diff"] = sum(ea) / len(ea) - sum(eb) / len(eb)
            entry[metric] = ent
        out["significance_vs_sqcad"][row] = entry
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--longmemeval", type=Path, required=True)
    ap.add_argument("--locomo", type=Path, required=True)
    ap.add_argument("--dense-scores-lme", type=Path, default=None)
    ap.add_argument("--dense-scores-locomo", type=Path, default=None)
    ap.add_argument("--qa-out-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", choices=("longmemeval_s", "locomo"),
                    default=None, help="run a single dataset (smoke)")
    args = ap.parse_args()

    payload: dict = {
        "config": {
            "budget_tokens": BUDGET_TOKENS,
            "workspace_budget": BUDGET,
            "n_boot": N_BOOT, "alpha": 0.05, "method": "studentized",
            "seeds": list(SEEDS),
            "note": ("score-based streaming store at the governance row's "
                     "observed store budget (storage-matched, stronger "
                     "than the recency-12 store); workspace = top-BUDGET "
                     "over the current store; frozen contract untouched"),
        },
        "datasets": {},
    }
    for name, path, ds in (
        ("longmemeval_s", args.longmemeval, args.dense_scores_lme),
        ("locomo", args.locomo, args.dense_scores_locomo),
    ):
        if args.only is not None and name != args.only:
            continue
        qa_out = (args.qa_out_dir / name) if args.qa_out_dir else None
        payload["datasets"][name] = run_dataset(name, path, ds, qa_out)
        print(f"== {name} ==")
        rows = payload["datasets"][name]["rows"]
        for row, r in rows.items():
            a = r["aggregate"]
            print(f"  {row:12s} {a}")
        for row, sig in payload["datasets"][name]["significance_vs_sqcad"].items():
            for metric, e in sig.items():
                if e.get("mean_diff") is None:
                    continue
                c = e["20260812"]
                flag = "*" if c["significant"] else ""
                print(f"  {row:12s} - sqcad {metric:11s}: "
                      f"{e['mean_diff']:+.4f} [{c['ci_low']:+.4f}, "
                      f"{c['ci_high']:+.4f}]{flag}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
