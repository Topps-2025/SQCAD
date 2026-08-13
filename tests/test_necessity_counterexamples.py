"""Gate-necessity tests: Lemma A/C/D counterexamples + Theorem 4 regret.

Each lemma demonstrates that a C1-C8 member is sufficient-not-necessary:
the condition can fail while the lifecycle contrast is still identified
via an alternative route.  Theorem 4 shows what IS necessary: on the
unidentified class (Theorem 1's sign-flip pair), every committing rule
suffers the regret/error lower bounds; the gate attains zero.
"""

import pytest

from sqcad.necessity_counterexamples import (
    lemma_a, lemma_c, lemma_d, theorem4_regret)


def test_lemma_a_c6_not_necessary_for_protocol_route():
    """adoption mis-measurement severity (0.01 vs 0.99) does not bias the
    protocol-route estimator: the rollout never reads the proxy D."""
    res = lemma_a(seed=3, n_trajectories=300, n_oracle=300, n_epochs=80)
    for ae in ("0.01", "0.99"):
        row = res[f"adoption_error_{ae}"]
        # within ~3 se of a 300-trajectory estimate (se ~= 1.4)
        assert abs(row["bias"]) < 4.0


def test_lemma_c_iv_identifies_without_randomization():
    """Wald IV recovers tau in a confounded world with no randomization;
    the observational contrast is biased."""
    res = lemma_c(n=40000)
    assert abs(res["iv_error"]) < 0.02
    assert abs(res["obs_bias"]) > 0.1          # confounding is real
    assert res["first_stage"] > 0.2            # relevance holds


def test_lemma_d_c8_drift_biases_intended_only():
    """Under measurement drift the rollout estimator is unbiased for the
    CURRENT value and biased for the pre-registered intended value."""
    res = lemma_d(seed=3, n_trajectories=300, n_oracle=300, n_epochs=80)
    assert abs(res["bias_vs_current"]) < 4.0
    assert res["bias_vs_intended"] > 2.0       # drift contribution positive


def test_theorem4_regret_bound_and_error_probability():
    res = theorem4_regret()
    assert res["theoretical_bound"] == pytest.approx(
        1650.0 * 1100.0 / 2750.0)              # = 660
    assert res["grid_min_worst_regret"] == pytest.approx(
        res["theoretical_bound"], abs=1e-9)
    assert res["argmin_p"] == pytest.approx(0.6, abs=0.01)
    assert res["error_probability_lower_bound"] == 0.5
    assert res["gate_false_decisions"] == 0.0


def test_theorem4_regret_bound_scales_with_effects():
    small = theorem4_regret(tau1=10.0, tau2=4.0)
    assert small["theoretical_bound"] == pytest.approx(10.0 * 4.0 / 14.0)
    assert small["argmin_p"] == pytest.approx(10.0 / 14.0, abs=0.01)


def test_lemma_c_deterministic():
    assert lemma_c(n=5000) == lemma_c(n=5000)
