from __future__ import annotations

import json

from sqcad.faithful_baseline_reproduction import (
    BaselineEpisode,
    CMIProtocol,
    DeMemProtocol,
    GovMemProtocol,
    MemoryCandidate,
    MemoryWorthProtocol,
    TriviumProtocol,
)


def _candidates():
    return {
        "m1": MemoryCandidate("m1", "alpha", partition_key="p"),
        "m2": MemoryCandidate("m2", "beta", partition_key="p"),
        "risky": MemoryCandidate("risky", "danger", risk=True),
    }


def test_cmi_records_three_interventions_and_risk_veto():
    episodes = [BaselineEpisode("e1", candidate_ids=("m1", "risky"))]
    values = {
        ("", "no_memory"): 0.2,
        ("m1", "with_memory"): 0.9,
        ("m1", "perturbed_memory"): 0.8,
        ("risky", "with_memory"): 1.0,
        ("risky", "perturbed_memory"): 0.9,
    }
    result = CMIProtocol(utility_threshold=0.1, stability_threshold=0.0).run(
        episodes, _candidates(), lambda e, mid, condition: values[(mid, condition)])
    assert result.baseline == "cmi_official_protocol"
    assert len(result.decisions) == 2
    assert result.final_state["selected_by_episode"]["e1"] == ["m1"]
    assert result.decisions[0]["utility"] == 0.7
    assert result.decisions[1]["risk_veto"] is True


def test_memory_worth_uses_only_exposed_ids_and_prior_history():
    episodes = [
        BaselineEpisode("e1", exposed_ids=("m1",), success=True),
        BaselineEpisode("e2", exposed_ids=("m2",), success=False),
    ]
    result = MemoryWorthProtocol(alpha=0.0, beta=0.0).run(episodes, _candidates())
    assert result.decisions[0]["worth_before_outcome"] == {"m1": 0.0, "m2": 0.0, "risky": 0.0}
    assert result.decisions[1]["worth_before_outcome"]["m1"] == 1.0
    assert result.final_state["hits_plus"]["m1"] == 1
    assert result.final_state["hits_plus"]["m2"] == 0
    assert result.final_state["hits_minus"]["m2"] == 1
    assert result.final_state["hits_minus"]["m1"] == 0


def test_demem_refines_after_certified_decision_conflict():
    episodes = [
        BaselineEpisode("e1", exposed_ids=("m1",), decision_label="A"),
        BaselineEpisode("e2", exposed_ids=("m1",), decision_label="B",
                        conflict_feature="context"),
    ]
    result = DeMemProtocol().run(episodes, _candidates())
    assert result.status == "partial"
    assert result.final_state["conflict_log"][1]["certified_conflicts"] == ["p"]
    assert any("context" in key for key in result.final_state["partitions"])


def test_trivium_persists_log_and_separates_regrets():
    episodes = [BaselineEpisode(
        "e1", probe_candidates=("m1",),
        probe_observations={"m1": {"effect": 0.5, "outcome_regret": 1,
                                   "temporal_regret": 2, "epistemic_regret": 3}})]
    result = TriviumProtocol(probe_budget=1).run(episodes, _candidates())
    assert len(result.final_state["causal_log"]) == 1
    assert result.final_state["regret"] == {"outcome": 1.0, "temporal": 2.0, "epistemic": 3.0}


def test_govmem_is_write_time_and_has_review_queue():
    episodes = [BaselineEpisode("e1", write_evidence={
        "m1": {"support_ids": ["s1"]},
        "m2": {"counterevidence_ids": ["c1"]},
    })]
    result = GovMemProtocol().run(episodes, _candidates())
    assert result.final_state["promoted_ids"] == ["m1"]
    assert result.final_state["needs_review_ids"] == ["m2"]
    json.dumps(result.to_dict(), ensure_ascii=False)
