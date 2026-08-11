"""Score semantic-decomposition predictions against Gate A annotations.

This scorer measures representation fidelity, provenance and scope.  It does
not estimate causal effects.  Gold and prediction files share immutable packet
content and differ only in their ``annotation`` fields.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple


TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
FACTOR_THRESHOLD = 0.50
PROVENANCE_THRESHOLD = 0.80
UPDATE_RELATIONS = {"updates", "contradicts", "supersedes", "reaffirms"}
GATE_THRESHOLDS = {
    "factor_micro_f1": (">=", 0.80),
    "relation_f1": (">=", 0.70),
    "provenance_coverage": (">=", 0.95),
    "scope_completeness": (">=", 0.90),
    "negation_error_rate": ("<=", 0.10),
    "temporal_error_rate": ("<=", 0.10),
    "update_error_rate": ("<=", 0.10),
    "rule_overgeneralization_rate": ("<=", 0.10),
}


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def prf(tp: float, pred_n: float, gold_n: float) -> Tuple[float, float, float]:
    precision = safe_div(tp, pred_n)
    recall = safe_div(tp, gold_n)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def normalized_tokens(value: object) -> Set[str]:
    return set(TOKEN_RE.findall(str(value or "").lower()))


def jaccard(left: Set[str], right: Set[str]) -> float:
    return safe_div(len(left & right), len(left | right)) if left or right else 1.0


def packet_turns(packet: Mapping[str, object]) -> Dict[Tuple[str, int], str]:
    return {
        (str(session["session_id"]), turn_index): str(turn["content"])
        for session in packet["evidence_sessions"]
        for turn_index, turn in enumerate(session["turns"])
    }


def span_token_keys(packet: Mapping[str, object], span: Mapping[str, object]) -> Set[Tuple[str, int, int]]:
    turns = packet_turns(packet)
    key = (str(span["session_id"]), int(span["turn_index"]))
    content = turns[key]
    start, end = int(span["char_start"]), int(span["char_end"])
    keys = {
        (key[0], key[1], token_index)
        for token_index, match in enumerate(TOKEN_RE.finditer(content))
        if match.start() < end and match.end() > start
    }
    if not keys:
        keys = {(key[0], key[1], position) for position in range(start, end)}
    return keys


def annotation_span_map(packet: Mapping[str, object]) -> Dict[str, Set[Tuple[str, int, int]]]:
    return {
        str(span["span_id"]): span_token_keys(packet, span)
        for span in packet["annotation"]["evidence_spans"]
    }


def unit_provenance(span_ids: Sequence[str], span_map: Mapping[str, Set[Tuple[str, int, int]]]) -> Set[Tuple[str, int, int]]:
    keys: Set[Tuple[str, int, int]] = set()
    for span_id in span_ids:
        keys.update(span_map.get(str(span_id), set()))
    return keys


def set_f1(predicted: Set[object], gold: Set[object]) -> float:
    if not predicted and not gold:
        return 1.0
    return safe_div(2 * len(predicted & gold), len(predicted) + len(gold))


def greedy_factor_match(gold_packet: Mapping[str, object], pred_packet: Mapping[str, object]) -> Tuple[List[Tuple[str, str, float, float]], Dict[str, str]]:
    gold_spans = annotation_span_map(gold_packet)
    pred_spans = annotation_span_map(pred_packet)
    gold_factors = {str(f["factor_id"]): f for f in gold_packet["annotation"]["factors"]}
    pred_factors = {str(f["factor_id"]): f for f in pred_packet["annotation"]["factors"]}
    candidates = []
    for pred_id, pred in pred_factors.items():
        for gold_id, gold in gold_factors.items():
            if pred["factor_type"] != gold["factor_type"]:
                continue
            lexical = jaccard(normalized_tokens(pred["normalized_form"]), normalized_tokens(gold["normalized_form"]))
            provenance = set_f1(
                unit_provenance(pred["span_ids"], pred_spans),
                unit_provenance(gold["span_ids"], gold_spans),
            )
            score = 0.6 * lexical + 0.4 * provenance
            if lexical >= FACTOR_THRESHOLD and provenance > 0.0:
                candidates.append((score, provenance, pred_id, gold_id))
    candidates.sort(reverse=True)
    used_pred, used_gold = set(), set()
    matches = []
    mapping: Dict[str, str] = {}
    for score, provenance, pred_id, gold_id in candidates:
        if pred_id in used_pred or gold_id in used_gold:
            continue
        used_pred.add(pred_id)
        used_gold.add(gold_id)
        matches.append((pred_id, gold_id, score, provenance))
        mapping[pred_id] = gold_id
    return matches, mapping


def relation_signature(relation: Mapping[str, object], factor_map: Mapping[str, str] | None = None) -> Tuple[object, ...]:
    factor_map = factor_map or {}
    source = tuple(sorted(factor_map.get(str(fid), str(fid)) for fid in relation.get("source_factor_ids", [])))
    target = tuple(sorted(factor_map.get(str(fid), str(fid)) for fid in relation.get("target_factor_ids", [])))
    return relation["relation_type"], source, target


def rule_signature(rule: Mapping[str, object], factor_map: Mapping[str, str] | None = None) -> Tuple[object, ...]:
    factor_map = factor_map or {}
    antecedent = tuple(sorted(factor_map.get(str(fid), str(fid)) for fid in rule["antecedent_factor_ids"]))
    consequent = tuple(sorted(factor_map.get(str(fid), str(fid)) for fid in rule["consequent_factor_ids"]))
    return antecedent, consequent


def required_scope_pairs(scope: Mapping[str, object]) -> List[Tuple[str, object]]:
    return [(key, value) for key, value in scope.items() if value is not None and value != ""]


def score_packet(gold: Mapping[str, object], pred: Mapping[str, object]) -> Dict[str, float]:
    counts: Counter[str] = Counter()
    gold_annotation, pred_annotation = gold["annotation"], pred["annotation"]
    gold_span_map, pred_span_map = annotation_span_map(gold), annotation_span_map(pred)
    gold_span_tokens = set().union(*gold_span_map.values()) if gold_span_map else set()
    pred_span_tokens = set().union(*pred_span_map.values()) if pred_span_map else set()
    counts["span_overlap"] = len(gold_span_tokens & pred_span_tokens)
    counts["gold_span_tokens"] = len(gold_span_tokens)
    counts["pred_span_tokens"] = len(pred_span_tokens)

    matches, factor_map = greedy_factor_match(gold, pred)
    gold_factors = {str(f["factor_id"]): f for f in gold_annotation["factors"]}
    pred_factors = {str(f["factor_id"]): f for f in pred_annotation["factors"]}
    counts["factor_tp"] = len(matches)
    counts["gold_factors"] = len(gold_factors)
    counts["pred_factors"] = len(pred_factors)
    for pred_id, gold_id, _, provenance in matches:
        counts["provenance_total"] += 1
        counts["provenance_correct"] += int(provenance >= PROVENANCE_THRESHOLD)
        gold_factor, pred_factor = gold_factors[gold_id], pred_factors[pred_id]
        for field in ("subject_scope", "task_scope", "temporal_scope"):
            gold_value = gold_factor.get(field)
            if gold_value is not None and gold_value != "":
                counts["scope_total"] += 1
                counts["scope_correct"] += int(pred_factor.get(field) == gold_value)

    gold_relations = {relation_signature(r): r for r in gold_annotation["relations"]}
    pred_relations = {relation_signature(r, factor_map): r for r in pred_annotation["relations"]}
    matched_relation_signatures = set(gold_relations) & set(pred_relations)
    counts["relation_tp"] = len(matched_relation_signatures)
    counts["gold_relations"] = len(gold_relations)
    counts["pred_relations"] = len(pred_relations)
    for signature in matched_relation_signatures:
        gold_relation, pred_relation = gold_relations[signature], pred_relations[signature]
        provenance = set_f1(
            unit_provenance(pred_relation["span_ids"], pred_span_map),
            unit_provenance(gold_relation["span_ids"], gold_span_map),
        )
        counts["provenance_total"] += 1
        counts["provenance_correct"] += int(provenance >= PROVENANCE_THRESHOLD)

    # Error denominators include missed gold units, so abstaining cannot game the gate.
    for gold_id, gold_factor in gold_factors.items():
        if gold_factor.get("polarity") == "negative":
            counts["negation_total"] += 1
            pred_id = next((pred_id for pred_id, mapped in factor_map.items() if mapped == gold_id), None)
            counts["negation_correct"] += int(pred_id is not None and pred_factors[pred_id].get("polarity") == "negative")
        if gold_factor["factor_type"] == "time":
            counts["temporal_total"] += 1
            pred_id = next((pred_id for pred_id, mapped in factor_map.items() if mapped == gold_id), None)
            counts["temporal_correct"] += int(
                pred_id is not None
                and normalized_tokens(pred_factors[pred_id]["normalized_form"]) == normalized_tokens(gold_factor["normalized_form"])
            )
    gold_update = {signature for signature in gold_relations if signature[0] in UPDATE_RELATIONS}
    counts["update_total"] = len(gold_update)
    counts["update_correct"] = len(gold_update & matched_relation_signatures)

    gold_rules = {rule_signature(rule): rule for rule in gold_annotation["abstract_rule_candidates"]}
    pred_rules = {rule_signature(rule, factor_map): rule for rule in pred_annotation["abstract_rule_candidates"]}
    counts["gold_rules"] = len(gold_rules)
    counts["pred_rules"] = len(pred_rules)
    matched_rules = set(gold_rules) & set(pred_rules)
    counts["rule_tp"] = len(matched_rules)
    overgeneralized = len(set(pred_rules) - set(gold_rules))
    for signature in matched_rules:
        gold_rule, pred_rule = gold_rules[signature], pred_rules[signature]
        required = required_scope_pairs(gold_rule.get("scope", {}))
        if any(pred_rule.get("scope", {}).get(key) != value for key, value in required):
            overgeneralized += 1
        for key, value in required:
            counts["scope_total"] += 1
            counts["scope_correct"] += int(pred_rule.get("scope", {}).get(key) == value)
    counts["overgeneralized_rules"] = overgeneralized
    return dict(counts)


def aggregate_counts(rows: Iterable[Mapping[str, float]]) -> Counter[str]:
    output: Counter[str] = Counter()
    for row in rows:
        output.update(row)
    return output


def metrics_from_counts(counts: Mapping[str, float]) -> Dict[str, float | None]:
    span_precision, span_recall, span_f1 = prf(counts.get("span_overlap", 0), counts.get("pred_span_tokens", 0), counts.get("gold_span_tokens", 0))
    factor_precision, factor_recall, factor_f1 = prf(counts.get("factor_tp", 0), counts.get("pred_factors", 0), counts.get("gold_factors", 0))
    relation_precision, relation_recall, relation_f1 = prf(counts.get("relation_tp", 0), counts.get("pred_relations", 0), counts.get("gold_relations", 0))
    rule_precision, rule_recall, rule_f1 = prf(counts.get("rule_tp", 0), counts.get("pred_rules", 0), counts.get("gold_rules", 0))

    def accuracy_or_none(correct: str, total: str) -> float | None:
        denominator = counts.get(total, 0)
        return safe_div(counts.get(correct, 0), denominator) if denominator else None

    def error_or_none(correct: str, total: str) -> float | None:
        accuracy = accuracy_or_none(correct, total)
        return 1.0 - accuracy if accuracy is not None else None

    return {
        "evidence_span_precision": span_precision,
        "evidence_span_recall": span_recall,
        "evidence_span_token_f1": span_f1,
        "factor_precision": factor_precision,
        "factor_recall": factor_recall,
        "factor_micro_f1": factor_f1,
        "relation_precision": relation_precision,
        "relation_recall": relation_recall,
        "relation_f1": relation_f1,
        "provenance_coverage": accuracy_or_none("provenance_correct", "provenance_total"),
        "scope_completeness": accuracy_or_none("scope_correct", "scope_total"),
        "negation_error_rate": error_or_none("negation_correct", "negation_total"),
        "temporal_error_rate": error_or_none("temporal_correct", "temporal_total"),
        "update_error_rate": error_or_none("update_correct", "update_total"),
        "rule_precision": rule_precision,
        "rule_recall": rule_recall,
        "rule_f1": rule_f1,
        "rule_overgeneralization_rate": safe_div(counts.get("overgeneralized_rules", 0), counts.get("pred_rules", 0)) if counts.get("pred_rules", 0) else None,
    }


def bootstrap(rows: Sequence[Mapping[str, float]], samples: int, seed: int) -> Dict[str, Dict[str, float]]:
    rng = random.Random(seed)
    values: Dict[str, List[float]] = defaultdict(list)
    for _ in range(samples):
        sampled = [rows[rng.randrange(len(rows))] for _ in rows]
        metrics = metrics_from_counts(aggregate_counts(sampled))
        for key, value in metrics.items():
            if value is not None and math.isfinite(value):
                values[key].append(float(value))
    intervals = {}
    for key, metric_values in values.items():
        ordered = sorted(metric_values)
        lower = ordered[int(0.025 * (len(ordered) - 1))]
        upper = ordered[int(0.975 * (len(ordered) - 1))]
        intervals[key] = {"lower": lower, "upper": upper, "samples": float(len(ordered))}
    return intervals


def gate_decision(metrics: Mapping[str, float | None], intervals: Mapping[str, Mapping[str, float]] | None = None) -> Dict[str, object]:
    intervals = intervals or {}
    checks = {}
    for metric, (operator, threshold) in GATE_THRESHOLDS.items():
        value = metrics.get(metric)
        interval = intervals.get(metric)
        conservative_value = None
        if value is not None:
            conservative_value = interval["lower"] if interval and operator == ">=" else interval["upper"] if interval else value
        passed = None if conservative_value is None else (conservative_value >= threshold if operator == ">=" else conservative_value <= threshold)
        checks[metric] = {
            "value": value,
            "ci95": interval,
            "decision_value": conservative_value,
            "operator": operator,
            "threshold": threshold,
            "passed": passed,
        }
    applicable = [check["passed"] for check in checks.values() if check["passed"] is not None]
    return {"passed": bool(applicable) and all(applicable), "checks": checks}


def read_packets(path: Path) -> Dict[str, Dict[str, object]]:
    return {
        packet["packet_id"]: packet
        for packet in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--split", choices=["pilot", "main", "all"], default="pilot")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260803)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    gold, predictions = read_packets(args.gold), read_packets(args.predictions)
    if set(gold) != set(predictions):
        raise ValueError("gold and prediction packet IDs differ")
    selected = [packet_id for packet_id, packet in gold.items() if args.split == "all" or packet["split"] == args.split]
    if not selected:
        raise ValueError("selected split is empty")
    rows = [score_packet(gold[packet_id], predictions[packet_id]) for packet_id in selected]
    counts = aggregate_counts(rows)
    metrics = metrics_from_counts(counts)
    intervals = bootstrap(rows, args.bootstrap_samples, args.bootstrap_seed)
    result = {
        "protocol": {
            "gold": str(args.gold.resolve()),
            "predictions": str(args.predictions.resolve()),
            "split": args.split,
            "packets": len(selected),
            "factor_match": "same type; normalized-token Jaccard>=0.5; non-zero provenance overlap; greedy maximum score",
            "provenance_correct": "matched unit evidence-token F1>=0.8",
            "bootstrap_samples": args.bootstrap_samples,
            "bootstrap_seed": args.bootstrap_seed,
            "warning": "representation-fidelity gate only; not causal-effect estimation",
        },
        "counts": dict(counts),
        "metrics": metrics,
        "bootstrap_ci95": intervals,
        "gate_a": gate_decision(metrics, intervals),
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
