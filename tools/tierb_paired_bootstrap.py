"""Tier-B paired bootstrap for the Qwen3-Embedding substitute rows (33- §5,
32- round-2 finding R2-M13: "tier-B significance missing -- public_dense_*.json
carries no significance, so the rows may claim mechanism replication only").

Runs the frozen public contract's dense row over the two Qwen3-Embedding
caches (0.6B / 8B) plus the frozen bm25 / sqcad rows on the *identical*
traces, then computes studentized paired bootstrap CIs (n_boot=2000,
pre-registered seeds 20260812 primary / 20260817 cross-check) for the row
pairs the frozen significance artifact lacks.  Units are the contract's
paired units: traces with needed evidence for LME-S (n=480 of 500) and
conversations for LoCoMo (n=10).

Usage: python tools/tierb_paired_bootstrap.py
Writes remote_results/lifecycle_audit/tierb_paired_bootstrap.json and prints
a markdown table.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sqcad.bootstrap_ci import paired_seed_diff_ci
from src.sqcad.public_unified_contract import (
    ALPHA, N_BOOT, mask_lme_chronological, run_policy, evaluate_trace,
    trace_features,
)
from src.sqcad.trace_grounded_runner import (
    load_longmemeval_s, load_locomo,
)

LME_DATA = Path("D:/Engineering/SQCAD/database/datasets/"
                "LongMemEval/longmemeval_s_cleaned.json")
LOCOMO_DATA = Path("D:/Engineering/SQCAD/database/datasets/"
                   "LoCoMo/locomo10.json")
CACHE_06 = Path("remote_results/cloud_dense_20260820/dense_cache_0.6B.json")
CACHE_8 = Path("remote_results/cloud_dense_20260820/8B/dense_cache_8B.json")
OUT = Path("remote_results/lifecycle_audit/tierb_paired_bootstrap.json")

ROWS = ("dense_qwen06", "dense_qwen8", "bm25", "sqcad")
PAIRS = (
    ("dense_qwen06", "bm25"),
    ("dense_qwen06", "sqcad"),
    ("dense_qwen8", "bm25"),
    ("dense_qwen8", "sqcad"),
    ("dense_qwen8", "dense_qwen06"),
)
METRICS = ("hit_rate", "recall_mean", "tokens_mean", "rare_recall")
SEEDS = (20260812, 20260817)


def _load_cache(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return d.get("cache", d)


def run_dataset(name: str, data_path: Path,
                cache06: dict, cache8: dict) -> dict:
    """Per-policy per-trace metric arrays for one dataset."""
    traces = (load_longmemeval_s(data_path)
              if name == "longmemeval_s" else load_locomo(data_path))
    per: dict = {r: [] for r in ROWS}
    n_masked_needed_total = 0
    for trace in traces:
        masked, _ = (mask_lme_chronological(trace)
                     if name == "longmemeval_s" else (trace, {}))
        visible_ids = {m.msg_id for m in masked.msgs}
        feats = trace_features(masked.msgs)
        for row in ROWS:
            if row.startswith("dense_"):
                model = "8B" if row.endswith("8") else "0.6B"
                cache = cache8 if row.endswith("8") else cache06
                ws = cache.get(trace.sample_id)
                if ws is None:
                    continue
                res = run_policy("dense", masked, dense_ws=ws, feats=feats)
            else:
                res = run_policy(row, masked, feats=feats)
            if res is None:
                continue
            ev = evaluate_trace(res, masked, visible_ids)
            per[row].append(ev)
    out: dict = {"n_traces": len(traces), "units": {}}
    for row, evals in per.items():
        out["units"][row] = {
            m: [e[m] for e in evals if e[m] is not None]
            for m in METRICS}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lme", type=Path, default=LME_DATA)
    ap.add_argument("--locomo", type=Path, default=LOCOMO_DATA)
    ap.add_argument("--cache06", type=Path, default=CACHE_06)
    ap.add_argument("--cache8", type=Path, default=CACHE_8)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    cache06 = _load_cache(args.cache06)
    cache8 = _load_cache(args.cache8)
    print(f"caches: 0.6B {len(cache06)} traces, 8B {len(cache8)} traces")

    payload: dict = {
        "config": {
            "n_boot": N_BOOT, "alpha": ALPHA, "method": "studentized",
            "seeds": list(SEEDS),
            "note": ("paired per-trace units, identical traces for all "
                     "rows; dense rows use the frozen contract's dense "
                     "policy over the Qwen3-Embedding caches (33- §5); "
                     "bm25/sqcad are the frozen rows"),
        },
        "datasets": {},
    }
    for name, path in (("longmemeval_s", args.lme), ("locomo", args.locomo)):
        data = run_dataset(name, path, cache06, cache8)
        units = data["units"]
        sig: dict = {}
        for metric in METRICS:
            sig[metric] = {}
            for a, b in PAIRS:
                ea, eb = units[a][metric], units[b][metric]
                if len(ea) != len(eb) or len(ea) < 2:
                    sig[metric][f"{a}_vs_{b}"] = {
                        "mean_diff": None, "note": "unit mismatch or n<2"}
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
        for metric in METRICS:
            for a, b in PAIRS:
                e = sig[metric].get(f"{a}_vs_{b}")
                if not e or e.get("mean_diff") is None:
                    continue
                c = e["20260812"]
                flag = "*" if c["significant"] else ""
                print(f"  {metric:11s} {a} - {b}: "
                      f"{c['mean_diff']:+.4f} [{c['ci_low']:+.4f}, "
                      f"{c['ci_high']:+.4f}]{flag} (n={e['n_units']})")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
