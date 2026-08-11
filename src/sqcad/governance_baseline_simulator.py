"""Multi-baseline governance simulator for causal memory retention.

The synthetic world contains rare critical, common useful, stale, and noise
memories.  Exposure is confounded by task difficulty and popularity.  The
proposed proxy decomposes items into known mechanism groups, pools evidence
within each group, estimates environment-specific effects, and scores the
worst-environment lower confidence bound.

This is a mechanism stress test, not a public benchmark or SOTA result.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev, variance
from typing import Dict, Iterable, List, Sequence, Tuple


GROUP_SIZES = {"rare_critical": 12, "common_useful": 24, "stale": 24, "noise": 60}
TRAIN_WEIGHTS = {"rare_critical": 0.03, "common_useful": 0.35, "stale": 0.45, "noise": 0.17}
TEST_WEIGHTS = {"rare_critical": 0.20, "common_useful": 0.35, "stale": 0.25, "noise": 0.20}
EFFECTS = {
    0: {"rare_critical": 2.5, "common_useful": 1.0, "stale": 1.5, "noise": 0.0},
    1: {"rare_critical": 2.5, "common_useful": 1.0, "stale": -0.8, "noise": 0.0},
    2: {"rare_critical": 2.5, "common_useful": 1.0, "stale": -1.0, "noise": 0.0},
}
BASE_PROPENSITY = {"rare_critical": 0.12, "common_useful": 0.55, "stale": 0.82, "noise": 0.30}
GROUP_BASELINE = {"rare_critical": -2.5, "common_useful": 0.0, "stale": 0.8, "noise": 1.0}


def make_items() -> Tuple[List[str], Dict[str, str]]:
    items: List[str] = []
    groups: Dict[str, str] = {}
    for group, size in GROUP_SIZES.items():
        for index in range(size):
            item = f"{group}_{index:02d}"
            items.append(item)
            groups[item] = group
    return items, groups


def item_weights(items: Sequence[str], groups: Dict[str, str], group_weights: Dict[str, float]) -> List[float]:
    return [group_weights[groups[item]] / GROUP_SIZES[groups[item]] for item in items]


def generate_logs(seed: int, samples_per_environment: int) -> Tuple[List[Dict[str, float]], Dict[str, str]]:
    rng = random.Random(seed)
    items, groups = make_items()
    weights = item_weights(items, groups, TRAIN_WEIGHTS)
    logs: List[Dict[str, float]] = []
    time = 0
    for environment in (0, 1):
        for _ in range(samples_per_environment):
            item = rng.choices(items, weights=weights, k=1)[0]
            group = groups[item]
            difficulty = int(rng.random() < (0.65 if group == "rare_critical" else 0.40))
            propensity = min(0.95, BASE_PROPENSITY[group] + 0.20 * difficulty)
            exposed = int(rng.random() < propensity)
            # Group-specific task solvability creates success/failure confounding:
            # rare critical memory can reduce loss without making the task pass,
            # while irrelevant/easy memories often co-occur with success.
            baseline = GROUP_BASELINE[group] - 0.5 * difficulty + rng.gauss(0.0, 0.75)
            outcome = baseline + EFFECTS[environment][group] * exposed
            logs.append(
                {
                    "time": float(time),
                    "environment": float(environment),
                    "item": item,
                    "difficulty": float(difficulty),
                    "propensity": propensity,
                    "exposed": float(exposed),
                    "outcome": outcome,
                    "success": float(outcome > 0.0),
                }
            )
            time += 1
    return logs, groups


def stratified_effect(rows: Sequence[Dict[str, float]]) -> Tuple[float, float]:
    """Adjusted difference by observed difficulty, plus plug-in standard error."""
    if not rows:
        return 0.0, float("inf")
    estimate = 0.0
    variance_sum = 0.0
    for difficulty in (0.0, 1.0):
        stratum = [row for row in rows if row["difficulty"] == difficulty]
        if not stratum:
            continue
        weight = len(stratum) / len(rows)
        exposed = [row["outcome"] for row in stratum if row["exposed"] == 1.0]
        hidden = [row["outcome"] for row in stratum if row["exposed"] == 0.0]
        if len(exposed) < 2 or len(hidden) < 2:
            return 0.0, float("inf")
        estimate += weight * (mean(exposed) - mean(hidden))
        variance_sum += weight * weight * (
            variance(exposed) / len(exposed) + variance(hidden) / len(hidden)
        )
    return estimate, math.sqrt(max(variance_sum, 0.0))


def scores(
    logs: Sequence[Dict[str, float]],
    groups: Dict[str, str],
    abstract_groups: Dict[str, str],
    abstract_confidence: Dict[str, float],
    confidence_threshold: float,
    item_negative_veto: float,
) -> Dict[str, Dict[str, float]]:
    items = list(groups)
    by_item: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    by_group: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    for row in logs:
        by_item[row["item"]].append(row)
        by_group[abstract_groups[row["item"]]].append(row)
    max_time = max(row["time"] for row in logs)
    result: Dict[str, Dict[str, float]] = {
        method: {} for method in (
            "recency", "frequency", "fade_like", "memory_worth_like",
            "causal_item_stable", "decomp_abstract_causal",
            "decomp_abstract_confidence_only", "decomp_abstract_sign_gate",
            "decomp_abstract_veto_only", "decomp_abstract_risk_gated",
        )
    }

    for item in items:
        rows = by_item[item]
        exposed_rows = [row for row in rows if row["exposed"] == 1.0]
        last = max((row["time"] for row in exposed_rows), default=-1.0)
        frequency = len(exposed_rows)
        age = max_time - last if last >= 0 else max_time + 1
        result["recency"][item] = last
        result["frequency"][item] = float(frequency)
        result["fade_like"][item] = math.exp(-age / 2500.0) * math.log1p(frequency)
        successes = sum(row["success"] for row in exposed_rows)
        result["memory_worth_like"][item] = (successes + 1.0) / (frequency + 2.0)
        environment_lcbs = []
        for environment in (0.0, 1.0):
            estimate, se = stratified_effect(
                [row for row in rows if row["environment"] == environment]
            )
            environment_lcbs.append(estimate - se if math.isfinite(se) else -1e6)
        result["causal_item_stable"][item] = min(environment_lcbs)

    group_scores: Dict[str, float] = {}
    for group, rows in by_group.items():
        environment_lcbs = []
        for environment in (0.0, 1.0):
            estimate, se = stratified_effect(
                [row for row in rows if row["environment"] == environment]
            )
            environment_lcbs.append(estimate - se if math.isfinite(se) else -1e6)
        group_scores[group] = min(environment_lcbs)
    for item in items:
        result["decomp_abstract_causal"][item] = group_scores[abstract_groups[item]]
        # Confidence is produced by the representation stage, not inferred
        # from the hidden true group.  Low-confidence assignments fall back to
        # the strongest item-level causal control rather than propagating a
        # potentially wrong abstract rule.
        group_score = group_scores[abstract_groups[item]]
        item_score = result["causal_item_stable"][item]
        item_estimable = item_score > -1e5
        cross_level_sign_conflict = (
            item_estimable
            and ((group_score > 0.0 > item_score) or (item_score > 0.0 > group_score))
        )
        item_level_harm_veto = item_estimable and item_score <= item_negative_veto
        result["decomp_abstract_confidence_only"][item] = (
            group_score if abstract_confidence[item] >= confidence_threshold else item_score
        )
        result["decomp_abstract_sign_gate"][item] = (
            item_score if cross_level_sign_conflict else group_score
        )
        result["decomp_abstract_veto_only"][item] = (
            item_score if item_level_harm_veto else group_score
        )
        result["decomp_abstract_risk_gated"][item] = (
            item_score
            if (
                abstract_confidence[item] < confidence_threshold
                or cross_level_sign_conflict
                or item_level_harm_veto
            )
            else group_score
        )
    return result


def retain(score: Dict[str, float], budget: int) -> set[str]:
    return set(sorted(score, key=lambda item: (score[item], item), reverse=True)[:budget])


def evaluate_retention(retained: set[str], groups: Dict[str, str], budget: int) -> Dict[str, float]:
    items = list(groups)
    weights = item_weights(items, groups, TEST_WEIGHTS)
    weight_by_item = dict(zip(items, weights))
    expected_utility = sum(
        weight_by_item[item] * EFFECTS[2][groups[item]] for item in retained
    )
    positives = {item for item in items if EFFECTS[2][groups[item]] > 0.0}
    rare = {item for item in items if groups[item] == "rare_critical"}
    stale = {item for item in items if groups[item] == "stale"}
    oracle = set(
        sorted(
            items,
            key=lambda item: (
                weight_by_item[item] * EFFECTS[2][groups[item]], item
            ),
            reverse=True,
        )[:budget]
    )
    oracle_utility = sum(
        weight_by_item[item] * EFFECTS[2][groups[item]] for item in oracle
    )
    return {
        "test_utility": expected_utility,
        "normalized_utility": expected_utility / oracle_utility,
        "oracle_regret": oracle_utility - expected_utility,
        "positive_memory_recall": len(retained & positives) / len(positives),
        "rare_critical_recall": len(retained & rare) / len(rare),
        "stale_retention_rate": len(retained & stale) / len(stale),
        "retained_positive_precision": len(retained & positives) / len(retained),
        "retained_count": float(len(retained)),
    }


def run_seed(
    seed: int,
    samples_per_environment: int,
    budget: int,
    group_noise: float,
    confidence_threshold: float = 0.75,
    item_negative_veto: float = -0.25,
) -> Dict[str, Dict[str, float]]:
    logs, groups = generate_logs(seed, samples_per_environment)
    abstract_groups = dict(groups)
    abstract_confidence: Dict[str, float] = {}
    assignment_rng = random.Random(1_000_000 + seed)
    confidence_rng = random.Random(2_000_000 + seed)
    labels = list(GROUP_SIZES)
    for item, true_group in groups.items():
        if assignment_rng.random() < group_noise:
            abstract_groups[item] = assignment_rng.choice([label for label in labels if label != true_group])
            # A calibrated-but-imperfect semantic confidence proxy: wrong
            # assignments tend to be less confident, but some survive the
            # gate.  The method observes only this confidence, not correctness.
            abstract_confidence[item] = confidence_rng.uniform(0.30, 0.80)
        else:
            abstract_confidence[item] = confidence_rng.uniform(0.75, 1.00)
    method_scores = scores(
        logs, groups, abstract_groups, abstract_confidence,
        confidence_threshold, item_negative_veto,
    )
    return {
        method: evaluate_retention(retain(score, budget), groups, budget)
        for method, score in method_scores.items()
    }


def summarize(per_seed: List[Dict[str, Dict[str, float]]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    output: Dict[str, Dict[str, Dict[str, float]]] = {}
    for method in per_seed[0]:
        output[method] = {}
        for metric in per_seed[0][method]:
            values = [row[method][metric] for row in per_seed]
            sd = stdev(values) if len(values) > 1 else 0.0
            output[method][metric] = {
                "mean": mean(values),
                "sd": sd,
                "ci95": 1.96 * sd / (len(values) ** 0.5),
                "n": float(len(values)),
            }
    return output


def paired_comparison(
    per_seed: List[Dict[str, Dict[str, float]]],
    proposed: str = "decomp_abstract_risk_gated",
    reference: str = "causal_item_stable",
) -> Dict[str, Dict[str, float]]:
    """Report paired deltas and win rates against the strongest causal control."""
    higher_is_better = {
        "normalized_utility": True,
        "rare_critical_recall": True,
        "stale_retention_rate": False,
        "retained_positive_precision": True,
    }
    output: Dict[str, Dict[str, float]] = {}
    for metric, maximize in higher_is_better.items():
        deltas = [row[proposed][metric] - row[reference][metric] for row in per_seed]
        sd = stdev(deltas) if len(deltas) > 1 else 0.0
        wins = [delta > 0 if maximize else delta < 0 for delta in deltas]
        ties = [delta == 0 for delta in deltas]
        output[metric] = {
            "mean_delta_proposed_minus_reference": mean(deltas),
            "sd_delta": sd,
            "ci95_half_width": 1.96 * sd / len(deltas) ** 0.5,
            "paired_win_rate": sum(wins) / len(wins),
            "paired_tie_rate": sum(ties) / len(ties),
            "higher_is_better": maximize,
            "n": float(len(deltas)),
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--samples-per-environment", type=int, default=12000)
    parser.add_argument("--budget", type=int, default=36)
    parser.add_argument("--group-noise", type=float, default=0.0)
    parser.add_argument("--confidence-threshold", type=float, default=0.75)
    parser.add_argument("--item-negative-veto", type=float, default=-0.25)
    parser.add_argument("--output", type=Path, default=Path("governance_baseline_simulator.json"))
    args = parser.parse_args()
    if not 0.0 <= args.group_noise <= 1.0 or not 0.0 <= args.confidence_threshold <= 1.0:
        raise SystemExit("--group-noise and --confidence-threshold must be in [0, 1]")
    per_seed = [
        run_seed(
            seed, args.samples_per_environment, args.budget,
            args.group_noise, args.confidence_threshold, args.item_negative_veto,
        )
        for seed in range(args.seeds)
    ]
    output = {
        "protocol": {
            "purpose": "multi-baseline governance stress test, not a public benchmark",
            "seeds": args.seeds,
            "samples_per_environment": args.samples_per_environment,
            "training_environments": [0, 1],
            "test_environment": 2,
            "memory_items": sum(GROUP_SIZES.values()),
            "retention_budget": args.budget,
            "group_noise": args.group_noise,
            "confidence_threshold": args.confidence_threshold,
            "item_negative_veto": args.item_negative_veto,
            "confidence_model": {
                "correct_assignment": "Uniform(0.75, 1.00)",
                "incorrect_assignment": "Uniform(0.30, 0.80)",
                "warning": "controlled calibrated-confidence model; not an estimate from a real semantic parser",
            },
            "cross_level_consistency_gate": "fall back to estimable item-level score on sign conflict or sufficiently negative item-level LCB",
            "groups": GROUP_SIZES,
            "warning": "group abstraction and confidence are controlled proxies; outputs are not public benchmark results",
        },
        "summary": summarize(per_seed),
        "paired_to_item_causal": paired_comparison(per_seed),
        "per_seed": per_seed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = {
        method: {
            metric: values[metric]["mean"]
            for metric in ("normalized_utility", "rare_critical_recall", "stale_retention_rate", "retained_positive_precision")
        }
        for method, values in output["summary"].items()
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
