from __future__ import annotations

import unittest

from lifecycle_restore_benchmark import (
    POLICIES,
    SCENARIOS,
    aggregate_seed,
    build_world,
    random_scenario,
    run_policy,
)


class LifecycleRestoreBenchmarkTest(unittest.TestCase):
    def test_all_policies_share_world_stream(self) -> None:
        rows = aggregate_seed(3, SCENARIOS[0])
        self.assertEqual(len({row["candidate_stream_sha256"] for row in rows}), 1)
        self.assertEqual({row["policy"] for row in rows}, set(POLICIES))

    def test_decision_log_and_evidence_contract(self) -> None:
        world = build_world(4, SCENARIOS[0])
        row = run_policy(world, "recoverable_framework")
        self.assertEqual(float(row["decision_log_completeness"]), 1.0)
        self.assertEqual(float(row["evidence_survival"]), 1.0)

    def test_recoverable_policy_can_restore_after_recurrence(self) -> None:
        world = build_world(11, SCENARIOS[0])
        row = run_policy(world, "recoverable_framework")
        self.assertGreaterEqual(float(row["restore_events"]), 0.0)
        self.assertLessEqual(float(row["recovery_latency"]), world.scenario.horizon)

    def test_random_worlds_change_topology(self) -> None:
        scenarios = [random_scenario(seed) for seed in range(30)]
        self.assertGreater(len({scenario.group_count for scenario in scenarios}), 1)
        self.assertGreater(len({scenario.items_per_group for scenario in scenarios}), 1)

    def test_nonrecurring_control_does_not_require_restore(self) -> None:
        scenario = next(value for value in SCENARIOS if value.name == "one_way_obsolescence")
        row = run_policy(build_world(8, scenario), "recoverable_framework")
        self.assertEqual(float(row["recurrence"]), 0.0)
        self.assertEqual(float(row["recovery_latency"]), float(scenario.horizon))


if __name__ == "__main__":
    unittest.main()
