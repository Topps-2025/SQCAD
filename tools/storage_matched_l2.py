"""Storage-matched L2 rows (12-slot cap on the retrieval baselines).

Round-2 leftover (32- §7.3): the main-table BM25/dense rows index the full
store (74,092 tokens) while the SQCAD row operates a 12-slot score-eviction
store (1,631 tokens), so part of the coverage gap could be a storage-budget
artifact.  This script re-runs BM25 and dense with the same 12-slot budget:
the retrieval pool is restricted to the most recent 12 messages (recency
cap -- the assumption-free storage baseline; SQCAD's own eviction rule is
strictly stronger), workspaces are drawn from that pool, and storage is
priced at the 12 messages' token count.

Rows: sqcad (frozen rule, reference), bm25_s12, dense_s12 (dense
candidates intersected with the 12-slot pool; candidates come from the
Qwen3-Embedding-0.6B tier-B cache -- the frozen MiniLM cache is not on
this machine, noted in the artifact).

Significance: paired studentized bootstrap vs sqcad, pre-registered seeds
20260812 / 20260817, n_boot=2000 -- same protocol as the frozen contract.

Usage: python tools/storage_matched_l2.py
Writes remote_results/lifecycle_audit/storage_matched_l2.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sqcad.bootstrap_ci import paired_seed_diff_ci
from src.sqcad.public_unified_contract import (
    ALPHA, BUDGET, N_BOOT, PolicyResult,
    _retrieval_engine, _storage_tokens, bm25_scores,
    mask_lme_chronological, run_policy, evaluate_trace, trace_features,
)
from src.sqcad.trace_grounded_runner import (
    load_longmemeval_s, load_locomo,
)

LME_DATA = Path("D:/Engineering/SQCAD/database/datasets/"
                "LongMemEval/longmemeval_s_cleaned.json")
LOCOMO_DATA = Path("D:/Engineering/SQCAD/database/datasets/"
                   "LoCoMo/locomo10.json")
CACHE_06 = Path("remote_results/cloud_dense_20260820/dense_cache_0.6B.json")
OUT = Path("remote_results/lifecycle_audit/storage_matched_l2.json")
ROWS = ("sqcad", "bm25_s12", "dense_s12")
PAIRS = (("bm25_s12", "sqcad"), ("dense_s12", "sqcad"))
METRICS = ("hit_rate", "recall_mean", "tokens_mean", "storage_tokens",
           "rare_recall")
SEEDS = (20260812, 20260817)


def _recent12(trace):
    """The 12 most recent messages of a masked trace (chronological order)."""
    ordered = sorted(trace.msgs, key=lambda m: m.date_idx)
    return ordered[-BUDGET:]


def run_rows(name: str, data_path: Path, cache06: dict) -> dict:
    traces = (load_longmemeval_s(data_path)
              if name == "longmemeval_s" else load_locomo(data_path))
    per: dict = {r: [] for r in ROWS}
    for trace in traces:
        masked, _ = (mask_lme_chronological(trace)
                     if name == "longmemeval_s" else (trace, {}))
        visible_ids = {m.msg_id for m in masked.msgs}
        feats = trace_features(masked.msgs)

        res_sq = run_policy("sqcad", masked, feats=feats)
        if res_sq is not None:
            per["sqcad"].append(evaluate_trace(res_sq, masked, visible_ids))

        s12 = _recent12(masked)
        s12_ids = [m.msg_id for m in s12]
        s12_set = set(s12_ids)

        # bm25 restricted to the 12-slot pool: score within the pool only
        res_b = _retrieval_engine(s12, masked.tasks, bm25_scores, "bm25_s12")
        per["bm25_s12"].append(
            evaluate_trace(res_b, masked, visible_ids))

        # dense candidates intersected with the 12-slot pool
        ws_d = {}
        for t in masked.tasks:
            cand = cache06.get(trace.sample_id, {}).get(t.task_id, ())
            ws_d[t.task_id] = tuple(mid for mid in cand if mid in s12_set)
        res_d = PolicyResult(
            policy="dense_s12",
            workspaces=ws_d,
            storage_ids=tuple(s12_ids),
            storage_tokens=_storage_tokens(masked.msgs, s12_set),
            lifecycle={"archives": 0, "restores": 0, "probes": 0,
                       "fallbacks": 0})
        per["dense_s12"].append(evaluate_trace(res_d, masked, visible_ids))

    out: dict = {"n_traces": len(traces), "rows": {}}
    for row, evals in per.items():
        out["rows"][row] = {
            m: [e[m] for e in evals if e[m] is not None]
            for m in METRICS}
        out["rows"][row]["means"] = {
            m: (sum(v) / len(v) if v else None)
            for m, v in out["rows"][row].items() if m != "means"}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lme", type=Path, default=LME_DATA)
    ap.add_argument("--locomo", type=Path, default=LOCOMO_DATA)
    ap.add_argument("--cache06", type=Path, default=CACHE_06)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    cache06 = json.loads(args.cache06.read_text(encoding="utf-8"))
    cache06 = cache06.get("cache", cache06)

    payload: dict = {
        "config": {
            "budget": BUDGET, "cap": "recency-12 (most recent 12 msgs)",
            "n_boot": N_BOOT, "alpha": ALPHA, "method": "studentized",
            "seeds": list(SEEDS),
            "note": ("storage-matched rows: retrieval pool restricted to "
                     "the 12 most recent messages; dense_s12 intersects "
                     "the Qwen3-Embedding-0.6B tier-B candidates with the "
                     "pool (frozen MiniLM cache not available locally); "
                     "sqcad is the frozen reference row"),
        },
        "datasets": {},
    }
    for name, path in (("longmemeval_s", args.lme), ("locomo", args.locomo)):
        data = run_rows(name, path, cache06)
        rows = data["rows"]
        sig: dict = {}
        for metric in METRICS:
            sig[metric] = {}
            for a, b in PAIRS:
                ea, eb = rows[a][metric], rows[b][metric]
                if len(ea) != len(eb) or len(ea) < 2:
                    sig[metric][f"{a}_vs_{b}"] = {
                        "mean": None, "note": "unit mismatch or n<2"}
                    continue
                entry = {}
                for seed in SEEDS:
                    ci = paired_seed_diff_ci(
                        ea, eb, n_boot=N_BOOT, seed=seed, alpha=ALPHA,
                        method="studentized")
                    ci["significant"] = bool(
                        ci.get("ci_low", 0) > 0.0 or ci.get("ci_high", 0) < 0.0)
                    entry[str(seed)] = ci
                entry["n_units"] = len(ea)
                sig[metric][f"{a}_vs_{b}"] = entry
        payload["datasets"][name] = {"n_traces": data["n_traces"],
                                     "significance": sig}
        print(f"== {name}: {data['n_traces']} traces ==")
        for row in ROWS:
            m = rows[row]["means"]
            print(f"  {row:10s} hit={m['hit_rate']:.4f} "
                  f"recall={m['recall_mean']:.4f} tok={m['tokens_mean']:.1f} "
                  f"store={m['storage_tokens']:.1f} "
                  f"rare={m['rare_recall']:.4f}")
        for metric in METRICS:
            for a, b in PAIRS:
                e = sig[metric].get(f"{a}_vs_{b}")
                if not e or e.get("mean") is None:
                    continue
                c = e["20260812"]
                flag = "*" if c["significant"] else ""
                print(f"  {metric:14s} {a} - {b}: {c['mean']:+8.4f} "
                      f"[{c['ci_low']:+8.4f}, {c['ci_high']:+8.4f}]{flag} "
                      f"(n={e['n_units']})")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
