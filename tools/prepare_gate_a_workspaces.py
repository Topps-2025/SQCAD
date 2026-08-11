"""Create independent answer-blinded pilot workspaces for two annotators."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from build_longmemeval_semantic_gate_a import canonical_json, immutable_projection, sha256_bytes


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("template", type=Path)
    parser.add_argument("parent_manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--annotators", nargs="+", default=["annotator_a", "annotator_b"])
    args = parser.parse_args()

    parent_bytes = args.parent_manifest.read_bytes()
    parent = json.loads(parent_bytes.decode("utf-8"))
    pilot = [packet for packet in read_jsonl(args.template) if packet["split"] == "pilot"]
    if len(pilot) != 40:
        raise ValueError(f"expected 40 pilot packets, found {len(pilot)}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    outputs = []
    for annotator_id in args.annotators:
        packets = []
        for source in pilot:
            packet = copy.deepcopy(source)
            answer_hash = packet["adjudication_only"]["reference_answer_sha256"]
            packet["adjudication_only"] = {
                "reference_answer": None,
                "reference_answer_sha256": answer_hash,
                "warning": "Answer-blinded workspace. Obtain the answer only during adjudication.",
            }
            packet["annotation"]["annotator_id"] = annotator_id
            packet["annotation"]["status"] = "unannotated"
            packets.append(packet)
        raw = b"".join(canonical_json(packet) + b"\n" for packet in packets)
        output = args.output_dir / f"pilot_{annotator_id}.jsonl"
        manifest_path = args.output_dir / f"pilot_{annotator_id}_manifest.json"
        output.write_bytes(raw)
        manifest = {
            "schema_version": parent["schema_version"],
            "purpose": "answer-blinded independent Gate A pilot annotation workspace",
            "annotator_id": annotator_id,
            "blinded": True,
            "parent_manifest": str(args.parent_manifest.resolve()),
            "parent_manifest_sha256": sha256_bytes(parent_bytes),
            "source_data": parent["source_data"],
            "source_sha256": parent["source_sha256"],
            "source_commit": parent["source_commit"],
            "license": parent["license"],
            "packet_count": len(packets),
            "split_counts": dict(Counter(packet["split"] for packet in packets)),
            "question_type_counts": dict(Counter(packet["question_type"] for packet in packets)),
            "evidence_session_count": sum(len(packet["evidence_sessions"]) for packet in packets),
            "evidence_turn_count": sum(
                len(session["turns"])
                for packet in packets
                for session in packet["evidence_sessions"]
            ),
            "annotation_file": str(output.resolve()),
            "annotation_file_sha256": sha256_bytes(raw),
            "packet_identity_sha256": sha256_bytes(canonical_json([immutable_projection(packet) for packet in packets])),
            "warnings": [
                "Do not share one annotator's labels with the other before adjudication.",
                "Reference answers are hidden; source answer hashes remain for identity validation.",
                "The workspace contains evaluation evidence selected by gold session labels and must not train the memory writer.",
            ],
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs.append({"annotator_id": annotator_id, "file": str(output.resolve()), "manifest": str(manifest_path.resolve()), "sha256": sha256_bytes(raw)})
    print(json.dumps({"created": outputs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
