"""Public-data unified contract (doc 17, D1/D2): chronological future split,
shared candidate stream / budget / evaluator, R1 controls + R2 structural
controls + the SQCAD dynamic lifecycle row, evaluated on LongMemEval S and
LoCoMo.

Contract rules (pre-registered, NOT tuned on the eval gold):

1. Chronology.  No policy may see anything that happens after the task it
   answers.  LongMemEval S samples carry session dates and a question_date:
   sessions dated after the question are masked for EVERY policy; needed
   sessions that fall behind the mask are reported as
   `n_masked_needed` and excluded from the recall denominator.  LoCoMo has
   no per-question timestamps (the official protocol asks all QA after the
   conversation), so the whole conversation is the past; policies process
   turns in order and QAs in the frozen dataset order.

2. Budget.  Every policy exposes at most BUDGET (12) items per task, except
   keep_all (the no-governance control, priced at full token cost).  The
   gold `needed_ids` never enter a policy: policies receive tasks with
   needed_ids stripped; the evaluator holds the gold.

3. Evaluator.  Objective metrics computed from the benchmark's own ground
   truth (answer_session_ids / evidence dia_ids): task hit rate, memory-level
   recall fraction, stratification by question type / LoCoMo category,
   temporal-consistency recall (knowledge-update subset), rare-positive
   recall, storage tokens, exposure tokens, and lifecycle counts.

4. Costs.  Persistent policies pay storage = tokens of retained items plus
   probe/restore actions; retrieval policies (bm25/dense/rrf) pay the
   index-everything storage cost (all stream tokens); keep_all pays the
   full-context exposure cost per task.

5. Significance.  Paired bootstrap over samples (LME: 500 samples; LoCoMo:
   10 conversations), studentized, n_boot=2000, seed=20260812 (Gate 5
   conventions).  A metric where the sqcad-vs-baseline paired CI excludes 0
   is "significant" under this pre-registered rule; everything is reported,
   including zeros and deficits.

SQCAD row (observable signals only, gold never read):

- Evidence: per-turn features -- recency, session frequency, version
  conflict (a later turn in a DIFFERENT session sharing >=3 content tokens),
  rare-session protection (session in the bottom quartile of session sizes),
  lineage (derived = turn sharing >=3 tokens with an earlier source turn in
  a different session).
- Qualification: conflicted (a newer version exists) -> unresolved while the
  updater is retained; the version PAIR cannot be split by eviction (no
  commitment on unresolved); orphan (source archived, derived retained) ->
  unresolved with a lineage note.
- Access: write-time keep/archive by score = recency-decay * log1p(freq)
  + conflict retention bonus + rare floor; QA-time ranking of the retained
  set by BM25 with negative attenuation for conflicted items; paid probe
  channel (archived items sharing >=3 content tokens with the query -- the
  module's established lexical-evidence threshold -- 1 probe per task);
  cost-aware restore (probed item re-admitted permanently iff its query
  overlap beats the weakest retained overlap; fixed_restore skips the
  comparison); conservative fallback (fill a short workspace from the
  archive; disabled by the fallback ablation).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .bootstrap_ci import paired_seed_diff_ci
from .trace_grounded_runner import (
    Trace, TraceMsg, TraceTask, bm25_scores, clean_tokens,
    load_locomo, load_longmemeval_s,
)

# ---------------------------------------------------------------------------
# pre-registered constants (no tuning on the eval gold)
# ---------------------------------------------------------------------------

BUDGET = 12                 # shared workspace budget (established contract)
HALF_LIFE = 60.0            # decay half-life (established decay engine)
CONFLICT_OVERLAP = 3        # version-conflict token overlap (audit detector)
CONFLICT_BONUS = 0.15       # conservative retention bonus for conflicted items
ATTENUATION = 0.8           # QA-time downweight of conflicted items
RARE_FLOOR = 0.05           # score floor for rare-session items
PROBE_BUDGET_PER_TASK = 1   # paid probe channel capacity
CANDIDATE_GUARD_BUDGET = 4  # one-shot proposal/coverage guard capacity
N_BOOT = 2000
BOOT_SEED = 20260812        # Gate 5 pre-registered bootstrap seed
ALPHA = 0.05

R1_POLICIES = (
    "no_memory", "keep_all", "fifo", "lru", "recency", "fixed_decay",
    "frequency_decay", "bm25", "bm25_answerability",
    "bm25_answerability_structured",
    "bm25_answerability_abstain", "dense", "rrf",
)
R2_POLICIES = ("association_only", "memory_worth", "causal_item",
               "bundle_control", "risk_gated_decomp_abstract")
SQCAD_ABLATIONS = (
    "sqcad_no_qualification", "sqcad_no_version_gate",
    "sqcad_no_silence_semantics", "sqcad_no_restore", "sqcad_no_probe",
    "sqcad_fixed_restore", "sqcad_no_lineage", "sqcad_item_only",
    "sqcad_no_positive_protection", "sqcad_no_negative_attenuation",
    "sqcad_no_fallback",
)
SQCAD_VARIANTS = (
    "sqcad_candidate_guard_1", "sqcad_candidate_guard_2",
    "sqcad_candidate_guard_4", "sqcad_candidate_guard_8",
    "sqcad_candidate_guard_16", "sqcad_candidate_guard_full",
    "sqcad_candidate_guard_adaptive", "sqcad_dense_guard_4",
    "sqcad_hybrid_guard_4", "sqcad_hybrid_guard_4_reserve_1",
    "sqcad_denoise_guard_4", "sqcad_denoise_guard_8",
    "sqcad_denoise_guard_16", "sqcad_denoise_compact_guard_4",
    "sqcad_denoise_compact_guard_16",
    "sqcad_denoise_compact1k_guard_16",
    "sqcad_denoise_compact280_guard_16",
    "sqcad_denoise_compact300_guard_16",
    "sqcad_denoise_guard_full",
    "sqcad_denoise_guard_32",
    "sqcad_denoise_nosmooth_guard_16", "sqcad_denoise_nodiverse_guard_16",
    "sqcad_fir_denoise_guard_16",
    "sqcad_fir_denoise_abstain_16",
    "sqcad_fir_denoise_expand_16",
    "sqcad_fir_structured_16",
    "sqcad_fir_structured_overlap_16",
    "sqcad_fir_structured_compact_1536",
    "sqcad_fir_structured_compact_1280",
    "sqcad_fir_denoise_guard_full",
    "sqcad_fir_denoise_overlap_16",
    "sqcad_fir_denoise_reader_v2_16",
    "sqcad_denoise_adaptive",
)
NAMED_BASELINE_POLICIES = (
    "simplemem_rc", "actmem_rc", "oblivion_rd", "memoryworth_rw",
    "trivium_rd", "govmem_rg",
)
ALL_POLICIES = (R1_POLICIES + R2_POLICIES + ("sqcad",)
                + SQCAD_ABLATIONS + SQCAD_VARIANTS + NAMED_BASELINE_POLICIES)

NAMED_BASELINE_ALIASES = {
    "simplemem_rc": "bm25",
    "actmem_rc": "dense",
    "oblivion_rd": "fixed_decay",
    "memoryworth_rw": "frequency_decay",
    "trivium_rd": "association_only",
    "govmem_rg": "risk_gated_decomp_abstract",
}

SENT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class PolicySpec:
    label: str
    group: str
    rule: str
    transportability: str
    transport_note: str


POLICY_SPECS: Dict[str, PolicySpec] = {
    "no_memory": PolicySpec("No-memory", "1-simple-controls",
                            "no persistent memory; nothing is exposed",
                            "transportable", "trivial control"),
    "keep_all": PolicySpec("Keep-all (no governance)", "1-simple-controls",
                           "everything retained and exposed; no forgetting",
                           "transportable",
                           "exceeds the budget BY DESIGN and is priced at "
                           "full token cost (the no-governance control)"),
    "fifo": PolicySpec("FIFO", "1-simple-controls",
                       "first-written memories evicted first",
                       "transportable",
                       "first BUDGET messages of the visible stream"),
    "lru": PolicySpec("LRU", "1-simple-controls",
                      "least-recently-accessed evicted first",
                      "transportable",
                      "access events = QA exposure events in frozen QA order"),
    "recency": PolicySpec("Recency", "1-simple-controls",
                          "most recent memories first",
                          "transportable", "static top-BUDGET by date_idx"),
    "fixed_decay": PolicySpec("Fixed exponential decay", "1-simple-controls",
                              "exp(-age/half_life) without refresh",
                              "transportable",
                              "half_life=60 (established decay engine)"),
    "frequency_decay": PolicySpec("Frequency decay", "1-simple-controls",
                                  "log1p(freq) * exp(-age/50)",
                                  "transportable",
                                  "freq = session turn count (observable)"),
    "bm25": PolicySpec("BM25 retrieval", "1-simple-controls",
                       "query-time BM25 top-BUDGET over the full visible "
                       "stream (the official LongMemEval retrieval protocol)",
                       "transportable",
                       "K1=1.5, B=0.75 (official); storage cost = index-"
                       "everything"),
    "bm25_answerability": PolicySpec(
        "BM25 retrieval (shared answerability readout)", "1-simple-controls",
        "query-time BM25 top-BUDGET with the same observable sentence readout "
        "used by the SQCAD main row",
        "transportable", "fair reader-matched control; index-everything storage"),
    "bm25_answerability_structured": PolicySpec(
        "BM25 retrieval (structured answerability readout)", "1-simple-controls",
        "query-time BM25 top-BUDGET with question-echo suppression and the "
        "same structured readout used by the SQCAD structured variant",
        "transportable", "fair reader-matched control; index-everything storage"),
    "bm25_answerability_abstain": PolicySpec(
        "BM25 retrieval (answerability + abstention)", "1-simple-controls",
        "BM25 with the shared answerability readout and zero-signal abstention",
        "transportable", "fair reader-matched abstention control"),
    "dense": PolicySpec("Dense retrieval (MiniLM)", "1-simple-controls",
                        "query-time all-MiniLM-L6-v2 cosine top-BUDGET",
                        "transportable",
                        "CPU embeddings; requires the frozen dense cache "
                        "(tools/precompute_dense.py); skipped otherwise"),
    "rrf": PolicySpec("BM25+dense RRF", "1-simple-controls",
                      "reciprocal rank fusion of BM25 and dense",
                      "transportable", "needs the dense cache; skipped "
                                       "otherwise"),
    "association_only": PolicySpec("Association-only", "2-structural",
                                   "historical association score "
                                   "(recency x frequency)",
                                   "transportable (control)",
                                   "the association estimand Memory Worth "
                                   "etc. estimate; no lifecycle awareness"),
    "memory_worth": PolicySpec("Memory Worth proxy", "2-structural",
                               "MW(m)=hits+/(hits++hits-) with the paper's "
                               "success signal substituted by an observable "
                               "query-overlap event (>=3 tokens)",
                               "proxy",
                               "the paper's success signal is unobservable "
                               "on public data; signal substituted, "
                               "labeled proxy"),
    "causal_item": PolicySpec("CMI proxy", "2-structural",
                              "query-local observational exposure contrast "
                              "(naive OPE) on the query-overlap value signal",
                              "proxy",
                              "query-local do-effect transport, gold-free "
                              "signal; Theorem 2 shows the estimand is "
                              "insufficient for lifecycle decisions"),
    "bundle_control": PolicySpec("Bundle (session-level) control",
                                 "2-structural",
                                 "session-level actions: session score = mean "
                                 "item score; whole sessions kept",
                                 "transportable", "bundle control row"),
    "risk_gated_decomp_abstract": PolicySpec(
        "SQCAD proxy (controlled)", "framework",
        "static transport of the smoke-runner gated score: conflict gate "
        "substitutes for the semantic-confidence/harm-veto signals that "
        "public data does not carry",
        "proxy",
        "doc 17 5.2: the FULL row must be the dynamic lifecycle runner; "
        "this row is the controlled proxy"),
    "sqcad": PolicySpec("SQCAD (dynamic lifecycle)", "framework",
                        "Evidence-Qualification-Access: observable version/"
                        "rare/lineage evidence, unresolved-pair conservative "
                        "eviction, paid probe/restore, attenuated QA ranking",
                        "transportable",
                        "this paper's framework on public traces"),
    **{
        name: PolicySpec(
            f"SQCAD + candidate coverage guard ({budget})",
            "framework-variant",
            "SQCAD plus bounded one-shot BM25 candidate probes before access; "
            "proposals do not authorize persistent writes",
            "transportable",
            f"{budget} candidate proposals per QA; persistent authorization "
            "unchanged")
        for name, budget in (
            ("sqcad_candidate_guard_1", 1),
            ("sqcad_candidate_guard_2", 2),
            ("sqcad_candidate_guard_4", 4),
            ("sqcad_candidate_guard_8", 8),
            ("sqcad_candidate_guard_16", 16),
            ("sqcad_candidate_guard_full", 10**9),
        )
    },
    "sqcad_candidate_guard_adaptive": PolicySpec(
        "SQCAD + adaptive candidate coverage guard",
        "framework-variant",
        "observable retained/archive BM25 margin selects 2, 8, or 16 "
        "one-shot candidate proposals; no persistent authorization",
        "transportable",
        "pre-registered adaptive budget: 2 when retained evidence is at "
        "least as strong, 8 when archive evidence is stronger, and 16 "
        "when retained evidence is absent but archive evidence is positive"),
    "sqcad_candidate_guard": PolicySpec(
        "SQCAD + candidate coverage guard (4; legacy alias)",
        "framework-variant",
        "Compatibility alias for sqcad_candidate_guard_4",
        "transportable",
        "legacy name; equivalent to four candidate proposals per QA"),
    "sqcad_dense_guard_4": PolicySpec(
        "SQCAD + dense candidate guard (4)", "framework-variant",
        "SQCAD plus four one-shot candidates from a frozen dense cache; "
        "persistent authorization unchanged",
        "transportable", "Qwen3-Embedding cache is an open-weight retrieval "
        "substitute; no generation/compression stage"),
    "sqcad_hybrid_guard_4": PolicySpec(
        "SQCAD + hybrid lexical+dense candidate guard (4)",
        "framework-variant",
        "SQCAD plus four one-shot candidates from reciprocal-rank union of "
        "observable BM25 and dense candidates; persistent authorization "
        "unchanged",
        "transportable", "Qwen3-Embedding cache is an open-weight retrieval "
        "substitute; no generation/compression stage"),
    "sqcad_hybrid_guard_4_reserve_1": PolicySpec(
        "SQCAD + hybrid guard-4 + one candidate reserve", "framework-variant",
        "SQCAD plus four RRF candidate proposals and one reserved workspace "
        "slot for the highest-ranked proposal; persistent authorization "
        "unchanged",
        "transportable", "pre-registered rerank/workspace intervention; "
        "Qwen3-Embedding cache is an open-weight retrieval substitute"),
    "sqcad_denoise_guard_4": PolicySpec(
        "SQCAD + denoising guard-4", "framework-variant",
        "SQCAD plus query-signal smoothing and redundancy-suppressed "
        "candidate ranking; proposals do not authorize persistent writes",
        "transportable", "fixed DSP-inspired smoothing and MMR-style "
        "evidence diversity; no evaluator gold or learned parameters"),
    "sqcad_denoise_guard_8": PolicySpec(
        "SQCAD + denoising guard-8", "framework-variant",
        "SQCAD plus eight denoised candidate proposals with redundancy "
        "suppression; proposals do not authorize persistent writes",
        "transportable", "same fixed query-time denoiser with a larger "
        "candidate budget"),
    "sqcad_denoise_guard_16": PolicySpec(
        "SQCAD + denoising guard-16", "framework-variant",
        "SQCAD plus sixteen denoised candidate proposals with redundancy "
        "suppression; proposals do not authorize persistent writes",
        "transportable", "same fixed query-time denoiser with a larger "
        "candidate budget"),
    "sqcad_denoise_guard_full": PolicySpec(
        "SQCAD + full-candidate denoising guard", "framework-variant",
        "All observable candidates are proposed, then ranked by graph "
        "denoising and redundancy suppression; no persistent authorization",
        "transportable", "diagnostic coverage upper bound; probe cost is "
        "reported and not treated as free"),
    "sqcad_denoise_guard_32": PolicySpec(
        "SQCAD + denoising guard-32", "framework-variant",
        "SQCAD plus thirty-two denoised candidate proposals with "
        "redundancy suppression",
        "transportable", "fixed candidate budget; probe cost is reported"),
    "sqcad_denoise_nosmooth_guard_16": PolicySpec(
        "SQCAD + denoising (no graph smoothing)", "framework-ablation",
        "Diversity-only ranking with graph low-pass disabled",
        "transportable", "isolates the consensus low-pass contribution"),
    "sqcad_denoise_nodiverse_guard_16": PolicySpec(
        "SQCAD + denoising (no diversity penalty)", "framework-ablation",
        "Graph-smoothed ranking with redundancy suppression disabled",
        "transportable", "isolates the MMR evidence-diversity contribution"),
    "sqcad_fir_denoise_guard_16": PolicySpec(
        "SQCAD + temporal FIR denoising guard-16", "framework-variant",
        "Fixed three-tap temporal low-pass filter, answerability readout, "
        "and redundancy suppression; proposals do not authorize persistent writes",
        "transportable", "kernel [0.25, 0.50, 0.25] and IDF/type-aware readout "
        "are fixed before evaluation"),
    "sqcad_fir_denoise_guard_full": PolicySpec(
        "SQCAD + FIR + answerability (full candidate diagnostic)",
        "framework-variant",
        "Full observable candidate guard followed by the main FIR and "
        "answerability readout; persistent authorization unchanged",
        "transportable", "coverage upper bound; proposal/probe cost is reported"),
    "sqcad_fir_denoise_expand_16": PolicySpec(
        "SQCAD + FIR + adjacent evidence expansion (16)",
        "framework-variant",
        "Hybrid seeds plus a bounded same-session temporal-neighborhood "
        "proposal before FIR denoising; persistent authorization unchanged",
        "transportable", "radius-one adjacency is structural and gold-free; "
        "proposal cost is reported"),
    "sqcad_fir_structured_16": PolicySpec(
        "SQCAD + structured response-prior FIR (16)", "framework-variant",
        "Hybrid candidate guard augmented with observable next-turn response "
        "edges, followed by FIR, MMR and structured answerability readout",
        "transportable", "response edges use only session order, punctuation, "
        "and visible text; no evaluator gold or answer fields"),
    "sqcad_fir_structured_overlap_16": PolicySpec(
        "SQCAD + structured response-prior FIR (overlap readout)",
        "framework-ablation",
        "The structured response-prior access layer with the original "
        "overlap-only reader", "transportable",
        "isolates candidate recovery from structured readout"),
    "sqcad_fir_structured_compact_1536": PolicySpec(
        "SQCAD + structured response-prior FIR (1536-token cap)",
        "framework-variant",
        "Structured response-prior FIR with a fixed query-time exposure cap",
        "transportable",
        "cap is applied only to exposed workspace/context; persistent storage "
        "and candidate proposals are unchanged"),
    "sqcad_fir_structured_compact_1280": PolicySpec(
        "SQCAD + structured response-prior FIR (1280-token cap)",
        "framework-variant",
        "Structured response-prior FIR with a stricter fixed query-time exposure cap",
        "transportable",
        "cap is applied only to exposed workspace/context; persistent storage "
        "and candidate proposals are unchanged"),
    "sqcad_fir_denoise_overlap_16": PolicySpec(
        "SQCAD + temporal FIR (overlap readout)", "framework-ablation",
        "FIR access with the original overlap-only sentence reader",
        "transportable", "readout ablation; persistent authorization unchanged"),
    "sqcad_fir_denoise_reader_v2_16": PolicySpec(
        "SQCAD + temporal FIR + answerability readout", "framework-variant",
        "FIR-denoised access followed by observable IDF/type-aware sentence "
        "readout; persistent authorization is unchanged",
        "transportable", "readout uses query terms and explicit temporal/count "
        "forms only; no evaluator gold or learned parameters"),
    "sqcad_denoise_adaptive": PolicySpec(
        "SQCAD + adaptive denoising guard", "framework-variant",
        "Adaptive 2/8/16 candidate guard followed by graph denoising and "
        "redundancy suppression",
        "transportable", "budget uses retained/archive score margin only; "
        "no future labels"),
    "sqcad_denoise_compact_guard_4": PolicySpec(
        "SQCAD + compact denoising guard-4", "framework-variant",
        "Denoising guard with a fixed 512-token exposure budget",
        "transportable", "same qualification and candidate stream as "
        "denoise guard-4; context budget is priced separately"),
    "sqcad_denoise_compact_guard_16": PolicySpec(
        "SQCAD + compact denoising guard-16", "framework-variant",
        "Denoising guard with sixteen proposals and a fixed 512-token "
        "exposure budget",
        "transportable", "same denoiser and qualification; context budget "
        "is priced separately"),
    "sqcad_denoise_compact1k_guard_16": PolicySpec(
        "SQCAD + denoising guard-16 (1k-token context)", "framework-variant",
        "Denoising guard with sixteen proposals and a fixed 1024-token "
        "exposure budget",
        "transportable", "same denoiser and qualification; context budget "
        "is priced separately"),
    "sqcad_denoise_compact280_guard_16": PolicySpec(
        "SQCAD + denoising guard-16 (280-token context)", "framework-variant",
        "Denoising guard with sixteen proposals and a fixed 280-token "
        "exposure budget",
        "transportable", "same denoiser and qualification; context budget "
        "is priced separately"),
    "sqcad_denoise_compact300_guard_16": PolicySpec(
        "SQCAD + denoising guard-16 (300-token context)", "framework-variant",
        "Denoising guard with sixteen proposals and a fixed 300-token "
        "exposure budget",
        "transportable", "same denoiser and qualification; context budget "
        "is priced separately"),
    **{ab: PolicySpec(
        "SQCAD ablation: " + ab.removeprefix("sqcad_").replace("_", " "),
        "framework-ablation",
        "SQCAD row with one mechanism removed (doc 17 section 6)",
        "transportable", "same contract, one toggle off")
       for ab in SQCAD_ABLATIONS},
}

POLICY_SPECS.update({
    "simplemem_rc": PolicySpec(
        "SimpleMem-RC (lexical/compression proxy)", "named-baseline",
        "BM25 top-BUDGET over the shared chronological stream",
        "proxy", "native write-time compression is not transported"),
    "actmem_rc": PolicySpec(
        "ActMem-RC (dense/graph proxy)", "named-baseline",
        "Qwen3-Embedding-0.6B dense top-BUDGET",
        "proxy", "native graph consolidation is not transported"),
    "oblivion_rd": PolicySpec(
        "Oblivion-RD (decay-core proxy)", "named-baseline",
        "fixed exponential recency decay",
        "proxy", "LLM uncertainty tier is not transported"),
    "memoryworth_rw": PolicySpec(
        "MemoryWorth-RW (worth proxy)", "named-baseline",
        "observable frequency-decay score",
        "proxy", "future outcome labels are not exposed"),
    "trivium_rd": PolicySpec(
        "Trivium-RD (demand proxy)", "named-baseline",
        "observable association/demand score",
        "proxy", "interactive probe oracle is not transported"),
    "govmem_rg": PolicySpec(
        "GovMem-RG (risk-governance proxy)", "named-baseline",
        "observable risk-gated qualification",
        "proxy", "write-time native controller is not transported"),
})

# ---------------------------------------------------------------------------
# chronological mask + gold isolation
# ---------------------------------------------------------------------------


def _lte_date(a: str, b: str) -> bool:
    """Lexicographic date compare; both are 'YYYY/MM/DD (W) HH:MM' strings."""
    if not a or not b:
        return True
    return a <= b


def mask_lme_chronological(trace: Trace) -> Tuple[Trace, Dict[str, int]]:
    """LongMemEval S: keep only sessions dated <= the question date.  The
    mask is part of the shared contract: identical for every policy."""
    qd = trace.tasks[0].date if trace.tasks else ""
    visible = tuple(m for m in trace.msgs if _lte_date(m.date, qd))
    visible_ids = {m.msg_id for m in visible}
    meta = {"n_msgs_before": len(trace.msgs), "n_msgs_visible": len(visible),
            "n_masked_msgs": len(trace.msgs) - len(visible)}
    meta["n_masked_needed"] = sum(
        1 for t in trace.tasks for mid in t.needed_ids
        if mid not in visible_ids)
    return Trace(sample_id=trace.sample_id, msgs=visible, tasks=trace.tasks), \
        meta


def needed_free(tasks: Sequence[TraceTask]) -> List[TraceTask]:
    """Policy input hygiene: strip the gold needed ids before any policy
    sees the tasks (doc 17 4.0 / 7.1)."""
    return [TraceTask(task_id=t.task_id, question=t.question,
                      query_tokens=t.query_tokens, needed_ids=(),
                      scope=t.scope, date=t.date) for t in tasks]


# ---------------------------------------------------------------------------
# observable evidence features (gold never read)
# ---------------------------------------------------------------------------


def _session_freq(msgs: Sequence[TraceMsg]) -> Dict[str, int]:
    return dict(Counter(m.session_id for m in msgs))


def _rare_sessions(msgs: Sequence[TraceMsg]) -> set:
    freq = _session_freq(msgs)
    if len(freq) < 4:
        return set()
    q1 = statistics.quantiles(sorted(freq.values()), n=4)[0]
    return {sid for sid, c in freq.items() if c <= q1}


def _version_map(msgs: Sequence[TraceMsg], overlap: int = CONFLICT_OVERLAP
                 ) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """Per message: later messages in a DIFFERENT session with >= overlap
    shared content tokens.  Returns (updaters_of, newest_for).  Token
    inverted index: one pass over postings per message instead of the
    O(n^2) pair scan."""
    postings: Dict[str, List[int]] = defaultdict(list)
    for i, m in enumerate(msgs):
        for t in set(m.tokens):
            postings[t].append(i)
    updaters: Dict[str, List[str]] = defaultdict(list)
    newest: Dict[str, str] = {}
    for i, m in enumerate(msgs):
        counts: Counter = Counter()
        for t in set(m.tokens):
            for j in postings[t]:
                if j > i:
                    counts[j] += 1
        # Deterministic order (j descending): `newest` is the LATEST
        # updater, and the updaters list does not depend on the hash-order
        # of `set(m.tokens)` (PYTHONHASHSEED), so runs are reproducible.
        for j in sorted(counts, reverse=True):
            if counts[j] >= overlap and msgs[j].session_id != m.session_id:
                updaters[m.msg_id].append(msgs[j].msg_id)
                newest[m.msg_id] = msgs[j].msg_id
    return updaters, newest


def _lineage_map(msgs: Sequence[TraceMsg], overlap: int = CONFLICT_OVERLAP
                 ) -> Dict[str, str]:
    """derived msg_id -> source msg_id (the latest earlier turn in a
    different session sharing >= overlap tokens)."""
    postings: Dict[str, List[int]] = defaultdict(list)
    for i, m in enumerate(msgs):
        for t in set(m.tokens):
            postings[t].append(i)
    lineage: Dict[str, str] = {}
    for i, m in enumerate(msgs):
        counts: Counter = Counter()
        for t in set(m.tokens):
            for j in postings[t]:
                if j < i:
                    counts[j] += 1
        for j in sorted(counts, reverse=True):
            if counts[j] >= overlap and msgs[j].session_id != m.session_id:
                lineage[m.msg_id] = msgs[j].msg_id
                break
    return lineage


def _base_scores(msgs: Sequence[TraceMsg], half_life: float = HALF_LIFE
                 ) -> Dict[str, float]:
    freq = _session_freq(msgs)
    max_idx = max((m.date_idx for m in msgs), default=0)
    return {m.msg_id: math.log1p(freq[m.session_id])
            / (1.0 + (max_idx - m.date_idx) / half_life)
            for m in msgs}


def _storage_tokens(msgs: Sequence[TraceMsg],
                    retained: Sequence[str]) -> int:
    by = {m.msg_id: m for m in msgs}
    return sum(len(by[mid].tokens) for mid in retained if mid in by)


@dataclass
class TraceFeatures:
    """Per-trace observable evidence, computed once and shared by every
    policy that needs it (the O(n) inverted-index version/lineage maps were
    the hot spot before this split)."""
    by: Dict[str, TraceMsg]
    toks: Dict[str, set]
    freq: Dict[str, int]
    rare: set
    updaters: Dict[str, List[str]]
    newest: Dict[str, str]
    lineage: Dict[str, str]
    base: Dict[str, float]


def trace_features(msgs: Sequence[TraceMsg]) -> TraceFeatures:
    updaters, newest = _version_map(msgs)
    return TraceFeatures(
        by={m.msg_id: m for m in msgs},
        toks={m.msg_id: set(m.tokens) for m in msgs},
        freq=_session_freq(msgs),
        rare=_rare_sessions(msgs),
        updaters=updaters,
        newest=newest,
        lineage=_lineage_map(msgs),
        base=_base_scores(msgs),
    )


# ---------------------------------------------------------------------------
# engine primitives
# ---------------------------------------------------------------------------

@dataclass
class PolicyResult:
    policy: str
    workspaces: Dict[str, Tuple[str, ...]]          # task_id -> exposed ids
    storage_ids: Tuple[str, ...]                    # persistent store at end
    storage_tokens: int
    lifecycle: Dict[str, int] = field(default_factory=lambda: {
        "archives": 0, "restores": 0, "probes": 0, "fallbacks": 0})
    rows: List[Dict] = field(default_factory=list)
    # Optional query-time packed text.  Message IDs remain unchanged for
    # evidence auditing, while denoising variants may expose only salient
    # sentences to the reader and pay their actual token count.
    context_texts: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    # Reader scoring mode is part of the frozen policy artifact so access and
    # readout variants cannot be conflated in a result table.
    reader_mode: str = "overlap"
    # ``storage_tokens`` is the currently authorized/retained set.  Physical
    # storage is a separate axis because SQCAD archives remain readable by
    # probe, fallback, and candidate-guard paths.  Legacy engines default to
    # retained-only semantics; governance engines must opt into archive-
    # readable accounting explicitly.
    physical_storage_tokens: Optional[int] = None
    physical_storage_semantics: str = "retained_only"

    def __post_init__(self) -> None:
        if self.physical_storage_tokens is None:
            self.physical_storage_tokens = self.storage_tokens
        if self.physical_storage_tokens < self.storage_tokens:
            raise ValueError("physical storage cannot be below authorized storage")


def _static_engine(msgs: Sequence[TraceMsg], tasks: Sequence[TraceTask],
                   score: Dict[str, float], policy: str,
                   keep_all: bool = False) -> PolicyResult:
    ranked = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
    retained = ([m.msg_id for m in msgs] if keep_all
                else [mid for mid, _ in ranked[:BUDGET]])
    ws = tuple(retained)
    return PolicyResult(
        policy=policy,
        workspaces={t.task_id: ws for t in tasks},
        storage_ids=tuple(retained),
        storage_tokens=_storage_tokens(msgs, retained),
        lifecycle={"archives": len(msgs) - len(retained), "restores": 0,
                   "probes": 0, "fallbacks": 0},
    )


def _retrieval_engine(msgs: Sequence[TraceMsg], tasks: Sequence[TraceTask],
                      retriever: Callable[[Sequence[TraceMsg], Sequence[str]],
                                          Dict[str, float]],
                      policy: str, reader_mode: str = "overlap") -> PolicyResult:
    out: Dict[str, Tuple[str, ...]] = {}
    for t in tasks:
        scores = retriever(msgs, t.query_tokens)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        out[t.task_id] = tuple(mid for mid, _ in ranked[:BUDGET])
    return PolicyResult(
        policy=policy, workspaces=out,
        storage_ids=tuple(m.msg_id for m in msgs),  # index-everything
        storage_tokens=sum(len(m.tokens) for m in msgs),
        lifecycle={"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0},
        reader_mode=reader_mode,
    )


def _lru_engine(msgs: Sequence[TraceMsg], tasks: Sequence[TraceTask],
                policy: str) -> PolicyResult:
    """Dynamic: last-access refreshed on QA exposure (frozen QA order)."""
    age: Dict[str, float] = {m.msg_id: float(len(msgs) - m.date_idx)
                             for m in msgs}
    retained: Tuple[str, ...] = ()
    out: Dict[str, Tuple[str, ...]] = {}
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}
    for t in tasks:
        ranked = sorted(age.items(), key=lambda kv: (kv[1], kv[0]))
        new_retained = tuple(mid for mid, _ in ranked[:BUDGET])
        for mid in new_retained:
            if mid not in retained:
                lifecycle["restores"] += 1
            age[mid] = 0.0
        for mid in retained:
            if mid not in new_retained:
                lifecycle["archives"] += 1
        retained = new_retained
        out[t.task_id] = retained
        for mid in age:
            if mid not in retained:
                age[mid] += 1.0
    return PolicyResult(policy=policy, workspaces=out,
                        storage_ids=retained,
                        storage_tokens=_storage_tokens(msgs, retained),
                        lifecycle=lifecycle)


def _stateful_ratio_engine(msgs: Sequence[TraceMsg],
                           tasks: Sequence[TraceTask],
                           policy: str,
                           posterior: Callable[[Dict[str, Tuple[int, int]]],
                                               Dict[str, float]]) -> PolicyResult:
    """memory_worth-style posterior-ratio policies: per-item success/failure
    counters over QA events (observable signal only), score = posterior mean,
    static top-BUDGET after the counters settle."""
    counters: Dict[str, Tuple[int, int]] = {m.msg_id: (0, 0) for m in msgs}
    toks = {m.msg_id: set(m.tokens) for m in msgs}
    for t in tasks:
        q = set(t.query_tokens)
        for m in msgs:
            hit = int(len(toks[m.msg_id] & q) >= CONFLICT_OVERLAP)
            h, n = counters[m.msg_id]
            counters[m.msg_id] = (h + hit, n + (1 - hit))
    scores = posterior(counters)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    retained = tuple(mid for mid, _ in ranked[:BUDGET])
    return PolicyResult(
        policy=policy,
        workspaces={t.task_id: retained for t in tasks},
        storage_ids=retained,
        storage_tokens=_storage_tokens(msgs, retained),
        lifecycle={"archives": len(msgs) - len(retained), "restores": 0,
                   "probes": 0, "fallbacks": 0},
    )


# ---------------------------------------------------------------------------
# SQCAD dynamic lifecycle engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SqcadConfig:
    qualification: bool = True
    version_gate: bool = True
    silence_semantics: bool = True
    restore: bool = True
    probe: bool = True
    cost_aware_restore: bool = True
    lineage: bool = True
    bundle: bool = True
    positive_protection: bool = True
    negative_attenuation: bool = True
    fallback: bool = True
    candidate_guard: bool = False
    candidate_guard_budget: int = 0
    adaptive_candidate_guard: bool = False
    candidate_source: str = "lexical"
    candidate_reserve: int = 0
    candidate_expansion: bool = False
    response_prior: bool = False
    denoise: bool = False
    context_token_budget: int = 0
    graph_smoothing: bool = True
    diversity_penalty: bool = True
    temporal_fir: bool = False
    reader_mode: str = "overlap"


def _jaccard(a: set, b: set) -> float:
    """Token-support overlap used only for query-time redundancy control."""
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _denoise_rank(ids: Sequence[str], scores: Dict[str, float],
                  toks: Dict[str, set], by: Dict[str, TraceMsg],
                  token_budget: int = 0, graph_smoothing: bool = True,
                  diversity_penalty: bool = True,
                  temporal_fir: bool = False) -> List[str]:
    """Select a diverse evidence set from a fixed candidate pool.

    The first term is a conservative local smoothing of the query signal:
    an item receives support only from a lexical neighbour in a different
    session.  The second term is greedy MMR, which prevents repeated turns
    from consuming the workspace.  Both operations are query-time only and
    cannot authorize persistent storage.
    """
    if not ids:
        return []
    support: Dict[str, float] = {}
    lowpass: Dict[str, float] = {}
    for mid in ids:
        neighbours = [
            (other, _jaccard(toks[mid], toks[other]))
            for other in ids if other != mid
            and by[other].session_id != by[mid].session_id
        ]
        total_w = sum(w for _, w in neighbours)
        support[mid] = (total_w / len(neighbours)) if neighbours else 0.0
        # One-step graph low-pass: retain the query signal while borrowing
        # only consensus from independent sessions.  The high-pass residual
        # is kept as a small penalty so isolated lexical spikes are treated
        # as noise rather than rewarded by the gate.
        neighbour_mean = (sum(w * scores[other] for other, w in neighbours)
                          / total_w) if total_w else scores[mid]
        lowpass[mid] = 0.82 * scores[mid] + 0.18 * neighbour_mean
    if temporal_fir:
        ordered = sorted(ids, key=lambda mid: (by[mid].date_idx, mid))
        for i, mid in enumerate(ordered):
            left = scores[ordered[i - 1]] if i else scores[mid]
            right = scores[ordered[i + 1]] if i + 1 < len(ordered) else scores[mid]
            lowpass[mid] = 0.25 * left + 0.50 * scores[mid] + 0.25 * right
        smoothed = {
            mid: lowpass[mid] - 0.08 * abs(scores[mid] - lowpass[mid])
            for mid in ids
        }
    elif graph_smoothing:
        smoothed = {
            mid: lowpass[mid] - 0.04 * abs(scores[mid] - lowpass[mid])
            + 0.08 * support[mid]
            for mid in ids
        }
    else:
        smoothed = dict(scores)
    selected: List[str] = []
    remaining = set(ids)
    used_tokens = 0
    # lambda is fixed before evaluation; relevance remains dominant while
    # repeated/near-duplicate turns are explicitly down-weighted.
    relevance_weight = 0.78
    while remaining and len(selected) < BUDGET:
        ranked = []
        for mid in remaining:
            redundancy = max((_jaccard(toks[mid], toks[other])
                              for other in selected), default=0.0)
            penalty = redundancy if diversity_penalty else 0.0
            mmr = (relevance_weight * smoothed[mid]
                   - (1.0 - relevance_weight) * penalty)
            ranked.append((mmr, smoothed[mid], mid))
        ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))
        chosen = None
        for _, _, mid in ranked:
            n_tokens = len(by[mid].tokens)
            if token_budget and selected and used_tokens + n_tokens > token_budget:
                continue
            if token_budget and not selected and n_tokens > token_budget:
                continue
            chosen = mid
            break
        if chosen is None:
            break
        selected.append(chosen)
        remaining.remove(chosen)
        used_tokens += len(by[chosen].tokens)
    return selected


_READER_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for",
    "is", "are", "was", "were", "be", "been", "did", "do", "does",
    "what", "when", "where", "who", "why", "how", "which", "would",
    "could", "should", "can", "will", "has", "have", "had", "it",
    "this", "that", "they", "them", "he", "she", "we", "you", "i",
}
_DATE_OR_TIME_RE = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|"
    r"october|november|december|yesterday|today|tomorrow|last|next|"
    r"\d{1,4}(?:st|nd|rd|th)?|\d{1,2}:\d{2})\b", re.I)
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_GENERIC_TURN_RE = re.compile(
    r"^(?:thanks|thank you|wow|nice|great|awesome|did you|what did it|"
    r"that(?:'s| is) (?:great|nice|awesome)|sounds good)\b", re.I)
_QUESTION_ECHO_RE = re.compile(
    r"^(?:what|when|where|who|why|how|did|does|do|is|are|can|could|"
    r"would|have|has|should)\b", re.I)


def _sentence_answerability(question: str, sentence: str,
                            all_sentences: Sequence[str],
                            suppress_question_echo: bool = False) -> float:
    """Score observable query/type signals for deterministic readout."""
    q = [t for t in clean_tokens(question) if t not in _READER_STOPWORDS]
    sent_tokens = set(clean_tokens(sentence))
    if not q:
        return 0.0
    df = Counter(t for text in all_sentences
                 for t in set(clean_tokens(text)))
    n = max(len(all_sentences), 1)
    overlap = set(q) & sent_tokens
    score = sum(math.log((1.0 + n) / (1.0 + df[t])) + 1.0
                for t in overlap)
    ql = question.lower()
    if ql.startswith(("when ", "what time", "what date")):
        score += 1.25 if _DATE_OR_TIME_RE.search(sentence) else 0.0
    if ql.startswith(("how many ", "how much ", "what number")):
        score += 1.25 if _NUMBER_RE.search(sentence) else 0.0
    if _GENERIC_TURN_RE.search(sentence.strip()):
        score -= 0.65
    if suppress_question_echo and _QUESTION_ECHO_RE.search(sentence.strip()):
        # A retrieved turn often repeats the user's question.  This is an
        # observable readout nuisance, not evidence that the turn is false;
        # keep it available but prefer declarative response sentences.
        score -= 0.85
    if len(clean_tokens(sentence)) < 4 and score > 0:
        score -= 0.15
    return score


def _pack_context(question: str, ids: Sequence[str], by: Dict[str, TraceMsg],
                  token_budget: int = 0,
                  reader_mode: str = "overlap") -> Tuple[str, ...]:
    """Pack query-supported sentences without changing evidence identity."""
    q = set(clean_tokens(question))
    ranked = []
    all_sentences = [s.strip() for mid in ids
                     for s in SENT_RE.split(by[mid].content) if s.strip()]
    for pos, mid in enumerate(ids):
        sentences = [s.strip() for s in SENT_RE.split(by[mid].content)
                     if s.strip()]
        if not sentences:
            continue
        supported = [s for s in sentences if q & set(clean_tokens(s))]
        chosen = supported or sentences[:1]
        for s in chosen:
            toks = clean_tokens(s)
            overlap = len(q & set(toks))
            signal = (_sentence_answerability(
                question, s, all_sentences,
                suppress_question_echo=(reader_mode == "answerability_structured"))
                      if reader_mode in {"answerability", "answerability_structured"}
                      else float(overlap))
            ranked.append((signal, overlap, -pos, s, len(toks)))
    ranked.sort(key=lambda x: (-x[0], -x[1], -x[2], x[3]))
    if not token_budget:
        return tuple(x[3] for x in sorted(ranked, key=lambda x: (-x[2], x[3])))
    selected = []
    used = 0
    for _, _, _, sentence, n_tokens in ranked:
        if used + n_tokens > token_budget:
            continue
        selected.append(sentence)
        used += n_tokens
    if not selected and ranked:
        # Never silently turn a non-empty workspace into an empty prompt;
        # one salient sentence is retained even when it exceeds the cap.
        selected.append(ranked[0][3])
    return tuple(selected)


SQCAD_ABLATION_CONFIG = {
    "sqcad": SqcadConfig(),
    "sqcad_candidate_guard_1": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=1),
    "sqcad_candidate_guard_2": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=2),
    "sqcad_candidate_guard_4": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=4),
    "sqcad_candidate_guard_8": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=8),
    "sqcad_candidate_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16),
    "sqcad_candidate_guard_full": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=10**9),
    "sqcad_candidate_guard_adaptive": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        adaptive_candidate_guard=True),
    "sqcad_candidate_guard": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=4),
    "sqcad_dense_guard_4": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=4,
        candidate_source="dense"),
    "sqcad_hybrid_guard_4": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=4,
        candidate_source="hybrid"),
    "sqcad_hybrid_guard_4_reserve_1": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=4,
        candidate_source="hybrid", candidate_reserve=1),
    "sqcad_denoise_guard_4": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=4,
        candidate_source="hybrid", denoise=True),
    "sqcad_denoise_guard_8": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=8,
        candidate_source="hybrid", denoise=True),
    "sqcad_denoise_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True),
    "sqcad_denoise_guard_full": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=10**9,
        candidate_source="hybrid", denoise=True),
    "sqcad_denoise_guard_32": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=32,
        candidate_source="hybrid", denoise=True),
    "sqcad_denoise_nosmooth_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True, graph_smoothing=False),
    "sqcad_denoise_nodiverse_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True, diversity_penalty=False),
    "sqcad_fir_denoise_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True, temporal_fir=True,
        reader_mode="answerability"),
    "sqcad_fir_denoise_abstain_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True, temporal_fir=True,
        reader_mode="answerability_abstain"),
    "sqcad_fir_denoise_guard_full": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=10**9,
        candidate_source="hybrid", denoise=True, temporal_fir=True,
        reader_mode="answerability"),
    "sqcad_fir_denoise_expand_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", candidate_expansion=True,
        denoise=True, temporal_fir=True, reader_mode="answerability"),
    "sqcad_fir_structured_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", response_prior=True,
        denoise=True, temporal_fir=True,
        reader_mode="answerability_structured"),
    "sqcad_fir_structured_overlap_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", response_prior=True,
        denoise=True, temporal_fir=True,
        reader_mode="overlap"),
    "sqcad_fir_structured_compact_1536": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", response_prior=True,
        denoise=True, temporal_fir=True, context_token_budget=1536,
        reader_mode="answerability_structured"),
    "sqcad_fir_structured_compact_1280": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", response_prior=True,
        denoise=True, temporal_fir=True, context_token_budget=1280,
        reader_mode="answerability_structured"),
    "sqcad_fir_denoise_overlap_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True, temporal_fir=True,
        reader_mode="overlap"),
    "sqcad_fir_denoise_reader_v2_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True, temporal_fir=True,
        reader_mode="answerability"),
    "sqcad_denoise_adaptive": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        adaptive_candidate_guard=True, candidate_source="hybrid",
        denoise=True),
    "sqcad_denoise_compact_guard_4": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=4,
        candidate_source="hybrid", denoise=True,
        context_token_budget=512),
    "sqcad_denoise_compact_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True,
        context_token_budget=512),
    "sqcad_denoise_compact1k_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True,
        context_token_budget=1024),
    "sqcad_denoise_compact280_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True,
        context_token_budget=280),
    "sqcad_denoise_compact300_guard_16": SqcadConfig(
        candidate_guard=True, candidate_guard_budget=16,
        candidate_source="hybrid", denoise=True,
        context_token_budget=300),
    "sqcad_no_qualification": SqcadConfig(qualification=False),
    "sqcad_no_version_gate": SqcadConfig(version_gate=False),
    "sqcad_no_silence_semantics": SqcadConfig(silence_semantics=False,
                                              restore=False, probe=False),
    "sqcad_no_restore": SqcadConfig(restore=False),
    "sqcad_no_probe": SqcadConfig(probe=False),
    "sqcad_fixed_restore": SqcadConfig(cost_aware_restore=False),
    "sqcad_no_lineage": SqcadConfig(lineage=False),
    "sqcad_item_only": SqcadConfig(bundle=False),
    "sqcad_no_positive_protection": SqcadConfig(positive_protection=False),
    "sqcad_no_negative_attenuation": SqcadConfig(negative_attenuation=False),
    "sqcad_no_fallback": SqcadConfig(fallback=False),
}


def _sqcad_engine(msgs: Sequence[TraceMsg], tasks: Sequence[TraceTask],
                  policy: str, feats: TraceFeatures,
                  dense_ws: Optional[Dict[str, Tuple[str, ...]]] = None
                  ) -> PolicyResult:
    cfg = SQCAD_ABLATION_CONFIG[policy]
    by = feats.by
    toks = feats.toks
    freq = feats.freq
    rare = feats.rare
    updaters, newest = feats.updaters, feats.newest
    lineage = feats.lineage
    base = feats.base

    retained: List[str] = []
    archived: List[str] = []
    rows: List[Dict] = []
    lifecycle = {"archives": 0, "restores": 0, "probes": 0, "fallbacks": 0}

    def score(mid: str) -> float:
        s = base[mid]
        if cfg.positive_protection and by[mid].session_id in rare:
            s += RARE_FLOOR
        if mid in updaters and cfg.version_gate:
            s += CONFLICT_BONUS
        return s

    def conflicted_unresolved(mid: str) -> bool:
        if not cfg.qualification or not cfg.version_gate:
            return False
        return mid in newest and newest[mid] in retained

    def evict() -> None:
        """Archive the weakest item (plus its session mates under bundle
        actions); unresolved version pairs are split only when nothing else
        can be evicted (no commitment on unresolved)."""
        candidates = [mid for mid in retained
                      if not conflicted_unresolved(mid)]
        forced = not candidates
        if forced:
            candidates = list(retained)
        victim = min(candidates, key=lambda mid: (score(mid), mid))
        to_archive = [victim]
        if cfg.bundle:
            to_archive += [mid for mid in retained if mid != victim
                           and by[mid].session_id == by[victim].session_id]
        for v in to_archive:
            if v not in retained:
                continue
            retained.remove(v)
            archived.append(v)
            lifecycle["archives"] += 1
            rows.append({"mid": v, "action": "archive",
                         "qualification": ("forced_pair" if forced
                                           else "identified"),
                         "reason": "budget_forced" if forced else "budget"})
            if cfg.lineage:
                for mid in list(retained):
                    if lineage.get(mid) == v:
                        retained.remove(mid)
                        archived.append(mid)
                        lifecycle["archives"] += 1
                        rows.append({"mid": mid, "action": "archive",
                                     "qualification": "orphan",
                                     "reason": "source_archived"})

    # ---- write time: chronological stream ----
    for m in msgs:
        if m.msg_id in retained:
            continue
        retained.append(m.msg_id)
        rows.append({"mid": m.msg_id, "action": "keep",
                     "qualification": ("unresolved"
                                       if conflicted_unresolved(m.msg_id)
                                       else "identified"),
                     "reason": "write"})
        while len(retained) > BUDGET:
            evict()

    # ---- QA time (frozen QA order) ----
    workspaces: Dict[str, Tuple[str, ...]] = {}
    context_texts: Dict[str, Tuple[str, ...]] = {}
    for t in tasks:
        q = set(t.query_tokens)
        overlap = {mid: len(toks[mid] & q) for mid in toks}
        pool = list(retained)

        probe_ids: List[str] = []
        if cfg.probe and cfg.silence_semantics and archived:
            # probe trigger: the module's established lexical-evidence
            # threshold (>=3 content tokens shared with the query), not the
            # 1-token common-vocabulary coincidence
            cand = [mid for mid in archived if overlap[mid] >= CONFLICT_OVERLAP]
            cand_ranked = sorted(cand, key=lambda mid: (-overlap[mid], mid))
            probe_ids = cand_ranked[:PROBE_BUDGET_PER_TASK]
            for mid in probe_ids:
                lifecycle["probes"] += 1
                rows.append({"mid": mid, "action": "probe",
                             "qualification": "probed",
                             "reason": "query_overlap"})

        # Coverage guard: association/BM25 may propose missing evidence for
        # this QA, but the proposal is one-shot and never authorizes a
        # persistent write.  Qualification remains the only write gate.
        candidate_probe_ids: List[str] = []
        if cfg.candidate_guard:
            all_scores = bm25_scores(msgs, t.query_tokens)
            lexical_ranked = sorted(
                all_scores.items(), key=lambda kv: (-kv[1], kv[0]))
            if cfg.candidate_source == "dense":
                if dense_ws is None:
                    raise ValueError(
                        f"{policy} requires a dense workspace cache")
                all_ranked = [(mid, 1.0) for mid in
                              dense_ws.get(t.task_id, ())]
            elif cfg.candidate_source == "hybrid":
                if dense_ws is None:
                    raise ValueError(
                        f"{policy} requires a dense workspace cache")
                ids = [m.msg_id for m in msgs]
                b_rank = {mid: i for i, (mid, _) in
                          enumerate(lexical_ranked)}
                d_rank = {mid: i for i, mid in enumerate(
                    dense_ws.get(t.task_id, ()))}
                # The dense cache stores only its top-B list. Missing dense
                # ranks are placed after the visible list; this is a fixed,
                # gold-free RRF candidate ordering.
                rrf = {
                    mid: (1.0 / (60 + 1 + b_rank[mid])
                          + 1.0 / (60 + 1 + d_rank.get(mid, len(ids))))
                    for mid in ids
                }
                all_ranked = sorted(ids,
                                    key=lambda mid: (-rrf[mid], mid))
                all_ranked = [(mid, rrf[mid]) for mid in all_ranked]
            else:
                all_ranked = lexical_ranked
            guard_budget = cfg.candidate_guard_budget
            if cfg.adaptive_candidate_guard:
                retained_best = max(
                    (all_scores.get(mid, 0.0) for mid in pool),
                    default=0.0)
                archive_best = max(
                    (all_scores.get(mid, 0.0) for mid in archived),
                    default=0.0)
                if retained_best <= 0.0 < archive_best:
                    guard_budget = 16
                elif archive_best > retained_best:
                    guard_budget = 8
                else:
                    guard_budget = 2
            if cfg.candidate_expansion or cfg.response_prior:
                # Expand observable high-score seeds in the same session.
                # ``candidate_expansion`` is the symmetric radius-one
                # diagnostic; ``response_prior`` is more structured: it
                # prefers the next declarative turn after an interrogative
                # anchor, which is an observable dialogue edge rather than a
                # query-local relevance assumption.
                session_order: Dict[str, List[str]] = defaultdict(list)
                for msg in sorted(msgs, key=lambda item: (item.session_id,
                                                            item.date_idx,
                                                            item.msg_id)):
                    session_order[msg.session_id].append(msg.msg_id)
                positions = {
                    mid: idx for sid, seq in session_order.items()
                    for idx, mid in enumerate(seq)
                }
                seed_ids = [mid for mid, value in all_ranked
                            if value > 0.0][:max(8, min(guard_budget, 8))]
                rank_value = {mid: (rank, value)
                              for rank, (mid, value) in enumerate(all_ranked)}
                proposal_order: List[str] = []
                if cfg.response_prior:
                    response_candidates: List[Tuple[float, int, str]] = []
                    for seed in seed_ids:
                        sid = by[seed].session_id
                        seq = session_order[sid]
                        idx = positions[seed]
                        anchor = by[seed].content.strip()
                        anchor_is_question = bool(
                            anchor.endswith("?") or
                            re.match(r"^(?:what|when|where|who|why|how|did|"
                                     r"does|do|is|are|can|could|would)\\b",
                                     anchor, re.I))
                        anchor_overlap = len(
                            (set(clean_tokens(anchor)) - _READER_STOPWORDS)
                            & (set(t.query_tokens) - _READER_STOPWORDS))
                        if not anchor_is_question or anchor_overlap < 2:
                            continue
                        # A response is usually the immediate next turn; a
                        # second step is allowed only as a lower-priority
                        # continuation for multi-sentence answers.
                        for step in (1,):
                            nidx = idx + step
                            if nidx >= len(seq):
                                continue
                            mid = seq[nidx]
                            if mid == seed:
                                continue
                            candidate = by[mid].content.strip()
                            if _QUESTION_ECHO_RE.search(candidate):
                                declarative = -0.35
                            else:
                                declarative = 0.35
                            lexical = min(max(all_scores.get(mid, 0.0),
                                              0.0), 1.0)
                            # Higher is better; rank breaks ties without using
                            # evaluator evidence.
                            priority = (1.0 if step == 1 else 0.55) + declarative \
                                + 0.10 * lexical
                            rank = rank_value.get(mid, (len(all_ranked), 0.0))[0]
                            response_candidates.append((-priority, rank, mid))
                    response_candidates.sort(key=lambda item: item)
                    proposal_order.extend(mid for _, _, mid in response_candidates)
                if cfg.candidate_expansion:
                    expanded: List[Tuple[float, float, str]] = []
                    for seed in seed_ids:
                        sid = by[seed].session_id
                        seq = session_order[sid]
                        idx = positions[seed]
                        for neighbour_idx in (idx - 1, idx + 1):
                            if not 0 <= neighbour_idx < len(seq):
                                continue
                            mid = seq[neighbour_idx]
                            distance = abs(neighbour_idx - idx)
                            rank, value = rank_value[mid]
                            expanded.append((rank + 0.25 * distance,
                                             -value, mid))
                    expanded.sort(key=lambda item: (item[0], item[1], item[2]))
                    proposal_order.extend(mid for _, _, mid in expanded)
                proposal_order += [mid for mid, value in all_ranked
                                   if value > 0.0]
                candidate_probe_ids = list(dict.fromkeys(
                    mid for mid in proposal_order
                    if mid not in pool and mid not in probe_ids))[:guard_budget]
            else:
                candidate_probe_ids = [
                    mid for mid, value in all_ranked
                    if value > 0.0 and mid not in pool and mid not in probe_ids
                ][:guard_budget]
            for mid in candidate_probe_ids:
                lifecycle["probes"] += 1
                rows.append({"mid": mid, "action": "candidate_probe",
                             "qualification": "proposed",
                             "reason": "coverage_guard"})

        if cfg.fallback:
            while len(pool) < BUDGET and archived:
                fill = max(archived, key=lambda mid: (overlap[mid], mid))
                archived.remove(fill)
                pool.append(fill)
                lifecycle["fallbacks"] += 1
                rows.append({"mid": fill, "action": "fallback",
                             "qualification": "silent_fill",
                             "reason": "short_workspace"})

        # exposure pool = persistent store + one-shot probes
        pool_exposure = list(dict.fromkeys(
            pool + probe_ids + candidate_probe_ids))
        q_scores = bm25_scores([by[mid] for mid in pool_exposure],
                               t.query_tokens)
        if cfg.negative_attenuation and cfg.qualification:
            eff = {mid: q_scores[mid] * (ATTENUATION if mid in updaters
                                         else 1.0) for mid in pool_exposure}
        else:
            eff = q_scores
        if cfg.denoise:
            # Denoising is an access-time transformation only.  The retained
            # and archived sets, qualification state, and all lifecycle
            # counters remain exactly those produced above.
            ranked = _denoise_rank(pool_exposure, eff, toks, by,
                                   cfg.context_token_budget,
                                   cfg.graph_smoothing,
                                   cfg.diversity_penalty,
                                   cfg.temporal_fir)
        else:
            ranked = sorted(pool_exposure, key=lambda mid: (-eff[mid], mid))
        if cfg.candidate_reserve and candidate_probe_ids:
            # Reserve only the highest-ranked observable candidate proposal;
            # all remaining slots use the normal qualification/risk ranking.
            # This isolates workspace competition from candidate coverage and
            # never reads evaluator gold or future needed IDs.
            reserve = [mid for mid in candidate_probe_ids
                       if mid in pool_exposure][:cfg.candidate_reserve]
            exposed = reserve + [mid for mid in ranked if mid not in reserve]
            exposed = exposed[:BUDGET]
        else:
            exposed = ranked[:BUDGET]
        workspaces[t.task_id] = tuple(exposed)
        if cfg.denoise:
            context_texts[t.task_id] = _pack_context(
                t.question, exposed, by, cfg.context_token_budget,
                cfg.reader_mode)

        # restore: a probed item is re-admitted permanently iff it earned an
        # exposure slot under this QA's ranking (cost-aware) -- or always
        # (fixed_restore ablation)
        if cfg.restore and probe_ids:
            for mid in probe_ids:
                admit = (mid in exposed) if cfg.cost_aware_restore else True
                if admit and mid not in retained:
                    retained.append(mid)
                    if mid in archived:
                        archived.remove(mid)
                    lifecycle["restores"] += 1
                    rows.append({"mid": mid, "action": "restore",
                                 "qualification": "restored",
                                 "reason": "earned_slot"})
                    while len(retained) > BUDGET:
                        evict()

    return PolicyResult(policy=policy, workspaces=workspaces,
                        storage_ids=tuple(retained),
                        storage_tokens=_storage_tokens(msgs, retained),
                        lifecycle=lifecycle, rows=rows,
                        context_texts=context_texts,
                        reader_mode=cfg.reader_mode,
                        physical_storage_tokens=sum(len(m.tokens) for m in msgs),
                        physical_storage_semantics="archive_readable")


# ---------------------------------------------------------------------------
# policy dispatch
# ---------------------------------------------------------------------------

def policy_requires_dense(policy: str) -> bool:
    """Whether ``policy`` needs the frozen dense workspace artifact.

    Keeping this predicate shared by dispatch and the batch CLI prevents a
    successful run from silently dropping hybrid SQCAD rows when a cache is
    absent or keyed differently.
    """
    policy = NAMED_BASELINE_ALIASES.get(policy, policy)
    if policy in ("dense", "rrf"):
        return True
    cfg = SQCAD_ABLATION_CONFIG.get(policy)
    return bool(cfg and cfg.candidate_source in {"dense", "hybrid"})


def run_policy(policy: str, trace: Trace,
               dense_ws: Optional[Dict[str, Tuple[str, ...]]] = None,
               feats: Optional[TraceFeatures] = None,
               ) -> Optional[PolicyResult]:
    """Run one policy on one (masked) trace.  Returns None when a required
    external artifact (dense cache) is missing.  `feats` (per-trace
    observable evidence) is computed lazily; batch runs should precompute
    it once per trace and pass it in."""
    policy = NAMED_BASELINE_ALIASES.get(policy, policy)
    msgs = trace.msgs
    tasks = needed_free(trace.tasks)
    if policy == "no_memory":
        return PolicyResult(
            policy=policy,
            workspaces={t.task_id: () for t in tasks},
            storage_ids=(), storage_tokens=0,
            lifecycle={"archives": 0, "restores": 0, "probes": 0,
                       "fallbacks": 0})
    if policy == "keep_all":
        return _static_engine(msgs, tasks, {m.msg_id: 0.0 for m in msgs},
                              policy, keep_all=True)
    if policy == "fifo":
        return _static_engine(msgs, tasks,
                              {m.msg_id: float(-m.date_idx) for m in msgs},
                              policy)
    if policy == "recency":
        return _static_engine(msgs, tasks,
                              {m.msg_id: float(m.date_idx) for m in msgs},
                              policy)
    if policy == "fixed_decay":
        return _static_engine(msgs, tasks, _base_scores(msgs), policy)
    if policy == "frequency_decay":
        freq = _session_freq(msgs)
        max_idx = max((m.date_idx for m in msgs), default=0)
        return _static_engine(msgs, tasks, {
            m.msg_id: math.log1p(freq[m.session_id])
            / (1.0 + (max_idx - m.date_idx) / 50.0) for m in msgs}, policy)
    if policy == "bm25":
        return _retrieval_engine(msgs, tasks, bm25_scores, policy)
    if policy == "bm25_answerability":
        return _retrieval_engine(msgs, tasks, bm25_scores, policy,
                                 reader_mode="answerability")
    if policy == "bm25_answerability_structured":
        return _retrieval_engine(msgs, tasks, bm25_scores, policy,
                                 reader_mode="answerability_structured")
    if policy == "bm25_answerability_abstain":
        return _retrieval_engine(msgs, tasks, bm25_scores, policy,
                                 reader_mode="answerability_abstain")
    if policy == "dense":
        if dense_ws is None:
            return None
        return PolicyResult(
            policy=policy, workspaces=dense_ws,
            storage_ids=tuple(m.msg_id for m in msgs),
            storage_tokens=sum(len(m.tokens) for m in msgs),
            lifecycle={"archives": 0, "restores": 0, "probes": 0,
                       "fallbacks": 0})
    if policy == "rrf":
        if dense_ws is None:
            return None
        out: Dict[str, Tuple[str, ...]] = {}
        ids = [m.msg_id for m in msgs]
        for t in tasks:
            b = bm25_scores(msgs, t.query_tokens)
            b_rank = {mid: i for i, mid in enumerate(
                sorted(ids, key=lambda m: (-b[m], m)))}
            d_rank = {mid: i for i, mid in enumerate(dense_ws[t.task_id])}
            rrf = {mid: (1.0 / (60 + 1 + b_rank[mid])
                         + 1.0 / (60 + 1 + d_rank.get(mid, len(ids))))
                   for mid in ids}
            ranked = sorted(ids, key=lambda mid: (-rrf[mid], mid))
            out[t.task_id] = tuple(ranked[:BUDGET])
        return PolicyResult(
            policy=policy, workspaces=out,
            storage_ids=tuple(ids),
            storage_tokens=sum(len(m.tokens) for m in msgs),
            lifecycle={"archives": 0, "restores": 0, "probes": 0,
                       "fallbacks": 0})
    if policy == "lru":
        return _lru_engine(msgs, tasks, policy)
    if policy == "association_only":
        freq = _session_freq(msgs)
        return _static_engine(msgs, tasks, {
            m.msg_id: float(m.date_idx) * math.log1p(freq[m.session_id])
            for m in msgs}, policy)
    if policy == "memory_worth":
        return _stateful_ratio_engine(
            msgs, tasks, policy,
            lambda c: {mid: (h + 1.0) / (h + n + 2.0)
                       for mid, (h, n) in c.items()})
    if policy == "causal_item":
        toks = {m.msg_id: set(m.tokens) for m in msgs}
        # naive observational exposure contrast over the QA sequence;
        # exposure = the item is in the current top-BUDGET by BM25; support
        # failure falls back to the base score (documented proxy behavior)
        exposed_val: Dict[str, List[float]] = defaultdict(list)
        unexposed_val: Dict[str, List[float]] = defaultdict(list)
        for t in tasks:
            q = set(t.query_tokens)
            scores = bm25_scores(msgs, t.query_tokens)
            ranked = sorted(scores, key=lambda mid: (-scores[mid], mid))
            top = set(ranked[:BUDGET])
            for m in msgs:
                v = float(len(toks[m.msg_id] & q) >= CONFLICT_OVERLAP)
                (exposed_val if m.msg_id in top
                 else unexposed_val)[m.msg_id].append(v)
        base = _base_scores(msgs)
        effect: Dict[str, float] = {}
        for m in msgs:
            if exposed_val[m.msg_id] and unexposed_val[m.msg_id]:
                effect[m.msg_id] = (
                    statistics.mean(exposed_val[m.msg_id])
                    - statistics.mean(unexposed_val[m.msg_id]))
            else:
                effect[m.msg_id] = base[m.msg_id]
        return _static_engine(msgs, tasks, effect, policy)
    if policy == "bundle_control":
        freq = _session_freq(msgs)
        base = _base_scores(msgs)
        sess_sum: Dict[str, float] = defaultdict(float)
        for m in msgs:
            sess_sum[m.session_id] += base[m.msg_id]
        sess_score = {sid: v / freq[sid] for sid, v in sess_sum.items()}
        ranked = sorted(msgs, key=lambda m: (-sess_score[m.session_id],
                                             m.msg_id))
        retained = [m.msg_id for m in ranked[:BUDGET]]
        return PolicyResult(
            policy=policy,
            workspaces={t.task_id: tuple(retained) for t in tasks},
            storage_ids=tuple(retained),
            storage_tokens=_storage_tokens(msgs, retained),
            lifecycle={"archives": len(msgs) - len(retained), "restores": 0,
                       "probes": 0, "fallbacks": 0})
    if policy == "risk_gated_decomp_abstract":
        # controlled proxy transport: base score with conflict-gate fallback
        # (group = session mean) substituting for the unavailable
        # semantic-confidence / harm-veto signals
        if feats is None:
            feats = trace_features(msgs)
        base = feats.base
        updaters = feats.updaters
        sess_sum: Dict[str, float] = defaultdict(float)
        sess_n: Dict[str, int] = defaultdict(int)
        for m in msgs:
            sess_sum[m.session_id] += base[m.msg_id]
            sess_n[m.session_id] += 1
        sess_mean = {sid: v / sess_n[sid] for sid, v in sess_sum.items()}
        score = {}
        for m in msgs:
            score[m.msg_id] = (min(base[m.msg_id],
                                   sess_mean[m.session_id])
                               if m.msg_id in updaters
                               else base[m.msg_id])
        return _static_engine(msgs, tasks, score, policy)
    if policy in SQCAD_ABLATION_CONFIG:
        cfg = SQCAD_ABLATION_CONFIG[policy]
        if policy_requires_dense(policy) and dense_ws is None:
            return None
        if feats is None:
            feats = trace_features(msgs)
        return _sqcad_engine(msgs, tasks, policy, feats, dense_ws=dense_ws)
    raise KeyError(policy)


# ---------------------------------------------------------------------------
# evaluation (gold used only here)
# ---------------------------------------------------------------------------

def evaluate_trace(res: PolicyResult, trace: Trace,
                   visible_ids: set) -> Dict[str, Any]:
    """Objective metrics of one policy result on one trace.  Gold needed
    ids enter ONLY here."""
    by = {m.msg_id: m for m in trace.msgs}
    needed_visible_by_task = {}
    n_masked_needed = 0
    for t in trace.tasks:
        nv = [mid for mid in t.needed_ids if mid in visible_ids]
        needed_visible_by_task[t.task_id] = nv
        n_masked_needed += len(t.needed_ids) - len(nv)

    rows: List[Dict] = []
    for t in trace.tasks:
        needed = needed_visible_by_task[t.task_id]
        ws = set(res.workspaces[t.task_id])
        # tasks whose needed evidence is entirely masked/missing carry no
        # objective target: excluded from hit/recall (None), tokens still
        # priced (the policy did pay for the workspace)
        if needed:
            hit = int(any(mid in ws for mid in needed))
            recall = len(ws & set(needed)) / len(needed)
        else:
            hit = None
            recall = None
        packed = res.context_texts.get(t.task_id)
        tokens = (sum(len(clean_tokens(s)) for s in packed)
                  if packed is not None else
                  sum(len(by[mid].tokens) for mid in ws if mid in by))
        rows.append({"task_id": t.task_id, "scope": t.scope,
                     "n_needed_visible": len(needed),
                     "hit": hit, "recall": recall,
                     "tokens": tokens,
                     "exposed": list(res.workspaces[t.task_id])})

    hits = [r["hit"] for r in rows if r["hit"] is not None]
    recalls = [r["recall"] for r in rows if r["recall"] is not None]
    hit_rate = statistics.mean(hits) if hits else None
    recall_mean = statistics.mean(recalls) if recalls else None
    tokens_mean = (statistics.mean(r["tokens"] for r in rows) if rows
                   else 0.0)

    # rare-positive recall (needed turns in rare sessions); traces without
    # any rare-needed turn carry no target for this metric
    rare = _rare_sessions(trace.msgs)
    rare_needed = {mid for t in trace.tasks for mid in
                   needed_visible_by_task[t.task_id]
                   if mid in by and by[mid].session_id in rare}
    rare_recall = (sum(1 for mid in rare_needed
                       if any(mid in res.workspaces[t.task_id]
                              for t in trace.tasks))
                   / len(rare_needed)) if rare_needed else None

    # temporal consistency: knowledge-update subset (LME scope strings)
    ku = [r for r in rows if r["scope"] == "knowledge-update"
          and r["recall"] is not None]
    ku_recall = (statistics.mean(r["recall"] for r in ku) if ku else None)
    ku_hit = (statistics.mean(r["hit"] for r in ku) if ku else None)

    # stale distractor exposure on the knowledge-update subset: a visible
    # turn from another session, later than a needed turn, sharing >=3
    # content tokens, present in the workspace
    distractor_exposed = distractor_pool = 0
    for t in trace.tasks:
        if t.scope != "knowledge-update":
            continue
        needed = needed_visible_by_task[t.task_id]
        ws = set(res.workspaces[t.task_id])
        for mid in needed:
            n = by.get(mid)
            if n is None:
                continue
            n_toks = set(n.tokens)
            for o in trace.msgs:
                if o.session_id == n.session_id or o.date_idx <= n.date_idx:
                    continue
                if len(n_toks & set(o.tokens)) >= CONFLICT_OVERLAP:
                    distractor_pool += 1
                    if o.msg_id in ws:
                        distractor_exposed += 1
    distractor_rate = (distractor_exposed / distractor_pool
                       if distractor_pool else None)

    return {
        "trace_id": trace.sample_id,
        "n_tasks": len(rows),
        "hit_rate": hit_rate,
        "recall_mean": recall_mean,
        "tokens_mean": tokens_mean,
        "rare_recall": rare_recall,
        "ku_recall": ku_recall,
        "ku_hit": ku_hit,
        "distractor_rate": distractor_rate,
        "storage_tokens": res.storage_tokens,
        "authorized_storage_tokens": res.storage_tokens,
        "physical_storage_tokens": res.physical_storage_tokens,
        "physical_storage_semantics": res.physical_storage_semantics,
        "lifecycle": dict(res.lifecycle),
        "n_masked_needed": n_masked_needed,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# LoCoMo QA: extractive reader + official-metric mirrors (in-repo tests)
# ---------------------------------------------------------------------------

def _sentence_reader(question: str, workspace: Tuple[str, ...],
                     by: Dict[str, TraceMsg],
                     context_texts: Optional[Tuple[str, ...]] = None,
                     reader_mode: str = "overlap") -> str:
    """Deterministic extractive reader (no generation model): top-3 turns
    by BM25; among their sentences pick the one with the largest token
    overlap with the question; fallback to the top turn's first sentence."""
    if not workspace:
        return ""
    q = set(clean_tokens(question))
    pool = [by[mid] for mid in workspace if mid in by]
    if not pool:
        return ""
    scores = bm25_scores(pool, clean_tokens(question))
    top = sorted(pool, key=lambda m: (-scores[m.msg_id], m.msg_id))[:3]
    best, best_signal = "", float("-inf")
    if context_texts is not None:
        sentence_groups = [context_texts]
    else:
        sentence_groups = [tuple(SENT_RE.split(m.content)) for m in top]
    all_sentences = [s.strip() for group in sentence_groups for s in group
                     if s.strip()]
    for sentences in sentence_groups:
        for sent in sentences:
            if reader_mode in {"answerability", "answerability_abstain",
                               "answerability_structured"}:
                signal = _sentence_answerability(
                    question, sent, all_sentences,
                    suppress_question_echo=(reader_mode ==
                                             "answerability_structured"))
            else:
                signal = float(len(q & set(clean_tokens(sent))))
            if signal > best_signal:
                best, best_signal = sent, signal
    if reader_mode == "answerability_abstain" and best_signal <= 0.0:
        return "No information available"
    if best:
        return best.strip()
    first = SENT_RE.split(top[0].content)
    return first[0].strip() if first else ""


def locomo_predictions(res: PolicyResult, trace: Trace,
                       qa_meta: Dict[str, Dict]) -> List[Dict]:
    """QA predictions under the frozen extractive reader.  `qa_meta` maps
    task_id -> {answer, category, evidence} straight from the dataset file;
    policies never see those fields at decision time."""
    by = {m.msg_id: m for m in trace.msgs}
    out = []
    for t in trace.tasks:
        meta = qa_meta.get(t.task_id, {})
        out.append({
            "sample_id": trace.sample_id,
            "question": t.question,
            "answer": meta.get("answer"),
            "category": meta.get("category"),
            "evidence": meta.get("evidence", []),
            "prediction": _sentence_reader(
                t.question, res.workspaces[t.task_id], by,
                res.context_texts.get(t.task_id), res.reader_mode),
            # official recall needs a non-empty list; a sentinel dia id
            # never matches any evidence id (recall 0 for empty workspaces)
            "prediction_context": list(res.workspaces[t.task_id])
            or ["D__none__"],
        })
    return out


def write_locomo_qa_files(pairs: Sequence[Tuple[Trace, PolicyResult]],
                          qa_meta: Dict[str, Dict], out_dir: Path) -> None:
    """One prediction file per policy, covering ALL traces (accumulated
    across the batch, not overwritten per trace)."""
    blocks: Dict[str, List[Dict]] = defaultdict(list)
    for trace, res in pairs:
        blocks[res.policy].append(
            {"sample_id": trace.sample_id,
             "rows": locomo_predictions(res, trace, qa_meta)})
    out_dir.mkdir(parents=True, exist_ok=True)
    for pol, b in blocks.items():
        (out_dir / f"predictions_{pol}.json").write_text(
            json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")


def mirror_f1_score(prediction: str, ground_truth: str) -> float:
    """In-repo mirror of the official LoCoMo token-F1 (evaluation.py:
    normalize -> Porter-stem -> counter intersection).  The official file
    remains the authoritative scorer (cross-checked at run time)."""
    from nltk.stem import PorterStemmer  # lazy: optional dependency
    ps = PorterStemmer()

    def normalize(s: str) -> str:
        s = s.replace(",", "")
        s = re.sub(r"\b(a|an|the|and)\b", " ", s)
        s = " ".join(s.split())
        return re.sub(r"[^a-z0-9 ]", "", s.lower())

    pt = [ps.stem(w) for w in normalize(prediction).split()]
    gt = [ps.stem(w) for w in normalize(ground_truth).split()]
    common = Counter(pt) & Counter(gt)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    p = num_same / len(pt) if pt else 0.0
    r = num_same / len(gt) if gt else 0.0
    return (2 * p * r) / (p + r) if p + r > 0 else 0.0


def mirror_locomo_f1(prediction: str, ground_truth: str, category: int
                     ) -> float:
    """Mirror of the official per-category aggregation (evaluation.py):
    category 1 splits multi-answers on commas; category 3 takes the first
    sub-answer; category 5 is the adversarial binary check."""
    if category == 1:
        preds = [p.strip() for p in prediction.split(",")]
        gts = [g.strip() for g in ground_truth.split(",")]
        return statistics.mean(
            max(mirror_f1_score(p, g) for p in preds) for g in gts)
    if category == 5:
        out = prediction.lower()
        return 1.0 if ("no information available" in out
                       or "not mentioned" in out) else 0.0
    if category == 3:
        ground_truth = ground_truth.split(";")[0].strip()
    return mirror_f1_score(prediction, ground_truth)


# ---------------------------------------------------------------------------
# aggregation + significance
# ---------------------------------------------------------------------------

METRIC_KEYS = ("hit_rate", "recall_mean", "tokens_mean", "rare_recall",
               "ku_recall", "distractor_rate", "storage_tokens",
               "authorized_storage_tokens", "physical_storage_tokens")


def aggregate(policy: str, evals: List[Dict]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"policy": policy, "n_units": len(evals)}
    for key in METRIC_KEYS:
        vals = [e[key] for e in evals if e[key] is not None]
        out[key] = {"mean": statistics.mean(vals) if vals else None,
                    "n": len(vals)}
    out["lifecycle_mean"] = {
        k: statistics.mean([e["lifecycle"][k] for e in evals]) if evals
        else 0.0
        for k in ("archives", "restores", "probes", "fallbacks")}
    out["n_masked_needed_total"] = sum(e["n_masked_needed"] for e in evals)
    return out


def significance(per_policy_evals: Dict[str, List[Dict]],
                 metric: str,
                 pairs: Sequence[Tuple[str, str]],
                 ) -> Dict[str, Dict]:
    """Paired bootstrap (studentized, n_boot=2000, seed pre-registered) of
    the per-sample metric differences.  Units are samples/conversations."""
    out: Dict[str, Dict] = {}
    for a, b in pairs:
        ea = [e[metric] for e in per_policy_evals[a] if e[metric] is not None]
        eb = [e[metric] for e in per_policy_evals[b] if e[metric] is not None]
        if len(ea) < 2 or len(ea) != len(eb):
            out[f"{a}_vs_{b}"] = {"mean_diff": None,
                                  "note": "unit mismatch or n<2"}
            continue
        ci = paired_seed_diff_ci(ea, eb, n_boot=N_BOOT, seed=BOOT_SEED,
                                 alpha=ALPHA, method="studentized")
        ci["significant"] = bool(ci["ci_low"] > 0.0 or ci["ci_high"] < 0.0)
        out[f"{a}_vs_{b}"] = ci
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load(name: str, path: Path, limit: Optional[int]):
    if name == "longmemeval_s":
        return load_longmemeval_s(path, limit)
    return load_locomo(path, limit)


def _qa_meta_by_task(name: str, path: Path) -> Dict[str, Dict]:
    """LoCoMo: task_id -> {answer, category, evidence} from the raw file
    (needed only to hand the official scorer its input fields)."""
    meta: Dict[str, Dict] = {}
    if name != "locomo":
        return meta
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for sample in data:
        for q_idx, qa in enumerate(sample.get("qa", [])):
            meta[f"{sample['sample_id']}:q{q_idx}"] = {
                "answer": qa.get("answer"),
                "category": qa.get("category"),
                "evidence": qa.get("evidence", []),
            }
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--longmemeval", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/"
                                     "LongMemEval/longmemeval_s_cleaned.json"))
    parser.add_argument("--locomo", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/datasets/"
                                     "LoCoMo/locomo10.json"))
    parser.add_argument("--dense-cache", type=Path, default=None,
                        help="dense workspace cache from "
                             "tools/precompute_dense.py (JSON)")
    parser.add_argument("--policies", default=",".join(ALL_POLICIES))
    parser.add_argument("--datasets", default="longmemeval_s,locomo",
                        help="comma-separated subset of the two datasets")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path,
                        default=Path("results/public_unified_contract.json"))
    parser.add_argument("--qa-out-dir", type=Path, default=None,
                        help="if set, write LoCoMo QA prediction files per "
                             "policy for the official scorer")
    args = parser.parse_args()

    policies = [p.strip() for p in args.policies.split(",") if p.strip()]
    dense_cache: Dict[str, Dict[str, Tuple[str, ...]]] = {}
    if args.dense_cache is not None and args.dense_cache.exists():
        loaded = json.loads(args.dense_cache.read_text(encoding="utf-8"))
        dense_cache = loaded.get("cache", loaded)

    result: Dict[str, Any] = {
        "config": {
            "budget": BUDGET, "half_life": HALF_LIFE,
            "conflict_overlap": CONFLICT_OVERLAP,
            "conflict_bonus": CONFLICT_BONUS,
            "attenuation": ATTENUATION, "rare_floor": RARE_FLOOR,
            "probe_budget_per_task": PROBE_BUDGET_PER_TASK,
            "n_boot": N_BOOT, "boot_seed": BOOT_SEED,
            "policies": policies,
            "chronological_mask": True,
            "qa_reader": "extractive sentence reader (no generation model)",
        },
        "datasets": {},
    }

    want = {d.strip() for d in args.datasets.split(",") if d.strip()}
    datasets = [
        ("longmemeval_s", args.longmemeval),
        ("locomo", args.locomo),
    ]
    for name, path in datasets:
        if name not in want:
            continue
        traces = _load(name, path, args.limit)
        if not traces:
            continue
        qa_meta = _qa_meta_by_task(name, path)
        ds_out: Dict[str, Any] = {
            "n_traces": len(traces),
            "mask": {},
            "policies": {},
            "significance": {},
        }
        evals: Dict[str, List[Dict]] = {}
        qa_pairs: List[Tuple[Trace, PolicyResult]] = []
        for trace in traces:
            masked, meta = (mask_lme_chronological(trace)
                            if name == "longmemeval_s"
                            else (trace, {}))
            visible_ids = {m.msg_id for m in masked.msgs}
            for key, val in meta.items():
                ds_out["mask"][key] = ds_out["mask"].get(key, 0) + val
            feats = trace_features(masked.msgs)  # once per trace, shared
            for pol in policies:
                dense_ws = dense_cache.get(trace.sample_id)
                if policy_requires_dense(pol) and dense_ws is None:
                    continue  # skipped: cache missing
                res = run_policy(pol, masked, dense_ws=dense_ws, feats=feats)
                if res is None:
                    continue
                # Preserve the canonical named-baseline label in artifacts;
                # the dispatcher executes its explicitly documented proxy.
                res.policy = pol
                evals.setdefault(pol, []).append(
                    evaluate_trace(res, masked, visible_ids))
                if name == "locomo" and args.qa_out_dir:
                    qa_pairs.append((masked, res))
        if name == "locomo" and args.qa_out_dir and qa_pairs:
            write_locomo_qa_files(qa_pairs, qa_meta, Path(args.qa_out_dir))

        for pol in policies:
            if pol in evals:
                ds_out["policies"][pol] = aggregate(pol, evals[pol])
            else:
                ds_out["policies"][pol] = {"policy": pol, "skipped": True}

        # pre-registered comparisons: sqcad vs every R1 row, vs the R2
        # structural rows, and sqcad vs its ablations
        pairs: List[Tuple[str, str]] = []
        for b in R1_POLICIES + R2_POLICIES:
            if b in evals and "sqcad" in evals:
                pairs.append(("sqcad", b))
        for ab in SQCAD_ABLATIONS:
            if ab in evals and "sqcad" in evals:
                pairs.append(("sqcad", ab))
        for variant in SQCAD_VARIANTS:
            if variant in evals:
                for baseline in ("sqcad", "bm25", "keep_all"):
                    if baseline in evals:
                        pairs.append((variant, baseline))
        for metric in METRIC_KEYS:
            ds_out["significance"][metric] = significance(evals, metric,
                                                          pairs)
        result["datasets"][name] = ds_out
        print(f"== {name} ==")
        for pol in policies:
            if pol not in evals:
                print(f"  {pol:36s} SKIPPED (dense cache missing)")
                continue
            agg = ds_out["policies"][pol]
            print(f"  {pol:36s} hit={agg['hit_rate']['mean']:.3f} "
                  f"recall={agg['recall_mean']['mean']:.3f} "
                  f"tok={agg['tokens_mean']['mean']:.1f} "
                  f"store={agg['storage_tokens']['mean']:.0f} "
                  f"P/R/A={agg['lifecycle_mean']['probes']:.1f}/"
                  f"{agg['lifecycle_mean']['restores']:.1f}/"
                  f"{agg['lifecycle_mean']['archives']:.1f}")

    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")


if __name__ == "__main__":
    main()
