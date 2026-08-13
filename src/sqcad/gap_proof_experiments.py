"""Gap-proof experiments: Proposition A, B, C — revised with formal rigour.

Revision goals (per reviewer feedback):
  Prop A — Two truly observationally equivalent SCMs with opposite-sign lifecycle values.
  Prop B — True do(E=1)/do(E=0) forced intervention, not E[Y|E=1]-E[Y|E=0].
  Prop C — Two worlds with identical source data, different target mechanisms.
  Regret — Strict positive regret on wrong actions; fixed key names.
  Stability — Proper multi-seed with mean/std/failure-rate.
  Conditions — Explicit identification-condition documentation.

Protocol: controlled synthetic worlds, not public benchmarks.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Sequence, Tuple

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

LogRow = Dict[str, float]
MethodScores = Dict[str, float]


def _seeded_rng(seed: int) -> random.Random:
    return random.Random(seed)


def _summarise(values: List[float]) -> Dict[str, float]:
    n = len(values)
    if n == 0:
        return {"mean": float("nan"), "sd": float("nan"), "n": 0}
    sd = stdev(values) if n > 1 else 0.0
    return {"mean": mean(values), "sd": sd,
            "ci95": 1.96 * sd / math.sqrt(n) if n > 1 else float("inf"),
            "n": float(n)}


# ---------------------------------------------------------------------------
# Baseline scoring methods
# ---------------------------------------------------------------------------

def score_memory_worth(logs: Sequence[LogRow], memory_ids: Sequence[str]) -> MethodScores:
    by_mem: Dict[str, List[float]] = defaultdict(list)
    for row in logs:
        if row["exposed"] == 1.0:
            by_mem[row["item"]].append(row["success"])
    return {mem: (sum(by_mem.get(mem, [])) + 1.0) / (len(by_mem.get(mem, [])) + 2.0)
            for mem in memory_ids}


def score_recency(logs: Sequence[LogRow], memory_ids: Sequence[str]) -> MethodScores:
    by_mem: Dict[str, float] = defaultdict(lambda: -1.0)
    for row in logs:
        if row["exposed"] == 1.0:
            by_mem[row["item"]] = max(by_mem[row["item"]], row["time"])
    return {mem: by_mem.get(mem, -1.0) for mem in memory_ids}


def score_frequency(logs: Sequence[LogRow], memory_ids: Sequence[str]) -> MethodScores:
    by_mem: Dict[str, int] = defaultdict(int)
    for row in logs:
        if row["exposed"] == 1.0:
            by_mem[row["item"]] += 1
    return {mem: float(by_mem.get(mem, 0)) for mem in memory_ids}


def score_fade_like(logs: Sequence[LogRow], memory_ids: Sequence[str],
                    half_life: float = 2500.0) -> MethodScores:
    by_mem: Dict[str, List[float]] = defaultdict(list)
    for row in logs:
        if row["exposed"] == 1.0:
            by_mem[row["item"]].append(row["time"])
    max_time = max((row["time"] for row in logs), default=0.0)
    scores: MethodScores = {}
    for mem in memory_ids:
        times = by_mem.get(mem, [])
        freq = len(times)
        last = max(times) if times else -1.0
        age = max_time - last if last >= 0 else max_time + 1
        scores[mem] = math.exp(-age / half_life) * math.log1p(freq)
    return scores


def decide_by_score(scores: MethodScores, threshold: float = 0.0) -> Dict[str, str]:
    return {m: "keep" if s > threshold else "archive" for m, s in scores.items()}


def decide_by_oracle(true_values: Dict[str, float]) -> Dict[str, str]:
    return {m: "keep" if v > 0 else "archive" for m, v in true_values.items()}


def compute_regret(decisions: Dict[str, str],
                   true_values: Dict[str, float]) -> Dict[str, float]:
    oracle_utility = sum(max(v, 0.0) for v in true_values.values())
    actual = sum(true_values.get(m, 0.0) if decisions.get(m) == "keep" else 0.0
                 for m in true_values)
    return {"oracle_utility": oracle_utility, "actual_utility": actual,
            "regret": oracle_utility - actual,
            "n_keep": float(sum(1 for v in decisions.values() if v == "keep")),
            "n_archive": float(sum(1 for v in decisions.values() if v == "archive"))}


# ===================================================================
# Proposition A — Two observationally equivalent SCMs
# ===================================================================
#
# Construction:
#   1. Generate ONE shared random sequence (task types, base noise, exposure draws).
#   2. m_star and m_prime are ALWAYS co-exposed (E_star = E_prime every timestep).
#   3. M₁ SCM:  Y = β₁·E_star + ε        (m_star IS the causal driver; β₁ > 0)
#   4. M₂ SCM:  Y = β₂s·E_star + β₂p·E_prime + ε
#               Since E_star ≡ E_prime: Y = (β₂s + β₂p)·E_star + ε
#               Choose β₂s < 0, β₂p = β₁ − β₂s  ⇒  P(O|M₁) = P(O|M₂)
#   5. Lifecycle values:
#        M₁: V(m_star) = β₁·p·H  > 0  → keep
#        M₂: V(m_star) = β₂s·p·H < 0  → archive!
#      Both non-zero, opposite signs.

@dataclass
class PropAConfig:
    n_timesteps: int = 5000
    n_future: int = 2000
    seed: int = 42
    exposure_rate: float = 0.55       # marginal P(E=1) for both m_star & m_prime
    beta1: float = 1.5                # M₁: m_star causal effect (positive)
    beta2_star: float = -1.0          # M₂: m_star causal effect (negative!)
    # M₂: m_prime effect = beta1 - beta2_star = 2.5  (derived, not a free param)
    outcome_noise: float = 0.50


def _prop_a_generate(cfg: PropAConfig) -> Tuple[List[LogRow], List[LogRow], List[str]]:
    """Generate M₁ and M₂ from a shared random sequence.

    Returns (logs_m1, logs_m2, memory_ids).
    """
    rng = _seeded_rng(cfg.seed)
    memory_ids = ["m_star", "m_prime", "m_noise_1", "m_noise_2", "m_noise_3"]
    logs_m1: List[LogRow] = []
    logs_m2: List[LogRow] = []
    time = 0

    beta2_prime = cfg.beta1 - cfg.beta2_star  # ensures observational equivalence

    for _ in range(cfg.n_timesteps):
        # ---- SHARED random draws ----
        task_type = rng.choice(["type_a", "type_b", "type_c"])
        difficulty = rng.random()
        noise = rng.gauss(0.0, cfg.outcome_noise)
        # m_star and m_prime ALWAYS exposed together
        both_exposed = 1.0 if rng.random() < cfg.exposure_rate else 0.0
        # Noise memories: independent random exposure
        noise_exposures = {f"m_noise_{i}": rng.choice([0.0, 1.0]) for i in range(1, 4)}

        # ---- M₁ outcome: m_star IS causal ----
        outcome_m1 = cfg.beta1 * both_exposed - 0.5 * difficulty + noise
        success_m1 = 1.0 if outcome_m1 > 0.0 else 0.0

        # ---- M₂ outcome: same distribution, different causal structure ----
        outcome_m2 = (cfg.beta2_star + beta2_prime) * both_exposed - 0.5 * difficulty + noise
        # = cfg.beta1 * both_exposed - 0.5 * difficulty + noise  (identical to M₁!)
        success_m2 = 1.0 if outcome_m2 > 0.0 else 0.0

        for mem in memory_ids:
            if mem == "m_star":
                exp = both_exposed
            elif mem == "m_prime":
                exp = both_exposed
            else:
                exp = noise_exposures.get(mem, 0.0)

            logs_m1.append({"time": float(time), "scope": 0.0, "item": mem,
                            "task_type": task_type, "difficulty": difficulty,
                            "propensity": cfg.exposure_rate, "exposed": exp,
                            "outcome": outcome_m1, "success": success_m1})
            logs_m2.append({"time": float(time), "scope": 0.0, "item": mem,
                            "task_type": task_type, "difficulty": difficulty,
                            "propensity": cfg.exposure_rate, "exposed": exp,
                            "outcome": outcome_m2, "success": success_m2})
        time += 1
    return logs_m1, logs_m2, memory_ids


def _prop_a_lifecycle_values(cfg: PropAConfig) -> Dict[str, float]:
    """True lifecycle value V(keep) - V(archive) for each memory in each world.

    Under archive: memory is never exposed.
    Under keep: memory exposed at cfg.exposure_rate, exerts its true causal effect.
    """
    # M₁: m_star effect = beta1 > 0
    # M₂: m_star effect = beta2_star < 0
    return {
        "m_star_M1": cfg.beta1 * cfg.exposure_rate * cfg.n_future,
        "m_star_M2": cfg.beta2_star * cfg.exposure_rate * cfg.n_future,
        "m_prime_M1": 0.0,   # m_prime has no causal role in M₁
        "m_prime_M2": (cfg.beta1 - cfg.beta2_star) * cfg.exposure_rate * cfg.n_future,
    }


def _prop_a_distribution_check(logs_m1: List[LogRow], logs_m2: List[LogRow],
                                memory_ids: List[str]) -> Dict[str, Any]:
    """Verify P(O|M₁) = P(O|M₂) across the full joint distribution.

    Fairness requirement: the two worlds must be observationally identical in
    EVERY observable field for EVERY row — not just the m_star outcome. Since
    outcomes are computed from the SAME random draws with algebraically
    equivalent structural equations, P(O|M₁) ≡ P(O|M₂) by construction; we
    verify it over all rows and all numeric fields.
    """
    m1_outcomes = [r["outcome"] for r in logs_m1 if r["item"] == "m_star"]
    m2_outcomes = [r["outcome"] for r in logs_m2 if r["item"] == "m_star"]
    max_abs_diff = max(abs(a - b) for a, b in zip(m1_outcomes, m2_outcomes))

    # Full-joint check: every observable field, every row (all memories).
    numeric_fields = ["time", "scope", "difficulty", "propensity",
                      "exposed", "outcome", "success"]
    max_field_diff = 0.0
    n_rows_checked = 0
    for r1, r2 in zip(logs_m1, logs_m2):
        n_rows_checked += 1
        if r1["item"] != r2["item"]:
            raise AssertionError("M₁/M₂ logs not aligned by item")
        for f in numeric_fields:
            max_field_diff = max(max_field_diff, abs(r1[f] - r2[f]))

    m1_star = [r for r in logs_m1 if r["item"] == "m_star"]
    m2_star = [r for r in logs_m2 if r["item"] == "m_star"]

    return {
        "construction": (
            "M₁ and M₂ share the SAME random sequence. "
            "M₁: Y = β₁·E + ε, with β₁={:.2f}. "
            "M₂: Y = (β₂s+β₂p)·E + ε = {:.2f}·E + ε, identical distribution. "
            "But M₁ m_star causal effect = {:.2f}, M₂ m_star causal effect = {:.2f}."
        ).format(cfg.beta1, cfg.beta1, cfg.beta1, cfg.beta2_star),
        "max_outcome_diff": max_abs_diff,
        "outcome_identical": max_abs_diff < 1e-9,
        "full_joint_identical": max_field_diff < 1e-9,
        "max_field_diff": max_field_diff,
        "n_rows_checked": n_rows_checked,
        "m_star_exposure_rate_M1": mean(r["exposed"] for r in m1_star),
        "m_star_exposure_rate_M2": mean(r["exposed"] for r in m2_star),
        "m_star_success_rate_M1": mean(r["success"] for r in m1_star if r["exposed"] == 1.0),
        "m_star_success_rate_M2": mean(r["success"] for r in m2_star if r["exposed"] == 1.0),
        "mean_outcome_M1": mean(r["outcome"] for r in m1_star),
        "mean_outcome_M2": mean(r["outcome"] for r in m2_star),
    }


# Import shared cfg at module level for _prop_a_distribution_check
cfg: PropAConfig  # forward ref for the closure below — resolved at call time


def run_proposition_a(cfg_a: PropAConfig | None = None) -> Dict[str, Any]:
    global cfg
    cfg = cfg_a or PropAConfig()

    logs_m1, logs_m2, memories = _prop_a_generate(cfg)

    # Baseline scores (these operate on observed data only)
    baselines = {
        "memory_worth": (score_memory_worth, {}),
        "recency": (score_recency, {}),
        "frequency": (score_frequency, {}),
        "fade_like": (score_fade_like, {"half_life": 2500.0}),
    }

    m1_scores: Dict[str, MethodScores] = {}
    m2_scores: Dict[str, MethodScores] = {}
    for name, (fn, kwargs) in baselines.items():
        m1_scores[name] = fn(logs_m1, memories, **kwargs)
        m2_scores[name] = fn(logs_m2, memories, **kwargs)

    # Distribution check
    dist_check = _prop_a_distribution_check(logs_m1, logs_m2, memories)

    # True lifecycle values
    lv = _prop_a_lifecycle_values(cfg)

    # Decision regret: each baseline decides on m_star using observed scores
    # The lifecycle value of m_star differs between M1 and M2
    lv_m1_map = {"m_star": lv["m_star_M1"], "m_prime": lv["m_prime_M1"],
                 "m_noise_1": 0.0, "m_noise_2": 0.0, "m_noise_3": 0.0}
    lv_m2_map = {"m_star": lv["m_star_M2"], "m_prime": lv["m_prime_M2"],
                 "m_noise_1": 0.0, "m_noise_2": 0.0, "m_noise_3": 0.0}

    regret_m1: Dict[str, Dict[str, float]] = {}
    regret_m2: Dict[str, Dict[str, float]] = {}
    for method in baselines:
        dec_m1 = decide_by_score(m1_scores[method], threshold=0.5 if method == "memory_worth" else 0.0)
        dec_m2 = decide_by_score(m2_scores[method], threshold=0.5 if method == "memory_worth" else 0.0)
        regret_m1[method] = compute_regret(dec_m1, lv_m1_map)
        regret_m2[method] = compute_regret(dec_m2, lv_m2_map)

    # Oracle
    oracle_m1 = compute_regret(decide_by_oracle(lv_m1_map), lv_m1_map)
    oracle_m2 = compute_regret(decide_by_oracle(lv_m2_map), lv_m2_map)

    # Verdict
    mw_m1_keeps = m1_scores["memory_worth"].get("m_star", 0.0) > 0.5
    mw_m2_keeps = m2_scores["memory_worth"].get("m_star", 0.0) > 0.5
    mw_regret_m2 = regret_m2["memory_worth"]["regret"]

    prop_a_holds = (
        dist_check["outcome_identical"]
        and dist_check["full_joint_identical"]
        and lv["m_star_M1"] > 0.5
        and lv["m_star_M2"] < -0.5
        and mw_m1_keeps
        and mw_m2_keeps
        and mw_regret_m2 > 0.1  # strict positive regret in M2
    )

    return {
        "proposition": "A",
        "title": "Two observationally equivalent SCMs, opposite lifecycle values",
        "protocol": {"n_timesteps": cfg.n_timesteps, "n_future": cfg.n_future,
                     "seed": cfg.seed, "beta1": cfg.beta1,
                     "beta2_star": cfg.beta2_star,
                     "exposure_rate": cfg.exposure_rate,
                     "construction": "shared random sequence; E_star ≡ E_prime; "
                     "P(O|M₁)=P(O|M₂) by algebraic equivalence"},
        "distribution_check": dist_check,
        "baseline_m_star_scores": {
            method: {"M1": m1_scores[method].get("m_star", 0.0),
                     "M2": m2_scores[method].get("m_star", 0.0)}
            for method in baselines
        },
        "lifecycle_values": lv,
        "regret": {"M1": regret_m1, "M2": regret_m2,
                   "oracle_M1": oracle_m1, "oracle_M2": oracle_m2},
        "verdict": {
            "proposition_holds": prop_a_holds,
            "P_O_identical": dist_check["outcome_identical"],
            "m_star_M1_positive": lv["m_star_M1"] > 0,
            "m_star_M2_negative": lv["m_star_M2"] < 0,
            "memory_worth_regret_in_M2": mw_regret_m2,
            "summary": (
                f"Proposition A HOLDS: P(O|M₁)=P(O|M₂) (max outcome diff "
                f"{dist_check['max_outcome_diff']:.1e}). M₁ lifecycle value "
                f"={lv['m_star_M1']:.1f} (keep), M₂ lifecycle value "
                f"={lv['m_star_M2']:.1f} (archive). Memory Worth regret in "
                f"M₂ = {mw_regret_m2:.1f}. Non-identifiability established."
                if prop_a_holds
                else "Proposition A FAILS."
            ),
        },
    }


# ===================================================================
# Proposition B — True do-intervention, equal Δ yet opposite lifecycle
# ===================================================================
#
# Construction:
#   - Fixed query context (same task, same candidate set, same evaluator).
#   - For each memory, directly simulate BOTH do(E=1) and do(E=0) on the
#     SAME query → true causal Δ_do = Y|do(E=1) - Y|do(E=0).
#   - m_short: Δ_do = α, but keeping it long-term crowds out critical
#     memories → negative lifecycle value.
#   - m_long: Δ_do = α (exactly same), but keeping it preserves rare
#     critical task retrieval path → positive lifecycle value.

@dataclass
class PropBConfig:
    n_queries: int = 500           # number of distinct query contexts
    n_future_steps: int = 2000
    seed: int = 123
    alpha: float = 2.0             # Δ_do for BOTH memories (exactly equal by construction)
    critical_value: float = 4.0    # value of rare critical task success
    crowding_prob: float = 0.25    # per-exposure prob m_short crowds out critical
    bridge_boost: float = 3.0      # m_long enables rare task success
    outcome_noise: float = 0.40
    memory_ids: Tuple[str, ...] = ("m_short", "m_long", "m_critical",
                                    "m_common_1", "m_common_2")


def _prop_b_generate(cfg: PropBConfig) -> Tuple[List[LogRow], List[str], Dict[str, float]]:
    """Generate source-period queries with true do-interventions.

    For each query context, we compute:
      - Y_do1(mem): outcome when memory is forced IN
      - Y_do0(mem): outcome when memory is forced OUT
      - Δ_do(mem) = Y_do1 - Y_do0

    By construction, Δ_do(m_short) = Δ_do(m_long) = alpha.

    Fairness: the true do-outcomes are returned SEPARATELY as an oracle map,
    never written into the observational log — a deployed system's log must
    not contain counterfactual columns that a baseline could (even
    accidentally) read.
    """
    rng = _seeded_rng(cfg.seed)
    memories = list(cfg.memory_ids)
    logs: List[LogRow] = []
    time = 0
    deltas: Dict[str, List[float]] = defaultdict(list)

    for _ in range(cfg.n_queries):
        task_type = rng.choice(["common", "rare_critical", "noise"])
        difficulty = rng.random()
        base_noise = rng.gauss(0.0, cfg.outcome_noise)

        # ---- Baseline outcome (no memories exposed) ----
        y_baseline = -0.5 * difficulty + base_noise

        # ---- m_short: forced-in adds alpha to current answer ----
        y_m_short_in = y_baseline + cfg.alpha
        # ---- m_long: forced-in also adds alpha to current answer ----
        y_m_long_in = y_baseline + cfg.alpha

        # ---- m_critical: forced-in has large effect on rare tasks ----
        if task_type == "rare_critical":
            y_critical_in = y_baseline + cfg.critical_value
        else:
            y_critical_in = y_baseline + 0.2

        # ---- Other memories: small or zero effect ----
        y_common_in = y_baseline + 0.3

        # Observational exposure is RANDOM (unconfounded), so
        # E[Y|E=1]-E[Y|E=0] is an UNBIASED estimate of the local do-effect —
        # the CMI baseline is given a fair, causally valid chance.
        for mem, y_do1 in [("m_short", y_m_short_in), ("m_long", y_m_long_in),
                            ("m_critical", y_critical_in),
                            ("m_common_1", y_common_in), ("m_common_2", y_common_in)]:
            exposed_flag = rng.choice([0.0, 1.0])
            y_obs = y_baseline if exposed_flag == 0.0 else y_do1
            logs.append({
                "time": float(time), "scope": 0.0, "item": mem,
                "task_type": task_type, "difficulty": difficulty,
                "propensity": 0.50, "exposed": exposed_flag,
                "outcome": y_obs,
                "success": 1.0 if y_obs > 0.0 else 0.0,
            })
            deltas[mem].append(y_do1 - y_baseline)
        time += 1

    true_do = {mem: mean(ds) for mem, ds in deltas.items()}
    return logs, memories, true_do


def _prop_b_lifecycle_values(cfg: PropBConfig) -> Dict[str, float]:
    """Future rollout: keep vs archive for each memory.

    m_short: Δ_do = α in source period, but in future rollout it provides
      ZERO benefit (its usefulness was specific to source-period task dist).
      Keeping it only crowds out critical memory → NEGATIVE lifecycle value.
    m_long: Δ_do = α in source period (identical), AND in future rollout
      it preserves the rare critical task retrieval bridge → POSITIVE value.
    """
    rng = _seeded_rng(cfg.seed + 50000)
    values: Dict[str, float] = {}

    for target_mem in cfg.memory_ids:
        utility_keep = 0.0
        utility_archive = 0.0
        critical_accessible_keep = True
        critical_accessible_archive = True

        for _ in range(cfg.n_future_steps):
            task_type = rng.choice(["common", "rare_critical", "noise"])
            difficulty = rng.random()

            if target_mem == "m_short":
                # m_short provides ZERO benefit in future (its source-period
                # usefulness does not generalise). It only crowds out.
                m_short_exposed = 1.0 if rng.random() < 0.5 else 0.0
                if m_short_exposed == 1.0 and critical_accessible_keep:
                    if rng.random() < cfg.crowding_prob:
                        critical_accessible_keep = False

                critical_used_keep = 1.0 if (
                    task_type == "rare_critical" and critical_accessible_keep
                    and rng.random() < 0.7
                ) else 0.0
                critical_used_archive = 1.0 if (
                    task_type == "rare_critical" and critical_accessible_archive
                    and rng.random() < 0.7
                ) else 0.0

                # m_short: zero own contribution in future
                utility_keep += (
                    0.0 * m_short_exposed  # no benefit!
                    + cfg.critical_value * critical_used_keep
                    - 0.5 * difficulty
                )
                utility_archive += (
                    cfg.critical_value * critical_used_archive
                    - 0.5 * difficulty
                )

            elif target_mem == "m_long":
                # m_long: keeping it preserves rare task bridge
                bridge_active_keep = True
                bridge_active_archive = False
                rare_success_keep = 1.0 if (
                    task_type == "rare_critical" and bridge_active_keep
                    and rng.random() < 0.7
                ) else 0.0
                rare_success_archive = 1.0 if (
                    task_type == "rare_critical" and bridge_active_archive
                    and rng.random() < 0.3  # much lower without bridge
                ) else 0.0

                utility_keep += (
                    cfg.critical_value * rare_success_keep
                    - 0.5 * difficulty
                )
                utility_archive += (
                    cfg.critical_value * rare_success_archive
                    - 0.5 * difficulty
                )

            elif target_mem == "m_critical":
                crit_used_keep = 1.0 if (
                    task_type == "rare_critical" and rng.random() < 0.7
                ) else 0.0
                utility_keep += (
                    cfg.critical_value * crit_used_keep - 0.5 * difficulty
                )
                utility_archive += -0.5 * difficulty

            else:
                utility_keep += -0.5 * difficulty
                utility_archive += -0.5 * difficulty

        values[target_mem] = utility_keep - utility_archive

    return values


def run_proposition_b(cfg_b: PropBConfig | None = None) -> Dict[str, Any]:
    cfg = cfg_b or PropBConfig()

    # True do-intervention effects are computed at generation time and kept
    # OUTSIDE the observational log (no oracle leakage into O).
    logs, memories, true_do = _prop_b_generate(cfg)

    # Observational baselines
    mw_scores = score_memory_worth(logs, memories)
    fade_scores = score_fade_like(logs, memories)
    # Observational "CMI-like" (what a real CMI implementation would estimate)
    cmi_obs: Dict[str, float] = {}
    by_mem_obs: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    for row in logs:
        by_mem_obs[row["item"]].append(row)
    for mem in memories:
        rows = by_mem_obs.get(mem, [])
        exposed = [r["outcome"] for r in rows if r["exposed"] == 1.0]
        hidden = [r["outcome"] for r in rows if r["exposed"] == 0.0]
        cmi_obs[mem] = (mean(exposed) if exposed else 0.0) - (mean(hidden) if hidden else 0.0)

    # True lifecycle values
    lv = _prop_b_lifecycle_values(cfg)

    # Key comparison
    m_short_do = true_do.get("m_short", 0.0)
    m_long_do = true_do.get("m_long", 0.0)
    m_short_lv = lv.get("m_short", 0.0)
    m_long_lv = lv.get("m_long", 0.0)

    # Decision regret
    baseline_scores_map = {
        "cmi_observational": cmi_obs,
        "memory_worth": mw_scores,
        "fade_like": fade_scores,
    }
    regret_results: Dict[str, Dict[str, float]] = {}
    for method, scores in baseline_scores_map.items():
        thresh = 0.5 if method == "memory_worth" else 0.0
        dec = decide_by_score(scores, threshold=thresh)
        regret_results[method] = compute_regret(dec, lv)
    regret_results["oracle"] = compute_regret(decide_by_oracle(lv), lv)

    # Verdict
    do_equal = abs(m_short_do - m_long_do) < 0.01  # exactly equal by construction
    lv_opposite = (m_short_lv < 0 < m_long_lv) or (m_long_lv < 0 < m_short_lv)
    cmi_regret = regret_results.get("cmi_observational", {}).get("regret", 0.0)
    prop_b_holds = do_equal and lv_opposite and cmi_regret > 0.1

    return {
        "proposition": "B",
        "title": "True do-intervention: equal Δ_do, opposite lifecycle values",
        "protocol": {"n_queries": cfg.n_queries, "n_future": cfg.n_future_steps,
                     "seed": cfg.seed, "alpha": cfg.alpha,
                     "intervention_type": "forced-in/forced-out on fixed query context"},
        "true_do_effects": {
            "m_short": m_short_do, "m_long": m_long_do,
            "diff": abs(m_short_do - m_long_do),
            "exactly_equal": do_equal,
        },
        "cmi_observational_estimates": {
            "m_short": cmi_obs.get("m_short", 0.0),
            "m_long": cmi_obs.get("m_long", 0.0),
            "note": "Observational E[Y|E=1]-E[Y|E=0] — what CMI would estimate from logs",
        },
        "lifecycle_values": {
            "m_short": m_short_lv, "m_long": m_long_lv,
            "m_short_should": "archive" if m_short_lv < 0 else "keep",
            "m_long_should": "archive" if m_long_lv < 0 else "keep",
        },
        "regret": regret_results,
        "verdict": {
            "proposition_holds": prop_b_holds,
            "do_equal": do_equal,
            "lifecycle_opposite_sign": lv_opposite,
            "cmi_regret_positive": cmi_regret > 0.1,
            "summary": (
                f"Proposition B HOLDS: Δ_do(m_short)={m_short_do:.3f}, "
                f"Δ_do(m_long)={m_long_do:.3f} (identical). "
                f"Lifecycle: m_short={m_short_lv:.1f} (archive), "
                f"m_long={m_long_lv:.1f} (keep). "
                f"CMI regret={cmi_regret:.1f}. "
                "True do-intervention effect ≠ lifecycle policy value."
                if prop_b_holds
                else "Proposition B FAILS."
            ),
        },
    }


# ===================================================================
# Proposition C — Two worlds, identical source data, different target
# ===================================================================
#
# Construction:
#   - Generate ONE set of source-scope logs (scopes s₁, s₂).
#   - WORLD 1 target mechanism: τ(s^*) > 0  (keep beneficial)
#   - WORLD 2 target mechanism: τ(s^*) < 0  (archive beneficial)
#   - Source data IDENTICAL between worlds → cannot distinguish.
#   - Scope weights used correctly for source-average estimation.

@dataclass
class PropCConfig:
    n_source_steps: int = 4000
    n_target_steps: int = 2000
    seed: int = 456
    scope_s1_weight: float = 0.55
    scope_s2_weight: float = 0.45
    # Per-scope effects (same in both worlds for source scopes)
    tau_s1: float = 0.8
    tau_s2: float = -1.6
    # Target scope effects DIFFER between worlds
    tau_target_w1: float = 2.0    # World 1: positive
    tau_target_w2: float = -2.0   # World 2: negative
    target_scope_id: float = 99.0
    outcome_noise: float = 0.50


def _prop_c_generate(cfg: PropCConfig) -> Tuple[List[LogRow], List[str]]:
    """Generate shared source-scope logs."""
    rng = _seeded_rng(cfg.seed)
    memory_ids = ["m_target", "m_ctrl_1", "m_ctrl_2", "m_noise_1", "m_noise_2"]
    logs: List[LogRow] = []
    time = 0

    n_s1 = int(cfg.n_source_steps * cfg.scope_s1_weight)
    n_s2 = cfg.n_source_steps - n_s1

    for scope_id, n_steps, tau in [(1.0, n_s1, cfg.tau_s1), (2.0, n_s2, cfg.tau_s2)]:
        for _ in range(n_steps):
            difficulty = rng.random()
            noise = rng.gauss(0.0, cfg.outcome_noise)
            for mem in memory_ids:
                if mem == "m_target":
                    exp = 1.0 if rng.random() < 0.55 else 0.0
                    outcome = tau * exp - 0.5 * difficulty + noise
                elif mem.startswith("m_ctrl"):
                    exp = rng.choice([0.0, 1.0])
                    outcome = 0.3 * exp - 0.5 * difficulty + noise
                else:
                    exp = rng.choice([0.0, 1.0])
                    outcome = -0.5 * difficulty + noise
                success = 1.0 if outcome > 0.0 else 0.0
                logs.append({"time": float(time), "scope": scope_id,
                             "item": mem, "difficulty": difficulty,
                             "propensity": 0.55, "exposed": exp,
                             "outcome": outcome, "success": success})
            time += 1
    return logs, memory_ids


def _prop_c_lifecycle_values(cfg: PropCConfig) -> Dict[str, Dict[str, float]]:
    """True lifecycle values for each memory in each world's target scope."""
    return {
        "m_target": {
            "s1": cfg.tau_s1, "s2": cfg.tau_s2,
            "target_world1": cfg.tau_target_w1,
            "target_world2": cfg.tau_target_w2,
        },
        "m_ctrl_1": {"s1": 0.3, "s2": 0.3, "target_world1": 0.3, "target_world2": 0.3},
        "m_ctrl_2": {"s1": 0.3, "s2": 0.3, "target_world1": 0.3, "target_world2": 0.3},
        "m_noise_1": {"s1": 0.0, "s2": 0.0, "target_world1": 0.0, "target_world2": 0.0},
        "m_noise_2": {"s1": 0.0, "s2": 0.0, "target_world1": 0.0, "target_world2": 0.0},
    }


def _prop_c_scope_weighted_estimate(logs: List[LogRow], memory_ids: List[str],
                                     scope_weights: Dict[float, float]) -> Dict[str, float]:
    """Estimate scope-weighted average causal effect (proper OPE-style).

    Within each scope: E[Y|E=1] - E[Y|E=0].
    Across scopes: weighted average by scope prevalence.
    """
    by_mem_scope: Dict[str, Dict[float, List[Dict[str, float]]]] = \
        defaultdict(lambda: defaultdict(list))
    for row in logs:
        by_mem_scope[row["item"]][row["scope"]].append(row)

    estimates: Dict[str, float] = {}
    for mem in memory_ids:
        weighted_sum = 0.0
        total_weight = 0.0
        for scope_id, weight in scope_weights.items():
            rows = by_mem_scope[mem].get(scope_id, [])
            exposed = [r["outcome"] for r in rows if r["exposed"] == 1.0]
            hidden = [r["outcome"] for r in rows if r["exposed"] == 0.0]
            if len(exposed) >= 2 and len(hidden) >= 2:
                scope_est = mean(exposed) - mean(hidden)
                weighted_sum += weight * scope_est
                total_weight += weight
        estimates[mem] = weighted_sum / total_weight if total_weight > 0 else 0.0
    return estimates


def run_proposition_c(cfg_c: PropCConfig | None = None) -> Dict[str, Any]:
    cfg = cfg_c or PropCConfig()

    # Shared source data
    logs, memories = _prop_c_generate(cfg)

    # Scope-weighted estimate (properly using source scope weights)
    scope_weights = {1.0: cfg.scope_s1_weight, 2.0: cfg.scope_s2_weight}
    weighted_scores = _prop_c_scope_weighted_estimate(logs, memories, scope_weights)

    # Other baselines
    mw_scores = score_memory_worth(logs, memories)
    fade_scores = score_fade_like(logs, memories)

    # True lifecycle values
    true_lv = _prop_c_lifecycle_values(cfg)

    # Source weighted average for m_target
    source_avg_estimated = weighted_scores.get("m_target", 0.0)
    source_avg_design = (cfg.scope_s1_weight * cfg.tau_s1 +
                         cfg.scope_s2_weight * cfg.tau_s2)

    # Target values in two worlds
    tau_target_w1 = cfg.tau_target_w1
    tau_target_w2 = cfg.tau_target_w2

    # Source average recommends...
    source_recommends = "keep" if source_avg_design > 0 else "archive"
    target_w1_needs = "keep" if tau_target_w1 > 0 else "archive"
    target_w2_needs = "keep" if tau_target_w2 > 0 else "archive"

    # Regret: using source-average decision in each target world
    lv_w1 = {mem: true_lv[mem]["target_world1"] for mem in memories}
    lv_w2 = {mem: true_lv[mem]["target_world2"] for mem in memories}

    # Source-average based decision applied to both target worlds
    source_dec = {mem: "keep" if weighted_scores.get(mem, 0.0) > 0 else "archive"
                  for mem in memories}

    regret_w1 = compute_regret(source_dec, lv_w1)
    regret_w2 = compute_regret(source_dec, lv_w2)
    oracle_w1 = compute_regret(decide_by_oracle(lv_w1), lv_w1)
    oracle_w2 = compute_regret(decide_by_oracle(lv_w2), lv_w2)

    # Verdict
    # The SAME source data leads to opposite recommendations in different worlds
    source_data_identical = True  # by construction
    target_effects_differ = (tau_target_w1 > 0) != (tau_target_w2 > 0)
    source_misleads_w1 = source_recommends != target_w1_needs
    source_misleads_w2 = source_recommends != target_w2_needs
    prop_c_holds = (source_data_identical and target_effects_differ
                    and (source_misleads_w1 or source_misleads_w2))

    return {
        "proposition": "C",
        "title": "Identical source data, different target mechanisms → non-transportability",
        "protocol": {"n_source_steps": cfg.n_source_steps, "seed": cfg.seed,
                     "scope_s1_weight": cfg.scope_s1_weight,
                     "scope_s2_weight": cfg.scope_s2_weight,
                     "tau_s1": cfg.tau_s1, "tau_s2": cfg.tau_s2,
                     "tau_target_world1": cfg.tau_target_w1,
                     "tau_target_world2": cfg.tau_target_w2,
                     "construction": "shared source logs; two worlds differ only "
                     "in target-scope structural mechanisms"},
        "source_estimates": {
            "scope_weighted_average_estimated": source_avg_estimated,
            "scope_weighted_average_design": source_avg_design,
            "source_recommends": source_recommends,
        },
        "target_scope_values": {
            "world1": tau_target_w1, "world1_should": target_w1_needs,
            "world2": tau_target_w2, "world2_should": target_w2_needs,
        },
        "source_data_identical": source_data_identical,
        "regret": {
            "source_avg_in_world1": regret_w1,
            "source_avg_in_world2": regret_w2,
            "oracle_world1": oracle_w1,
            "oracle_world2": oracle_w2,
        },
        "verdict": {
            "proposition_holds": prop_c_holds,
            "source_data_identical": source_data_identical,
            "target_signs_differ": target_effects_differ,
            "source_misleads_at_least_one_world": source_misleads_w1 or source_misleads_w2,
            "summary": (
                f"Proposition C HOLDS: Source data identical across worlds. "
                f"Source weighted avg = {source_avg_design:.2f} → '{source_recommends}'. "
                f"World 1 target τ = {tau_target_w1:.1f} → '{target_w1_needs}'. "
                f"World 2 target τ = {tau_target_w2:.1f} → '{target_w2_needs}'. "
                f"Source data cannot identify target value → scope transport "
                f"non-identifiability established."
                if prop_c_holds
                else "Proposition C FAILS."
            ),
        },
    }


# ===================================================================
# Integrated experiment (fixed key names, proper regret extraction)
# ===================================================================

def run_integrated(
    prop_a_cfg: PropAConfig | None = None,
    prop_b_cfg: PropBConfig | None = None,
    prop_c_cfg: PropCConfig | None = None,
) -> Dict[str, Any]:
    result_a = run_proposition_a(prop_a_cfg)
    result_b = run_proposition_b(prop_b_cfg)
    result_c = run_proposition_c(prop_c_cfg)

    all_hold = all(r["verdict"]["proposition_holds"]
                   for r in [result_a, result_b, result_c])

    return {
        "title": "Integrated gap-proof experiment (revised — formal rigour)",
        "propositions": {"A": result_a, "B": result_b, "C": result_c},
        "regret_summary": {
            "A_memory_worth_regret_M2": (
                result_a["regret"]["M2"].get("memory_worth", {}).get("regret", 0.0)
            ),
            "B_cmi_regret": (
                result_b["regret"].get("cmi_observational", {}).get("regret", 0.0)
            ),
            "C_source_avg_regret_world1": (
                result_c["regret"]["source_avg_in_world1"].get("regret", 0.0)
            ),
            "C_source_avg_regret_world2": (
                result_c["regret"]["source_avg_in_world2"].get("regret", 0.0)
            ),
        },
        "overall_verdict": {
            "all_hold": all_hold,
            "summary": (
                "All three counterexamples hold. Each baseline path "
                "(association, local intervention, scope-average) fails on "
                "its corresponding construction. This provides "
                "counterexample-supported evidence for a memory-specific "
                "lifecycle identification gap — a candidate theoretical blank."
                if all_hold
                else "Not all propositions hold. See individual verdicts."
            ),
        },
    }


# ===================================================================
# Multi-seed stability (properly iterates seeds)
# ===================================================================

def run_multi_seed(n_seeds: int = 10, base_seed: int = 0) -> Dict[str, Any]:
    """Run all propositions across multiple seeds, reporting mean/std/failure rate."""
    results_a: List[bool] = []
    results_b: List[bool] = []
    results_c: List[bool] = []
    regrets_a: List[float] = []
    regrets_b: List[float] = []
    regrets_c: List[float] = []

    for i in range(n_seeds):
        seed_a = base_seed + i * 100 + 42
        seed_b = base_seed + i * 100 + 123
        seed_c = base_seed + i * 100 + 456

        ra = run_proposition_a(PropAConfig(seed=seed_a))
        rb = run_proposition_b(PropBConfig(seed=seed_b))
        rc = run_proposition_c(PropCConfig(seed=seed_c))

        results_a.append(ra["verdict"]["proposition_holds"])
        results_b.append(rb["verdict"]["proposition_holds"])
        results_c.append(rc["verdict"]["proposition_holds"])

        regrets_a.append(ra["regret"]["M2"].get("memory_worth", {}).get("regret", 0.0))
        regrets_b.append(rb["regret"].get("cmi_observational", {}).get("regret", 0.0))
        regrets_c.append(rc["regret"]["source_avg_in_world1"].get("regret", 0.0))

    return {
        "n_seeds": n_seeds,
        "proposition_A": {
            "hold_rate": sum(results_a) / n_seeds,
            "regret": _summarise(regrets_a),
            "all_hold": all(results_a),
        },
        "proposition_B": {
            "hold_rate": sum(results_b) / n_seeds,
            "regret": _summarise(regrets_b),
            "all_hold": all(results_b),
        },
        "proposition_C": {
            "hold_rate": sum(results_c) / n_seeds,
            "regret": _summarise(regrets_c),
            "all_hold": all(results_c),
        },
    }


# ===================================================================
# Identification conditions (documented per reviewer request)
# ===================================================================

IDENTIFICATION_CONDITIONS = """
Minimum identification conditions for persistent-access lifecycle value
V_s^π(a) under the SQCAD framework (derived from the counterexample
constructions above):

1. CONSISTENCY
   The observed persistent action must equal the counterfactual action
   under the assigned treatment: A_i^{obs} = A_i^{pers} when assigned.

2. SEQUENTIAL EXCHANGEABILITY
   Given full history (task state, policy state, memory state, candidate
   stream), treatment assignment is independent of potential outcomes.
   Requires: no unobserved confounders driving both access decisions and
   future outcomes.

3. POSITIVITY / OVERLAP
   Every candidate persistent action (keep, downweight, isolate, archive,
   restore) must have non-zero probability in every relevant stratum of
   the state space.

4. TREATMENT OBSERVABILITY
   Access action type, effective duration, and rollback must be recorded
   in the log. "Appeared in prompt" is not sufficient for adoption.

5. EXPOSURE OBSERVABILITY
   Candidate stream, exposure propensity, position, budget, and reader
   context must be distinguishable in the logs.

6. ADOPTION MEASUREMENT
   Whether the model actually used the memory cannot be equated with
   prompt presence. Requires an observable proxy, error model, or
   explicit non-identification bounds.

7. INTERFERENCE SPECIFICATION
   Co-memory competition, workspace budget constraints, and shared
   exposure must be explicitly modelled. Per-memory additive effects
   are not generally valid (see Theorem candidate 5).

8. MEASUREMENT STABILITY
   Reader, model version, tool configuration, and evaluator must be
   fixed or explicitly modelled within each source evaluation window.

9. SCOPE TRANSPORT (for Gap 2)
   Target scope must fall within the support of source scope
   distributions, OR explicit transport assumptions (invariant
   mechanisms, overlap) must be stated and validated.

When any of conditions 1–8 fail, V_s^π(a) may only be partially
identified (bounds) or unresolved (no permission to change access).
"""


# ===================================================================
# CLI
# ===================================================================

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proposition", choices=["A", "B", "C", "all"], default="all")
    p.add_argument("--multi-seed", type=int, default=0,
                   help="Run N random seeds for stability analysis")
    p.add_argument("--output", type=Path,
                   default=Path("results/gap_proof_experiments_v2.json"))
    p.add_argument("--compact", action="store_true")
    p.add_argument("--identification-conditions", action="store_true",
                   help="Print identification conditions and exit")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.identification_conditions:
        print(IDENTIFICATION_CONDITIONS)
        return 0

    if args.multi_seed > 0:
        stability = run_multi_seed(args.multi_seed)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(stability, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        for prop in ["proposition_A", "proposition_B", "proposition_C"]:
            s = stability[prop]
            print(f"{prop}: hold_rate={s['hold_rate']:.2f}, "
                  f"mean_regret={s['regret']['mean']:.3f} ± {s['regret']['sd']:.3f}")
        return 0

    integrated = run_integrated()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.compact:
        compact = {
            "overall_verdict": integrated["overall_verdict"],
            "proposition_verdicts": {
                k: integrated["propositions"][k]["verdict"]
                for k in ["A", "B", "C"]
            },
        }
        args.output.write_text(json.dumps(compact, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        print(json.dumps(compact, ensure_ascii=True, indent=2))
    else:
        args.output.write_text(json.dumps(integrated, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        for k in ["A", "B", "C"]:
            s = integrated['propositions'][k]['verdict']['summary']
            for u, a in [('₁', '_1'), ('₂', '_2'), ('≠', '!='),
                         ('Δ', 'Delta'), ('τ', 'tau'), ('→', '->')]:
                s = s.replace(u, a)
            print(f"Proposition {k}: {s}")
        ov = integrated['overall_verdict']['summary'].replace('—', '--')
        print(f"\n{ov}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
