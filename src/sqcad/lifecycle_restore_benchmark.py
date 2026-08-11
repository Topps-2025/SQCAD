"""Long-horizon lifecycle stress test for recoverable Agent Memory governance.

This benchmark tests the lifecycle part of the framework that a one-shot path
selector cannot test: a memory can be downweighted or archived during a regime
shift and become useful again after the regime recurs.  The policy observes
task/version metadata, noisy semantic cues, automatic groups, logged outcomes,
and interventions it actually pays for.  True groups and potential outcomes
are evaluator-only.

The result is a controlled mechanism study, not a public Agent Memory benchmark.
No policy is trained, fine-tuned, or tuned per scenario.  The main claim is
conditional: recoverable governance should help when regimes recur and false
forgetting is costly; irreversible or associative policies remain legitimate
controls when the regime never returns or the gap is weak.
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
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


POLICIES = (
    "association_irreversible",
    "item_causal_irreversible",
    "hierarchical_irreversible",
    "recoverable_framework",
)


@dataclass(frozen=True)
class Scenario:
    name: str
    drift: bool
    recurrence_probability: float
    confounding: float
    coherence: float
    decomposition_accuracy: float
    observation_sd: float
    intervention_cost_scale: float
    false_forgetting_weight: float
    horizon: int
    group_count: int
    items_per_group: int
    description: str


SCENARIOS: Tuple[Scenario, ...] = (
    Scenario(
        "recurring_regime_shift",
        drift=True,
        recurrence_probability=1.0,
        confounding=0.90,
        coherence=0.88,
        decomposition_accuracy=0.90,
        observation_sd=0.55,
        intervention_cost_scale=1.00,
        false_forgetting_weight=2.20,
        horizon=90,
        group_count=6,
        items_per_group=3,
        description="A useful mechanism becomes harmful, then returns after a version shift.",
    ),
    Scenario(
        "one_way_obsolescence",
        drift=True,
        recurrence_probability=0.0,
        confounding=0.90,
        coherence=0.88,
        decomposition_accuracy=0.90,
        observation_sd=0.55,
        intervention_cost_scale=1.00,
        false_forgetting_weight=2.20,
        horizon=90,
        group_count=6,
        items_per_group=3,
        description="A useful mechanism becomes obsolete and never returns.",
    ),
    Scenario(
        "weak_gap_stationary",
        drift=False,
        recurrence_probability=0.0,
        confounding=0.10,
        coherence=0.75,
        decomposition_accuracy=0.90,
        observation_sd=0.55,
        intervention_cost_scale=1.00,
        false_forgetting_weight=0.80,
        horizon=90,
        group_count=6,
        items_per_group=3,
        description="No meaningful exposure gap and no regime shift.",
    ),
    Scenario(
        "noisy_recurrence",
        drift=True,
        recurrence_probability=1.0,
        confounding=0.85,
        coherence=0.75,
        decomposition_accuracy=0.55,
        observation_sd=0.85,
        intervention_cost_scale=1.00,
        false_forgetting_weight=2.20,
        horizon=90,
        group_count=6,
        items_per_group=3,
        description="Recurrence exists but automatic grouping is near its failure boundary.",
    ),
    Scenario(
        "high_restore_cost",
        drift=True,
        recurrence_probability=1.0,
        confounding=0.85,
        coherence=0.88,
        decomposition_accuracy=0.90,
        observation_sd=0.65,
        intervention_cost_scale=2.20,
        false_forgetting_weight=2.20,
        horizon=90,
        group_count=6,
        items_per_group=3,
        description="Recurrence exists but restoration and probing are expensive.",
    ),
    Scenario(
        "stationary_associational_control",
        drift=False,
        recurrence_probability=0.0,
        confounding=0.05,
        coherence=0.92,
        decomposition_accuracy=0.95,
        observation_sd=0.45,
        intervention_cost_scale=1.00,
        false_forgetting_weight=0.60,
        horizon=90,
        group_count=6,
        items_per_group=3,
        description="Associational exposure is already a good proxy for value.",
    ),
)


@dataclass(frozen=True)
class MemoryItem:
    item_id: str
    true_group: int
    observed_group: int
    phase0_effect: float
    phase1_effect: float
    semantic_prior: float
    association_prior: float
    execution_cost: float


@dataclass(frozen=True)
class Task:
    task_id: str
    episode: int
    phase: int
    version: int
    target_group: int
    risk: float
    ambiguity: float
    semantic_scores: Mapping[str, float]


@dataclass(frozen=True)
class World:
    seed: int
    scenario: Scenario
    recurrence: bool
    drift_group: int
    items: Tuple[MemoryItem, ...]
    tasks: Tuple[Task, ...]
    stream_hash: str


@dataclass
class Belief:
    mean: float
    sd: float
    count: int = 0


def clipped(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def keyed_rng(*values: object) -> random.Random:
    digest = stable_hash(values)
    return random.Random(int(digest[:16], 16))


def normal_update(belief: Belief, observation: float, observation_sd: float) -> None:
    prior_precision = 1.0 / max(belief.sd * belief.sd, 1e-9)
    observation_precision = 1.0 / max(observation_sd * observation_sd, 1e-9)
    variance = 1.0 / (prior_precision + observation_precision)
    belief.mean = variance * (prior_precision * belief.mean + observation_precision * observation)
    belief.sd = math.sqrt(variance)
    belief.count += 1


def phase_for_episode(episode: int, horizon: int, recurrence: bool, drift: bool) -> int:
    if not drift:
        return 0
    if recurrence:
        return 0 if episode < horizon // 3 or episode >= 2 * horizon // 3 else 1
    return 0 if episode < horizon // 2 else 1


def build_world(seed: int, scenario: Scenario) -> World:
    if scenario.group_count < 4 or scenario.items_per_group < 2:
        raise ValueError("world topology must contain at least four groups and two items per group")
    rng = random.Random((seed + 17) * 1_000_003 + sum(ord(c) for c in scenario.name))
    recurrence = rng.random() < scenario.recurrence_probability
    drift_group = rng.randrange(scenario.group_count) if scenario.drift else -1
    group_values = [
        rng.uniform(1.70, 2.35),
        rng.uniform(0.65, 1.15),
        rng.uniform(0.25, 0.75),
        rng.uniform(-1.20, -0.55),
    ]
    group_values.extend(rng.uniform(-0.25, 1.05) for _ in range(scenario.group_count - 4))
    rng.shuffle(group_values)
    items: List[MemoryItem] = []
    for group in range(scenario.group_count):
        for index in range(scenario.items_per_group):
            observed_group = (
                group
                if rng.random() <= scenario.decomposition_accuracy
                else rng.choice([value for value in range(scenario.group_count) if value != group])
            )
            phase0 = scenario.coherence * group_values[group] + (1.0 - scenario.coherence) * rng.gauss(0.0, 0.65)
            if group == drift_group:
                phase1 = -0.82 * phase0 + rng.gauss(0.0, 0.12)
            else:
                phase1 = phase0 + rng.gauss(0.0, 0.10) if scenario.drift else phase0
            items.append(
                MemoryItem(
                    item_id=f"world{seed:04d}_g{group}_i{index}",
                    true_group=group,
                    observed_group=observed_group,
                    phase0_effect=phase0,
                    phase1_effect=phase1,
                    semantic_prior=clipped(rng.uniform(0.35, 0.75)),
                    association_prior=rng.uniform(-0.20, 1.20),
                    execution_cost=rng.uniform(0.03, 0.14),
                )
            )

    tasks: List[Task] = []
    for episode in range(scenario.horizon):
        phase = phase_for_episode(episode, scenario.horizon, recurrence, scenario.drift)
        version = phase
        target_group = drift_group if drift_group >= 0 and rng.random() < 0.32 else rng.randrange(scenario.group_count)
        risk = rng.uniform(0.10, 1.00)
        ambiguity = rng.uniform(0.05, 1.00)
        semantic_scores = {}
        for item in items:
            match = 1.0 if item.true_group == target_group else 0.0
            score = sigmoid(2.8 * match - 0.45 + rng.gauss(0.0, 0.95))
            semantic_scores[item.item_id] = score
        tasks.append(
            Task(
                task_id=f"{scenario.name}_seed{seed:04d}_episode{episode:04d}",
                episode=episode,
                phase=phase,
                version=version,
                target_group=target_group,
                risk=risk,
                ambiguity=ambiguity,
                semantic_scores=semantic_scores,
            )
        )
    stream_hash = stable_hash({"items": [asdict(item) for item in items], "tasks": [asdict(task) for task in tasks]})
    return World(seed, scenario, recurrence, drift_group, tuple(items), tuple(tasks), stream_hash)


def task_effect(item: MemoryItem, task: Task) -> float:
    base = item.phase0_effect if task.phase == 0 else item.phase1_effect
    match = 1.0 if item.true_group == task.target_group else 0.12
    return base * match


def task_budget(task: Task) -> float:
    return 2.15 + 1.10 * task.risk + 0.85 * task.ambiguity


def path_value(item: Optional[MemoryItem], task: Task) -> float:
    if item is None:
        return 0.0
    return task_effect(item, task) - item.execution_cost


def target_best_value(world: World, task: Task) -> float:
    return max([0.0] + [path_value(item, task) for item in world.items if item.true_group == task.target_group])


def probe_value(world: World, item: MemoryItem, task: Task, policy_seed: int, label: object, sd_scale: float) -> float:
    truth = task_effect(item, task)
    noise = keyed_rng(world.seed, task.episode, item.item_id, policy_seed, label).gauss(0.0, world.scenario.observation_sd * sd_scale)
    return truth + noise


def weak_association_prior(item: MemoryItem, task: Task, scenario: Scenario) -> float:
    # The score is intentionally endogenous: easy-task co-occurrence and
    # retrieval popularity are allowed to dominate when confounding is high.
    task_signal = task.semantic_scores[item.item_id]
    return (1.0 - scenario.confounding) * (0.55 * task_signal + 0.45 * item.association_prior) + scenario.confounding * item.association_prior


def initialise_beliefs(items: Sequence[MemoryItem]) -> Tuple[Dict[str, Belief], Dict[int, Belief]]:
    item_belief = {item.item_id: Belief(0.0, 1.15) for item in items}
    group_belief = {group: Belief(0.0, 1.30) for group in sorted({item.observed_group for item in items})}
    return item_belief, group_belief


def lcb(belief: Belief, risk: float) -> float:
    return belief.mean - (0.42 + 0.38 * risk) * belief.sd


def choose_promising_groups(groups: Mapping[int, List[MemoryItem]], group_belief: Mapping[int, Belief], task: Task) -> List[int]:
    count = max(1, int(math.sqrt(len(groups))))
    return [
        group
        for group, _ in sorted(
            groups.items(),
            key=lambda entry: (lcb(group_belief[entry[0]], task.risk), entry[0]),
            reverse=True,
        )[:count]
    ]


def run_policy(world: World, policy: str) -> Dict[str, object]:
    if policy not in POLICIES:
        raise KeyError(policy)
    items = {item.item_id: item for item in world.items}
    item_belief, group_belief = initialise_beliefs(world.items)
    groups: Dict[int, List[MemoryItem]] = {group: [] for group in sorted({item.observed_group for item in world.items})}
    for item in world.items:
        groups[item.observed_group].append(item)
    active = set(items)
    archived = set()
    deleted = set()
    association = {item.item_id: item.association_prior for item in world.items}
    group_observations: Dict[int, List[float]] = {group: [] for group in groups}
    last_version = world.tasks[0].version
    utility = 0.0
    regret = 0.0
    harmful = 0
    positive = 0
    false_forgetting = 0
    probes = 0
    probe_cost = 0.0
    restores = 0
    restore_successes = 0
    archive_events = 0
    recovery_latency: Optional[int] = None
    recurrence_start = 2 * world.scenario.horizon // 3 if world.recurrence else None
    log_rows: List[Dict[str, object]] = []

    for task in world.tasks:
        # A version change is observable metadata, but the useful group is not.
        if policy == "recoverable_framework" and task.version != last_version:
            # Restore only candidates with a current task signal.  The source
            # evidence survives, while Access Policy is re-opened provisionally.
            ranked_archived = sorted(
                archived,
                key=lambda item_id: (task.semantic_scores[item_id], item_id),
                reverse=True,
            )[: max(2, int(math.sqrt(max(1, len(archived)))))]
            for item_id in ranked_archived:
                archived.remove(item_id)
                active.add(item_id)
                restores += 1
            last_version = task.version

        budget = task_budget(task)
        spent = 0.0
        task_probes = 0
        if policy in {"hierarchical_irreversible", "recoverable_framework"}:
            # Group probes are treatment operations, not free labels.
            for group in sorted(groups):
                members = [item for item in groups[group] if item.item_id in active]
                group_cost = world.scenario.intervention_cost_scale * (0.42 + 0.025 * len(members))
                if not members or spent + group_cost > budget:
                    continue
                observations = [probe_value(world, item, task, world.seed, (policy, "group", group), 0.72) for item in members]
                group_observations[group].extend(observations)
                normal_update(group_belief[group], mean(observations), world.scenario.observation_sd * 0.72)
                spent += group_cost
                probe_cost += group_cost
                task_probes += 1
            promising = choose_promising_groups(groups, group_belief, task)
        else:
            promising = sorted(groups)

        if policy in {"item_causal_irreversible", "hierarchical_irreversible", "recoverable_framework"}:
            item_pool = [
                item
                for item in world.items
                if item.item_id in active
                and (
                    item.observed_group in promising
                    or policy in {"item_causal_irreversible", "recoverable_framework"}
                )
            ]
            item_pool = sorted(item_pool, key=lambda item: (task.semantic_scores[item.item_id], item.item_id), reverse=True)
            for item in item_pool[: max(1, int(2 + task.risk * 2))]:
                cost = world.scenario.intervention_cost_scale * 0.78
                if spent + cost > budget:
                    break
                observation = probe_value(world, item, task, world.seed, (policy, "item"), 1.0)
                normal_update(item_belief[item.item_id], observation, world.scenario.observation_sd)
                spent += cost
                probe_cost += cost
                task_probes += 1

        candidates = [items[item_id] for item_id in active]
        if not candidates:
            selected: Optional[MemoryItem] = None
        else:
            def score(item: MemoryItem) -> Tuple[float, str]:
                semantic = task.semantic_scores[item.item_id]
                if policy == "association_irreversible":
                    value = association[item.item_id] + 0.18 * semantic
                elif policy == "item_causal_irreversible":
                    value = lcb(item_belief[item.item_id], task.risk) + 0.12 * semantic
                elif policy in {"hierarchical_irreversible", "recoverable_framework"}:
                    group_value = lcb(group_belief[item.observed_group], task.risk)
                    item_value = lcb(item_belief[item.item_id], task.risk)
                    if policy == "recoverable_framework":
                        observations = group_observations[item.observed_group]
                        spread = stdev(observations) if len(observations) > 1 else world.scenario.observation_sd
                        trust = clipped(
                            1.0 / (1.0 + 0.55 * spread + 0.25 / max(1, group_belief[item.observed_group].count)),
                            0.25,
                            0.72,
                        )
                        # Group evidence is a prior, not a veto.  If the
                        # item-level lower bound is already negative, fall
                        # back to the item rather than propagating a noisy
                        # group decision to every member.
                        value = trust * group_value + (1.0 - trust) * item_value + 0.16 * semantic
                        if item_belief[item.item_id].count >= 2 and item_value < -0.25:
                            value -= 0.75
                    else:
                        value = 0.74 * group_value + 0.26 * item_value + 0.16 * semantic
                else:
                    raise AssertionError(policy)
                return value - 0.04 * item.execution_cost, item.item_id

            selected = max(candidates, key=score)
            if score(selected)[0] < 0.0 and policy != "association_irreversible":
                selected = None

        oracle = max([None] + list(world.items), key=lambda item: path_value(item, task))
        selected_effect = task_effect(selected, task) if selected is not None else 0.0
        selected_value = path_value(selected, task)
        oracle_value = path_value(oracle, task)
        task_false_forgetting = (
            oracle is not None
            and oracle_value > 0.55
            and selected is None
            and all(item.item_id not in active for item in world.items if item.true_group == task.target_group)
        )
        ff_penalty = world.scenario.false_forgetting_weight * float(task_false_forgetting)
        task_utility = selected_value - 0.10 * spent - ff_penalty
        utility += task_utility
        regret += max(0.0, oracle_value - selected_value)
        harmful += int(selected is not None and selected_effect < -0.10)
        positive += int(selected is not None and selected_effect > 0.45)
        false_forgetting += int(task_false_forgetting)
        if recurrence_start is not None and task.episode >= recurrence_start and recovery_latency is None and selected is not None:
            if selected.true_group == world.drift_group and selected_effect > 0.45:
                recovery_latency = task.episode - recurrence_start
                restore_successes += 1
        if selected is not None:
            # Every policy sees the same realized action outcome; the policy's
            # state update differs only by its declared governance rule.
            confounded_outcome = selected_effect + 0.35 * world.scenario.confounding * (task.risk < 0.45) + keyed_rng(world.seed, task.episode, selected.item_id, "outcome").gauss(0.0, world.scenario.observation_sd)
            association[selected.item_id] = 0.86 * association[selected.item_id] + 0.14 * confounded_outcome
            if policy in {"item_causal_irreversible", "hierarchical_irreversible", "recoverable_framework"}:
                normal_update(item_belief[selected.item_id], confounded_outcome, world.scenario.observation_sd)

            # Lifecycle update: negative lower bounds leave the hot policy.
            selected_belief = item_belief[selected.item_id]
            negative = selected_belief.mean - 0.25 * selected_belief.sd < -0.20 or confounded_outcome < -0.35
            if negative and selected.item_id in active:
                active.remove(selected.item_id)
                archived.add(selected.item_id)
                archive_events += 1
                if policy != "recoverable_framework":
                    deleted.add(selected.item_id)

        probes += task_probes

        log_rows.append(
            {
                "task_id": task.task_id,
                "version": task.version,
                "selected_id": selected.item_id if selected is not None else None,
                "selected_effect": selected_effect,
                "oracle_value": oracle_value,
                "utility": task_utility,
                "false_forgetting": int(task_false_forgetting),
                "active_count": len(active),
                "archived_count": len(archived),
                "probes": task_probes,
                "restore_count": restores,
            }
        )

    return {
        "policy": policy,
        "seed": float(world.seed),
        "scenario": world.scenario.name,
        "candidate_stream_sha256": world.stream_hash,
        "recurrence": float(world.recurrence),
        "utility": utility / world.scenario.horizon,
        "regret": regret / world.scenario.horizon,
        "harmful_selection": harmful / world.scenario.horizon,
        "positive_selection": positive / world.scenario.horizon,
        "false_forgetting_rate": false_forgetting / world.scenario.horizon,
        "probe_cost": probe_cost / world.scenario.horizon,
        "mean_probes": probes / world.scenario.horizon,
        "archive_events": float(archive_events),
        "restore_events": float(restores),
        "restore_successes": float(restore_successes),
        "recovery_latency": float(recovery_latency if recovery_latency is not None else world.scenario.horizon),
        "evidence_survival": 1.0 if policy == "recoverable_framework" else float(len(deleted) == 0),
        "decision_log_completeness": len(log_rows) / world.scenario.horizon,
        "decision_log": log_rows,
    }


METRICS = (
    "utility",
    "regret",
    "harmful_selection",
    "positive_selection",
    "false_forgetting_rate",
    "probe_cost",
    "mean_probes",
    "archive_events",
    "restore_events",
    "restore_successes",
        "recovery_latency",
    "evidence_survival",
    "decision_log_completeness",
)


def aggregate_seed(seed: int, scenario: Scenario) -> List[Dict[str, object]]:
    world = build_world(seed, scenario)
    rows = []
    for policy in POLICIES:
        row = run_policy(world, policy)
        rows.append(row)
    if len({row["candidate_stream_sha256"] for row in rows}) != 1:
        raise RuntimeError("all policies must receive the same world stream")
    return rows


def summarize(rows: Sequence[Mapping[str, object]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    output: Dict[str, Dict[str, Dict[str, float]]] = {}
    for scenario in sorted({str(row["scenario"]) for row in rows}):
        output[scenario] = {}
        for policy in POLICIES:
            selected = [row for row in rows if row["scenario"] == scenario and row["policy"] == policy]
            output[scenario][policy] = {}
            for metric in METRICS:
                values = [float(row[metric]) for row in selected]
                sd = stdev(values) if len(values) > 1 else 0.0
                output[scenario][policy][metric] = {
                    "mean": mean(values),
                    "sd": sd,
                    "ci95": 1.96 * sd / math.sqrt(len(values)) if len(values) > 1 else 0.0,
                    "n": float(len(values)),
                }
    return output


def pairwise_framework(rows: Sequence[Mapping[str, object]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    output: Dict[str, Dict[str, Dict[str, float]]] = {}
    for scenario in sorted({str(row["scenario"]) for row in rows}):
        output[scenario] = {}
        scenario_rows = [row for row in rows if row["scenario"] == scenario]
        seeds = sorted({int(float(row["seed"])) for row in scenario_rows})
        lookup = {(int(float(row["seed"])), str(row["policy"])): row for row in scenario_rows}
        for baseline in POLICIES:
            if baseline == "recoverable_framework":
                continue
            utility_delta = [
                float(lookup[(seed, "recoverable_framework")]["utility"]) - float(lookup[(seed, baseline)]["utility"])
                for seed in seeds
            ]
            regret_delta = [
                float(lookup[(seed, baseline)]["regret"]) - float(lookup[(seed, "recoverable_framework")]["regret"])
                for seed in seeds
            ]
            output[scenario][baseline] = {
                "mean_utility_delta": mean(utility_delta),
                "utility_delta_ci95": 1.96 * stdev(utility_delta) / math.sqrt(len(seeds)) if len(seeds) > 1 else 0.0,
                "utility_win_rate": mean(float(value > 0.0) for value in utility_delta),
                "mean_regret_reduction": mean(regret_delta),
                "regret_reduction_ci95": 1.96 * stdev(regret_delta) / math.sqrt(len(seeds)) if len(seeds) > 1 else 0.0,
                "regret_win_rate": mean(float(value > 0.0) for value in regret_delta),
                "n_seeds": float(len(seeds)),
            }
    return output


def random_scenario(seed: int) -> Scenario:
    rng = random.Random(91_171 + seed * 7_919)
    recurring = rng.random() < 0.62
    drift = rng.random() < 0.78
    return Scenario(
        name="randomized_lifecycle_worlds",
        drift=drift,
        recurrence_probability=1.0 if recurring else 0.0,
        confounding=rng.uniform(0.05, 1.00),
        coherence=rng.uniform(0.50, 0.95),
        decomposition_accuracy=rng.uniform(0.55, 0.98),
        observation_sd=rng.uniform(0.40, 1.10),
        intervention_cost_scale=rng.uniform(0.75, 2.30),
        false_forgetting_weight=rng.uniform(0.50, 2.50),
        horizon=90,
        group_count=rng.randint(4, 10),
        items_per_group=rng.randint(2, 5),
        description="Randomized lifecycle DGP with recurrence, drift, and candidate topology.",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--random-world-seeds", type=int, default=120)
    parser.add_argument("--output", type=Path, default=Path("lifecycle_restore_benchmark.json"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    rows: List[Dict[str, object]] = []
    for scenario in SCENARIOS:
        for seed in range(args.seeds):
            rows.extend(aggregate_seed(seed, scenario))
    random_rows: List[Dict[str, object]] = []
    for seed in range(args.random_world_seeds):
        scenario = random_scenario(seed)
        random_rows.extend(aggregate_seed(seed, scenario))
    rows.extend(random_rows)
    result = {
        "protocol": {
            "purpose": "long-horizon lifecycle and recoverability mechanism stress test; not a public benchmark",
            "fixed_hyperparameters": True,
            "per_domain_tuning": False,
            "manual_path_labels": False,
            "privileged_path_level_cues": False,
            "learned_parameters": False,
            "fine_tuning": False,
            "scenario_seeds": args.seeds,
            "random_world_seeds": args.random_world_seeds,
            "horizon": 90,
            "policies": POLICIES,
            "shared": "world stream, tasks, semantic cues, potential outcomes, evaluator and cost contract",
            "scenario_definitions": [asdict(scenario) for scenario in SCENARIOS],
            "random_world_parameter_box": {
                "recurrence_probability": [0.0, 1.0],
                "confounding": [0.05, 1.00],
                "coherence": [0.50, 0.95],
                "decomposition_accuracy": [0.55, 0.98],
                "intervention_cost_scale": [0.75, 2.30],
                "group_count": [4, 10],
                "items_per_group": [2, 5],
            },
        },
        "summary": summarize(rows),
        "framework_pairwise": pairwise_framework(rows),
        "per_seed_policy": [
            {key: value for key, value in row.items() if key != "decision_log"}
            for row in rows
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.quiet:
        print(json.dumps({"summary": result["summary"], "framework_pairwise": result["framework_pairwise"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
