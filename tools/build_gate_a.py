"""Build the LongMemEval-S semantic-decomposition Gate A annotation set.

The output is evaluation-only.  Gold answer-session IDs are used solely to
select evidence packets for human annotation; they must not be exposed to a
query-independent memory writer or used to train the proposed method.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List


QUOTAS = {
    "multi-session": 70,
    "temporal-reasoning": 50,
    "knowledge-update": 50,
    "single-session-preference": 30,
}
PILOT_PER_TYPE = 10
SEED = "semantic-gate-a-20260803-v1"
SCHEMA_VERSION = "longmemeval-semantic-gate-a.v1"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def deterministic_key(question_type: str, question_id: str) -> str:
    return hashlib.sha256(f"{SEED}:{question_type}:{question_id}".encode("utf-8")).hexdigest()


def immutable_projection(packet: Dict[str, object]) -> Dict[str, object]:
    """Return packet content that annotators are never allowed to modify."""
    projection = {
        key: value for key, value in packet.items()
        if key not in {"annotation", "adjudication_only"}
    }
    adjudication = packet.get("adjudication_only", {})
    reference_hash = adjudication.get("reference_answer_sha256")
    if reference_hash is None and adjudication.get("reference_answer") is not None:
        reference_hash = sha256_bytes(str(adjudication["reference_answer"]).encode("utf-8"))
    projection["reference_answer_sha256"] = reference_hash
    return projection


def build_packet(item: Dict[str, object], split: str) -> Dict[str, object]:
    session_lookup = {
        session_id: {"date": date, "turns": session}
        for session_id, date, session in zip(
            item["haystack_session_ids"], item["haystack_dates"], item["haystack_sessions"]
        )
    }
    evidence_sessions: List[Dict[str, object]] = []
    for session_id in item["answer_session_ids"]:
        source = session_lookup[session_id]
        turns = source["turns"]
        evidence_sessions.append(
            {
                "session_id": session_id,
                "date": source["date"],
                "turns": turns,
                "content_sha256": sha256_bytes(canonical_json(turns)),
            }
        )
    question_id = str(item["question_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "packet_id": f"gatea_{question_id}",
        "split": split,
        "question_id": question_id,
        "question_type": item["question_type"],
        "question": item["question"],
        "question_date": item["question_date"],
        "evidence_sessions": evidence_sessions,
        "adjudication_only": {
            "reference_answer": item["answer"],
            "reference_answer_sha256": sha256_bytes(str(item["answer"]).encode("utf-8")),
            "warning": "Hide this field during the independent first-pass annotation.",
        },
        "annotation": {
            "status": "unannotated",
            "annotator_id": None,
            "evidence_spans": [],
            "factors": [],
            "relations": [],
            "abstract_rule_candidates": [],
            "query_required_factor_ids": [],
            "counterexample_checks": [],
            "notes": None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    data_bytes = args.data.read_bytes()
    data = json.loads(data_bytes.decode("utf-8"))
    eligible = [
        item for item in data
        if not str(item.get("question_id", "")).endswith("_abs") and item.get("answer_session_ids")
    ]
    by_type: Dict[str, List[Dict[str, object]]] = {}
    for question_type, quota in QUOTAS.items():
        candidates = [item for item in eligible if item["question_type"] == question_type]
        candidates.sort(key=lambda item: deterministic_key(question_type, str(item["question_id"])))
        if len(candidates) < quota:
            raise ValueError(f"insufficient {question_type}: need {quota}, found {len(candidates)}")
        by_type[question_type] = candidates[:quota]

    packets = []
    for question_type in QUOTAS:
        for index, item in enumerate(by_type[question_type]):
            split = "pilot" if index < PILOT_PER_TYPE else "main"
            packets.append(build_packet(item, split))
    packets.sort(key=lambda packet: (packet["split"], packet["question_type"], packet["packet_id"]))

    jsonl = b"".join(canonical_json(packet) + b"\n" for packet in packets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(jsonl)

    split_counts = Counter(packet["split"] for packet in packets)
    type_counts = Counter(packet["question_type"] for packet in packets)
    evidence_session_count = sum(len(packet["evidence_sessions"]) for packet in packets)
    evidence_turn_count = sum(
        len(session["turns"])
        for packet in packets
        for session in packet["evidence_sessions"]
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "evaluation-only semantic decomposition Gate A; not a causal-effect gold set",
        "source_data": str(args.data.resolve()),
        "source_sha256": sha256_bytes(data_bytes),
        "source_commit": "9e0b455f4ef0e2ab8f2e582289761153549043fc",
        "license": "MIT (upstream LongMemEval repository); verify redistribution obligations before release",
        "selection_seed": SEED,
        "selection": "deterministic SHA-256 ranking within question type",
        "quotas": QUOTAS,
        "pilot_per_type": PILOT_PER_TYPE,
        "packet_count": len(packets),
        "split_counts": dict(split_counts),
        "question_type_counts": dict(type_counts),
        "evidence_session_count": evidence_session_count,
        "evidence_turn_count": evidence_turn_count,
        "annotation_file": str(args.output.resolve()),
        "annotation_file_sha256": sha256_bytes(jsonl),
        "packet_identity_sha256": sha256_bytes(canonical_json([immutable_projection(packet) for packet in packets])),
        "warnings": [
            "Gold answer-session IDs select evaluation packets and must not enter the memory writer.",
            "Reference answers are adjudication-only and should be hidden during first-pass annotation.",
            "Factors and rules are task-relevant semantic annotations, not verified causal effects.",
        ],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
