from __future__ import annotations

import unittest

from structural_generalization_benchmark import (
    SCENARIOS,
    aggregate_seed,
    build_episode,
    random_scenario,
    pairwise_framework_wins,
    run_policy,
    task_budget,
)


class StructuralGeneralizationBenchmarkTest(unittest.TestCase):
    def test_every_policy_receives_same_candidate_stream(self) -> None:
        rows = aggregate_seed(seed=3, scenario=SCENARIOS[0], episodes=12)
        self.assertEqual(len({row["candidate_stream_sha256"] for row in rows}), 1)

    def test_budgeted_policies_respect_task_budget(self) -> None:
        scenario = SCENARIOS[0]
        for episode in range(20):
            task, paths, group_noise = build_episode(9, episode, scenario)
            for policy in ("uniform_item_probe", "greedy_item_lcb", "hierarchical_no_gate", "hierarchical_framework"):
                row = run_policy(task, paths, group_noise, scenario, policy)
                self.assertLessEqual(float(row["intervention_cost"]), task_budget(task) + 1e-12)

    def test_framework_advantage_is_not_asserted_in_gap_absent_control(self) -> None:
        scenario = next(value for value in SCENARIOS if value.name == "semantic_aligned_stationary")
        rows = aggregate_seed(seed=17, scenario=scenario, episodes=120)
        by_policy = {str(row["policy"]): row for row in rows}
        self.assertGreater(
            float(by_policy["association"]["net_utility"]),
            float(by_policy["hierarchical_framework"]["net_utility"]),
        )

    def test_hierarchical_structure_beats_item_probe_in_core_gap(self) -> None:
        scenario = next(value for value in SCENARIOS if value.name == "core_endogenous")
        rows = aggregate_seed(seed=23, scenario=scenario, episodes=160)
        by_policy = {str(row["policy"]): row for row in rows}
        self.assertLess(
            float(by_policy["hierarchical_framework"]["regret"]),
            float(by_policy["greedy_item_lcb"]["regret"]),
        )

    def test_random_worlds_vary_candidate_topology_without_changing_stream_fairness(self) -> None:
        scenarios = [random_scenario(seed) for seed in range(30)]
        self.assertGreater(len({scenario.group_count for scenario in scenarios}), 1)
        self.assertGreater(len({scenario.items_per_group for scenario in scenarios}), 1)
        for seed, scenario in enumerate(scenarios[:5]):
            task, paths, _ = build_episode(seed, 0, scenario)
            self.assertEqual(len(paths), scenario.group_count * scenario.items_per_group)
            rows = aggregate_seed(seed, scenario, episodes=5)
            self.assertEqual(len({row["candidate_stream_sha256"] for row in rows}), 1)

    def test_pairwise_summary_reports_seed_level_uncertainty(self) -> None:
        rows = []
        scenario = SCENARIOS[0]
        for seed in range(4):
            rows.extend(aggregate_seed(seed, scenario, episodes=8))
        summary = pairwise_framework_wins(rows)[scenario.name]["greedy_item_lcb"]
        self.assertIn("net_utility_delta_ci95", summary)
        self.assertIn("regret_reduction_ci95", summary)
        self.assertEqual(summary["n_seeds"], 4.0)


if __name__ == "__main__":
    unittest.main()
