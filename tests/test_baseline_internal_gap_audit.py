"""Regression tests for the constructive baseline-internal gap audit."""

from __future__ import annotations

import dataclasses
import json

import pytest

from src.sqcad.baseline_internal_gap_audit import (
    BASELINE_SCORE_SPECS,
    PublicDecisionView,
    run_baseline_internal_gap_audit,
    summarize_score_fibers,
)


def _row(episode: str, score: float, delta: float) -> dict:
    return {
        "episode_id": episode,
        "family": "test",
        "variant": episode,
        "score": score,
        "delta_keep_minus_archive": delta,
        "oracle_action": ("keep" if delta > 0 else
                          "archive" if delta < 0 else "neutral"),
    }


def test_score_view_cannot_expose_hidden_future_labels():
    names = {field.name for field in dataclasses.fields(PublicDecisionView)}
    forbidden = {"needed_future_ids", "oracle_action", "tau_keep_archive",
                 "lifecycle_value_keep", "lifecycle_value_archive",
                 "decision_action_label", "family", "variant"}
    assert names.isdisjoint(forbidden)
    assert all(spec.score.__annotations__.get("view") in
               (PublicDecisionView, "PublicDecisionView")
               for spec in BASELINE_SCORE_SPECS.values())


def test_same_score_fiber_and_opposite_sign_regret():
    result = summarize_score_fibers([
        _row("negative", 0.5, -2.0),
        _row("positive", 0.5, 3.0),
        _row("singleton", 0.7, 10.0),
    ])
    assert result["n_score_fibers"] == 2
    assert result["n_collision_fibers"] == 1
    assert result["n_heterogeneous_fibers"] == 1
    assert result["n_opposite_sign_fibers"] == 1
    assert result["epsilon_lc_lower_witness"] == 5.0
    assert result["max_deterministic_fixed_cost_regret"] == 2.0
    assert result["max_randomized_fixed_cost_regret"] == pytest.approx(6 / 5)


def test_value_difference_without_sign_flip_is_cost_shift_only():
    result = summarize_score_fibers([
        _row("low", 1.0, 1.0), _row("high", 1.0, 5.0)])
    assert result["n_heterogeneous_fibers"] == 1
    assert result["n_opposite_sign_fibers"] == 0
    assert result["max_randomized_fixed_cost_regret"] == 0.0
    assert result["max_cost_shift_regret_lower_bound"] == 1.0


def test_empty_tie_and_neutral_fibers_are_safe():
    empty = summarize_score_fibers([])
    assert empty["n_score_fibers"] == 0
    assert empty["max_gap_witness"] is None
    tied = summarize_score_fibers([
        _row("a", 0.0, 0.0), _row("b", 0.0, 0.0)])
    assert tied["n_heterogeneous_fibers"] == 0
    assert tied["n_opposite_sign_fibers"] == 0


@pytest.fixture(scope="module")
def audit() -> dict:
    return run_baseline_internal_gap_audit(control_pairs=2)


def test_constructive_audit_is_serializable_and_evidence_tiered(audit):
    json.dumps(audit, ensure_ascii=False)
    levels = {
        row["evidence_level"]
        for row in audit["baseline_results"].values()
    }
    assert any("official-code surface" in level for level in levels)
    assert any("transported official rule" in level for level in levels)
    assert any("associational signal proxy" in level for level in levels)
    assert "actmem" in audit["excluded_baselines"]
    assert audit["identification_positive_control"][
        "use_in_baseline_epsilon"] is False


def test_primary_audit_finds_algorithmic_score_witnesses(audit):
    for name, row in audit["baseline_results"].items():
        assert row["n_episodes"] > 0, name
        assert 0.0 <= row["future_kernel_non_null_rate"] <= 1.0
        assert 0.0 <= row["value_relevant_rate"] <= 1.0
        # A null result is informative: this small, exact-score sample may
        # fail to collide for a high-dimensional proxy (here Trivium).  The
        # audit must report zero rather than manufacture a witness.
        assert row["n_heterogeneous_fibers"] >= 0, name
        assert row["epsilon_lc_lower_witness"] >= 0.0, name
    witnessed = [name for name, row in audit["baseline_results"].items()
                 if row["epsilon_lc_lower_witness"] > 0.0]
    assert len(witnessed) >= 6


def test_identification_pairs_are_controls_not_baseline_failures(audit):
    control = audit["identification_positive_control"]
    assert control["n_pairs"] == 2
    assert control["n_oracle_flip_pairs"] == 2
    assert control["use_in_baseline_epsilon"] is False
