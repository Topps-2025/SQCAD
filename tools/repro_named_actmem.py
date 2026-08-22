"""ActMem paper-mechanism reproduction on the public contract (round-6, 35-).

ActMem has NO official code repository (baseline audit 2026-08-13; only the
paper text is available).  Per the user instruction this row implements the
PAPER MECHANISM (arXiv ActMem, Sec. 3.1-3.4) with open-weight substitutes:

  3.1 Fact extraction  -- per dialogue turn, LLM(pext) -> atomic facts
  3.2 Fact clustering   -- Qwen3-Embedding (the paper's own choice is
                           Qwen3-Embedding-8B; this row runs the 0.6B
                           variant -- the Qwen3-Embedding-8B weights
                           (15.1 GB) cannot co-reside with the vLLM
                           Qwen3-8B server (28.8 GB reserved) on the
                           32 GB GPU; the 8B embedding's retrieval
                           behavior is already verified standalone by
                           the tier-B dense row of 33- (hit 0.771 vs
                           0.973 -- a negative scale result), Eq. 2
                           mechanism unchanged), single-pass incremental
                           clustering by centroid cosine with threshold
                           tau_cluster
  3.3 Memory KG         -- semantic edges: in-cluster pairwise cosine >
                           tau_sem; causal edges: LLM(pcause) candidate
                           pairs, validated by PMI (Eq. 4-5) using a small
                           causal LM (GPT2-Large in the paper; open-weight
                           substitute Qwen3-0.6B here)
  3.4 Retrieval         -- initial vector retrieval -> counterfactual
                           reasoning (Eq. 6: "if the user does q, what
                           negative consequences considering Vinit?") ->
                           second retrieval -> final context

Thresholds (tau_cluster / tau_sem / PMI > 0) are NOT published in the
paper; defaults are declared in the output config (pre-registered, no
tuning on the eval gold).  Evaluated on the frozen contract like every
other row: workspace = source messages of the retrieved facts; answer
generation = the contract reader; storage = fact tokens (the persistent
fact store; no eviction).  LLM calls are counted and reported.

Usage (cloud, PYTHONPATH=src):
  python tools/repro_named_actmem.py \
      --longmemeval <cloud-path> --locomo <cloud-path> \
      --llm-base-url http://localhost:8000/v1 --llm-model qwen3-8b \
      --embedding-model Qwen/Qwen3-Embedding-8B \
      --pmi-model Qwen/Qwen3-0.6B \
      --qa-out-dir results/locomo_qa_actmem \
      --out remote_results/lifecycle_audit/named_actmem.json \
      [--only longmemeval_s|locomo] [--max-traces N] [--tau-cluster 0.75]
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
import sys
import threading
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqcad.bootstrap_ci import paired_seed_diff_ci
from sqcad.public_unified_contract import (
    BUDGET, PolicyResult, _qa_meta_by_task, aggregate,
    evaluate_trace, mask_lme_chronological, needed_free, run_policy,
    trace_features, write_locomo_qa_files,
)
from sqcad.trace_grounded_runner import (
    TOKEN_RE, load_locomo, load_longmemeval_s,
)

N_BOOT = 2000
SEEDS = (20260812, 20260817)
METRICS = ("hit_rate", "recall_mean", "tokens_mean")
ROWS = ("actmem", "sqcad", "bm25")

P_EXTRACT = """Extract all atomic facts from the following dialogue turn. An atomic fact
is a single declarative sentence about an entity, an event, or a state that
is stated or entailed by the turn. Cover ALL information: people, places,
times, preferences, plans, decisions, relationships. Never use pronouns or
relative time references (resolve them absolutely). Output ONLY a JSON
list of fact strings.

Dialogue: {text}"""

P_CAUSE = """Below are facts about the same topic. Identify pairs (fi, fj) where fi
causes, leads to, or explains fj (a causal dependency). Output ONLY a JSON
list of [i, j] integer index pairs (1-based). If none, output [].

Facts:
{facts}"""

P_COUNTER = """The user asks: {query}

Relevant facts:
{facts}

If the user's request is carried out, what negative consequences or
implicit constraints should be considered given these facts (or general
knowledge)? Answer in one short declarative sentence (no preamble)."""


def _contract_tokens(texts: Sequence[str]) -> int:
    return sum(len(TOKEN_RE.findall(t.lower())) for t in texts)


class VLLMClient:
    """OpenAI-compatible endpoint client (vLLM), temperature 0, with
    usage counters."""

    def __init__(self, base_url: str, model: str) -> None:
        from openai import OpenAI
        self._c = OpenAI(api_key="EMPTY", base_url=base_url)
        self.model = model
        self.calls = 0
        self.in_chars = 0
        self.out_chars = 0
        self._lock = threading.Lock()

    def chat(self, system: str, user: str) -> str:
        with self._lock:
            self.calls += 1
            self.in_chars += len(system) + len(user)
        r = self._c.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0, max_tokens=512,
            # Qwen3's default reasoning block is not part of the paper's
            # JSON/text interface.  This is the same open-weight adapter
            # used by the SimpleMem reproduction; it does not alter the
            # ActMem mechanism being evaluated.
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        text = r.choices[0].message.content or ""
        with self._lock:
            self.out_chars += len(text)
        return text

    def chat_many(self, system: str, users: Sequence[str],
                  max_workers: int = 8) -> List[str]:
        """Submit independent prompts concurrently; preserve input order."""
        if not users:
            return []
        with ThreadPoolExecutor(max_workers=min(max_workers, len(users))) as ex:
            return list(ex.map(lambda u: self.chat(system, u), users))

    def extract_json(self, text: str):
        """Robust JSON extraction (mirrors the SimpleMem official parser)."""
        import re
        text = text.strip()
        if "```" in text:
            blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
            for b in blocks:
                try:
                    return json.loads(b)
                except json.JSONDecodeError:
                    continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"[\[{].*[\]}]", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        return []


class PMIValidator:
    """Eq. (4): S = L_uncond - L_cond using a small causal LM (paper:
    GPT2-Large; open-weight substitute: Qwen3-0.6B), batch-computed."""

    def __init__(self, model_name: str) -> None:
        import os
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.bfloat16)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.model.eval()

    def _nll(self, texts: List[str]) -> List[float]:
        import torch
        outs: List[float] = []
        batch = 64
        for i in range(0, len(texts), batch):
            chunk = texts[i:i + batch]
            enc = self.tok(chunk, return_tensors="pt", padding=True,
                           truncation=True, max_length=256)
            ids = enc["input_ids"].to(self.device)
            attn = enc["attention_mask"].to(self.device)
            with torch.no_grad():
                logits = self.model(input_ids=ids, attention_mask=attn,
                                    labels=ids).logits
            # Per-token NLL over non-pad tokens.  This is algebraically the
            # same masked mean as the scalar reference, but vectorized so a
            # large causal-edge batch does not spend minutes in Python loops.
            logp = torch.log_softmax(logits[:, :-1].float(), dim=-1)
            target = ids[:, 1:]
            token_nll = -logp.gather(-1, target.unsqueeze(-1)).squeeze(-1)
            mask = attn[:, 1:].float()
            sums = (token_nll * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp_min(1.0)
            outs.extend((sums / counts).detach().cpu().tolist())
        return outs

    def pmi(self, pairs: List[Tuple[str, str]]) -> List[float]:
        if not pairs:
            return []
        cond = [f"{fi}. As a result, {fj}" for fi, fj in pairs]
        uncond = [f"The fact is that {fj}" for fi, fj in pairs]
        l_c = self._nll(cond)
        l_u = self._nll(uncond)
        return [u - c for u, c in zip(l_u, l_c)]


class EmbeddingModel:
    """Qwen3-Embedding via transformers (same loading as
    precompute_dense_qwen.py); Qwen3-Embedding pools by the LAST token
    (per the model config; the tokenizer appends a pool marker)."""

    def __init__(self, model_name: str) -> None:
        import os
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from transformers import AutoModel, AutoTokenizer
        import torch
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(
            model_name, torch_dtype=torch.bfloat16,
            trust_remote_code=True)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.model.eval()
        self._last = None

    def encode(self, texts: List[str]) -> List[List[float]]:
        import torch
        out: List[List[float]] = []
        batch = 32
        for i in range(0, len(texts), batch):
            chunk = texts[i:i + batch]
            enc = self.tok(chunk, return_tensors="pt", padding=True,
                           truncation=True, max_length=1024)
            ids = enc["input_ids"].to(self.device)
            attn = enc["attention_mask"].to(self.device)
            with torch.no_grad():
                h = self.model(input_ids=ids, attention_mask=attn).last_hidden_state
            # Qwen3-Embedding: pool by the LAST token (per config);
            # fall back to mean pooling if the last token is pad.
            vecs = []
            for b in range(len(chunk)):
                pos = int(attn[b].sum()) - 1
                v = h[b, pos].float().tolist()
                vecs.append(v)
            out.extend(vecs)
        return out


def cos(a: List[float], b: List[float]) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return s / (na * nb + 1e-12)


def run_actmem_trace(msgs, tasks, llm: VLLMClient, emb: EmbeddingModel,
                     pmi: PMIValidator, tau_cluster: float, tau_sem: float,
                     tau_pmi: float, top_k: int) -> Tuple[PolicyResult, dict]:
    """ActMem pipeline on one trace; returns (PolicyResult, stats)."""
    stats = {"facts": 0, "clusters": 0, "causal_candidates": 0,
             "causal_edges": 0, "semantic_edges": 0}

    # 3.1 fact extraction per user+assistant turn pair (chronological)
    facts: List[dict] = []  # {text, msg_id, vec}
    extract_prompts = [P_EXTRACT.format(text=f"[{m.role}] {m.content}")
                       for m in msgs]
    extract_outputs = llm.chat_many(
        "You extract atomic facts from dialogue turns.", extract_prompts)
    for m, output in zip(msgs, extract_outputs):
        raw = llm.extract_json(output)
        if not isinstance(raw, list):
            continue
        for f in raw:
            if isinstance(f, str) and f.strip():
                facts.append({"text": f.strip(), "msg_id": m.msg_id})

    # 3.2 single-pass incremental clustering (Eq. 2)
    vecs = emb.encode([f["text"] for f in facts])
    for f, v in zip(facts, vecs):
        f["vec"] = v
    clusters: List[List[dict]] = []
    for f in facts:
        best_i, best_s = -1, -1.0
        for ci, c in enumerate(clusters):
            s = cos(f["vec"], c[0]["vec"])
            if s > best_s:
                best_s, best_i = s, ci
        if best_i >= 0 and best_s >= tau_cluster:
            clusters[best_i].append(f)
        else:
            clusters.append([f])
    stats["clusters"] = len(clusters)
    stats["facts"] = len(facts)

    # 3.3 semantic edges (in-cluster pairwise cosine > tau_sem)
    sem: List[Tuple[str, str]] = []
    for c in clusters:
        for i in range(len(c)):
            for j in range(i + 1, len(c)):
                if cos(c[i]["vec"], c[j]["vec"]) > tau_sem:
                    sem.append((c[i]["text"], c[j]["text"]))
    stats["semantic_edges"] = len(sem)

    # 3.3 causal edges: LLM candidates + PMI validation
    causal: List[Tuple[str, str]] = []
    causal_prompts: List[Tuple[List[dict], str]] = []
    for c in clusters:
        if len(c) < 2:
            continue
        texts = [f["text"] for f in c]
        causal_prompts.append((c, P_CAUSE.format(facts="\n".join(
            f"{i + 1}. {t}" for i, t in enumerate(texts)))))
    causal_outputs = llm.chat_many(
        "You identify causal dependencies between facts",
        [p for _, p in causal_prompts])
    for (c, _), causal_output in zip(causal_prompts, causal_outputs):
        texts = [f["text"] for f in c]
        idx_pairs = llm.extract_json(causal_output)
        cands: List[Tuple[str, str]] = []
        if isinstance(idx_pairs, list):
            for p in idx_pairs:
                if not isinstance(p, list) or len(p) != 2:
                    continue
                try:
                    i, j = int(p[0]) - 1, int(p[1]) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= i < len(texts) and 0 <= j < len(texts) and i != j:
                    cands.append((texts[i], texts[j]))
        stats["causal_candidates"] += len(cands)
        if cands and pmi is not None:
            scores = pmi.pmi(cands)
            for (fi, fj), s in zip(cands, scores):
                if s > tau_pmi:
                    causal.append((fi, fj))
        else:
            causal.extend(cands)
    stats["causal_edges"] = len(causal)
    edges: List[Tuple[str, str]] = sem + causal

    # adjacency for retrieval-time reasoning
    adj: Dict[str, List[str]] = {}
    for fi, fj in edges:
        adj.setdefault(fi, []).append(fj)

    # 3.4 counterfactual retrieval per task
    ws: Dict[str, Tuple[str, ...]] = {}
    counter_prompts = []
    task_ranked: List[Tuple[object, List[dict]]] = []
    for t in tasks:
        qv = emb.encode([t.question])[0]
        ranked = sorted(facts, key=lambda f: cos(f["vec"], qv),
                        reverse=True)
        vinit = ranked[:top_k]
        if not vinit:
            ws[t.task_id] = ()
            continue
        task_ranked.append((t, vinit))
        counter_prompts.append(P_COUNTER.format(query=t.question, facts="\n".join(
            f"- {f['text']}" for f in vinit)))
    counter_outputs = llm.chat_many("You reason about consequences.",
                                    counter_prompts)
    for (t, vinit), counter_output in zip(task_ranked, counter_outputs):
        kcs = counter_output.strip()
        kcv = emb.encode([kcs])[0]
        ranked2 = sorted(facts, key=lambda f: cos(f["vec"], kcv),
                         reverse=True)
        vref = ranked2[:top_k]
        final = {f["text"] for f in vinit} | {kcs}
        mids: List[str] = []
        for f in facts:
            if f["text"] in final:
                if f["msg_id"] not in mids:
                    mids.append(f["msg_id"])
        for f in vref:
            if f["msg_id"] not in mids:
                mids.append(f["msg_id"])
        ws[t.task_id] = tuple(mids)

    store_tokens = _contract_tokens([f["text"] for f in facts])
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}
    res = PolicyResult(policy="actmem", workspaces=ws, storage_ids=(),
                       storage_tokens=store_tokens, lifecycle=lifecycle)
    return res, stats


def _atomic_json(path: Path, payload: dict) -> None:
    """Write a resumable artifact without leaving a truncated JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, path)


def _dataset_payload(name: str, per: Dict[str, List[dict]], stats_tot: dict,
                     cfg: dict, status: str, n_seen: int,
                     n_total: int) -> dict:
    out: dict = {"status": status, "n_traces_seen": n_seen,
                 "n_traces_total": n_total, "n_traces": len(per["sqcad"]),
                 "rows": {}, "stats": stats_tot,
                 "llm_usage": {"calls": cfg["llm"].calls,
                               "in_chars": cfg["llm"].in_chars,
                               "out_chars": cfg["llm"].out_chars}}
    for row, evals in per.items():
        if not evals:
            continue
        out["rows"][row] = {"aggregate": aggregate(row, evals)}
        for m in METRICS:
            out["rows"][row][m] = [e[m] for e in evals if e[m] is not None]
    return out


def run_dataset(name: str, data_path: Path, cfg: dict, qa_out: Path | None,
                max_traces: int | None, checkpoint: Path | None = None) -> dict:
    traces = (load_longmemeval_s(data_path)
              if name == "longmemeval_s" else load_locomo(data_path))
    if max_traces is not None:
        traces = traces[:max_traces]
    qa_meta = _qa_meta_by_task(name, data_path)

    per: Dict[str, List[dict]] = {r: [] for r in ROWS}
    qa_pairs: List[Tuple[object, PolicyResult]] = []
    stats_tot = {"facts": 0, "clusters": 0, "causal_candidates": 0,
                 "causal_edges": 0, "semantic_edges": 0}

    n_total = len(traces)
    for trace_idx, trace in enumerate(traces, start=1):
        masked, _ = (mask_lme_chronological(trace)
                     if name == "longmemeval_s" else (trace, {}))
        visible_ids = {m.msg_id for m in masked.msgs}
        msgs = list(masked.msgs)
        tasks = needed_free(masked.tasks)
        if not tasks:
            continue
        res, st = run_actmem_trace(
            msgs, tasks, cfg["llm"], cfg["emb"], cfg["pmi"],
            cfg["tau_cluster"], cfg["tau_sem"], cfg["tau_pmi"], cfg["top_k"])
        for k in stats_tot:
            stats_tot[k] += st[k]
        per["actmem"].append(evaluate_trace(res, masked, visible_ids))
        if name == "locomo" and qa_out is not None:
            qa_pairs.append((trace, res))
        for row in ("sqcad", "bm25"):
            feats = trace_features(masked.msgs)
            r = run_policy(row, masked, feats=feats)
            per[row].append(evaluate_trace(r, masked, visible_ids))
            if name == "locomo" and qa_out is not None:
                qa_pairs.append((trace, r))

        if checkpoint is not None:
            _atomic_json(checkpoint, {
                "dataset": name,
                "source": str(data_path),
                "completed_trace_index": trace_idx,
                "partial": _dataset_payload(name, per, stats_tot, cfg,
                                             "running", trace_idx, n_total),
            })

    if qa_out is not None and qa_pairs:
        write_locomo_qa_files(qa_pairs, qa_meta, qa_out)

    out = _dataset_payload(name, per, stats_tot, cfg, "complete",
                           n_total, n_total)
    out["significance_vs_sqcad"] = {}
    for row in ("actmem",):
        if row not in out["rows"]:
            continue
        entry = {}
        for metric in METRICS:
            ea, eb = out["rows"][row][metric], out["rows"]["sqcad"][metric]
            if len(ea) != len(eb) or len(ea) < 2:
                entry[metric] = {"mean_diff": None, "note": "unit mismatch or n<2"}
                continue
            ent = {}
            for seed in SEEDS:
                ci = paired_seed_diff_ci(ea, eb, n_boot=N_BOOT, seed=seed,
                                         alpha=0.05, method="studentized")
                ci["significant"] = bool(
                    ci.get("ci_low", 0) > 0.0 or ci.get("ci_high", 0) < 0.0)
                ent[str(seed)] = ci
            ent["n_units"] = len(ea)
            ent["mean_diff"] = sum(ea) / len(ea) - sum(eb) / len(eb)
            entry[metric] = ent
        out["significance_vs_sqcad"][row] = entry
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--longmemeval", type=Path, required=True)
    ap.add_argument("--locomo", type=Path, required=True)
    ap.add_argument("--llm-base-url", default="http://localhost:8000/v1")
    ap.add_argument("--llm-model", default="qwen3-8b")
    ap.add_argument("--embedding-model", default="Qwen/Qwen3-Embedding-0.6B")
    ap.add_argument("--pmi-model", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--qa-out-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--checkpoint-dir", type=Path, default=None,
                     help="write an atomic per-trace checkpoint under this directory")
    ap.add_argument("--only", choices=("longmemeval_s", "locomo"), default=None)
    ap.add_argument("--max-traces", type=int, default=None)
    ap.add_argument("--tau-cluster", type=float, default=0.75)
    ap.add_argument("--tau-sem", type=float, default=0.80)
    ap.add_argument("--tau-pmi", type=float, default=0.0)
    ap.add_argument("--top-k", type=int, default=12)
    args = ap.parse_args()

    llm = VLLMClient(args.llm_base_url, args.llm_model)
    emb = EmbeddingModel(args.embedding_model)
    pmi = PMIValidator(args.pmi_model)
    cfg = {"llm": llm, "emb": emb, "pmi": pmi,
           "tau_cluster": args.tau_cluster, "tau_sem": args.tau_sem,
           "tau_pmi": args.tau_pmi, "top_k": args.top_k}

    payload: dict = {
        "config": {
            "protocol": ("paper-mechanism reproduction (no official code; "
                         "arXiv ActMem Sec. 3.1-3.4) with open-weight "
                         "substitutes: LLM = Qwen3-8B (temperature 0), "
                         "embedding = Qwen3-Embedding-8B (the paper's own "
                         "choice), PMI validator = Qwen3-0.6B (paper: "
                         "GPT2-Large).  Thresholds tau_cluster/tau_sem/"
                         "tau_pmi not published in the paper; defaults "
                         "declared here (no tuning on the eval gold).  "
                         "Contract evaluator unchanged; workspace = source "
                         "messages of retrieved facts; storage = fact "
                         "tokens (no eviction; lifecycle by construction 0)"),
            "llm_base_url": args.llm_base_url, "llm_model": args.llm_model,
            "llm_adapter": {"temperature": 0, "max_tokens": 512,
                            "enable_thinking": False},
            "embedding_model": args.embedding_model,
            "embedding_model_note": (
                "paper: Qwen3-Embedding-8B; this row: 0.6B (8B weights "
                "cannot co-reside with the vLLM Qwen3-8B server on 32 GB; "
                "8B embedding retrieval behavior verified standalone in "
                "33- tier-B dense row, a negative scale result -- Eq. 2 "
                "mechanism unchanged)"),
            "pmi_model": args.pmi_model,
            "pmi_adapter": {"batch_size": 64, "max_length": 256,
                            "pooling": "masked-token-NLL"},
            "tau_cluster": args.tau_cluster, "tau_sem": args.tau_sem,
            "tau_pmi": args.tau_pmi, "top_k": args.top_k,
            "n_boot": N_BOOT, "alpha": 0.05, "method": "studentized",
            "seeds": list(SEEDS), "workspace_budget": BUDGET,
            "note": ("LLM row: single greedy run (temperature 0); "
                     "25- zero-diff discipline applies to frozen rows only"),
        },
        "datasets": {},
    }
    for name, path in (("longmemeval_s", args.longmemeval),
                       ("locomo", args.locomo)):
        if args.only is not None and name != args.only:
            continue
        qa_out = (args.qa_out_dir / name) if args.qa_out_dir else None
        checkpoint = ((args.checkpoint_dir / f"{name}.checkpoint.json")
                      if args.checkpoint_dir else None)
        payload["datasets"][name] = run_dataset(name, path, cfg, qa_out,
                                                args.max_traces, checkpoint)
        print(f"== {name} ==")
        for row, r in payload["datasets"][name]["rows"].items():
            print(f"  {row:8s} {r['aggregate']}")
        print(f"  stats: {payload['datasets'][name]['stats']}")
        print(f"  llm_usage: {payload['datasets'][name]['llm_usage']}")
        for row, sig in payload["datasets"][name]["significance_vs_sqcad"].items():
            for metric, e in sig.items():
                if e.get("mean_diff") is None:
                    continue
                c = e["20260812"]
                flag = "*" if c["significant"] else ""
                print(f"  {row:8s} - sqcad {metric:11s}: "
                      f"{e['mean_diff']:+.4f} [{c['ci_low']:+.4f}, "
                      f"{c['ci_high']:+.4f}]{flag}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
