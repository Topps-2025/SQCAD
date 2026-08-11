"""Cross-DGP stress test for structural Agent Memory governance.

The benchmark asks whether a fixed hierarchical intervention policy generalizes
across trajectories and data-generating processes without per-domain tuning,
manual path labels, or privileged path-level causal/risk cues.

The proposed policy only observes task-level risk/ambiguity, semantic and
associational priors available to every baseline, an automatically produced
(and possibly corrupted) grouping, and outcomes of interventions it actually
pays for.  Latent effects and true groups are evaluator-only.

This remains a synthetic mechanism test.  It cannot establish universal
superiority or replace public Agent Memory benchmarks.
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
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


POLICIES = (
    "semantic",
    "association",
    "fixed_hybrid",
    "uniform_item_probe",
    "greedy_item_lcb",
    "full_item_probe",
    "hierarchical_no_gate",
    "hierarchical_framework",
)


@dataclass(frozen=True)
class Scenario:
    name: str
    coherence: float
    semantic_alignment: float
    confounding: float
    drift_probability: float
    decomposition_accuracy: float
    observation_sd: float
    intervention_cost_scale: float
    group_count: int
    items_per_group: int
    description: str


@dataclass(frozen=True)
class Task:
    task_id: str
    risk: float
    ambiguity: float


@dataclass(frozen=True)
class MemoryPath:
    path_id: str
    true_group: int
    observed_group: int
    train_effect: float
    test_effect: float
    semantic_score: float
    association_score: float
    probe_cost: float
    execution_cost: float
    probe_priority: float
    item_observations: Tuple[float, ...]


SCENARIOS: Tuple[Scenario, ...] = (
    Scenario(
        "core_endogenous",
        coherence=0.85,
        semantic_alignment=0.10,
        confounding=0.90,
        drift_probability=0.25,
        decomposition_accuracy=0.90,
        observation_sd=0.55,
        intervention_cost_scale=1.00,
        group_count=6,
        items_per_group=3,
        description="Endogenous exposure, weak semantic-value alignment and moderate drift.",
    ),
    Scenario(
        "cross_domain_negative_alignment",
        coherence=0.75,
        semantic_alignment=-0.25,
        confounding=0.65,
        drift_probability=0.20,
        decomposition_accuracy=0.85,
        observation_sd=0.65,
        intervention_cost_scale=1.00,
        group_count=6,
        items_per_group=3,
        description="Surface similarity is anti-aligned with deployment value.",
    ),
    Scenario(
        "high_drift",
        coherence=0.80,
        semantic_alignment=0.25,
        confounding=0.75,
        drift_probability=0.55,
        decomposition_accuracy=0.88,
        observation_sd=0.65,
        intervention_cost_scale=1.00,
        group_count=6,
        items_per_group=3,
        description="Previously useful groups may reverse after a version or environment shift.",
    ),
    Scenario(
        "low_overlap_noisy_intervention",
        coherence=0.80,
        semantic_alignment=0.15,
        confounding=0.80,
        drift_probability=0.25,
        decomposition_accuracy=0.85,
        observation_sd=1.10,
        intervention_cost_scale=1.10,
        group_count=6,
        items_per_group=3,
        description="Counterfactual observations are noisy and relatively costly.",
    ),
    Scenario(
        "noisy_decomposition",
        coherence=0.80,
        semantic_alignment=0.10,
        confounding=0.80,
        drift_probability=0.25,
        decomposition_accuracy=0.52,
        observation_sd=0.65,
        intervention_cost_scale=1.00,
        group_count=6,
        items_per_group=3,
        description="Automatic grouping is near the representation failure boundary.",
    ),
    Scenario(
        "weak_structure",
        coherence=0.20,
        semantic_alignment=0.20,
        confounding=0.70,
        drift_probability=0.20,
        decomposition_accuracy=0.80,
        observation_sd=0.65,
        intervention_cost_scale=1.00,
        group_count=6,
        items_per_group=3,
        description="Items within a decomposed group share little mechanism-level effect.",
    ),
    Scenario(
        "semantic_aligned_stationary",
        coherence=0.70,
        semantic_alignment=0.90,
        confounding=0.05,
        drift_probability=0.00,
        decomposition_accuracy=0.90,
        observation_sd=0.55,
        intervention_cost_scale=1.00,
        group_count=6,
        items_per_group=3,
        description="Gap-absent control: semantic similarity already tracks deployment value.",
    ),
    Scenario(
        "high_intervention_cost",
        coherence=0.82,
        semantic_alignment=0.10,
        confounding=0.85,
        drift_probability=0.25,
        decomposition_accuracy=0.88,
        observation_sd=0.60,
        intervention_cost_scale=2.20,
        group_count=6,
        items_per_group=3,
        description="Gap is present but interventions are expensive.",
    ),
)


def clipped(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def build_episode(seed: int, episode: int, scenario: Scenario) -> Tuple[Task, List[MemoryPath], Dict[int, float]]:
    """Generate one task with randomly permuted mechanism values.

    No observed group identifier has a fixed semantic meaning across episodes.
    A policy cannot learn that, for example, group 0 is always valuable.
    """

    rng = random.Random((seed + 1) * 1_000_003 + episode * 9_176 + sum(ord(c) for c in scenario.name))
    task = Task(
        task_id=f"{scenario.name}_seed{seed:03d}_episode{episode:04d}",
        risk=rng.uniform(0.10, 1.00),
        ambiguity=rng.uniform(0.05, 1.00),
    )
    if scenario.group_count < 4 or scenario.items_per_group < 2:
        raise ValueError("randomized topology requires at least four groups and two items per group")
    group_values = [
        rng.uniform(1.65, 2.30),
        rng.uniform(0.75, 1.25),
        rng.uniform(0.45, 0.90),
        rng.uniform(-1.10, -0.45),
    ]
    group_values.extend(
        rng.uniform(-0.25, 1.10)
        for _ in range(scenario.group_count - len(group_values))
    )
    rng.shuffle(group_values)
    drift_group = rng.randrange(scenario.group_count) if rng.random() < scenario.drift_probability else -1
    paths: List[MemoryPath] = []

    for true_group in range(scenario.group_count):
        train_group_effect = group_values[true_group]
        test_group_effect = -0.75 * train_group_effect if true_group == drift_group else train_group_effect
        for local_index in range(scenario.items_per_group):
            independent_train = rng.gauss(0.0, 0.70)
            independent_test = rng.gauss(0.0, 0.70)
            train_effect = scenario.coherence * train_group_effect + (1.0 - scenario.coherence) * independent_train
            test_effect = scenario.coherence * test_group_effect + (1.0 - scenario.coherence) * independent_test
            if rng.random() <= scenario.decomposition_accuracy:
                observed_group = true_group
            else:
                observed_group = rng.choice(
                    [value for value in range(scenario.group_count) if value != true_group]
                )

            surface_noise = rng.gauss(0.0, 0.85)
            semantic = sigmoid(scenario.semantic_alignment * train_effect + surface_noise)
            # Under endogenous exposure, the observed success co-occurrence
            # increasingly reflects retrieval popularity and easy-task mix
            # rather than the path's deployment effect.  When confounding is
            # near zero, the same signal remains a faithful effect proxy.
            retrieval_popularity = rng.uniform(0.0, 1.0)
            easy_success_cooccurrence = 2.20 * retrieval_popularity + rng.gauss(0.0, 0.35)
            association = (
                (1.0 - scenario.confounding) * train_effect
                + scenario.confounding * easy_success_cooccurrence
                + rng.gauss(0.0, 0.30)
            )
            probe_cost = scenario.intervention_cost_scale * rng.uniform(0.78, 1.22)
            execution_cost = rng.uniform(0.03, 0.14)
            observations = tuple(test_effect + rng.gauss(0.0, scenario.observation_sd) for _ in range(6))
            paths.append(
                MemoryPath(
                    path_id=f"{task.task_id}_g{true_group}_i{local_index}",
                    true_group=true_group,
                    observed_group=observed_group,
                    train_effect=train_effect,
                    test_effect=test_effect,
                    semantic_score=semantic,
                    association_score=association,
                    probe_cost=probe_cost,
                    execution_cost=execution_cost,
                    probe_priority=rng.random(),
                    item_observations=observations,
                )
            )

    group_noise = {
        observed_group: rng.gauss(0.0, scenario.observation_sd * 0.72)
        for observed_group in range(scenario.group_count)
    }
    return task, paths, group_noise


def path_value(task: Task, path: MemoryPath) -> float:
    positive = max(path.test_effect, 0.0)
    return path.test_effect - path.execution_cost + 0.10 * task.risk * positive


def normal_update(mu: float, sd: float, observation: float, observation_sd: float) -> Tuple[float, float]:
    prior_precision = 1.0 / (sd * sd)
    observation_precision = 1.0 / (observation_sd * observation_sd)
    variance = 1.0 / (prior_precision + observation_precision)
    return (
        variance * (prior_precision * mu + observation_precision * observation),
        math.sqrt(variance),
    )


def weak_association_prior(path: MemoryPath) -> Tuple[float, float]:
    return clipped(0.28 * path.association_score, -0.60, 0.85), 0.95


def task_budget(task: Task) -> float:
    """One fixed budget rule shared across every scenario; no domain tuning."""

    return 3.60 + 1.70 * task.risk + 1.25 * task.ambiguity


def select_by_item_probes(
    task: Task,
    paths: Sequence[MemoryPath],
    scenario: Scenario,
    policy: str,
) -> Tuple[MemoryPath, float, int]:
    posterior: Dict[str, Tuple[float, float]] = {path.path_id: weak_association_prior(path) for path in paths}
    counts = {path.path_id: 0 for path in paths}
    spent = 0.0
    budget = float("inf") if policy == "full_item_probe" else task_budget(task)

    while True:
        affordable = [
            path for path in paths
            if spent + path.probe_cost <= budget and counts[path.path_id] < len(path.item_observations)
        ]
        if not affordable:
            break
        if policy == "uniform_item_probe":
            unprobed = [path for path in affordable if counts[path.path_id] == 0]
            target = min(unprobed or affordable, key=lambda path: (path.probe_priority, path.path_id))
        elif policy == "greedy_item_lcb":
            unprobed = [path for path in affordable if counts[path.path_id] == 0]
            target = max(
                unprobed or affordable,
                key=lambda path: (
                    posterior[path.path_id][0] + 0.85 * posterior[path.path_id][1],
                    path.association_score,
                    path.path_id,
                ),
            )
        elif policy == "full_item_probe":
            unprobed = [path for path in affordable if counts[path.path_id] == 0]
            if not unprobed:
                break
            target = min(unprobed, key=lambda path: path.path_id)
        else:
            raise KeyError(policy)
        observation_index = counts[target.path_id]
        observation = target.item_observations[observation_index]
        posterior[target.path_id] = normal_update(
            *posterior[target.path_id], observation, scenario.observation_sd
        )
        counts[target.path_id] += 1
        spent += target.probe_cost

    risk_aversion = 0.45 + 0.35 * task.risk
    selected = max(
        paths,
        key=lambda path: (
            posterior[path.path_id][0] - risk_aversion * posterior[path.path_id][1],
            -path.execution_cost,
            path.path_id,
        ),
    )
    return selected, spent, sum(counts.values())


def select_hierarchical(
    task: Task,
    paths: Sequence[MemoryPath],
    group_noise: Mapping[int, float],
    scenario: Scenario,
    use_observational_agreement_gate: bool,
) -> Tuple[MemoryPath, float, int]:
    """Coarse-to-fine intervention without path-level mechanism labels."""

    if use_observational_agreement_gate:
        semantic_top = sorted(paths, key=lambda path: (path.semantic_score, path.path_id), reverse=True)[:4]
        association_top = sorted(paths, key=lambda path: (path.association_score, path.path_id), reverse=True)[:4]
        overlap = len({path.path_id for path in semantic_top} & {path.path_id for path in association_top})
        # If two independently available observational views agree on most of
        # the shortlist, intervention is unlikely to repay its cost.  The gate
        # has no learned or domain-specific parameter and uses no latent label.
        if overlap >= 3:
            return association_top[0], 0.0, 0

    budget = task_budget(task)
    spent = 0.0
    probes = 0
    groups: Dict[int, List[MemoryPath]] = {group: [] for group in range(scenario.group_count)}
    for path in paths:
        groups[path.observed_group].append(path)

    group_posterior: Dict[int, Tuple[float, float]] = {group: (0.0, 1.10) for group in groups}
    group_order = sorted(groups, key=lambda group: stable_hash((task.task_id, "group", group)))
    for group in group_order:
        members = groups[group]
        if not members:
            continue
        group_cost = scenario.intervention_cost_scale * (0.48 + 0.025 * len(members))
        if spent + group_cost > budget:
            break
        observation = mean(path.test_effect for path in members) + group_noise[group]
        group_posterior[group] = normal_update(
            *group_posterior[group], observation, scenario.observation_sd * 0.72
        )
        spent += group_cost
        probes += 1

    # Group probes define a data-derived prior.  Associational history is kept
    # weak to avoid discarding useful information while preventing it from
    # overriding intervention evidence.
    item_posterior: Dict[str, Tuple[float, float]] = {}
    item_counts = {path.path_id: 0 for path in paths}
    for path in paths:
        group_mu, group_sd = group_posterior[path.observed_group]
        assoc_mu, _ = weak_association_prior(path)
        item_posterior[path.path_id] = (
            0.82 * group_mu + 0.18 * assoc_mu,
            math.sqrt(group_sd * group_sd + 0.34 * 0.34),
        )

    promising_group_count = max(1, int(math.sqrt(len(groups))))
    promising_groups = {
        group
        for group, _ in sorted(
            group_posterior.items(),
            key=lambda item: (item[1][0] - 0.45 * item[1][1], item[0]),
            reverse=True,
        )[:promising_group_count]
    }

    while True:
        affordable = [
            path for path in paths
            if path.observed_group in promising_groups
            and spent + path.probe_cost <= budget
            and item_counts[path.path_id] < len(path.item_observations)
        ]
        if not affordable:
            break
        unprobed = [path for path in affordable if item_counts[path.path_id] == 0]
        target = max(
            unprobed or affordable,
            key=lambda path: (
                item_posterior[path.path_id][0]
                + (0.80 + 0.35 * task.risk) * item_posterior[path.path_id][1]
                - 0.08 * path.probe_cost,
                -item_counts[path.path_id],
                path.path_id,
            ),
        )
        index = item_counts[target.path_id]
        observation = target.item_observations[index]
        item_posterior[target.path_id] = normal_update(
            *item_posterior[target.path_id], observation, scenario.observation_sd
        )
        item_counts[target.path_id] += 1
        spent += target.probe_cost
        probes += 1

    risk_aversion = 0.45 + 0.35 * task.risk
    selected = max(
        paths,
        key=lambda path: (
            item_posterior[path.path_id][0] - risk_aversion * item_posterior[path.path_id][1],
            -path.execution_cost,
            path.path_id,
        ),
    )
    return selected, spent, probes


def run_policy(
    task: Task,
    paths: Sequence[MemoryPath],
    group_noise: Mapping[int, float],
    scenario: Scenario,
    policy: str,
) -> Dict[str, float | str]:
    if policy == "semantic":
        selected = max(paths, key=lambda path: (path.semantic_score, path.path_id))
        spent = 0.0
        probes = 0
    elif policy == "association":
        selected = max(paths, key=lambda path: (path.association_score, path.path_id))
        spent = 0.0
        probes = 0
    elif policy == "fixed_hybrid":
        selected = max(
            paths,
            key=lambda path: (0.55 * path.semantic_score + 0.45 * sigmoid(path.association_score), path.path_id),
        )
        spent = 0.0
        probes = 0
    elif policy in {"uniform_item_probe", "greedy_item_lcb", "full_item_probe"}:
        selected, spent, probes = select_by_item_probes(task, paths, scenario, policy)
    elif policy in {"hierarchical_no_gate", "hierarchical_framework"}:
        selected, spent, probes = select_hierarchical(
            task,
            paths,
            group_noise,
            scenario,
            use_observational_agreement_gate=policy == "hierarchical_framework",
        )
    else:
        raise KeyError(policy)

    oracle = max(paths, key=lambda path: (path_value(task, path), path.path_id))
    selected_value = path_value(task, selected)
    cost_weight = 0.10
    return {
        "policy": policy,
        "regret": max(0.0, path_value(task, oracle) - selected_value),
        "gross_value": selected_value,
        "net_utility": selected_value - cost_weight * spent,
        "positive_selection": float(selected.test_effect > 0.35),
        "harmful_selection": float(selected.test_effect < 0.0),
        "intervention_cost": spent,
        "probes": float(probes),
        "oracle_value": path_value(task, oracle),
    }


METRICS = (
    "regret",
    "gross_value",
    "net_utility",
    "positive_selection",
    "harmful_selection",
    "intervention_cost",
    "probes",
    "oracle_value",
)


def aggregate_seed(seed: int, scenario: Scenario, episodes: int) -> List[Dict[str, float | str]]:
    collected: Dict[str, List[Dict[str, float | str]]] = {policy: [] for policy in POLICIES}
    stream_hashes = []
    for episode in range(episodes):
        task, paths, group_noise = build_episode(seed, episode, scenario)
        stream_hashes.append(stable_hash((asdict(task), [asdict(path) for path in paths], group_noise)))
        for policy in POLICIES:
            collected[policy].append(run_policy(task, paths, group_noise, scenario, policy))
    shared_hash = stable_hash(stream_hashes)
    rows: List[Dict[str, float | str]] = []
    for policy in POLICIES:
        row: Dict[str, float | str] = {
            "seed": float(seed),
            "scenario": scenario.name,
            "policy": policy,
            "candidate_stream_sha256": shared_hash,
            "coherence": scenario.coherence,
            "semantic_alignment": scenario.semantic_alignment,
            "confounding": scenario.confounding,
            "drift_probability": scenario.drift_probability,
            "decomposition_accuracy": scenario.decomposition_accuracy,
            "observation_sd": scenario.observation_sd,
            "intervention_cost_scale": scenario.intervention_cost_scale,
            "group_count": float(scenario.group_count),
            "items_per_group": float(scenario.items_per_group),
        }
        for metric in METRICS:
            row[metric] = mean(float(item[metric]) for item in collected[policy])
        rows.append(row)
    return rows


def summarize(rows: Sequence[Dict[str, float | str]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    output: Dict[str, Dict[str, Dict[str, float]]] = {}
    for scenario in [value.name for value in SCENARIOS] + ["randomized_worlds"]:
        scenario_rows = [row for row in rows if row["scenario"] == scenario]
        if not scenario_rows:
            continue
        output[scenario] = {}
        for policy in POLICIES:
            selected = [row for row in scenario_rows if row["policy"] == policy]
            output[scenario][policy] = {}
            for metric in METRICS:
                values = [float(row[metric]) for row in selected]
                sd = stdev(values) if len(values) > 1 else 0.0
                output[scenario][policy][metric] = {
                    "mean": mean(values),
                    "sd": sd,
                    "ci95": 1.96 * sd / math.sqrt(len(values)),
                    "n": float(len(values)),
                }
    return output


def random_scenario(seed: int) -> Scenario:
    rng = random.Random(70_000_019 + seed * 13_337)
    return Scenario(
        name="randomized_worlds",
        coherence=rng.uniform(0.40, 0.95),
        semantic_alignment=rng.uniform(-0.35, 0.80),
        confounding=rng.uniform(0.20, 1.00),
        drift_probability=rng.uniform(0.00, 0.55),
        decomposition_accuracy=rng.uniform(0.62, 0.98),
        observation_sd=rng.uniform(0.40, 1.05),
        intervention_cost_scale=rng.uniform(0.75, 1.50),
        group_count=rng.randint(4, 10),
        items_per_group=rng.randint(2, 5),
        description="Each seed samples a new DGP and candidate topology from a preregistered parameter box.",
    )


def pairwise_framework_wins(rows: Sequence[Dict[str, float | str]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    output: Dict[str, Dict[str, Dict[str, float]]] = {}
    scenarios = sorted({str(row["scenario"]) for row in rows})
    for scenario in scenarios:
        output[scenario] = {}
        scenario_rows = [row for row in rows if row["scenario"] == scenario]
        by_seed_policy = {(int(float(row["seed"])), str(row["policy"])): row for row in scenario_rows}
        seeds = sorted({int(float(row["seed"])) for row in scenario_rows})
        for baseline in POLICIES:
            if baseline == "hierarchical_framework":
                continue
            utility_deltas = [
                float(by_seed_policy[(seed, "hierarchical_framework")]["net_utility"])
                - float(by_seed_policy[(seed, baseline)]["net_utility"])
                for seed in seeds
            ]
            regret_deltas = [
                float(by_seed_policy[(seed, baseline)]["regret"])
                - float(by_seed_policy[(seed, "hierarchical_framework")]["regret"])
                for seed in seeds
            ]
            output[scenario][baseline] = {
                "net_utility_win_rate": mean(float(value > 0.0) for value in utility_deltas),
                "mean_net_utility_delta": mean(utility_deltas),
                "net_utility_delta_sd": stdev(utility_deltas) if len(utility_deltas) > 1 else 0.0,
                "net_utility_delta_ci95": (
                    1.96 * stdev(utility_deltas) / math.sqrt(len(utility_deltas))
                    if len(utility_deltas) > 1 else 0.0
                ),
                "regret_win_rate": mean(float(value > 0.0) for value in regret_deltas),
                "mean_regret_reduction": mean(regret_deltas),
                "regret_reduction_sd": stdev(regret_deltas) if len(regret_deltas) > 1 else 0.0,
                "regret_reduction_ci95": (
                    1.96 * stdev(regret_deltas) / math.sqrt(len(regret_deltas))
                    if len(regret_deltas) > 1 else 0.0
                ),
                "n_seeds": float(len(seeds)),
            }
    return output


def random_world_subgroups(rows: Sequence[Dict[str, float | str]]) -> Dict[str, object]:
    """Predefined theory-based strata, not post-hoc performance partitions."""

    random_rows = [row for row in rows if row["scenario"] == "randomized_worlds"]
    subgroup_rows: Dict[str, List[Dict[str, float | str]]] = {
        "identifiable_gap": [],
        "gap_but_structure_or_cost_failure": [],
        "weak_gap": [],
    }
    for row in random_rows:
        confounding = float(row["confounding"])
        identifiable = (
            float(row["coherence"]) >= 0.60
            and float(row["decomposition_accuracy"]) >= 0.70
            and float(row["intervention_cost_scale"]) <= 1.30
        )
        if confounding < 0.50:
            subgroup = "weak_gap"
        elif identifiable:
            subgroup = "identifiable_gap"
        else:
            subgroup = "gap_but_structure_or_cost_failure"
        copied = dict(row)
        copied["scenario"] = subgroup
        subgroup_rows[subgroup].append(copied)

    flattened = [row for values in subgroup_rows.values() for row in values]
    return {
        "definition": {
            "identifiable_gap": "confounding >= 0.50, coherence >= 0.60, decomposition_accuracy >= 0.70, intervention_cost_scale <= 1.30",
            "gap_but_structure_or_cost_failure": "confounding >= 0.50 and at least one identifiability/structure/cost condition fails",
            "weak_gap": "confounding < 0.50",
        },
        "seed_counts": {
            key: float(len({int(float(row["seed"])) for row in values}))
            for key, values in subgroup_rows.items()
        },
        "summary": summarize_named_scenarios(flattened),
        "framework_pairwise": pairwise_framework_wins(flattened),
    }


def summarize_named_scenarios(rows: Sequence[Dict[str, float | str]]) -> Dict[str, Dict[str, Dict[str, Dict[str, float]]]]:
    output: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    for scenario in sorted({str(row["scenario"]) for row in rows}):
        scenario_rows = [row for row in rows if row["scenario"] == scenario]
        output[scenario] = {}
        for policy in POLICIES:
            selected = [row for row in scenario_rows if row["policy"] == policy]
            if not selected:
                continue
            output[scenario][policy] = {}
            for metric in METRICS:
                values = [float(row[metric]) for row in selected]
                sd = stdev(values) if len(values) > 1 else 0.0
                output[scenario][policy][metric] = {
                    "mean": mean(values),
                    "sd": sd,
                    "ci95": 1.96 * sd / math.sqrt(len(values)),
                    "n": float(len(values)),
                }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--episodes", type=int, default=120)
    parser.add_argument("--random-world-seeds", type=int, default=120)
    parser.add_argument("--random-world-episodes", type=int, default=60)
    parser.add_argument("--output", type=Path, default=Path("structural_generalization_benchmark.json"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    rows: List[Dict[str, float | str]] = []
    for scenario in SCENARIOS:
        for seed in range(args.seeds):
            rows.extend(aggregate_seed(seed, scenario, args.episodes))
    for seed in range(args.random_world_seeds):
        rows.extend(aggregate_seed(seed, random_scenario(seed), args.random_world_episodes))

    result = {
        "protocol": {
            "purpose": "cross-DGP structural mechanism stress test; not a public Agent Memory benchmark",
            "fixed_hyperparameters": True,
            "per_domain_tuning": False,
            "manual_path_labels": False,
            "privileged_path_level_cues": False,
            "learned_parameters": False,
            "fine_tuning": False,
            "randomized_candidate_topology": True,
            "scenario_seeds": args.seeds,
            "episodes_per_scenario_seed": args.episodes,
            "random_world_seeds": args.random_world_seeds,
            "episodes_per_random_world": args.random_world_episodes,
            "policies": POLICIES,
            "shared": "candidate streams, observation draws, task budgets, evaluator and cost coefficient",
            "scenario_definitions": [asdict(value) for value in SCENARIOS],
            "random_world_parameter_box": {
                "coherence": [0.40, 0.95],
                "semantic_alignment": [-0.35, 0.80],
                "confounding": [0.20, 1.00],
                "drift_probability": [0.00, 0.55],
                "decomposition_accuracy": [0.62, 0.98],
                "observation_sd": [0.40, 1.05],
                "intervention_cost_scale": [0.75, 1.50],
                "group_count": [4, 10],
                "items_per_group": [2, 5],
            },
        },
        "summary": summarize(rows),
        "framework_pairwise": pairwise_framework_wins(rows),
        "random_world_subgroups": random_world_subgroups(rows),
        "per_seed_policy": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.quiet:
        print(json.dumps({"summary": result["summary"], "framework_pairwise": result["framework_pairwise"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
