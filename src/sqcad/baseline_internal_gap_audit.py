"""Constructive, baseline-internal audit of lifecycle-score sufficiency.

This module does not compare a baseline with SQCAD.  It freezes each
baseline's own observable score, runs the same keep/archive intervention in
LifecycleBench, and asks whether a score fiber contains different lifecycle
contrasts.  Official-code surfaces, transported paper rules, and mechanism
proxies are deliberately reported as different evidence levels.

The score adapters receive ``PublicDecisionView`` rather than an episode.
That type contains no future outcome, needed-memory id, oracle action, or
lifecycle value.  A local CMI/Trivium proxy is computed from visible
decision-time relevance and correction evidence; no future rollout field
enters any baseline score.
"""

from __future__ import annotations

import dataclasses
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .lifecycle_bench.evaluator import EpisodeOutcome, evaluate
from .lifecycle_bench.frozen import ADOPT_THRESHOLD, GAMMA, TAU_TOL
from .lifecycle_bench.generator import all_episodes
from .lifecycle_bench.realizer import RealizedEpisode, overlap, tokenize
from .lifecycle_bench.rollout import PairedRollout, paired_rollout


AUDIT_VERSION = "baseline-internal-lifecycle-gap-v1"
DEFAULT_SCORE_DIGITS = 8


@dataclass(frozen=True)
class PublicDecisionView:
    """Gold-free inputs exposed to score adapters.

    ``future_demand`` uses only the declared public future query schedule.  It gives the
    Trivium proxy a transductive upper-bound demand signal; hidden
    ``needed_fid`` values are never exposed.  ``local_access_effect`` is a
    pre-decision local-effect proxy and does not inspect slots 1..H.
    """

    memory_text: str
    memory_tokens: Tuple[str, ...]
    decision_query: str
    decision_tokens: Tuple[str, ...]
    memory_scope: str
    decision_scope: str
    storage_tokens: int
    session_count: int
    mention_frequency: int
    mention_age: int
    local_relevance: float
    semantic_confidence: float
    visible_event_overlap: int
    local_access_effect: float
    mean_memory_relevance: float
    future_demand: float


@dataclass(frozen=True)
class BaselineScoreSpec:
    name: str
    label: str
    evidence_level: str
    score_definition: str
    audit_scope: str
    score: Callable[[PublicDecisionView], float]


def _mentions(ep: RealizedEpisode) -> Tuple[int, int]:
    decision = ep.tokens(ep.world.decision_fid)
    hits: List[int] = []
    for index, session in enumerate(ep.sessions):
        if max((overlap(decision, tokenize(msg.text))
                for msg in session.messages), default=0) >= ADOPT_THRESHOLD:
            hits.append(index)
    age = len(ep.sessions) if not hits else len(ep.sessions) - 1 - hits[-1]
    return len(hits), age


def build_public_view(ep: RealizedEpisode) -> PublicDecisionView:
    memory = ep.memory(ep.world.decision_fid)
    frequency, age = _mentions(ep)
    decision_tokens = tuple(ep.decision_task.tokens)
    local_overlap = overlap(memory.tokens, decision_tokens)
    local_relevance = local_overlap / max(len(set(decision_tokens)), 1)
    semantic_confidence = local_overlap / max(
        len(set(memory.tokens) | set(decision_tokens)), 1)

    event_overlap = 0
    for session in ep.sessions:
        for msg in session.messages:
            if msg.kind in ("update", "correction"):
                event_overlap = max(
                    event_overlap, overlap(memory.tokens, tokenize(msg.text)))

    memory_relevances = [
        overlap(m.tokens, decision_tokens) / max(len(set(decision_tokens)), 1)
        for m in ep.memories
    ]
    future_demand = 0.0
    for item in ep.future_items:
        if item.task is None:
            continue
        query_overlap = overlap(memory.tokens, item.task.tokens)
        if query_overlap >= ADOPT_THRESHOLD:
            future_demand += GAMMA ** item.spec.slot

    # Local causal proxy: visible correction evidence attenuates the
    # decision-time relevance estimate.  This is intentionally a proxy, not
    # a claim that LifecycleBench estimates the full CMI perturbation effect.
    local_access_effect = local_relevance - (0.5 if event_overlap else 0.0)

    return PublicDecisionView(
        memory_text=memory.text,
        memory_tokens=tuple(memory.tokens),
        decision_query=ep.decision_task.query,
        decision_tokens=decision_tokens,
        memory_scope=memory.spec.scope,
        decision_scope=ep.world.decision_scope,
        storage_tokens=memory.spec.storage_tokens,
        session_count=len(ep.sessions),
        mention_frequency=frequency,
        mention_age=age,
        local_relevance=local_relevance,
        semantic_confidence=semantic_confidence,
        visible_event_overlap=event_overlap,
        local_access_effect=local_access_effect,
        mean_memory_relevance=(sum(memory_relevances) / len(memory_relevances)
                               if memory_relevances else 0.0),
        future_demand=future_demand,
    )


def _simplemem_lexical(view: PublicDecisionView) -> float:
    """Official verified +1 substring surface on a raw-memory row.

    The official +2 keyword-list channel is zero because LifecycleBench raw
    memories do not contain SimpleMem's LLM-generated keyword field.
    """
    text = view.memory_text.lower()
    return float(sum(str(token).lower() in text
                     for token in view.decision_tokens))


def _oblivion(view: PublicDecisionView) -> float:
    max_frequency = max(view.session_count, 1)
    local_utility = max(view.local_relevance, 0.0)
    strength = local_utility + view.mention_frequency / max_frequency
    return math.exp(-view.mention_age / (max(strength, 1e-6) * 3.0))


def _memory_worth(view: PublicDecisionView) -> float:
    # Same Beta(1,1), implicit-100-history transport as the unified runner.
    success_rate = min(max(view.local_relevance, 0.0), 1.0)
    return (100.0 * success_rate + 1.0) / 102.0


def _fademem(view: PublicDecisionView) -> float:
    tau_sem = 20.0 + 40.0 * view.semantic_confidence
    return math.log1p(view.mention_frequency) * math.exp(
        -view.mention_age / tau_sem)


def _demem(view: PublicDecisionView) -> float:
    # Paper-mechanism proxy: preserve a local decision distinction.
    return abs(view.local_relevance - view.mean_memory_relevance)


def _cmi(view: PublicDecisionView) -> float:
    return view.local_access_effect


def _trivium(view: PublicDecisionView) -> float:
    # Transductive upper-bound demand: public query schedule, no needed ids.
    return view.local_access_effect * view.future_demand


def _govmem(view: PublicDecisionView) -> float:
    # Strict-online coverage proxy with semantic tie break.
    return view.mention_frequency + 1e-6 * view.semantic_confidence


BASELINE_SCORE_SPECS: Mapping[str, BaselineScoreSpec] = {
    "simplemem_lexical": BaselineScoreSpec(
        "simplemem_lexical", "SimpleMem lexical surface",
        "official-code surface + constructed intervention audit",
        "official keyword_search raw-row channel: +1 per query token "
        "contained in memory text; LLM compression/keywords/embedding absent",
        "verified lexical retrieval surface only; not full SimpleMem",
        _simplemem_lexical),
    "oblivion_decay": BaselineScoreSpec(
        "oblivion_decay", "Oblivion decay rule",
        "transported official rule + constructed intervention audit",
        "exp(-age / ((local_utility + normalized_frequency) * 3))",
        "core paper decay equation; uncertainty/Qdrant tiers absent",
        _oblivion),
    "memory_worth": BaselineScoreSpec(
        "memory_worth", "Memory Worth",
        "associational signal proxy + constructed intervention audit",
        "(100 * local_success_rate + 1) / 102",
        "associational score proxy; full writer/query bookkeeping absent",
        _memory_worth),
    "fademem": BaselineScoreSpec(
        "fademem", "FadeMem differential-decay proxy",
        "internal proxy + constructed intervention audit",
        "log1p(frequency) * exp(-age / (20 + 40 * semantic_confidence))",
        "named proxy only; official Agent-memory implementation unverified",
        _fademem),
    "demem": BaselineScoreSpec(
        "demem", "DeMem-inspired distinction heuristic",
        "internal heuristic + constructed intervention audit",
        "abs(local_relevance - mean_candidate_local_relevance)",
        "local distinction proxy; compression decoder absent",
        _demem),
    "cmi_local": BaselineScoreSpec(
        "cmi_local", "CMI-inspired local relevance heuristic",
        "internal heuristic + constructed intervention audit",
        "local decision relevance - 0.5 * visible correction indicator",
        "controlled local-effect proxy only; full perturbation estimator absent",
        _cmi),
    "trivium": BaselineScoreSpec(
        "trivium", "Trivium-inspired demand-weighted control",
        "internal heuristic + constructed intervention audit",
        "local_access_effect * discounted_public_future_query_demand",
        "transductive demand upper bound; probing layer absent",
        _trivium),
    "govmem": BaselineScoreSpec(
        "govmem", "GovMem-incompatible access coverage control",
        "not transportable as GovMem + constructed control audit",
        "prior_session_coverage + 1e-6 * semantic_confidence",
        "access-time coverage control; GovMem is write-time and is not "
        "transportable under this audit",
        _govmem),
}


EXCLUDED_BASELINES = {
    "actmem": {
        "evidence_level": "paper-mechanism proxy; partial execution path",
        "reason": "ActMem defines graph construction and counterfactual "
                  "retrieval, but no scalar persistent keep/archive score "
                  "that can be frozen without inventing a new policy.",
    },
    "sage": {
        "evidence_level": "not transportable",
        "reason": "Interactive guidance is outside the fixed score audit.",
    },
    "memaudit": {
        "evidence_level": "not transportable",
        "reason": "Retrospective attribution is not a retention score.",
    },
    "gatemem": {
        "evidence_level": "not transportable",
        "reason": "Multi-principal access-control benchmark is not a "
                  "single-agent keep/archive score.",
    },
}


def _log_fingerprint(log: object) -> Tuple[object, ...]:
    state = log.state
    return (
        tuple(log.candidates), tuple(log.workspace), tuple(log.probes),
        tuple(log.restore), tuple(log.adopted), round(log.storage_cost, 8),
        round(log.exposure_cost, 8), round(log.probe_cost, 8),
        tuple(sorted(state.store)), tuple(sorted(state.archive)),
        tuple(sorted((fid, str(cert.status))
                     for fid, cert in state.certs.items())),
    )


def differing_future_slots(paired: PairedRollout) -> Tuple[int, ...]:
    return tuple(
        keep.slot for keep, archive in zip(paired.keep.logs,
                                           paired.archive.logs)
        if _log_fingerprint(keep) != _log_fingerprint(archive)
    )


def _episode_row(ep: RealizedEpisode, paired: PairedRollout,
                 outcome: EpisodeOutcome, spec: BaselineScoreSpec,
                 score_digits: int) -> Dict[str, object]:
    view = build_public_view(ep)
    score = float(spec.score(view))
    slots = differing_future_slots(paired)
    return {
        "episode_id": ep.world.episode_id,
        "family": ep.world.family,
        "variant": ep.world.variant,
        "paired_key": ep.world.paired_key,
        "score": round(score, score_digits),
        "delta_keep_minus_archive": outcome.tau_keep_archive,
        "value_keep": outcome.lifecycle_value_keep,
        "value_archive": outcome.lifecycle_value_archive,
        "oracle_action": outcome.oracle_action,
        "future_kernel_non_null": bool(slots),
        "differing_future_slots": list(slots),
        "last_differing_slot": max(slots) if slots else None,
        "value_relevant": abs(outcome.tau_keep_archive) > TAU_TOL,
    }


def _pair_payload(a: Mapping[str, object], b: Mapping[str, object]) \
        -> Dict[str, object]:
    da = float(a["delta_keep_minus_archive"])
    db = float(b["delta_keep_minus_archive"])
    return {
        "score": a["score"],
        "episode_1": a["episode_id"],
        "episode_2": b["episode_id"],
        "family_variant_1": f"{a['family']}/{a['variant']}",
        "family_variant_2": f"{b['family']}/{b['variant']}",
        "delta_1": da,
        "delta_2": db,
        "oracle_1": a["oracle_action"],
        "oracle_2": b["oracle_action"],
        "absolute_delta_gap": abs(da - db),
        "cost_shift_regret_lower_bound": abs(da - db) / 4.0,
    }


def summarize_score_fibers(rows: Sequence[Mapping[str, object]]) \
        -> Dict[str, object]:
    fibers: Dict[float, List[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        fibers[float(row["score"])].append(row)

    heterogeneous: List[Dict[str, object]] = []
    opposite: List[Dict[str, object]] = []
    for score, fiber in fibers.items():
        if len(fiber) < 2:
            continue
        ordered = sorted(fiber,
                         key=lambda row: float(row["delta_keep_minus_archive"]))
        lo, hi = ordered[0], ordered[-1]
        gap = float(hi["delta_keep_minus_archive"]) - float(
            lo["delta_keep_minus_archive"])
        if gap > TAU_TOL:
            heterogeneous.append(_pair_payload(lo, hi))

        negatives = [r for r in fiber
                     if float(r["delta_keep_minus_archive"]) < -TAU_TOL]
        positives = [r for r in fiber
                     if float(r["delta_keep_minus_archive"]) > TAU_TOL]
        for neg in negatives:
            for pos in positives:
                payload = _pair_payload(neg, pos)
                d_minus = -float(neg["delta_keep_minus_archive"])
                d_plus = float(pos["delta_keep_minus_archive"])
                payload["deterministic_minimax_regret"] = min(d_plus, d_minus)
                payload["randomized_minimax_regret"] = (
                    d_plus * d_minus / (d_plus + d_minus))
                opposite.append(payload)

    heterogeneous.sort(key=lambda x: float(x["absolute_delta_gap"]),
                       reverse=True)
    opposite.sort(key=lambda x: float(x["randomized_minimax_regret"]),
                  reverse=True)
    return {
        "n_score_fibers": len(fibers),
        "n_collision_fibers": sum(len(v) >= 2 for v in fibers.values()),
        "n_heterogeneous_fibers": len(heterogeneous),
        "n_opposite_sign_fibers": len({float(w["score"]) for w in opposite}),
        "epsilon_lc_lower_witness": (
            heterogeneous[0]["absolute_delta_gap"] if heterogeneous else 0.0),
        "max_cost_shift_regret_lower_bound": (
            heterogeneous[0]["cost_shift_regret_lower_bound"]
            if heterogeneous else 0.0),
        "max_randomized_fixed_cost_regret": (
            opposite[0]["randomized_minimax_regret"] if opposite else 0.0),
        "max_deterministic_fixed_cost_regret": (
            max(float(w["deterministic_minimax_regret"]) for w in opposite)
            if opposite else 0.0),
        "max_gap_witness": heterogeneous[0] if heterogeneous else None,
        "max_opposite_sign_witness": opposite[0] if opposite else None,
    }


def select_small_constructed_sample(
        episodes: Sequence[RealizedEpisode], control_pairs: int = 4,
        ) -> Tuple[List[RealizedEpisode], List[RealizedEpisode]]:
    """One deterministic episode per observable family/variant/entity cell.

    Observation-equivalent pairs are returned separately.  They are a
    positive control for non-identifiability and are excluded from every
    baseline-specific epsilon/regret estimate.
    """
    main: Dict[Tuple[str, str, str], RealizedEpisode] = {}
    paired: Dict[str, List[RealizedEpisode]] = defaultdict(list)
    for ep in episodes:
        if ep.world.paired_key is not None:
            paired[ep.world.paired_key].append(ep)
            continue
        entity = ep.memory(ep.world.decision_fid).spec.entity
        key = (ep.world.family, ep.world.variant, entity)
        if key not in main or ep.world.episode_id < main[key].world.episode_id:
            main[key] = ep
    controls: List[RealizedEpisode] = []
    for key in sorted(paired)[:control_pairs]:
        controls.extend(sorted(paired[key], key=lambda e: e.world.episode_id))
    return ([main[key] for key in sorted(main)], controls)


def _run_rows(episodes: Iterable[RealizedEpisode],
              spec: BaselineScoreSpec,
              score_digits: int) -> List[Dict[str, object]]:
    rows = []
    for ep in episodes:
        paired = paired_rollout(ep)
        outcome = evaluate(ep, paired.keep, paired.archive)
        rows.append(_episode_row(ep, paired, outcome, spec, score_digits))
    return rows


def _identification_controls(
        episodes: Sequence[RealizedEpisode]) -> Dict[str, object]:
    groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for ep in episodes:
        paired = paired_rollout(ep)
        outcome = evaluate(ep, paired.keep, paired.archive)
        groups[str(ep.world.paired_key)].append({
            "episode_id": ep.world.episode_id,
            "delta_keep_minus_archive": outcome.tau_keep_archive,
            "oracle_action": outcome.oracle_action,
        })
    witnesses = []
    for key, rows in sorted(groups.items()):
        if len(rows) != 2:
            continue
        a, b = rows
        if a["oracle_action"] != b["oracle_action"]:
            witnesses.append({"paired_key": key, "episodes": rows})
    return {
        "n_pairs": len(groups),
        "n_oracle_flip_pairs": len(witnesses),
        "use_in_baseline_epsilon": False,
        "reason": "Public traces are identical, so these pairs diagnose "
                  "irreducible identification rather than a specific "
                  "baseline score omission.",
        "witnesses": witnesses,
    }


def run_baseline_internal_gap_audit(
        episodes: Optional[Sequence[RealizedEpisode]] = None,
        score_digits: int = DEFAULT_SCORE_DIGITS,
        control_pairs: int = 4) -> Dict[str, object]:
    if episodes is None:
        episodes = all_episodes()
    main, controls = select_small_constructed_sample(episodes, control_pairs)
    baselines: Dict[str, object] = {}
    for name, spec in BASELINE_SCORE_SPECS.items():
        rows = _run_rows(main, spec, score_digits)
        summary = summarize_score_fibers(rows)
        summary.update({
            "label": spec.label,
            "evidence_level": spec.evidence_level,
            "score_definition": spec.score_definition,
            "audit_scope": spec.audit_scope,
            "n_episodes": len(rows),
            "future_kernel_non_null_rate": sum(
                bool(row["future_kernel_non_null"]) for row in rows) / len(rows),
            "value_relevant_rate": sum(
                bool(row["value_relevant"]) for row in rows) / len(rows),
            "rows": rows,
        })
        baselines[name] = summary

    return {
        "audit_version": AUDIT_VERSION,
        "claim_scope": (
            "Constructive algorithm-level baseline-internal evidence only; "
            "not a natural-task external-validity result and not a full-"
            "system reproduction claim."),
        "estimand": "Delta(x)=V_keep(x)-V_archive(x)",
        "score_fiber_contract": (
            f"exact equality after rounding scores to {score_digits} digits"),
        "sample": {
            "selection": "one deterministic episode per family/variant/entity",
            "n_primary_episodes": len(main),
            "n_identification_control_episodes": len(controls),
            "primary_episode_ids": [ep.world.episode_id for ep in main],
        },
        "baseline_results": baselines,
        "excluded_baselines": EXCLUDED_BASELINES,
        "identification_positive_control": _identification_controls(controls),
        "interpretation_rules": {
            "future_kernel_non_null": "keep/archive changes a future Agent "
                                      "state/access/evidence transcript field",
            "value_relevant": f"abs(Delta) > {TAU_TOL}",
            "heterogeneous_fiber": "same score and unequal Delta",
            "fixed_cost_witness": "same score with Delta_1 < 0 < Delta_2",
            "cost_shift_witness": "unequal same-score contrasts imply a "
                                  "midpoint-shift regret lower bound gap/4",
        },
    }


def write_audit(path: Path, **kwargs: object) -> Dict[str, object]:
    result = run_baseline_internal_gap_audit(**kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return result


def compact_summary(result: Mapping[str, object]) -> List[Dict[str, object]]:
    rows = []
    baselines = result["baseline_results"]
    assert isinstance(baselines, Mapping)
    for name, raw in baselines.items():
        item = dict(raw)
        rows.append({
            "baseline": name,
            "evidence_level": item["evidence_level"],
            "n": item["n_episodes"],
            "kernel_non_null_rate": item["future_kernel_non_null_rate"],
            "value_relevant_rate": item["value_relevant_rate"],
            "heterogeneous_fibers": item["n_heterogeneous_fibers"],
            "opposite_sign_fibers": item["n_opposite_sign_fibers"],
            "epsilon_lc_witness": item["epsilon_lc_lower_witness"],
            "fixed_cost_randomized_regret":
                item["max_randomized_fixed_cost_regret"],
        })
    return rows
