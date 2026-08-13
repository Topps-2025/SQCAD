"""Tests for unified_baseline_runner — Gate 1 M1 migration contract.

The shared contract must be airtight (same stream, same evaluator, same
budget for every policy), the transports must behave as their paper rules
prescribe, and the two-table split must be honest (not_transportable rows
never carry numbers, simplified transports are labeled proxy).
"""

import pytest

from src.sqcad.unified_baseline_runner import (
    BASELINE_SPECS, UNIFIED_METRICS,
    run_policy_unified, build_original_protocol_table, summarize_main_table,
)

BUDGET = 12
STEPS = 100


def _row(policy: str, seed: int = 0) -> dict:
    return run_policy_unified(seed, policy, 0.2, STEPS, BUDGET)


class TestSharedContract:
    def test_all_policies_receive_the_identical_stream(self):
        hashes = {_row(p)["candidate_stream_sha256"]
                  for p in BASELINE_SPECS
                  if BASELINE_SPECS[p]["transportability"]
                  != "not_transportable"}
        assert len(hashes) == 1

    def test_decision_logs_complete_for_every_policy(self):
        for p in BASELINE_SPECS:
            if BASELINE_SPECS[p]["transportability"] == "not_transportable":
                continue
            assert _row(p)["decision_log_completeness"] == 1.0, p


class TestSimpleControls:
    def test_no_memory_zero_tokens_zero_recall(self):
        row = _row("no_memory")
        assert row["average_workspace_tokens"] == 0.0
        assert row["required_evidence_recall"] < 0.25  # only 'none' tasks

    def test_keep_all_prices_the_context_cost(self):
        """keep-all exceeds the budget BY DESIGN; its token cost is the
        no-governance price and it exposes stale memories."""
        row = _row("keep_all")
        mean_token = 24.5  # 20 + randrange(21) mean
        assert row["average_workspace_tokens"] > BUDGET * mean_token * 3
        assert row["stale_exposure_rate"] == 1.0
        assert row["required_evidence_recall"] == 1.0

    def test_fifo_is_not_trivially_optimal(self):
        """Regression guard: the stream's write order is shuffled, so FIFO
        (write-order retention) is a random-budget control, not a ceiling."""
        row = _row("fifo")
        assert row["average_utility"] < 0.9
        assert row["rare_critical_recall"] < 0.9

    def test_recency_retains_stale_recent_memories(self):
        """The stream's realistic design: the most recent memories are the
        stale ones, so recency-style governance exposes them."""
        row = _row("recency")
        assert row["stale_exposure_rate"] == 1.0
        assert row["rare_critical_recall"] == 0.0

    def test_retrieval_controls_have_no_persistent_governance(self):
        for p in ("bm25", "dense", "rrf"):
            row = _row(p)
            assert row["archives"] == 0.0
            assert row["restores"] == 0.0
            assert row["probes"] == 0.0

    def test_rrf_fuses_bm25_and_dense(self):
        rrf = _row("rrf")
        bm25 = _row("bm25")
        dense = _row("dense")
        # fusion beats the noisier single retrievers on stale exposure
        assert rrf["stale_exposure_rate"] <= bm25["stale_exposure_rate"]
        assert rrf["stale_exposure_rate"] <= dense["stale_exposure_rate"]


class TestGovernanceTransports:
    def test_memory_worth_associational_signal_trusts_stale(self):
        """The paper's success signal is explicitly associational; on this
        stream stale memories have high observed success, so Memory Worth
        retains them (the failure the review asks us to keep visible)."""
        row = _row("memory_worth")
        assert row["stale_exposure_rate"] == 1.0
        assert row["archives"] == 32.0 - BUDGET

    def test_dynamic_decay_policies_refresh_on_exposure(self):
        for p in ("oblivion", "fademem"):
            row = _row(p)
            assert row["restores"] > 0.0  # re-admission after eviction

    def test_static_governance_archives_the_below_budget_tail(self):
        for p in ("recency", "fixed_decay", "frequency_decay",
                  "memory_worth", "simplemem", "demem", "causal_item",
                  "trivium", "risk_gated_decomp_abstract"):
            row = _row(p)
            assert row["archives"] == 32.0 - BUDGET, p

    def test_demem_preserves_distinctions_drops_neutral(self):
        row = _row("demem")
        assert row["rare_critical_recall"] > 0.5  # rare kept (distinct)


class TestClosestTheory:
    def test_causal_item_suffers_unidentified_rare_items(self):
        """CMI-style item effect: 75% of rare items are unidentified in the
        stream (item_effect_lcb = -inf), so the local-effect-only strategy
        drops them."""
        row = _row("causal_item")
        assert row["rare_critical_recall"] < 0.5
        assert row["stale_exposure_rate"] == 0.0

    def test_trivium_regret_weighting_keeps_rare(self):
        row = _row("trivium")
        assert row["rare_critical_recall"] > 0.5

    def test_sqcad_group_fallback_rescues_rare_items(self):
        causal = _row("causal_item")
        gated = _row("risk_gated_decomp_abstract")
        assert gated["rare_critical_recall"] > causal["rare_critical_recall"]
        assert gated["stale_exposure_rate"] == 0.0
        # and at no token premium
        assert gated["average_workspace_tokens"] <= \
            causal["average_workspace_tokens"] * 1.05


class TestTwoTables:
    def test_not_transportable_rows_carry_no_numbers(self):
        spec = BASELINE_SPECS
        not_transportable = [p for p, s in spec.items()
                             if s["transportability"] == "not_transportable"]
        assert set(not_transportable) == {"sage", "memaudit", "gatemem"}
        # their engines do not exist: no numbers can be produced for them
        for p in not_transportable:
            with pytest.raises(KeyError):
                run_policy_unified(0, p, 0.2, STEPS, BUDGET)

    def test_original_protocol_table_honest_verdicts(self):
        table = build_original_protocol_table()
        by_policy = {r["policy"]: r for r in table}
        assert by_policy["sage"]["verdict"] == "not reproduced"
        assert by_policy["oblivion"]["verdict"] == "not reproduced"
        assert "not reproduced" in by_policy["simplemem"]["verdict"]
        assert by_policy["memory_worth"]["verdict"] == "not reproduced"
        assert BASELINE_SPECS["fademem"]["transportability"] == "proxy"
        # controls are internal, not reproductions
        assert by_policy["recency"]["verdict"] == "internal control"

    def test_main_table_splits_transportability(self):
        rows = [_row(p) for p in BASELINE_SPECS
                if BASELINE_SPECS[p]["transportability"] != "not_transportable"]
        table = summarize_main_table(rows, seeds=1)
        assert "not_transportable_rows" in table["contract"]
        assert "sage" in table["contract"]["not_transportable_rows"]
        # every row in the main table carries the full metric set
        for p, r in table["rows"].items():
            assert set(r["metrics"]) == set(UNIFIED_METRICS)
