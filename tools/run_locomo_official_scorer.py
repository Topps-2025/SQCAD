"""Official LoCoMo QA scorer, run in place over the frozen upstream file.

Runs under the `longmemeval-py310` venv (numpy/nltk/regex).  The official
`task_eval/evaluation.py` (frozen at D-drive `upstream/benchmarks/LoCoMo`,
CC BY-NC 4.0) imports bert_score at module level but the deterministic
token-F1 path never calls it; we stub the import so the frozen file runs
UNTAMPERED, and record its SHA-256 into the reproduction registry.

Input: prediction files written by `src/sqcad/public_unified_contract.py`
(one JSON per policy: [{"sample_id", "rows": [{question, answer, category,
evidence, prediction, prediction_context}]}]).

Output: results/locomo_official_qa.json with, per policy, the OFFICIAL
`eval_question_answering` numbers (mean token-F1, mean evidence-recall
given the workspace context) and the artifact hashes.

Usage (venv python):
  python tools/run_locomo_official_scorer.py \
      --pred-dir results/locomo_qa --out results/locomo_official_qa.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path

EVAL_FILE = Path("D:/Engineering/SQCAD/database/upstream/benchmarks/LoCoMo/"
                 "task_eval/evaluation.py")


def _stub_bert_score() -> None:
    """The official file imports bert_score (LLM-judge tier, unused by the
    deterministic token-F1 metric).  Stub it so the frozen file loads."""
    stub = types.ModuleType("bert_score")
    stub.score = lambda *a, **k: None
    sys.modules["bert_score"] = stub


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pred-dir", type=Path,
                        default=Path("results/locomo_qa"))
    parser.add_argument("--out", type=Path,
                        default=Path("results/locomo_official_qa.json"))
    args = parser.parse_args()

    if not EVAL_FILE.exists():
        print(f"official evaluation.py missing at {EVAL_FILE}; abort")
        return 1
    _stub_bert_score()
    sys.path.insert(0, str(EVAL_FILE.parent))
    from evaluation import eval_question_answering  # noqa: E402

    report = {
        "official_file": str(EVAL_FILE),
        "official_file_sha256": _sha256(EVAL_FILE),
        "scorer": "task_eval/evaluation.py::eval_question_answering "
                  "(metric='f1', the official deterministic token-F1)",
        "policies": {},
    }
    for pred_file in sorted(args.pred_dir.glob("predictions_*.json")):
        policy = pred_file.stem.removeprefix("predictions_")
        data = json.loads(pred_file.read_text(encoding="utf-8"))
        qas = []
        for block in data:
            for row in block["rows"]:
                qas.append({**row, "sample_id": block["sample_id"]})
        ems, _, recall = eval_question_answering(
            qas, eval_key="prediction", metric="f1")
        report["policies"][policy] = {
            "official_f1_mean": sum(ems) / len(ems) if ems else 0.0,
            "official_recall_mean": sum(recall) / len(recall)
            if recall else 0.0,
            "n_qa": len(ems),
            "predictions_file": str(pred_file),
            "predictions_sha256": _sha256(pred_file),
        }
        entry = report["policies"][policy]
        print(f"{policy:36s} official F1={entry['official_f1_mean']:.4f} "
              f"recall={entry['official_recall_mean']:.4f} (n={len(ems)})")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
