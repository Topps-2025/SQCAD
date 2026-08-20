"""Paired bootstrap for the SQCAD-v2 (Theorem-6 rule) row on the public
contract (32- round-3 finding R3-M6: the paper's v2 coverage CI
[−0.097, −0.036] had no frozen artifact — public_v2_rule.json stores
aggregates only).

Runs the frozen `sqcad` policy and the v2 rule (src/sqcad/public_v2_rule.py,
write-time admission gate, frozen engine verbatim) on the *identical* traces,
then computes studentized paired bootstrap CIs (n_boot = 2000, pre-registered
seeds 20260812 primary / 20260817 cross-check) for hit_rate / recall_mean /
tokens_mean (exposure tokens).  Units: traces with needed evidence for LME-S
(n=480 of 500) and conversations for LoCoMo (n=10).

Usage: python tools/v2_paired_bootstrap.py
Writes remote_results/lifecycle_audit/v2_paired_bootstrap.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sqcad.bootstrap_ci import paired_seed_diff_ci
from src.sqcad.public_unified_contract import (
    ALPHA, N_BOOT, mask_lme_chronological, run_policy, evaluate_trace,
    trace_features,
)
from src.sqcad.public_v2_rule import run_v2_policy
from src.sqcad.trace_grounded_runner import (
    load_longmemeval_s, load_locomo,
)

LME_DATA = Path("D:/Engineering/SQCAD/database/datasets/"
                "LongMemEval/longmemeval_s_cleaned.json")
LOCOMO_DATA = Path("D:/Engineering/SQCAD/database/datasets/"
                   "LoCoMo/locomo10.json")
OUT = Path("remote_results/lifecycle_audit/v2_paired_bootstrap.json")

ROWS = ("sqcad", "sqcad_v2")
METRICS = ("hit_rate", "recall_mean", "tokens_mean")
SEEDS = (20260812, 20260817)


def run_dataset(name: str, data_path: Path) -> dict:
    traces = (load_longmemeval_s(data_path)
              if name == "longmemeval_s" else load_locomo(data_path))
    per: dict = {r: [] for r in ROWS}
    for trace in traces:
        masked, _ = (mask_lme_chronological(trace)
                     if name == "longmemeval_s" else (trace, {}))
        visible_ids = {m.msg_id for m in masked.msgs}
        feats = trace_features(masked.msgs)
        for row in ROWS:
            res = (run_policy(row, masked, feats=feats)
                   if row == "sqcad"
                   else run_v2_policy("sqcad_v2", masked))
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
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    payload: dict = {
        "config": {
            "n_boot": N_BOOT, "alpha": ALPHA, "method": "studentized",
            "seeds": list(SEEDS),
            "note": ("paired per-trace units, identical traces for both "
                     "rows; sqcad is the frozen contract row, sqcad_v2 is "
                     "src/sqcad/public_v2_rule.py (write-time gate, frozen "
                     "engine verbatim); complements the aggregate-only "
                     "results/public_v2_rule.json"),
        },
        "datasets": {},
    }
    for name, path in (("longmemeval_s", args.lme), ("locomo", args.locomo)):
        data = run_dataset(name, path)
        units = data["units"]
        sig: dict = {}
        for metric in METRICS:
            ea, eb = units["sqcad_v2"][metric], units["sqcad"][metric]
            if len(ea) != len(eb) or len(ea) < 2:
                sig[metric] = {"mean_diff": None, "note": "unit mismatch or n<2"}
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
            entry["mean_diff"] = sum(ea) / len(ea) - sum(eb) / len(eb)
            sig[metric] = entry
        payload["datasets"][name] = {"n_traces": data["n_traces"],
                                     "significance": sig}
        print(f"== {name}: {data['n_traces']} traces ==")
        for metric in METRICS:
            e = sig[metric]
            if e.get("mean_diff") is None:
                continue
            c = e["20260812"]
            flag = "*" if c["significant"] else ""
            print(f"  {metric:11s} v2 - sqcad: {e['mean_diff']:+.4f} "
                  f"[{c['ci_low']:+.4f}, {c['ci_high']:+.4f}]{flag} "
                  f"(n={e['n_units']})")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
