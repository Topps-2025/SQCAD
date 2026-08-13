"""Gate 2.2/2.3 tests — injections, randomization counterfactuals, retrieval.

Small deterministic fixtures verify the estimator mechanics; the real-trace
tests skip when the frozen D-drive assets are absent.
"""

from pathlib import Path

import pytest

from src.sqcad.trace_grounded_runner import (
    Trace, TraceMsg, TraceTask, by_id, load_locomo, load_longmemeval_s,
)
from src.sqcad.trace_semisynthetic_benchmark import (
    GAMMA, LAMBDA_TOK, RHO_DILUTION, episodic_value, inject,
    inject_co_memory_competition, inject_hitchhiker, inject_rare_protective,
    inject_scope_shift, inject_stale_version, run_counterfactuals,
    run_retrieval_layer, summarize_condition,
)

LME = Path("D:/Engineering/SQCAD/database/datasets/LongMemEval/longmemeval_s_cleaned.json")
LOCOMO = Path("D:/Engineering/SQCAD/database/datasets/LoCoMo/locomo10.json")


def _tiny_trace() -> Trace:
    msgs = [TraceMsg(f"m{i}", f"s{i}", "d", i, "user", f"text {i}",
                     (f"tok{i}",)) for i in range(6)]
    tasks = [TraceTask("t0", "q", ("tok0",), ("m0",), "single", "d"),
             TraceTask("t1", "q", ("tok0",), ("m0", "m1"), "single", "d")]
    return Trace("tiny", tuple(msgs), tuple(tasks))


@pytest.fixture(scope="module")
def locomo():
    if not LOCOMO.exists():
        pytest.skip("LoCoMo frozen asset missing")
    return load_locomo(LOCOMO)


class TestEpisodicValue:
    def test_hit_payoff_and_dilution_penalty(self):
        toks = {"a": 1, "b": 1, "c": 1}
        v_hit = episodic_value(["a", "b"], ["a"], toks)
        v_miss = episodic_value(["a", "b"], ["z"], toks)
        assert v_hit > v_miss
        assert v_hit == pytest.approx(
            1.0 - RHO_DILUTION * 0.5 - LAMBDA_TOK * 2)
        assert v_miss == pytest.approx(
            0.0 - RHO_DILUTION * 1.0 - LAMBDA_TOK * 2)

    def test_empty_workspace_is_zero(self):
        assert episodic_value([], ["a"], {"a": 1}) == 0.0


class TestInjections:
    def test_hitchhiker_adds_never_needed_distractors(self, locomo):
        t = locomo[0]
        t2 = inject_hitchhiker(t, 1.0, 0)
        needed = {mid for task in t.tasks for mid in task.needed_ids}
        added = [m for m in t2.msgs if m.msg_id not in
                 {m.msg_id for m in t.msgs}]
        assert len(added) >= 2 * len(t.tasks)  # rate=1.0 -> 2 per task
        assert all(m.msg_id not in needed for m in added)
        assert all(m.msg_id.startswith(f"{t.sample_id}:hitch:") for m in added)

    def test_stale_version_keeps_old_needed_and_adds_update(self, locomo):
        t = locomo[0]
        t2 = inject_stale_version(t)
        for task, task2 in zip(t.tasks, t2.tasks):
            assert set(task.needed_ids) <= set(task2.needed_ids)
        updates = [m for m in t2.msgs if ":update:" in m.msg_id]
        assert len(updates) == sum(len(task.needed_ids) for task in t.tasks)

    def test_rare_protective_demotes_needed_to_front(self, locomo):
        t = locomo[0]
        t2 = inject_rare_protective(t, 0, 0)
        needed = {mid for task in t.tasks for mid in task.needed_ids}
        demoted = [m for m in t2.msgs if m.msg_id in needed and m.date_idx < 3]
        assert demoted  # at least some needed memories moved to the front

    def test_scope_shift_empties_some_needed_sets(self, locomo):
        t = locomo[0]
        t2 = inject_scope_shift(t, 0)
        assert any(not task.needed_ids for task in t2.tasks)  # dropped support

    def test_co_memory_competition_scales_budget(self, locomo):
        t2, scale = inject_co_memory_competition(locomo[0], 0.5)
        assert scale == 0.5
        assert t2 is locomo[0]          # stream unchanged; budget contracts

    def test_inject_dispatcher(self, locomo):
        t2, scale = inject(locomo[0], "co_memory_competition")
        assert scale == 0.5
        t3, scale3 = inject(locomo[0], "control")
        assert scale3 == 1.0 and t3 is locomo[0]
        with pytest.raises(KeyError):
            inject(locomo[0], "nope")


class TestCounterfactuals:
    def test_estimator_on_tiny_trace(self):
        """On a 2-task trace where m0 is needed by both tasks and m1 by one,
        the randomized protocol estimator must give both a positive lifecycle
        value and rank the twice-needed memory strictly above the once-needed
        one (monotonicity of the protocol-path estimator)."""
        t = _tiny_trace()
        res = run_counterfactuals(t, budget=2, engine="bm25", rounds=128,
                                  seed=3, memory_cap=6)
        assert res["m0"]["v_rct"] > 0.0
        assert res["m1"]["v_rct"] > 0.0
        assert res["m0"]["v_rct"] > res["m1"]["v_rct"]

    def test_support_n_equals_engine_exposure_count(self, locomo):
        from src.sqcad.trace_grounded_runner import engine_workspaces
        t = locomo[0]
        max_tasks = 100          # matches run_counterfactuals' truncation
        ws = engine_workspaces(t, 12, "bm25")
        res = run_counterfactuals(t, budget=12, engine="bm25", rounds=4,
                                  seed=0, memory_cap=8, max_tasks=max_tasks)
        for mid, r in res.items():
            engine_exposures = sum(
                1 for task in t.tasks[:max_tasks] if mid in ws[task.task_id][0])
            assert r["support_n"] == engine_exposures, mid

    def test_observational_estimator_unresolved_without_support(self, locomo):
        t = locomo[0]
        max_tasks = 100
        res = run_counterfactuals(t, budget=12, engine="bm25", rounds=4,
                                  seed=0, memory_cap=8, max_tasks=max_tasks)
        from src.sqcad.trace_grounded_runner import engine_workspaces
        ws = engine_workspaces(t, 12, "bm25")
        all_exposed = {mid for task in t.tasks[:max_tasks]
                       for mid in ws[task.task_id][0]}
        for mid, r in res.items():
            if r["support_n"] == 0:
                assert mid not in all_exposed
                assert r["v_obs"] != r["v_obs"]  # nan -> unresolved


class TestSummarize:
    def test_rates_unit_interval_and_totals(self, locomo):
        t = locomo[0]
        res = run_counterfactuals(t, 12, "bm25", 4, seed=0, memory_cap=8)
        s = summarize_condition(res)
        assert s["n_memories"] == float(len(res))
        assert 0.0 <= s["support_failure_rate"] <= 1.0
        assert s["n_support"] == sum(1 for r in res.values()
                                     if r["support_n"] > 0)
        assert abs(s["n_support"] / s["n_memories"]
                   - (1.0 - s["support_failure_rate"])) < 1e-9


class TestRetrievalLayer:
    def test_bm25_beats_random_and_recency(self):
        if not LME.exists() or not LOCOMO.exists():
            pytest.skip("frozen assets missing")
        lme = load_longmemeval_s(LME, 60)
        r = run_retrieval_layer(lme, k=12)
        assert r["bm25_recall_at_k"] > r["random_recall_at_k"]
        assert r["bm25_recall_at_k"] > r["recency_recall_at_k"]

    def test_locomo_bm25_strong(self, locomo):
        r = run_retrieval_layer(locomo, k=12)
        assert r["bm25_recall_at_k"] > 0.4
        assert r["random_recall_at_k"] < 0.1
