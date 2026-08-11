from __future__ import annotations

import unittest

from governance_baseline_simulator import paired_comparison, run_seed


class GovernanceBaselineSimulatorTest(unittest.TestCase):
    def test_all_methods_obey_same_retention_budget(self) -> None:
        row = run_seed(seed=0, samples_per_environment=1000, budget=36, group_noise=0.1)
        self.assertGreaterEqual(len(row), 6)
        self.assertTrue(all(metrics["retained_count"] == 36.0 for metrics in row.values()))

    def test_paired_summary_is_seed_level_and_direction_aware(self) -> None:
        rows = [run_seed(seed, 1000, 36, 0.0) for seed in range(5)]
        paired = paired_comparison(rows)
        self.assertEqual(paired["normalized_utility"]["n"], 5.0)
        self.assertTrue(paired["normalized_utility"]["higher_is_better"])
        self.assertFalse(paired["stale_retention_rate"]["higher_is_better"])
        self.assertGreaterEqual(paired["normalized_utility"]["paired_win_rate"], 0.0)
        self.assertLessEqual(paired["normalized_utility"]["paired_win_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
