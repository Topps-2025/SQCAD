"""P0-P4 upgrades per 13-必要性证明方向 (docs/自用/01-research-gap/研究逻辑与理论证明/13-...).

P0-1 lemma_a2: C6 isolation.  The TRUE adoption mechanism is unchanged;
    only the OBSERVED proxy is polluted.  Protocol-route estimates are
    bit-identical across pollution levels (the estimator reads A, E, Y
    only), while the observational adoption-kernel contrast degrades.
P0-2 lemma_c2: lifecycle IV.  Persistent access action + multi-period
    discounted return + exposure-only-when-kept feedback + unobserved
    confound + valid instrument: Wald-IV on the discounted return
    recovers the lifecycle contrast under additive effect homogeneity
    (otherwise LATE on Z-induced keepers -- documented caveat).
P1 theorem5: general decision-identification theorem.  For a binary
    persistent-access decision with identification set [L, U]:
    committing is worst-case safe iff [L, U] does not straddle 0; if
    L < 0 < U, minimax regret is R*(L,U) = U(-L)/(U-L) at commit prob
    p* = U/(U-L).  Instance checks: crossing pair (-1100, 1650) -> 660;
    decision-identified-not-point-identified pair (500, 1650) -> safe keep.
P2 governance_boundary: optimal choice among commit / defer / probe
    given (L, U, C_defer, C_probe, post-probe shrink).  Connects the
    identification theory to the Gate 4 cost contract (lambda_probe).
P3 self_confirming: no-exploration -> linear regret (self-confirming
    unidentifiability: a wrongly archived memory never re-enters the
    evidence stream); budgeted probing -> regret plateaus after
    evidence-driven restoration.
P4 probe_complexity: KL lower bound N >= log(1/delta)/KL(P1||P2) vs
    SQCAD-style stopping rule (probe until the CI excludes 0): empirical
    mean probe count matches the lower bound up to a constant factor.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from statistics import mean, pstdev
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# P0-1: C6 isolation -- proxy pollution vs mechanism change
# ---------------------------------------------------------------------------

def lemma_a2_isolated_proxy(n_mem: int = 2000, h: int = 30, tau: float = 2.0,
                            p_expose: float = 0.6, noise: float = 0.5,
                            eps_values: Tuple[float, ...] = (0.0, 0.3),
                            seed: int = 7) -> Dict[str, Any]:
    """One world generated ONCE (mechanism fixed); for each pollution
    level eps the logged proxy D_obs is D_true with probability 1-eps
    else flipped.  The protocol estimator uses (A, Y) only, so it is
    identical across eps by construction; the observational
    adoption-kernel contrast E[Y|D_obs=1]-E[Y|D_obs=0] dilutes as eps
    grows -- C6 is route-specific (protocol: not necessary;
    observational adoption kernel: necessary)."""
    rng = random.Random(seed)
    a = [rng.random() < 0.5 for _ in range(n_mem)]          # randomized action
    y_keep: List[float] = []
    y_arc: List[float] = []
    d_true: List[int] = []
    for i in range(n_mem):
        g_keep = g_arc = 0.0
        obs_keep = obs_arc = []
        for _ in range(h):
            e = rng.random() < p_expose                     # kept exposure
            y = tau * e + rng.gauss(0.0, noise)             # archived: e=0
            g_keep += y
            g_arc += rng.gauss(0.0, noise)
            obs_keep.append(int(e))
        y_keep.append(g_keep / h)
        y_arc.append(g_arc / h)
        d_true.append(1 if mean(obs_keep) > 0.5 else 0)     # true adoption
    out: Dict[str, Any] = {"protocol": {
        "n_mem": n_mem, "h": h, "tau": tau, "p_expose": p_expose,
        "noise": noise, "seed": seed,
        "note": "true adoption mechanism fixed across eps; only D_obs "
                "is polluted -- mechanism change vs measurement error "
                "are isolated"}}
    g_real = [y_keep[i] if a[i] else y_arc[i] for i in range(n_mem)]
    for eps in eps_values:
        rng2 = random.Random(seed + 1000)
        d_obs = [1 - v if rng2.random() < eps else v for v in d_true]
        # protocol route: realized outcomes grouped by the RANDOMIZED
        # action -- reads (A, E, Y) only, never the proxy
        est_proto = mean(g_real[i] for i in range(n_mem) if a[i]) \
            - mean(g_real[i] for i in range(n_mem) if not a[i])
        # observational adoption-kernel contrast (selection-weighted
        # quantity by construction; dilutes toward zero as the proxy is
        # polluted: random flip at rate eps scales it by ~(1 - 2 eps))
        y1 = [y_keep[i] for i in range(n_mem) if d_obs[i] == 1]
        y0 = [y_keep[i] for i in range(n_mem) if d_obs[i] == 0]
        est_obs = mean(y1) - mean(y0)
        out[f"eps_{eps}"] = {
            "protocol_estimate": est_proto,
            "obs_adoption_contrast": est_obs,
            "proxy_accuracy": mean(int(d_obs[i] == d_true[i])
                                   for i in range(n_mem)),
        }
    return out


# ---------------------------------------------------------------------------
# P0-2: lifecycle IV (persistent action, discounted return, exposure
# feedback, unobserved confound, valid instrument)
# ---------------------------------------------------------------------------

def lemma_c2_lifecycle_iv(n: int = 40000, h: int = 30, gamma: float = 0.95,
                          tau: float = 1.0, p_expose: float = 0.6,
                          gamma_conf: float = 0.8, alpha: float = 0.7,
                          delta: float = 0.5, noise: float = 0.1,
                          seed: int = 11) -> Dict[str, Any]:
    """Z (external quota) -> A (persistent keep), U unobserved confound.
    Y_t = tau*A*E_t + gamma_conf*U + eps_t, E_t only when kept (the
    persistent-access feedback: archived memories are never exposed).
    G = sum gamma^{t-1} Y_t; S = sum gamma^{t-1}.  Wald-IV on G:
    (E[G|Z=1]-E[G|Z=0])/(E[A|Z=1]-E[A|Z=0]) = tau*p_expose*S under
    exclusion + relevance, i.e. tau_iv = Wald/S ~ tau.  The observational
    contrast E[G|A=1]-E[G|A=0] is biased by gamma_conf.  Caveat: additive
    effect homogeneity (no A x U interaction); otherwise the Wald
    estimand is a LATE on Z-induced keepers, not the lifecycle ATE."""
    rng = random.Random(seed)
    g_by_z: Dict[int, List[float]] = {0: [], 1: []}
    a_by_z: Dict[int, List[float]] = {0: [], 1: []}
    g_by_a: Dict[int, List[float]] = {0: [], 1: []}
    s = sum(gamma ** t for t in range(h))
    for _ in range(n):
        z = 1 if rng.random() < 0.5 else 0
        u = rng.gauss(0.0, 1.0)
        nu = rng.gauss(0.0, 0.5)
        a = 1 if (alpha * z + delta * u + nu) > 0.0 else 0
        g = 0.0
        for t in range(h):
            e = (rng.random() < p_expose) if a else 0
            y = tau * a * e + gamma_conf * u + rng.gauss(0.0, noise)
            g += gamma ** t * y
        g_by_z[z].append(g)
        a_by_z[z].append(a)
        g_by_a[a].append(g)
    num = mean(g_by_z[1]) - mean(g_by_z[0])
    den = mean(a_by_z[1]) - mean(a_by_z[0])
    iv_g = num / den if den != 0.0 else float("nan")
    iv_tau = iv_g / (p_expose * s)
    obs = mean(g_by_a[1]) - mean(g_by_a[0])
    return {"n": n, "h": h, "gamma": gamma, "tau_true": tau,
            "p_expose": p_expose, "first_stage": den,
            "iv_tau_estimate": iv_tau, "iv_error": iv_tau - tau,
            "obs_contrast": obs, "obs_bias_vs_tau_p_S": obs - tau * p_expose * s,
            "note": "lifecycle estimand: discounted return over kept-only "
                    "exposure; additive homogeneity assumed (else LATE)"}


# ---------------------------------------------------------------------------
# P1: general decision-identification theorem
# ---------------------------------------------------------------------------

def r_star(L: float, U: float) -> float:
    """Minimax regret of any committing rule on identification set
    [L, U].  0 if the set does not straddle 0 (a safe action exists);
    U(-L)/(U-L) otherwise, attained at commit prob p* = U/(U-L)."""
    if U <= 0.0 or L >= 0.0:
        return 0.0
    return U * (-L) / (U - L)


def general_decision_regret(L: float, U: float, p: float) -> float:
    """Worst-case expected regret of committing with keep-probability p
    when the compatible worlds' values span [L, U]."""
    if U <= 0.0:
        return p * (-U)          # archive is safe; keep errs by -U
    if L >= 0.0:
        return (1.0 - p) * L     # keep is safe; archive errs by L
    return max((1.0 - p) * U, p * (-L))


def theorem5_instances() -> Dict[str, Any]:
    """Instance checks for the general theorem:
    (i) crossing set (-1100, 1650): R* = 660 at p* = 0.6 -- Theorem 4's
        verified pair as a special case;
    (ii) decision-identified-not-point-identified set (500, 1650): two
        compatible worlds with DIFFERENT values but the SAME optimal
        action -- committing keep has worst-case regret 0 although the
        value is not point-identified."""
    L, U = -1100.0, 1650.0
    ps = [i / 100 for i in range(101)]
    worst = [general_decision_regret(L, U, p) for p in ps]
    argmin = min(range(len(ps)), key=lambda i: worst[i])
    safe_keep = general_decision_regret(500.0, 1650.0, 1.0)
    safe_keep_worst = max(general_decision_regret(500.0, 1650.0, p)
                          for p in ps)
    return {
        "crossing": {
            "L": L, "U": U, "r_star_formula": r_star(L, U),
            "grid_min": worst[argmin], "argmin_p": ps[argmin],
            "theorem4_instance_reproduced": abs(r_star(L, U) - 660.0) < 1e-9,
        },
        "decision_identified_not_point_identified": {
            "L": 500.0, "U": 1650.0,
            "commit_keep_worst_regret": safe_keep,
            "worst_over_all_committing": safe_keep_worst,
            "safe_commit_exists": safe_keep == 0.0,
        },
    }


# ---------------------------------------------------------------------------
# P2: commit / defer / probe governance boundary
# ---------------------------------------------------------------------------

def governance_choice(L: float, U: float, c_defer: float, c_probe: float,
                      shrink: float = 0.5) -> Dict[str, float]:
    """Optimal governance action given the identification set [L, U],
    deferral cost C_defer, probe cost C_probe, and post-probe width
    shrink factor (probe shrinks the set toward the truth; the shrunken
    set [L*shrink, U*shrink] is the honest simplification used here).
    Returns {action, expected_worst_regret}."""
    if U <= 0.0:
        return {"action": "archive", "expected_worst_regret": 0.0}
    if L >= 0.0:
        return {"action": "keep", "expected_worst_regret": 0.0}
    r_commit = r_star(L, U)
    r_defer = c_defer
    L2, U2 = L * shrink, U * shrink
    r_probe = c_probe + r_star(L2, U2)
    options = [("commit", r_commit), ("defer", r_defer), ("probe", r_probe)]
    action, regret = min(options, key=lambda kv: kv[1])
    return {"action": action, "expected_worst_regret": regret,
            "commit_regret": r_commit, "defer_regret": r_defer,
            "probe_regret": r_probe}


def probe_price_boundary(L: float = -1100.0, U: float = 1650.0,
                         c_defer: float = 500.0, shrink: float = 0.5,
                         steps: int = 40) -> List[Dict[str, Any]]:
    """Sweep C_probe: find the price region where probing beats
    committing (the identification-theory counterpart of Gate 4's
    break-even lambda_probe*)."""
    rows = []
    r_commit = r_star(L, U)
    c_probe_max = r_commit + 100.0
    for i in range(steps + 1):
        c_probe = c_probe_max * i / steps
        choice = governance_choice(L, U, c_defer, c_probe, shrink)
        rows.append({"c_probe": c_probe, "action": choice["action"],
                     "regret": choice["expected_worst_regret"]})
    return rows


# ---------------------------------------------------------------------------
# P3: self-confirming unidentifiability (dynamic necessity, direction A)
# ---------------------------------------------------------------------------

def self_confirming_regret(tau: float = 10.0, p_value: float = 0.6,
                           t_steps: int = 2000, noise: float = 1.0,
                           probe_prob: float = 0.0, threshold: float = 2.0,
                           n_seeds: int = 20, seed0: int = 11,
                           ) -> Dict[str, float]:
    """A rare-critical memory with true per-step exposure value tau is
    wrongly archived (confounded negative prior).  With probe_prob = 0 it
    is never exposed again -> no evidence -> stays archived forever ->
    linear regret.  With probing q > 0, archived candidates re-enter the
    evidence stream and restoration happens once the running mean
    crosses the threshold -> regret plateaus."""
    regrets: List[float] = []
    for si in range(n_seeds):
        rng = random.Random(seed0 + si)
        archived = True
        ev_sum = ev_n = 0.0
        regret = 0.0
        for _ in range(t_steps):
            if archived:
                regret += tau * p_value                      # missed value
                if rng.random() < probe_prob:                # budgeted probe
                    ev_sum += tau + rng.gauss(0.0, noise)
                    ev_n += 1
                    if ev_n > 0 and ev_sum / ev_n > threshold:
                        archived = False                     # restore
        regrets.append(regret)
    return {"tau": tau, "p_value": p_value, "t_steps": t_steps,
            "probe_prob": probe_prob, "threshold": threshold,
            "n_seeds": n_seeds, "mean_regret_T": mean(regrets),
            "sd_regret_T": pstdev(regrets) if n_seeds > 1 else 0.0,
            "per_step_slope": mean(regrets) / t_steps}


# ---------------------------------------------------------------------------
# P4: probe complexity lower bound vs SQCAD-style stopping rule
# ---------------------------------------------------------------------------

def probe_complexity(mu1: float = 0.3, mu2: float = -0.5, sigma: float = 1.0,
                     delta: float = 0.05, n_seeds: int = 200,
                     seed0: int = 3) -> Dict[str, Any]:
    """Two worlds: probes ~ N(mu1, sigma^2) (keep-optimal) vs
    N(mu2, sigma^2) (archive-optimal), mu2 < 0 < mu1.  Lower bound:
    N >= log(1/delta)/KL, KL = (mu1-mu2)^2/(2 sigma^2).  Upper: the
    SQCAD-style stopping rule -- probe until mean - z*sigma/sqrt(n) > 0
    (CI excludes 0) -- simulated in the keep-optimal world."""
    kl = (mu1 - mu2) ** 2 / (2.0 * sigma ** 2)
    lower = math.log(1.0 / delta) / kl
    z = 1.96
    stops: List[int] = []
    errors = 0
    for si in range(n_seeds):
        rng = random.Random(seed0 + si)
        ev_sum = ev_n = 0.0
        for n in range(1, 10000):
            ev_sum += mu1 + rng.gauss(0.0, sigma)
            ev_n += 1
            if ev_n > 1 and ev_sum / ev_n - z * sigma / math.sqrt(ev_n) > 0.0:
                stops.append(ev_n)
                break
        else:
            stops.append(10000)
            errors += 1
    return {"mu1": mu1, "mu2": mu2, "sigma": sigma, "delta": delta,
            "kl": kl, "lower_bound": lower,
            "empirical_mean_stop": mean(stops),
            "empirical_p90_stop": sorted(stops)[int(0.9 * n_seeds)],
            "ratio_mean_over_lower": mean(stops) / lower,
            "failure_to_commit_rate": errors / n_seeds,
            "note": "O(log(1/delta)/Delta^2) upper matches the KL lower "
                    "bound up to a constant factor in the Gaussian "
                    "instance"}


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=str,
                        default="results/decision_identification_theory.json")
    args = parser.parse_args()
    result = {
        "P0_lemma_a2_c6_isolation": lemma_a2_isolated_proxy(),
        "P0_lemma_c2_lifecycle_iv": lemma_c2_lifecycle_iv(),
        "P1_theorem5_instances": theorem5_instances(),
        "P2_governance_boundary": {
            "L": -1100.0, "U": 1650.0, "c_defer": 500.0, "shrink": 0.5,
            "choices": {
                str(c): governance_choice(-1100.0, 1650.0, 500.0, c, 0.5)
                for c in (0.0, 100.0, 300.0, 700.0, 1200.0)},
            "probe_price_sweep": probe_price_boundary(),
        },
        "P3_self_confirming": {
            "no_probe": self_confirming_regret(probe_prob=0.0),
            "with_probe_q0.05": self_confirming_regret(probe_prob=0.05),
            "with_probe_q0.2": self_confirming_regret(probe_prob=0.2),
        },
        "P4_probe_complexity": probe_complexity(),
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
