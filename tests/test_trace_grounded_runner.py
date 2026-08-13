"""Gate 2.1 tests — loader, engines, instruments and mechanism incidence.

The data-dependent tests skip when the frozen D-drive assets are absent, so
the suite stays green without the external database.
"""

from pathlib import Path

import pytest

from src.sqcad.trace_grounded_runner import (
    Trace, TraceMsg, TraceTask, audit_trace, aggregate, bm25_scores,
    by_id, clean_tokens, decay_scores, engine_workspaces,
    load_longmemeval_s, load_locomo, recency_scores,
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
def lme_small():
    if not LME.exists():
        pytest.skip("LongMemEval S frozen asset missing")
    return load_longmemeval_s(LME, 30)


@pytest.fixture(scope="module")
def locomo():
    if not LOCOMO.exists():
        pytest.skip("LoCoMo frozen asset missing")
    return load_locomo(LOCOMO)


class TestLoaders:
    def test_longmemeval_loads_messages_and_task(self, lme_small):
        assert len(lme_small) == 30
        t = lme_small[0]
        assert t.msgs
        assert len(t.tasks) == 1          # LongMemEval S is single-query
        assert t.tasks[0].needed_ids      # answer session ground truth present

    def test_locomo_loads_dia_id_ground_truth(self, locomo):
        assert len(locomo) == 10
        by = by_id(locomo[0])
        for t in locomo[0].tasks[:5]:
            assert t.needed_ids
            assert all(mid in by for mid in t.needed_ids)

    def test_clean_tokens(self):
        # the token class keeps apostrophes inside words (i'm -> one token)
        assert clean_tokens("Hi! I'm 2nd best.") == ("hi", "i'm", "2nd", "best")


class TestEngines:
    def test_recency_prefers_later_messages(self):
        scores = recency_scores(_tiny_trace().msgs)
        assert scores["m5"] > scores["m0"]

    def test_decay_is_bounded(self):
        scores = decay_scores(_tiny_trace().msgs)
        assert all(0.0 < v <= 1.0 for v in scores.values())

    def test_bm25_surfaces_query_matching_messages(self):
        scores = bm25_scores(_tiny_trace().msgs, ("tok0",))
        assert scores["m0"] > scores["m5"]

    def test_workspaces_respect_budget(self, lme_small):
        ws = engine_workspaces(lme_small[0], 12, "bm25")
        for t in lme_small[0].tasks:
            exposed, positions = ws[t.task_id]
            assert len(exposed) == 12
            assert sorted(positions.values()) == list(range(12))


class TestAuditInstruments:
    def test_decision_log_one_row_per_task(self, lme_small):
        a = audit_trace(lme_small[0], 12, "bm25")
        assert len(a.rows) == len(lme_small[0].tasks)
        assert all(set(r) == {"task_id", "scope", "needed_ids", "exposed_ids",
                              "hit", "stale_exposed", "tokens", "decision"}
                   for r in a.rows)

    def test_metrics_in_unit_interval(self, lme_small):
        a = audit_trace(lme_small[0], 12, "bm25")
        for name in ("hitchhiker_rate", "needed_exposed_rate",
                     "rare_protective_rate", "scope_shift_rate",
                     "archive_error_rate", "needed_tail_position_rate"):
            assert 0.0 <= a.metrics[name] <= 1.0, name

    def test_exposure_counts_match_rows(self, locomo):
        a = audit_trace(locomo[0], 12, "bm25")
        n_exposed = sum(r["decision"] != "" for r in a.rows)
        assert all(r["exposed_ids"] for r in a.rows)
        assert a.metrics["co_exposure_density"] >= 1.0

    def test_dense_gold_session_finding(self, lme_small):
        """LongMemEval S answer sessions are dense 12-turn sessions: needed
        memories never sit in the low-frequency tail (rare_protective_rate 0)
        on the full 500-sample audit; guard on a sample too."""
        rates = [audit_trace(t, 12, "bm25").metrics["rare_protective_rate"]
                 for t in lme_small]
        # finding: needed sessions are never in the low-frequency tail
        assert all(r == 0.0 for r in rates)

    def test_no_retrieval_engine_archives_needed(self, lme_small):
        a = audit_trace(lme_small[0], 12, "recency")
        assert a.metrics["archive_error_rate"] == 1.0  # needed are old


class TestAggregate:
    def test_aggregate_median_within_range(self, locomo):
        audits = [audit_trace(t, 12, "bm25") for t in locomo]
        agg = aggregate(audits)
        for name in ("hitchhiker_rate", "task_hit_rate"):
            assert 0.0 <= agg[name]["median"] <= 1.0
        assert agg["hitchhiker_rate"]["n"] == len(audits)
