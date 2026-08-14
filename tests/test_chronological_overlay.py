"""Chronological overlay tests (doc 19-): injection validity, label
correctness, chronology, and the exposure-semantics evaluator."""

from pathlib import Path

import pytest

from src.sqcad.chronological_overlay import (
    OverlaidTrace, evaluate_overlay, inject_overlay, set_qa_answers,
)
from src.sqcad.public_unified_contract import run_policy, trace_features
from src.sqcad.trace_grounded_runner import (
    Trace, TraceMsg, TraceTask, clean_tokens, load_locomo,
)

LOCOMO = Path("D:/Engineering/SQCAD/database/datasets/LoCoMo/locomo10.json")


def _msg(mid: str, sid: str, idx: int, text: str) -> TraceMsg:
    return TraceMsg(mid, sid, str(idx), idx, "user", text, clean_tokens(text))


def _tiny() -> Trace:
    msgs = [
        _msg("D1:1", "session_1", 0,
             "caroline went to the support group on 7 may 2023"),
        _msg("D1:2", "session_1", 1, "she met alex there and talked"),
        _msg("D2:1", "session_2", 2, "caroline and alex went to a concert"),
        _msg("D3:1", "session_3", 3, "they planned a trip to paris"),
        _msg("D3:2", "session_3", 4, "the trip was booked for june"),
        _msg("D4:1", "session_4", 5, "they visited the louvre on day one"),
        _msg("D4:2", "session_4", 6, "then they walked along the seine"),
        _msg("D5:1", "session_5", 7, "they flew back home on sunday"),
        _msg("D5:2", "session_5", 8, "and uploaded the trip photos"),
        _msg("D6:1", "session_6", 9, "the next week they started new jobs"),
    ]
    tasks = [TraceTask("c0:q0", "when did caroline go to the support group",
                       clean_tokens("when did caroline go to the support "
                                    "group"), ("D1:1",), "2", ""),
             TraceTask("c0:q1", "where did they plan to go",
                       clean_tokens("where did they plan to go"),
                       ("D3:1",), "1", "")]
    return Trace("c0", tuple(msgs), tuple(tasks))


@pytest.fixture(scope="module")
def locomo():
    if not LOCOMO.exists():
        pytest.skip("LoCoMo frozen asset missing")
    set_qa_answers(LOCOMO)
    return load_locomo(LOCOMO)


def test_injection_preserves_original_messages():
    tr = _tiny()
    over = inject_overlay(tr, n_per_type=2)
    original_ids = {m.msg_id for m in tr.msgs}
    assert original_ids <= {m.msg_id for m in over.trace.msgs}
    # date_idx stays chronological after injection
    idx = [m.date_idx for m in over.trace.msgs]
    assert idx == sorted(idx)
    assert over.meta["n_injected"] == len(over.trace.msgs) - len(tr.msgs)


def test_injection_is_deterministic():
    tr = _tiny()
    a = inject_overlay(tr, seed=7)
    b = inject_overlay(tr, seed=7)
    assert [m.content for m in a.trace.msgs] == \
        [m.content for m in b.trace.msgs]


def test_e1_update_shares_tokens_and_is_later():
    tr = _tiny()
    over = inject_overlay(tr, n_per_type=2)
    e1 = [e for e in over.events if e.event_type == "E1"]
    assert e1, "tiny fixture should produce at least one E1"
    by = {m.msg_id: m for m in over.trace.msgs}
    for e in e1:
        upd = by[e.update_id]
        anchor = by[e.needed_ids[0]]
        assert upd.date_idx > anchor.date_idx
        assert len(set(upd.tokens) & set(anchor.tokens)) >= 3


def test_e2_false_fact_contradicts_gold_and_correction_restores():
    tr = _tiny()
    from src.sqcad import chronological_overlay as co
    co._QA_ANSWER_CACHE["c0:q0"] = {"answer": "7 May 2023", "category": "2"}
    co._QA_ANSWER_CACHE["c0:q1"] = {"answer": "Paris", "category": "1"}
    over = inject_overlay(tr, n_per_type=2)
    e2 = [e for e in over.events if e.event_type == "E2"]
    assert e2, "tiny fixture should produce at least one E2"
    by = {m.msg_id: m for m in over.trace.msgs}
    for e in e2:
        gold = co._QA_ANSWER_CACHE[e.task_id]["answer"].lower()
        false = by[e.false_id].content.lower()
        corr = by[e.correction_id].content.lower()
        assert gold in corr                      # correction restores the gold
        assert f"not {gold}" in false            # false fact negates the gold
        assert by[e.false_id].date_idx < by[e.correction_id].date_idx


def test_evaluator_exposure_semantics():
    tr = _tiny()
    over = inject_overlay(tr, n_per_type=2)
    feats = trace_features(over.trace.msgs)
    res = run_policy("sqcad", over.trace, feats=feats)
    ev = evaluate_overlay(res, over.trace, over.events)
    assert set(ev["events"]) == {"E1", "E2", "E3", "E4", "E5"}
    for etype, o in ev["events"].items():
        assert 0.0 <= o["hit"] <= 1.0
        assert 0.0 <= o["harmful"] <= 1.0
        assert 0.0 <= o["rescue"] <= 1.0
        assert 0.0 <= o["false_forgetting"] <= 1.0


def test_keep_all_never_false_forgets_and_exposes_distractors():
    tr = _tiny()
    over = inject_overlay(tr, n_per_type=2)
    feats = trace_features(over.trace.msgs)
    res = run_policy("keep_all", over.trace, feats=feats)
    ev = evaluate_overlay(res, over.trace, over.events)
    assert ev["events"]["E5"]["false_forgetting"] == 0.0
    assert ev["events"]["E5"]["hit"] == 1.0
    # keep-all exposes everything -> evidence always present, so harmful
    # exposure (false fact AND no evidence) is structurally zero and
    # distractor exposure is zero by the same AND-semantics; the cost is
    # its full-context token bill
    assert ev["events"]["E2"]["harmful"] == 0.0
    assert ev["events"]["E3"]["harmful"] == 0.0


def test_smoke_full_locomo(locomo):
    tr = locomo[0]
    over = inject_overlay(tr)
    feats = trace_features(over.trace.msgs)
    res = run_policy("sqcad", over.trace, feats=feats)
    ev = evaluate_overlay(res, over.trace, over.events)
    assert ev["events"]["E5"]["n"] > 0
    assert over.meta["n_injected"] > 0
