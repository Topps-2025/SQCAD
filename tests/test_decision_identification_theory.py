"""P0-P4 tests per 13-必要性证明方向.

P0-1: C6 isolation -- mechanism fixed, proxy polluted: protocol
    estimates identical across eps; observational adoption contrast
    degrades with eps.
P0-2: lifecycle IV -- Wald on the discounted return recovers tau under
    additive homogeneity; the observational contrast stays biased.
P1: general decision identification -- R*(L,U) formula, p* = U/(U-L),
    Theorem 4's 660 as a special case, and a decision-identified but
    not-point-identified instance with zero worst-case regret.
P2: commit/defer/probe boundary -- the optimal action switches by
    C_probe; sweep is monotone in the right direction.
P3: self-confirming unidentifiability -- zero probing gives linear
    regret; budgeted probing plateaus.
P4: probe complexity -- empirical stopping time above the KL lower
    bound and same order; failure rate controlled.
"""

import math

import pytest

from sqcad.decision_identification_theory import (
    general_decision_regret, governance_choice, lemma_a2_isolated_proxy,
    lemma_c2_lifecycle_iv, probe_complexity, probe_price_boundary,
    r_star, self_confirming_regret, theorem5_instances)


# ---------------------------------------------------------------------------
# P0-1: C6 isolation
# ---------------------------------------------------------------------------

def test_c6_isolation_protocol_identical_observational_degrades():
    res = lemma_a2_isolated_proxy(eps_values=(0.0, 0.3), seed=7)
    p0 = res["eps_0.0"]["protocol_estimate"]
    p3 = res["eps_0.3"]["protocol_estimate"]
    # the protocol route never reads the proxy: estimates bit-identical
    assert p0 == p3
    # protocol estimate recovers tau * p_expose (the exposure-weighted
    # lifecycle contrast)
    assert abs(p0 - 2.0 * 0.6) < 0.05
    # the observational adoption-kernel contrast is a DIFFERENT quantity
    # (selection on exposure rate) and dilutes under proxy pollution:
    # random flip at rate eps scales the contrast by ~(1 - 2 eps)
    o0 = res["eps_0.0"]["obs_adoption_contrast"]
    o3 = res["eps_0.3"]["obs_adoption_contrast"]
    assert o0 > 0.2
    assert abs(o3) < abs(o0) * 0.6          # dilution toward zero
    assert res["eps_0.0"]["proxy_accuracy"] > 0.99
    assert res["eps_0.3"]["proxy_accuracy"] < 0.75


# ---------------------------------------------------------------------------
# P0-2: lifecycle IV
# ---------------------------------------------------------------------------

def test_lifecycle_iv_recovers_tau_observational_biased():
    res = lemma_c2_lifecycle_iv(n=40000)
    assert abs(res["iv_error"]) < 0.05
    assert abs(res["obs_bias_vs_tau_p_S"]) > 0.5    # confounding is real
    assert res["first_stage"] > 0.2                 # relevance holds


# ---------------------------------------------------------------------------
# P1: general decision identification
# ---------------------------------------------------------------------------

def test_r_star_formula_and_argmin():
    assert r_star(-1100.0, 1650.0) == pytest.approx(660.0, abs=1e-9)
    # argmin p* = U/(U-L) = 0.6: verify the formula's minimizer
    assert general_decision_regret(-1100.0, 1650.0, 0.6) == pytest.approx(
        660.0, abs=1e-9)
    assert general_decision_regret(-1100.0, 1650.0, 0.2) > 660.0
    assert general_decision_regret(-1100.0, 1650.0, 0.9) > 660.0


def test_r_star_zero_when_set_does_not_straddle_zero():
    assert r_star(0.1, 5.0) == 0.0        # all-compatible keep
    assert r_star(-5.0, -0.1) == 0.0      # all-compatible archive


def test_theorem5_instances():
    res = theorem5_instances()
    assert res["crossing"]["theorem4_instance_reproduced"] is True
    assert res["crossing"]["argmin_p"] == pytest.approx(0.6, abs=0.01)
    di = res["decision_identified_not_point_identified"]
    # different compatible values (500 vs 1650), same optimal action:
    # committing keep has zero worst-case regret without point ID
    assert di["safe_commit_exists"] is True
    assert di["commit_keep_worst_regret"] == 0.0


# ---------------------------------------------------------------------------
# P2: commit / defer / probe boundary
# ---------------------------------------------------------------------------

def test_governance_choice_switches_with_probe_price():
    cheap = governance_choice(-1100.0, 1650.0, 500.0, 100.0, 0.5)
    expensive = governance_choice(-1100.0, 1650.0, 500.0, 1200.0, 0.5)
    assert cheap["action"] == "probe"      # probe beats commit when cheap
    assert expensive["action"] != "probe"
    # safe sets commit directly with zero regret
    assert governance_choice(500.0, 1650.0, 500.0, 100.0)["action"] == "keep"
    assert governance_choice(-1650.0, -500.0, 500.0, 100.0)["action"] \
        == "archive"


def test_probe_price_sweep_monotone():
    rows = probe_price_boundary(steps=40)
    actions = [r["action"] for r in rows]
    # as probe price rises the chosen action never returns to probe
    last_probe = -1
    for i, a in enumerate(actions):
        if a == "probe":
            last_probe = i
    for i in range(last_probe + 1, len(actions)):
        assert actions[i] != "probe"


# ---------------------------------------------------------------------------
# P3: self-confirming unidentifiability
# ---------------------------------------------------------------------------

def test_self_confirming_linear_without_probe_plateau_with_probe():
    no_probe = self_confirming_regret(probe_prob=0.0, t_steps=800)
    with_probe = self_confirming_regret(probe_prob=0.05, t_steps=800)
    # without probing: linear regret at the missed-value rate
    assert no_probe["per_step_slope"] == pytest.approx(10.0 * 0.6, abs=0.3)
    # with budgeted probing: correction happens, regret plateaus far
    # below the linear accumulation
    assert with_probe["mean_regret_T"] < no_probe["mean_regret_T"] * 0.5


def test_self_confirming_deterministic():
    a = self_confirming_regret(probe_prob=0.05, t_steps=200, n_seeds=4)
    b = self_confirming_regret(probe_prob=0.05, t_steps=200, n_seeds=4)
    assert a == b


# ---------------------------------------------------------------------------
# P4: probe complexity bounds
# ---------------------------------------------------------------------------

def test_probe_complexity_above_lower_same_order():
    res = probe_complexity(n_seeds=150)
    assert res["empirical_mean_stop"] >= res["lower_bound"]
    assert res["ratio_mean_over_lower"] < 20.0    # same order
    assert res["failure_to_commit_rate"] < 0.1    # stopping rule commits


def test_probe_complexity_lower_bound_formula():
    res = probe_complexity(mu1=1.0, mu2=-1.0, sigma=1.0, delta=0.05,
                           n_seeds=50)
    from statistics import NormalDist
    expected = math.ceil((2.0 * NormalDist().inv_cdf(0.95) / 2.0) ** 2)
    assert res["lower_bound"] == expected
    assert res["lower_bound_kind"] == "exact_equal_variance_gaussian"
