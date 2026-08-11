from __future__ import annotations

import unittest

from unified_agent_memory_runner import POLICIES, run_policy


class UnifiedRunnerTest(unittest.TestCase):
    def test_policies_share_candidate_stream_and_complete_logs(self) -> None:
        rows = [run_policy(0, policy, 0.2, 20, 12) for policy in POLICIES]
        self.assertEqual(len({row["candidate_stream_sha256"] for row in rows}), 1)
        self.assertTrue(all(row["decision_log_completeness"] == 1.0 for row in rows))
        self.assertTrue(all(row["governance_transitions"] == 20.0 for row in rows))

    def test_risk_gated_policy_preserves_more_rare_critical_evidence(self) -> None:
        item_rows = [run_policy(seed, "causal_item", 0.2, 30, 12) for seed in range(10)]
        gated_rows = [run_policy(seed, "risk_gated_decomp_abstract", 0.2, 30, 12) for seed in range(10)]
        self.assertGreater(
            sum(float(row["rare_critical_recall"]) for row in gated_rows),
            sum(float(row["rare_critical_recall"]) for row in item_rows),
        )
        self.assertTrue(all(float(row["stale_exposure_rate"]) == 0.0 for row in gated_rows))


if __name__ == "__main__":
    unittest.main()
