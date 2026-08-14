"""Gate 5: paired seed/episode bootstrap CI.

Motivation (Gate 3, 04 report): the normal-approximation CI of the RCT
protocol estimator covered only 88.5% at z*=1.96 and coverage FELL with the
sample size (94.4% -> 72.2%) -- the within-run trajectory variance
underestimates the seed-to-seed (world realization) spread.  This module
implements the fix and validates it:

  A1  heavy-tailed control (known truth): the normal and the plain
      percentile CIs both under-cover under skew; the BCa interval
      (bias-corrected + accelerated, second-order accurate) restores
      nominal coverage -- the empirical reason this module defaults to BCa;
  A2  D0-world seed-level coverage: for each memory, the protocol estimate
      is a per-seed quantity; the CI must be computed over SEEDS (paired
      across the keep/archive rollouts of the same seed), not inside one
      seed.  The within-seed normal CI against realized truths reproduces
      Gate 3's ~0.86 (wrong unit); the seed-level CI against the
      seed-population mean truth recovers nominal coverage;
  B   paired seed/episode bootstrap applied to the frozen Gate 1 main
      table and the Gate 4 cost contract: per-policy metric CIs and CIs of
      (framework - best baseline) DIFFERENCES, computed on the paired
      per-seed differences (resampling the same seed indices across
      policies), with the independent CI given to quantify what pairing
      removes;
  C   (freeze_four_piece.py) the four-piece freeze is a separate module.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from statistics import mean, pstdev, stdev
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .unified_baseline_runner import (
    BASELINE_SPECS, run_policy_unified,
)
from .cost_contract_experiment import (
    DEFAULT_COEF, cost_value, run_episode,
)

try:  # pragma: no cover - import mode depends on how the script is launched
    from .identification_recovery_experiment import (
        World, WorldConfig, compute_oracle_values, estimate_sqcad_rct,
    )
except ImportError:  # pragma: no cover - direct script compatibility
    from identification_recovery_experiment import (
        World, WorldConfig, compute_oracle_values, estimate_sqcad_rct,
    )

# ---------------------------------------------------------------------------
# Bootstrap primitives
# ---------------------------------------------------------------------------


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def _normal_cdf(x: float) -> float:
    """Standard-normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bca_from_replicates(xs: List[float], reps: List[float],
                         n_boot: int, alpha: float) -> Dict[str, float]:
    """BCa endpoints from an existing list of bootstrap replicates of the
    mean of `xs`.  Bias correction z0 from the replicate rank of the
    observed mean; acceleration a from the leave-one-out jackknife."""
    n = len(xs)
    theta_hat = mean(xs)
    z0 = _normal_quantile(min(max(
        sum(1 for r in reps if r < theta_hat) / n_boot, 1e-12), 1.0 - 1e-12))
    total = sum(xs)
    leaves = [(total - xs[i]) / (n - 1) for i in range(n)]
    jbar = mean(leaves)
    num = sum((jbar - l) ** 3 for l in leaves)
    den = 6.0 * (sum((jbar - l) ** 2 for l in leaves) ** 1.5)
    a = num / den if den > 0 else 0.0
    za = _normal_quantile(1.0 - alpha / 2.0)
    # adjusted quantiles are PROBABILITIES: Phi(z0 + (z0 +/- za)/(1 - a(...)))
    # (z0 clamped to [-8, 8] keeps the denominators away from 0 and the
    # CDF arguments finite; endpoint clamping in _pct handles the rest)
    z0 = min(max(z0, -8.0), 8.0)
    den_lo = 1.0 - a * (z0 - za)
    den_hi = 1.0 - a * (z0 + za)
    alo = _normal_cdf(z0 + (z0 - za) / den_lo) if den_lo != 0.0 else 0.0
    ahi = _normal_cdf(z0 + (z0 + za) / den_hi) if den_hi != 0.0 else 1.0
    reps.sort()
    def _pct(p: float) -> float:
        p = min(max(p, 0.5 / n_boot), 1.0 - 0.5 / n_boot)
        return reps[int(p * n_boot)]
    lo, hi = _pct(alo), _pct(ahi)
    if lo > hi:
        lo, hi = hi, lo
    return {"z0": z0, "acceleration": a, "ci_low": lo, "ci_high": hi}


def _interval_from_replicates(xs: List[float], reps: List[float],
                              n_boot: int, alpha: float, method: str,
                              rep_ses: Optional[List[float]] = None,
                              se_obs: Optional[float] = None,
                              theta_hat: Optional[float] = None,
                              ) -> Dict[str, float]:
    """CI endpoints from bootstrap replicates of a statistic of `xs`.

    method="percentile"  -- quantiles of the replicates (first order);
    method="bca"         -- bias-corrected + accelerated (second order);
    method="studentized" -- percentile-t: t* = (stat* - stat)/se* studentized
                            with each replicate's own se, pivoted by the
                            observed se (requires rep_ses and se_obs).

    Empirically (A1, n=30, known truth): normal 0.866 / percentile 0.860 /
    BCa 0.877 / studentized 0.928 on lognormal(1), and on t_4 (kurtosis)
    studentized 0.941 where BCa degrades to 0.905 -- the studentized
    interval is the module default."""
    out: Dict[str, float] = {}
    if method == "bca":
        out.update(_bca_from_replicates(xs, reps, n_boot, alpha))
    elif method == "percentile":
        reps.sort()
        lo = reps[max(0, int(alpha / 2.0 * n_boot))]
        hi = reps[min(n_boot - 1, int((1.0 - alpha / 2.0) * n_boot) - 1)]
        out.update({"ci_low": lo, "ci_high": hi})
    elif method == "studentized":
        if rep_ses is None or se_obs is None:
            raise ValueError("studentized method requires rep_ses and se_obs")
        if theta_hat is None:
            theta_hat = mean(xs)
        valid = [(r, se) for r, se in zip(reps, rep_ses) if se > 0.0]
        if len(valid) < max(50, n_boot // 4) or se_obs <= 0.0:
            # degenerate resamples: fall back to the percentile interval
            reps.sort()
            lo = reps[max(0, int(alpha / 2.0 * n_boot))]
            hi = reps[min(n_boot - 1, int((1.0 - alpha / 2.0) * n_boot) - 1)]
            out.update({"ci_low": lo, "ci_high": hi, "fallback": True})
        else:
            ts = sorted((r - theta_hat) / se for r, se in valid)
            n_v = len(ts)
            lo = theta_hat - ts[int((1.0 - alpha / 2.0) * n_v) - 1] * se_obs
            hi = theta_hat - ts[int(alpha / 2.0 * n_v)] * se_obs
            if lo > hi:
                lo, hi = hi, lo
            out.update({"ci_low": lo, "ci_high": hi})
    else:
        raise ValueError(f"unknown bootstrap method: {method}")
    out.update({"mean": mean(xs), "se": pstdev(reps),
                "n_boot": float(n_boot), "method": method})
    return out


def _normal_quantile(p: float) -> float:
    """Inverse standard-normal CDF via the rational (Acklam) approximation
    on the logit scale (deterministic, no scipy dependency)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02,
         -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02,
         -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01,
         -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01,
         2.445134137142996e+00, 3.754408661907416e+00]
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p <= 0.0:
        return -float("inf")
    if p >= 1.0:
        return float("inf")
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q
                 + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2])
                                         * q + d[3]) * q + 1.0)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r
                 + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r
                                               + b[2]) * r + b[3]) * r
                                              + b[4]) * r + 1.0)
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q
              + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2])
                                      * q + d[3]) * q + 1.0)


def percentile_ci(samples: Sequence[float], n_boot: int = 2000,
                  seed: int = 42, alpha: float = 0.05) -> Dict[str, float]:
    """Nonparametric percentile CI of the mean (resample with replacement).

    First-order accurate only: on skewed data it shares the normal CI's
    skew bias (A1).  The module default is the studentized interval."""
    return _bootstrap_mean_ci(samples, method="percentile",
                              n_boot=n_boot, seed=seed, alpha=alpha)


def bca_ci(samples: Sequence[float], n_boot: int = 2000,
           seed: int = 42, alpha: float = 0.05) -> Dict[str, float]:
    """BCa (bias-corrected and accelerated) interval of the mean.

    Second-order accurate, but A1 shows it degrades under kurtosis (t_4:
    0.905) where the studentized interval holds 0.941 -- kept as a
    reference method, not the default."""
    return _bootstrap_mean_ci(samples, method="bca",
                              n_boot=n_boot, seed=seed, alpha=alpha)


def studentized_ci(samples: Sequence[float], n_boot: int = 2000,
                   seed: int = 42, alpha: float = 0.05) -> Dict[str, float]:
    """Studentized (percentile-t) interval of the mean: the module default.

    Every replicate is studentized with its own resample se, and the
    observed se pivots the t-quantiles back onto the data scale.  A1:
    restores coverage toward nominal under skew (lognormal(1), n=30:
    0.928 vs normal 0.866) and under kurtosis (t_4: 0.941)."""
    return _bootstrap_mean_ci(samples, method="studentized",
                              n_boot=n_boot, seed=seed, alpha=alpha)


def _bootstrap_mean_ci(samples: Sequence[float], method: str,
                       n_boot: int, seed: int, alpha: float) -> Dict[str, float]:
    rng = _rng(seed)
    xs = list(samples)
    n = len(xs)
    if n == 0:
        return {"mean": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0,
                "n_boot": 0.0, "method": method}
    reps, rep_ses = [], []
    for _ in range(n_boot):
        rs = [xs[int(rng.random() * n)] for _ in range(n)]
        reps.append(mean(rs))
        rep_ses.append(pstdev(rs) / math.sqrt(n))
    se_obs = (pstdev(xs) / math.sqrt(n) if n > 1 else 0.0)
    return _interval_from_replicates(xs, reps, n_boot, alpha, method,
                                     rep_ses=rep_ses, se_obs=se_obs)


def _resample_pairs(ks: List[float], ac: List[float], rng: random.Random,
                    n_boot: int) -> List[float]:
    n = len(ks)
    return [mean(ks[rng.randrange(n)] - ac[rng.randrange(n)]
                 for _ in range(n)) for _ in range(n_boot)]


def paired_trajectory_ci(keep_u: Sequence[float], arc_u: Sequence[float],
                         n_boot: int = 2000, seed: int = 42,
                         alpha: float = 0.05,
                         method: str = "studentized") -> Dict[str, float]:
    """Paired trajectory bootstrap of the mean difference: the SAME index
    is resampled for keep and archive, preserving the within-seed
    correlation of the two rollout arms."""
    ks, ac = list(keep_u), list(arc_u)
    assert len(ks) == len(ac)
    n = len(ks)
    if n == 0:
        return {"mean": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    rng = _rng(seed)
    diffs = [k - a for k, a in zip(ks, ac)]
    reps, rep_ses = [], []
    for _ in range(n_boot):
        rs = [diffs[int(rng.random() * n)] for _ in range(n)]
        m = math.fsum(rs) / n
        reps.append(m)
        v = math.fsum((x - m) * (x - m) for x in rs) / (n - 1) \
            if n > 1 else 0.0
        rep_ses.append(math.sqrt(v / n))
    se_obs = pstdev(diffs) / math.sqrt(n) if n > 1 else 0.0
    out = _interval_from_replicates(diffs, reps, n_boot, alpha, method,
                                    rep_ses=rep_ses, se_obs=se_obs)
    out["n_trajectories"] = float(n)
    return out


def paired_seed_ci(per_seed: Sequence[float], n_boot: int = 2000,
                   seed: int = 42, alpha: float = 0.05,
                   method: str = "studentized") -> Dict[str, float]:
    """CI of the per-seed mean; the sampling unit is the SEED (the world
    realization), not the step or the trajectory.  Default method:
    studentized (A1)."""
    xs = list(per_seed)
    n = len(xs)
    if n == 0:
        return {"mean": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0,
                "method": method}
    rng = _rng(seed)
    reps, rep_ses = [], []
    for _ in range(n_boot):
        rs = [xs[int(rng.random() * n)] for _ in range(n)]
        m = math.fsum(rs) / n
        reps.append(m)
        v = math.fsum((x - m) * (x - m) for x in rs) / (n - 1) \
            if n > 1 else 0.0
        rep_ses.append(math.sqrt(v / n))
    se_obs = pstdev(xs) / math.sqrt(n) if n > 1 else 0.0
    out = _interval_from_replicates(xs, reps, n_boot, alpha, method,
                                    rep_ses=rep_ses, se_obs=se_obs)
    out["n_seeds"] = float(n)
    return out


def paired_seed_diff_ci(a: Sequence[float], b: Sequence[float],
                        n_boot: int = 2000, seed: int = 42,
                        alpha: float = 0.05,
                        method: str = "bca") -> Dict[str, float]:
    """CI of (mean_a - mean_b) on the PAIRED per-seed differences: the same
    seed index is resampled for both policies, so the shared stream
    variation cancels and the CI reflects the within-seed policy gap."""
    as_, bs = list(a), list(b)
    assert len(as_) == len(bs), "policies must share the seed index"
    diffs = [x - y for x, y in zip(as_, bs)]
    out = paired_seed_ci(diffs, n_boot=n_boot, seed=seed, alpha=alpha,
                         method=method)
    out["paired"] = True
    return out


def independent_seed_diff_ci(a: Sequence[float], b: Sequence[float],
                             n_boot: int = 2000, seed: int = 42,
                             alpha: float = 0.05,
                             method: str = "studentized") -> Dict[str, float]:
    """CI of (mean_a - mean_b) under INDEPENDENT resampling: policy A and
    policy B resample DIFFERENT seed indices, so the shared world/stream
    noise does not cancel.  Comparing this with the paired CI quantifies
    how much of the difference uncertainty the pairing removes."""
    as_, bs_ = list(a), list(b)
    n = len(as_)
    if n == 0:
        return {"mean": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0,
                "method": method}
    rng = _rng(seed)
    reps, rep_ses = [], []
    for _ in range(n_boot):
        ra = [as_[int(rng.random() * n)] for _ in range(n)]
        rb = [bs_[int(rng.random() * n)] for _ in range(n)]
        ma = math.fsum(ra) / n
        mb = math.fsum(rb) / n
        reps.append(ma - mb)
        va = math.fsum((x - ma) * (x - ma) for x in ra) / (n - 1) \
            if n > 1 else 0.0
        vb = math.fsum((x - mb) * (x - mb) for x in rb) / (n - 1) \
            if n > 1 else 0.0
        rep_ses.append(math.hypot(math.sqrt(va), math.sqrt(vb))
                       / math.sqrt(n))
    se_obs = math.sqrt(pstdev(as_) ** 2 / n + pstdev(bs_) ** 2 / n) \
        if n > 1 else 0.0
    stat_mean = mean(as_) - mean(bs_)
    out = _interval_from_replicates(
        as_, reps, n_boot, alpha, method,
        rep_ses=rep_ses, se_obs=se_obs,
        theta_hat=stat_mean)
    out["mean"] = stat_mean
    out["paired"] = False
    return out


def normal_ci(per_seed: Sequence[float], z: float = 1.96) -> Dict[str, float]:
    """The pre-registration normal CI at the seed level (for comparison)."""
    xs = list(per_seed)
    n = len(xs)
    if n == 0:
        return {"mean": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    m = mean(xs)
    se = stdev(xs) / math.sqrt(n) if n > 1 else 0.0
    return {"mean": m, "se": se, "ci_low": m - z * se, "ci_high": m + z * se}


# ---------------------------------------------------------------------------
# A1: heavy-tailed control with known truth
# ---------------------------------------------------------------------------


def run_heavy_tail_control(n: int = 30, reps: int = 2000, n_boot: int = 999,
                           seed: int = 7) -> Dict[str, float]:
    """Coverage of four CIs on a skewed (lognormal sigma=1) population with
    analytically known mean E[exp(N(0,1))] = exp(0.5).

    Vectorized probe at n=30, reps=2000: normal 0.866 / percentile 0.860 /
    BCa 0.877 / studentized 0.928; on t_4 (kurtosis): normal 0.951 /
    percentile 0.922 / BCa 0.905 / studentized 0.941.  The normal CI
    under-covers under skew; the plain percentile shares its bias
    (first-order only); BCa helps moderately under skew but degrades under
    kurtosis; the studentized (percentile-t) interval restores coverage
    toward nominal in both regimes -- the module default."""
    rng = _rng(seed)
    mu = math.exp(0.5)          # E[exp(N(0,1))] = exp(0.5)
    hits = {m: 0 for m in ("normal", "percentile", "bca", "studentized")}
    for rep in range(reps):
        xs = [math.exp(rng.gauss(0.0, 1.0)) for _ in range(n)]
        for method, ci in (
                ("normal", normal_ci(xs)),
                ("percentile", percentile_ci(xs, n_boot=n_boot,
                                             seed=seed + rep + 1)),
                ("bca", bca_ci(xs, n_boot=n_boot, seed=seed + rep + 1)),
                ("studentized", studentized_ci(xs, n_boot=n_boot,
                                               seed=seed + rep + 1))):
            hits[method] += int(ci["ci_low"] <= mu <= ci["ci_high"])
    return {
        "n": n, "reps": reps, "truth": mu, "distribution": "lognormal(1)",
        "normal_coverage": hits["normal"] / reps,
        "percentile_coverage": hits["percentile"] / reps,
        "bca_coverage": hits["bca"] / reps,
        "studentized_coverage": hits["studentized"] / reps,
    }


# ---------------------------------------------------------------------------
# A2: D0-world seed-level coverage
# ---------------------------------------------------------------------------


def run_d0_seed_level_coverage(seed0: int = 3, n_seeds: int = 8,
                               n_trajectories: int = 100, n_oracle: int = 150,
                               n_epochs: int = 80, n_boot: int = 999,
                               boot_seed: int = 20260812) -> Dict[str, Any]:
    """Seed-level CI coverage on the D0 world (world config identical to the
    Gate 3 sample-size curve: n_oracle=150, n_epochs=80).

    The estimand of the protocol estimator is E_s[theta_s]: the expected
    lifecycle value over the seed (world realization) population.  Two
    coverage checks are reported:

      within-seed normal (reproduction of Gate 3): each seed's within-seed
          normal CI against that seed's REALIZED oracle truth.  Gate 3
          measured 0.861 at n_trajectories=100 and 0.722 at 300 (seeds
          3,5,7) -- the CI shrinks with n while the realized truth keeps
          its oracle MC noise, so coverage falls.  The seed set matters at
          small n (0.86-0.95 at n_traj=100 across seed ranges): the
          within-seed CI is only accidentally calibrated.
      seed-level normal / seed-level bootstrap: CI built over the per-seed
          estimates (sampling unit = seed), checked against the per-memory
          MEAN of the realized truths (consistent estimate of E_s[theta_s];
          oracle MC noise shrinks as sqrt(1/(n_oracle*n_seeds)) and is
          small relative to the seed-level CI half-width).

    The per-seed realized-truth coverage of a mean-CI is NOT expected to be
    95% -- the realized truth is a random target with irreducible MC noise
    and between-seed spread; that is exactly the unit error Gate 3 measured.
    """
    worlds: List[Tuple[World, WorldConfig]] = []
    for s in range(seed0, seed0 + n_seeds):
        cfg = WorldConfig(seed=s, n_trajectories=n_trajectories,
                          n_oracle=n_oracle, n_epochs=n_epochs)
        worlds.append((World(cfg), cfg))
    mem_ids = [m.mem_id for m in worlds[0][0].memories]

    per_mem: Dict[str, Dict[str, Any]] = {}
    within_hits = within_n = 0
    within_widths: List[float] = []
    for mem in mem_ids:
        m_hits = m_n = 0
        ests, truths = [], []
        for world, cfg in worlds:
            e = estimate_sqcad_rct(world, cfg, [mem])[mem]
            t = compute_oracle_values(world, cfg)[mem]
            ests.append(e["estimate"])
            truths.append(t)
            if e["ci_low"] is not None:
                m_n += 1
                m_hits += int(e["ci_low"] <= t <= e["ci_high"])
                within_widths.append(e["ci_high"] - e["ci_low"])
        within_n += m_n
        within_hits += m_hits
        seed_mean_truth = mean(truths)
        ci_normal = normal_ci(ests)
        ci_boot = paired_seed_ci(ests, n_boot=n_boot, seed=boot_seed)
        per_mem[mem] = {
            "mean_estimate": mean(ests),
            "seed_mean_truth": seed_mean_truth,
            "seed_estimates": ests,
            "within_seed_normal_hits": m_hits,
            "within_seed_normal_n": m_n,
            "seed_normal_contains_seed_mean_truth": int(
                ci_normal["ci_low"] <= seed_mean_truth <= ci_normal["ci_high"]),
            "seed_bootstrap_contains_seed_mean_truth": int(
                ci_boot["ci_low"] <= seed_mean_truth <= ci_boot["ci_high"]),
            "seed_normal": ci_normal,
            "seed_bootstrap": ci_boot,
        }
    n_mem = len(mem_ids)
    return {
        "protocol": {
            "n_seeds": n_seeds, "n_trajectories_per_seed": n_trajectories,
            "n_oracle": n_oracle, "n_epochs": n_epochs,
            "n_boot": n_boot, "memories": n_mem,
            "note": ("within-seed coverage reproduces Gate 3 (wrong unit: "
                     "within-seed CI vs realized truth); seed-level "
                     "coverage targets E_s[theta_s] via the seed-mean truth"),
        },
        "coverage": {
            "within_seed_normal_vs_realized_truth": (within_hits / within_n
                                                     if within_n else 0.0),
            "seed_level_normal_vs_seed_mean_truth": mean(
                m["seed_normal_contains_seed_mean_truth"]
                for m in per_mem.values()),
            "seed_level_bootstrap_vs_seed_mean_truth": mean(
                m["seed_bootstrap_contains_seed_mean_truth"]
                for m in per_mem.values()),
            "n_within_checks": within_n, "n_seed_mean_checks": n_mem,
            "mean_within_seed_ci_width": mean(within_widths),
            "mean_seed_bootstrap_ci_width": mean(
                m["seed_bootstrap"]["ci_high"] - m["seed_bootstrap"]["ci_low"]
                for m in per_mem.values()),
        },
        "per_memory": {
            m: {k: v for k, v in row.items()
                if k not in ("seed_estimates",)}
            for m, row in per_mem.items()},
    }


# ---------------------------------------------------------------------------
# B: paired bootstrap on the frozen Gate 1 / Gate 4 tables
# ---------------------------------------------------------------------------


def _per_seed_metrics(policy: str, seeds: int, steps: int,
                      budget: int) -> List[Dict[str, float]]:
    rows = []
    for seed in range(seeds):
        row = run_policy_unified(seed, policy, 0.2, steps, budget)
        rows.append({
            "average_utility": row["average_utility"],
            "rare_critical_recall": row["rare_critical_recall"],
            "stale_exposure_rate": row["stale_exposure_rate"],
            "average_workspace_tokens": row["average_workspace_tokens"],
        })
    return rows


def run_main_table_ci(seeds: int = 30, steps: int = 100, budget: int = 12,
                      n_boot: int = 2000,
                      boot_seed: int = 20260812) -> Dict[str, Any]:
    """Paired seed bootstrap over the frozen Gate 1 main table metrics,
    plus paired CIs of the (framework - best baseline) differences."""
    policies = [p for p in BASELINE_SPECS
                if BASELINE_SPECS[p]["transportability"] != "not_transportable"]
    per_seed: Dict[str, List[Dict[str, float]]] = {}
    for policy in policies:
        per_seed[policy] = _per_seed_metrics(policy, seeds, steps, budget)
    table: Dict[str, Any] = {}
    for policy in policies:
        rows = per_seed[policy]
        table[policy] = {
            metric: paired_seed_ci([r[metric] for r in rows],
                                   n_boot=n_boot, seed=boot_seed)
            for metric in ("average_utility", "rare_critical_recall",
                           "stale_exposure_rate",
                           "average_workspace_tokens")}
        table[policy]["normal_average_utility"] = normal_ci(
            [r["average_utility"] for r in rows])
    best_util = max(
        (p for p in policies if p != "risk_gated_decomp_abstract"),
        key=lambda p: table[p]["average_utility"]["mean"])
    best_non_probe = max(
        (p for p in policies
         if p != "risk_gated_decomp_abstract"
         and BASELINE_SPECS[p]["transportability"] != "not_transportable"
         and p not in ("causal_item", "trivium")),
        key=lambda p: table[p]["average_utility"]["mean"])
    diffs: Dict[str, Any] = {}
    for label, other in (("vs_best_util_baseline", best_util),
                         ("vs_best_non_probing", best_non_probe)):
        sq = [r["average_utility"]
              for r in per_seed["risk_gated_decomp_abstract"]]
        ot = [r["average_utility"] for r in per_seed[other]]
        diffs[label] = {
            "other": other,
            "average_utility": paired_seed_diff_ci(
                sq, ot, n_boot=n_boot, seed=boot_seed),
            "rare_critical_recall": paired_seed_diff_ci(
                [r["rare_critical_recall"] for r in per_seed[
                    "risk_gated_decomp_abstract"]],
                [r["rare_critical_recall"] for r in per_seed[other]],
                n_boot=n_boot, seed=boot_seed),
        }
        independent = independent_seed_diff_ci(
            sq, ot, n_boot=n_boot, seed=boot_seed)
        diffs[label]["independent_seed_ci"] = independent
        diffs[label]["paired_ci_width"] = (
            diffs[label]["average_utility"]["ci_high"]
            - diffs[label]["average_utility"]["ci_low"])
        diffs[label]["independent_ci_width"] = (
            independent["ci_high"] - independent["ci_low"])
    return {
        "protocol": {
            "purpose": "paired seed bootstrap over the frozen Gate 1 "
                       "unified-contract main table",
            "seeds": seeds, "steps_per_seed": steps, "budget": budget,
            "n_boot": n_boot, "boot_seed": boot_seed,
        },
        "per_policy": table,
        "differences": diffs,
    }


def run_cost_contract_ci(seeds: int = 10, steps: int = 100, budget: int = 12,
                         probe_budget: int = 8, n_boot: int = 2000,
                         boot_seed: int = 20260812) -> Dict[str, Any]:
    """Paired seed bootstrap of the Gate 4 net benefit V at DEFAULT prices
    and of the (framework - best baseline) V differences."""
    policies = ["risk_gated_decomp_abstract", "causal_item", "trivium",
                "rrf", "memory_worth", "keep_all", "no_memory"]
    per_seed: Dict[str, List[float]] = {}
    for policy in policies:
        vs = []
        for seed in range(seeds):
            row, rows = run_episode(seed, policy, probe_budget)
            vs.append(cost_value(rows, DEFAULT_COEF,
                                 float(row["rare_kept_final"])))
        per_seed[policy] = vs
    table: Dict[str, Dict[str, Any]] = {}
    for policy in policies:
        table[policy] = paired_seed_ci(per_seed[policy], n_boot=n_boot,
                                       seed=boot_seed)
        table[policy]["normal"] = normal_ci(per_seed[policy])
    diffs: Dict[str, Any] = {}
    best = max((p for p in policies
                if p != "risk_gated_decomp_abstract"),
               key=lambda p: table[p]["mean"])
    for label, other in (("vs_best", best),):
        sq = per_seed["risk_gated_decomp_abstract"]
        diffs[label] = {
            "other": other,
            "V": paired_seed_diff_ci(sq, per_seed[other], n_boot=n_boot,
                                     seed=boot_seed),
            "V_independent": independent_seed_diff_ci(
                sq, per_seed[other], n_boot=n_boot, seed=boot_seed),
        }
    return {
        "protocol": {
            "purpose": "paired seed bootstrap of the Gate 4 cost contract "
                       "V at default prices",
            "seeds": seeds, "steps_per_seed": steps, "budget": budget,
            "probe_budget": probe_budget, "n_boot": n_boot,
            "boot_seed": boot_seed,
        },
        "per_policy": table,
        "differences": diffs,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("results/bootstrap_ci.json"))
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()

    if args.fast:
        heavy = run_heavy_tail_control(n=30, reps=400, n_boot=199)
        d0 = {
            "n_trajectories_40": run_d0_seed_level_coverage(
                n_seeds=4, n_trajectories=40, n_oracle=80, n_epochs=40),
        }
        main_ci = run_main_table_ci(seeds=8, steps=60, n_boot=200)
        cost_ci = run_cost_contract_ci(seeds=4, steps=60, n_boot=200)
    else:
        heavy = run_heavy_tail_control()
        d0 = {
            # Gate 3's failing regime is n_trajectories=300 (coverage 0.722
            # at seeds 3,5,7); n_trajectories=100 anchors the accidentally
            # calibrated regime.  Seed range 3..10 contains Gate 3's seeds.
            "n_trajectories_100": run_d0_seed_level_coverage(
                n_seeds=8, n_trajectories=100),
            "n_trajectories_300": run_d0_seed_level_coverage(
                n_seeds=8, n_trajectories=300),
        }
        main_ci = run_main_table_ci()
        cost_ci = run_cost_contract_ci()

    result = {
        "protocol": {
            "purpose": "Gate 5 paired seed/episode bootstrap CI",
            "fast": args.fast,
        },
        "A1_heavy_tail_control": heavy,
        "A2_d0_seed_level_coverage": d0,
        "B_main_table_ci": main_ci,
        "B_cost_contract_ci": cost_ci,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({
        "A1": {"normal": heavy["normal_coverage"],
               "studentized": heavy["studentized_coverage"]},
        "A2": {k: v["coverage"] for k, v in d0.items()},
        "B_main_diff": {k: {kk: vv["mean"] for kk, vv in v.items()
                            if isinstance(vv, dict) and "mean" in vv}
                        for k, v in result["B_main_table_ci"]
                        ["differences"].items()},
        "B_cost_V": {p: v["mean"] for p, v in
                     result["B_cost_contract_ci"]["per_policy"].items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
