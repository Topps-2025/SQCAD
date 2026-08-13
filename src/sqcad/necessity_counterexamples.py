"""Gate-necessity counterexamples (Lemma A-D, Theorem 4 computation).

Necessity of the C1-C8 family is FALSE per-condition (each lemma gives a
world where the condition fails but the lifecycle contrast is still
identified via an alternative route); necessity of the GATE is TRUE
(Theorem 4: any committing rule on the unidentified class has worst-case
regret >= |tau1||tau2|/(|tau1|+|tau2|) and worst-case error probability
>= 1/2; only refusal or fresh interventional evidence beats the bound).

Lemma A: C6 (adoption measurement) is route-specific.  The protocol-route
    rollout estimator never reads the adoption proxy D: it is unbiased for
    the realized world's contrast under ANY adoption mechanism (verified
    at adoption_error 0.01 vs 0.99 -- mis-measurement severity does not
    bias estimation; it corrupts only the observational adoption kernel
    and the gate's mechanism diagnosis).
Lemma C: C2/C3 (exchangeability/positivity via randomization) are
    replaceable by an instrument.  A confounded world with no
    randomization and unobserved U: Wald IV identifies tau; the
    observational contrast is biased.  The substitute's cost is an
    untestable exclusion assertion, where the protocol route's C2/C3 are
    design guarantees -- the auditable-condition advantage of the family.
Lemma D: C8 (stability) is necessary only for cross-time reuse.  Under
    measurement drift the rollout estimator is unbiased for the CURRENT
    (drifted) value and biased for the pre-registered intended value.
Theorem 4: two-world sign-flip pair from Theorem 1 (tau1 = +1650,
    tau2 = -1100, identical observational distributions): worst-case
    regret of any committing rule >= tau1*tau2/(tau1+tau2) = 660, error
    probability >= 1/2; the gate attains 0 false decisions.
"""

from __future__ import annotations

import argparse
import json
import random
from statistics import mean
from typing import Any, Dict, List

from sqcad.identification_recovery_experiment import (
    World, WorldConfig, compute_oracle_values, estimate_sqcad_rct)


# ---------------------------------------------------------------------------
# Lemma A: C6 is not necessary for the protocol route
# ---------------------------------------------------------------------------

def lemma_a(seed: int = 3, n_trajectories: int = 300, n_oracle: int = 300,
            n_epochs: int = 80) -> Dict[str, Any]:
    """Same seed, two worlds differing ONLY in adoption mis-measurement
    severity (0.01 vs 0.99).  The protocol estimator never reads D, so in
    each world it is unbiased for that world's own oracle contrast -- C6
    failure does not bias the protocol route (it corrupts the observational
    adoption kernel and the gate's diagnosis, which are different paths)."""
    out: Dict[str, Any] = {}
    for ae in (0.01, 0.99):
        cfg = WorldConfig(seed=seed, n_trajectories=n_trajectories,
                          n_oracle=n_oracle, n_epochs=n_epochs,
                          adoption_error=ae)
        world = World(cfg)
        est = estimate_sqcad_rct(world, cfg, ["m0"])["m0"]["estimate"]
        truth = compute_oracle_values(world, cfg)["m0"]
        out[f"adoption_error_{ae}"] = {
            "estimate": est, "oracle": truth, "bias": est - truth,
        }
    return {"protocol": {"seed": seed, "n_trajectories": n_trajectories,
                         "n_oracle": n_oracle, "n_epochs": n_epochs,
                         "note": "estimator reads E and Y only; D enters "
                                 "neither the rollout nor the oracle"},
            **out}


# ---------------------------------------------------------------------------
# Lemma C: IV replaces C2/C3 (no randomization, unobserved confounder)
# ---------------------------------------------------------------------------

def lemma_c(n: int = 40000, tau: float = 1.0, gamma: float = 0.8,
            alpha: float = 0.7, delta: float = 0.5, seed: int = 11) -> Dict[str, Any]:
    """Self-contained IV world: Z (external quota lottery, Bernoulli 0.5)
    shifts the persistent keep action A; unobserved U confounds A-Y.
    Y = tau*A + gamma*U + eps.  Wald: (E[Y|Z=1]-E[Y|Z=0]) /
    (E[A|Z=1]-E[A|Z=0]) -> tau under exclusion + relevance; the
    observational contrast E[Y|A=1]-E[Y|A=0] is biased by gamma."""
    rng = random.Random(seed)
    by_z: Dict[int, List[float]] = {0: [], 1: []}
    by_z_a: Dict[int, List[float]] = {0: [], 1: []}
    by_a: Dict[int, List[float]] = {0: [], 1: []}
    for _ in range(n):
        z = 1 if rng.random() < 0.5 else 0
        u = rng.gauss(0.0, 1.0)
        nu = rng.gauss(0.0, 0.5)
        a = 1 if (alpha * z + delta * u + nu) > 0.0 else 0
        y = tau * a + gamma * u + rng.gauss(0.0, 0.1)
        by_z[z].append(y)
        by_z_a[z].append(a)
        by_a[a].append(y)
    num = mean(by_z[1]) - mean(by_z[0])
    den = mean(by_z_a[1]) - mean(by_z_a[0])
    iv = num / den if den != 0.0 else float("nan")
    obs = mean(by_a[1]) - mean(by_a[0])
    return {"n": n, "tau_true": tau, "iv_estimate": iv, "iv_error": iv - tau,
            "obs_contrast": obs, "obs_bias": obs - tau,
            "first_stage": den,
            "note": "C2/C3 violated (no randomization, no protocol "
                    "propensity); IV identifies tau at the cost of an "
                    "untestable exclusion assertion"}


# ---------------------------------------------------------------------------
# Lemma D: C8 is necessary only for cross-time reuse
# ---------------------------------------------------------------------------

def lemma_d(seed: int = 3, n_trajectories: int = 300, n_oracle: int = 300,
            n_epochs: int = 80) -> Dict[str, Any]:
    """measurement_drift world: the rollout estimator samples the drifted
    mechanism (drift=cfg.measurement_drift) and is unbiased for the CURRENT
    value; biased for the pre-registered intended value (the oracle always
    evaluates the intended estimand, drift never applied)."""
    cfg = WorldConfig(seed=seed, n_trajectories=n_trajectories,
                      n_oracle=n_oracle, n_epochs=n_epochs,
                      measurement_drift=True)
    world = World(cfg)
    est = estimate_sqcad_rct(world, cfg, ["m0"])["m0"]["estimate"]
    intended = compute_oracle_values(world, cfg)["m0"]
    rng = random.Random(cfg.seed + 99)
    keep_u = [world.sample_rollout(rng, "m0", "keep", drift=True)[0]
              for _ in range(n_oracle)]
    arc_u = [world.sample_rollout(rng, "m0", "archive", drift=True)[0]
             for _ in range(n_oracle)]
    current = mean(keep_u) - mean(arc_u)
    return {"seed": seed, "n_trajectories": n_trajectories,
            "n_oracle": n_oracle, "n_epochs": n_epochs,
            "estimate": est, "oracle_intended": intended,
            "oracle_current": current,
            "bias_vs_intended": est - intended,
            "bias_vs_current": est - current,
            "note": "C8 failure biases the INTENDED estimand only; fresh "
                    "randomization identifies the current value (C8 is an "
                    "estimand-stability condition, not an identification "
                    "condition)"}


# ---------------------------------------------------------------------------
# Theorem 4: necessity of the gate on the unidentified class
# ---------------------------------------------------------------------------

def theorem4_regret(tau1: float = 1650.0, tau2: float = 1100.0,
                    p_steps: int = 100) -> Dict[str, Any]:
    """Theorem 1's verified pair: P(O|M1)=P(O|M2), tau1=+1650 (keep
    optimal in M1), tau2=-1100 (archive optimal in M2).  Any committing
    rule with keep-probability p (identical in both worlds) has worst-case
    expected regret max((1-p)|tau1|, p|tau2|) >= tau1*tau2/(tau1+tau2),
    attained at p = tau1/(tau1+tau2) = 0.6; worst-case error probability
    max(1-p, p) >= 0.5.  The gated rule (unresolved) has 0 false
    decisions and 0 decision regret."""
    ps = [i / p_steps for i in range(p_steps + 1)]
    worst = [max((1.0 - p) * tau1, p * tau2) for p in ps]
    argmin = min(range(len(ps)), key=lambda i: worst[i])
    bound = tau1 * tau2 / (tau1 + tau2)
    return {"tau1": tau1, "tau2": tau2,
            "theoretical_bound": bound,
            "grid_min_worst_regret": worst[argmin],
            "argmin_p": ps[argmin],
            "error_probability_lower_bound": 0.5,
            "gate_false_decisions": 0.0, "gate_decision_regret": 0.0,
            "note": "below the bound requires refusal (unresolved) or "
                    "fresh interventional evidence (protocol route)"}


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=str,
                        default="results/necessity_counterexamples.json")
    args = parser.parse_args()
    result = {
        "lemma_a_c6_not_route_necessary": lemma_a(),
        "lemma_c_iv_replaces_c2c3": lemma_c(),
        "lemma_d_c8_estimand_stability": lemma_d(),
        "theorem4_gate_necessity": theorem4_regret(),
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({
        "lemma_a": {k: v for k, v in result["lemma_a_c6_not_route_necessary"].items()
                    if isinstance(v, dict)},
        "lemma_c_iv_error": result["lemma_c_iv_replaces_c2c3"]["iv_error"],
        "lemma_c_obs_bias": result["lemma_c_iv_replaces_c2c3"]["obs_bias"],
        "lemma_d_bias_intended": result["lemma_d_c8_estimand_stability"]["bias_vs_intended"],
        "lemma_d_bias_current": result["lemma_d_c8_estimand_stability"]["bias_vs_current"],
        "theorem4": result["theorem4_gate_necessity"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
