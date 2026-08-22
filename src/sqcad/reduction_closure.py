"""T2/P4 theory-closure experiments (16-).

T2 (Theorem 2, strict reduction-separation):
  * pairing identity: Regret_K(pi) + Regret_A(pi) = tau*p*(T - n_early) exactly
    for the coupled censored-committed policies used by the reduction proof;
  * reduction image: standard learners (UCB, contextual bandit, log OPE)
    consuming only phi(obs) -- the image under a faithful feedback-preserving
    reduction -- accrue exact linear regret on the W2 pair (Theta(T));
  * forbidden-phi control: contextual_bandit_oracle -- the image context would
    depend on the latent world identity (phi NOT world-independent); the
    smuggled signal makes the same learner succeed, pinning the impossibility
    on the phi constraint (16- 1.5-1.6).

P4 (Theorems 3-4, minimax probe lower bound):
  * detection sweep: exact symmetric-Gaussian fixed-sample N*(delta) =
    ceil((sigma Phi^-1(1-delta)/tau)^2) vs
    empirical probes-to-decision of the CI-exclusion rule under the probe
    channel (attempt rate q, success rho) -- E[N]/N* is inspected as an
    order/constant-factor diagnostic in the binding regime (16- 2.2);
  * regret decomposition: total regret = probe cost + restore wait (lifecycle
    loss) + wrong-governance loss.  The strict finite-horizon comparison uses
    the truncated survival-sum lifecycle lower bound; the historical
    L=(N*/rho)(tau*p/q+c_probe) is retained only as an infinite-horizon
    diagnostic.  U_cons is likewise a conservative diagnostic envelope.
"""

import math
import random
from statistics import NormalDist
from typing import Any, Dict, List, Sequence, Tuple

from sqcad.self_obscuring_ablation import (
    config_for, build_world, run_policy)

TAU = 10.0
P_EXPOSE = 0.6
N_EARLY = 50.0
HORIZON = 2000
PER_STEP_PAIR_SUM = TAU * P_EXPOSE * (HORIZON - N_EARLY)  # 11700


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def _mean_of_sum(slopes_a: Sequence[float],
                 slopes_b: Sequence[float]) -> float:
    """mean(slopes_a[i] + slopes_b[i]) -- list, not generator, version."""
    return sum(x + y for x, y in zip(slopes_a, slopes_b)) / len(slopes_a)


# ---------------------------------------------------------------------------
# T2: pairing identity + reduction image
# ---------------------------------------------------------------------------


def pairing_identity(n_seeds: int = 12, seed0: int = 21,
                     horizon: int = HORIZON) -> Dict[str, Any]:
    """Check the paired identity on the coupled policies used here.

    The formal reduction theorem is restricted to the fully censored,
    committed/no-restore subclass.  ``random_flip`` is retained as a coupled
    implementation control, not as evidence for an arbitrary-policy theorem.
    """
    policies = ("watchful_no_restore", "association_commit",
                "watchful_restore", "random_flip")
    out: Dict[str, Any] = {}
    for policy in policies:
        diffs: List[float] = []
        sums: List[float] = []
        for seed in range(seed0, seed0 + n_seeds):
            k = run_policy(build_world(config_for(seed, "K", "W2")),
                           policy)
            a = run_policy(build_world(config_for(seed, "A", "W2")),
                           policy)
            s = k["regret_T"] + a["regret_T"]
            sums.append(s)
            diffs.append(abs(s - PER_STEP_PAIR_SUM))
        out[policy] = {
            "pair_sum_mean": _mean(sums),
            "expected_pair_sum": PER_STEP_PAIR_SUM,
            "max_abs_deviation": max(diffs),
            "exact": max(diffs) < 1e-9,
        }
    return out


def reduction_image(n_seeds: int = 12, seed0: int = 21,
                    horizon: int = HORIZON) -> Dict[str, Any]:
    """T2 numerics (16- 1.6): standard learners on the image under a faithful
    feedback-preserving reduction (phi = identity on observations) accrue
    exact Theta(T) regret on the W2 pair; the forbidden-phi control (image
    context would see the latent world identity) succeeds.

    contextual_bandit is a third control: it starts "kept" and is therefore
    NEVER censored -- it learns the stream (slope ~0).  The failure of the
    other learners is thus pinned on the ACTION-DEPENDENT censoring (the
    committed archive silences the evidence flow), not on learner weakness."""
    learners = ("bandit_ucb", "standard_ope", "contextual_bandit",
                "contextual_bandit_oracle")
    out: Dict[str, Any] = {}
    for learner in learners:
        slopes_k: List[float] = []
        slopes_a: List[float] = []
        for seed in range(seed0, seed0 + n_seeds):
            k = run_policy(build_world(config_for(seed, "K", "W2")),
                           learner)
            a = run_policy(build_world(config_for(seed, "A", "W2")),
                           learner)
            slopes_k.append(k["per_step_slope"])
            slopes_a.append(a["per_step_slope"])
        out[learner] = {
            "mean_slope_K": _mean(slopes_k),
            "mean_slope_A": _mean(slopes_a),
            "max_slope_K": max(slopes_k),
            "mean_pair_sum": _mean_of_sum(slopes_k, slopes_a) * horizon,
        }
    return out


# ---------------------------------------------------------------------------
# P4: detection bound + regret decomposition under the probe channel
# ---------------------------------------------------------------------------

TAUS = (0.25, 0.5, 1.0, 2.0, 5.0)
QS = (0.05, 0.2, 1.0)
Z = 1.96
DELTA = 0.05


def _n_star(tau: float, sigma: float = 1.0,
            delta: float = DELTA) -> float:
    """Exact integer threshold for the symmetric Gaussian fixed-sample test.

    For ``N(+tau, sigma^2)`` versus ``N(-tau, sigma^2)``, the likelihood-ratio
    test has maximal error ``Phi(-|tau|*sqrt(n)/sigma)``.  This is a
    fixed-sample threshold only; it makes no claim about arbitrary sequential
    stopping rules or their coverage.
    """
    if not 0.0 < delta < 0.5:
        raise ValueError("delta must lie in (0, 0.5) for the two-point bound")
    if tau == 0.0 or sigma <= 0.0:
        raise ValueError("tau must be nonzero and sigma positive")
    z = NormalDist().inv_cdf(1.0 - delta)
    return float(math.ceil((sigma * z / abs(tau)) ** 2))


def _bh_n_lower(tau: float, sigma: float = 1.0,
                delta: float = DELTA) -> float:
    """Generic Bretagnolle--Huber/Le Cam weak lower bound.

    This bound is distribution-agnostic and is intentionally weaker than the
    exact Gaussian threshold used by ``_n_star``.
    """
    if not 0.0 < delta < 0.5:
        raise ValueError("delta must lie in (0, 0.5) for the two-point bound")
    if tau == 0.0 or sigma <= 0.0:
        raise ValueError("tau must be nonzero and sigma positive")
    kl = 2.0 * tau ** 2 / (sigma ** 2)
    return math.log(1.0 / (4.0 * delta)) / kl


def _finite_lifecycle_lower(n: int, success_prob: float,
                            horizon: int) -> float:
    """Survival-sum lower bound for a finite-horizon N-success wait.

    The bound is E[min(S_N, H)] for iid Bernoulli(success_prob) trials.
    It is the finite-horizon replacement for the untruncated N/success_prob
    expression; no probe-cost lower bound is implied when the horizon ends
    before N successes are collected.
    """
    if n < 1 or horizon < 0 or not 0.0 <= success_prob <= 1.0:
        raise ValueError("invalid finite-horizon negative-binomial parameters")
    # Distribution of the number of successes after the current step,
    # capped at n.  The CDF at n-1 is the survival probability for S_N.
    mass = [0.0] * (n + 1)
    mass[0] = 1.0
    total = 0.0
    for _ in range(horizon):
        total += sum(mass[:n])
        nxt = [0.0] * (n + 1)
        for successes, prob in enumerate(mass):
            nxt[successes] += prob * (1.0 - success_prob)
            nxt[min(n, successes + 1)] += prob * success_prob
        mass = nxt
    return total


def _ci_stop_trial(tau_true: float, q: float, rho: float, sigma: float,
                   z: float, rng: random.Random,
                   max_steps: int = 100000) -> Tuple[int, int, float]:
    """One trial of the CI-exclusion rule under the probe channel:
    archived state, probe attempt with prob q per step, success rho,
    observation y ~ N(tau_true, sigma^2).  Stops when the CI of probed
    observations excludes 0 on the positive side (commit keep).  Returns
    (steps, attempts, final mean)."""
    ev_sum = ev_n = 0.0
    attempts = 0
    steps = 0
    while steps < max_steps:
        steps += 1
        if rng.random() > q:
            continue
        attempts += 1
        if rng.random() > rho:
            continue
        ev_sum += tau_true + rng.gauss(0.0, sigma)
        ev_n += 1.0
        if ev_n > 1 and ev_sum / ev_n - z * sigma / math.sqrt(ev_n) > 0.0:
            break
    return steps, attempts, (ev_sum / ev_n if ev_n else 0.0)


def detection_bound_sweep(taus: Sequence[float] = TAUS,
                          qs: Sequence[float] = QS,
                          n_seeds: int = 200, seed0: int = 3) -> Dict[str, Any]:
    """Theorems 3-4 + Corollary 4 (16- 2.2-2.4): per (tau, q), N*(delta) vs
    empirical probes-to-decision and the regret decomposition
    E[Regret_K] = c_probe*attempts + tau*p*steps (lifecycle loss while the
    wrong archive persists), compared against the finite-horizon truncated
    lifecycle lower bound and the asymptotic diagnostic
    L_inf = (N*/rho)(tau*p/q + c_probe).  U_cons is a conservative diagnostic
    envelope; the exact Bernoulli-model upper is
    tau*p/(q*rho) + c_probe/rho + c_restore."""
    sigma = 1.0
    rho = 1.0
    tau_p = TAU * P_EXPOSE
    c_probe = 30.0
    c_restore = 80.0
    out: Dict[str, Any] = {}
    for tau in taus:
        n_star = _n_star(tau, sigma)
        row: Dict[str, Any] = {"n_star": n_star,
                               "kl": 2.0 * tau ** 2 / sigma ** 2}
        for q in qs:
            steps_l: List[float] = []
            attempts_l: List[float] = []
            for si in range(n_seeds):
                rng = random.Random(seed0 * 1000 + si)
                s, att, _ = _ci_stop_trial(tau, q, rho, sigma, Z, rng)
                steps_l.append(float(s))
                attempts_l.append(float(att))
            e_steps = _mean(steps_l)
            e_att = _mean(attempts_l)
            regret_k = c_probe * e_att + tau_p * e_steps
            finite_lifecycle_lower = tau_p * _finite_lifecycle_lower(
                int(n_star), q * rho, int(HORIZON - N_EARLY))
            lower_asymptotic = (n_star / rho) * (tau_p / q + c_probe)
            upper = (tau_p + c_probe) / (q * rho) + c_restore
            row[f"q_{q}"] = {
                "empirical_steps": e_steps,
                "empirical_attempts": e_att,
                "probe_ratio_E_over_Nstar": e_att / n_star if n_star > 0.01
                else None,
                "regret_K": regret_k,
                "lower_bound_L": lower_asymptotic,
                "lower_bound_finite_lifecycle": finite_lifecycle_lower,
                "upper_bound_U": upper,
                "regret_over_L": regret_k / lower_asymptotic,
                "regret_over_finite_lifecycle_lower": (
                    regret_k / finite_lifecycle_lower
                    if finite_lifecycle_lower > 0.0 else None),
                "U_over_L": upper / lower_asymptotic,
                "decomposition": {
                    "probe_cost": c_probe * e_att,
                    "restore_wait_lifecycle": tau_p * e_steps,
                },
            }
        out[f"tau_{tau}"] = row
    return {"delta": DELTA, "z": Z, "sigma": sigma, "rho": rho,
            "c_probe": c_probe, "c_restore": c_restore,
            "tau_p": tau_p, "taus": list(taus), "qs": list(qs),
            "rows": out}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("results/reduction_closure.json"))
    parser.add_argument("--seeds", type=int, default=12)
    args = parser.parse_args()
    out = {
        "protocol": {
            "purpose": "T2 strict reduction-separation and P4 minimax probe "
                       "lower bound (16-) -- pairing identity, reduction "
                       "image, forbidden-phi control, detection sweep, "
                       "regret decomposition vs T1(b)",
            "tau": TAU, "p_expose": P_EXPOSE, "n_early": N_EARLY,
            "horizon": HORIZON,
        },
        "pairing_identity": pairing_identity(n_seeds=args.seeds),
        "reduction_image": reduction_image(n_seeds=args.seeds),
        "detection_bound_sweep": detection_bound_sweep(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "protocol"},
                     ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()
