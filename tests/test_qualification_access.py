"""Tests for the decision-identification-aware qualification/access module."""

import pytest

from src.sqcad.qualification_access import (
    AccessCandidate, GovernanceAction, PersistentAction, ProbeOption,
    QualificationCertificate, QualificationStatus, ScopeKey,
    SequentialQualificationGate,
    decide_persistent_action, plan_access, probe_value,
    anytime_qualification_certificate,
)
from src.sqcad.safe_recovery_theory import anytime_boundary


SCOPE = ScopeKey("qa", "u0", "tool-v1", "model-v1", "policy-v1")


def _cert(mid, status, lower=None, upper=None):
    return QualificationCertificate(mid, SCOPE, status, lower, upper,
                                    evidence_ids=(f"ev:{mid}",))


def test_non_crossing_certificates_authorize_opposite_actions():
    keep = decide_persistent_action(
        _cert("keep", QualificationStatus.BOUND, 0.2, 1.1), 1.0)
    archive = decide_persistent_action(
        _cert("archive", QualificationStatus.BOUND, -1.1, -0.2), 1.0)
    assert keep.action is GovernanceAction.KEEP
    assert archive.action is GovernanceAction.ARCHIVE
    assert keep.expected_risk == archive.expected_risk == 0.0


def test_anytime_certificate_authorizes_only_after_strict_boundary_crossing():
    unresolved = anytime_qualification_certificate(
        "m0", SCOPE, [0.0], sigma=1.0, alpha=0.05)
    assert unresolved.status is QualificationStatus.UNRESOLVED
    assert unresolved.authorized_action() is None

    positive = anytime_qualification_certificate(
        "m1", SCOPE, [3.0] * 200, sigma=1.0, alpha=0.05)
    negative = anytime_qualification_certificate(
        "m2", SCOPE, [-3.0] * 200, sigma=1.0, alpha=0.05)
    assert positive.authorized_action() is PersistentAction.KEEP
    assert negative.authorized_action() is PersistentAction.ARCHIVE
    assert positive.lower > 0.0 and negative.upper < 0.0


def test_exact_zero_endpoint_is_unresolved_not_authorized():
    """The bridge theorem requires strict endpoint inequalities."""
    radius = anytime_boundary(1, sigma=1.0, alpha=0.05)
    boundary = anytime_qualification_certificate(
        "m-boundary", SCOPE, [radius], sigma=1.0, alpha=0.05)
    assert boundary.status is QualificationStatus.UNRESOLVED
    assert boundary.authorized_action() is None
    assert boundary.lower == 0.0


def test_failed_probe_is_not_a_statistical_observation():
    """Only successful-probe values enter the sequential certificate."""
    no_success = anytime_qualification_certificate(
        "m-failed", SCOPE, [], sigma=1.0, alpha=0.05)
    one_success = anytime_qualification_certificate(
        "m-failed", SCOPE, [3.0], sigma=1.0, alpha=0.05)
    assert no_success.status is QualificationStatus.UNRESOLVED
    assert no_success.diagnostics == ("n=0", "alpha=0.05")
    assert one_success.diagnostics[0] == "n=1"


def test_bridge_interval_is_pathwise_same_radius_as_theorem_13():
    observations = (1.2, -0.4, 2.1, 0.7)
    cert = anytime_qualification_certificate(
        "m-bridge", SCOPE, observations, sigma=1.3, alpha=0.07)
    mean = sum(observations) / len(observations)
    radius = anytime_boundary(len(observations), 1.3, 0.07)
    assert cert.lower == pytest.approx(mean - radius)
    assert cert.upper == pytest.approx(mean + radius)
    assert cert.authorized_action() is None


def test_stateful_gate_enforces_terminal_no_probe_invariant():
    gate = SequentialQualificationGate("m-state", SCOPE, sigma=1.0, alpha=0.05)
    gate.observe(2.8, evidence_id="probe-1")
    cert = gate.observe(2.8, evidence_id="probe-2")
    assert cert.authorized_action() is PersistentAction.KEEP
    assert gate.terminal_action is PersistentAction.KEEP
    assert gate.is_terminal
    assert gate.certificate.evidence_ids == ("probe-1", "probe-2")
    with pytest.raises(RuntimeError):
        gate.observe(3.0, evidence_id="probe-after-terminal")


def test_stateful_gate_horizon_close_keeps_unresolved_non_authorizing():
    gate = SequentialQualificationGate("m-close", SCOPE, sigma=1.0, alpha=0.05)
    cert = gate.close_horizon()
    assert gate.is_terminal
    assert gate.terminal_action is None
    assert cert.authorized_action() is None


def test_nonfinite_probe_values_are_rejected():
    with pytest.raises(ValueError):
        anytime_qualification_certificate(
            "m-nan", SCOPE, [float("nan")], sigma=1.0, alpha=0.05)
    gate = SequentialQualificationGate("m-inf", SCOPE, sigma=1.0, alpha=0.05)
    with pytest.raises(ValueError):
        gate.observe(float("inf"))


def test_crossing_interval_never_commits_and_cheap_probe_wins():
    crossing = _cert("m0", QualificationStatus.BOUND, -1.0, 1.0)
    probe = ProbeOption("m0", cost=0.1, post_lower=0.2, post_upper=0.8)
    decision = decide_persistent_action(crossing, defer_cost=1.0, probe=probe)
    assert decision.action is GovernanceAction.PROBE
    assert decision.action not in (GovernanceAction.KEEP, GovernanceAction.ARCHIVE)
    assert probe_value(1.0, probe) == 0.9


def test_mismatch_defers_even_when_a_probe_is_cheap():
    cert = _cert("m0", QualificationStatus.MISMATCH, None, None)
    probe = ProbeOption("m0", cost=0.0, post_lower=1.0, post_upper=2.0)
    decision = decide_persistent_action(cert, defer_cost=1.0, probe=probe)
    assert decision.action is GovernanceAction.DEFER
    assert decision.reason == "scope_or_version_mismatch"


def test_access_uses_retrieval_only_after_authorization_and_probe_selection():
    archived = AccessCandidate(
        "old-negative", 100.0,
        _cert("old-negative", QualificationStatus.BOUND, -2.0, -1.0), True)
    restore = AccessCandidate(
        "qualified-positive", 0.5,
        _cert("qualified-positive", QualificationStatus.BOUND, 0.3, 1.0), False)
    proposed = AccessCandidate(
        "bm25-proposal", 99.0,
        _cert("bm25-proposal", QualificationStatus.UNRESOLVED, -1.0, 1.0),
        False)
    plan = plan_access(
        (archived, restore, proposed), workspace_budget=2, probe_budget=1,
        defer_cost=1.0,
        probes={"bm25-proposal": ProbeOption(
            "bm25-proposal", cost=0.1, post_lower=0.1, post_upper=0.9)},
    )
    assert "old-negative" not in plan.exposure_ids
    assert plan.probe_ids == ("bm25-proposal",)
    assert set(plan.exposure_ids) == {"qualified-positive", "bm25-proposal"}
    assert plan.persistent_actions["old-negative"] is PersistentAction.ARCHIVE
    assert plan.persistent_actions["qualified-positive"] is PersistentAction.RESTORE
    assert "bm25-proposal" not in plan.persistent_actions


def test_probe_priority_is_value_first_and_retrieval_second():
    low_value = AccessCandidate(
        "lexically-high", 100.0,
        _cert("lexically-high", QualificationStatus.UNRESOLVED, -1.0, 1.0),
        False)
    high_value = AccessCandidate(
        "information-high", 0.1,
        _cert("information-high", QualificationStatus.UNRESOLVED, -1.0, 1.0),
        False)
    plan = plan_access(
        (low_value, high_value), workspace_budget=1, probe_budget=1,
        defer_cost=1.0,
        probes={
            "lexically-high": ProbeOption("lexically-high", 0.4, -1.0, 1.0),
            "information-high": ProbeOption("information-high", 0.1, 0.2, 1.0),
        },
    )
    assert plan.probe_ids == ("information-high",)
    assert plan.exposure_ids == ("information-high",)
