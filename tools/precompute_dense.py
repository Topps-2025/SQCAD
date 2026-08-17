"""Dense workspace precompute for the public unified contract (doc 17 D1/D2).

Runs under the frozen `longmemeval-py310` venv (torch CPU + transformers):
embeds every visible message of LongMemEval S / LoCoMo with
all-MiniLM-L6-v2 (mean pooling, L2-normalized -- the official LongMemEval
dense variant) and writes, per sample, the per-task top-BUDGET workspaces
that `src/sqcad/public_unified_contract.py` reads via --dense-cache.

The chronological mask is applied here with the same code path as the main
contract runner, so the dense rows obey the identical shared contract.

Usage (venv python, PYTHONPATH=src):
  python tools/precompute_dense.py --dataset longmemeval_s \
      --out results/dense_cache_longmemeval_s.json
  python tools/precompute_dense.py --dataset locomo \
      --out results/dense_cache_locomo.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

from src.sqcad.public_unified_contract import (
    BUDGET, mask_lme_chronological, needed_free,
)
from src.sqcad.trace_grounded_runner import (
    load_locomo, load_longmemeval_s,
)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH = 64
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def embed(texts, tokenizer, model) -> torch.Tensor:
    """Mean-pooled, L2-normalized MiniLM embeddings (CUDA when available)."""
    out = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i:i + BATCH]
        enc = tokenizer(batch, padding=True, truncation=True,
                        max_length=256, return_tensors="pt")
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
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.data is None:
        base = Path("D:/Engineering/SQCAD/database/datasets")
        args.data = (base / "LongMemEval/longmemeval_s_cleaned.json"
                     if args.dataset == "longmemeval_s"
                     else base / "LoCoMo/locomo10.json")

    from transformers import AutoModel, AutoTokenizer  # venv-only dep
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME)
    model.to(DEVICE)
    model.eval()

    traces = (load_longmemeval_s(args.data)
              if args.dataset == "longmemeval_s" else load_locomo(args.data))

    cache: dict = {}
    n_texts = 0
    for trace in traces:
        masked, _ = (mask_lme_chronological(trace)
                     if args.dataset == "longmemeval_s"
                     else (trace, {}))
        msgs = list(masked.msgs)
        tasks = needed_free(masked.tasks)
        texts = [m.content for m in msgs] + [t.question for t in tasks]
        vecs = embed(texts, tokenizer, model)
        msg_vecs = {msgs[i].msg_id: vecs[i].tolist() for i in range(len(msgs))}
        q_vecs = [vecs[len(msgs) + i] for i in range(len(tasks))]

        msg_mat = torch.tensor(list(msg_vecs.values()), dtype=torch.float32)
        out: dict = {}
        for t, qv in zip(tasks, q_vecs):
            scores = (msg_mat @ torch.tensor(qv, dtype=torch.float32)).tolist()
            ranked = sorted(zip(msg_vecs.keys(), scores),
                            key=lambda kv: (-kv[1], kv[0]))
            out[t.task_id] = [mid for mid, _ in ranked[:BUDGET]]
        cache[trace.sample_id] = out
        n_texts += len(texts)
        print(f"{trace.sample_id}: {len(msgs)} msgs, {len(tasks)} tasks",
              flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"model": MODEL_NAME, "dataset": args.dataset, "budget": BUDGET,
         "n_texts": n_texts, "cache": cache},
        ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out} ({n_texts} texts embedded)")


if __name__ == "__main__":
    main()
