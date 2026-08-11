"""Structural tests for the query-independent Gate A negative control."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_semantic_gate_a import score_packet


ROOT = Path(__file__).resolve().parent
DATABASE = Path(r"D:\Engineering\SQCAD\database")
GOLD = DATABASE / "datasets" / "GateA" / "longmemeval_semantic_gate_a_200.jsonl"
PRED = DATABASE / "results" / "gate_a" / "predictions_pos_regex_baseline.jsonl"


class BaselineArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gold = {item["packet_id"]: item for item in (json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip())}
        cls.pred = {item["packet_id"]: item for item in (json.loads(line) for line in PRED.read_text(encoding="utf-8").splitlines() if line.strip())}

    def test_packet_identity_and_no_gold_leak(self) -> None:
        self.assertEqual(set(self.gold), set(self.pred))
        for packet_id, packet in self.pred.items():
            self.assertNotIn("adjudication_only", packet)
            self.assertNotIn("answer_session_ids", packet)
            serialized = json.dumps(packet, ensure_ascii=False)
            self.assertNotIn("reference_answer", serialized)
            for key in ("schema_version", "packet_id", "split", "question_id", "question_type", "question", "question_date", "evidence_sessions"):
                self.assertEqual(packet[key], self.gold[packet_id][key], packet_id)

    def test_provenance_and_factor_closure(self) -> None:
        for packet_id, packet in self.pred.items():
            annotation = packet["annotation"]
            spans = {span["span_id"]: span for span in annotation["evidence_spans"]}
            factors = {factor["factor_id"]: factor for factor in annotation["factors"]}
            self.assertEqual(annotation["status"], "in_progress")
            self.assertEqual(len(spans), len(annotation["evidence_spans"]))
            self.assertEqual(len(factors), len(annotation["factors"]))
            turns = {(session["session_id"], index): turn for session in packet["evidence_sessions"] for index, turn in enumerate(session["turns"])}
            for span in spans.values():
                turn = turns[(span["session_id"], span["turn_index"])]
                self.assertEqual(turn["content"][span["char_start"]:span["char_end"]], span["text"], packet_id)
                self.assertEqual(turn["role"], span["role"], packet_id)
            for factor in factors.values():
                self.assertTrue(set(factor["span_ids"]).issubset(spans), packet_id)
            for relation in annotation["relations"]:
                refs = set(relation["source_factor_ids"]) | set(relation["target_factor_ids"])
                self.assertTrue(refs and refs.issubset(factors), packet_id)
                self.assertTrue(set(relation["span_ids"]).issubset(spans), packet_id)

    def test_scorer_can_read_prediction_schema(self) -> None:
        # Empty-template gold intentionally makes the values non-evaluative,
        # but this confirms the artifact reaches the Gate A scorer interface.
        packet_id = next(iter(self.gold))
        row = score_packet(self.gold[packet_id], self.pred[packet_id])
        self.assertIn("pred_factors", row)
        self.assertIn("pred_relations", row)


if __name__ == "__main__":
    unittest.main()
