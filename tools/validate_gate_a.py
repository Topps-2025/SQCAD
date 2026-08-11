"""Validate Gate A packets against the authoritative LongMemEval-S release."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from build_longmemeval_semantic_gate_a import QUOTAS, SCHEMA_VERSION, canonical_json, immutable_projection, sha256_bytes


FACTOR_TYPES = {"entity", "attribute", "condition", "action", "outcome", "preference", "time", "constraint", "tool", "version"}
EVIDENTIAL_STATUSES = {"explicit", "necessary_inference", "hypothesized", "contradicted"}
RELATION_TYPES = {
    "is_a", "has_attribute", "belongs_to", "part_of", "before", "after", "during",
    "valid_from", "expired_at", "updates", "contradicts", "supersedes", "reaffirms",
    "performs", "uses_tool", "produces", "prevents", "enables", "applicable_under",
    "scoped_to", "exception_to", "prefers", "avoids", "indifferent_to", "causal_candidate",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    raw = args.annotations.read_bytes()
    text = raw.decode("utf-8")
    if "\ufffd" in text:
        raise ValueError("annotation file contains U+FFFD")
    packets = [json.loads(line) for line in text.splitlines() if line.strip()]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    source = json.loads(args.data.read_text(encoding="utf-8"))
    source_by_id = {str(item["question_id"]): item for item in source}

    if len(packets) != manifest["packet_count"]:
        raise ValueError(f"expected {manifest['packet_count']} packets, found {len(packets)}")
    if len({packet["packet_id"] for packet in packets}) != len(packets):
        raise ValueError("duplicate packet_id")
    if len({packet["question_id"] for packet in packets}) != len(packets):
        raise ValueError("duplicate question_id")
    if Counter(packet["question_type"] for packet in packets) != Counter(manifest["question_type_counts"]):
        raise ValueError("question-type counts do not match manifest")
    if Counter(packet["split"] for packet in packets) != Counter(manifest["split_counts"]):
        raise ValueError("split counts do not match manifest")

    for packet in packets:
        if packet["schema_version"] != SCHEMA_VERSION:
            raise ValueError(f"schema mismatch: {packet['packet_id']}")
        source_item = source_by_id.get(packet["question_id"])
        if source_item is None or str(source_item["question_id"]).endswith("_abs"):
            raise ValueError(f"invalid source question: {packet['question_id']}")
        if packet["question"] != source_item["question"] or packet["question_type"] != source_item["question_type"]:
            raise ValueError(f"question metadata mismatch: {packet['question_id']}")
        expected_answer_hash = sha256_bytes(str(source_item["answer"]).encode("utf-8"))
        adjudication = packet.get("adjudication_only", {})
        if adjudication.get("reference_answer_sha256") != expected_answer_hash:
            raise ValueError(f"reference-answer hash mismatch: {packet['question_id']}")
        if adjudication.get("reference_answer") is not None and adjudication["reference_answer"] != source_item["answer"]:
            raise ValueError(f"reference answer mismatch: {packet['question_id']}")
        packet_ids = [session["session_id"] for session in packet["evidence_sessions"]]
        if packet_ids != list(source_item["answer_session_ids"]):
            raise ValueError(f"evidence IDs mismatch: {packet['question_id']}")
        source_sessions = dict(zip(source_item["haystack_session_ids"], source_item["haystack_sessions"]))
        for session in packet["evidence_sessions"]:
            turns = source_sessions[session["session_id"]]
            if session["turns"] != turns:
                raise ValueError(f"turn mismatch: {packet['question_id']} / {session['session_id']}")
            if session["content_sha256"] != sha256_bytes(canonical_json(turns)):
                raise ValueError(f"content hash mismatch: {packet['question_id']} / {session['session_id']}")
        annotation = packet["annotation"]
        if annotation["status"] not in {"unannotated", "in_progress", "double_annotated", "adjudicated"}:
            raise ValueError(f"invalid annotation status: {packet['packet_id']}")

        turn_lookup = {
            (session["session_id"], turn_index): turn
            for session in packet["evidence_sessions"]
            for turn_index, turn in enumerate(session["turns"])
        }
        spans = {}
        for span in annotation["evidence_spans"]:
            span_id = span["span_id"]
            if span_id in spans:
                raise ValueError(f"duplicate span_id: {packet['packet_id']} / {span_id}")
            turn = turn_lookup.get((span["session_id"], span["turn_index"]))
            if turn is None:
                raise ValueError(f"invalid span turn pointer: {packet['packet_id']} / {span_id}")
            content = turn["content"]
            start, end = span["char_start"], span["char_end"]
            if not (0 <= start < end <= len(content)) or content[start:end] != span["text"]:
                raise ValueError(f"span text/offset mismatch: {packet['packet_id']} / {span_id}")
            if span["role"] != turn["role"]:
                raise ValueError(f"span role mismatch: {packet['packet_id']} / {span_id}")
            spans[span_id] = span

        factors = {}
        for factor in annotation["factors"]:
            factor_id = factor["factor_id"]
            if factor_id in factors:
                raise ValueError(f"duplicate factor_id: {packet['packet_id']} / {factor_id}")
            if factor["factor_type"] not in FACTOR_TYPES:
                raise ValueError(f"invalid factor type: {packet['packet_id']} / {factor_id}")
            if factor["evidential_status"] not in EVIDENTIAL_STATUSES:
                raise ValueError(f"invalid factor evidential status: {packet['packet_id']} / {factor_id}")
            if not factor["span_ids"] or not set(factor["span_ids"]).issubset(spans):
                raise ValueError(f"invalid factor provenance: {packet['packet_id']} / {factor_id}")
            factors[factor_id] = factor

        relation_ids = set()
        for relation in annotation["relations"]:
            relation_id = relation["relation_id"]
            if relation_id in relation_ids:
                raise ValueError(f"duplicate relation_id: {packet['packet_id']} / {relation_id}")
            relation_ids.add(relation_id)
            if relation["relation_type"] not in RELATION_TYPES:
                raise ValueError(f"invalid relation type: {packet['packet_id']} / {relation_id}")
            if relation["evidential_status"] not in EVIDENTIAL_STATUSES:
                raise ValueError(f"invalid relation evidential status: {packet['packet_id']} / {relation_id}")
            factor_refs = set(relation.get("source_factor_ids", [])) | set(relation.get("target_factor_ids", []))
            if not factor_refs or not factor_refs.issubset(factors):
                raise ValueError(f"invalid relation factor reference: {packet['packet_id']} / {relation_id}")
            if not set(relation["span_ids"]).issubset(spans):
                raise ValueError(f"invalid relation provenance: {packet['packet_id']} / {relation_id}")
            if relation["relation_type"] == "causal_candidate" and not relation.get("causal_validation_required", False):
                raise ValueError(f"causal candidate lacks validation flag: {packet['packet_id']} / {relation_id}")

        rule_ids = set()
        for rule in annotation["abstract_rule_candidates"]:
            rule_id = rule["rule_id"]
            if rule_id in rule_ids:
                raise ValueError(f"duplicate rule_id: {packet['packet_id']} / {rule_id}")
            rule_ids.add(rule_id)
            factor_refs = set(rule["antecedent_factor_ids"]) | set(rule["consequent_factor_ids"])
            if not factor_refs or not factor_refs.issubset(factors):
                raise ValueError(f"invalid rule factor reference: {packet['packet_id']} / {rule_id}")
            if not set(rule["support_span_ids"]).issubset(spans):
                raise ValueError(f"invalid rule provenance: {packet['packet_id']} / {rule_id}")
            if rule["status"] != "candidate" or not rule.get("causal_validation_required", False):
                raise ValueError(f"rule must remain validation-required candidate: {packet['packet_id']} / {rule_id}")

        required = set(annotation["query_required_factor_ids"])
        if not required.issubset(factors):
            raise ValueError(f"invalid query-required factor: {packet['packet_id']}")
        if any(factors[factor_id]["evidential_status"] == "hypothesized" for factor_id in required):
            raise ValueError(f"hypothesized factor cannot be query-required gold: {packet['packet_id']}")
        if annotation["status"] == "unannotated" and any(
            annotation[key] for key in (
                "evidence_spans", "factors", "relations", "abstract_rule_candidates",
                "query_required_factor_ids", "counterexample_checks",
            )
        ):
            raise ValueError(f"unannotated packet contains labels: {packet['packet_id']}")

    identity_hash = sha256_bytes(canonical_json([immutable_projection(packet) for packet in packets]))
    if manifest["packet_identity_sha256"] != identity_hash:
        raise ValueError("immutable packet identity mismatch")
    if all(packet["annotation"]["status"] == "unannotated" for packet in packets):
        if manifest["annotation_file_sha256"] != sha256_bytes(raw):
            raise ValueError("unannotated template hash mismatch")
    if manifest["source_sha256"] != sha256_bytes(args.data.read_bytes()):
        raise ValueError("manifest source hash mismatch")
    if manifest["packet_count"] != len(packets):
        raise ValueError("manifest packet count mismatch")
    result = {
        "valid": True,
        "packet_count": len(packets),
        "split_counts": dict(Counter(packet["split"] for packet in packets)),
        "question_type_counts": dict(Counter(packet["question_type"] for packet in packets)),
        "evidence_session_count": sum(len(packet["evidence_sessions"]) for packet in packets),
        "annotation_sha256": sha256_bytes(raw),
        "packet_identity_sha256": identity_hash,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
