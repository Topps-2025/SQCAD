"""Tests for cost_contract_experiment — Gate 4 net-benefit contract.

The contract arithmetic must be exact (golden values), the probe layer must
charge only qualification-time probes of the framework-family policies, the
probe budget must buy rare-critical protection, and the forced-decision
controls (the KEPT negative lifecycle-restore result) must collapse in value
or in harm while the gated framework stays intact.
"""

from statistics import mean

import pytest

from src.sqcad.cost_contract_experiment import (
    DEFAULT_COEF, aggregate, break_even, cost_components, cost_value,
    efficiency, run_episode, variant_episode,
)
from src.sqcad.unified_baseline_runner import run_policy_unified

BUDGET = 12
STEPS = 60
SEEDS = 5


def _episode(policy: str, probe_budget: int, seed: int = 0,
             variant: bool = False, steps: int = STEPS):
    episode = variant_episode(seed, 0.2, steps) if variant else None
    rows: list = []
    row = run_policy_unified(seed, policy, 0.2, steps, BUDGET,
                             probe_budget=probe_budget, collect_rows=rows,
                             episode=episode)
    return row, rows


def _v_mean(policy: str, probe_budget: int, seeds: int = SEEDS,
            variant: bool = False) -> float:
    values = []
    for seed in range(seeds):
        row, rows = _episode(policy, probe_budget, seed=seed, variant=variant)
        values.append(cost_value(rows, DEFAULT_COEF,
                                 float(row["rare_kept_final"])))
    return mean(values)


def _stale_mean(policy: str, probe_budget: int, seeds: int = SEEDS,
                variant: bool = False) -> float:
    return mean(_episode(policy, probe_budget, seed=seed, variant=variant)[0]
                ["stale_exposure_rate"] for seed in range(seeds))


class TestContractArithmetic:
    def test_golden_cost_value(self):
        rows = [
            {"utility": 1.0, "tokens": 100.0, "probes": 2.0,
             "n_exposed": 10.0, "stale": 0.0},
            {"utility": 0.0, "tokens": 50.0, "probes": 0.0,
             "n_exposed": 5.0, "stale": 1.0},
        ]
        v = cost_value(rows, DEFAULT_COEF, rare_kept_final=3.0)
        # utility 1.0 - tokens 0.1495 - probes 0.1 - latency 0.0299
        # - harm 0.3465 - ff 0.25
        assert v == pytest.approx(0.1241, abs=1e-9)

    def test_components_decompose_exactly(self):
        rows = [
            {"utility": 1.0, "tokens": 100.0, "probes": 2.0,
             "n_exposed": 10.0, "stale": 0.0},
            {"utility": 0.0, "tokens": 50.0, "probes": 0.0,
             "n_exposed": 5.0, "stale": 1.0},
        ]
        comps = cost_components(rows, DEFAULT_COEF, rare_kept_final=3.0)
        charged = (comps["utility"] - comps["tokens"] - comps["probes"]
                   - comps["latency"] - comps["harm"] - comps["ff"])
        assert charged == pytest.approx(
            cost_value(rows, DEFAULT_COEF, rare_kept_final=3.0), abs=1e-12)
        assert comps["n_probes"] == pytest.approx(2.0)  # step-0 only

    def test_ff_charges_unprotected_rare_memories(self):
        rows = [{"utility": 1.0, "tokens": 0.0, "probes": 0.0,
                 "n_exposed": 0.0, "stale": 0.0}]
        full = cost_value(rows, DEFAULT_COEF, rare_kept_final=4.0)
        empty = cost_value(rows, DEFAULT_COEF, rare_kept_final=0.0)
        assert full - empty == pytest.approx(DEFAULT_COEF["rho_ff"] * 4.0)

    def test_efficiency_guard_for_zero_tokens(self):
        assert efficiency([]) == 0.0
        row, rows = _episode("no_memory", 0)
        assert row["average_workspace_tokens"] == 0.0
        assert efficiency(rows) == 0.0


class TestProbeLayer:
    def test_probes_charged_at_step_zero_only(self):
        rows: list = []
        row = run_policy_unified(0, "risk_gated_decomp_abstract", 0.2,
                                 STEPS, BUDGET, probe_budget=8,
                                 collect_rows=rows)
        assert row["probes"] > 0.0
        assert rows[0]["probes"] == pytest.approx(row["probes"])
        assert all(r["probes"] == 0.0 for r in rows[1:])
        assert len(rows) == STEPS
        assert [r["step"] for r in rows] == list(range(STEPS))

    def test_non_probing_policies_never_pay_probes(self):
        for policy in ("no_memory", "keep_all", "recency", "bm25", "demem",
                       "memory_worth"):
            row, rows = _episode(policy, probe_budget=8)
            assert row["probes"] == 0.0, policy
            assert all(r["probes"] == 0.0 for r in rows), policy

    def test_forced_controls_never_probe(self):
        for policy in ("blind_gate", "forced_restore"):
            row, rows = _episode(policy, probe_budget=8)
            assert row["probes"] == 0.0, policy

    def test_probe_budget_buys_rare_protection_for_framework(self):
        kept = [0.0, 0.0]
        for seed in range(SEEDS):
            for i, pb in enumerate((0, 8)):
                row, _ = _episode("risk_gated_decomp_abstract", pb, seed=seed)
                kept[i] += row["rare_kept_ever"]
        # probing resolves unidentified rare items: never worse, better in
        # expectation (mislabeled rare items are recovered)
        assert kept[1] >= kept[0]

    def test_probe_budget_resolves_causal_item_gap(self):
        """Without probes, causal_item archives every unidentified item
        (point estimate -1e6); the probe contract resolves them."""
        recall = []
        for pb in (0, 8):
            recall.append(mean(
                _episode("causal_item", pb, seed=seed)[0]
                ["rare_critical_recall"] for seed in range(SEEDS)))
        assert recall[0] < 0.6          # most rare items unidentified
        assert recall[1] > recall[0] + 0.3

    def test_collect_rows_share_the_contract_quantities(self):
        row, rows = _episode("keep_all", 0, seed=2)
        assert row["average_workspace_tokens"] == pytest.approx(
            mean(r["tokens"] for r in rows))
        assert row["stale_exposure_rate"] == 1.0


class TestForcedNegativeResult:
    """The KEPT negative lifecycle-restore result: forcing the persistent
    access decision where identification failed collapses value (standard
    world) or harm (variant world); the gated framework refuses instead."""

    def test_blind_gate_collapses_value_in_standard_world(self):
        # blind_gate decides from the raw point estimate of unidentified
        # items: rare critical memories are archived.  Task hits are
        # group-level, so the cost shows as lost rare protection (recall
        # 0.25 vs 1.0), a 4x low-frequency-protection fee and ~3 units of
        # net benefit; the harm collapse is forced_restore's job in the
        # variant world (below)
        assert _v_mean("blind_gate", 0) < _v_mean(
            "risk_gated_decomp_abstract", 8) - 2.0

    def test_blind_gate_is_the_probe_free_causal_policy(self):
        # the forced point-decision control is EXACTLY the CMI-style
        # local-causal policy without its qualification probe: identical
        # episodes under the shared contract (same stream, same evaluator)
        blind, _ = _episode("blind_gate", 0, seed=3)
        causal, _ = _episode("causal_item", 0, seed=3)
        for key in ("task_success_rate", "average_utility",
                    "rare_critical_recall", "stale_exposure_rate",
                    "average_workspace_tokens"):
            assert blind[key] == causal[key], key

    def test_variant_world_contains_unidentified_harm(self):
        total = 0
        for seed in range(SEEDS):
            candidates, _ = variant_episode(seed, 0.2, STEPS)
            total += sum(
                1 for c in candidates
                if c.true_group == "stale" and c.item_effect_lcb <= -1e5)
        assert total > 3  # p=0.75 over 8 stale items x 5 seeds: E ~= 30

    def test_forced_restore_collapses_harm_in_variant_world(self):
        # when harmful items are unidentified, "when in doubt, keep"
        # restores them into the workspace every step
        assert _stale_mean("forced_restore", 0, variant=True) > 0.5
        assert _stale_mean("forced_restore", 0, variant=True) > \
            _stale_mean("risk_gated_decomp_abstract", 8, variant=True) + 0.3
        assert _v_mean("forced_restore", 0, variant=True) < \
            _v_mean("risk_gated_decomp_abstract", 8, variant=True) - 5.0

    def test_gated_framework_stays_intact_in_variant_world(self):
        # the gate refuses (probe or unresolved) rather than deciding:
        # no harm collapse in either world
        assert _stale_mean("risk_gated_decomp_abstract", 8,
                           variant=True) < 0.1
        assert _v_mean("risk_gated_decomp_abstract", 8) - _v_mean(
            "risk_gated_decomp_abstract", 8, variant=True) < 10.0

    def test_variant_stream_shared_across_policies(self):
        hashes = set()
        for policy in ("risk_gated_decomp_abstract", "forced_restore",
                       "causal_item"):
            row, _ = _episode(policy, 4, seed=1, variant=True)
            hashes.add(row["candidate_stream_sha256"])
        assert len(hashes) == 1
        standard, _ = _episode("risk_gated_decomp_abstract", 4, seed=1)
        assert standard["candidate_stream_sha256"] not in hashes


class TestBreakEven:
    def test_break_even_structure(self):
        table = aggregate(
            ["risk_gated_decomp_abstract", "causal_item", "trivium",
             "memory_worth"], seeds=3, probe_budget=4)
        be = break_even(table, "risk_gated_decomp_abstract", 4)
        assert be["best_baseline"] in ("causal_item", "trivium",
                                       "memory_worth")
        # lead at zero probe price: framework ahead or (at 3 seeds) tied
        assert be["lead_V_at_zero_probe_price"] >= -0.5
        # no finite star when the best baseline probes as much as the
        # framework; positive star against a non-probing baseline
        assert be["lambda_probe_star"] is None or be["lambda_probe_star"] >= 0.0
        assert be["best_non_probing_baseline"] is not None
        assert be["lambda_probe_star_vs_non_probing"] > 0.0

    def test_break_even_monotone_in_probe_demand(self):
        """The explicit formula: V(fw, lam) - V(best, lam) is linear in lam
        with slope (n_best - n_fw).  Verify the stored numbers satisfy the
        identity used to derive lambda_probe*."""
        table = aggregate(
            ["risk_gated_decomp_abstract", "causal_item", "trivium",
             "memory_worth"], seeds=2, probe_budget=8)
        be = break_even(table, "risk_gated_decomp_abstract", 8)
        fw = table["risk_gated_decomp_abstract"]["regimes"]["default"]
        best = table[be["best_baseline"]]["regimes"]["default"]
        n_fw, n_best = fw["n_probes"], best["n_probes"]
        lead = (fw["V"] + DEFAULT_COEF["lam_probe"] * (n_fw - n_best)
                - best["V"])
        assert lead == pytest.approx(be["lead_V_at_zero_probe_price"])
