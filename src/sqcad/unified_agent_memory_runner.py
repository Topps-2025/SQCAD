"""Executable smoke runner for a common Agent Memory workflow.

Every policy receives the same evidence stream, task sequence, workspace
budget and evaluator.  The runner verifies write -> candidate retrieval ->
workspace exposure -> agent action -> outcome -> decision log -> reversible
state update.  It is a controlled engineering test, not a public benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List, Sequence, Tuple

try:
    from .causal_memory_store import CausalMemoryStore
except ImportError:  # pragma: no cover - direct script compatibility
    from causal_memory_store import CausalMemoryStore


POLICIES = (
    "recency", "frequency", "fade_like", "outcome_feedback_like",
    "causal_item", "risk_gated_decomp_abstract",
)


@dataclass(frozen=True)
class Candidate:
    memory_id: str
    true_group: str
    semantic_group: str
    semantic_confidence: float
    last_access: float
    frequency: float
    success_rate: float
    item_effect_lcb: float
    group_effect_lcb: float
    token_cost: int


@dataclass(frozen=True)
class Task:
    task_id: str
    required_group: str


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def build_episode(seed: int, group_noise: float, steps: int) -> Tuple[List[Candidate], List[Task]]:
    rng = random.Random(seed)
    group_sizes = {"rare_critical": 4, "common_useful": 8, "stale": 8, "noise": 12}
    effects = {"rare_critical": 2.5, "common_useful": 1.0, "stale": -1.0, "noise": 0.0}
    candidates: List[Candidate] = []
    groups = list(group_sizes)
    for group, size in group_sizes.items():
        for index in range(size):
            wrong = rng.random() < group_noise
            semantic_group = rng.choice([value for value in groups if value != group]) if wrong else group
            confidence = rng.uniform(0.30, 0.80) if wrong else rng.uniform(0.75, 1.00)
            if group == "rare_critical":
                recency, frequency, success = rng.uniform(0, 20), rng.uniform(1, 3), rng.uniform(0.10, 0.35)
                item_lcb = -1e6 if rng.random() < 0.75 else rng.uniform(-0.10, 0.50)
            elif group == "common_useful":
                recency, frequency, success = rng.uniform(20, 70), rng.uniform(20, 50), rng.uniform(0.55, 0.80)
                item_lcb = rng.uniform(0.45, 0.95)
            elif group == "stale":
                recency, frequency, success = rng.uniform(70, 100), rng.uniform(40, 80), rng.uniform(0.70, 0.95)
                item_lcb = rng.uniform(-1.20, -0.55)
            else:
                recency, frequency, success = rng.uniform(10, 90), rng.uniform(5, 45), rng.uniform(0.55, 0.90)
                item_lcb = rng.uniform(-0.20, 0.15)
            group_lcb = effects[semantic_group] + rng.gauss(0.0, 0.08)
            candidates.append(Candidate(
                memory_id=f"{group}_{index:02d}",
                true_group=group,
                semantic_group=semantic_group,
                semantic_confidence=confidence,
                last_access=recency,
                frequency=frequency,
                success_rate=success,
                item_effect_lcb=item_lcb,
                group_effect_lcb=group_lcb,
                token_cost=20 + rng.randrange(21),
            ))
    tasks = []
    for step in range(steps):
        draw = rng.random()
        required = "rare_critical" if draw < 0.30 else "common_useful" if draw < 0.85 else "none"
        tasks.append(Task(f"task_{step:04d}", required))
    return candidates, tasks


def policy_score(candidate: Candidate, policy: str, max_recency: float) -> float:
    if policy == "recency":
        return candidate.last_access
    if policy == "frequency":
        return candidate.frequency
    if policy == "fade_like":
        age = max_recency - candidate.last_access
        return math.exp(-age / 25.0) * math.log1p(candidate.frequency)
    if policy == "outcome_feedback_like":
        return candidate.success_rate
    if policy == "causal_item":
        return candidate.item_effect_lcb
    if policy != "risk_gated_decomp_abstract":
        raise KeyError(policy)
    item_estimable = candidate.item_effect_lcb > -1e5
    sign_conflict = item_estimable and (
        (candidate.group_effect_lcb > 0.0 > candidate.item_effect_lcb)
        or (candidate.item_effect_lcb > 0.0 > candidate.group_effect_lcb)
    )
    harm_veto = item_estimable and candidate.item_effect_lcb <= -0.25
    if candidate.semantic_confidence < 0.75 or sign_conflict or harm_veto:
        return candidate.item_effect_lcb
    return candidate.group_effect_lcb


def run_policy(seed: int, policy: str, group_noise: float, steps: int, budget: int) -> Dict[str, float | str]:
    candidates, tasks = build_episode(seed, group_noise, steps)
    stream_hash = canonical_hash({"candidates": [asdict(item) for item in candidates], "tasks": [asdict(task) for task in tasks]})
    store = CausalMemoryStore()
    evidence_ids: Dict[str, str] = {}
    for item in candidates:
        evidence_id = store.add_evidence(
            content=f"Memory {item.memory_id} represents {item.true_group} evidence.",
            source_id=f"source_{item.memory_id}",
            subject_scope="shared-user",
            task_scope="controlled-runner",
        )
        store.add_factor(evidence_id, "condition", item.semantic_group, "controlled-v1", item.semantic_confidence)
        evidence_ids[item.memory_id] = evidence_id

    max_recency = max(item.last_access for item in candidates)
    ranking = sorted(candidates, key=lambda item: (policy_score(item, policy, max_recency), item.memory_id), reverse=True)
    retained = ranking[:budget]
    retained_ids = {item.memory_id for item in retained}
    successes = required_hits = stale_exposures = total_tokens = 0
    utility_sum = 0.0
    for step, task in enumerate(tasks):
        exposed = retained
        required_hit = task.required_group == "none" or any(item.true_group == task.required_group for item in exposed)
        stale_exposed = any(item.true_group == "stale" for item in exposed)
        # Stale exposure is a separate risk penalty rather than an automatic
        # task failure, preventing the evaluator from trivially zeroing any
        # policy that retains one obsolete item.
        success = required_hit
        utility = float(required_hit) - 0.35 * float(stale_exposed)
        required_hits += int(required_hit)
        stale_exposures += int(stale_exposed)
        successes += int(success)
        utility_sum += utility
        total_tokens += sum(item.token_cost for item in exposed)
        adoption = {item.memory_id: item.true_group == task.required_group for item in exposed}
        store.record_decision(
            episode_id=f"seed-{seed}-{policy}",
            step=step,
            history={"task_id": task.task_id, "required_group": task.required_group, "budget": budget},
            candidates=[item.memory_id for item in candidates],
            behavior_action={"policy": policy, "workspace_ids": sorted(retained_ids)},
            propensity=1.0,
            exposure={item.memory_id: 1 for item in exposed},
            adoption=adoption,
            agent_action={"type": "controlled_decision", "success": success},
            outcome={
                "success": int(success), "utility": utility,
                "required_hit": int(required_hit), "stale_exposed": int(stale_exposed),
            },
        )

    for item in candidates:
        if item.memory_id in retained_ids:
            continue
        if item.item_effect_lcb <= -0.25:
            store.archive_evidence(evidence_ids[item.memory_id], f"{policy}:stable_negative")
        else:
            store.downweight_evidence(evidence_ids[item.memory_id], f"{policy}:budget_exit")
    positives = {item.memory_id for item in candidates if item.true_group in {"rare_critical", "common_useful"}}
    decision_rows = store.decisions(f"seed-{seed}-{policy}")
    return {
        "candidate_stream_sha256": stream_hash,
        "task_success_rate": successes / steps,
        "average_utility": utility_sum / steps,
        "required_evidence_recall": required_hits / steps,
        "stale_exposure_rate": stale_exposures / steps,
        "average_workspace_tokens": total_tokens / steps,
        "retained_positive_precision": len(retained_ids & positives) / budget,
        "rare_critical_recall": len({item.memory_id for item in retained if item.true_group == "rare_critical"}) / 4,
        "decision_log_completeness": len(decision_rows) / steps,
        "governance_transitions": float(len(json.loads(store.audit_log()))),
    }


def summarize(rows: Sequence[Dict[str, float | str]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    output: Dict[str, Dict[str, Dict[str, float]]] = {}
    for policy in POLICIES:
        selected = [row for row in rows if row["policy"] == policy]
        output[policy] = {}
        for metric in (
            "task_success_rate", "average_utility", "required_evidence_recall", "stale_exposure_rate",
            "average_workspace_tokens", "retained_positive_precision", "rare_critical_recall",
            "decision_log_completeness", "governance_transitions",
        ):
            values = [float(row[metric]) for row in selected]
            sd = stdev(values) if len(values) > 1 else 0.0
            output[policy][metric] = {"mean": mean(values), "sd": sd, "ci95": 1.96 * sd / len(values) ** 0.5, "n": float(len(values))}
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--budget", type=int, default=12)
    parser.add_argument("--group-noise", type=float, default=0.2)
    parser.add_argument("--output", type=Path, default=Path("unified_agent_memory_runner.json"))
    args = parser.parse_args()
    rows: List[Dict[str, float | str]] = []
    for seed in range(args.seeds):
        expected_hash = None
        for policy in POLICIES:
            row = run_policy(seed, policy, args.group_noise, args.steps, args.budget)
            expected_hash = expected_hash or row["candidate_stream_sha256"]
            if row["candidate_stream_sha256"] != expected_hash:
                raise RuntimeError("policies did not receive the same candidate stream")
            row.update({"seed": float(seed), "policy": policy})
            rows.append(row)
    result = {
        "protocol": {
            "purpose": "common-workflow engineering smoke test; not a public benchmark",
            "seeds": args.seeds,
            "steps_per_seed": args.steps,
            "workspace_item_budget": args.budget,
            "group_noise": args.group_noise,
            "policies": POLICIES,
            "shared": "evidence stream, task sequence, workspace budget, evaluator and logging schema",
        },
        "summary": summarize(rows),
        "per_seed_policy": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

