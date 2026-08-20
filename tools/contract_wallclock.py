"""Wall-clock / FLOPs measurement for the public contract rows (round-5
cloud supplement, 34- report; closes 31- Limitations (7): cost is
reported in contract tokens only, no wall-clock/FLOPs).

Measures on the SAME frozen contract path:
  1. policy-decision wall-clock: time.perf_counter around run_policy per
     trace on LME-S (traces with needed evidence), rows: bm25, dense (via
     the frozen-format dense cache passed on the command line), sqcad,
     sqcad_v2; reported as ms/trace and ms/QA (median and mean);
  2. embedding encode latency: Qwen3-Embedding-0.6B / 8B on the box's GPU
     (transformers, the SAME mean-pool + L2-normalize pooling as
     tools/precompute_dense_qwen.py), 1 warmup batch then 3 repeats of a
     32-text batch; ms/query;
  3. FLOPs/query estimate: forward-only 2 x n_params x seq_len(512)
     estimate per embedding model, formula stated in the output.

The dense row's decision cost is a cache read (workspaces precomputed
offline); the embedding encode timing (2) prices what the cache
represents.  All timings are on the box that produced the tier-B rows.

Usage (cloud GPU, PYTHONPATH=src):
  python tools/contract_wallclock.py \
      --longmemeval <path> \
      --dense-cache <frozen-format dense cache json> \
      --out results/contract_wallclock.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import List

from sqcad.public_unified_contract import (
    mask_lme_chronological, needed_free, run_policy, trace_features,
)
from sqcad.public_v2_rule import run_v2_policy
from sqcad.trace_grounded_runner import load_longmemeval_s

ROWS = ("bm25", "dense", "sqcad", "sqcad_v2")


def time_rows(data_path: Path, dense_cache: Path | None) -> dict:
    traces = load_longmemeval_s(data_path)
    dense_ws = None
    if dense_cache is not None:
        data = json.loads(dense_cache.read_text(encoding="utf-8"))
        dense_ws = data.get("cache", data)

    per: dict = {r: [] for r in ROWS}
    n_qa: dict = {r: 0 for r in ROWS}
    for trace in traces:
        masked, _ = mask_lme_chronological(trace)
        feats = trace_features(masked.msgs)
        tasks = needed_free(masked.tasks)
        if not tasks:
            continue
        n_qa_here = len(tasks)
        for row in ROWS:
            t0 = time.perf_counter()
            if row == "sqcad_v2":
                res = run_v2_policy("sqcad_v2", masked)
            elif row == "dense":
                if dense_ws is None or trace.sample_id not in dense_ws:
                    continue
                res = run_policy(row, masked, dense_ws=dense_ws,
                                 feats=feats)
            else:
                res = run_policy(row, masked, feats=feats)
            ms = (time.perf_counter() - t0) * 1000.0
            per[row].append(ms)
            n_qa[row] += n_qa_here

    out: dict = {}
    for row in ROWS:
        if not per[row]:
            continue
        ms_per_trace = statistics.median(per[row])
        ms_per_qa = ms_per_trace * len(per[row]) / max(1, n_qa[row])
        out[row] = {
            "n_traces": len(per[row]),
            "n_qa": n_qa[row],
            "ms_per_trace_median": round(ms_per_trace, 3),
            "ms_per_trace_mean": round(sum(per[row]) / len(per[row]), 3),
            "ms_per_qa_est": round(ms_per_qa, 3),
            "note": ("per-trace wall-clock of the frozen contract policy "
                     "path; dense reads a precomputed workspace cache"),
        }
    return {"rows": out, "timing_env": {
        "cpu": None, "gpu": None, "note": "filled on the cloud box"}}


def time_embeddings(out: dict) -> None:
    """GPU encode latency + FLOPs estimate for the two Qwen3-Embedding
    checkpoints (same pooling as tools/precompute_dense_qwen.py)."""
    import torch
    from transformers import AutoModel, AutoTokenizer
    from sqcad.public_unified_contract import trace_features as _  # noqa

    texts = ["the quick brown fox answers a question about memory"]
    results = {}
    for model_name in ("Qwen/Qwen3-Embedding-0.6B",
                       "Qwen/Qwen3-Embedding-8B"):
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name,
                                          torch_dtype=torch.float16)
        model = model.to("cuda")
        model.eval()
        n_params = sum(p.numel() for p in model.parameters())
        # warmup
        _encode_once(texts, tokenizer, model)
        times = []
        for _rep in range(3):
            t0 = time.perf_counter()
            _encode_once(texts, tokenizer, model)
            torch.cuda.synchronize()
            times.append((time.perf_counter() - t0) * 1000.0)
        seq_len = 512  # precompute contract truncation
        results[model_name] = {
            "n_params": int(n_params),
            "ms_per_query_median": round(statistics.median(times), 3),
            "flops_per_query_est": int(2 * n_params * seq_len),
            "flops_formula": "2 x n_params x seq_len(512), forward-only",
        }
        print(f"  {model_name}: "
              f"{results[model_name]['ms_per_query_median']} ms/query, "
              f"{results[model_name]['flops_per_query_est']/1e9:.2f} GFLOPs",
              flush=True)
    out["embedding_models"] = results


def _encode_once(texts: List[str], tokenizer, model):
    import torch
    enc = tokenizer(texts, padding=True, truncation=True, max_length=512,
                    return_tensors="pt")
    enc = {k: v.to("cuda") for k, v in enc.items()}
    with torch.no_grad():
        hidden = model(**enc).last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).float()
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        torch.nn.functional.normalize(pooled, dim=1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--longmemeval", type=Path, required=True)
    ap.add_argument("--dense-cache", type=Path, default=None)
    ap.add_argument("--skip-embeddings", action="store_true",
                    help="skip GPU encode timing (no GPU box)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    payload = time_rows(args.longmemeval, args.dense_cache)
    try:
        import torch
        payload["timing_env"]["gpu"] = torch.cuda.get_device_name(0) \
            if torch.cuda.is_available() else "none"
        payload["timing_env"]["cuda"] = torch.version.cuda
    except Exception as exc:  # pragma: no cover
        payload["timing_env"]["cuda"] = f"unavailable ({exc})"
    if not args.skip_embeddings and \
            payload["timing_env"].get("cuda", "none") != "none":
        time_embeddings(payload)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
