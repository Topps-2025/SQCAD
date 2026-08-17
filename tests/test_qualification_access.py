"""Tests for the decision-identification-aware qualification/access module."""

from src.sqcad.qualification_access import (
    AccessCandidate, GovernanceAction, PersistentAction, ProbeOption,
    QualificationCertificate, QualificationStatus, ScopeKey,
    decide_persistent_action, plan_access, probe_value,
)


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
