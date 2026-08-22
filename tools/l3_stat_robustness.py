#!/usr/bin/env python3
"""G-8 + G-11: honest statistics and parameter robustness for LifecycleBench.

Closes three gates from 0823-ICLR2027完整补充方案 without touching the frozen
dataset (§0.1: bucket count is a frozen taxonomy, not a sampling parameter).

G-8②  bucket-level paired bootstrap CI for the baselines that had NO artifact
       (memory_worth / keep_all / archive_all / event_rule / scope_literal /
       recency2 / frequency2 / storage12 / random50) vs sqcad_cert.
G-8③  stratified bootstrap (resample buckets, then episodes within bucket ->
       bucket kept as a random effect) + Holm-Bonferroni over the ablation
       family, reported alongside both statistical units.
G-11   GAMMA x TAU_TOL x PROBE_COST grid via audit.frozen_override, checking
       whether `no_censoring` (the only significant L3 effect) survives.
       Evaluation parameters only -- the 1380 episodes are never regenerated.

Writes remote_results/lifecycle_audit/l3_stat_robustness.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqcad.lifecycle_bench.audit import cached_episodes, frozen_override, outcome_of
from sqcad.lifecycle_bench.baselines import (
    ABLATIONS, BUCKET_KEY, DECISION_POLICIES, bootstrap_diff, branch_value,
    p_sqcad_cert,
)
from sqcad.lifecycle_bench.evaluator import EpisodeOutcome
from sqcad.lifecycle_bench.realizer import RealizedEpisode

RESULTS = Path("results/lifecycle_bench")
OUT_DEFAULT = Path("remote_results/lifecycle_audit/l3_stat_robustness.json")

N_BOOT = 2000
SEED = 20260817

# The paper's main L3 claim (31-:763) is about *interval authorization*, i.e.
# the `sqcad_v2` rule in tools/l3_sqcad_v2.py -- NOT the `sqcad_cert` entry of
# the frozen DECISION_POLICIES registry.  Defaulting the reference to
# sqcad_cert would test a claim the paper does not make, so the v2 rule is
# imported here and selected with --reference.
from l3_sqcad_v2 import p_sqcad_v2, p_sqcad_v2_probe  # noqa: E402

EXTRA_POLICIES = {"sqcad_v2": p_sqcad_v2, "sqcad_v2_probe": p_sqcad_v2_probe}
ALL_POLICIES = {**DECISION_POLICIES, **EXTRA_POLICIES}
REFERENCE = "sqcad_v2"


# ---------------------------------------------------------------------------
# statistical units
# ---------------------------------------------------------------------------
def bucket_means(pairs: Sequence[Tuple[str, float]]) -> Dict[str, float]:
    acc: Dict[str, List[float]] = {}
    for bucket, value in pairs:
        acc.setdefault(bucket, []).append(value)
    return {b: float(np.mean(v)) for b, v in acc.items()}


def bucket_level_ci(ref: Sequence[Tuple[str, float]],
                    base: Sequence[Tuple[str, float]]) -> Dict[str, Any]:
    """Paired bootstrap over the 14 buckets (the honest unit)."""
    rm, bm = bucket_means(ref), bucket_means(base)
    buckets = sorted(rm)
    out = bootstrap_diff([rm[b] for b in buckets], [bm[b] for b in buckets],
                         n_boot=N_BOOT, seed=SEED)
    out["n_units"] = len(buckets)
    out["unit"] = "bucket"
    return out


def stratified_ci(ref: Sequence[Tuple[str, float]],
                  base: Sequence[Tuple[str, float]]) -> Dict[str, Any]:
    """G-8③ two-stage bootstrap: resample buckets with replacement, then
    episodes within each drawn bucket.  Keeps bucket as a random effect, so
    the CI does not inherit the episode-level unit's false precision."""
    per: Dict[str, List[float]] = {}
    for (rb, rv), (bb, bv) in zip(ref, base):
        assert rb == bb, "unpaired rows"
        per.setdefault(rb, []).append(rv - bv)
    buckets = sorted(per)
    arrs = {b: np.asarray(per[b], dtype=float) for b in buckets}
    rng = np.random.default_rng(SEED)
    n_b = len(buckets)
    draws = np.empty(N_BOOT, dtype=float)
    for i in range(N_BOOT):
        idx = rng.integers(0, n_b, size=n_b)
        means = np.empty(n_b, dtype=float)
        for j, bi in enumerate(idx):
            a = arrs[buckets[bi]]
            means[j] = a[rng.integers(0, a.size, size=a.size)].mean()
        draws[i] = means.mean()
    lo, hi = np.percentile(draws, [2.5, 97.5])
    obs = float(np.mean([arrs[b].mean() for b in buckets]))
    return {"diff_mean": obs, "ci_lo": float(lo), "ci_hi": float(hi),
            "n_boot": N_BOOT, "significant": bool(lo > 0 or hi < 0),
            "n_units": n_b, "unit": "stratified(bucket,episode)"}


def boot_p_value(ref: Sequence[Tuple[str, float]],
                 base: Sequence[Tuple[str, float]]) -> float:
    """Two-sided bootstrap p for Holm-Bonferroni, on the stratified draws."""
    per: Dict[str, List[float]] = {}
    for (rb, rv), (_, bv) in zip(ref, base):
        per.setdefault(rb, []).append(rv - bv)
    buckets = sorted(per)
    arrs = {b: np.asarray(per[b], dtype=float) for b in buckets}
    obs = float(np.mean([arrs[b].mean() for b in buckets]))
    rng = np.random.default_rng(SEED + 1)
    n_b = len(buckets)
    centered = {b: arrs[b] - arrs[b].mean() for b in buckets}
    hits = 0
    for _ in range(N_BOOT):
        idx = rng.integers(0, n_b, size=n_b)
        means = []
        for bi in idx:
            a = centered[buckets[bi]]
            means.append(a[rng.integers(0, a.size, size=a.size)].mean())
        if abs(float(np.mean(means))) >= abs(obs):
            hits += 1
    return (hits + 1) / (N_BOOT + 1)


def holm_bonferroni(pvals: Dict[str, float],
                    alpha: float = 0.05) -> Dict[str, Any]:
    order = sorted(pvals, key=lambda k: pvals[k])
    m = len(order)
    out, rejected_so_far = {}, True
    for i, key in enumerate(order):
        thresh = alpha / (m - i)
        reject = rejected_so_far and pvals[key] <= thresh
        rejected_so_far = reject
        out[key] = {"p": round(pvals[key], 5), "threshold": round(thresh, 5),
                    "reject_at_0.05": bool(reject), "rank": i + 1}
    return out


# ---------------------------------------------------------------------------
# row builders
# ---------------------------------------------------------------------------
def policy_pairs(eps: List[RealizedEpisode],
                 name: str) -> List[Tuple[str, float]]:
    fn = ALL_POLICIES[name]
    return [(BUCKET_KEY(ep), branch_value(ep, fn(ep))) for ep in eps]


def ablation_pairs(eps: List[RealizedEpisode], cfg_name: str,
                   reference: str = REFERENCE) -> List[Tuple[str, float]]:
    """Ablated follow-on under the *reference decision* (31-:786 attributes the
    defer path's cost under the sqcad_v2 decision, so the reference rule must
    match the one the claim is about)."""
    cfg = ABLATIONS[cfg_name]
    fn = ALL_POLICIES[reference]
    return [(BUCKET_KEY(ep), branch_value(ep, fn(ep), cfg)) for ep in eps]


# ---------------------------------------------------------------------------
# G-8: missing CIs + stratified + Holm-Bonferroni
# ---------------------------------------------------------------------------
def run_g8(eps: List[RealizedEpisode],
           reference: str = REFERENCE) -> Dict[str, Any]:
    ref = policy_pairs(eps, reference)
    ref_vals = [v for _, v in ref]

    baselines: Dict[str, Any] = {}
    for name in ALL_POLICIES:
        if name == reference:
            continue
        base = policy_pairs(eps, name)
        baselines[name] = {
            "episode_level": {
                **bootstrap_diff(ref_vals, [v for _, v in base],
                                 n_boot=N_BOOT, seed=SEED),
                "n_units": len(base), "unit": "episode",
            },
            "bucket_level": bucket_level_ci(ref, base),
            "stratified": stratified_ci(ref, base),
        }
        b = baselines[name]
        print(f"  {name:22s} ep={b['episode_level']['diff_mean']:+8.3f}"
              f" sig={b['episode_level']['significant']!s:5s}"
              f" | bucket={b['bucket_level']['diff_mean']:+8.3f}"
              f" [{b['bucket_level']['ci_lo']:+7.2f},"
              f"{b['bucket_level']['ci_hi']:+7.2f}]"
              f" sig={b['bucket_level']['significant']!s:5s}"
              f" | strat sig={b['stratified']['significant']}")

    print("\n  ablation family (Holm-Bonferroni over 5):")
    abl: Dict[str, Any] = {}
    pvals: Dict[str, float] = {}
    for cfg_name in ABLATIONS:
        base = ablation_pairs(eps, cfg_name, reference)
        abl[cfg_name] = {
            "episode_level": {
                **bootstrap_diff(ref_vals, [v for _, v in base],
                                 n_boot=N_BOOT, seed=SEED),
                "n_units": len(base), "unit": "episode",
            },
            "bucket_level": bucket_level_ci(ref, base),
            "stratified": stratified_ci(ref, base),
        }
        pvals[cfg_name] = boot_p_value(ref, base)
        a = abl[cfg_name]
        print(f"  {cfg_name:22s} bucket={a['bucket_level']['diff_mean']:+8.3f}"
              f" [{a['bucket_level']['ci_lo']:+7.2f},"
              f"{a['bucket_level']['ci_hi']:+7.2f}]"
              f" p={pvals[cfg_name]:.4f}")

    holm = holm_bonferroni(pvals)
    for k, v in holm.items():
        print(f"    holm {k:20s} p={v['p']:.4f} thr={v['threshold']:.4f}"
              f" reject={v['reject_at_0.05']}")
    return {"reference": reference, "baselines": baselines,
            "ablations": abl, "holm_bonferroni": holm}


# ---------------------------------------------------------------------------
# G-11: parameter robustness grid (evaluation params only)
# ---------------------------------------------------------------------------
GAMMA_GRID = (0.9, 0.95, 0.99)
TAU_GRID = (0.25, 0.5, 1.0)
PROBE_GRID = (0.5, 1.0, 2.0)


def run_g11(eps: List[RealizedEpisode], full: bool,
            reference: str = REFERENCE) -> Dict[str, Any]:
    """censoring suppression is the only significant L3 effect; if it only
    holds at GAMMA=0.9 the L3 main finding is suspended (§4.4)."""
    combos: List[Tuple[float, float, float]] = []
    for g in GAMMA_GRID:
        for t in TAU_GRID:
            if full:
                for p in PROBE_GRID:
                    combos.append((g, t, p))
            else:
                combos.append((g, t, 1.0))

    cells: List[Dict[str, Any]] = []
    for gamma, tau, probe in combos:
        with frozen_override(gamma=gamma, tau_tol=tau, probe_cost=probe):
            ref = policy_pairs(eps, reference)
            base = ablation_pairs(eps, "no_censoring", reference)
            bl = bucket_level_ci(ref, base)
            st = stratified_ci(ref, base)
            # oracle agreement moves with TAU_TOL, so re-derive labels too
            fn = ALL_POLICIES[reference]
            agree = 0
            for ep in eps:
                out, _ = outcome_of(ep)
                if fn(ep) == out.oracle_action:
                    agree += 1
        cell = {
            "gamma": gamma, "tau_tol": tau, "probe_cost": probe,
            "no_censoring_bucket_diff": round(bl["diff_mean"], 4),
            "ci_lo": round(bl["ci_lo"], 4), "ci_hi": round(bl["ci_hi"], 4),
            "bucket_significant": bl["significant"],
            "stratified_significant": st["significant"],
            "oracle_agreement": round(agree / len(eps), 4),
        }
        cells.append(cell)
        print(f"  gamma={gamma:<5} tau={tau:<5} probe={probe:<4}"
              f" diff={cell['no_censoring_bucket_diff']:+8.3f}"
              f" [{cell['ci_lo']:+7.2f},{cell['ci_hi']:+7.2f}]"
              f" bucket_sig={bl['significant']!s:5s}"
              f" strat_sig={st['significant']!s:5s}"
              f" oracle_agree={cell['oracle_agreement']:.3f}")

    n_sig = sum(1 for c in cells if c["bucket_significant"])
    verdict = ("robust" if n_sig >= max(1, int(round(len(cells) * 7 / 9)))
               else "parameter-sensitive")
    print(f"\n  censoring significant in {n_sig}/{len(cells)} cells"
          f" -> {verdict}")
    return {"grid": cells, "n_cells": len(cells),
            "n_bucket_significant": n_sig,
            "closure_rule": "censoring significant in >=7/9 -> robust; "
                            "otherwise report the sensitive region honestly",
            "verdict": verdict}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--episodes", type=Path,
                    default=RESULTS / "episodes.pkl")
    ap.add_argument("--full-grid", action="store_true",
                    help="3x3x3 instead of 3x3 (PROBE_COST held at 1.0)")
    ap.add_argument("--skip-g11", action="store_true")
    ap.add_argument("--reference", default=REFERENCE,
                    choices=sorted(ALL_POLICIES),
                    help="decision rule the claim is about (default sqcad_v2)")
    args = ap.parse_args()

    eps = cached_episodes(args.episodes)
    print(f"episodes: {len(eps)}  buckets: "
          f"{len({BUCKET_KEY(e) for e in eps})}  reference: {args.reference}")

    print("\n=== G-8: statistical units ===")
    g8 = run_g8(eps, args.reference)

    g11: Dict[str, Any] = {"skipped": True}
    if not args.skip_g11:
        print("\n=== G-11: parameter robustness ===")
        g11 = run_g11(eps, args.full_grid, args.reference)

    payload = {
        "reference_policy": args.reference,
        "n_episodes": len(eps),
        "n_buckets": len({BUCKET_KEY(e) for e in eps}),
        "n_boot": N_BOOT, "seed": SEED,
        "note": ("bucket count is frozen taxonomy (11 mechanism + 3 control); "
                 "G-11 varies EVALUATION parameters only via frozen_override, "
                 "the 1380 episodes are never regenerated"),
        "g8_statistical_units": g8,
        "g11_parameter_robustness": g11,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

