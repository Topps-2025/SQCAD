from __future__ import annotations

import copy
import unittest

from score_semantic_gate_a import gate_decision, metrics_from_counts, score_packet


def packet() -> dict:
    return {
        "packet_id": "p1",
        "split": "pilot",
        "evidence_sessions": [
            {
                "session_id": "s1",
                "turns": [{"role": "user", "content": "I no longer prefer tea after June."}],
            }
        ],
        "annotation": {
            "status": "adjudicated",
            "evidence_spans": [
                {"span_id": "sp1", "session_id": "s1", "turn_index": 0, "char_start": 2, "char_end": 23, "text": "no longer prefer tea", "role": "user"},
                {"span_id": "sp2", "session_id": "s1", "turn_index": 0, "char_start": 24, "char_end": 34, "text": "after June", "role": "user"},
            ],
            "factors": [
                {"factor_id": "f1", "factor_type": "preference", "normalized_form": "does not prefer tea", "span_ids": ["sp1"], "subject_scope": "user", "task_scope": "beverage", "temporal_scope": "after June", "polarity": "negative", "evidential_status": "explicit"},
                {"factor_id": "f2", "factor_type": "time", "normalized_form": "after June", "span_ids": ["sp2"], "subject_scope": "user", "task_scope": "beverage", "temporal_scope": "after June", "polarity": "positive", "evidential_status": "explicit"},
            ],
            "relations": [
                {"relation_id": "r1", "relation_type": "applicable_under", "source_factor_ids": ["f1"], "target_factor_ids": ["f2"], "span_ids": ["sp1", "sp2"], "evidential_status": "explicit"}
            ],
            "abstract_rule_candidates": [],
            "query_required_factor_ids": ["f1", "f2"],
            "counterexample_checks": [],
        },
    }


class GateAScorerTests(unittest.TestCase):
    def test_identical_annotation_scores_one(self):
        gold = packet()
        counts = score_packet(gold, copy.deepcopy(gold))
        metrics = metrics_from_counts(counts)
        self.assertAlmostEqual(metrics["factor_micro_f1"], 1.0)
        self.assertAlmostEqual(metrics["relation_f1"], 1.0)
        self.assertAlmostEqual(metrics["provenance_coverage"], 1.0)
        self.assertAlmostEqual(metrics["scope_completeness"], 1.0)
        self.assertAlmostEqual(metrics["negation_error_rate"], 0.0)
        self.assertAlmostEqual(metrics["temporal_error_rate"], 0.0)
        self.assertTrue(gate_decision(metrics)["passed"])

    def test_missing_time_and_relation_fails_gate(self):
        gold = packet()
        pred = copy.deepcopy(gold)
        pred["annotation"]["factors"] = pred["annotation"]["factors"][:1]
        pred["annotation"]["relations"] = []
        pred["annotation"]["query_required_factor_ids"] = ["f1"]
        counts = score_packet(gold, pred)
        metrics = metrics_from_counts(counts)
        self.assertLess(metrics["factor_recall"], 1.0)
        self.assertEqual(metrics["relation_f1"], 0.0)
        self.assertEqual(metrics["temporal_error_rate"], 1.0)
        self.assertFalse(gate_decision(metrics)["passed"])

    def test_wrong_scope_reduces_completeness(self):
        gold = packet()
        pred = copy.deepcopy(gold)
        pred["annotation"]["factors"][0]["subject_scope"] = "global"
        counts = score_packet(gold, pred)
        metrics = metrics_from_counts(counts)
        self.assertLess(metrics["scope_completeness"], 1.0)
        self.assertFalse(gate_decision(metrics)["checks"]["scope_completeness"]["passed"])

    def test_gate_uses_conservative_confidence_bound(self):
        metrics = {
            "factor_micro_f1": 0.82,
            "relation_f1": 0.75,
            "provenance_coverage": 0.97,
            "scope_completeness": 0.92,
            "negation_error_rate": 0.05,
            "temporal_error_rate": 0.05,
            "update_error_rate": 0.05,
            "rule_overgeneralization_rate": 0.05,
        }
        intervals = {
            key: {"lower": max(0.0, value - 0.05), "upper": min(1.0, value + 0.05), "samples": 1000.0}
            for key, value in metrics.items()
        }
        decision = gate_decision(metrics, intervals)
        self.assertFalse(decision["passed"])
        self.assertFalse(decision["checks"]["factor_micro_f1"]["passed"])


if __name__ == "__main__":
    unittest.main()
