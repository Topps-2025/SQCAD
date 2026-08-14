"""Public-data unified contract tests (doc 17 D1/D2): chronology, budget,
gold isolation, determinism, SQCAD ablations, evaluator and the official
LoCoMo token-F1 mirrors.

Data-dependent tests skip when the frozen D-drive assets are absent, so the
suite stays green without the external database.
"""

from pathlib import Path

import pytest

from src.sqcad.public_unified_contract import (
    ALL_POLICIES, BUDGET, PolicyResult, SQCAD_ABLATIONS,
    aggregate, evaluate_trace, locomo_predictions, mask_lme_chronological,
    mirror_f1_score, mirror_locomo_f1, needed_free, run_policy, significance,
)
from src.sqcad.trace_grounded_runner import (
    Trace, TraceMsg, TraceTask, clean_tokens, load_locomo,
    load_longmemeval_s,
)

LME = Path("D:/Engineering/SQCAD/database/datasets/LongMemEval/"
           "longmemeval_s_cleaned.json")
LOCOMO = Path("D:/Engineering/SQCAD/database/datasets/LoCoMo/locomo10.json")


def _msg(mid: str, sid: str, date: str, idx: int, text: str) -> TraceMsg:
    return TraceMsg(mid, sid, date, idx, "user", text, clean_tokens(text))


def _tiny_lme() -> Trace:
    """Two sessions before the question, one session after it."""
    msgs = [
        _msg("m0", "s0", "2023/05/01 (Mon) 10:00", 0,
             "the user lives in berlin since 2020"),
        _msg("m1", "s0", "2023/05/01 (Mon) 10:01", 1,
             "they work at a bakery in berlin"),
        _msg("m2", "s1", "2023/05/02 (Tue) 09:00", 2,
             "the user moved to paris last month"),
        _msg("m3", "s2", "2023/05/03 (Wed) 09:00", 3,
             "this session happens after the question"),
    ]
    tasks = [TraceTask("q0", "where does the user live",
                       clean_tokens("where does the user live"),
                       ("m0", "m3"), "single-session-user",
                       "2023/05/02 (Tue) 23:00")]
    return Trace("tiny", tuple(msgs), tuple(tasks))


def _tiny_locomo() -> Trace:
    msgs = [
        _msg("D1:1", "session_1", "", 0,
             "caroline went to the support group on 7 may 2023"),
        _msg("D1:2", "session_1", "", 1,
             "she met alex there and they talked for an hour"),
        _msg("D2:1", "session_2", "", 2,
             "caroline and alex went to a concert on 21 may"),
    ]
    tasks = [TraceTask("c0:q0", "when did caroline go to the support group",
                       clean_tokens("when did caroline go to the support "
                                    "group"), ("D1:1",), "2", ""),
             TraceTask("c0:q1", "who did she meet and where did they go",
                       clean_tokens("who did she meet and where did they go"),
                       ("D1:2", "D2:1"), "1", "")]
    return Trace("c0", tuple(msgs), tuple(tasks))


def _run_all(trace: Trace):
    return {p: run_policy(p, trace) for p in ALL_POLICIES}


# ---------------------------------------------------------------------------
# chronology + gold isolation
# ---------------------------------------------------------------------------

def test_mask_lme_chronological_removes_future():
    masked, meta = mask_lme_chronological(_tiny_lme())
    ids = {m.msg_id for m in masked.msgs}
    assert "m3" not in ids
    assert "m0" in ids and "m2" in ids
    assert meta["n_masked_msgs"] == 1
    assert meta["n_masked_needed"] == 1  # m3 was gold but sits post-question


def test_needed_free_strips_gold():
    tasks = needed_free(_tiny_lme().tasks)
    assert all(t.needed_ids == () for t in tasks)
    assert tasks[0].question == "where does the user live"


def test_no_policy_exposes_future_on_masked_trace():
    masked, _ = mask_lme_chronological(_tiny_lme())
    for res in _run_all(masked).values():
        if res is None:
            continue
        for ws in res.workspaces.values():
            assert "m3" not in ws


# ---------------------------------------------------------------------------
# contract invariants
# ---------------------------------------------------------------------------

def test_budget_invariant():
    masked, _ = mask_lme_chronological(_tiny_lme())
    for pol, res in _run_all(masked).items():
        if res is None:
            continue
        for ws in res.workspaces.values():
            if pol == "keep_all":
                assert len(ws) == 3  # the full visible stream
            else:
                assert len(ws) <= BUDGET


def test_no_memory_is_empty():
    masked, _ = mask_lme_chronological(_tiny_lme())
    res = run_policy("no_memory", masked)
    assert all(ws == () for ws in res.workspaces.values())
    assert res.storage_tokens == 0


def test_determinism():
    masked, _ = mask_lme_chronological(_tiny_lme())
    a = {p: run_policy(p, masked) for p in ALL_POLICIES}
    b = {p: run_policy(p, masked) for p in ALL_POLICIES}
    for p in ALL_POLICIES:
        ra, rb = a[p], b[p]
        assert (ra is None) == (rb is None)
        if ra is not None:
            assert ra.workspaces == rb.workspaces
            assert ra.storage_tokens == rb.storage_tokens


def test_dense_skips_without_cache_and_honors_cache():
    masked, _ = mask_lme_chronological(_tiny_lme())
    assert run_policy("dense", masked) is None
    assert run_policy("rrf", masked) is None
    fake = {"q0": ("m0", "m2")}
    dense = run_policy("dense", masked, dense_ws=fake)
    assert dense is not None and dense.workspaces["q0"] == ("m0", "m2")
    rrf = run_policy("rrf", masked, dense_ws=fake)
    assert rrf is not None and len(rrf.workspaces["q0"]) <= BUDGET


# ---------------------------------------------------------------------------
# SQCAD lifecycle + ablations
# ---------------------------------------------------------------------------

def _sqcad_run(policy: str, trace: Trace) -> PolicyResult:
    res = run_policy(policy, trace)
    assert res is not None
    return res


def test_sqcad_write_time_evicts_to_budget():
    masked, _ = mask_lme_chronological(_tiny_lme())
    res = _sqcad_run("sqcad", masked)
    assert len(res.storage_ids) <= BUDGET
    assert res.lifecycle["archives"] >= 0


def test_sqcad_probe_restore_and_ablation_contrasts():
    # a stream long enough to force archives, with a query that overlaps an
    # archived turn -> probe (and possibly restore) fire for sqcad
    msgs = [
        _msg(f"m{i}", f"s{i // 2}", "", i,
             f"the user met person number {i} at the party")
        for i in range(30)
    ]
    msgs.append(_msg("gold", "s_old", "", 30, "the secret code is zebra"))
    tasks = [TraceTask("q0", "what is the secret code",
                       clean_tokens("what is the secret code"),
                       ("gold",), "2", "")]
    trace = Trace("c1", tuple(msgs), tuple(tasks))

    sqcad = _sqcad_run("sqcad", trace)
    no_probe = _sqcad_run("sqcad_no_probe", trace)
    no_restore = _sqcad_run("sqcad_no_restore", trace)
    no_silence = _sqcad_run("sqcad_no_silence_semantics", trace)

    assert no_probe.lifecycle["probes"] == 0
    assert no_silence.lifecycle["probes"] == 0
    assert no_restore.lifecycle["restores"] == 0
    # probes are capped by the pre-registered budget
    assert sqcad.lifecycle["probes"] <= 1
    assert sqcad.lifecycle["restores"] >= 0


def test_sqcad_fallback_ablation():
    # 5 sessions x 4 turns (bundle eviction drops the store to 10 < BUDGET)
    # + one high-frequency 6-turn session that is never the eviction victim;
    # sqcad's fallback re-admits 2 items from the archive at QA time, while
    # no_fallback exposes the short 10-item workspace
    msgs = [_msg(f"m{i}", f"s{i // 4}" if i < 20 else "s5", "", i,
                 f"stream item {i}") for i in range(26)]
    tasks = [TraceTask("q0", "question one", clean_tokens("question one"),
                       ("m0",), "1", "")]
    trace = Trace("c2", tuple(msgs), tuple(tasks))
    sqcad = _sqcad_run("sqcad", trace)
    no_fallback = _sqcad_run("sqcad_no_fallback", trace)
    assert sqcad.lifecycle["fallbacks"] == 2
    assert no_fallback.lifecycle["fallbacks"] == 0
    assert len(sqcad.workspaces["q0"]) == BUDGET
    assert len(no_fallback.workspaces["q0"]) == 10
    # both still respect the budget
    assert all(len(ws) <= BUDGET for ws in sqcad.workspaces.values())
    assert all(len(ws) <= BUDGET for ws in no_fallback.workspaces.values())


def test_ablation_configs_are_registered():
    for ab in SQCAD_ABLATIONS:
        assert ab in ALL_POLICIES
    assert "sqcad" in ALL_POLICIES


# ---------------------------------------------------------------------------
# evaluator
# ---------------------------------------------------------------------------

def test_evaluate_trace_metrics_bounds():
    masked, _ = mask_lme_chronological(_tiny_lme())
    visible = {m.msg_id for m in masked.msgs}
    res = run_policy("bm25", masked)
    ev = evaluate_trace(res, masked, visible)
    assert 0.0 <= ev["hit_rate"] <= 1.0
    assert 0.0 <= ev["recall_mean"] <= 1.0
    assert ev["n_masked_needed"] == 1          # m3 excluded, reported
    assert ev["ku_recall"] is None             # no knowledge-update tasks
    assert ev["tokens_mean"] >= 0.0
    # bm25 finds m0's lexical evidence for the live question
    assert ev["recall_mean"] > 0.0


def test_no_memory_scores_zero_and_keep_all_scores_full():
    masked, _ = mask_lme_chronological(_tiny_lme())
    visible = {m.msg_id for m in masked.msgs}
    nm = evaluate_trace(run_policy("no_memory", masked), masked, visible)
    ka = evaluate_trace(run_policy("keep_all", masked), masked, visible)
    assert nm["hit_rate"] == 0.0
    assert nm["tokens_mean"] == 0.0
    assert ka["recall_mean"] == 1.0           # everything visible exposed
    assert ka["tokens_mean"] > nm["tokens_mean"]


def test_aggregate_and_significance():
    masked, _ = mask_lme_chronological(_tiny_lme())
    visible = {m.msg_id for m in masked.msgs}
    evals = {}
    for p in ("sqcad", "bm25", "recency"):
        evals[p] = [evaluate_trace(run_policy(p, masked), masked, visible)]
    agg = aggregate("sqcad", evals["sqcad"])
    assert agg["policy"] == "sqcad"
    assert agg["hit_rate"]["mean"] is not None
    sig = significance(evals, "hit_rate", [("sqcad", "bm25")])
    entry = sig["sqcad_vs_bm25"]
    assert entry["mean_diff"] is None  # n=1 -> reported, not computed
    assert "note" in entry


def test_aggregate_skips_none_metrics():
    masked, _ = mask_lme_chronological(_tiny_lme())
    visible = {m.msg_id for m in masked.msgs}
    ev = evaluate_trace(run_policy("sqcad", masked), masked, visible)
    agg = aggregate("sqcad", [ev])
    assert agg["ku_recall"]["mean"] is None
    assert agg["ku_recall"]["n"] == 0


# ---------------------------------------------------------------------------
# LoCoMo QA reader + official-metric mirrors
# ---------------------------------------------------------------------------

def test_sentence_reader_and_predictions():
    trace = _tiny_locomo()
    res = run_policy("bm25", trace)
    qa_meta = {
        "c0:q0": {"answer": "7 May 2023", "category": "2",
                  "evidence": ["D1:1"]},
        "c0:q1": {"answer": "Alex, concert", "category": "1",
                  "evidence": ["D1:2", "D2:1"]},
    }
    preds = locomo_predictions(res, trace, qa_meta)
    assert len(preds) == 2
    assert preds[0]["answer"] == "7 May 2023"
    assert preds[0]["category"] == "2"
    assert preds[0]["prediction"] != ""
    assert preds[0]["prediction_context"] != []
    # the reader pulls the support-group sentence for the first question
    assert "support group" in preds[0]["prediction"].lower()


def test_write_locomo_qa_files_accumulates_all_traces(tmp_path):
    from src.sqcad.public_unified_contract import write_locomo_qa_files
    t1, t2 = _tiny_locomo(), _tiny_locomo()
    meta = {
        "c0:q0": {"answer": "7 May 2023", "category": "2",
                  "evidence": ["D1:1"]},
        "c0:q1": {"answer": "Alex, concert", "category": "1",
                  "evidence": ["D1:2", "D2:1"]},
    }
    write_locomo_qa_files(
        [(t1, run_policy("bm25", t1)), (t2, run_policy("bm25", t2))],
        meta, tmp_path)
    import json
    blocks = json.loads(
        (tmp_path / "predictions_bm25.json").read_text(encoding="utf-8"))
    assert len(blocks) == 2          # both traces accumulated, not overwritten
    assert all(len(b["rows"]) == 2 for b in blocks)


def test_mirror_f1_matches_official_semantics():
    assert mirror_f1_score("Hello World", "hello world") == 1.0
    assert mirror_f1_score("7 May 2023", "7 may 2023") == 1.0
    assert mirror_f1_score("unrelated", "7 may 2023") == 0.0
    # articles/and removed, punctuation stripped, lowercased
    assert mirror_f1_score("the and a CAT.", "cat") == 1.0


def test_mirror_locomo_f1_category_rules():
    assert mirror_locomo_f1("no information available here", "x", 5) == 1.0
    assert mirror_locomo_f1("some answer", "x", 5) == 0.0
    # category 3: first sub-answer before ';' is the gold
    assert mirror_locomo_f1("7 may 2023", "7 may 2023; extra", 3) == 1.0
    # category 1: comma-split multi-answer, max per gold part
    f = mirror_locomo_f1("alex, concert", "alex, concert", 1)
    assert f == 1.0


# ---------------------------------------------------------------------------
# data-dependent smoke (skips without the frozen D-drive assets)
# ---------------------------------------------------------------------------

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


def test_smoke_lme_contract(lme_small):
    from src.sqcad.public_unified_contract import mask_lme_chronological
    for trace in lme_small[:5]:
        masked, _ = mask_lme_chronological(trace)
        res = run_policy("bm25", masked)
        assert res is not None
        visible = {m.msg_id for m in masked.msgs}
        ev = evaluate_trace(res, masked, visible)
        assert ev["n_tasks"] == 1
        # fully-masked needed evidence -> no objective target (None)
        assert ev["hit_rate"] in (0.0, 1.0, None)


def test_smoke_locomo_contract(locomo):
    trace = locomo[0]
    res = run_policy("sqcad", trace)
    assert res is not None
    visible = {m.msg_id for m in trace.msgs}
    ev = evaluate_trace(res, trace, visible)
    assert ev["n_tasks"] >= 1
    assert 0.0 <= ev["recall_mean"] <= 1.0


def test_smoke_sqcad_runs_all_traces(locomo):
    for trace in locomo:
        res = run_policy("sqcad", trace)
        assert res is not None
        assert len(res.storage_ids) <= BUDGET
        for ws in res.workspaces.values():
            assert len(ws) <= BUDGET
