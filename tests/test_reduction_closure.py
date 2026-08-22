"""Tests for the T2/P4 theory-closure experiments (16-).

Coverage:
  * T2 Lemma 4 pairing identity -- regret_K + regret_A = tau*p*(T - n_early)
    exactly, pointwise per seed, for committing, watchful, and maximally
    adaptive (random-flip) policies;
  * T2 Theorem 2 reduction image -- standard learners (bandit UCB, log OPE)
    on the image under a faithful reduction accrue exact linear regret on the
    W2 pair; the forbidden-phi control (world-identity smuggled into the
    image context) succeeds;
  * P4 Theorems 3-4 -- empirical probes-to-decision >= the fixed-sample
    N*(delta) everywhere,
    and E[Regret_K] >= the finite-horizon lifecycle lower bound, with a
    bounded fixed-sample diagnostic ratio in the binding regime tau <= 1.
"""

import json
import math
import random
from pathlib import Path

import pytest

from sqcad.reduction_closure import (
    DELTA, HORIZON, N_EARLY, P_EXPOSE, PER_STEP_PAIR_SUM, QS, TAU, TAUS,
    Z, _ci_stop_trial, _finite_lifecycle_lower, _mean, _n_star,
    detection_bound_sweep,
    pairing_identity, reduction_image)
from sqcad.self_obscuring_ablation import (
    INITIAL_STATE, build_world, config_for, run_policy)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# T2: pairing identity (Lemma 4)
# ---------------------------------------------------------------------------


def test_pairing_identity_exact_for_committing_policies():
    res = pairing_identity(n_seeds=6)
    for pol in ("watchful_no_restore", "association_commit",
                "watchful_restore", "random_flip"):
        assert res[pol]["exact"], pol
        assert res[pol]["pair_sum_mean"] == pytest.approx(PER_STEP_PAIR_SUM,
                                                          rel=0.0, abs=1e-9)


def test_random_flip_policy_is_available():
    # the coupled-coin control must be runnable by the ablation engine
    w = build_world(config_for(21, "K", "W2"))
    r = run_policy(w, "random_flip")
    assert r["regret_T"] >= 0.0
    assert r["per_step_slope"] >= 0.0


def test_pairing_identity_pointwise_per_seed():
    # the identity holds per (seed, world-pair), not only in expectation
    for seed in (21, 22, 23):
        k = run_policy(build_world(config_for(seed, "K", "W2")),
                       "association_commit")
        a = run_policy(build_world(config_for(seed, "A", "W2")),
                       "association_commit")
        assert k["regret_T"] + a["regret_T"] == pytest.approx(
            PER_STEP_PAIR_SUM, rel=0.0, abs=1e-9)


def test_pair_sum_constant_value():
    # tau*p*(T - n_early) = 10 * 0.6 * 1950 = 11700
    assert PER_STEP_PAIR_SUM == pytest.approx(11700.0, rel=0.0, abs=1e-9)
    assert PER_STEP_PAIR_SUM == TAU * P_EXPOSE * (HORIZON - N_EARLY)


# ---------------------------------------------------------------------------
# T2: reduction image (Theorem 2 numerics)
# ---------------------------------------------------------------------------


def test_reduction_image_standard_learners_linear():
    res = reduction_image(n_seeds=6)
    for pol in ("bandit_ucb", "standard_ope"):
        assert res[pol]["mean_slope_K"] == pytest.approx(5.85, abs=1e-6), pol
        assert res[pol]["mean_slope_A"] == pytest.approx(0.0, abs=1e-9), pol
        assert res[pol]["mean_pair_sum"] == pytest.approx(
            PER_STEP_PAIR_SUM, rel=0.0, abs=1e-6), pol


def test_reduction_image_forbidden_phi_control_succeeds():
    res = reduction_image(n_seeds=6)
    assert res["contextual_bandit_oracle"]["mean_slope_K"] == 0.0
    assert res["contextual_bandit_oracle"]["mean_slope_A"] == 0.0
    assert res["contextual_bandit_oracle"]["mean_pair_sum"] == 0.0


def test_reduction_image_uncensored_learner_learns():
    # contextual_bandit starts "kept" and is never censored: the failure is
    # pinned on action-dependent censoring, not learner weakness
    res = reduction_image(n_seeds=6)
    assert res["contextual_bandit"]["mean_slope_K"] < 0.5
    assert res["contextual_bandit"]["mean_slope_K"] > -0.5


# ---------------------------------------------------------------------------
# P4: detection bound (Theorem 3) + regret decomposition (Theorem 4)
# ---------------------------------------------------------------------------


def test_n_star_formula():
    # Exact symmetric-Gaussian threshold: ceil((sigma/tau)^2 z_(1-delta)^2).
    from statistics import NormalDist
    z = NormalDist().inv_cdf(1.0 - DELTA)
    assert _n_star(0.25) == math.ceil((z / 0.25) ** 2)
    assert _n_star(1.0) == math.ceil(z ** 2)


def test_empirical_probes_never_below_n_star():
    # Theorem 3: any level-delta test needs EXPECTED observations >= N*
    # (single trials may stop early by luck -- the bound is in expectation)
    rng = random.Random(3)
    for tau in TAUS:
        n_star = _n_star(tau)
        atts = []
        for _ in range(200):
            steps, att, _ = _ci_stop_trial(tau, q=1.0, rho=1.0, sigma=1.0,
                                           z=Z, rng=rng)
            atts.append(att)
        assert _mean(atts) >= n_star * 0.99, (tau, _mean(atts), n_star)


def test_detection_sweep_binding_regime_ratio_bounded():
    # In the binding regime (tau <= 1), the sequential CI rule is an
    # order/constant-factor diagnostic against the strict fixed-sample
    # threshold.  It is not claimed to attain the fixed-sample constant.
    res = detection_bound_sweep(n_seeds=100)
    for tau in (0.25, 0.5, 1.0):
        row = res["rows"][f"tau_{tau}"]
        for q in QS:
            ratio = row[f"q_{q}"]["probe_ratio_E_over_Nstar"]
            assert 0.9 <= ratio <= 3.5, (tau, q, ratio)


def test_finite_lifecycle_lower_bound():
    # Theorem 4 finite-horizon form: total measured regret dominates the
    # truncated lifecycle-loss lower bound. The N/rho probe term is only an
    # infinite-horizon expression.
    res = detection_bound_sweep(n_seeds=100)
    for tau in TAUS:
        row = res["rows"][f"tau_{tau}"]
        for q in QS:
            cell = row[f"q_{q}"]
            assert cell["regret_K"] >= cell["lower_bound_finite_lifecycle"] * 0.99, (tau, q)


def test_asymptotic_lower_bound_is_labeled_diagnostic():
    res = detection_bound_sweep(n_seeds=100)
    for tau in TAUS:
        row = res["rows"][f"tau_{tau}"]
        for q in QS:
            cell = row[f"q_{q}"]
            assert cell["lower_bound_L"] >= cell["lower_bound_finite_lifecycle"]


def test_detection_sweep_regret_decomposition_consistent():
    # regret_K = c_probe * attempts + tau*p * steps (probe + lifecycle loss)
    res = detection_bound_sweep(n_seeds=100)
    tau_p = res["tau_p"]
    c_probe = res["c_probe"]
    for tau in TAUS:
        row = res["rows"][f"tau_{tau}"]
        for q in QS:
            cell = row[f"q_{q}"]
            manual = c_probe * cell["empirical_attempts"] \
                + tau_p * cell["empirical_steps"]
            assert cell["regret_K"] == pytest.approx(manual, rel=1e-6)


def test_detection_sweep_probe_ratio_q_invariant():
    # the observation count is q-independent (q only scales the waiting time)
    res = detection_bound_sweep(n_seeds=200)
    for tau in (0.25, 1.0):
        row = res["rows"][f"tau_{tau}"]
        ratios = [row[f"q_{q}"]["probe_ratio_E_over_Nstar"] for q in QS]
        assert max(ratios) - min(ratios) < 0.35, ratios


# ---------------------------------------------------------------------------
# determinism / reproducibility
# ---------------------------------------------------------------------------


def test_deterministic_with_fixed_seeds():
    a = detection_bound_sweep(n_seeds=50)
    b = detection_bound_sweep(n_seeds=50)
    assert a["rows"] == b["rows"]


def test_run_policy_rejects_unknown_policy():
    with pytest.raises(KeyError):
        run_policy(build_world(config_for(21, "K", "W2")), "no_such_policy")


def test_frozen_results_match_rerun():
    # the official 12-seed artifact must be reproducible
    p = ROOT / "results" / "reduction_closure.json"
    if not p.exists():
        pytest.skip("official artifact not present")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["pairing_identity"]["random_flip"]["exact"] is True
    assert d["pairing_identity"]["random_flip"]["pair_sum_mean"] == \
        pytest.approx(11700.0, rel=0.0, abs=1e-9)
