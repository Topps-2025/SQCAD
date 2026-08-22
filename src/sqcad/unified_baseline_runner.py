"""Unified-contract baseline runner (Gate 1, M1 migration table).

The reviewer's requirement: the baseline comparison is not "run more
baselines" but a TWO-LAYER comparison --

  * original-protocol table: R0-R3 status per baseline, proving the
    baselines are not misimplemented (or stating `not reproduced` with the
    reason);
  * unified-contract main table: governance strategies transported onto ONE
    shared contract (same candidate stream, task sequence, workspace budget,
    evaluator, seeds), with explicit transportability labels.

Every entry in BASELINE_SPECS records the paper rule, the repo/commit
identity, the exact translation to the shared stream, and whether the
transport is faithful ("transportable"), an estimand-faithful simplification
("proxy", with the omitted component named), or impossible under the
protocol ("not_transportable", no numbers claimed).

End-to-end systems that need interactive LLM endpoints (SimpleMem salience,
Oblivion LLM uncertainty, SAGE oracles, Trivium probing) are NOT squeezed
into one module: their governance RULE is transported where the rule is a
deterministic function of the shared stream, and the LLM/probe layer is
written down as not transported.  This follows the review's instruction:
"若完整系统无法公平迁移，应写为 not reproduced 或 not transportable under
the unified protocol，不能用弱 proxy 替代后宣称胜过该系统。"
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .unified_agent_memory_runner import (
    Candidate, EFFECTS, Task, build_episode, canonical_hash,
)

try:
    from .causal_memory_store import CausalMemoryStore
except ImportError:  # pragma: no cover - direct script compatibility
    from causal_memory_store import CausalMemoryStore

# ---------------------------------------------------------------------------
# Baseline registry: paper rule -> shared-stream translation -> transport
# ---------------------------------------------------------------------------

GROUP1 = "1-simple-controls"
GROUP2 = "2-governance"
GROUP3 = "3-closest-theory"
GROUPF = "framework"

BASELINE_SPECS: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------- group 1
    "no_memory": {
        "group": GROUP1,
        "label": "No-memory",
        "paper": "internal control",
        "repo": "-",
        "rule": "no persistent memory; nothing is exposed",
        "translation": "expose the empty workspace every step",
        "transportability": "transportable",
        "transport_note": "trivial control; defines the zero-memory baseline",
    },
    "keep_all": {
        "group": GROUP1,
        "label": "Keep-all (no governance)",
        "paper": "internal control",
        "repo": "-",
        "rule": "everything is retained and exposed; no forgetting",
        "translation": "expose the full candidate stream every step; token "
                       "cost is recorded without the budget cap (this is the "
                       "'bigger context' control, not a budgeted policy)",
        "transportability": "transportable",
        "transport_note": "exceeds the shared workspace budget BY DESIGN: its "
                          "purpose is to price the no-governance context cost",
    },
    "fifo": {
        "group": GROUP1,
        "label": "FIFO",
        "paper": "internal control",
        "repo": "-",
        "rule": "first-written memories evicted first; fixed capacity",
        "translation": "retain the first `budget` candidates of the stream "
                       "(write order), never reorder",
        "transportability": "transportable",
        "transport_note": "no write/evict churn in the static stream, so FIFO "
                          "is the static first-budget set",
    },
    "lru": {
        "group": GROUP1,
        "label": "LRU",
        "paper": "internal control",
        "repo": "-",
        "rule": "least-recently-accessed memories evicted first",
        "translation": "dynamic: last_access updated on exposure; retain the "
                       "top-`budget` by access recency",
        "transportability": "transportable",
        "transport_note": "dynamic counterpart of static recency; access "
                          "events are the exposure rows of the shared log",
    },
    "recency": {
        "group": GROUP1,
        "label": "Recency",
        "paper": "internal control",
        "repo": "-",
        "rule": "most recent memories first",
        "translation": "rank by stream last_access (static), top-`budget`",
        "transportability": "transportable",
        "transport_note": "the smoke-runner policy, unchanged",
    },
    "fixed_decay": {
        "group": GROUP1,
        "label": "Fixed exponential decay",
        "paper": "internal control",
        "repo": "-",
        "rule": "score = exp(-age / tau), fixed tau",
        "translation": "score = exp(-age/25) with age = max(last_access) - "
                       "last_access; top-`budget`",
        "transportability": "transportable",
        "transport_note": "tau=25 matches the smoke runner's fade_like",
    },
    "frequency_decay": {
        "group": GROUP1,
        "label": "Frequency decay",
        "paper": "internal control",
        "repo": "-",
        "rule": "score = frequency x decay(age)",
        "translation": "score = log1p(frequency) x exp(-age/50); top-`budget`",
        "transportability": "transportable",
        "transport_note": "frequency-only governance",
    },
    "bm25": {
        "group": GROUP1,
        "label": "BM25 retrieval",
        "paper": "LongMemEval official BM25",
        "repo": "LongMemEval (upstream, frozen); R3 status: benchmark layer",
        "rule": "lexical retrieval: BM25(query, content), top-k",
        "translation": "per-task BM25 over the shared content_tokens vs "
                       "query_tokens; top-`budget`; NO persistent governance",
        "transportability": "transportable",
        "transport_note": "retriever-only control: rules out 'just a better "
                          "retriever' explanations; official BM25 R3 numbers "
                          "are a benchmark-layer item, not a governance one",
    },
    "dense": {
        "group": GROUP1,
        "label": "Dense retrieval",
        "paper": "embedding retriever control",
        "repo": "-",
        "rule": "semantic similarity retrieval, top-k",
        "translation": "per-task cosine over shared semantic embeddings "
                       "(deterministic function of the semantic label, "
                       "including mislabeled candidates); top-`budget`; NO "
                       "persistent governance",
        "transportability": "transportable",
        "transport_note": "retriever-only control; embeddings are part of the "
                          "shared stream (same for every policy)",
    },
    "rrf": {
        "group": GROUP1,
        "label": "BM25+dense RRF",
        "paper": "rank fusion control",
        "repo": "-",
        "rule": "reciprocal rank fusion of BM25 and dense lists",
        "translation": "rrf(k=60) over the two per-task rank lists; "
                       "top-`budget`; NO persistent governance",
        "transportability": "transportable",
        "transport_note": "retriever-only control",
    },
    # -------------------------------------------------------------- group 2
    "memory_worth": {
        "group": GROUP2,
        "label": "Memory Worth",
        "paper": "Simsek 2026 (arXiv); trust/suppression from success-failure "
                 "co-occurrence; success signal is EXPLICITLY associational",
        "repo": "no verified official implementation on record -> R1 pending",
        "rule": "score = Beta(1,1) posterior of success given exposure "
                "(associational)",
        "translation": "score = posterior success_rate with implicit 100-"
                       "exposure history; top-`budget`",
        "transportability": "proxy",
        "transport_note": "MW-shaped associational score only: this runner "
                          "uses the stream's success_rate / implicit history, "
                          "not the paper's per-memory success/failure counters "
                          "conditioned on actual retrieval.  Not reproduced "
                          "as the full method; use only as an associational "
                          "control.",
    },
    "oblivion": {
        "group": GROUP2,
        "label": "Oblivion",
        "paper": "Rana et al. 2026 (arXiv:2604.00131): decay-driven "
                 "activation; R = exp(-t/(S*T)), S = utility + "
                 "access_frequency, T temperature",
        "repo": "official repo frozen at b2512f9c (R1 ok); R2 env pending; "
                "R3 not reproduced (needs OpenAI endpoint)",
        "rule": "retention = Ebbinghaus decay refreshed by exposure; "
                "uncertainty-modulated activation",
        "translation": "dynamic: age in stream units, S = success_rate + "
                       "frequency/max_frequency, T=3 (paper default for "
                       "isolated benchmarks); retain top-`budget`; exposure "
                       "refreshes age",
        "transportability": "transportable",
        "transport_note": "the LLM uncertainty tier (Decayer) is not "
                          "transportable offline -> the transported rule is "
                          "the paper's core decay equation (functional "
                          "description Section 5); the LLM tier is not "
                          "reproduced, stated explicitly, not silently "
                          "omitted from the claim",
    },
    "fademem": {
        "group": GROUP2,
        "label": "FadeMem",
        "paper": "Wei et al. 2026 (arXiv:2601.18642): differential decay from "
                 "semantic relevance, access frequency and temporal patterns",
        "repo": "official Agent Memory implementation NOT verified on record "
                "-> R1 pending; a same-named video-diffusion repo was "
                "rejected as identity mismatch",
        "rule": "accessibility = f(relevance, frequency, recency) with "
                "differential decay rates",
        "translation": "score = log1p(frequency) x exp(-age / tau_sem) with "
                       "tau_sem = 20 + 40 x semantic_confidence (confident "
                       "memories decay slower); dynamic age refresh on "
                       "exposure",
        "transportability": "proxy",
        "transport_note": "the paper's exact decay parameterization is not "
                          "available (official implementation unverified); "
                          "this is a named differential-decay proxy, NOT a "
                          "claim of reproducing FadeMem",
    },
    "simplemem": {
        "group": GROUP2,
        "label": "SimpleMem",
        "paper": "Wang et al. 2026: write-time salience + retrieval gating",
        "repo": "paper-release commit 16912523 frozen (R1 ok); R2/R3 need "
                "LoCoMo + GPT-4.1-mini/Qwen + Qwen3-Embedding-0.6B -> not "
                "reproduced offline",
        "rule": "memories enter long-term memory by salience at write time; "
                "gated retrieval",
        "translation": "salience = semantic_confidence x success_rate; "
                       "retain top-`budget` above threshold (gating, not "
                       "continuous ranking)",
        "transportability": "proxy",
        "transport_note": "LLM-computed salience is not transportable "
                          "offline; the transported rule is the salience-"
                          "gated retention structure with the stream's "
                          "semantic signal; not reproduced as the full system",
    },
    "demem": {
        "group": GROUP2,
        "label": "DeMem",
        "paper": "Zou et al. 2026: compression preserving distinctions that "
                 "affect downstream decisions",
        "repo": "official implementation NOT verified on record -> R1 pending",
        "rule": "compress away memories whose removal does not change "
                "expected downstream outcomes; keep decision-relevant "
                "distinctions",
        "translation": "score = |group_effect_lcb - mean_group_effect_lcb| "
                       "(distinction from the aggregate); top-`budget` keeps "
                       "the most decision-relevant groups, neutral groups "
                       "compress away",
        "transportability": "proxy",
        "transport_note": "internal distinction heuristic transported onto "
                          "effect estimates.  It does not implement DeMem's "
                          "certified decision-conflict partition learner or "
                          "rate-distortion boundary; named proxy only.",
    },
    "sage": {
        "group": GROUP2,
        "label": "SAGE",
        "paper": "interactive-guidance memory system",
        "repo": "not on record",
        "rule": "interactive oracle guidance",
        "translation": "none",
        "transportability": "not_transportable",
        "transport_note": "requires an interactive oracle outside the shared "
                          "protocol; per the review: not transportable under "
                          "the unified protocol, no numbers claimed",
    },
    # -------------------------------------------------------------- group 3
    "causal_item": {
        "group": GROUP3,
        "label": "CMI-style local causal effect",
        "paper": "Causal Memory Intervention (Srivastava 2026): controlled "
                 "perturbations for query-time selection",
        "repo": "simplified implementation used in gap-proof experiments "
                "(estimation-validity use, not full system reproduction)",
        "rule": "select by the query-local causal do-effect of exposure",
        "translation": "score = item_effect_lcb (the shared stream's "
                       "per-item do-effect estimate); top-`budget`",
        "transportability": "proxy",
        "transport_note": "local-effect estimand control only.  CMI's "
                          "official three-condition no/with/perturbed LLM "
                          "intervention pipeline is not run here; full CMI "
                          "system not reproduced.",
    },
    "trivium": {
        "group": GROUP3,
        "label": "Trivium",
        "paper": "Chang 2026 (arXiv:2606.04421): temporal regret as a "
                 "first-class objective; persistent causal evidence + "
                 "explicit probing",
        "repo": "arXiv preprint; no official repo on record -> R1 pending",
        "rule": "retain memories by discounted temporal regret of their "
                "absence",
        "translation": "score = effect x demand(semantic_group) with "
                       "demand(g) = sum_t gamma^t P(required=g at t) from "
                       "the shared task distribution; item effect used when "
                       "identified, group effect otherwise",
        "transportability": "proxy",
        "transport_note": "demand-weighted effect control only.  It does not "
                          "implement Trivium's persistent causal log, temporal/"
                          "epistemic regret ledger, detectability assumptions, "
                          "or its budgeted causal probes.",
    },
    "memaudit": {
        "group": GROUP3,
        "label": "MemAudit",
        "paper": "Tan et al. 2026: replay-based attribution for harmful-"
                 "memory diagnosis",
        "repo": "not on record",
        "rule": "retrospective attribution audit, not a retention policy",
        "translation": "none",
        "transportability": "not_transportable",
        "transport_note": "capability boundary: attribution diagnosis is "
                          "orthogonal to the unified retention contract; "
                          "listed so the local-causal/attribution space is "
                          "not mislabeled as a blank",
    },
    "gatemem": {
        "group": GROUP3,
        "label": "GateMem",
        "paper": "Ren et al. 2026 (arXiv:2606.18829): memory governance in "
                 "multi-principal shared-memory agents",
        "repo": "benchmark paper; not on record as a retention strategy",
        "rule": "multi-principal governance benchmark",
        "translation": "none",
        "transportability": "not_transportable",
        "transport_note": "capability boundary: multi-principal access "
                          "control benchmark, not a single-agent retention "
                          "strategy under this protocol",
    },
    # ------------------------------------------------------------- framework
    "risk_gated_decomp_abstract": {
        "group": GROUPF,
        "label": "SQCAD (evidence-qualification-access)",
        "paper": "this paper",
        "repo": "src/sqcad (this repository)",
        "rule": "item-level effect with group fallback when the item is "
                "unidentified; harm veto; confidence gate",
        "translation": "the smoke runner's risk_gated_decomp_abstract "
                       "scoring, evaluated under the same contract",
        "transportability": "transportable",
        "transport_note": "framework row; qualification threshold and probe "
                          "budget are fixed by the shared contract",
    },
}

# ---------------------------------------------------------------------------
# Retrieval primitives (shared inputs: content_tokens / query_tokens /
# semantic labels — identical for every policy)
# ---------------------------------------------------------------------------

K1, B = 1.5, 0.75
RRF_K = 60


def _bm25_scores(candidates: Sequence[Candidate], query_tokens: Sequence[str],
                 ) -> Dict[str, float]:
    if not query_tokens:
        return {c.memory_id: 0.0 for c in candidates}
    df: Dict[str, int] = {}
    lens = [len(c.content_tokens) for c in candidates]
    avgdl = mean(lens) if lens else 1.0
    for c in candidates:
        for t in set(c.content_tokens):
            df[t] = df.get(t, 0) + 1
    n = max(len(candidates), 1)
    scores: Dict[str, float] = {}
    for c in candidates:
        tf: Dict[str, int] = {}
        for t in c.content_tokens:
            tf[t] = tf.get(t, 0) + 1
        dl = max(len(c.content_tokens), 1)
        s = 0.0
        for t in query_tokens:
            if t not in tf:
                continue
            idf = math.log(1.0 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
            s += idf * (tf[t] * (K1 + 1.0)) / (
                tf[t] + K1 * (1.0 - B + B * dl / avgdl))
        scores[c.memory_id] = s
    return scores


def _dense_scores(candidates: Sequence[Candidate], task: Task,
                  emb: Dict[str, List[float]]) -> Dict[str, float]:
    if not task.query_tokens:
        return {c.memory_id: 0.0 for c in candidates}
    q = emb.get(task.query_tokens[0], [1.0, 0.0, 0.0, 0.0])
    scores: Dict[str, float] = {}
    for c in candidates:
        key = c.semantic_group
        v = emb.get(f"tok_{key}", [0.0, 0.0, 0.0, 1.0])
        dot = sum(a * b for a, b in zip(q, v))
        nq = math.sqrt(sum(x * x for x in q)) or 1.0
        nv = math.sqrt(sum(x * x for x in v)) or 1.0
        scores[c.memory_id] = dot / (nq * nv)
    return scores


def _rrf_scores(bm25: Dict[str, float], dense: Dict[str, float],
                candidates: Sequence[Candidate]) -> Dict[str, float]:
    ids = [c.memory_id for c in candidates]
    b_rank = {mid: i for i, mid in enumerate(
        sorted(ids, key=lambda m: bm25[m], reverse=True))}
    d_rank = {mid: i for i, mid in enumerate(
        sorted(ids, key=lambda m: dense[m], reverse=True))}
    return {mid: (1.0 / (RRF_K + 1 + b_rank[mid])
                  + 1.0 / (RRF_K + 1 + d_rank[mid])) for mid in ids}


def _shared_embeddings() -> Dict[str, List[float]]:
    groups = ("rare_critical", "common_useful", "stale", "noise")
    emb: Dict[str, List[float]] = {}
    for i, g in enumerate(groups):
        vec = [0.0] * 4
        vec[i] = 1.0
        emb[f"tok_{g}"] = vec
    return emb


# ---------------------------------------------------------------------------
# Per-policy engines.  Every engine returns (exposed_ids_by_step, lifecycle)
# where lifecycle counts archive/restore/rollback/probe actions.
# ---------------------------------------------------------------------------

def _top_budget(ranked: List[Candidate], budget: int) -> List[str]:
    return [c.memory_id for c in ranked[:budget]]


def _probe_qualification(policy: str, candidates: Sequence[Candidate],
                         probe_budget: int, rng: random.Random,
                         ) -> Tuple[Dict[str, float], int]:
    """Gate 4 probe layer: qualification-time probing of archived candidates
    with unidentified item effects.  Each probe pays one unit of the probe
    budget and resolves the item effect (oracle: the candidate's true-group
    effect plus stream evidence noise).  Which policies probe, and whom:
      risk_gated_decomp_abstract / causal_item - unidentified item effects
      trivium - unidentified OR low-magnitude items (its explicit probing
                layer; the probe cost now lives here, per the Gate 1 note)
      all other transports - no probing (their papers' probing is either
                absent or an LLM tier already labeled not reproduced)
    """
    if probe_budget <= 0 or policy not in (
            "risk_gated_decomp_abstract", "causal_item", "trivium"):
        return {}, 0
    if policy == "trivium":
        pool = [c for c in candidates
                if c.item_effect_lcb <= -1e5 or abs(c.item_effect_lcb) < 0.2]
    else:
        pool = [c for c in candidates if c.item_effect_lcb <= -1e5]
    rng.shuffle(pool)
    state: Dict[str, float] = {}
    for c in pool[:probe_budget]:
        state[c.memory_id] = EFFECTS[c.true_group] + rng.gauss(0.0, 0.10)
    return state, len(state)


def _resolved_item(c: Candidate, probe_state: Dict[str, float]) -> float:
    """The item effect a policy can act on: the stream estimate when
    identified, otherwise the probe-resolved oracle value."""
    if c.item_effect_lcb > -1e5:
        return c.item_effect_lcb
    return probe_state.get(c.memory_id, c.item_effect_lcb)


def _gated_score(c: Candidate, probe_state: Dict[str, float]) -> float:
    """The gated framework score (probe-aware): resolved item evidence with
    group fallback when the item stays unidentified, sign-conflict and harm
    veto.  Mirrors policy_score in the smoke runner, with probe_state
    standing in for qualification evidence."""
    item = _resolved_item(c, probe_state)
    item_estimable = item > -1e5
    sign_conflict = item_estimable and (
        (c.group_effect_lcb > 0.0 > item)
        or (item > 0.0 > c.group_effect_lcb))
    harm_veto = item_estimable and item <= -0.25
    if c.semantic_confidence < 0.75 or sign_conflict or harm_veto:
        return item
    return c.group_effect_lcb


def _static_engine(score_fn: Callable[[Candidate], float],
                   candidates: Sequence[Candidate], tasks: Sequence[Task],
                   budget: int, keep_all: bool = False,
                   probes: int = 0,
                   ) -> Tuple[List[List[str]], Dict[str, int]]:
    ranked = sorted(candidates,
                    key=lambda c: (score_fn(c), c.memory_id), reverse=True)
    retained = _top_budget(ranked, budget)
    ids = [c.memory_id for c in candidates]
    exposed = [list(ids) if keep_all else list(retained)
               for _ in tasks]
    archived = len(ids) - (0 if keep_all else len(retained))
    return exposed, {"archives": archived, "restores": 0, "rollbacks": 0,
                     "probes": probes}


def _dynamic_engine(score_fn: Callable[[Candidate, float], float],
                    candidates: Sequence[Candidate], tasks: Sequence[Task],
                    budget: int, max_age: float, probes: int = 0,
                    ) -> Tuple[List[List[str]], Dict[str, int]]:
    """score_fn(candidate, age) with age refreshed on exposure."""
    age: Dict[str, float] = {c.memory_id: max_age - c.last_access
                             for c in candidates}
    retained: List[str] = []
    lifecycle: Dict[str, int] = {"archives": 0, "restores": 0, "rollbacks": 0,
                                 "probes": probes}
    exposed_by_step: List[List[str]] = []
    for step, task in enumerate(tasks):
        ranked = sorted(candidates,
                        key=lambda c: (score_fn(c, age[c.memory_id]),
                                       c.memory_id), reverse=True)
        new_retained = _top_budget(ranked, budget)
        for mid in new_retained:
            if mid not in retained:
                lifecycle["restores"] += 1
            age[mid] = 0.0
        for mid in retained:
            if mid not in new_retained:
                lifecycle["archives"] += 1
        retained = new_retained
        exposed_by_step.append(list(retained))
        for c in candidates:
            if c.memory_id not in retained:
                age[c.memory_id] += 1.0
    return exposed_by_step, lifecycle


def _retrieval_engine(retriever: Callable[[Sequence[Candidate], Task],
                                          Dict[str, float]],
                      candidates: Sequence[Candidate], tasks: Sequence[Task],
                      budget: int, probes: int = 0,
                      ) -> Tuple[List[List[str]], Dict[str, int]]:
    exposed_by_step: List[List[str]] = []
    for task in tasks:
        scores = retriever(candidates, task)
        ranked = sorted(candidates,
                        key=lambda c: (scores[c.memory_id], c.memory_id),
                        reverse=True)
        exposed_by_step.append(_top_budget(ranked, budget))
    return exposed_by_step, {"archives": 0, "restores": 0, "rollbacks": 0,
                             "probes": probes}


def run_policy_unified(seed: int, policy: str, group_noise: float,
                       steps: int, budget: int, probe_budget: int = 0,
                       collect_rows: Optional[List[Dict]] = None,
                       episode: Optional[Tuple[List[Candidate],
                                              List[Task]]] = None,
                       ) -> Dict[str, Any]:
    """One episode of one policy under the shared contract.

    probe_budget: Gate 4 probe contract — qualification-time probes of
    unidentified item effects (see _probe_qualification), charged in the
    returned lifecycle["probes"] and in step-0 of collect_rows.
    collect_rows: when given, per-step decision rows are appended
    (utility / tokens / stale / probes / hit) for the cost contract.
    episode: optional (candidates, tasks) pair replacing build_episode
    (Gate 4 variant worlds keep the stream identical for every policy
    within the block; the pair is generated once per seed).
    """
    if episode is None:
        candidates, tasks = build_episode(seed, group_noise, steps)
    else:
        candidates, tasks = episode
    # The stream's WRITE order must be uninformative about quality (the
    # builder emits groups in quality order, which would let FIFO win on
    # stream construction instead of on governance).  The permutation is
    # seeded and identical for every policy: part of the shared stream.
    rng = random.Random(seed * 7919 + 17)
    rng.shuffle(candidates)
    max_age = max(c.last_access for c in candidates)
    emb = _shared_embeddings()
    mid_of = {c.memory_id: c for c in candidates}

    probe_state, n_probes = _probe_qualification(
        policy, candidates, probe_budget, rng)

    if policy == "no_memory":
        exposed, lifecycle = [list() for _ in tasks], \
            {"archives": 0, "restores": 0, "rollbacks": 0, "probes": 0}
    elif policy == "keep_all":
        exposed, lifecycle = _static_engine(
            lambda c: 0.0, candidates, tasks, budget, keep_all=True)
    elif policy == "fifo":
        write_order = {c.memory_id: i for i, c in enumerate(candidates)}
        exposed, lifecycle = _static_engine(
            lambda c: -write_order[c.memory_id], candidates, tasks, budget)
    elif policy == "recency":
        exposed, lifecycle = _static_engine(
            lambda c: c.last_access, candidates, tasks, budget)
    elif policy == "lru":
        def _lru(c: Candidate, age: float) -> float:
            return -age
        exposed, lifecycle = _dynamic_engine(_lru, candidates, tasks, budget,
                                             max_age)
    elif policy == "fixed_decay":
        exposed, lifecycle = _static_engine(
            lambda c: math.exp(-(max_age - c.last_access) / 25.0),
            candidates, tasks, budget)
    elif policy == "frequency_decay":
        exposed, lifecycle = _static_engine(
            lambda c: math.log1p(c.frequency)
                      * math.exp(-(max_age - c.last_access) / 50.0),
            candidates, tasks, budget)
    elif policy == "bm25":
        exposed, lifecycle = _retrieval_engine(
            lambda cs, t: _bm25_scores(cs, t.query_tokens),
            candidates, tasks, budget)
    elif policy == "dense":
        exposed, lifecycle = _retrieval_engine(
            lambda cs, t: _dense_scores(cs, t, emb), candidates, tasks,
            budget)
    elif policy == "rrf":
        def _rrf(cs: Sequence[Candidate], t: Task) -> Dict[str, float]:
            return _rrf_scores(_bm25_scores(cs, t.query_tokens),
                               _dense_scores(cs, t, emb), cs)
        exposed, lifecycle = _retrieval_engine(_rrf, candidates, tasks, budget)
    elif policy == "memory_worth":
        # Beta(1,1) posterior with an implicit 100-exposure history; the
        # paper's success signal is associational by design.
        exposed, lifecycle = _static_engine(
            lambda c: (c.success_rate * 100.0 + 1.0) / 102.0,
            candidates, tasks, budget)
    elif policy == "oblivion":
        def _oblivion(c: Candidate, age: float) -> float:
            s = c.success_rate + c.frequency / max_age  # utility+freq (norm.)
            return math.exp(-age / (max(s, 1e-6) * 3.0))
        exposed, lifecycle = _dynamic_engine(_oblivion, candidates, tasks,
                                             budget, max_age)
    elif policy == "fademem":
        def _fade(c: Candidate, age: float) -> float:
            tau = 20.0 + 40.0 * c.semantic_confidence
            return math.log1p(c.frequency) * math.exp(-age / tau)
        exposed, lifecycle = _dynamic_engine(_fade, candidates, tasks, budget,
                                             max_age)
    elif policy == "simplemem":
        def _salience(c: Candidate) -> float:
            return c.semantic_confidence * c.success_rate
        exposed, lifecycle = _static_engine(_salience, candidates, tasks,
                                            budget)
    elif policy == "demem":
        mean_effect = mean(c.group_effect_lcb for c in candidates)
        def _distinction(c: Candidate) -> float:
            return abs(c.group_effect_lcb - mean_effect)
        exposed, lifecycle = _static_engine(_distinction, candidates, tasks,
                                            budget, probes=n_probes)
    elif policy == "causal_item":
        # probe-aware: resolved item effects enter the ranking (the CMI
        # perturbation oracle, charged to the probe contract)
        exposed, lifecycle = _static_engine(
            lambda c: _resolved_item(c, probe_state), candidates, tasks,
            budget, probes=n_probes)
    elif policy == "trivium":
        demand: Dict[str, float] = {}
        for t in tasks:
            if t.required_group == "none":
                continue
            demand[t.required_group] = demand.get(t.required_group, 0.0) + 1.0
        def _trivium(c: Candidate) -> float:
            effect = _resolved_item(c, probe_state)
            if effect <= -1e5:
                effect = c.group_effect_lcb
            return effect * demand.get(c.semantic_group, 0.0)
        exposed, lifecycle = _static_engine(_trivium, candidates, tasks,
                                            budget, probes=n_probes)
    elif policy == "risk_gated_decomp_abstract":
        # the framework row with the qualification probe: unresolved item
        # effects are probed (bounded by the contract budget) and the gated
        # decision then uses the resolved effect
        exposed, lifecycle = _static_engine(
            lambda c: _gated_score(c, probe_state), candidates, tasks,
            budget, probes=n_probes)
    elif policy in ("blind_gate", "forced_restore"):
        # Gate 4 forced-decision controls (negative lifecycle-restore
        # result, kept on purpose -- NOT rows of the main table).  Both
        # override the gate's refusal to persist access decisions where
        # lifecycle value is unidentified:
        #   blind_gate    -- decide from the raw point estimate anyway
        #                   (no group fallback, no harm veto, no probes);
        #   forced_restore-- "when in doubt, keep": every unidentified
        #                   candidate is restored to the workspace, the
        #                   gated ranking fills the remaining slots.
        if policy == "blind_gate":
            exposed, lifecycle = _static_engine(
                lambda c: c.item_effect_lcb, candidates, tasks, budget)
        else:
            def _restore_first(c: Candidate) -> float:
                if c.item_effect_lcb <= -1e5:
                    return 1e6
                return _gated_score(c, probe_state)
            exposed, lifecycle = _static_engine(
                _restore_first, candidates, tasks, budget)
    else:
        raise KeyError(f"unknown unified policy: {policy}")

    # shared evaluator (identical to the smoke runner's metric definitions)
    store = CausalMemoryStore()
    successes = required_hits = stale_exposures = total_tokens = 0
    utility_sum = 0.0
    for step, task in enumerate(tasks):
        ids = exposed[step]
        exposed_items = [mid_of[i] for i in ids]
        required_hit = task.required_group == "none" or any(
            item.true_group == task.required_group for item in exposed_items)
        stale_exposed = any(item.true_group == "stale"
                            for item in exposed_items)
        success = required_hit
        utility = float(required_hit) - 0.35 * float(stale_exposed)
        required_hits += int(required_hit)
        stale_exposures += int(stale_exposed)
        successes += int(success)
        utility_sum += utility
        step_tokens = sum(item.token_cost for item in exposed_items)
        total_tokens += step_tokens
        if collect_rows is not None:
            collect_rows.append({
                "seed": float(seed),
                "policy": policy,
                "step": float(step),
                "utility": float(required_hit),
                "tokens": float(step_tokens),
                "stale": float(stale_exposed),
                "n_exposed": float(len(ids)),
                # probes are a qualification-time cost, charged at step 0
                "probes": float(n_probes if step == 0 else 0),
            })
        adoption = {item.memory_id: item.true_group == task.required_group
                    for item in exposed_items}
        store.record_decision(
            episode_id=f"u-{seed}-{policy}",
            step=step,
            history={"task_id": task.task_id,
                     "required_group": task.required_group, "budget": budget},
            candidates=[c.memory_id for c in candidates],
            behavior_action={"policy": policy,
                             "workspace_ids": sorted(ids)},
            propensity=1.0,
            exposure={m: 1.0 for m in ids},
            adoption=adoption,
            agent_action={"type": "controlled_decision", "success": success},
            outcome={
                "success": int(success), "utility": utility,
                "required_hit": int(required_hit),
                "stale_exposed": int(stale_exposed),
            },
        )
    positives = {c.memory_id for c in candidates
                 if c.true_group in {"rare_critical", "common_useful"}}
    retained_any = {m for step_ids in exposed for m in step_ids}
    rare_ids = {c.memory_id for c in candidates
                if c.true_group == "rare_critical"}
    stream_hash = canonical_hash({
        "candidates": [asdict(c) for c in candidates],
        "tasks": [asdict(t) for t in tasks],
    })
    return {
        "policy": policy,
        "candidate_stream_sha256": stream_hash,
        "task_success_rate": successes / steps,
        "average_utility": utility_sum / steps,
        "required_evidence_recall": required_hits / steps,
        "stale_exposure_rate": stale_exposures / steps,
        "average_workspace_tokens": total_tokens / steps,
        "retained_positive_precision": (
            len(retained_any & positives) / len(retained_any)
            if retained_any else 0.0),
        "rare_critical_recall": (
            len({m for m in retained_any
                 if mid_of[m].true_group == "rare_critical"}) / 4.0),
        "decision_log_completeness": (
            len(store.decisions(f"u-{seed}-{policy}")) / steps),
        "governance_transitions": float(len(json.loads(store.audit_log()))),
        "archives": float(lifecycle["archives"]),
        "restores": float(lifecycle["restores"]),
        "rollbacks": float(lifecycle["rollbacks"]),
        "probes": float(lifecycle["probes"]),
        # low-frequency-protection quantities for the Gate 4 cost contract:
        # final-step persistent retention vs ever-retained during the episode
        "rare_kept_final": (
            float(len(set(exposed[-1]) & rare_ids)) if steps else 0.0),
        "rare_kept_ever": float(len(retained_any & rare_ids)),
    }


# ---------------------------------------------------------------------------
# Two tables
# ---------------------------------------------------------------------------

UNIFIED_METRICS = (
    "task_success_rate", "average_utility", "required_evidence_recall",
    "rare_critical_recall", "stale_exposure_rate",
    "average_workspace_tokens", "retained_positive_precision",
    "archives", "restores",
)


def build_original_protocol_table() -> List[Dict[str, Any]]:
    """R0-R3 gate status per baseline (proves non-misimplementation or
    states `not reproduced` with the reason).  Rows are registry-driven;
    the numeric statuses mirror docs/03-基线复现分级与首轮审计-20260811.md."""
    rows: List[Dict[str, Any]] = []
    for policy, spec in BASELINE_SPECS.items():
        transport = spec["transportability"]
        if transport == "not_transportable":
            verdict = "not reproduced"
            note = spec["transport_note"]
            r0 = r1 = r2 = r3 = "n/a"
        elif spec["repo"].startswith("-") and spec["group"] == GROUP1:
            verdict = "internal control"
            note = "not a published system; no reproduction gate applies"
            r0 = r1 = r2 = r3 = "n/a"
        else:
            r0 = "pass" if "frozen" in spec["repo"] or "R1 ok" in spec["repo"] \
                else "pending"
            r1 = "frozen" if "frozen" in spec["repo"] else "pending"
            r2 = "pending"
            if "R3 not reproduced" in spec["repo"] or \
                    "not reproduced offline" in spec["repo"]:
                verdict = "not reproduced"
                note = spec["transport_note"]
                r3 = "blocked"
            elif spec["group"] == GROUP2 and "R1 pending" in spec["repo"]:
                verdict = "not reproduced"
                note = spec["transport_note"]
                r3 = "blocked"
            elif spec["group"] == GROUP3 and "no official repo" in spec["repo"]:
                verdict = "not reproduced"
                note = spec["transport_note"]
                r3 = "blocked"
            else:
                verdict = "proxy"
                note = spec["transport_note"]
                r3 = "not run (offline)"
        rows.append({
            "policy": policy, "group": spec["group"],
            "label": spec["label"], "paper": spec["paper"],
            "R0": r0, "R1": r1, "R2": r2, "R3": r3,
            "verdict": verdict, "note": note,
        })
    return rows


def summarize_main_table(rows: Sequence[Dict[str, Any]],
                         seeds: int) -> Dict[str, Any]:
    table: Dict[str, Any] = {}
    by_policy: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_policy.setdefault(row["policy"], []).append(row)
    for policy in BASELINE_SPECS:
        selected = by_policy.get(policy, [])
        if not selected:
            continue
        spec = BASELINE_SPECS[policy]
        stats: Dict[str, Dict[str, float]] = {}
        for metric in UNIFIED_METRICS:
            values = [float(r[metric]) for r in selected]
            sd = stdev(values) if len(values) > 1 else 0.0
            stats[metric] = {
                "mean": mean(values), "sd": sd,
                "ci95": 1.96 * sd / len(values) ** 0.5, "n": float(len(values)),
            }
        table[policy] = {
            "label": spec["label"], "group": spec["group"],
            "transportability": spec["transportability"],
            "transport_note": spec["transport_note"],
            "metrics": stats,
        }
    return {
        "contract": {
            "shared": "candidate stream (incl. content tokens and semantic "
                      "embeddings), task sequence, workspace item budget, "
                      "evaluator (required-hit, stale penalty 0.35, token "
                      "cost), seeds, logging schema",
            "seeds": seeds,
            "not_transportable_rows": [
                p for p, s in BASELINE_SPECS.items()
                if s["transportability"] == "not_transportable"],
        },
        "rows": table,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--budget", type=int, default=12)
    parser.add_argument("--group-noise", type=float, default=0.2)
    parser.add_argument("--output", type=Path,
                        default=Path("results/unified_baseline_main.json"))
    args = parser.parse_args()

    rows: List[Dict[str, Any]] = []
    for seed in range(args.seeds):
        expected_hash = None
        for policy in BASELINE_SPECS:
            if BASELINE_SPECS[policy]["transportability"] == \
                    "not_transportable":
                continue
            row = run_policy_unified(seed, policy, args.group_noise,
                                     args.steps, args.budget)
            if expected_hash is None:
                expected_hash = row["candidate_stream_sha256"]
            if row["candidate_stream_sha256"] != expected_hash:
                raise RuntimeError("policies did not receive the same "
                                   "candidate stream")
            row.update({"seed": float(seed)})
            rows.append(row)

    result = {
        "protocol": {
            "purpose": ("Gate 1 unified-contract main table (M1); "
                        "original-protocol table is registry-driven"),
            "seeds": args.seeds, "steps_per_seed": args.steps,
            "workspace_item_budget": args.budget,
            "group_noise": args.group_noise,
            "shared": "same candidate stream, task sequence, workspace "
                      "budget, evaluator and seeds for every row",
        },
        "original_protocol_table": build_original_protocol_table(),
        "unified_main_table": summarize_main_table(rows, args.seeds),
        "per_seed_policy": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({
        "original_protocol_table": result["original_protocol_table"],
        "unified_main_table_means": {
            p: {m: v["mean"]
                for m, v in r["metrics"].items()}
            for p, r in result["unified_main_table"]["rows"].items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
