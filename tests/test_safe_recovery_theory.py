import math

import pytest

from sqcad.safe_recovery_theory import (
    bernoulli_kl,
    gaussian_sign_kl,
    n_delta,
    safe_recovery_lower_bound,
    safe_recovery_upper_bound,
    simulate_fixed_certificate,
    anytime_boundary,
    anytime_margin_threshold,
    safe_anytime_upper_bound,
    stitched_boundary,
    stitched_margin_threshold,
    safe_stitched_upper_bound,
    simulate_stitched_gate,
    margin_band_sample_lower_bound,
)


def test_gaussian_threshold_and_kl_are_exact_for_declared_model():
    assert n_delta(mu=1.0, sigma=1.0, delta=0.05) == 3
    assert gaussian_sign_kl(1.0, 1.0) == pytest.approx(2.0)


def test_bernoulli_kl_boundary_and_symmetry_inputs():
    assert bernoulli_kl(0.5, 0.5) == pytest.approx(0.0)
    assert bernoulli_kl(0.95, 0.05) > 0
    assert math.isinf(bernoulli_kl(1.0, 0.0))


def test_safe_upper_contains_both_worlds_tail_error():
    out = safe_recovery_upper_bound(
        mu=1.0, sigma=1.0, q=0.5, rho=0.8, delta=0.05,
        horizon=100, nu=2.0, probe_cost=3.0, restore_cost=4.0)
    assert out["n_delta"] == 3
    assert out["tail_error_cost"] == pytest.approx(10.0)
    assert out["worst_case_upper"] == pytest.approx(
        out["lifecycle_wait"] + out["probe_cost"]
        + out["restore_cost"] + out["tail_error_cost"])


def test_safe_lower_has_censoring_factor_and_low_recovery_branch():
    out = safe_recovery_lower_bound(
        mu=1.0, sigma=1.0, q=0.5, rho=0.8, delta=0.05,
        horizon=100, nu=2.0, probe_cost=3.0, restore_cost=4.0)
    assert out["successful_probe_lower"] > 0
    assert out["keep_time_lower"] == pytest.approx(
        out["successful_probe_lower"] / (0.5 * 0.8))
    assert out["low_recovery_branch_regret"] == pytest.approx(10.0)
    assert out["probe_cost_lower"] > 0
    assert out["restore_cost_lower"] == pytest.approx(3.8)
    assert out["high_recovery_total_cost_lower"] == pytest.approx(
        out["lifecycle_regret_lower"] + out["probe_cost_lower"]
        + out["restore_cost_lower"])


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        n_delta(0.0, 1.0, 0.05)
    with pytest.raises(ValueError):
        safe_recovery_upper_bound(
            mu=1.0, sigma=1.0, q=0.0, rho=1.0, delta=0.05,
            horizon=10, nu=1.0, probe_cost=1.0, restore_cost=1.0)


def test_anytime_boundary_and_margin_gate():
    alpha = 0.05
    n = anytime_margin_threshold(margin=1.0, sigma=1.0, alpha=alpha)
    assert n > 1
    assert anytime_boundary(n, 1.0, alpha) < 0.5
    out = safe_anytime_upper_bound(
        margin=1.0, sigma=1.0, q=0.5, rho=0.8, alpha=alpha,
        horizon=100, nu=2.0, probe_cost=3.0, restore_cost=4.0)
    assert out["n_margin"] == pytest.approx(float(n))
    assert out["tail_lifecycle_error_cost"] == pytest.approx(10.0)
    assert out["tail_probe_error_cost"] == pytest.approx(15.0)
    assert out["tail_error_cost"] == pytest.approx(25.0)


def test_stitched_boundary_has_loglog_gate_and_valid_formula():
    n = stitched_margin_threshold(margin=1.0, sigma=1.0, alpha=0.05)
    assert n > 1
    assert stitched_boundary(n, 1.0, 0.05) < 0.5
    out = safe_stitched_upper_bound(
        margin=1.0, sigma=1.0, q=0.5, rho=0.8, alpha=0.05,
        horizon=100, nu=2.0, probe_cost=3.0, restore_cost=4.0)
    assert out["n_margin"] == pytest.approx(float(n))


def test_stitched_integer_epochs_cover_noninteger_eta_without_rounding_gap():
    eta = 1.17
    for n in (1, 2, 3, 7, 11, 19, 37, 101):
        radius = stitched_boundary(n, sigma=1.0, alpha=0.05, eta=eta)
        assert math.isfinite(radius) and radius > 0.0
    threshold = stitched_margin_threshold(
        margin=1.0, sigma=1.0, alpha=0.05, eta=eta, max_n=2_000_000)
    assert stitched_boundary(threshold, 1.0, 0.05, eta) < 0.5


def test_stitched_gate_controls_wrong_authorization_in_both_worlds():
    pos = simulate_stitched_gate(
        world="+", mu=1.0, sigma=1.0, q=1.0, rho=1.0,
        alpha=0.05, horizon=300, trials=3000, seed=8)
    neg = simulate_stitched_gate(
        world="-", mu=1.0, sigma=1.0, q=1.0, rho=1.0,
        alpha=0.05, horizon=300, trials=3000, seed=9)
    assert pos["wrong_authorization_rate"] < 0.05
    assert neg["wrong_authorization_rate"] < 0.05


def test_margin_band_lower_bound_diverges_quadratically():
    a = margin_band_sample_lower_bound(1.0, 1.0, 0.05)
    b = margin_band_sample_lower_bound(0.5, 1.0, 0.05)
    assert b == pytest.approx(4.0 * a)


def test_fixed_certificate_audit_exposes_both_error_directions():
    positive = simulate_fixed_certificate(
        world="+", mu=2.0, sigma=1.0, q=1.0, rho=1.0,
        delta=0.05, horizon=100, trials=5000, seed=4)
    negative = simulate_fixed_certificate(
        world="-", mu=2.0, sigma=1.0, q=1.0, rho=1.0,
        delta=0.05, horizon=100, trials=5000, seed=5)
    assert positive["failure_to_recover_rate"] < 0.05
    assert negative["false_restore_rate"] < 0.05
    assert positive["mean_probe_attempts"] == pytest.approx(
        positive["n_delta"], abs=0.15)
