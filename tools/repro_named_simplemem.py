"""SimpleMem open-weight reproduction on the public contract (round-6, 35-).

Official pipeline (SimpleMem-paper-release snapshot) run with the LLM layer
replaced by a local open-weight model (Qwen3-8B served by vLLM at an
OpenAI-compatible endpoint, temperature 0 for reproducibility) and the
embedding layer replaced by Qwen3-Embedding-0.6B (the official repo's own
qwen3 mapping; same model class as the paper's text-embedding layer).
This closes the round-3/4 reviewer item "named-system baselines missing"
for SimpleMem: the row reproduces the official MEMORY MANAGEMENT (windowed
semantic structured compression + planning/reflection hybrid retrieval)
and evaluates it on the frozen contract like every other row.

Reproduction discipline (30- R1 "open-weight substitute protocol"):
  * Official code path untouched: MemoryBuilder + HybridRetriever +
    VectorStore run as-is, configured via config.py (endpoint/model).
    Subclasses only RECORD provenance (entry -> source dialogue ids) --
    no behavior change.
  * Contract evaluation: frozen evaluator for every row (evaluate_trace,
    LoCoMo official F1 via the contract reader).  The workspace of a task
    = the SOURCE MESSAGES of the memory entries retrieved by the official
    retriever (entry-level -> message-level mapping recorded by the
    subclass).  Answer generation stays the contract reader (identical to
    sqcad/bm25 rows) so only the memory-management mechanism differs.
  * Storage = tokens of all compressed memory entries (SimpleMem's
    persistent store: every compressed entry retained, no eviction).
    Lifecycle counters are zero by construction (SimpleMem has no
    archive/restore channel) -- reported honestly.
  * Determinism: temperature forced to 0 (greedy); a single LLM pass is
    reported per the named-system protocol (25- zero-diff discipline
    applies to frozen rows only).
  * LLM usage counted and reported (calls / in chars / out chars).

Usage (cloud, PYTHONPATH=src):
  python tools/repro_named_simplemem.py \
      --longmemeval <cloud-path> --locomo <cloud-path> \
      --simplemem-dir <SimpleMem-paper-release path> \
      --llm-base-url http://localhost:8000/v1 --llm-model qwen3-8b \
      --embedding-model Qwen/Qwen3-Embedding-0.6B \
      --qa-out-dir results/locomo_qa_simplemem \
      --out remote_results/lifecycle_audit/named_simplemem.json \
      [--only longmemeval_s|locomo] [--max-traces N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

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
ROWS = ("simplemem", "sqcad", "bm25")


def _contract_tokens(texts: Sequence[str]) -> int:
    """Token count under the contract tokenizer (same unit as the frozen
    storage-token metric)."""
    return sum(len(TOKEN_RE.findall(t.lower())) for t in texts)

class CountingLLMClient:
    """Wrapper around the official LLMClient: counts calls/chars and forces
    temperature 0 (greedy decoding, reproducibility)."""

    def __init__(self, client) -> None:
        self._c = client
        self.calls = 0
        self.in_chars = 0
        self.out_chars = 0

    def chat_completion(self, messages, temperature=0.2,
                        response_format=None, max_retries=3) -> str:
        self.calls += 1
        self.in_chars += sum(len(m.get("content", "")) for m in messages)
        out = self._c.chat_completion(
            messages, temperature=0, response_format=response_format,
            max_retries=max_retries)
        self.out_chars += len(out)
        return out

    def extract_json(self, text: str):
        return self._c.extract_json(text)


class ContractedMemoryBuilder:
    """Provenance wrapper around the official MemoryBuilder: records
    entry_id -> source dialogue ids for the contract's message-level
    workspace mapping.  Generation logic is entirely the official one."""

    def __init__(self, builder, source_map: Dict[str, List[int]]) -> None:
        self._b = builder
        self._source_map = source_map

    def __getattr__(self, name):
        return getattr(self._b, name)

    def _generate_memory_entries(self, dialogues, dialogue_ids):
        entries = self._b._generate_memory_entries(dialogues, dialogue_ids)
        for e in entries:
            self._source_map[e.entry_id] = list(dialogue_ids)
        return entries

    def add_dialogue(self, dialogue, auto_process=True):
        return self._b.add_dialogue(dialogue, auto_process=auto_process)

    def add_dialogues(self, dialogues, auto_process=True):
        return self._b.add_dialogues(dialogues, auto_process=auto_process)

    def process_remaining(self):
        return self._b.process_remaining()


def run_simplemem_trace(system, source_map, msgs, tasks, d2m, dialogue_cls):
    """Feed a trace into SimpleMem, retrieve per task, map entries back to
    source messages, and return a PolicyResult."""
    dialogues = []
    for i, m in enumerate(msgs, start=1):
        dialogues.append(
            dialogue_cls(dialogue_id=i, speaker=m.role, content=m.content,
                         timestamp=m.date))
        d2m[i] = m.msg_id
    system.memory_builder.add_dialogues(dialogues, auto_process=False)
    system.finalize()

    ws: Dict[str, Tuple[str, ...]] = {}
    for t in tasks:
        entries = system.hybrid_retriever.retrieve(t.question)
        mids: List[str] = []
        for e in entries:
            for d_id in source_map.get(e.entry_id, []):
                mid = d2m.get(d_id)
                if mid is not None and mid not in mids:
                    mids.append(mid)
        ws[t.task_id] = tuple(mids)

    # Persistent store = all compressed entries (restatement + keywords +
    # topic); SimpleMem keeps every entry, so storage = entries' tokens.
    store_texts = [
        e.lossless_restatement + " " + " ".join(e.keywords) + " "
        + (e.topic or "")
        for e in system.get_all_memories()
    ]
    storage_tokens = _contract_tokens(store_texts)
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}
    return PolicyResult(policy="simplemem", workspaces=ws,
                        storage_ids=(), storage_tokens=storage_tokens,
                        lifecycle=lifecycle)


def run_dataset(name: str, data_path: Path, cfg: dict, qa_out: Path | None,
                max_traces: int | None) -> dict:
    traces = (load_longmemeval_s(data_path)
              if name == "longmemeval_s" else load_locomo(data_path))
    if max_traces is not None:
        traces = traces[:max_traces]
    qa_meta = _qa_meta_by_task(name, data_path)

    per: Dict[str, List[dict]] = {r: [] for r in ROWS}
    qa_pairs: List[Tuple[object, PolicyResult]] = []
    llm_usage = {"calls": 0, "in_chars": 0, "out_chars": 0}

    for trace in traces:
        masked, _ = (mask_lme_chronological(trace)
                     if name == "longmemeval_s" else (trace, {}))
        visible_ids = {m.msg_id for m in masked.msgs}
        msgs = list(masked.msgs)
        tasks = needed_free(masked.tasks)
        if not tasks:
            continue

        system = cfg["make_system"]()
        source_map: Dict[str, List[int]] = {}
        system.memory_builder = ContractedMemoryBuilder(
            system.memory_builder, source_map)
        d2m: Dict[int, str] = {}
        res = run_simplemem_trace(system, source_map, msgs, tasks, d2m,
                                  cfg["dialogue_cls"])
        per["simplemem"].append(evaluate_trace(res, masked, visible_ids))
        if name == "locomo" and qa_out is not None:
            qa_pairs.append((trace, res))

        for row in ("sqcad", "bm25"):
            feats = trace_features(masked.msgs)
            r = run_policy(row, masked, feats=feats)
            per[row].append(evaluate_trace(r, masked, visible_ids))
            if name == "locomo" and qa_out is not None:
                qa_pairs.append((trace, r))

        u = cfg["usage"]
        u["calls"] += system.llm_client.calls
        u["in_chars"] += system.llm_client.in_chars
        u["out_chars"] += system.llm_client.out_chars

    if qa_out is not None and qa_pairs:
        write_locomo_qa_files(qa_pairs, qa_meta, qa_out)

    out: dict = {"n_traces": len(per["sqcad"]), "rows": {}, "llm_usage": llm_usage}
    for row, evals in per.items():
        if not evals:
            continue
        out["rows"][row] = {"aggregate": aggregate(row, evals)}
        for m in METRICS:
            out["rows"][row][m] = [e[m] for e in evals if e[m] is not None]
    out["significance_vs_sqcad"] = {}
    for row in ("simplemem",):
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
    ap.add_argument("--simplemem-dir", type=Path, required=True)
    ap.add_argument("--llm-base-url", default="http://localhost:8000/v1")
    ap.add_argument("--llm-model", default="qwen3-8b")
    ap.add_argument("--embedding-model", default="Qwen/Qwen3-Embedding-0.6B")
    ap.add_argument("--qa-out-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", choices=("longmemeval_s", "locomo"), default=None)
    ap.add_argument("--max-traces", type=int, default=None)
    ap.add_argument("--db-dir", type=Path, default=Path("results/simplemem_db"))
    args = ap.parse_args()

    # Import official SimpleMem (needs config.py in the snapshot root);
    # config.py is the pristine example file: attribute edits below are
    # the ONLY configuration (no reload -- that would reset them).
    snapshot = str(args.simplemem_dir.resolve())
    sys.path.insert(0, snapshot)
    import config as sm_config  # noqa: F401  (official modules read it)
    sm_config.OPENAI_API_KEY = "EMPTY"
    sm_config.OPENAI_BASE_URL = args.llm_base_url
    sm_config.LLM_MODEL = args.llm_model
    sm_config.EMBEDDING_MODEL = args.embedding_model
    sm_config.USE_JSON_FORMAT = True

    from models.memory_entry import Dialogue
    from utils.embedding import EmbeddingModel as _RealEmbedding
    _shared_embedding = _RealEmbedding(model_name=args.embedding_model)

    from main import SimpleMemSystem

    _db_dir = args.db_dir
    _db_dir.mkdir(parents=True, exist_ok=True)
    _db_counter = [0]

    def make_system():
        from utils.llm_client import LLMClient
        client = LLMClient()
        wrapped = CountingLLMClient(client)
        _db_counter[0] += 1
        db_path = str(_db_dir / f"mem_{_db_counter[0]:04d}.lance")
        system = SimpleMemSystem(
            api_key="EMPTY", model=args.llm_model, base_url=args.llm_base_url,
            db_path=db_path, table_name="memory_entries", clear_db=True,
            enable_planning=True, enable_reflection=True,
            max_reflection_rounds=2, enable_parallel_processing=False,
            enable_parallel_retrieval=True, max_retrieval_workers=3)
        # route every official LLM call through the counter (single
        # wrapper instance shared by all components)
        for obj in (system.llm_client,
                    system.memory_builder.llm_client,
                    system.hybrid_retriever.llm_client,
                    system.answer_generator.llm_client):
            obj.chat_completion = wrapped.chat_completion
            obj.extract_json = wrapped.extract_json
        system.llm_client = wrapped
        system.hybrid_retriever.llm_client = wrapped
        return system

    usage = {"calls": 0, "in_chars": 0, "out_chars": 0}

    payload: dict = {
        "config": {
            "protocol": ("open-weight substitute reproduction (30- R1); "
                         "official SimpleMem pipeline, LLM layer replaced by "
                         "local Qwen3-8B (temperature 0), embedding = "
                         "Qwen3-Embedding-0.6B; contract evaluator unchanged; "
                         "workspace = source messages of retrieved entries; "
                         "storage = compressed-entry tokens (no eviction; "
                         "lifecycle by construction 0)"),
            "llm_base_url": args.llm_base_url, "llm_model": args.llm_model,
            "embedding_model": args.embedding_model,
            "window_size": getattr(sm_config, "WINDOW_SIZE", 10),
            "overlap_size": getattr(sm_config, "OVERLAP_SIZE", 2),
            "semantic_top_k": getattr(sm_config, "SEMANTIC_TOP_K", 5),
            "keyword_top_k": getattr(sm_config, "KEYWORD_TOP_K", 3),
            "structured_top_k": getattr(sm_config, "STRUCTURED_TOP_K", 10),
            "n_boot": N_BOOT, "alpha": 0.05, "method": "studentized",
            "seeds": list(SEEDS),
            "workspace_budget": BUDGET,
            "note": ("LLM row: single greedy run (temperature 0); "
                     "25- zero-diff discipline applies to frozen rows only"),
        },
        "datasets": {},
    }
    cfg = {"make_system": make_system, "usage": usage,
           "dialogue_cls": Dialogue}
    for name, path in (("longmemeval_s", args.longmemeval),
                       ("locomo", args.locomo)):
        if args.only is not None and name != args.only:
            continue
        qa_out = (args.qa_out_dir / name) if args.qa_out_dir else None
        payload["datasets"][name] = run_dataset(name, path, cfg, qa_out,
                                                args.max_traces)
        print(f"== {name} ==")
        for row, r in payload["datasets"][name]["rows"].items():
            print(f"  {row:10s} {r['aggregate']}")
        u = payload["datasets"][name]["llm_usage"]
        print(f"  llm_usage: {u}")
        for row, sig in payload["datasets"][name]["significance_vs_sqcad"].items():
            for metric, e in sig.items():
                if e.get("mean_diff") is None:
                    continue
                c = e["20260812"]
                flag = "*" if c["significant"] else ""
                print(f"  {row:10s} - sqcad {metric:11s}: "
                      f"{e['mean_diff']:+.4f} [{c['ci_low']:+.4f}, "
                      f"{c['ci_high']:+.4f}]{flag}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
