"""Estimation-validity experiments: the observational route (Theorem 3(b)(c)).

Closes the reviewer's Gate 3: the lifecycle estimate itself must be trusted,
independent of data realism and of cost-benefit.  Stage 1 of the
identification recovery experiment validated only the randomized protocol
route (Theorem 3(a)).  This module implements and compares, on worlds with
known truth:

  A. Local-effect estimators on CONFOUNDED observational data
     (regression adjustment / g-formula, IPW, doubly robust DR/OPE), each
     with correct and deliberately misspecified outcome and propensity
     models, and with true exposure E vs. the adoption proxy D (C6
     misattribution).  Produces the double-robustness boundary table.

  B. Sequential g-formula for LIFECYCLE values from the D0 observational
     log: the exposure and outcome processes are fitted from the log and
     simulated forward under the target persistent-action policy.  The
     expected failure is an estimand/support failure: memories whose
     persistent-action support (active-set composition) is absent from the
     log are extrapolated as if the action had no effect on the exposure
     process.

  C. Partial identification when identification fails (crowding support,
     C7 co-exposure rank deficiency): point estimates are replaced by
     bounds over the unidentified mechanism, compared against forced point
     estimates and the gate's unresolved/mismatch outcomes.

  D. Qualification calibration of the protocol route across seeds: Brier,
     ECE, sign-error rate, CI coverage, and the coverage-risk curve over
     the gate's confidence threshold z* -- not merely "zero confident
     errors", which is necessary but not sufficient (a gate can buy safety
     by abstaining).

  E. Sample-size - bias - CI-coverage curves for RCT / g-formula / DR.

Protocol: controlled synthetic worlds, not public benchmarks.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, pstdev, stdev
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:  # pragma: no cover - import mode depends on how the script is launched
    from .identification_recovery_experiment import (
        ROLE_BRIDGE,
        ROLE_SHORT_TERM,
        SHORT_SUPPRESS,
        World,
        WorldConfig,
        compute_bundle_oracle,
        compute_local_effects,
        compute_oracle_values,
        estimate_sqcad_rct,
    )
except ImportError:  # pragma: no cover - direct script compatibility
    from identification_recovery_experiment import (
        ROLE_BRIDGE,
        ROLE_SHORT_TERM,
        SHORT_SUPPRESS,
        World,
        WorldConfig,
        compute_bundle_oracle,
        compute_local_effects,
        compute_oracle_values,
        estimate_sqcad_rct,
    )

import numpy as np  # numpy is available in the project environment


# ---------------------------------------------------------------------------
# Small linear-algebra helpers (numpy OLS / logistic IRLS)
# ---------------------------------------------------------------------------

def ols_fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ordinary least squares coefficients (intercept included in X)."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def logistic_fit(X: np.ndarray, y: np.ndarray,
                 iterations: int = 30) -> np.ndarray:
    """Iteratively reweighted least squares logistic regression."""
    beta = np.zeros(X.shape[1])
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ beta, -30.0, 30.0)))
        w = np.clip(p * (1.0 - p), 1e-8, 1.0)
        z = (y - p) / w
        try:
            beta_new = np.linalg.solve(X.T @ (X * w[:, None]), X.T @ (w * z)) \
                + beta
        except np.linalg.LinAlgError:  # pragma: no cover - singular matrix
            return beta
        if np.max(np.abs(beta_new - beta)) < 1e-9:
            return beta_new
        beta = beta_new
    return beta


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ---------------------------------------------------------------------------
# Section A -- confounded per-step DGP with adoption misattribution
# ---------------------------------------------------------------------------

@dataclass
class ConfoundedStepConfig:
    n_steps: int = 4000
    n_seeds: int = 5
    effect: float = 1.0             # true per-exposure effect of the target
    noise: float = 0.4
    base: float = 1.0
    difficulty_weight: float = 1.0  # outcome baseline falls with difficulty
    prop_intercept: float = 0.30    # P(E=1 | d) = clip(a + b*d)
    prop_slope: float = 0.60
    adoption_error: float = 0.25    # C6: P(D != E) per step
    seed: int = 101


def sample_confounded_log(cfg: ConfoundedStepConfig,
                          rng: random.Random) -> List[Dict[str, float]]:
    """Per-step log with difficulty confounding:
    harder tasks are more likely to expose the memory AND lower the baseline
    outcome, so the naive exposure contrast is biased for the do-effect.
    """
    rows: List[Dict[str, float]] = []
    for t in range(cfg.n_steps):
        difficulty = rng.random()
        p = min(max(cfg.prop_intercept + cfg.prop_slope * difficulty, 0.05), 0.95)
        e = 1.0 if rng.random() < p else 0.0
        d = (1.0 - e) if rng.random() < cfg.adoption_error else e
        y = (cfg.base - cfg.difficulty_weight * difficulty
             + cfg.effect * e + rng.gauss(0.0, cfg.noise))
        rows.append({
            "time": float(t), "difficulty": difficulty,
            "exposed": float(e), "adoption": float(d), "outcome": y,
        })
    return rows


# ---------------------------------------------------------------------------
# Section A -- local-effect estimators
# ---------------------------------------------------------------------------

def _design(row: Dict[str, float], use_adoption: bool,
            outcome_spec: str) -> np.ndarray:
    """Feature vector for the outcome model (g-formula / DR outcome part)."""
    treat = row["adoption"] if use_adoption else row["exposed"]
    feats = [1.0, treat]
    if outcome_spec == "correct":
        feats.append(row["difficulty"])
    # misspecified outcome: the confounder (difficulty) is dropped
    return np.array(feats)


def _prop_design(row: Dict[str, float], use_adoption: bool,
                 prop_spec: str) -> np.ndarray:
    treat = row["adoption"] if use_adoption else row["exposed"]
    feats = [1.0, treat * 0.0 + 0.0]  # placeholder removed below
    feats = [1.0]
    if prop_spec == "correct":
        feats.append(row["difficulty"])
    # misspecified propensity: the exposure-affecting covariate is dropped,
    # i.e. a constant model -- exposure is treated as randomized
    return np.array(feats)


def _weighted_design(rows: Sequence[Dict[str, float]], use_adoption: bool,
                     prop_spec: str) -> np.ndarray:
    return np.array([_prop_design(r, use_adoption, prop_spec) for r in rows])


def _outcome_design(rows: Sequence[Dict[str, float]], use_adoption: bool,
                    outcome_spec: str) -> np.ndarray:
    return np.array([_design(r, use_adoption, outcome_spec) for r in rows])


def regression_adjustment(rows: Sequence[Dict[str, float]],
                          use_adoption: bool,
                          outcome_spec: str) -> Tuple[float, float]:
    """Outcome-regression g-formula: E[Y | do(E=e)] contrast.

    Correct specification of the outcome model is REQUIRED for consistency;
    this is the non-doubly-robust comparison point.
    """
    X = _outcome_design(rows, use_adoption, outcome_spec)
    y = np.array([r["outcome"] for r in rows])
    beta = ols_fit(X, y)
    treat_idx = 1
    # contrast with the empirical covariate distribution
    X1, X0 = X.copy(), X.copy()
    X1[:, treat_idx] = 1.0
    X0[:, treat_idx] = 0.0
    contrast = float(np.mean(X1 @ beta - X0 @ beta))
    se = float(np.std(X @ beta - y)) / math.sqrt(len(rows)) * 2.0
    return contrast, se


def ipw(rows: Sequence[Dict[str, float]], use_adoption: bool,
        prop_spec: str) -> Tuple[float, float]:
    """Inverse-probability weighting contrast.

    Correct specification of the propensity model is REQUIRED for
    consistency; the non-doubly-robust comparison point on the propensity
    side.
    """
    X = _weighted_design(rows, use_adoption, prop_spec)
    treats = np.array([(r["adoption"] if use_adoption else r["exposed"])
                       for r in rows])
    y = np.array([r["outcome"] for r in rows])
    beta = logistic_fit(X, treats)
    p = 1.0 / (1.0 + np.exp(-np.clip(X @ beta, -30.0, 30.0)))
    p = np.clip(p, 0.01, 0.99)
    est = float(np.mean(treats * y / p) - np.mean((1.0 - treats) * y / (1.0 - p)))
    se = float(np.std(treats * y / p - (1.0 - treats) * y / (1.0 - p))
               / math.sqrt(len(rows)))
    return est, se


def doubly_robust(rows: Sequence[Dict[str, float]], use_adoption: bool,
                  outcome_spec: str, prop_spec: str) -> Tuple[float, float]:
    """Sequential doubly-robust contrast: consistent if EITHER the outcome
    model or the propensity model is correct."""
    Xo = _outcome_design(rows, use_adoption, outcome_spec)
    Xp = _weighted_design(rows, use_adoption, prop_spec)
    treats = np.array([(r["adoption"] if use_adoption else r["exposed"])
                       for r in rows])
    y = np.array([r["outcome"] for r in rows])
    beta = ols_fit(Xo, y)
    X1, X0 = Xo.copy(), Xo.copy()
    X1[:, 1] = 1.0
    X0[:, 1] = 0.0
    mu1 = X1 @ beta
    mu0 = X0 @ beta
    pi_beta = logistic_fit(Xp, treats)
    p = 1.0 / (1.0 + np.exp(-np.clip(Xp @ pi_beta, -30.0, 30.0)))
    p = np.clip(p, 0.01, 0.99)
    dr_i = mu1 - mu0 + treats * (y - mu1) / p \
        - (1.0 - treats) * (y - mu0) / (1.0 - p)
    est = float(np.mean(dr_i))
    se = float(np.std(dr_i) / math.sqrt(len(rows)))
    return est, se


def naive_contrast(rows: Sequence[Dict[str, float]],
                   use_adoption: bool) -> Tuple[float, float]:
    """Association-style contrast (what Memory-Worth-like and CMI-like
    scores would read off the log)."""
    treats = np.array([(r["adoption"] if use_adoption else r["exposed"])
                       for r in rows])
    y = np.array([r["outcome"] for r in rows])
    est = float(np.mean(y[treats == 1]) - np.mean(y[treats == 0]))
    n1 = int(treats.sum())
    n0 = int(len(treats) - n1)
    se = float(np.sqrt(np.var(y[treats == 1]) / max(n1, 1)
                       + np.var(y[treats == 0]) / max(n0, 1)))
    return est, se


SPECS = ("correct", "misspecified")


def run_double_robustness(cfg: ConfoundedStepConfig | None = None
                          ) -> Dict[str, Any]:
    """3x2 double-robustness table + adoption-error sensitivity.

    Each cell is bias of the estimator for the true do-effect (cfg.effect)
    over n_seeds logs.  Rows distinguish the treatment variable the
    estimator sees: true exposure E, or the adoption proxy D (C6).
    """
    cfg = cfg or ConfoundedStepConfig()
    methods = {
        "gformula": lambda rows, ua, os_, ps: regression_adjustment(rows, ua, os_),
        "ipw": lambda rows, ua, os_, ps: ipw(rows, ua, ps),
        "dr": lambda rows, ua, os_, ps: doubly_robust(rows, ua, os_, ps),
        "naive": lambda rows, ua, os_, ps: naive_contrast(rows, ua),
    }
    tables: Dict[str, Dict[str, Dict[str, float]]] = {}
    for use_adoption in (False, True):
        table: Dict[str, Dict[str, float]] = {}
        for os_ in SPECS:
            for ps in SPECS:
                vals: List[float] = []
                for seed in range(cfg.seed, cfg.seed + cfg.n_seeds):
                    rows = sample_confounded_log(cfg, random.Random(seed))
                    for name, fn in methods.items():
                        est, _ = fn(rows, use_adoption, os_, ps)
                        key = f"{name}/outcome={os_}/propensity={ps}"
                        table.setdefault(key, []).append(est)
        for key, vals in sorted(table.items()):
            b = [v - cfg.effect for v in vals]
            table[key] = {
                "estimate_mean": mean(vals),
                "bias_mean": mean(b),
                "bias_sd": stdev(b) if len(b) > 1 else 0.0,
                "n": len(vals),
            }
        tables["exposure" if not use_adoption else "adoption_proxy"] = table

    # adoption-error sensitivity for DR/g-formula with correct models
    sensitivity: Dict[str, Any] = {}
    for error in (0.0, 0.10, 0.25, 0.50):
        err_cfg = dataclasses_replace(cfg, adoption_error=error)
        row_stats: Dict[str, List[float]] = {}
        for seed in range(err_cfg.seed, err_cfg.seed + err_cfg.n_seeds):
            rows = sample_confounded_log(err_cfg, random.Random(seed))
            est_dr, _ = doubly_robust(rows, True, "correct", "correct")
            est_dr_e, _ = doubly_robust(rows, False, "correct", "correct")
            est_gf, _ = regression_adjustment(rows, True, "correct")
            row_stats.setdefault("dr_on_D", []).append(est_dr)
            row_stats.setdefault("dr_on_E", []).append(est_dr_e)
            row_stats.setdefault("gformula_on_D", []).append(est_gf)
        sensitivity[f"adoption_error_{error}"] = {
            k: {"mean": mean(v), "sd": stdev(v) if len(v) > 1 else 0.0}
            for k, v in row_stats.items()
        }
    return {
        "true_effect": cfg.effect,
        "adoption_error": cfg.adoption_error,
        "double_robustness_table": tables,
        "adoption_error_sensitivity": sensitivity,
    }


def dataclasses_replace(cfg: ConfoundedStepConfig, **kwargs) -> ConfoundedStepConfig:
    return ConfoundedStepConfig(**{**asdict(cfg), **kwargs})


# ---------------------------------------------------------------------------
# Section B -- sequential g-formula for lifecycle values on the D0 world
# ---------------------------------------------------------------------------

def sample_observational_log(world: World, cfg: WorldConfig, n_steps: int,
                             seed: int) -> List[Dict[str, Any]]:
    """Observational log produced by the DEPLOYMENT policy's own exposure
    engine, mirroring `World._rollout_core` step-for-step (adoption-feedback
    boost, C7 coupling, C6 misattribution all included), recorded under the
    status-quo background policy with per-row active status.

    The active-set composition never varies under the status quo, so the
    crowding mechanism (short_term suppressing bridge exposure) has NO
    support in this log -- that support failure is what Section C bounds.
    """
    rng = random.Random(seed)
    bg = world.background_access()
    active = [m for m, act in bg.items() if act == "keep"]
    mem_ids = [m.mem_id for m in world.memories]
    spec = world.spec_map
    last_adoption: Dict[str, float] = {}
    rows: List[Dict[str, Any]] = []
    for t in range(n_steps):
        task = world._task_type(rng, "source")
        difficulty = rng.random()
        n_short = sum(1 for m in active if spec[m].role == ROLE_SHORT_TERM)
        E: Dict[str, float] = {}
        for mid in active:
            mem = spec[mid]
            p = cfg.p_expose
            if mem.role == ROLE_BRIDGE and n_short > 0:
                p *= SHORT_SUPPRESS ** n_short
            p = min(p * (1.0 + 0.5 * last_adoption.get(mid, 0.0)), 1.0)
            E[mid] = 1.0 if rng.random() < p else 0.0
        if world.pair is not None and all(m in E for m in world.pair):
            u, h = world.pair
            E[h] = E[u]
        for mid in bg:            # platform exploration: probe archived
            if mid not in active:
                E[mid] = 1.0 if rng.random() < cfg.p_probe else 0.0
        D: Dict[str, float] = dict(E)
        if cfg.adoption_error > 0.0:
            D = {m: (1.0 - v) if rng.random() < cfg.adoption_error else v
                 for m, v in E.items()}
        y = 0.5 - 0.5 * difficulty
        for mid, e in E.items():
            y += spec[mid].effect * e
        if task in ("rare", "critical"):
            for mid in active:
                if spec[mid].role == ROLE_BRIDGE:
                    y += spec[mid].bridge_bonus
        y += rng.gauss(0.0, cfg.noise)
        for m in mem_ids:
            rows.append({
                "time": float(t), "scope": "source", "item": m,
                "status": "active" if m in active else "archived",
                "task": task, "difficulty": difficulty,
                "exposed": E.get(m, 0.0), "adoption": D.get(m, 0.0),
                "outcome": y, "success": 1.0 if y > 0.0 else 0.0,
            })
        last_adoption = D
    return rows


def _pivot_log(log: Sequence[Dict[str, Any]],
               mem_ids: Sequence[str]) -> Dict[str, Any]:
    """Reconstruct per-time-step rows (the log is per (t, item))."""
    by_time: Dict[float, Dict[str, Any]] = {}
    for row in log:
        t = row["time"]
        entry = by_time.setdefault(t, {"time": t, "task": row["task"],
                                       "difficulty": row["difficulty"],
                                       "outcome": row["outcome"],
                                       "exposed": {}, "adoption": {},
                                       "status": {}})
        entry["exposed"][row["item"]] = row["exposed"]
        entry["adoption"][row["item"]] = row["adoption"]
        entry["status"][row["item"]] = row["status"]
    return {"by_time": by_time, "mem_ids": list(mem_ids)}


def _fit_exposure_model(log: Sequence[Dict[str, Any]],
                        mem_ids: Sequence[str]) -> Dict[str, Any]:
    """P(E_m = 1 | status, previous adoption) per memory, from the log.

    A memory that never appears with a given status leaves that cell
    unidentified (None) -- the source of the support failure.  The probe
    rows (archived items probed by platform exploration) identify the
    archived-status rate.
    """
    counts: Dict[str, Dict[str, Dict[float, List[float]]]] = {
        m: {"active": {0.0: [], 1.0: []}, "archived": {0.0: [], 1.0: []}}
        for m in mem_ids}
    last: Dict[str, float] = {}
    statuses: Dict[str, Dict[str, int]] = {
        m: {"active": 0, "archived": 0} for m in mem_ids}
    by_time = sorted(set(r["time"] for r in log))
    for t in by_time:
        rows_t = [r for r in log if r["time"] == t]
        for m in mem_ids:
            row = next(r for r in rows_t if r["item"] == m)
            statuses[m][row["status"]] += 1
            if m in last:
                counts[m][row["status"]][last[m]].append(row["exposed"])
        for r in rows_t:
            last[r["item"]] = r["adoption"]
    model: Dict[str, Any] = {}
    for m in mem_ids:
        cell: Dict[str, Any] = {}
        for status in ("active", "archived"):
            p0 = (mean(counts[m][status][0.0]) if counts[m][status][0.0]
                  else None)
            p1 = (mean(counts[m][status][1.0]) if counts[m][status][1.0]
                  else None)
            cell[status] = {"p_given_no_adoption": p0,
                            "p_given_adoption": p1,
                            "n_rows": statuses[m][status]}
        model[m] = cell
    return model


def _fit_outcome_model(log: Sequence[Dict[str, Any]],
                       mem_ids: Sequence[str]) -> np.ndarray:
    """Additive outcome model: y ~ 1 + {E_m} + difficulty + task dummies.

    Correctly specified for the D0 per-step mechanism EXCEPT for the active
    status: the bridge status bonus is absorbed by the task coefficients
    (bridges are always active in the log), so a policy that archives a
    bridge keeps receiving it in the model -- an outcome-side support
    failure, documented in the report.
    """
    pivot = _pivot_log(log, mem_ids)
    rows = sorted(pivot["by_time"].values(), key=lambda r: r["time"])
    X: List[List[float]] = []
    y: List[float] = []
    for entry in rows:
        x = [1.0] + [entry["exposed"].get(m, 0.0) for m in mem_ids]
        x += [entry["difficulty"], 1.0 if entry["task"] == "rare" else 0.0,
              1.0 if entry["task"] == "critical" else 0.0]
        X.append(x)
        y.append(entry["outcome"])
    return ols_fit(np.array(X), np.array(y))


def _exposure_rate(model: Dict[str, Any], mem: str, status: str,
                   last_adoption: float) -> Optional[float]:
    """Fitted P(E=1 | status, last adoption), or None if unidentified."""
    cell = model[mem].get(status)
    if cell is None:
        return None
    p = (cell["p_given_adoption"] if last_adoption > 0.5
         else cell["p_given_no_adoption"])
    return p


def _simulate_policy(world: World, cfg: WorldConfig,
                     log: Sequence[Dict[str, Any]],
                     outcome_beta: np.ndarray,
                     exposure_model: Dict[str, Any],
                     mem_ids: Sequence[str],
                     target_id: Optional[str], target_action: Optional[str],
                     n_sims: int, suppress: float = 1.0) -> float:
    """Sequential g-formula rollout under the target persistent-action
    policy.

    keep    -> the memory is in the workspace: exposure follows the fitted
               active-status chain; if that cell is unidentified (the memory
               was never active in the log), the fitted archived/probed rate
               is used as the extrapolated active rate.
    archive -> workspace removal: E = 0 (the D0 oracle convention).
    suppress -> crowding strength applied to bridge exposure while
               short_term memories are active (1.0 = the g-formula's
               extrapolation: crowding invisible to the log).
    """
    rng = random.Random(cfg.seed + 31)
    bg = world.background_access()
    active = [m for m, act in bg.items() if act == "keep"]
    if target_id is not None:
        if target_action == "keep" and target_id not in active:
            active.append(target_id)
        elif target_action == "archive" and target_id in active:
            active.remove(target_id)
    is_bridge = {m: world.spec(m).role == ROLE_BRIDGE for m in mem_ids}
    utilities: List[float] = []
    for _ in range(n_sims):
        last: Dict[str, float] = {m: (1.0 if m in active else 0.0)
                                  for m in mem_ids}
        total = 0.0
        for t in range(cfg.n_epochs):
            task = world._task_type(rng, "source")
            difficulty = rng.random()
            n_short = sum(1 for m in active
                          if world.spec(m).role == ROLE_SHORT_TERM)
            e_vec: List[float] = []
            for m in mem_ids:
                if m in active:
                    p = _exposure_rate(exposure_model, m, "active", last[m])
                    if p is None:               # never active in the log
                        p = _exposure_rate(exposure_model, m, "archived",
                                           last[m])
                    if p is None:
                        p = 0.5
                    if is_bridge[m] and n_short > 0:
                        p = p * (suppress ** n_short)
                else:
                    p = 0.0                     # archive => E = 0
                e_vec.append(1.0 if rng.random() < p else 0.0)
            x = [1.0] + e_vec + [difficulty,
                                 1.0 if task == "rare" else 0.0,
                                 1.0 if task == "critical" else 0.0]
            y = float(np.dot(outcome_beta, np.array(x)))
            total += math.pow(cfg.gamma, t) * y
            for m, e in zip(mem_ids, e_vec):
                last[m] = e
        utilities.append(total)
    return mean(utilities)


def estimate_sequential_g_formula(world: World, cfg: WorldConfig,
                                  log: Sequence[Dict[str, Any]],
                                  n_sims: int = 200) -> Dict[str, Any]:
    """Lifecycle values via the observational sequential g-formula.

    The exposure and outcome processes are fitted from the observational
    log; the persistent action enters only through workspace membership.
    Memories whose active-status exposure cell is unidentified in the log
    are extrapolated from their probed (archived) rate.
    """
    mem_ids = [m.mem_id for m in world.memories]
    exposure_model = _fit_exposure_model(log, mem_ids)
    outcome_beta = _fit_outcome_model(log, mem_ids)
    values: Dict[str, Dict[str, Any]] = {}
    for mem in mem_ids:
        v_keep = _simulate_policy(world, cfg, log, outcome_beta,
                                  exposure_model, mem_ids, mem, "keep", n_sims)
        v_archive = _simulate_policy(world, cfg, log, outcome_beta,
                                     exposure_model, mem_ids, mem, "archive",
                                     n_sims)
        cell = exposure_model[mem]
        values[mem] = {
            "keep": v_keep, "archive": v_archive,
            "lifecycle": v_keep - v_archive,
            "active_support": cell["active"]["n_rows"],
            "archived_support": cell["archived"]["n_rows"],
            "active_rate_p1": cell["active"]["p_given_adoption"],
            "archived_rate": cell["archived"]["p_given_no_adoption"],
        }
    return {
        "estimator": "sequential_g_formula",
        "note": ("exposure process fitted from the deployment log; the "
                 "persistent action enters only through workspace "
                 "membership; crowding/status-bonus support absent from the "
                 "log"),
        "values": values,
    }


# ---------------------------------------------------------------------------
# Section C -- partial identification bounds
# ---------------------------------------------------------------------------

@dataclass
class BoundsConfig:
    n_sims: int = 200
    crowding_grid: Tuple[float, ...] = (0.0, 0.15, 0.5, 1.0)
    seed: int = 41


def partial_identification_bounds(world: World, cfg: WorldConfig,
                                  log: Sequence[Dict[str, Any]],
                                  bc: BoundsConfig | None = None
                                  ) -> Dict[str, Any]:
    """Bounds on lifecycle values over the unidentified mechanism
    parameters.

    The observational log identifies the exposure process per observed
    status only.  Unidentified quantities, bounded from the mechanism
    structure alone:
      * crowding strength s in [0, 1] (short_term suppresses bridge
        exposure) -- no active-set variation in the log;
      * the active-status exposure rate of memories that were never active
        in the log (harmful/short/neutral), bounded in [0, 1];
      * the per-bridge share of the status bonus (never separated: bridges
        are always active), bounded in [0, total].
    The bound grid sweeps the crowding strength; the never-active rate is
    handled by the simulator's extrapolation (probed rate), which lies
    inside the identified range.
    """
    bc = bc or BoundsConfig()
    mem_ids = [m.mem_id for m in world.memories]
    exposure_model = _fit_exposure_model(log, mem_ids)
    outcome_beta = _fit_outcome_model(log, mem_ids)
    results: Dict[str, Any] = {}
    for mem in mem_ids:
        grid: Dict[str, float] = {}
        for s in bc.crowding_grid:
            keep = _simulate_policy(world, cfg, log, outcome_beta,
                                    exposure_model, mem_ids, mem, "keep",
                                    bc.n_sims, suppress=float(s))
            arc = _simulate_policy(world, cfg, log, outcome_beta,
                                   exposure_model, mem_ids, mem, "archive",
                                   bc.n_sims)
            grid[f"s={s:.2f}"] = keep - arc
        lo = min(grid.values())
        hi = max(grid.values())
        decision = ("keep" if lo > 0.0 else
                    "archive" if hi < 0.0 else "unresolved")
        results[mem] = {"lo": lo, "hi": hi, "grid": grid,
                        "bound_decision": decision}
    return {
        "estimator": "partial_identification_bounds",
        "unidentified_mechanisms": [
            "crowding strength s in [0,1]: per-active short_term multiplies "
            "bridge exposure by s (no active-set variation in the log)",
            "active-status exposure rate of never-active memories in [0,1]",
            "per-bridge share of the active-status bonus in [0,total]",
        ],
        "memories": results,
    }


def _oracle_se(world: World, cfg: WorldConfig,
               n_probe: int = 16) -> Dict[str, float]:
    """Empirical MC standard error of the oracle mean for each memory.

    The frozen oracle returns only the mean over n_oracle rollouts, so the
    per-memory noise level is estimated from a small probe sample of
    keep/archive trajectory differences, scaled by 1/sqrt(n_oracle).
    """
    rng = random.Random(cfg.seed + 99)
    se: Dict[str, float] = {}
    for mem in world.memories:
        diffs = []
        for _ in range(n_probe):
            k, _, _ = world.sample_rollout(rng, mem.mem_id, "keep")
            a, _, _ = world.sample_rollout(rng, mem.mem_id, "archive")
            diffs.append(k - a)
        se[mem.mem_id] = pstdev(diffs) / math.sqrt(cfg.n_oracle)
    return se


def run_partial_identification(world: World, cfg: WorldConfig,
                               log: Sequence[Dict[str, Any]],
                               bc: BoundsConfig | None = None
                               ) -> Dict[str, Any]:
    """Compare forced point estimate, partial-ID bounds, and the oracle."""
    mem_ids = [m.mem_id for m in world.memories]
    gf = estimate_sequential_g_formula(world, cfg, log,
                                       n_sims=bc.n_sims if bc else 200)
    bounds = partial_identification_bounds(world, cfg, log, bc)
    true_values = compute_oracle_values(world, cfg)
    se_oracle = _oracle_se(world, cfg)
    table: Dict[str, Any] = {}
    for mem in mem_ids:
        point = gf["values"][mem]["lifecycle"]
        b = bounds["memories"][mem]
        truth = true_values[mem]
        se = se_oracle[mem]
        table[mem] = {
            "true": truth,
            "true_se": se,
            "true_nonzero": abs(truth) > 1.96 * se,
            "point_estimate": point,
            "point_decision": "keep" if point > 0 else "archive",
            "point_sign_error": (point > 0) != (truth > 0),
            "lo": b["lo"], "hi": b["hi"],
            "bounds_nondegenerate": b["lo"] < b["hi"],
            "bound_decision": b["bound_decision"],
            "truth_inside_bounds": b["lo"] <= truth <= b["hi"],
            "bounds_avoid_point_sign_error": (
                b["lo"] <= truth <= b["hi"]
                and b["bound_decision"] != "keep"
                if (point > 0) != (truth > 0) else None),
        }
    t_all = [t for t in table.values()]
    t_nz = [t for t in t_all if t["true_nonzero"]]
    return {
        "n_memories": len(t_all),
        "n_nonzero_truth": len(t_nz),
        "truth_inside_bounds_all": all(t["truth_inside_bounds"]
                                       for t in t_all),
        "truth_inside_bounds_all_nonzero": (all(t["truth_inside_bounds"]
                                                for t in t_nz)
                                            if t_nz else None),
        "point_sign_errors": sum(t["point_sign_error"] for t in t_all),
        "point_sign_errors_on_nonzero_truth": sum(
            t["point_sign_error"] for t in t_nz),
        "point_decision_errors": sum(
            (t["point_decision"] == "keep") != (t["true"] > 0)
            for t in t_all),
        "point_decision_errors_on_nonzero_truth": sum(
            (t["point_decision"] == "keep") != (t["true"] > 0)
            for t in t_nz),
        "bound_decision_errors": sum(
            t["bound_decision"] in ("keep", "archive")
            and (t["bound_decision"] == "keep") != (t["true"] > 0)
            for t in t_all),
        "bound_decision_errors_on_nonzero_truth": sum(
            t["bound_decision"] in ("keep", "archive")
            and (t["bound_decision"] == "keep") != (t["true"] > 0)
            for t in t_nz),
        "n_unresolved_bounds": sum(
            t["bound_decision"] == "unresolved" for t in t_all),
        "bounds_rescue_count": sum(
            t["bounds_avoid_point_sign_error"] is True for t in t_all),
        "table": table,
    }


def run_coexposure_identification(world_cfg: WorldConfig,
                                  ) -> Dict[str, Any]:
    """C7 partial identification: perfectly coupled exposures (bundle).

    The per-item coefficients are rank-deficient (E_h == E_u in the log);
    the bundle contrast IS identified.  Per-item lifecycle values are
    one-sided identified (u >= bundle with harm <= 0), so the gate must
    abstain per item and decide on the bundle.
    """
    cfg = dataclasses_config_replace(world_cfg, co_exposure=True)
    world = World(cfg)
    mem_ids = [m.mem_id for m in world.memories]
    log = sample_observational_log(world, cfg, cfg.n_source_steps,
                                   cfg.seed + 2)
    pivot = _pivot_log(log, mem_ids)
    u, h = world.pair

    # collinearity detection in the outcome design
    rows = sorted(pivot["by_time"].values(), key=lambda r: r["time"])
    X = np.array([[1.0] + [entry["exposed"].get(m, 0.0) for m in mem_ids]
                  for entry in rows])
    eu = X[:, mem_ids.index(u) + 1]
    eh = X[:, mem_ids.index(h) + 1]
    corr = float(np.corrcoef(eu, eh)[0, 1])

    # bundle regression: collapse the pair into one column
    other_cols = [m for m in mem_ids if m not in (u, h)]
    Xb = np.array([[1.0]
                   + [entry["exposed"].get(m, 0.0) for m in other_cols]
                   + [entry["exposed"].get(u, 0.0),
                      entry["difficulty"],
                      1.0 if entry["task"] == "rare" else 0.0,
                      1.0 if entry["task"] == "critical" else 0.0]
                   for entry in rows])
    yb = np.array([entry["outcome"] for entry in rows])
    beta_b = ols_fit(Xb, yb)
    bundle_local = float(beta_b[1 + len(other_cols)])  # pair column index
    # lifecycle bundle value from the log: effect x exposure-rate contrast
    exposure_model = _fit_exposure_model(log, mem_ids)
    rate_u_active = (exposure_model[u]["active"]["p_given_adoption"] or 0.0)
    rate_u_archived = (exposure_model[u]["archived"]["p_given_no_adoption"]
                       or 0.0)
    sum_gamma = sum(math.pow(cfg.gamma, t) for t in range(cfg.n_epochs))
    bundle_lifecycle_log = bundle_local * (rate_u_active - rate_u_archived) \
        * sum_gamma

    bundle_oracle = compute_bundle_oracle(world, cfg, world.pair)
    bundle_lifecycle_true = bundle_oracle["bundle_value"]

    return {
        "pair": list(world.pair),
        "exposure_correlation": corr,
        "rank_deficient": abs(corr) > 0.999,
        "per_item_identifiability": "not identified (rank deficient)",
        "bundle_local_contrast_log": bundle_local,
        "bundle_lifecycle_log": bundle_lifecycle_log,
        "bundle_lifecycle_true": bundle_lifecycle_true,
        "bundle_recovered": abs(bundle_lifecycle_log - bundle_lifecycle_true)
        < 0.25 * abs(bundle_lifecycle_true),
        "per_item_identified_set": {
            u: {"constraint": f"beta_u + beta_h = {bundle_local:.3f}",
                "one_sided": f"beta_u >= {bundle_local:.3f} (harm <= 0)"},
            h: {"constraint": f"beta_u + beta_h = {bundle_local:.3f}",
                "one_sided": "beta_h <= 0 (harm role)"},
        },
        "gate": "per-item unresolved; bundle-level decision available",
    }

# ---------------------------------------------------------------------------
# Section D -- qualification calibration and coverage-risk curve
# ---------------------------------------------------------------------------

def run_calibration(cfg: WorldConfig | None = None,
                    n_seeds: int = 8,
                    z_grid: Tuple[float, ...] = (0.5, 1.0, 1.28, 1.64, 1.96, 2.58)
                    ) -> Dict[str, Any]:
    """Protocol-route calibration across seeds: Brier, ECE, sign error,
    CI coverage, and the coverage-risk curve over the threshold z*."""
    triples: List[Dict[str, float]] = []
    for seed in range(cfg_seed_start(cfg), cfg_seed_start(cfg) + n_seeds):
        wcfg = dataclasses_config_replace(cfg, seed=seed,
                                          n_trajectories=40, n_oracle=80)
        world = World(wcfg)
        mem_ids = [m.mem_id for m in world.memories]
        rct = estimate_sqcad_rct(world, wcfg, mem_ids)
        true_values = compute_oracle_values(world, wcfg)
        for mem in mem_ids:
            est = rct[mem]
            if est["estimate"] is None:
                continue
            triples.append({"est": est["estimate"], "se": est["se"],
                            "true": true_values[mem]})
    n = len(triples)
    ests = np.array([t["est"] for t in triples])
    ses = np.array([t["se"] for t in triples])
    trues = np.array([t["true"] for t in triples])
    z = ests / np.maximum(ses, 1e-9)
    p_hat = np.array([_norm_cdf(float(v)) for v in z])   # P(V > 0)
    c = (trues > 0).astype(float)

    brier = float(np.mean((p_hat - c) ** 2))
    # ECE in 5 bins
    bins = np.linspace(0.0, 1.0, 6)
    ece = 0.0
    bin_stats = {}
    for i in range(5):
        sel = (p_hat >= bins[i]) & (p_hat < bins[i + 1]) | \
            ((i == 4) & (p_hat <= 1.0))
        if sel.sum() == 0:
            continue
        conf = p_hat[sel].mean()
        acc = c[sel].mean()
        ece += (sel.sum() / n) * abs(conf - acc)
        bin_stats[f"bin_{i}"] = {"n": int(sel.sum()), "conf": float(conf),
                                 "freq": float(acc)}
    covered = np.mean((np.abs(ests - trues) <= 1.96 * ses))

    curve: Dict[str, Any] = {}
    for z_star in z_grid:
        decided = np.abs(z) >= z_star
        n_d = int(decided.sum())
        if n_d == 0:
            curve[f"z={z_star}"] = {"coverage": 0.0, "error_rate": None,
                                    "n_decided": 0, "n_total": n,
                                    "forgone_value": float(trues[trues > 0].sum())}
            continue
        decided_sign = (ests[decided] > 0).astype(float)
        errors = (decided_sign != c[decided]).mean()
        forgone = float(np.sum(trues[(~decided) & (trues > 0)]))
        curve[f"z={z_star}"] = {
            "coverage": n_d / n,
            "error_rate": float(errors),
            "n_decided": n_d, "n_total": n,
            "forgone_value": forgone,
        }
    return {
        "n_memories_seeds": n,
        "brier": brier,
        "ece": ece,
        "bin_stats": bin_stats,
        "sign_error_confident_z196": float(
            np.mean((np.sign(ests) != np.sign(trues))[np.abs(z) >= 1.96])
            if (np.abs(z) >= 1.96).any() else None),
        "ci_coverage_95": float(covered),
        "coverage_risk_curve": curve,
        "note": ("zero confident errors at z=1.96 is necessary but not "
                 "sufficient; the curve reports how much coverage and value "
                 "the gate gives up to achieve it"),
    }


def cfg_seed_start(cfg: WorldConfig) -> int:
    return cfg.seed


def dataclasses_config_replace(cfg: WorldConfig, **kwargs) -> WorldConfig:
    return WorldConfig(**{**asdict(cfg), **kwargs})


# ---------------------------------------------------------------------------
# Section E -- sample-size / bias / CI-coverage curves
# ---------------------------------------------------------------------------

def run_sample_size_curves() -> Dict[str, Any]:
    """RCT: bias/RMSE/coverage vs n_trajectories; g-formula/DR: vs n_steps."""
    rct_curve: Dict[str, Any] = {}
    for n_traj in (10, 30, 100, 300):
        biases: List[float] = []
        rmses: List[float] = []
        coverages: List[float] = []
        for seed in (3, 5, 7):
            wcfg = WorldConfig(seed=seed, n_trajectories=n_traj,
                               n_oracle=150, n_epochs=80)
            world = World(wcfg)
            mem_ids = [m.mem_id for m in world.memories]
            rct = estimate_sqcad_rct(world, wcfg, mem_ids)
            true_values = compute_oracle_values(world, wcfg)
            for mem in mem_ids:
                e = rct[mem]
                b = e["estimate"] - true_values[mem]
                biases.append(b)
                rmses.append(b * b)
                coverages.append(e["ci_low"] <= true_values[mem] <= e["ci_high"])
        rct_curve[f"n_trajectories={n_traj}"] = {
            "bias": mean(biases), "rmse": math.sqrt(mean(rmses)),
            "ci_coverage": mean(coverages), "n": len(biases),
        }
    dr_curve: Dict[str, Any] = {}
    for n_steps in (300, 1000, 3000, 10000):
        biases: List[float] = []
        for seed in (101, 102, 103):
            cfg_c = ConfoundedStepConfig(n_steps=n_steps, seed=seed,
                                         n_seeds=1)
            rows = sample_confounded_log(cfg_c, random.Random(seed))
            est, _ = doubly_robust(rows, False, "correct", "correct")
            biases.append(est - cfg_c.effect)
        dr_curve[f"n_steps={n_steps}"] = {
            "bias": mean(biases),
            "bias_sd": stdev(biases) if len(biases) > 1 else 0.0,
            "n_seeds": len(biases),
        }
    return {"rct": rct_curve, "dr_observational": dr_curve}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_estimation_validity(fast: bool = False) -> Dict[str, Any]:
    if fast:
        dr_cfg = ConfoundedStepConfig(n_steps=800, n_seeds=2)
        world_cfg = WorldConfig(seed=7, n_epochs=60, n_trajectories=20,
                                n_oracle=40, n_source_steps=600)
        n_seeds = 3
        n_sims = 60
    else:
        dr_cfg = None
        world_cfg = WorldConfig()
        n_seeds = 8
        n_sims = 200
    world = World(world_cfg)
    mem_ids = [m.mem_id for m in world.memories]

    log = sample_observational_log(world, world_cfg, world_cfg.n_source_steps,
                                   world_cfg.seed + 2)
    dr = run_double_robustness(dr_cfg)
    gf = estimate_sequential_g_formula(world, world_cfg, log, n_sims=n_sims)
    partial = run_partial_identification(world, world_cfg, log,
                                         BoundsConfig(n_sims=n_sims))
    c7 = run_coexposure_identification(world_cfg)
    calibration = run_calibration(world_cfg, n_seeds=n_seeds)
    curves = run_sample_size_curves()
    true_values = compute_oracle_values(world, world_cfg)
    local_effects = compute_local_effects(world, world_cfg)

    # head-to-head: estimator lifecycle estimates vs oracle lifecycle values
    comparison: Dict[str, Any] = {}
    for mem in mem_ids:
        comparison[mem] = {
            "true_lifecycle": true_values[mem],
            "true_local_effect": local_effects[mem],
            "gformula_lifecycle": gf["values"][mem]["lifecycle"],
            "gformula_sign_error": (
                (gf["values"][mem]["lifecycle"] > 0) != (true_values[mem] > 0)),
        }
    return {
        "protocol": {
            "purpose": ("estimation-validity experiments: observational "
                        "route (Theorem 3(b)(c)), double robustness, "
                        "partial identification, calibration, coverage-risk"),
            "fast": fast,
            "world_n_memories": len(mem_ids),
            "n_epochs": world_cfg.n_epochs,
            "gamma": world_cfg.gamma,
        },
        "double_robustness": dr,
        "sequential_g_formula": gf,
        "partial_identification": partial,
        "coexposure_c7": c7,
        "calibration": calibration,
        "sample_size_curves": curves,
        "estimator_comparison": comparison,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true",
                        help="reduced sizes for CI/test runs")
    parser.add_argument("--output", type=Path,
                        default=Path("results/estimation_validity.json"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_estimation_validity(fast=args.fast)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({"double_robustness": result["double_robustness"]
                      ["double_robustness_table"],
                      "partial_identification":
                      result["partial_identification"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
