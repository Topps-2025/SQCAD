import pytest

from sqcad.lifecycle_belief_theory import (
    binary_classification_information_value,
    finite_lifecycle_trichotomy,
    finite_score_quotient_violations,
    fiber_minimax_regret,
    lifecycle_contrast,
    priced_recoverability_regret_floor,
    probe_is_bayes_preferred,
    recoverability_regret_lower_bound,
    recoverability_value,
    required_recoverability_kl,
    task_universal_shifted_regret,
    value_separating_signed_kernel_contrasts,
    two_state_score_regret,
)


def _finite_transcript_fixture():
    states = ("x1", "x2")
    tasks = ("z",)
    scores = {"x1": "same-score", "x2": "same-score"}
    return states, tasks, scores


def test_finite_trichotomy_detects_future_null_channel():
    states, tasks, scores = _finite_transcript_fixture()
    keep = {(state, "z"): {"y": 1.0} for state in states}
    archive = {(state, "z"): {"y": 1.0} for state in states}
    assert finite_lifecycle_trichotomy(
        states, tasks, scores, keep, archive
    ) == "future-null"


def test_finite_trichotomy_detects_lifecycle_complete_score():
    states, tasks, scores = _finite_transcript_fixture()
    keep = {(state, "z"): {"useful": 0.75, "noise": 0.25} for state in states}
    archive = {(state, "z"): {"useful": 0.25, "noise": 0.75} for state in states}
    immediate = {(state, "z"): -0.1 for state in states}
    assert finite_lifecycle_trichotomy(
        states,
        tasks,
        scores,
        keep,
        archive,
        immediate_contrasts=immediate,
    ) == "lifecycle-complete"


def test_finite_trichotomy_detects_future_lossy_score():
    states, tasks, scores = _finite_transcript_fixture()
    keep = {
        ("x1", "z"): {"useful": 1.0},
        ("x2", "z"): {"noise": 1.0},
    }
    archive = {(state, "z"): {"noise": 1.0} for state in states}
    assert finite_lifecycle_trichotomy(
        states, tasks, scores, keep, archive
    ) == "future-lossy"


def test_midpoint_shift_has_opposite_gaps_and_quarter_regret():
    result = task_universal_shifted_regret(3.0, -1.0)
    assert result["midpoint_shift"] == pytest.approx(1.0)
    assert result["first_shifted_contrast"] == pytest.approx(2.0)
    assert result["second_shifted_contrast"] == pytest.approx(-2.0)
    assert result["minimax_regret"] == pytest.approx(1.0)


def test_finite_trichotomy_rejects_invalid_probability_distribution():
    states, tasks, scores = _finite_transcript_fixture()
    keep = {(state, "z"): {"y": 1.0} for state in states}
    keep[("x1", "z")] = {"y": 1.2}
    archive = {(state, "z"): {"y": 1.0} for state in states}
    with pytest.raises(ValueError, match="sum to one"):
        finite_lifecycle_trichotomy(states, tasks, scores, keep, archive)


def test_finite_trichotomy_rejects_hidden_immediate_cost():
    states, tasks, scores = _finite_transcript_fixture()
    keep = {(state, "z"): {"y": 1.0} for state in states}
    archive = {(state, "z"): {"y": 1.0} for state in states}
    immediate = {("x1", "z"): 0.0, ("x2", "z"): 1.0}
    with pytest.raises(ValueError, match="constant on score fibers"):
        finite_lifecycle_trichotomy(
            states,
            tasks,
            scores,
            keep,
            archive,
            immediate_contrasts=immediate,
        )


def test_lifecycle_bellman_three_term_identity():
    contrast = lifecycle_contrast(
        immediate_keep=-1.0,
        immediate_archive=0.0,
        access_keep=-0.5,
        access_archive=0.0,
        information_keep=3.0,
        information_archive=0.5,
        gamma=0.9,
    )
    assert contrast.immediate == -1.0
    assert contrast.access == -0.5
    assert contrast.information == 2.5
    assert contrast.total == pytest.approx(0.8)


def test_same_score_agent_witness_requires_opposite_actions():
    reward = 8.0
    gamma = 0.9
    immediate = -gamma * reward / 4.0
    recoverable = lifecycle_contrast(
        immediate, 0.0, 0.0, 0.0, reward / 2.0, 0.0, gamma
    )
    censored = lifecycle_contrast(
        immediate, 0.0, 0.0, 0.0, 0.0, 0.0, gamma
    )
    assert recoverable.total == pytest.approx(gamma * reward / 4.0)
    assert censored.total == pytest.approx(-gamma * reward / 4.0)

    regret = two_state_score_regret(recoverable.total, censored.total)
    assert regret["p_keep_minimax"] == pytest.approx(0.5)
    assert regret["minimax_regret"] == pytest.approx(gamma * reward / 8.0)
    assert regret["least_favorable_bayes_regret"] == regret["minimax_regret"]


def test_score_fiber_minimax_regret_is_bounded_by_quarter_width():
    result = fiber_minimax_regret(lower=-3.0, upper=1.0)
    assert result["p_keep"] == pytest.approx(0.25)
    assert result["regret"] == pytest.approx(0.75)
    assert result["regret"] <= result["quarter_width_bound"]


@pytest.mark.parametrize(
    ("lower", "upper", "p_keep"),
    [
        (0.0, 0.0, 1.0),
        (0.0, 2.0, 1.0),
        (-2.0, 0.0, 0.0),
        (1.0, 3.0, 1.0),
        (-3.0, -1.0, 0.0),
    ],
)
def test_non_crossing_score_fiber_has_zero_regret(lower, upper, p_keep):
    result = fiber_minimax_regret(lower, upper)
    assert result["p_keep"] == p_keep
    assert result["regret"] == 0.0


def test_score_fiber_rejects_reversed_interval():
    with pytest.raises(ValueError):
        fiber_minimax_regret(1.0, -1.0)


def test_blackwell_more_informative_binary_experiment_has_more_value():
    archive = binary_classification_information_value(0.5, reward=10.0)
    noisy_keep = binary_classification_information_value(0.75, reward=10.0)
    perfect_keep = binary_classification_information_value(1.0, reward=10.0)
    assert archive == 0.0
    assert perfect_keep > noisy_keep > archive


def test_continuation_vor_is_distinct_from_conditional_information_vor():
    value = recoverability_value(
        access_keep=-3.0,
        access_archive=0.0,
        information_keep=2.0,
        information_archive=0.0,
        gamma=0.9,
    )
    assert value.conditional_information == pytest.approx(1.8)
    assert value.access == pytest.approx(-2.7)
    assert value.continuation == pytest.approx(-0.9)


def test_common_state_kernel_makes_continuation_and_information_vor_equal():
    value = recoverability_value(1.0, 1.0, 2.0, 0.5, gamma=0.8)
    assert value.access == 0.0
    assert value.continuation == value.conditional_information


def test_dynamic_score_quotient_accepts_lumpable_agent_kernel():
    states = ("recoverable-a", "recoverable-b", "archived-a", "archived-b")
    quotient = {
        "recoverable-a": "recoverable",
        "recoverable-b": "recoverable",
        "archived-a": "archived",
        "archived-b": "archived",
    }
    actions = ("keep", "archive")
    rewards = {(state, action): 0.0 for state in states for action in actions}
    transitions = {
        (state, action): {
            ("recoverable-a" if action == "keep" else "archived-a"): 1.0
        }
        for state in states
        for action in actions
    }
    assert not finite_score_quotient_violations(
        states, actions, quotient, rewards, transitions
    )


def test_dynamic_score_quotient_detects_unencoded_recoverability_kernel():
    states = ("same-score-recoverable", "same-score-censored", "future-evidence", "no-evidence")
    quotient = {
        "same-score-recoverable": "current-score",
        "same-score-censored": "current-score",
        "future-evidence": "evidence",
        "no-evidence": "none",
    }
    actions = ("archive",)
    rewards = {(state, "archive"): 0.0 for state in states}
    transitions = {
        ("same-score-recoverable", "archive"): {"future-evidence": 1.0},
        ("same-score-censored", "archive"): {"no-evidence": 1.0},
        ("future-evidence", "archive"): {"future-evidence": 1.0},
        ("no-evidence", "archive"): {"no-evidence": 1.0},
    }
    violations = finite_score_quotient_violations(
        states, actions, quotient, rewards, transitions
    )
    assert violations == [
        "transition:'archive':'same-score-recoverable'!='same-score-censored'"
    ]


def test_value_separating_signed_kernel_constructs_opposite_actions():
    result = value_separating_signed_kernel_contrasts(0.75, -0.25, gamma=0.8)
    assert result["immediate_contrast"] == pytest.approx(-0.2)
    assert result["first_contrast"] == pytest.approx(0.4)
    assert result["second_contrast"] == pytest.approx(-0.4)


def test_probe_threshold_is_strict():
    assert probe_is_bayes_preferred(2.0, cost=0.9, gamma=0.5)
    assert not probe_is_bayes_preferred(2.0, cost=1.0, gamma=0.5)


def test_recoverability_information_budget_lower_bound():
    no_information = recoverability_regret_lower_bound(8.0, 8.0, transcript_kl=0.0)
    one_nat = recoverability_regret_lower_bound(8.0, 8.0, transcript_kl=1.0)
    assert no_information == pytest.approx(2.0)
    assert one_nat == pytest.approx(2.0 / 2.718281828459045)
    assert one_nat < no_information


def test_recoverability_information_budget_handles_asymmetric_gaps():
    # The weighted BH relaxation gives d_plus*d_minus/(2*(d_plus+d_minus))
    # when the two lifecycle worlds have unequal authorization gaps.
    bound = recoverability_regret_lower_bound(6.0, 2.0, transcript_kl=0.0)
    assert bound == pytest.approx(0.75)
    assert recoverability_regret_lower_bound(6.0, 2.0, transcript_kl=1.0) < bound


def test_required_recoverability_kl_inverts_regret_floor():
    required = required_recoverability_kl(8.0, 8.0, target_regret=0.5)
    assert required == pytest.approx(1.3862943611198906)
    assert recoverability_regret_lower_bound(8.0, 8.0, required) == pytest.approx(0.5)
    assert required_recoverability_kl(8.0, 8.0, target_regret=2.0) == 0.0


def test_priced_recoverability_frontier_balances_cost_and_error():
    floor = priced_recoverability_regret_floor(
        8.0,
        8.0,
        kl_per_action=1.0,
        action_cost=0.5,
    )
    expected_actions = floor / 0.5
    terminal_floor = recoverability_regret_lower_bound(
        8.0,
        8.0,
        transcript_kl=expected_actions,
    )
    assert floor == pytest.approx(terminal_floor)
    assert 0.0 < floor < recoverability_regret_lower_bound(8.0, 8.0, 0.0)


def test_zero_kl_recovery_action_cannot_reduce_priced_frontier():
    assert priced_recoverability_regret_floor(
        8.0,
        8.0,
        kl_per_action=0.0,
        action_cost=0.5,
    ) == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("positive_gap", "negative_gap", "transcript_kl"),
    [(0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, -1.0)],
)
def test_recoverability_lower_bound_rejects_invalid_inputs(
    positive_gap, negative_gap, transcript_kl
):
    with pytest.raises(ValueError):
        recoverability_regret_lower_bound(positive_gap, negative_gap, transcript_kl)


@pytest.mark.parametrize("accuracy", [0.49, 1.01])
def test_binary_information_value_rejects_invalid_accuracy(accuracy):
    with pytest.raises(ValueError):
        binary_classification_information_value(accuracy)
