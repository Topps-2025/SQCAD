"""Fixed-protocol challenge suite for the minimal Agent Memory framework.

This experiment asks which proposed modules remain necessary after comparison
against simpler alternatives. It reuses the lifecycle world's potential
outcomes, but replaces the policy layer with an explicit modular design:

1. associational versus intervention-updated beliefs;
2. item-only versus noisy hierarchical treatment construction;
3. fixed versus task-adaptive information budgets;
4. group-to-item correction with or without an item-level veto;
5. fixed temporal decay versus risk-conditioned access decay;
6. irreversible retirement versus evidence-preserving restoration.

The protocol is intentionally fixed across scenarios. No policy reads latent
effects or true groups, except the named oracle upper bound. Ordinary online
outcomes update associational statistics only; causal beliefs are updated only
by interventions actually paid for.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import NormalDist, mean, stdev
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "lifecycle_restore_benchmark.py"
RESULTS_DIR = ROOT / "results"


def load_base_module():
    spec = importlib.util.spec_from_file_location("minimality_lifecycle_base", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load lifecycle base from {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base_module()


@dataclass(frozen=True)
class PolicySpec:
    name: str
    causal: bool
    hierarchical: bool
    adaptive_budget: bool
    sentinel_correction: bool
    decay_rule: str
    recoverable: bool
    restore_enabled: bool
    conditional_association: bool = False
    oracle_groups: bool = False
    no_memory: bool = False


POLICY_SPECS: Tuple[PolicySpec, ...] = (
    PolicySpec(
        "no_memory",
        causal=False,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="none",
        recoverable=True,
        restore_enabled=False,
        no_memory=True,
    ),
    PolicySpec(
        "association_fixed_decay",
        causal=False,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="fixed",
        recoverable=False,
        restore_enabled=False,
    ),
    PolicySpec(
        "association_recoverable_decay",
        causal=False,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="fixed",
        recoverable=True,
        restore_enabled=True,
    ),
    PolicySpec(
        "conditional_association_recoverable",
        causal=False,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="fixed",
        recoverable=True,
        restore_enabled=True,
        conditional_association=True,
    ),
    PolicySpec(
        "conditional_association_fixed_no_restore",
        causal=False,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="fixed",
        recoverable=False,
        restore_enabled=False,
        conditional_association=True,
    ),
    PolicySpec(
        "item_causal_fixed_no_restore",
        causal=True,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="fixed",
        recoverable=False,
        restore_enabled=False,
        conditional_association=True,
    ),
    PolicySpec(
        "item_causal_fixed_recoverable",
        causal=True,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="fixed",
        recoverable=True,
        restore_enabled=True,
        conditional_association=True,
    ),
    PolicySpec(
        "item_causal_risk_no_restore",
        causal=True,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="risk",
        recoverable=False,
        restore_enabled=False,
        conditional_association=True,
    ),
    PolicySpec(
        "minimal_framework",
        causal=True,
        hierarchical=False,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="risk",
        recoverable=True,
        restore_enabled=True,
        conditional_association=True,
    ),
    PolicySpec(
        "task_adaptive_cap_candidate",
        causal=True,
        hierarchical=False,
        adaptive_budget=True,
        sentinel_correction=False,
        decay_rule="risk",
        recoverable=True,
        restore_enabled=True,
        conditional_association=True,
    ),
    PolicySpec(
        "hierarchical_candidate",
        causal=True,
        hierarchical=True,
        adaptive_budget=False,
        sentinel_correction=False,
        decay_rule="risk",
        recoverable=True,
        restore_enabled=True,
        conditional_association=True,
    ),
    PolicySpec(
        "hierarchical_sentinel_candidate",
        causal=True,
        hierarchical=True,
        adaptive_budget=False,
        sentinel_correction=True,
        decay_rule="risk",
        recoverable=True,
        restore_enabled=True,
        conditional_association=True,
    ),
    PolicySpec(
        "oracle_structure_reference",
        causal=True,
        hierarchical=True,
        adaptive_budget=False,
        sentinel_correction=True,
        decay_rule="risk",
        recoverable=True,
        restore_enabled=True,
        conditional_association=True,
        oracle_groups=True,
    ),
)

POLICIES = tuple(spec.name for spec in POLICY_SPECS)
POLICY_BY_NAME = {spec.name: spec for spec in POLICY_SPECS}

# Exact expectation of base.task_budget under the task generator's uniform
# risk U(0.10, 1.00) and ambiguity U(0.05, 1.00); not selected from outcomes.
FIXED_EXPECTED_BUDGET = 2.15 + 1.10 * 0.55 + 0.85 * 0.525
FIXED_DECAY_RATE = 0.035
ARCHIVE_THRESHOLD = 0.12
RESTORE_FLOOR = 0.38
PROBE_COST_WEIGHT = 0.10
NORMAL = NormalDist()
EVSI_Z_NODES = tuple(NORMAL.inv_cdf((index + 0.5) / 32.0) for index in range(32))


@dataclass
class Belief:
    mean: float = 0.0
    sd: float = 1.15
    count: int = 0


def clipped(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def normal_update(belief: Belief, observation: float, observation_sd: float) -> None:
    prior_precision = 1.0 / max(belief.sd * belief.sd, 1e-9)
    observation_precision = 1.0 / max(observation_sd * observation_sd, 1e-9)
    variance = 1.0 / (prior_precision + observation_precision)
    belief.mean = variance * (
        prior_precision * belief.mean + observation_precision * observation
    )
    belief.sd = math.sqrt(variance)
    belief.count += 1


def expected_positive_and_negative(belief: Belief) -> Tuple[float, float]:
    sd = max(belief.sd, 1e-6)
    z = belief.mean / sd
    density = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    positive = sd * density + belief.mean * NORMAL.cdf(z)
    negative = sd * density - belief.mean * NORMAL.cdf(-z)
    return max(0.0, positive), max(0.0, negative)


def bayes_action_value(belief: Belief, risk: float) -> float:
    """Posterior use value under asymmetric negative-effect loss."""

    positive, negative = expected_positive_and_negative(belief)
    return positive - (1.0 + risk) * negative


def qualified_action_value(
    belief: Belief,
    risk: float,
    family_size: int,
) -> float:
    """Return Bayes value only after a one-sided family-wise qualification gate."""

    if belief.count <= 0:
        return -math.inf
    alpha = sequential_qualification_alpha(belief.count, family_size)
    z_score = belief.mean / max(belief.sd, 1e-9)
    if 1.0 - NORMAL.cdf(z_score) > alpha:
        return -math.inf
    return bayes_action_value(belief, risk)


def causal_qualification_state(belief: Belief, family_size: int) -> str:
    if belief.count <= 0:
        return "unresolved"
    alpha = sequential_qualification_alpha(belief.count, family_size)
    positive_probability = NORMAL.cdf(
        belief.mean / max(belief.sd, 1e-9)
    )
    if 1.0 - positive_probability <= alpha:
        return "positive-qualified"
    if positive_probability <= alpha:
        return "negative-qualified"
    return "unresolved"


def sequential_qualification_alpha(count: int, family_size: int) -> float:
    """Bonferroni plus summable alpha spending for repeated sequential looks."""

    look = max(1, count)
    return (
        0.05
        / max(1, family_size)
        * 6.0
        / (math.pi * math.pi * look * look)
    )


def conditional_association_value(
    association: float,
    semantic_scope: float,
    risk: float,
    execution_cost: float,
) -> float:
    """Current-task fallback value; never a causal qualification signal."""

    return (1.0 - clipped(risk)) * (
        association * clipped(semantic_scope) - execution_cost
    )


def governed_access_value(
    belief: Belief,
    family_size: int,
    full_association_value: float,
    conditional_fallback_value: float,
) -> float:
    state = causal_qualification_state(belief, family_size)
    if state == "positive-qualified":
        return max(0.0, full_association_value)
    if state == "negative-qualified":
        return 0.0
    return max(0.0, conditional_fallback_value)


def qualification_evsi(
    belief: Belief,
    observation_sd: float,
    family_size: int,
    full_association_value: float,
    conditional_fallback_value: float,
    alternative_value: float,
) -> float:
    prior_var = max(belief.sd * belief.sd, 1e-9)
    noise_var = max(observation_sd * observation_sd, 1e-9)
    posterior_var = 1.0 / (1.0 / prior_var + 1.0 / noise_var)
    posterior_sd = math.sqrt(posterior_var)
    preposterior_sd = prior_var / math.sqrt(prior_var + noise_var)
    alternative_value = max(0.0, alternative_value)
    expected_after = mean(
        max(
            alternative_value,
            governed_access_value(
                Belief(
                    mean=belief.mean + preposterior_sd * z_node,
                    sd=posterior_sd,
                    count=belief.count + 1,
                ),
                family_size,
                full_association_value,
                conditional_fallback_value,
            ),
        )
        for z_node in EVSI_Z_NODES
    )
    current = max(
        alternative_value,
        governed_access_value(
            belief,
            family_size,
            full_association_value,
            conditional_fallback_value,
        ),
    )
    return max(0.0, expected_after - current)


def one_step_evsi(
    belief: Belief,
    observation_sd: float,
    risk: float,
    alternative_value: float = 0.0,
) -> float:
    """Analytic one-step expected value of sample information.

    The downstream action is use-versus-abstain under the same risk-adjusted
    lower-confidence value used by selection.  A probe is therefore valuable
    only when it can change that decision; entropy reduction alone is not
    treated as utility.
    """

    prior_var = max(belief.sd * belief.sd, 1e-9)
    noise_var = max(observation_sd * observation_sd, 1e-9)
    posterior_var = 1.0 / (1.0 / prior_var + 1.0 / noise_var)
    posterior_sd = math.sqrt(posterior_var)
    preposterior_sd = prior_var / math.sqrt(prior_var + noise_var)
    alternative_value = max(0.0, alternative_value)
    expected_after = mean(
        max(
            alternative_value,
            bayes_action_value(
                Belief(
                    mean=(
                        belief.mean
                        if preposterior_sd <= 1e-9
                        else belief.mean
                        + preposterior_sd
                        * z_node
                    ),
                    sd=posterior_sd,
                    count=belief.count + 1,
                ),
                risk,
            ),
        )
        for z_node in EVSI_Z_NODES
    )
    current = max(
        alternative_value,
        bayes_action_value(belief, risk),
    )
    return max(0.0, expected_after - current)


def group_map(world, spec: PolicySpec) -> Dict[int, List[object]]:
    groups: Dict[int, List[object]] = {}
    for item in world.items:
        group = item.true_group if spec.oracle_groups else item.observed_group
        groups.setdefault(group, []).append(item)
    return groups


def common_probe(world, item, task, level: str, group: int = -1) -> float:
    label = ("shared-probe", level, group, item.item_id)
    scale = 0.72 if level == "group" else 1.0
    return base.probe_value(world, item, task, 0, label, scale)


def common_online_outcome(world, item, task) -> float:
    effect = base.task_effect(item, task)
    easy_task_bias = 0.35 * world.scenario.confounding * float(task.risk < 0.45)
    noise = base.keyed_rng(world.seed, task.episode, item.item_id, "shared-online-outcome").gauss(
        0.0, world.scenario.observation_sd
    )
    return effect + easy_task_bias + noise


def historical_association_prior(world, item, sample_size: int = 64) -> float:
    """Generate an observable success co-occurrence statistic from a micro-log.

    Latent task difficulty affects both memory exposure and outcome.  The
    resulting exposed-only mean is close to the item effect when confounding is
    weak and selection-biased when confounding is strong.  Policies receive
    only this scalar summary, never the latent difficulty or item effect.
    """

    rng = base.keyed_rng(world.seed, -1, item.item_id, "historical-association-log")
    exposed_outcomes: List[float] = []
    for _ in range(sample_size):
        difficulty = rng.gauss(0.0, 1.0)
        exposure_probability = base.sigmoid(
            -0.20
            - world.scenario.confounding * difficulty
            + 0.25 * item.semantic_prior
        )
        if rng.random() <= exposure_probability:
            exposed_outcomes.append(
                item.phase0_effect
                - world.scenario.confounding * difficulty
                + rng.gauss(0.0, world.scenario.observation_sd)
            )
    return mean(exposed_outcomes) if exposed_outcomes else 0.0


def policy_budget(task, spec: PolicySpec) -> float:
    return base.task_budget(task) if spec.adaptive_budget else FIXED_EXPECTED_BUDGET


def apply_fixed_decay(access: MutableMapping[str, float]) -> None:
    multiplier = math.exp(-FIXED_DECAY_RATE)
    for item_id in access:
        access[item_id] *= multiplier


def apply_risk_decay(
    world,
    task,
    item_belief: Mapping[str, Belief],
    access: MutableMapping[str, float],
) -> None:
    """Update access from a Bayes risk difference rather than elapsed time.

    The retain action pays expected negative-effect loss; the archive action
    pays false-forgetting loss on the positive tail. The access state decays
    only when the retain loss is larger. Favorable evidence can raise access
    again, so this operator is reversible by construction.
    """

    for item in world.items:
        belief = item_belief[item.item_id]
        qualification = causal_qualification_state(
            belief,
            len(item_belief),
        )
        if qualification == "unresolved":
            continue
        positive, negative = expected_positive_and_negative(belief)
        scope_match = task.semantic_scores[item.item_id]
        retain_loss = (
            scope_match * (1.0 + task.risk) * negative
            + item.execution_cost
        )
        archive_loss = (
            world.scenario.false_forgetting_weight
            * scope_match
            * positive
        )
        margin = retain_loss - archive_loss
        if margin > 0.0:
            access[item.item_id] *= math.exp(-margin)
        else:
            recovery = 1.0 - math.exp(margin)
            access[item.item_id] += (1.0 - access[item.item_id]) * recovery
        access[item.item_id] = clipped(access[item.item_id])


def prepare_restoration(
    world,
    task,
    spec: PolicySpec,
    item_belief: Mapping[str, Belief],
    association: Mapping[str, float],
    access: MutableMapping[str, float],
    archived: set[str],
    active: set[str],
    version_changed: bool,
) -> Tuple[int, set[str]]:
    if not spec.recoverable or not spec.restore_enabled or not archived:
        return 0, set()
    ranked = sorted(
        archived,
        key=lambda item_id: (task.semantic_scores[item_id], item_id),
        reverse=True,
    )
    quota = max(1, int(math.sqrt(len(archived)))) if version_changed else 1
    restored = 0
    pending_revalidation: set[str] = set()
    for item_id in ranked:
        if restored + len(pending_revalidation) >= quota:
            break
        semantic = task.semantic_scores[item_id]
        if not version_changed and semantic < 0.82:
            continue
        if spec.causal:
            belief = item_belief[item_id]
            evidence_value = qualified_action_value(
                belief,
                task.risk,
                len(item_belief),
            )
            if belief.count <= 0:
                pending_revalidation.add(item_id)
                continue
        else:
            evidence_value = association[item_id] * semantic
        if evidence_value > 0.0:
            archived.remove(item_id)
            active.add(item_id)
            access[item_id] = max(access[item_id], RESTORE_FLOOR)
            restored += 1
    return restored, pending_revalidation


def choose_group_order(
    groups: Mapping[int, Sequence[object]],
    group_belief: Mapping[int, Belief],
    task,
    scenario,
) -> List[int]:
    def group_voi(group: int) -> Tuple[float, int]:
        members = groups[group]
        if not members:
            return (-math.inf, group)
        cost = scenario.intervention_cost_scale * (0.42 + 0.025 * len(members))
        evsi = one_step_evsi(
            group_belief[group],
            scenario.observation_sd * 0.72,
            task.risk,
        )
        return (evsi - PROBE_COST_WEIGHT * cost, -group)

    return sorted(groups, key=group_voi, reverse=True)


def choose_promising_groups(
    groups: Mapping[int, Sequence[object]],
    group_belief: Mapping[int, Belief],
    task,
) -> set[int]:
    count = max(1, int(math.sqrt(len(groups))))
    return {
        group
        for group in sorted(
            groups,
            key=lambda value: (
                bayes_action_value(group_belief[value], task.risk),
                value,
            ),
            reverse=True,
        )[:count]
    }


def causal_proposal_ids(
    active: set[str],
    task,
    association: Mapping[str, float],
) -> set[str]:
    """Use cheap signals only to propose, never to causally qualify, items."""

    if not active:
        return set()
    count = max(1, math.ceil(math.sqrt(len(active))))
    semantic = sorted(
        active,
        key=lambda item_id: (task.semantic_scores[item_id], item_id),
        reverse=True,
    )[:count]
    associational = sorted(
        active,
        key=lambda item_id: (
            association[item_id] * task.semantic_scores[item_id],
            item_id,
        ),
        reverse=True,
    )[:count]
    return set(semantic) | set(associational)


def initialize_scoped_beliefs(
    world,
    groups: Mapping[int, Sequence[object]],
) -> Tuple[
    Dict[Tuple[str, int], Belief],
    Dict[Tuple[int, int], Belief],
]:
    """Create causal states scoped by the observable environment version.

    Evidence collected under one version must not overwrite another. Task
    scope is enforced upstream by the frozen candidate-construction policy;
    uncalibrated semantic scores are not treated as linear effect modifiers.
    """

    versions = sorted({task.version for task in world.tasks})
    item_beliefs = {
        (item.item_id, version): Belief()
        for item in world.items
        for version in versions
    }
    group_beliefs = {
        (group, version): Belief(sd=1.30)
        for group in groups
        for version in versions
    }
    return item_beliefs, group_beliefs


def run_policy(world, spec: PolicySpec) -> Dict[str, object]:
    items = {item.item_id: item for item in world.items}
    groups = group_map(world, spec)
    item_group = {
        item.item_id: item.true_group if spec.oracle_groups else item.observed_group
        for item in world.items
    }
    scoped_item_belief, scoped_group_belief = initialize_scoped_beliefs(world, groups)
    association = {
        item.item_id: historical_association_prior(world, item)
        for item in world.items
    }
    access = {item.item_id: 1.0 for item in world.items}
    active = set(items)
    archived: set[str] = set()
    deleted: set[str] = set()

    utility = 0.0
    regret = 0.0
    harmful = 0
    risk_weighted_harm = 0.0
    positive = 0
    false_forgetting = 0
    false_forgetting_regret = 0.0
    probes = 0
    group_probes = 0
    item_probes = 0
    causal_selections = 0
    association_selections = 0
    probe_cost = 0.0
    restores = 0
    archive_events = 0
    active_fraction = 0.0
    access_mean = 0.0
    recurrence_start = 2 * world.scenario.horizon // 3 if world.recurrence else None
    recovery_latency: Optional[int] = None
    decision_log_hashes: List[str] = []
    last_version = world.tasks[0].version

    for task in world.tasks:
        version_changed = task.version != last_version
        item_belief = {
            item.item_id: scoped_item_belief[(item.item_id, task.version)]
            for item in world.items
        }
        group_belief = {
            group: scoped_group_belief[(group, task.version)]
            for group in groups
        }
        if spec.decay_rule == "fixed":
            apply_fixed_decay(access)
        elif spec.decay_rule == "risk":
            apply_risk_decay(world, task, item_belief, access)

        for item_id in list(active):
            if access[item_id] < ARCHIVE_THRESHOLD:
                active.remove(item_id)
                archived.add(item_id)
                archive_events += 1
                if not spec.recoverable:
                    deleted.add(item_id)

        direct_restores, pending_revalidation = prepare_restoration(
            world,
            task,
            spec,
            item_belief,
            association,
            access,
            archived,
            active,
            version_changed,
        )
        restores += direct_restores
        last_version = task.version

        spent = 0.0
        task_probes = 0
        budget = policy_budget(task, spec)

        if spec.causal and spec.hierarchical and active:
            active_groups = {
                group: [item for item in members if item.item_id in active]
                for group, members in groups.items()
            }
            active_groups = {group: members for group, members in active_groups.items() if members}
            for group in choose_group_order(
                active_groups,
                group_belief,
                task,
                world.scenario,
            ):
                members = active_groups[group]
                cost = world.scenario.intervention_cost_scale * (0.42 + 0.025 * len(members))
                evsi = one_step_evsi(
                    group_belief[group],
                    world.scenario.observation_sd * 0.72,
                    task.risk,
                )
                if evsi <= PROBE_COST_WEIGHT * cost:
                    continue
                if spent + cost > budget:
                    continue
                observation = mean(common_probe(world, item, task, "group", group) for item in members)
                normal_update(
                    group_belief[group],
                    observation,
                    world.scenario.observation_sd * 0.72,
                )
                spent += cost
                probe_cost += cost
                task_probes += 1
                group_probes += 1
            promising = choose_promising_groups(active_groups, group_belief, task)
        else:
            promising = set(groups)

        if spec.causal and active:
            proposal_ids = causal_proposal_ids(active, task, association)
            pool_ids = {
                item_id
                for item_id in proposal_ids
                if not spec.hierarchical or item_group[item_id] in promising
            }
            if spec.hierarchical and spec.sentinel_correction:
                sentinel_count = max(1, math.ceil(math.sqrt(len(active))))
                sentinels = sorted(
                    (items[item_id] for item_id in active),
                    key=lambda item: (
                        task.semantic_scores[item.item_id],
                        item.item_id,
                    ),
                    reverse=True,
                )[:sentinel_count]
                pool_ids.update(item.item_id for item in sentinels)
            pool_ids.update(pending_revalidation)
            pool = [items[item_id] for item_id in pool_ids]
            probed_item_ids: set[str] = set()
            remaining = {item.item_id: item for item in pool}
            while remaining:
                current_values = {
                    item.item_id: governed_access_value(
                        item_belief[item.item_id],
                        len(pool),
                        association[item.item_id]
                        * task.semantic_scores[item.item_id]
                        - item.execution_cost,
                        conditional_association_value(
                            association[item.item_id],
                            task.semantic_scores[item.item_id],
                            task.risk,
                            item.execution_cost,
                        ),
                    )
                    for item in pool
                }
                ranked_actions = []
                for item_id, item in remaining.items():
                    alternative = max(
                        [0.0]
                        + [
                            value
                            for other_id, value in current_values.items()
                            if other_id != item_id
                        ]
                    )
                    cost = world.scenario.intervention_cost_scale * 0.78
                    evsi = qualification_evsi(
                        item_belief[item_id],
                        world.scenario.observation_sd,
                        len(pool),
                        association[item_id]
                        * task.semantic_scores[item_id]
                        - item.execution_cost,
                        conditional_association_value(
                            association[item_id],
                            task.semantic_scores[item_id],
                            task.risk,
                            item.execution_cost,
                        ),
                        alternative,
                    )
                    ranked_actions.append((evsi - PROBE_COST_WEIGHT * cost, item_id))
                net_value, item_id = max(ranked_actions)
                if net_value <= 0.0:
                    break
                item = remaining.pop(item_id)
                cost = world.scenario.intervention_cost_scale * 0.78
                if spent + cost > budget:
                    break
                observation = common_probe(world, item, task, "item")
                normal_update(
                    item_belief[item.item_id],
                    observation,
                    world.scenario.observation_sd,
                )
                probed_item_ids.add(item.item_id)
                spent += cost
                probe_cost += cost
                task_probes += 1
                item_probes += 1
            for item_id in pending_revalidation & probed_item_ids:
                if qualified_action_value(
                    item_belief[item_id],
                    task.risk,
                    len(item_belief),
                ) > 0.0:
                    archived.remove(item_id)
                    active.add(item_id)
                    access[item_id] = max(access[item_id], RESTORE_FLOOR)
                    restores += 1

        candidates = [items[item_id] for item_id in active]
        selected = None
        selected_source = None
        selected_score = -math.inf
        if not spec.no_memory:
            for item in candidates:
                semantic = task.semantic_scores[item.item_id]
                if spec.causal:
                    belief = item_belief[item.item_id]
                    qualification = causal_qualification_state(
                        belief, len(candidates)
                    )
                    if qualification == "positive-qualified":
                        value = association[item.item_id] * semantic - item.execution_cost
                        source = "causal"
                    elif qualification == "negative-qualified":
                        value = -math.inf
                        source = "causal-negative-veto"
                    else:
                        value = conditional_association_value(
                            association[item.item_id],
                            semantic,
                            task.risk,
                            item.execution_cost,
                        )
                        source = "conditional-association"
                else:
                    if spec.conditional_association:
                        value = conditional_association_value(
                            association[item.item_id],
                            semantic,
                            task.risk,
                            item.execution_cost,
                        )
                        source = "conditional-association"
                    else:
                        value = association[item.item_id] * semantic - item.execution_cost
                        source = "association"
                if (value, item.item_id) > (selected_score, selected.item_id if selected else ""):
                    selected = item
                    selected_score = value
                    selected_source = source
            if spec.causal and selected_score < 0.0:
                selected = None
                selected_source = None

        oracle = max([None] + list(world.items), key=lambda item: base.path_value(item, task))
        selected_effect = base.task_effect(selected, task) if selected is not None else 0.0
        selected_value = base.path_value(selected, task)
        oracle_value = base.path_value(oracle, task)
        governance_regret = (
            max(0.0, oracle_value - selected_value)
            if oracle is not None and oracle.item_id not in active
            else 0.0
        )
        task_false_forgetting = governance_regret > 0.0
        ff_penalty = world.scenario.false_forgetting_weight * governance_regret
        task_harm_loss = task.risk * max(0.0, -selected_effect)
        task_utility = (
            selected_value
            - task_harm_loss
            - PROBE_COST_WEIGHT * spent
            - ff_penalty
        )
        utility += task_utility
        regret += max(0.0, oracle_value - selected_value)
        harmful += int(selected is not None and selected_effect < -0.10)
        risk_weighted_harm += task_harm_loss
        positive += int(selected is not None and selected_effect > 0.45)
        causal_selections += int(selected_source == "causal")
        association_selections += int(
            selected_source in {"association", "conditional-association"}
        )
        false_forgetting += int(task_false_forgetting)
        false_forgetting_regret += governance_regret

        if (
            recurrence_start is not None
            and task.episode >= recurrence_start
            and recovery_latency is None
            and selected is not None
            and selected.true_group == world.drift_group
            and selected_effect > 0.45
        ):
            recovery_latency = task.episode - recurrence_start

        if selected is not None:
            outcome = common_online_outcome(world, selected, task)
            association[selected.item_id] = (
                0.86 * association[selected.item_id] + 0.14 * outcome
            )
            if spec.decay_rule == "fixed":
                if outcome >= 0.0:
                    reinforcement = 0.20 * (1.0 - math.exp(-outcome))
                    access[selected.item_id] += (1.0 - access[selected.item_id]) * reinforcement
                else:
                    access[selected.item_id] *= math.exp(outcome)
                access[selected.item_id] = clipped(access[selected.item_id])

        probes += task_probes
        active_fraction += len(active) / max(1, len(items))
        access_mean += mean(access.values())
        decision_log_hashes.append(
            stable_hash(
                {
                    "task": task.task_id,
                    "policy": spec.name,
                    "budget": budget,
                    "spent": spent,
                    "candidate_count": len(candidates),
                    "selected": selected.item_id if selected is not None else None,
                    "selected_source": selected_source,
                    "utility": task_utility,
                    "active": len(active),
                    "archived": len(archived),
                }
            )
        )

    horizon = world.scenario.horizon
    return {
        "policy": spec.name,
        "seed": float(world.seed),
        "scenario": world.scenario.name,
        "candidate_stream_sha256": world.stream_hash,
        "policy_contract_sha256": stable_hash(asdict(spec)),
        "decision_log_sha256": stable_hash(decision_log_hashes),
        "recurrence": float(world.recurrence),
        "confounding": world.scenario.confounding,
        "coherence": world.scenario.coherence,
        "decomposition_accuracy": world.scenario.decomposition_accuracy,
        "observation_sd": world.scenario.observation_sd,
        "intervention_cost_scale": world.scenario.intervention_cost_scale,
        "false_forgetting_weight": world.scenario.false_forgetting_weight,
        "group_count": float(world.scenario.group_count),
        "items_per_group": float(world.scenario.items_per_group),
        "utility": utility / horizon,
        "regret": regret / horizon,
        "harmful_selection": harmful / horizon,
        "risk_weighted_harm": risk_weighted_harm / horizon,
        "positive_selection": positive / horizon,
        "causal_selection_rate": causal_selections / horizon,
        "association_selection_rate": association_selections / horizon,
        "false_forgetting_rate": false_forgetting / horizon,
        "false_forgetting_regret": false_forgetting_regret / horizon,
        "probe_cost": probe_cost / horizon,
        "mean_probes": probes / horizon,
        "mean_group_probes": group_probes / horizon,
        "mean_item_probes": item_probes / horizon,
        "archive_events": float(archive_events),
        "restore_events": float(restores),
        "archive_rate": archive_events / horizon,
        "restore_rate": restores / horizon,
        "recovery_latency": float(
            recovery_latency if recovery_latency is not None else horizon
        ),
        "evidence_survival": float(len(deleted) == 0),
        "active_fraction": active_fraction / horizon,
        "mean_access_weight": access_mean / horizon,
        "decision_log_completeness": 1.0,
    }


METRICS = (
    "utility",
    "regret",
    "harmful_selection",
    "risk_weighted_harm",
    "positive_selection",
    "causal_selection_rate",
    "association_selection_rate",
    "false_forgetting_rate",
    "false_forgetting_regret",
    "probe_cost",
    "mean_probes",
    "mean_group_probes",
    "mean_item_probes",
    "archive_events",
    "restore_events",
    "archive_rate",
    "restore_rate",
    "recovery_latency",
    "evidence_survival",
    "active_fraction",
    "mean_access_weight",
    "decision_log_completeness",
)


def aggregate_seed(seed: int, scenario) -> List[Dict[str, object]]:
    world = base.build_world(seed, scenario)
    rows = [run_policy(world, spec) for spec in POLICY_SPECS]
    if len({row["candidate_stream_sha256"] for row in rows}) != 1:
        raise RuntimeError("all policies must share the same world stream")
    return rows


def metric_summary(values: Sequence[float]) -> Dict[str, object]:
    if not values:
        return {
            "mean": None,
            "sd": None,
            "ci95": None,
            "n": 0.0,
        }
    sd = stdev(values) if len(values) > 1 else 0.0
    return {
        "mean": mean(values),
        "sd": sd,
        "ci95": 1.96 * sd / math.sqrt(len(values)) if len(values) > 1 else 0.0,
        "n": float(len(values)),
    }


def summarize(rows: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    output: Dict[str, object] = {}
    for scenario in sorted({str(row["scenario"]) for row in rows}):
        output[scenario] = {}
        for policy in POLICIES:
            selected = [
                row
                for row in rows
                if row["scenario"] == scenario and row["policy"] == policy
            ]
            output[scenario][policy] = {
                metric: metric_summary([float(row[metric]) for row in selected])
                for metric in METRICS
            }
    return output


def paired_minimality(rows: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    output: Dict[str, object] = {}
    for scenario in sorted({str(row["scenario"]) for row in rows}):
        scenario_rows = [row for row in rows if row["scenario"] == scenario]
        seeds = sorted({int(float(row["seed"])) for row in scenario_rows})
        lookup = {
            (int(float(row["seed"])), str(row["policy"])): row
            for row in scenario_rows
        }
        output[scenario] = {}
        for baseline in POLICIES:
            if baseline in {"minimal_framework", "oracle_structure_reference"}:
                continue
            utility_delta = [
                float(lookup[(seed, "minimal_framework")]["utility"])
                - float(lookup[(seed, baseline)]["utility"])
                for seed in seeds
            ]
            regret_reduction = [
                float(lookup[(seed, baseline)]["regret"])
                - float(lookup[(seed, "minimal_framework")]["regret"])
                for seed in seeds
            ]
            harmful_reduction = [
                float(lookup[(seed, baseline)]["harmful_selection"])
                - float(lookup[(seed, "minimal_framework")]["harmful_selection"])
                for seed in seeds
            ]
            output[scenario][baseline] = {
                "utility_delta": metric_summary(utility_delta),
                "regret_reduction": metric_summary(regret_reduction),
                "harmful_selection_reduction": metric_summary(harmful_reduction),
                "joint_utility_regret_win_rate": mean(
                    float(u > 0.0 and r > 0.0)
                    for u, r in zip(utility_delta, regret_reduction)
                ),
            }
    return output


def random_subgroups(rows: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    output: Dict[str, object] = {}
    for label, predicate in (
        ("recurrence", lambda row: float(row["recurrence"]) == 1.0),
        ("non_recurrence", lambda row: float(row["recurrence"]) == 0.0),
    ):
        selected_rows = [row for row in rows if predicate(row)]
        output[label] = {
            policy: {
                metric: metric_summary(
                    [
                        float(row[metric])
                        for row in selected_rows
                        if row["policy"] == policy
                    ]
                )
                for metric in METRICS
            }
            for policy in POLICIES
        }
    return output


def module_contrasts() -> Dict[str, Tuple[str, str]]:
    return {
        "causal_evidence": (
            "conditional_association_fixed_no_restore",
            "item_causal_fixed_no_restore",
        ),
        "hierarchical_structure": (
            "minimal_framework",
            "hierarchical_candidate",
        ),
        "adaptive_budget": (
            "minimal_framework",
            "task_adaptive_cap_candidate",
        ),
        "group_to_item_sentinel_correction": (
            "hierarchical_candidate",
            "hierarchical_sentinel_candidate",
        ),
        "risk_conditioned_decay": (
            "item_causal_fixed_recoverable",
            "minimal_framework",
        ),
        "recoverability": (
            "item_causal_risk_no_restore",
            "minimal_framework",
        ),
        "oracle_structure_reference": (
            "hierarchical_sentinel_candidate",
            "oracle_structure_reference",
        ),
    }


def contrast_summary(
    named_rows: Sequence[Mapping[str, object]],
    random_rows: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    all_rows = list(named_rows) + list(random_rows)
    output: Dict[str, object] = {}
    named_scenarios = sorted(
        {
            str(row["scenario"])
            for row in named_rows
            if row["scenario"] != "randomized_lifecycle_worlds"
        }
    )
    slices = [
        ("all", lambda row: True),
        ("recurrence", lambda row: float(row["recurrence"]) == 1.0),
        ("non_recurrence", lambda row: float(row["recurrence"]) == 0.0),
        (
            "random_weak_gap",
            lambda row: row["scenario"] == "randomized_lifecycle_worlds"
            and float(row["confounding"]) <= 0.20,
        ),
        (
            "random_noisy_decomposition",
            lambda row: row["scenario"] == "randomized_lifecycle_worlds"
            and float(row["decomposition_accuracy"]) <= 0.65,
        ),
        (
            "random_high_intervention_cost",
            lambda row: row["scenario"] == "randomized_lifecycle_worlds"
            and float(row["intervention_cost_scale"]) >= 1.80,
        ),
    ]
    slices.extend(
        (
            f"named:{scenario}",
            lambda row, scenario=scenario: row["scenario"] == scenario,
        )
        for scenario in named_scenarios
    )
    for module, (without, with_module) in module_contrasts().items():
        output[module] = {}
        for slice_name, predicate in slices:
            selected = [row for row in all_rows if predicate(row)]
            keys = sorted(
                {
                    (str(row["scenario"]), int(float(row["seed"])))
                    for row in selected
                }
            )
            lookup = {
                (
                    str(row["scenario"]),
                    int(float(row["seed"])),
                    str(row["policy"]),
                ): row
                for row in selected
            }
            utility_delta = []
            regret_reduction = []
            harmful_reduction = []
            risk_weighted_harm_reduction = []
            false_forgetting_regret_reduction = []
            active_fraction_reduction = []
            probe_cost_change = []
            zero_probe_price_utility_delta = []
            restore_rate_change = []
            for scenario, seed in keys:
                before = lookup[(scenario, seed, without)]
                after = lookup[(scenario, seed, with_module)]
                utility_delta.append(float(after["utility"]) - float(before["utility"]))
                regret_reduction.append(float(before["regret"]) - float(after["regret"]))
                harmful_reduction.append(
                    float(before["harmful_selection"])
                    - float(after["harmful_selection"])
                )
                risk_weighted_harm_reduction.append(
                    float(before["risk_weighted_harm"])
                    - float(after["risk_weighted_harm"])
                )
                false_forgetting_regret_reduction.append(
                    float(before["false_forgetting_regret"])
                    - float(after["false_forgetting_regret"])
                )
                active_fraction_reduction.append(
                    float(before["active_fraction"])
                    - float(after["active_fraction"])
                )
                probe_cost_change.append(
                    float(after["probe_cost"])
                    - float(before["probe_cost"])
                )
                zero_probe_price_utility_delta.append(
                    float(after["utility"])
                    + PROBE_COST_WEIGHT * float(after["probe_cost"])
                    - float(before["utility"])
                    - PROBE_COST_WEIGHT * float(before["probe_cost"])
                )
                restore_rate_change.append(
                    float(after["restore_rate"])
                    - float(before["restore_rate"])
                )
            mean_probe_cost_change = mean(probe_cost_change) if probe_cost_change else 0.0
            mean_zero_price_delta = (
                mean(zero_probe_price_utility_delta)
                if zero_probe_price_utility_delta
                else 0.0
            )
            mean_restore_rate_change = (
                mean(restore_rate_change) if restore_rate_change else 0.0
            )
            output[module][slice_name] = {
                "without": without,
                "with": with_module,
                "utility_delta": metric_summary(utility_delta),
                "regret_reduction": metric_summary(regret_reduction),
                "harmful_selection_reduction": metric_summary(harmful_reduction),
                "risk_weighted_harm_reduction": metric_summary(
                    risk_weighted_harm_reduction
                ),
                "false_forgetting_regret_reduction": metric_summary(
                    false_forgetting_regret_reduction
                ),
                "active_fraction_reduction": metric_summary(active_fraction_reduction),
                "probe_cost_change": metric_summary(probe_cost_change),
                "zero_probe_price_utility_delta": metric_summary(
                    zero_probe_price_utility_delta
                ),
                "probe_price_break_even": (
                    mean_zero_price_delta / mean_probe_cost_change
                    if mean_probe_cost_change > 0.0
                    else None
                ),
                "restore_rate_change": metric_summary(restore_rate_change),
                "restore_price_break_even": (
                    mean(utility_delta) / mean_restore_rate_change
                    if utility_delta and mean_restore_rate_change > 0.0
                    else None
                ),
                "joint_utility_regret_win_rate": (
                    mean(
                        float(u > 0.0 and r > 0.0)
                        for u, r in zip(utility_delta, regret_reduction)
                    )
                    if utility_delta
                    else None
                ),
            }
    return output


def run_experiment(
    named_seeds: int,
    random_world_seeds: int,
    horizon: Optional[int] = None,
) -> Dict[str, object]:
    named_rows: List[Dict[str, object]] = []
    for scenario in base.SCENARIOS:
        selected_scenario = replace(scenario, horizon=horizon) if horizon else scenario
        for seed in range(named_seeds):
            named_rows.extend(aggregate_seed(seed, selected_scenario))

    random_rows: List[Dict[str, object]] = []
    for seed in range(random_world_seeds):
        scenario = base.random_scenario(seed)
        if horizon:
            scenario = replace(scenario, horizon=horizon)
        random_rows.extend(aggregate_seed(seed, scenario))

    protocol = {
        "status": "revised-after-v2-formal-audit-and-refrozen",
        "benchmark_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(),
        "named_seeds": named_seeds,
        "random_world_seeds": random_world_seeds,
        "horizon_override": horizon,
        "policies": [asdict(spec) for spec in POLICY_SPECS],
        "fixed_expected_budget": FIXED_EXPECTED_BUDGET,
        "fixed_budget_derivation": "E[2.15 + 1.10*risk + 0.85*ambiguity] under task-generator uniforms",
        "fixed_decay_rate": FIXED_DECAY_RATE,
        "archive_threshold": ARCHIVE_THRESHOLD,
        "restore_floor": RESTORE_FLOOR,
        "probe_cost_weight": PROBE_COST_WEIGHT,
        "ordinary_outcomes_update_causal_belief": False,
        "association_prior_source": "exposed-only mean from a fixed endogenous historical micro-log",
        "causal_proposal_rule": "union of top ceil(sqrt(N)) semantic and associational candidates; proposal only",
        "associational_fallback": "current-task only, discounted by (1-task risk), never updates causal belief",
        "causal_qualification_gate": "two-sided Bonferroni family control with summable 6/(pi^2 n^2) sequential alpha spending",
        "per_scenario_tuning": False,
        "manual_path_labels": False,
        "privileged_groups": "oracle_structure_reference only",
        "shared_probe_potential_outcomes": True,
        "causal_belief_scope": "task.version plus the frozen task-conditioned proposal contract",
        "probe_stop_rule": "best-alternative-aware qualification EVSI <= priced intervention cost",
        "restore_rule": "reuse positive same-version causal evidence; otherwise pay for item revalidation",
        "risk_decay_gate": "unresolved causal beliefs cannot change access; only positive/negative-qualified states govern decay or recovery",
        "candidate_only_modules": [
            "task_adaptive_cap_candidate",
            "hierarchical_candidate",
            "hierarchical_sentinel_candidate",
        ],
    }
    return {
        "schema_version": "minimal-framework-challenge.v3",
        "protocol": protocol,
        "protocol_sha256": stable_hash(protocol),
        "named_summary": summarize(named_rows),
        "named_pairwise_minimal": paired_minimality(named_rows),
        "random_subgroups": random_subgroups(random_rows),
        "module_contrasts": contrast_summary(named_rows, random_rows),
        "named_rows": named_rows,
        "random_rows": random_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--named-seeds", type=int, default=50)
    parser.add_argument("--random-world-seeds", type=int, default=120)
    parser.add_argument("--horizon", type=int, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_DIR / "minimal_framework_challenge_v3.json",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = run_experiment(
        named_seeds=args.named_seeds,
        random_world_seeds=args.random_world_seeds,
        horizon=args.horizon,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not args.quiet:
        print(args.output)
        print(json.dumps(result["module_contrasts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

