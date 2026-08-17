"""Run the frozen LoCoMo token-F1 scorer with explicit filesystem paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--eval-file", type=Path, required=True)
    p.add_argument("--pred-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    stub = types.ModuleType("bert_score")
    stub.score = lambda *a, **k: None
    sys.modules["bert_score"] = stub
    sys.path.insert(0, str(args.eval_file.parent))
    from evaluation import eval_question_answering

    report = {
        "official_file": str(args.eval_file),
        "official_file_sha256": sha256(args.eval_file),
        "scorer": "frozen task_eval/evaluation.py::eval_question_answering",
        "policies": {},
    }
    for pred in sorted(args.pred_dir.glob("predictions_*.json")):
        blocks = json.loads(pred.read_text(encoding="utf-8"))
        qas = [{**row, "sample_id": block["sample_id"]}
               for block in blocks for row in block["rows"]]
        scores, _, recall = eval_question_answering(
            qas, eval_key="prediction", metric="f1")
        policy = pred.stem.removeprefix("predictions_")
        report["policies"][policy] = {
            "official_f1_mean": sum(scores) / len(scores) if scores else 0.0,
            "official_recall_mean": sum(recall) / len(recall) if recall else 0.0,
            "n_qa": len(scores),
            "predictions_sha256": sha256(pred),
        }
        row = report["policies"][policy]
        print(f"{policy:36s} F1={row['official_f1_mean']:.4f} "
              f"recall={row['official_recall_mean']:.4f} n={row['n_qa']}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
