"""Official-code verification of SimpleMem (frozen commit 16912523, MIT).

What runs on this machine (no GPU, no API keys, no model weights):

1. The OFFICIAL LoCoMo data reader (test_locomo10.py) runs UNTAMPERED with
   stubs for the heavyweight imports (sentence_transformers / rouge_score /
   bert_score / tqdm), because the paper's reader path never calls them.
   We cross-check its sample/QA/evidence counts against the unified-contract
   loader (src/sqcad/trace_grounded_runner.load_locomo).
2. The OFFICIAL lexical scoring rule of
   database/vector_store.py::keyword_search (score += 2 for a keyword-list
   hit, += 1 for substring-in-text, top_k=3) is ported VERBATIM onto raw
   dialogue turns -- the LLM compression tier (MemoryBuilder) and the
   embedding tier (Qwen3 weights) are absent and recorded as such.  The
   resulting `simplemem_lexical` row is evaluated under the SAME unified
   contract (same turns, same QA order, same evaluate_trace) so its numbers
   are comparable with the frozen main table.
3. SHA-256 of the official files is recorded for the reproduction registry.

The answer-generation tier (GPT-4.1-mini) and the embedding tier remain
`not reproduced (endpoint/weights blocked)` -- this script NARROWS what
still needs endpoints, per the audit (15-, section 4.5).

Usage (venv python, PYTHONPATH=src):
  python tools/verify_simplemem_official.py \
      --simplemem D:/Engineering/SQCAD/database/upstream/baselines/SimpleMem-paper-release \
      --locomo D:/Engineering/SQCAD/database/datasets/LoCoMo/locomo10.json \
      --out results/simplemem_official_verification.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path

from sqcad.public_unified_contract import (
    PolicyResult, aggregate, evaluate_trace, run_policy, significance,
)
from sqcad.trace_grounded_runner import load_locomo


def _stub_heavy_imports() -> None:
    """The official reader never calls these at parse time; stub them so the
    frozen file loads with its guarded init blocks taking the no-model path
    (exactly what the upstream code does when weights are missing).  The
    LLM/embedding/DB tiers (openai, lancedb, pyarrow, sentence_transformers)
    are imported by the system modules but never exercised by the data
    reader path this script runs."""
    for name in ("sentence_transformers", "sentence_transformers.util",
                 "rouge_score", "bert_score", "tqdm"):
        mod = types.ModuleType(name)
        mod.SentenceTransformer = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("stubbed: no weights on this machine"))
        mod.pytorch_cos_sim = None
        mod.rouge_scorer = types.SimpleNamespace(RougeScorer=None)
        mod.score = None
        mod.tqdm = lambda x, **k: x
        sys.modules[name] = mod
    for name in ("openai", "lancedb", "pyarrow", "config", "dateparser"):
        mod = types.ModuleType(name)
        if name == "openai":
            mod.OpenAI = object
        if name == "pyarrow":
            mod.__version__ = "999.0"
            mod.array = lambda *a, **k: None
            mod.schema = lambda *a, **k: None
        if name == "config":
            mod.EMBEDDING_MODEL = "qwen3-0.6b"
            mod.KEYWORD_TOP_K = 3
            mod.STRUCTURED_TOP_K = 3
            mod.SEMANTIC_TOP_K = 3
        sys.modules[name] = mod


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def official_lexical_scoring(keywords, rows):
    """VERBATIM port of the scoring loop in
    database/vector_store.py::keyword_search (inclusion-based score:
    +2 for a keyword-list hit, +1 for substring in the restatement text).
    `rows` are plain dicts with keys keywords / lossless_restatement
    standing in for the LanceDB table rows."""
    scored = []
    for row in rows:
        score = 0
        row_keywords = list(row["keywords"]) if row["keywords"] is not None \
            else []
        row_text = str(row["lossless_restatement"]).lower()
        for kw in keywords:
            kw_lower = str(kw).lower()
            if len(row_keywords) > 0 and any(
                    kw_lower in str(rk).lower() for rk in row_keywords):
                score += 2
            if kw_lower in row_text:
                score += 1
        if score > 0:
            scored.append((score, row["entry_id"]))
    scored.sort(key=lambda kv: (-kv[0], kv[1]))
    return [mid for _, mid in scored[:3]]  # official KEYWORD_TOP_K = 3


def simplemem_lexical_row(traces, qa_meta):
    """Official-rule lexical row under the unified contract: per QA, score
    every dialogue turn with the official inclusion rule (keywords = the
    query words), top-3 by the official KEYWORD_TOP_K; a turn-level
    transport of the official code's lexical layer with the LLM compression
    tier absent (rows = raw turns, keywords = [])."""
    rows_out = []
    for trace in traces:
        by = {m.msg_id: m for m in trace.msgs}
        workspaces = {}
        for t in trace.tasks:
            keywords = [w for w in t.query_tokens]
            if not keywords:
                workspaces[t.task_id] = ()
                continue
            rows = [{"keywords": [], "lossless_restatement": m.content,
                     "entry_id": m.msg_id} for m in trace.msgs]
            top = official_lexical_scoring(keywords, rows)
            # QA questions reference conversation content; the official
            # layer retrieves at most KEYWORD_TOP_K=3 entries
            workspaces[t.task_id] = tuple(top)
        res = PolicyResult(policy="simplemem_lexical", workspaces=workspaces,
                           storage_ids=tuple(by),
                           storage_tokens=sum(len(m.tokens)
                                              for m in trace.msgs),
                           lifecycle={"archives": 0, "restores": 0,
                                      "probes": 0, "fallbacks": 0})
        visible = {m.msg_id for m in trace.msgs}
        rows_out.append(evaluate_trace(res, trace, visible))
    return rows_out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simplemem", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/"
                                     "upstream/baselines/"
                                     "SimpleMem-paper-release"))
    parser.add_argument("--locomo", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/"
                                     "LoCoMo/locomo10.json"))
    parser.add_argument("--out", type=Path,
                        default=Path("results/"
                                     "simplemem_official_verification.json"))
    args = parser.parse_args()

    reader = args.simplemem / "test_locomo10.py"
    vs = args.simplemem / "database" / "vector_store.py"
    if not reader.exists():
        print(f"official test_locomo10.py missing at {reader}")
        return 1

    # ---- 1. official reader, untampered ----
    _stub_heavy_imports()
    sys.path.insert(0, str(args.simplemem))
    import importlib.util
    spec = importlib.util.spec_from_file_location("simplemem_test_locomo10",
                                                  reader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # guarded init blocks take the no-model path
    samples = mod.load_locomo_dataset(args.locomo)
    n_qa = sum(len(s.qa) for s in samples)

    # ---- 2. cross-check against the unified-contract loader ----
    traces = load_locomo(args.locomo)
    n_ours = sum(len(t.tasks) for t in traces)
    n_evidence_ours = sum(len(task.needed_ids) for t in traces
                          for task in t.tasks)
    n_evidence_official = sum(len(q.evidence) for s in samples
                              for q in s.qa)

    # ---- 3. official-rule lexical row under the unified contract ----
    qa_meta = {f"{s.sample_id}:{i}": {"answer": q.answer,
                                      "category": q.category,
                                      "evidence": q.evidence}
               for s in samples for i, q in enumerate(s.qa)}
    evals = simplemem_lexical_row(traces, qa_meta)

    # ---- 4. paired comparison vs the frozen contract rows (same traces,
    #         same evaluate_trace; n=10 conversation units) ----
    contract_evals: dict = {}
    for pol in ("bm25", "sqcad"):
        rows = []
        for trace in traces:
            res = run_policy(pol, trace)
            visible = {m.msg_id for m in trace.msgs}
            rows.append(evaluate_trace(res, trace, visible))
        contract_evals[pol] = rows
    comparisons = {}
    for metric in ("hit_rate", "recall_mean", "rare_recall",
                   "storage_tokens"):
        comparisons[metric] = significance(
            {"simplemem_lexical": evals, **contract_evals}, metric,
            [("simplemem_lexical", "bm25"),
             ("simplemem_lexical", "sqcad")])

    report = {
        "official_commit": "16912523 (paper release)",
        "official_files": {
            str(reader): _sha256(reader),
            str(vs): _sha256(vs),
        },
        "reader_cross_check": {
            "official_n_samples": len(samples),
            "official_n_qa": n_qa,
            "contract_loader_n_traces": len(traces),
            "contract_loader_n_qa": n_ours,
            "qa_count_match": n_qa == n_ours,
            "official_n_evidence_ids": n_evidence_official,
            "contract_loader_n_needed_ids": n_evidence_ours,
        },
        "simplemem_lexical_row": aggregate("simplemem_lexical", evals),
        "transport_note": "official inclusion-scoring rule (vector_store."
                          "keyword_search, +2 keyword-list / +1 text, "
                          "KEYWORD_TOP_K=3) on raw turns; LLM compression "
                          "tier (MemoryBuilder) and Qwen3 embedding tier "
                          "absent -- not reproduced, endpoint/weights "
                          "blocked",
        "significance_vs_contract": comparisons,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False,
                                         indent=2), encoding="utf-8")
    print("reader cross-check:", report["reader_cross_check"])
    row = report["simplemem_lexical_row"]
    print(f"simplemem_lexical: hit={row['hit_rate']['mean']:.3f} "
          f"recall={row['recall_mean']['mean']:.3f} "
          f"(n_units={row['n_units']})")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
