"""Finite-horizon safe-recovery bounds for archived-committed governance.

This module implements the formulas in
``17-安全恢复证书定理与匹配下界-20260821.md``.  It deliberately does not
reuse the old one-sided ``restore after one positive probe`` calculation as a
minimax result: the safe class controls false restore in the negative world,
and the resulting information cost depends on ``log(1/delta)``.
"""

from __future__ import annotations

import math
from statistics import NormalDist
import random
from typing import Dict


def _check(mu: float, sigma: float, q: float, rho: float,
           delta: float, horizon: int) -> None:
    if mu <= 0 or sigma <= 0:
        raise ValueError("mu and sigma must be positive")
    if not 0 < q <= 1 or not 0 < rho <= 1:
        raise ValueError("q and rho must lie in (0, 1]")
    if not 0 < delta < 0.5:
        raise ValueError("delta must lie in (0, 0.5)")
    if horizon < 1:
        raise ValueError("horizon must be positive")


def n_delta(mu: float, sigma: float, delta: float) -> int:
    """Exact fixed-sample Gaussian threshold for two-sided sign testing."""
    if mu <= 0 or sigma <= 0 or not 0 < delta < 0.5:
        raise ValueError("invalid Gaussian testing parameters")
    z = NormalDist().inv_cdf(1.0 - delta)
    return int(math.ceil((sigma * z / mu) ** 2))


def anytime_boundary(n: int, sigma: float, alpha: float) -> float:
    """Anytime sub-Gaussian radius used by the Qualification gate.

    With ``b_n = anytime_boundary(n, sigma, alpha)``, a union bound over
    ``n >= 1`` gives ``P(for all n: |mean_n - tau| <= b_n) >= 1-alpha``.
    The ``pi^2 n^2 / (3 alpha)`` factor is chosen so the tail series sums
    exactly to ``alpha``.
    """
    if n < 1 or sigma <= 0 or not 0 < alpha < 1:
        raise ValueError("invalid anytime-boundary parameters")
    return sigma * math.sqrt(
        2.0 * math.log(math.pi ** 2 * n * n / (3.0 * alpha)) / n)


def anytime_margin_threshold(margin: float, sigma: float,
                             alpha: float, max_n: int = 10_000_000) -> int:
    """First successful-sample count at which the anytime radius is < margin/2."""
    if margin <= 0 or sigma <= 0 or not 0 < alpha < 1:
        raise ValueError("invalid anytime-threshold parameters")
    for n in range(1, max_n + 1):
        if anytime_boundary(n, sigma, alpha) < margin / 2.0:
            return n
    raise ValueError("max_n too small for requested margin/alpha")


def stitched_boundary(n: int, sigma: float, alpha: float,
                     eta: float = 2.0) -> float:
    """Geometric-epoch stitched sub-Gaussian confidence radius.

    Epoch ``k`` contains the integer indices
    ``ceil(eta**k) <= n <= ceil(eta**(k+1))-1`` and receives error budget
    ``6 alpha / (pi^2 (k+1)^2)``.  The integer ratio ``M_k/m_k`` is used in
    the radius (rather than an unrounded ``eta``), so the epoch maximal
    inequality is valid without a hidden rounding assumption.
    """
    if n < 1 or sigma <= 0 or not 0 < alpha < 1 or eta <= 1:
        raise ValueError("invalid stitched-boundary parameters")
    log_eta = math.log(eta)
    k = max(0, int(math.floor(math.log(n) / log_eta)))
    # Correct floating-point boundary cases (e.g. n exactly eta**k).
    while math.ceil(eta ** (k + 1)) <= n:
        k += 1
    while k > 0 and math.ceil(eta ** k) > n:
        k -= 1
    m_k = math.ceil(eta ** k)
    # For eta very close to one, some geometric epochs contain no integer
    # index.  Clamp the endpoint so the radius remains defined; the boundary
    # lookup above always selects an epoch containing n.
    M_k = max(m_k, math.ceil(eta ** (k + 1)) - 1)
    alpha_k = 6.0 * alpha / (math.pi ** 2 * (k + 1) ** 2)
    return sigma * math.sqrt(2.0 * (M_k / m_k)
                               * math.log(2.0 / alpha_k) / n)


def stitched_margin_threshold(margin: float, sigma: float,
                              alpha: float, eta: float = 2.0,
                              max_n: int = 10_000_000) -> int:
    """First n at which the stitched radius is < margin/2."""
    if margin <= 0 or sigma <= 0 or not 0 < alpha < 1 or eta <= 1:
        raise ValueError("invalid stitched-threshold parameters")
    for n in range(1, max_n + 1):
        if stitched_boundary(n, sigma, alpha, eta) < margin / 2.0:
            return n
    raise ValueError("max_n too small for requested margin/alpha")


def safe_anytime_upper_bound(*, margin: float, sigma: float, q: float,
                             rho: float, alpha: float, horizon: int,
                             nu: float, probe_cost: float,
                             restore_cost: float) -> Dict[str, float]:
    """Theorem 13 upper bound for the anytime interval-authorization gate.

    The gate keeps when ``mean_n - b_n > 0``, archives when
    ``mean_n + b_n < 0``, and otherwise continues probing.  The theorem is
    guaranteed only for worlds with ``|tau| >= margin``; the unidentified
    margin band is deliberately left unresolved.  The displayed waiting term
    uses ``q`` as a verified conditional attempt rate (or verified lower rate),
    not merely as an upper bound on a slower schedule.
    """
    _check(margin, sigma, q, rho, alpha, horizon)
    if nu < 0 or probe_cost < 0 or restore_cost < 0:
        raise ValueError("costs must be non-negative")
    n = anytime_margin_threshold(margin, sigma, alpha)
    wait = nu * n / (q * rho)
    probes = probe_cost * n / rho
    # On the confidence-complement event the gate may continue probing until
    # the horizon.  Since the bad event is correlated with the observed
    # transcript, its probe count cannot be multiplied by q; the only
    # pathwise bound is M_H <= horizon (at most one attempt per epoch).
    tail_life = nu * horizon * alpha
    tail_probe = probe_cost * horizon * alpha
    return {
        "margin": float(margin),
        "alpha": float(alpha),
        "n_margin": float(n),
        "boundary_at_n": anytime_boundary(n, sigma, alpha),
        "lifecycle_wait": wait,
        "probe_cost": probes,
        "restore_cost": float(restore_cost),
        "tail_error_cost": tail_life + tail_probe,
        "tail_lifecycle_error_cost": tail_life,
        "tail_probe_error_cost": tail_probe,
        "worst_case_upper": wait + probes + restore_cost + tail_life + tail_probe,
    }


def safe_stitched_upper_bound(*, margin: float, sigma: float, q: float,
                              rho: float, alpha: float, horizon: int,
                              nu: float, probe_cost: float,
                              restore_cost: float,
                              eta: float = 2.0) -> Dict[str, float]:
    """Theorem 13 stitched version with only log-log confidence overhead.

    The ``q`` cost term has the same verified-rate interpretation as in
    :func:`safe_anytime_upper_bound`; safety alone permits a slower predictable
    probing schedule.
    """
    _check(margin, sigma, q, rho, alpha, horizon)
    if eta <= 1 or nu < 0 or probe_cost < 0 or restore_cost < 0:
        raise ValueError("invalid stitched-bound parameters")
    n = stitched_margin_threshold(margin, sigma, alpha, eta)
    wait = nu * n / (q * rho)
    probes = probe_cost * n / rho
    tail_life = nu * horizon * alpha
    tail_probe = probe_cost * horizon * alpha
    return {
        "margin": float(margin), "alpha": float(alpha), "eta": eta,
        "n_margin": float(n),
        "boundary_at_n": stitched_boundary(n, sigma, alpha, eta),
        "lifecycle_wait": wait, "probe_cost": probes,
        "restore_cost": float(restore_cost),
        "tail_error_cost": tail_life + tail_probe,
        "tail_lifecycle_error_cost": tail_life,
        "tail_probe_error_cost": tail_probe,
        "worst_case_upper": wait + probes + restore_cost + tail_life + tail_probe,
    }


def gaussian_sign_kl(mu: float, sigma: float) -> float:
    """KL(N(+mu,sigma^2) || N(-mu,sigma^2))."""
    if mu <= 0 or sigma <= 0:
        raise ValueError("mu and sigma must be positive")
    return 2.0 * mu * mu / (sigma * sigma)


def margin_band_sample_lower_bound(epsilon: float, sigma: float,
                                   delta: float) -> float:
    """Lemma 14: samples required to authorize both signs near zero."""
    if epsilon <= 0 or sigma <= 0 or not 0 < delta < 0.5:
        raise ValueError("invalid margin-band parameters")
    return bernoulli_kl(1.0 - delta, delta) / gaussian_sign_kl(
        epsilon, sigma)


def bernoulli_kl(a: float, b: float) -> float:
    """Stable Bernoulli KL, including the boundary values used by the bound."""
    if not 0 <= a <= 1 or not 0 <= b <= 1:
        raise ValueError("Bernoulli probabilities must lie in [0, 1]")
    total = 0.0
    if a > 0:
        if b == 0:
            return math.inf
        total += a * math.log(a / b)
    if a < 1:
        if b == 1:
            return math.inf
        total += (1.0 - a) * math.log((1.0 - a) / (1.0 - b))
    return total


def safe_recovery_upper_bound(*, mu: float, sigma: float, q: float,
                              rho: float, delta: float, horizon: int,
                              nu: float, probe_cost: float,
                              restore_cost: float) -> Dict[str, float]:
    """Theorem 11: finite-horizon upper bound for the fixed-sample certificate.

    The ``nu * horizon * delta`` term covers both a wrong archive in W+ and a
    false restore in W-.  It is intentionally retained rather than hidden in
    an asymptotic ``O`` term.
    """
    _check(mu, sigma, q, rho, delta, horizon)
    if nu < 0 or probe_cost < 0 or restore_cost < 0:
        raise ValueError("costs must be non-negative")
    n = n_delta(mu, sigma, delta)
    wait = nu * n / (q * rho)
    probes = probe_cost * n / rho
    tail = nu * horizon * delta
    return {
        "n_delta": float(n),
        "lifecycle_wait": wait,
        "probe_cost": probes,
        "restore_cost": float(restore_cost),
        "tail_error_cost": tail,
        "worst_case_upper": wait + probes + restore_cost + tail,
    }


def safe_recovery_lower_bound(*, mu: float, sigma: float, q: float,
                              rho: float, delta: float, horizon: int,
                              nu: float, probe_cost: float = 0.0,
                              restore_cost: float = 0.0) -> Dict[str, float]:
    """Theorem 12: KL and total-cost lower bound for safe policies.

    The returned high-recovery branch includes probe cost via Wald's identity
    and restore cost via ``P_+(keep) >= 1-delta``.  The complementary branch
    has lifecycle regret at least ``nu * delta * horizon`` when the positive
    world is not recovered with probability ``1-delta``.  The high-recovery
    numbers are conditional: if the required expected evidence exceeds the
    finite horizon, that branch is infeasible and the low-recovery branch is
    the applicable alternative.
    """
    _check(mu, sigma, q, rho, delta, horizon)
    if nu < 0 or probe_cost < 0 or restore_cost < 0:
        raise ValueError("costs must be non-negative")
    k = gaussian_sign_kl(mu, sigma)
    event_kl = bernoulli_kl(1.0 - delta, delta)
    n_lb = event_kl / k
    tau_lb = n_lb / (q * rho)
    probe_attempts = n_lb / rho
    return {
        "event_kl": event_kl,
        "sample_kl": k,
        "successful_probe_lower": n_lb,
        "keep_time_lower": tau_lb,
        "lifecycle_regret_lower": nu * tau_lb,
        "probe_attempt_lower": probe_attempts,
        "probe_cost_lower": probe_cost * probe_attempts,
        "restore_cost_lower": restore_cost * (1.0 - delta),
        "high_recovery_total_cost_lower": (
            nu * tau_lb + probe_cost * probe_attempts
            + restore_cost * (1.0 - delta)),
        "low_recovery_branch_regret": nu * delta * horizon,
    }


def safe_recovery_summary(*, mu: float, sigma: float, q: float,
                          rho: float, delta: float, horizon: int,
                          nu: float, probe_cost: float,
                          restore_cost: float) -> Dict[str, Dict[str, float]]:
    """Return both sides of the theorem pair for audit tables."""
    return {
        "upper": safe_recovery_upper_bound(
            mu=mu, sigma=sigma, q=q, rho=rho, delta=delta,
            horizon=horizon, nu=nu, probe_cost=probe_cost,
            restore_cost=restore_cost),
        "lower": safe_recovery_lower_bound(
            mu=mu, sigma=sigma, q=q, rho=rho, delta=delta,
            horizon=horizon, nu=nu, probe_cost=probe_cost,
            restore_cost=restore_cost),
    }


def simulate_fixed_certificate(*, world: str, mu: float, sigma: float,
                                q: float, rho: float, delta: float,
                                horizon: int, trials: int,
                                seed: int = 0) -> Dict[str, float]:
    """Small audit simulator for Theorem 11's fixed-sample policy.

    It reports the two quantities that the old one-sided experiment omitted:
    false restore in ``W-`` and failure-to-recover in ``W+``.  This is a
    diagnostic Monte Carlo, not part of the proof.
    """
    _check(mu, sigma, q, rho, delta, horizon)
    if world not in {"+", "-"} or trials < 1:
        raise ValueError("world must be '+' or '-' and trials positive")
    n = n_delta(mu, sigma, delta)
    rng = random.Random(seed)
    keeps = 0
    total_keep_time = 0.0
    total_attempts = 0.0
    for _ in range(trials):
        successes = 0
        total = 0.0
        keep_time = horizon
        for t in range(1, horizon + 1):
            if rng.random() <= q:
                total_attempts += 1.0
            else:
                continue
            if rng.random() <= rho:
                successes += 1
                total += (mu if world == "+" else -mu) + rng.gauss(0.0, sigma)
                if successes >= n:
                    keep_time = t
                    if total / successes > 0:
                        keeps += 1
                    break
        total_keep_time += keep_time
    return {
        "n_delta": float(n),
        "keep_rate": keeps / trials,
        "false_restore_rate": (keeps / trials if world == "-" else 0.0),
        "failure_to_recover_rate": (1.0 - keeps / trials if world == "+" else 0.0),
        "mean_keep_time_or_horizon": total_keep_time / trials,
        "mean_probe_attempts": total_attempts / trials,
    }


def simulate_stitched_gate(*, world: str, mu: float, sigma: float,
                           q: float, rho: float, alpha: float,
                           horizon: int, trials: int,
                           seed: int = 0, eta: float = 2.0) -> Dict[str, float]:
    """Diagnostic Monte Carlo for the anytime stitched Qualification gate."""
    _check(mu, sigma, q, rho, alpha, horizon)
    if world not in {"+", "-"} or trials < 1 or eta <= 1:
        raise ValueError("invalid stitched simulation parameters")
    rng = random.Random(seed)
    wrong = 0
    decisions = 0
    for _ in range(trials):
        n = 0
        total = 0.0
        decision = None
        for _t in range(horizon):
            if rng.random() > q or rng.random() > rho:
                continue
            n += 1
            total += (mu if world == "+" else -mu) + rng.gauss(0.0, sigma)
            b = stitched_boundary(n, sigma, alpha, eta)
            mean = total / n
            if mean - b > 0:
                decision = "+"
                break
            if mean + b < 0:
                decision = "-"
                break
        if decision is not None:
            decisions += 1
            if decision != world:
                wrong += 1
    return {
        "decision_rate": decisions / trials,
        "wrong_authorization_rate": wrong / trials,
        "wrong_given_decision_rate": wrong / decisions if decisions else 0.0,
    }
