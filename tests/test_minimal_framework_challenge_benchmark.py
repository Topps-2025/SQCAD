from __future__ import annotations

import math
from dataclasses import replace

import minimal_framework_challenge_benchmark as benchmark


def tiny_world():
    scenario = replace(benchmark.base.SCENARIOS[0], horizon=12)
    return benchmark.base.build_world(3, scenario)


def test_all_policies_share_candidate_stream():
    world = tiny_world()
    rows = [benchmark.run_policy(world, spec) for spec in benchmark.POLICY_SPECS]
    assert len({row["candidate_stream_sha256"] for row in rows}) == 1
    assert {row["policy"] for row in rows} == set(benchmark.POLICIES)


def test_outputs_are_finite_and_logs_complete():
    world = tiny_world()
    for spec in benchmark.POLICY_SPECS:
        row = benchmark.run_policy(world, spec)
        for metric in benchmark.METRICS:
            assert math.isfinite(float(row[metric]))
        assert row["decision_log_completeness"] == 1.0


def test_only_oracle_policy_uses_true_groups():
    assert sum(spec.oracle_groups for spec in benchmark.POLICY_SPECS) == 1
    assert benchmark.POLICY_BY_NAME["oracle_structure_reference"].oracle_groups
    assert not benchmark.POLICY_BY_NAME["minimal_framework"].oracle_groups


def test_minimal_framework_excludes_unproven_candidate_modules():
    spec = benchmark.POLICY_BY_NAME["minimal_framework"]
    assert spec.causal
    assert not spec.hierarchical
    assert not spec.adaptive_budget
    assert not spec.sentinel_correction
    assert spec.decay_rule == "risk"
    assert spec.recoverable and spec.restore_enabled
    assert spec.conditional_association


def test_causal_beliefs_are_separated_by_observable_version():
    world = tiny_world()
    groups = benchmark.group_map(world, benchmark.POLICY_BY_NAME["minimal_framework"])
    item_beliefs, group_beliefs = benchmark.initialize_scoped_beliefs(world, groups)
    versions = {task.version for task in world.tasks}
    assert len(item_beliefs) == len(world.items) * len(versions)
    assert len(group_beliefs) == len(groups) * len(versions)
    item_id = world.items[0].item_id
    if len(versions) > 1:
        first, second = sorted(versions)[:2]
        benchmark.normal_update(item_beliefs[(item_id, first)], 1.0, 0.5)
        assert item_beliefs[(item_id, first)].count == 1
        assert item_beliefs[(item_id, second)].count == 0


def test_historical_association_prior_is_deterministic_observed_summary():
    world = tiny_world()
    first = benchmark.historical_association_prior(world, world.items[0])
    second = benchmark.historical_association_prior(world, world.items[0])
    assert math.isfinite(first)
    assert first == second


def test_cheap_association_only_proposes_a_bounded_causal_shortlist():
    world = tiny_world()
    items = {item.item_id: item for item in world.items}
    active = set(items)
    task = world.tasks[0]
    association = {
        item.item_id: benchmark.historical_association_prior(world, item)
        for item in world.items
    }
    proposed = benchmark.causal_proposal_ids(active, task, association)
    bound = 2 * math.ceil(math.sqrt(len(active)))
    assert 0 < len(proposed) <= bound
    top_semantic = max(active, key=lambda item_id: task.semantic_scores[item_id])
    assert top_semantic in proposed


def test_causal_belief_updates_require_probes():
    belief = benchmark.Belief()
    assert belief.count == 0
    benchmark.normal_update(belief, 1.0, 0.5)
    assert belief.count == 1
    assert belief.mean > 0.0
    protocol = benchmark.run_experiment(1, 1, horizon=8)["protocol"]
    assert protocol["ordinary_outcomes_update_causal_belief"] is False


def test_evsi_is_decision_relevant_and_shrinks_with_certainty_or_noise():
    uncertain = benchmark.Belief(mean=0.0, sd=1.15)
    certain = benchmark.Belief(mean=0.0, sd=0.08)
    assert benchmark.one_step_evsi(uncertain, 0.55, risk=0.7) > 0.0
    assert benchmark.one_step_evsi(uncertain, 0.55, risk=0.7) > benchmark.one_step_evsi(
        certain, 0.55, risk=0.7
    )
    assert benchmark.one_step_evsi(uncertain, 0.40, risk=0.7) > benchmark.one_step_evsi(
        uncertain, 2.00, risk=0.7
    )
    assert benchmark.one_step_evsi(
        uncertain, 0.55, risk=0.7, alternative_value=1.5
    ) < benchmark.one_step_evsi(uncertain, 0.55, risk=0.7)


def test_associational_fallback_disappears_at_maximum_risk():
    low_risk = benchmark.conditional_association_value(1.0, 0.9, 0.0, 0.1)
    high_risk = benchmark.conditional_association_value(1.0, 0.9, 1.0, 0.1)
    assert low_risk > 0.0
    assert high_risk == 0.0


def test_causal_action_requires_family_wise_qualification():
    unprobed = benchmark.Belief(mean=2.0, sd=0.1, count=0)
    weak = benchmark.Belief(mean=0.2, sd=0.5, count=2)
    strong = benchmark.Belief(mean=2.0, sd=0.1, count=2)
    assert benchmark.qualified_action_value(unprobed, 0.5, 10) == -math.inf
    assert benchmark.qualified_action_value(weak, 0.5, 10) == -math.inf
    assert math.isfinite(benchmark.qualified_action_value(strong, 0.5, 10))
    negative = benchmark.Belief(mean=-2.0, sd=0.1, count=2)
    assert benchmark.causal_qualification_state(strong, 10) == "positive-qualified"
    assert benchmark.causal_qualification_state(negative, 10) == "negative-qualified"
    assert benchmark.causal_qualification_state(weak, 10) == "unresolved"
    assert benchmark.sequential_qualification_alpha(5, 10) < benchmark.sequential_qualification_alpha(1, 10)


def test_qualification_evsi_values_access_state_changes_not_reranking():
    uncertain = benchmark.Belief(mean=0.0, sd=1.0, count=0)
    value = benchmark.qualification_evsi(
        uncertain,
        observation_sd=0.5,
        family_size=5,
        full_association_value=1.0,
        conditional_fallback_value=0.2,
        alternative_value=0.0,
    )
    assert value >= 0.0


def test_causal_restore_requires_scoped_evidence_or_paid_revalidation():
    world = tiny_world()
    spec = benchmark.POLICY_BY_NAME["minimal_framework"]
    item = world.items[0]
    task = max(world.tasks, key=lambda value: value.semantic_scores[item.item_id])
    beliefs = {entry.item_id: benchmark.Belief() for entry in world.items}
    association = {entry.item_id: 1.0 for entry in world.items}
    access = {entry.item_id: 0.05 for entry in world.items}
    archived = {item.item_id}
    active = {entry.item_id for entry in world.items if entry.item_id != item.item_id}
    restored, pending = benchmark.prepare_restoration(
        world,
        task,
        spec,
        beliefs,
        association,
        access,
        archived,
        active,
        version_changed=True,
    )
    assert restored == 0
    assert item.item_id in pending
    assert item.item_id in archived

    beliefs[item.item_id] = benchmark.Belief(mean=1.0, sd=0.10, count=2)
    restored, pending = benchmark.prepare_restoration(
        world,
        task,
        spec,
        beliefs,
        association,
        access,
        archived,
        active,
        version_changed=True,
    )
    assert restored == 1
    assert not pending
    assert item.item_id in active


def test_unqualified_causal_belief_cannot_drive_access_decay():
    world = tiny_world()
    task = world.tasks[0]
    beliefs = {item.item_id: benchmark.Belief() for item in world.items}
    access = {item.item_id: 1.0 for item in world.items}
    benchmark.apply_risk_decay(world, task, beliefs, access)
    assert set(access.values()) == {1.0}

    target = world.items[0].item_id
    beliefs[target] = benchmark.Belief(mean=-2.0, sd=0.1, count=2)
    benchmark.apply_risk_decay(world, task, beliefs, access)
    assert access[target] < 1.0


def test_module_contrasts_are_declared():
    contrasts = benchmark.module_contrasts()
    assert {
        "causal_evidence",
        "hierarchical_structure",
        "adaptive_budget",
        "group_to_item_sentinel_correction",
        "risk_conditioned_decay",
        "recoverability",
        "oracle_structure_reference",
    } <= set(contrasts)


def test_module_contrasts_change_only_the_declared_mechanism():
    expected_differences = {
        "causal_evidence": {"causal"},
        "hierarchical_structure": {"hierarchical"},
        "adaptive_budget": {"adaptive_budget"},
        "group_to_item_sentinel_correction": {"sentinel_correction"},
        "risk_conditioned_decay": {"decay_rule"},
        "recoverability": {"recoverable", "restore_enabled"},
        "oracle_structure_reference": {"oracle_groups"},
    }
    for module, (without, with_module) in benchmark.module_contrasts().items():
        before = benchmark.POLICY_BY_NAME[without]
        after = benchmark.POLICY_BY_NAME[with_module]
        differences = {
            field
            for field in before.__dataclass_fields__
            if field != "name" and getattr(before, field) != getattr(after, field)
        }
        assert differences == expected_differences[module]


def test_fixed_budget_is_the_generator_expectation_not_a_tuned_value():
    expected = 2.15 + 1.10 * ((0.10 + 1.00) / 2.0) + 0.85 * ((0.05 + 1.00) / 2.0)
    assert math.isclose(benchmark.FIXED_EXPECTED_BUDGET, expected)


def test_empty_subgroup_is_reported_without_fabricated_statistics():
    summary = benchmark.metric_summary([])
    assert summary == {"mean": None, "sd": None, "ci95": None, "n": 0.0}
    report = benchmark.run_experiment(1, 1, horizon=8)
    for subgroup in report["random_subgroups"].values():
        for policy in subgroup.values():
            for metric in policy.values():
                if metric["n"] == 0.0:
                    assert metric["mean"] is None
