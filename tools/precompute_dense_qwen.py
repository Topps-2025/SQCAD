"""Qwen3-Embedding dense workspace precompute (33- report, 30- R1 tier-B
open-weight substitute rows).

Same cache format as the frozen tools/precompute_dense.py (doc 17 D1/D2),
evaluated through the identical contract path (--dense-cache of
public_unified_contract.py), but with a Qwen3-Embedding checkpoint as the
retriever instead of all-MiniLM-L6-v2:

  Qwen/Qwen3-Embedding-0.6B  -- SimpleMem-tier substitute (their embedding
                                size class)
  Qwen/Qwen3-Embedding-8B    -- ActMem-tier substitute (their e5-mistral-7b
                                size class)

Honest scope (tier B, never upgraded): these rows reproduce the RETRIEVAL
mechanism of those systems under the unified cost contract (same budget,
same extractive reader, same chronological mask).  The generation-based
stages of the original systems (SimpleMem's LLM compression/rewrite,
ActMem's LLM importance scoring/consolidation) are NOT reproduced; the rows
therefore bound only the retrieval-tier contribution.

Qwen3-Embedding scoring: cosine similarity on normalized embeddings
(default model behavior).  No task-instruction prefix is added, to keep the
row comparable with the frozen MiniLM row (which also has none).

Usage (cloud GPU, PYTHONPATH=src):
  python tools/precompute_dense_qwen.py --dataset longmemeval_s \\
      --model Qwen/Qwen3-Embedding-0.6B --out results/dense_qwen06_lme.json
  python tools/precompute_dense_qwen.py --dataset locomo \\
      --model Qwen/Qwen3-Embedding-8B --out results/dense_qwen8b_locomo.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from sqcad.public_unified_contract import (
    BUDGET, mask_lme_chronological, needed_free,
)
from sqcad.trace_grounded_runner import (
    load_locomo, load_longmemeval_s,
)

MODEL_0_6B = "Qwen/Qwen3-Embedding-0.6B"
MODEL_8B = "Qwen/Qwen3-Embedding-8B"
BATCH = 32
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def embed(texts, tokenizer, model) -> torch.Tensor:
    """Mean-pooled, L2-normalized Qwen3-Embedding vectors (CUDA when
    available).  Same pooling contract as the frozen MiniLM precompute."""
    out = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i:i + BATCH]
        enc = tokenizer(batch, padding=True, truncation=True,
                        max_length=512, return_tensors="pt")
        enc = {k: v.to(DEVICE) for k, v in enc.items()}
        with torch.no_grad():
            hidden = model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            pooled = torch.nn.functional.normalize(pooled, dim=1)
        out.append(pooled.cpu())
    return torch.cat(out, dim=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True,
                        choices=("longmemeval_s", "locomo"))
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--model", default=MODEL_0_6B,
                        choices=(MODEL_0_6B, MODEL_8B))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scores-out", type=Path, default=None,
                        help=("also dump per-query FULL score maps "
                              "{sample_id: {task_id: {msg_id: score}}} "
                              "for the streaming-manager rows "
                              "(tools/streaming_managed_baselines.py)"))
    args = parser.parse_args()

    if args.data is None:
        base = Path("D:/Engineering/SQCAD/database/datasets")
        args.data = (base / "LongMemEval/longmemeval_s_cleaned.json"
                     if args.dataset == "longmemeval_s"
                     else base / "LoCoMo/locomo10.json")

    from transformers import AutoModel, AutoTokenizer  # venv-only dep
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModel.from_pretrained(args.model, torch_dtype=torch.float16)
    model.to(DEVICE)
    model.eval()

    traces = (load_longmemeval_s(args.data)
              if args.dataset == "longmemeval_s" else load_locomo(args.data))

    cache: dict = {}
    scores: dict = {}
    msg_sims: dict = {}
    n_texts = 0
    for trace in traces:
        masked, _ = (mask_lme_chronological(trace)
                     if args.dataset == "longmemeval_s"
                     else (trace, {}))
        msgs = list(masked.msgs)
        tasks = needed_free(masked.tasks)
        if not msgs:
            # Frozen MiniLM row: gpt4_2f56ae70 has zero messages after the
            # chronological mask (all messages post-date the single task);
            # the frozen dense cache records it as an empty candidate list.
            # Mirror that exactly so the Qwen row stays item-comparable.
            out = {t.task_id: [] for t in tasks}
            cache[trace.sample_id] = out
            if args.scores_out is not None:
                scores[trace.sample_id] = {t.task_id: {} for t in tasks}
                msg_sims[trace.sample_id] = {}
            print(f"{trace.sample_id}: 0 msgs, {len(tasks)} tasks "
                  f"(empty -> no candidates)", flush=True)
            continue
        texts = [m.content for m in msgs] + [t.question for t in tasks]
        vecs = embed(texts, tokenizer, model)
        msg_vecs = {msgs[i].msg_id: vecs[i].tolist() for i in range(len(msgs))}
        q_vecs = [vecs[len(msgs) + i] for i in range(len(tasks))]

        msg_mat = torch.tensor(list(msg_vecs.values()), dtype=torch.float32)
        if args.scores_out is not None:
            # online salience: mean cosine of message i to the messages
            # seen so far (strictly chronological, no look-ahead).
            # Iterate the UNIQUE ids (msg_vecs may collapse duplicate
            # msg_ids -- same alignment as the frozen zip semantics).
            sim_mat = msg_mat @ msg_mat.T
            sims = {}
            for j, mid in enumerate(msg_vecs):
                sims[mid] = (0.0 if j == 0
                             else float(sim_mat[j, :j].mean()))
            msg_sims[trace.sample_id] = sims
        out: dict = {}
        out_scores: dict = {}
        for t, qv in zip(tasks, q_vecs):
            scores_ = (msg_mat @ torch.tensor(qv, dtype=torch.float32)).tolist()
            if args.scores_out is not None:
                out_scores[t.task_id] = dict(zip(msg_vecs.keys(), scores_))
            ranked = sorted(zip(msg_vecs.keys(), scores_),
                            key=lambda kv: (-kv[1], kv[0]))
            out[t.task_id] = [mid for mid, _ in ranked[:BUDGET]]
        cache[trace.sample_id] = out
        if args.scores_out is not None:
            scores[trace.sample_id] = out_scores
        n_texts += len(texts)
        print(f"{trace.sample_id}: {len(msgs)} msgs, {len(tasks)} tasks",
              flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"model": args.model, "dataset": args.dataset, "budget": BUDGET,
         "n_texts": n_texts, "cache": cache},
        ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out} ({n_texts} texts embedded)")
    if args.scores_out is not None:
        args.scores_out.parent.mkdir(parents=True, exist_ok=True)
        args.scores_out.write_text(json.dumps(
            {"model": args.model, "dataset": args.dataset, "budget": BUDGET,
             "scores": scores, "msg_sims": msg_sims},
            ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.scores_out} (full score maps + msg_sims)")


if __name__ == "__main__":
    main()
