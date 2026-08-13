"""Tests for the W0-W3 structural ablation (14- §5/§7.1-§7.3).

Headline cells (mechanism-level, 4 seeds, tau=10, p_expose=0.6):
  * W0 query-local uncensored: watchful policies correct (slope ~ 0),
    committed static rules fail linearly (slope = tau*p_expose).
  * W2 censored no-restore: self-confirming -- even watchful rules accrue
    linear regret; association_commit is observationally equivalent across
    K/A (bit-identical logs, opposite lifecycle values).
  * W3 restore channel: fixed-probability restore, staleness-triggered
    restore and cost-aware commit/defer/probe plateau; no-restore rules
    (no_probe_commit, local_causal_commit, gate_no_probe, gate_keep_default)
    stay linear.  The gate commits because the confounded early signal is
    statistically resolved-negative -- the resolution is the trap.
  * Reduction controls (14- §7.2): standard machinery (static bandit,
    contextual bandit, log-based OPE, candidate-exploring UCB) succeeds in
    W0/W1 and fails linearly in W2 (censoring breaks overlap).
"""

import math

import pytest

from sqcad.self_obscuring_ablation import (
    AUTO_ARCHIVED_POLICIES,
    DECISION_POLICIES,
    config_for,
    run_policy,
    build_world,
    observational_equivalence,
    paired_bootstrap,
    summarize,
    structural_ablation,
)

N_SEEDS = 4
SEED0 = 21
SLOPE = 10.0 * 0.6  # tau * p_expose = 6.0 per step (mean is 5.85 over 2000)


def slope_of(rows, label, world, policy):
    cell = rows[f"{label}_{world}_{policy}"]
    return cell["per_step_slope"]["mean"]


def run_matrix(policies, labels=("W0", "W1", "W2", "W3")):
    rows = []
    for label in labels:
        for seed in range(SEED0, SEED0 + N_SEEDS):
            for world_name in ("K", "A"):
                cfg = config_for(seed, world_name, label)
                world = build_world(cfg)
                for policy in policies:
                    row = run_policy(world, policy)
                    row["world_label"] = label
                    rows.append(row)
    return summarize(rows)


# ---------------------------------------------------------------------------
# W0-W3 structural matrix
# ---------------------------------------------------------------------------


def test_w0_query_local_watchful_corrects():
    rows = run_matrix(("watchful_no_restore",))
    # K: committed archive is wrong, but evidence is uncensored -> corrects
    assert slope_of(rows, "W0", "K", "watchful_no_restore") < 0.3
    # A: committed archive is right -> no regret
    assert slope_of(rows, "W0", "A", "watchful_no_restore") == 0.0


def test_w0_committed_static_rule_fails_linearly():
    rows = run_matrix(("association_commit",))
    # association_commit never watches: even uncensored evidence is ignored
    assert slope_of(rows, "W0", "K", "association_commit") > 0.9 * SLOPE
    assert slope_of(rows, "W0", "A", "association_commit") == 0.0


def test_w2_self_confirming_linear_regret():
    rows = run_matrix(("watchful_no_restore", "association_commit"))
    for policy in ("watchful_no_restore", "association_commit"):
        # censoring: evidence stops arriving -> wrong archive never corrected
        assert slope_of(rows, "W2", "K", policy) > 0.9 * SLOPE
        assert slope_of(rows, "W2", "A", policy) == 0.0


def test_w1_uncensored_but_persistent_corrects():
    rows = run_matrix(("watchful_no_restore",))
    # persistent action + uncensored evidence: watchful rule corrects
    assert slope_of(rows, "W1", "K", "watchful_no_restore") < 0.3


def test_w3_restore_channel_plateaus():
    rows = run_matrix(("watchful_restore", "watchful_no_restore"), ("W3",))
    # restore channel re-opens the stream at a cost -> plateau
    assert slope_of(rows, "W3", "K", "watchful_restore") < 0.9 * SLOPE
    # same policy WITHOUT the channel (W2) is linear -- the channel is the
    # causal lever, not the policy
    rows2 = run_matrix(("watchful_restore",), ("W2",))
    assert slope_of(rows2, "W2", "K", "watchful_restore") > 0.9 * SLOPE


def test_w0_w2_contrast_paired():
    """Same watchful policy: W0 corrects, W2 self-confirms.  The reduction
    separation at the policy level (14- §7.2)."""
    rows = run_matrix(("watchful_no_restore",), ("W0", "W2"))
    k0 = slope_of(rows, "W0", "K", "watchful_no_restore")
    k2 = slope_of(rows, "W2", "K", "watchful_no_restore")
    assert k2 - k0 > 0.9 * SLOPE


# ---------------------------------------------------------------------------
# Observational equivalence (Theorem 1 mechanism)
# ---------------------------------------------------------------------------


def test_observational_equivalence_bit_identical():
    eq = observational_equivalence(seed=5)
    assert eq["bit_identical"] is True
    assert eq["max_field_diff"] == 0.0
    # opposite lifecycle values on identical logs
    assert eq["K_lifecycle_value_per_step"] == 6.0
    assert eq["A_lifecycle_value_per_step"] == -6.0


# ---------------------------------------------------------------------------
# Self-confirming comparison (14- §7.3)
# ---------------------------------------------------------------------------


def test_self_confirming_no_restore_linear():
    rows = run_matrix(("no_probe_commit", "local_causal_commit",
                       "gate_no_probe", "gate_keep_default"), ("W3",))
    for policy in ("no_probe_commit", "local_causal_commit", "gate_no_probe",
                   "gate_keep_default"):
        assert slope_of(rows, "W3", "K", policy) > 0.9 * SLOPE
        assert slope_of(rows, "W3", "A", policy) < 0.05


def test_self_confirming_restore_rules_plateau():
    rows = run_matrix(("fixed_prob_restore", "uncertainty_triggered_restore",
                       "cost_aware_commit_defer_probe"), ("W3",))
    for policy in ("fixed_prob_restore", "uncertainty_triggered_restore",
                   "cost_aware_commit_defer_probe"):
        assert slope_of(rows, "W3", "K", policy) < 0.9 * SLOPE, policy
        assert slope_of(rows, "W3", "A", policy) < 0.1, policy


def test_restore_rules_pay_cost_or_probe():
    """Restore rules must pay for the channel (c_probe/c_restore) -- the
    plateau is not free; the channel cost is part of the tradeoff."""
    rows = run_matrix(("fixed_prob_restore", "uncertainty_triggered_restore",
                       "cost_aware_commit_defer_probe"), ("W3",))
    for policy in ("fixed_prob_restore", "uncertainty_triggered_restore",
                   "cost_aware_commit_defer_probe"):
        cost = (rows[f"W3_K_{policy}"]["probe_cost"]["mean"]
                + rows[f"W3_K_{policy}"]["restore_cost"]["mean"])
        assert cost > 0.0, policy


def test_gate_keep_default_commits_confounded_prior():
    """The keep-default gate archives in K because the confounded early
    signal is statistically resolved-negative (CI excludes 0) -- the
    resolution itself is the trap, not an estimation failure."""
    rows = run_matrix(("gate_keep_default",), ("W3",))
    cell = rows["W3_K_gate_keep_default"]
    assert cell["per_step_slope"]["mean"] > 0.9 * SLOPE
    assert cell["correction_time"]["mean"] > 0.9 * 2000  # never corrected


# ---------------------------------------------------------------------------
# Reduction controls (14- §7.2)
# ---------------------------------------------------------------------------


def _controls():
    cells = {
        ("static_bandit_ucb", "W0"): [], ("contextual_bandit", "W0"): [],
        ("standard_ope", "W1"): [], ("standard_ope", "W2"): [],
        ("bandit_ucb", "W1"): [], ("bandit_ucb", "W2"): [],
    }
    for (policy, label), rows in cells.items():
        for seed in range(SEED0, SEED0 + N_SEEDS):
            cfg = config_for(seed, "K", label)
            rows.append(run_policy(build_world(cfg), policy))
    out = {}
    for (policy, label), rows in cells.items():
        out[f"{label}_{policy}"] = sum(r["regret_T"] for r in rows) \
            / (len(rows) * 2000)
    return out


def test_standard_machinery_succeeds_w0_w1():
    c = _controls()
    assert c["W0_static_bandit_ucb"] < 0.3
    assert c["W0_contextual_bandit"] < 0.3
    assert c["W1_standard_ope"] < 0.3
    assert c["W1_bandit_ucb"] < 0.3


def test_standard_machinery_fails_w2():
    c = _controls()
    assert c["W2_standard_ope"] > 0.9 * SLOPE  # overlap broken by censoring
    assert c["W2_bandit_ucb"] > 0.9 * SLOPE     # candidate exploration dead


# ---------------------------------------------------------------------------
# Structural ablation full run + paired bootstrap smoke
# ---------------------------------------------------------------------------


def test_full_ablation_paired_bootstrap_ci_excludes_zero():
    """Headline contrasts must be significant under the paired seed
    bootstrap (sampling unit = seed)."""
    ablation = structural_ablation(n_seeds=N_SEEDS, seed0=SEED0)
    assert ablation["W2_K_watchful_no_restore"]["per_step_slope"]["mean"] \
        > 0.9 * SLOPE
    assert ablation["W1_K_watchful_no_restore"]["per_step_slope"]["mean"] \
        < 0.3
    assert ablation["W3_K_watchful_restore"]["per_step_slope"]["mean"] \
        < 0.9 * SLOPE

    raw = []
    for label in ("W0", "W1", "W2", "W3"):
        for seed in range(SEED0, SEED0 + N_SEEDS):
            for world_name in ("K", "A"):
                cfg = config_for(seed, world_name, label)
                world = build_world(cfg)
                for policy in ("association_commit", "watchful_no_restore",
                               "watchful_restore"):
                    row = run_policy(world, policy)
                    row["world_label"] = label
                    raw.append(row)
    for seed in range(SEED0, SEED0 + N_SEEDS):
        for world_name in ("K", "A"):
            cfg = config_for(seed, world_name, "W3")
            world = build_world(cfg)
            for policy in AUTO_ARCHIVED_POLICIES + ("gate_keep_default",):
                row = run_policy(world, policy)
                row["world_label"] = "W3"
                raw.append(row)
    pairs = (
        ("w2_vs_w1", "W2", "K", "watchful_no_restore",
         "W1", "K", "watchful_no_restore"),
        ("restore_vs_no_channel", "W3", "K", "watchful_restore",
         "W2", "K", "watchful_restore"),
        ("sc_no_probe_vs_fixed", "W3", "K", "no_probe_commit",
         "W3", "K", "fixed_prob_restore"),
    )
    boot = paired_bootstrap(raw, pairs, n_boot=200)
    for name, result in boot.items():
        ci = result["slope_diff"]
        assert ci["ci_low"] * ci["ci_high"] > 0.0, name  # CI excludes 0


def test_policy_sets_consistent():
    assert "uncertainty_triggered_restore" in AUTO_ARCHIVED_POLICIES
    assert "gate_keep_default" in DECISION_POLICIES
    assert len(set(AUTO_ARCHIVED_POLICIES) & set(DECISION_POLICIES)) == 0
