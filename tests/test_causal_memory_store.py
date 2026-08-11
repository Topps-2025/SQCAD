from __future__ import annotations

import json
import unittest

from causal_memory_store import CausalMemoryStore


class CausalMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = CausalMemoryStore()

    def _supported_rule(self):
        evidence = [
            self.store.add_evidence("A contains condition X.", "s1", "user-a", "task-food"),
            self.store.add_evidence("B contains condition X.", "s2", "user-a", "task-food"),
        ]
        factors = [
            self.store.add_factor(eid, "condition", "X", "extractor-v1", 0.95)
            for eid in evidence
        ]
        rule = self.store.propose_rule(
            "condition X changes outcome Y",
            factors,
            "user-a",
            "task-food",
            stability=0.9,
            evidence_coverage=1.0,
        )
        return evidence, factors, rule

    def test_rule_requires_evidence_backed_factor(self):
        with self.assertRaises(ValueError):
            self.store.propose_rule("unsupported", [], "u", "t", 1.0, 1.0)

    def test_activation_requires_multiple_supports(self):
        eid = self.store.add_evidence("one source", "s", "u", "t")
        factor = self.store.add_factor(eid, "condition", "X", "v1", 1.0)
        rule = self.store.propose_rule("r", [factor], "u", "t", 1.0, 1.0)
        decision = self.store.try_activate_rule(rule)
        self.assertFalse(decision.activated)
        self.assertIn("insufficient_support", decision.reason)

    def test_scope_mismatch_blocks_activation(self):
        e1 = self.store.add_evidence("x", "s1", "u1", "t")
        e2 = self.store.add_evidence("x", "s2", "u2", "t")
        f1 = self.store.add_factor(e1, "condition", "X", "v1", 1.0)
        f2 = self.store.add_factor(e2, "condition", "X", "v1", 1.0)
        rule = self.store.propose_rule("r", [f1, f2], "u1", "t", 1.0, 1.0)
        decision = self.store.try_activate_rule(rule)
        self.assertFalse(decision.activated)
        self.assertIn("scope_mismatch", decision.reason)

    def test_active_rule_is_scope_filtered_and_traceable(self):
        _, _, rule = self._supported_rule()
        self.assertTrue(self.store.try_activate_rule(rule).activated)
        self.assertEqual(len(self.store.eligible_rules("user-a", "task-food")), 1)
        self.assertEqual(len(self.store.eligible_rules("user-b", "task-food")), 0)
        self.assertEqual(len(self.store.provenance(rule)), 2)

    def test_archived_evidence_blocks_new_rule_activation_and_restores(self):
        evidence, _, rule = self._supported_rule()
        self.store.archive_evidence(evidence[0], "governance_test")
        decision = self.store.try_activate_rule(rule)
        self.assertFalse(decision.activated)
        self.assertIn("inactive_provenance", decision.reason)
        self.store.restore_evidence(evidence[0], "rollback")
        self.assertTrue(self.store.try_activate_rule(rule).activated)
        self.assertIn("governance_test", self.store.audit_log())
        self.assertIn("rollback", self.store.audit_log())

    def test_downweight_and_isolate_are_reversible(self):
        evidence = self.store.add_evidence("critical constraint", "s1", "u", "t")
        self.store.downweight_evidence(evidence, "low_default_exposure")
        self.store.restore_evidence(evidence, "task_trigger")
        self.store.isolate_evidence(evidence, "scope_guard")
        self.store.restore_evidence(evidence, "scope_match")
        status = self.store.conn.execute(
            "SELECT status FROM evidence WHERE evidence_id = ?", (evidence,)
        ).fetchone()["status"]
        self.assertEqual(status, "active")
        self.assertIn("low_default_exposure", self.store.audit_log())
        self.assertIn("scope_guard", self.store.audit_log())

    def test_decision_log_round_trip(self):
        decision_id = self.store.record_decision(
            episode_id="ep-1",
            step=2,
            history={"task": "qa", "model_version": "m1"},
            candidates=[{"component_id": "fa-1", "evidence_id": "ev-1"}],
            behavior_action={"governance": "keep", "exposure": "show"},
            propensity=0.25,
            exposure={"fa-1": 1},
            adoption={"fa-1": True},
            agent_action={"type": "answer", "text": "ok"},
            outcome={"success": 1, "loss": 0.0},
        )
        rows = self.store.decisions("ep-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision_id"], decision_id)
        self.assertAlmostEqual(rows[0]["propensity"], 0.25)
        self.assertEqual(json.loads(rows[0]["candidates_json"])[0]["evidence_id"], "ev-1")

    def test_decision_log_rejects_invalid_propensity(self):
        with self.assertRaises(ValueError):
            self.store.record_decision(
                episode_id="ep-1", step=0, history={}, candidates=[],
                behavior_action={}, propensity=0.0, exposure={}, adoption={},
                agent_action={}, outcome={},
            )


if __name__ == "__main__":
    unittest.main()
