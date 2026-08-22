"""Faithful, protocol-separated reproductions of the named memory baselines.

This module deliberately does not reuse the historical lexical/score proxies.
Each runner consumes an explicit chronological episode contract and returns
evidence-bearing decisions.  Where a paper does not publish enough details to
uniquely determine an implementation, the result is marked ``partial`` and
the unresolved component is retained in the output instead of being silently
replaced by a heuristic.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


EVIDENCE_LEVELS = {
    "official-code faithful core",
    "paper-mechanism faithful core",
    "paper-mechanism faithful core (partial)",
}


@dataclass(frozen=True)
class MemoryCandidate:
    """A memory available to a controller at write/access time."""

    memory_id: str
    content: str = ""
    risk: bool = False
    partition_key: str = "default"
    dependencies: Tuple[str, ...] = ()


@dataclass(frozen=True)
class BaselineEpisode:
    """Chronological input contract shared by all faithful cores.

    ``exposed_ids`` is the *actual* retrieved workspace, not lexical overlap.
    ``success`` is the episode-level evaluator outcome and may be ``None`` for
    an episode that has not yet been scored.  The optional fields carry the
    extra evidence required by the papers without leaking future labels into a
    decision made at the start of the episode.
    """

    episode_id: str
    query: str = ""
    candidate_ids: Tuple[str, ...] = ()
    exposed_ids: Tuple[str, ...] = ()
    success: Optional[bool] = None
    decision_context: str = "default"
    decision_label: Optional[str] = None
    conflict_feature: Optional[str] = None
    cmi_scores: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    probe_candidates: Tuple[str, ...] = ()
    probe_observations: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    write_evidence: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


@dataclass
class FaithfulBaselineResult:
    baseline: str
    status: str
    evidence_level: str
    decisions: List[Dict[str, Any]]
    final_state: Dict[str, Any]
    unresolved: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _require_evidence(level: str) -> str:
    if level not in EVIDENCE_LEVELS:
        raise ValueError(f"unknown evidence level: {level}")
    return level


class CMIProtocol:
    """CMI's official three-condition item intervention protocol.

    The scorer is supplied by the caller because the official repository uses
    an LLM/evaluator.  It must return a scalar task score for ``no_memory`` or
    for one candidate under ``with_memory``/``perturbed_memory``.
    """

    def __init__(self, utility_threshold: float = 0.0,
                 stability_threshold: float = 0.0,
                 veto_risky: bool = True) -> None:
        self.utility_threshold = float(utility_threshold)
        self.stability_threshold = float(stability_threshold)
        self.veto_risky = bool(veto_risky)

    def run(
        self,
        episodes: Sequence[BaselineEpisode],
        candidates: Mapping[str, MemoryCandidate],
        score: Callable[[BaselineEpisode, str, str], float],
        perturbation: Optional[Callable[[MemoryCandidate], Any]] = None,
    ) -> FaithfulBaselineResult:
        decisions: List[Dict[str, Any]] = []
        selected_by_episode: Dict[str, List[str]] = {}
        for episode in episodes:
            no = float(score(episode, "", "no_memory"))
            selected: List[str] = []
            ids = episode.candidate_ids or tuple(candidates)
            for memory_id in ids:
                if memory_id not in candidates:
                    raise KeyError(f"CMI candidate missing: {memory_id}")
                with_memory = float(score(episode, memory_id, "with_memory"))
                perturbation_record: Any = None
                if perturbation is not None:
                    perturbation_record = perturbation(candidates[memory_id])
                perturbed = float(score(episode, memory_id, "perturbed_memory"))
                utility = with_memory - no
                stability = with_memory - perturbed
                veto = self.veto_risky and self._is_risky(candidates[memory_id])
                keep = (utility > self.utility_threshold and
                        stability >= self.stability_threshold and not veto)
                if keep:
                    selected.append(memory_id)
                decisions.append({
                    "episode_id": episode.episode_id,
                    "memory_id": memory_id,
                    "s_no": no,
                    "s_with": with_memory,
                    "s_perturbed": perturbed,
                    "utility": utility,
                    "stability": stability,
                    "risk_veto": veto,
                    "selected": keep,
                    "perturbation": (perturbation_record if perturbation_record is not None
                                     else "caller-defined scorer"),
                })
            selected_by_episode[episode.episode_id] = selected
        return FaithfulBaselineResult(
            baseline="cmi_official_protocol",
            status="faithful_core",
            evidence_level=_require_evidence("official-code faithful core"),
            decisions=decisions,
            final_state={"selected_by_episode": selected_by_episode,
                         "utility_threshold": self.utility_threshold,
                         "stability_threshold": self.stability_threshold,
                         "veto_risky": self.veto_risky},
            notes=["Official core requires an evaluator-backed no/with/perturbed scorer."],
        )

    @staticmethod
    def _is_risky(candidate: MemoryCandidate) -> bool:
        content = candidate.content.lower()
        risky_phrases = (
            "ask for a grade change", "change my grade", "ignore the question",
            "demanding tone", "always write extremely long", "ignore class-specific",
        )
        return candidate.risk or any(phrase in content for phrase in risky_phrases)


class MemoryWorthProtocol:
    """Chronological retrieval-conditioned two-counter Memory Worth."""

    def __init__(self, alpha: float = 0.0, beta: float = 0.0,
                 retain_threshold: Optional[float] = None,
                 budget: Optional[int] = None) -> None:
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.retain_threshold = retain_threshold
        self.budget = budget

    def run(self, episodes: Sequence[BaselineEpisode],
            candidates: Mapping[str, MemoryCandidate]) -> FaithfulBaselineResult:
        plus: Dict[str, int] = defaultdict(int)
        minus: Dict[str, int] = defaultdict(int)
        decisions: List[Dict[str, Any]] = []
        workspaces: Dict[str, List[str]] = {}
        all_ids = tuple(candidates)
        for episode in episodes:
            # The decision uses only counters from strictly earlier episodes.
            worth = {
                mid: (plus[mid] + self.alpha) /
                (plus[mid] + minus[mid] + self.alpha + self.beta)
                if plus[mid] + minus[mid] + self.alpha + self.beta > 0 else 0.0
                for mid in all_ids
            }
            ranked = sorted(worth, key=lambda mid: (-worth[mid], mid))
            if self.retain_threshold is not None:
                ranked = [mid for mid in ranked
                          if worth[mid] >= self.retain_threshold]
            if self.budget is not None:
                ranked = ranked[:self.budget]
            workspaces[episode.episode_id] = ranked
            decisions.append({
                "episode_id": episode.episode_id,
                "workspace_ids": ranked,
                "worth_before_outcome": worth,
                "exposed_ids": list(episode.exposed_ids),
                "outcome_used": episode.success,
            })
            if episode.success is not None:
                for mid in set(episode.exposed_ids):
                    if mid not in candidates:
                        raise KeyError(f"Memory Worth exposed candidate missing: {mid}")
                    if episode.success:
                        plus[mid] += 1
                    else:
                        minus[mid] += 1
        final_worth = {
            mid: (plus[mid] + self.alpha) /
            (plus[mid] + minus[mid] + self.alpha + self.beta)
            if plus[mid] + minus[mid] + self.alpha + self.beta > 0 else 0.0
            for mid in all_ids
        }
        return FaithfulBaselineResult(
            baseline="memory_worth_faithful_core",
            status="faithful_core",
            evidence_level=_require_evidence("paper-mechanism faithful core"),
            decisions=decisions,
            final_state={"hits_plus": dict(plus), "hits_minus": dict(minus),
                         "worth": final_worth, "workspaces": workspaces,
                         "alpha": self.alpha, "beta": self.beta},
            unresolved=["An evaluator must provide episode success/failure; lexical overlap is not a substitute."],
        )


class DeMemProtocol:
    """Partial but explicit DeMem partition/conflict refinement state machine."""

    def __init__(self, budget: Optional[int] = None) -> None:
        self.budget = budget

    def run(self, episodes: Sequence[BaselineEpisode],
            candidates: Mapping[str, MemoryCandidate]) -> FaithfulBaselineResult:
        partitions: Dict[str, List[str]] = defaultdict(list)
        for mid, candidate in candidates.items():
            partitions[candidate.partition_key].append(mid)
        observed_labels: Dict[str, set[str]] = defaultdict(set)
        conflict_log: List[Dict[str, Any]] = []
        decisions: List[Dict[str, Any]] = []
        for episode in episodes:
            before = {key: list(value) for key, value in partitions.items()}
            labels: Dict[str, set[str]] = defaultdict(set)
            if episode.decision_label is not None:
                for key, mids in partitions.items():
                    if set(mids) & set(episode.exposed_ids):
                        labels[key].update(observed_labels[key])
                        labels[key].add(episode.decision_label)
            conflicts = [key for key, values in labels.items() if len(values) > 1]
            refined: List[Dict[str, Any]] = []
            if conflicts and episode.conflict_feature:
                for key in conflicts:
                    mids = partitions.pop(key)
                    groups: Dict[str, List[str]] = defaultdict(list)
                    for mid in mids:
                        groups[f"{key}|{episode.conflict_feature}|{mid}"].append(mid)
                    partitions.update(groups)
                    refined.append({"partition": key, "feature": episode.conflict_feature,
                                    "new_partitions": list(groups)})
            retained = [mid for key in sorted(partitions)
                        for mid in partitions[key]]
            if self.budget is not None:
                retained = retained[:self.budget]
            conflict_log.append({"episode_id": episode.episode_id,
                                 "certified_conflicts": conflicts,
                                 "refinement": refined})
            decisions.append({"episode_id": episode.episode_id,
                              "partitions_before": before,
                              "partitions_after": {k: list(v) for k, v in partitions.items()},
                              "retained_ids": retained})
            if episode.decision_label is not None:
                for key, mids in partitions.items():
                    if set(mids) & set(episode.exposed_ids):
                        observed_labels[key].add(episode.decision_label)
        return FaithfulBaselineResult(
            baseline="demem_faithful_core_partial",
            status="partial",
            evidence_level=_require_evidence("paper-mechanism faithful core (partial)"),
            decisions=decisions,
            final_state={"partitions": {k: list(v) for k, v in partitions.items()},
                         "conflict_log": conflict_log, "budget": self.budget},
            unresolved=["The paper does not uniquely specify a production decoder/judge and all threshold details; these remain explicit protocol inputs."],
        )


class TriviumProtocol:
    """Persistent causal log with budgeted uncertainty probes and regret ledger."""

    def __init__(self, probe_budget: int = 0) -> None:
        self.probe_budget = int(probe_budget)

    def run(self, episodes: Sequence[BaselineEpisode],
            candidates: Mapping[str, MemoryCandidate]) -> FaithfulBaselineResult:
        causal_log: List[Dict[str, Any]] = []
        regrets = {"outcome": 0.0, "temporal": 0.0, "epistemic": 0.0}
        posterior: Dict[str, Dict[str, float]] = {
            mid: {"n": 0.0, "mean": 0.0, "m2": 0.0} for mid in candidates
        }
        decisions: List[Dict[str, Any]] = []
        for episode in episodes:
            observations = episode.probe_observations
            ranked = sorted(episode.probe_candidates,
                            key=lambda mid: (-self._uncertainty(posterior.get(mid)), mid))
            probed = ranked[:self.probe_budget]
            entries: List[Dict[str, Any]] = []
            for mid in probed:
                obs = observations.get(mid)
                if obs is None:
                    continue
                outcome_regret = float(obs.get("outcome_regret", 0.0))
                temporal_regret = float(obs.get("temporal_regret", 0.0))
                epistemic_regret = float(obs.get("epistemic_regret", 0.0))
                regrets["outcome"] += outcome_regret
                regrets["temporal"] += temporal_regret
                regrets["epistemic"] += epistemic_regret
                value = float(obs.get("effect", 0.0))
                self._update(posterior[mid], value)
                entry = {"episode_id": episode.episode_id, "memory_id": mid,
                         "observation": dict(obs), "probed": True}
                causal_log.append(entry)
                entries.append(entry)
            decisions.append({"episode_id": episode.episode_id,
                              "probed_ids": probed, "observations": entries,
                              "persistent_log_size": len(causal_log)})
        return FaithfulBaselineResult(
            baseline="trivium_faithful_core_partial",
            status="partial",
            evidence_level=_require_evidence("paper-mechanism faithful core (partial)"),
            decisions=decisions,
            final_state={"causal_log": causal_log, "posterior": posterior,
                         "regret": regrets, "probe_budget": self.probe_budget},
            unresolved=["Exact change-point detector and probe utility policy must be instantiated from the target paper/config; this core records them rather than substituting future demand."],
        )

    @staticmethod
    def _uncertainty(state: Optional[Mapping[str, float]]) -> float:
        if not state or state.get("n", 0.0) < 2:
            return float("inf")
        return math.sqrt(max(state.get("m2", 0.0), 0.0) / state["n"])

    @staticmethod
    def _update(state: Dict[str, float], value: float) -> None:
        n0 = state["n"]
        n1 = n0 + 1.0
        delta = value - state["mean"]
        state["mean"] += delta / n1
        state["m2"] += delta * (value - state["mean"])
        state["n"] = n1


class GovMemProtocol:
    """Write-time support/counterevidence adjudication for GovMem."""

    def __init__(self, adjudicator: Optional[
            Callable[[str, Mapping[str, Any]], str]] = None) -> None:
        self.adjudicator = adjudicator

    def run(self, episodes: Sequence[BaselineEpisode],
            candidates: Mapping[str, MemoryCandidate]) -> FaithfulBaselineResult:
        decisions: List[Dict[str, Any]] = []
        promoted: List[str] = []
        rejected: List[str] = []
        review: List[str] = []
        for episode in episodes:
            for mid, evidence in episode.write_evidence.items():
                if mid not in candidates:
                    raise KeyError(f"GovMem candidate missing: {mid}")
                support = list(evidence.get("support_ids", ()))
                counter = list(evidence.get("counterevidence_ids", ()))
                dependencies = list(candidates[mid].dependencies)
                missing_dependencies = [dep for dep in dependencies
                                        if dep not in support]
                payload = {"support_ids": support,
                           "counterevidence_ids": counter,
                           "dependencies": dependencies,
                           "missing_dependencies": missing_dependencies,
                           "episode_id": episode.episode_id}
                if self.adjudicator is not None:
                    action = self.adjudicator(mid, payload)
                elif missing_dependencies:
                    action = "needs-review"
                elif counter and len(counter) >= len(support):
                    action = "needs-review"
                elif support:
                    action = "promote"
                else:
                    action = "reject"
                if action not in {"promote", "reject", "needs-review"}:
                    raise ValueError(f"invalid GovMem action: {action}")
                if action == "promote":
                    promoted.append(mid)
                elif action == "reject":
                    rejected.append(mid)
                else:
                    review.append(mid)
                decisions.append({"episode_id": episode.episode_id,
                                  "memory_id": mid, "action": action,
                                  "support_ids": support,
                                  "counterevidence_ids": counter,
                                  "dependencies": dependencies,
                                  "missing_dependencies": missing_dependencies})
        return FaithfulBaselineResult(
            baseline="govmem_write_time_faithful_core",
            status="faithful_core",
            evidence_level=_require_evidence("paper-mechanism faithful core"),
            decisions=decisions,
            final_state={"promoted_ids": promoted, "rejected_ids": rejected,
                         "needs_review_ids": review},
            unresolved=["Write-time evidence retrieval and adjudication must be supplied by the target agent/retriever; access-time lexical coverage is not used."],
        )


def load_contract(path: Path | str) -> Tuple[List[BaselineEpisode], Dict[str, MemoryCandidate]]:
    """Load the small JSON contract used by the faithful runner CLI."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    candidates = {
        str(row["memory_id"]): MemoryCandidate(
            memory_id=str(row["memory_id"]), content=str(row.get("content", "")),
            risk=bool(row.get("risk", False)),
            partition_key=str(row.get("partition_key", "default")),
            dependencies=tuple(map(str, row.get("dependencies", []))),
        ) for row in data.get("candidates", [])
    }
    episodes = [BaselineEpisode(
        episode_id=str(row["episode_id"]), query=str(row.get("query", "")),
        candidate_ids=tuple(map(str, row.get("candidate_ids", []))),
        exposed_ids=tuple(map(str, row.get("exposed_ids", []))),
        success=row.get("success"), decision_context=str(row.get("decision_context", "default")),
        decision_label=row.get("decision_label"), conflict_feature=row.get("conflict_feature"),
        probe_candidates=tuple(map(str, row.get("probe_candidates", []))),
        probe_observations=row.get("probe_observations", {}),
        cmi_scores=row.get("cmi_scores", {}),
        write_evidence=row.get("write_evidence", {}),
    ) for row in data.get("episodes", [])]
    return episodes, candidates


__all__ = [
    "BaselineEpisode", "CMIProtocol", "DeMemProtocol", "FaithfulBaselineResult",
    "GovMemProtocol", "MemoryCandidate", "MemoryWorthProtocol", "TriviumProtocol",
    "load_contract",
]
