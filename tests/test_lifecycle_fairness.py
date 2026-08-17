"""Tests for the fairness audit suite (R1/R2/R3/R5 + baseline matrix).

These guard the audit TOOLS themselves (the audit RUNS are reported in
remote_results/lifecycle_audit/*.json and 23-).  Deterministic: all tests
run on small fixed episode subsets with fixed seeds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sqcad.lifecycle_bench import baselines as B
from sqcad.lifecycle_bench import frozen, world, evaluator
from sqcad.lifecycle_bench.audit import (
    FLIP_ROBUST_THRESHOLD, cached_episodes, frozen_override,
    metadata_shortcut_audit, sensitivity_audit,
)
from sqcad.lifecycle_bench.generator import build_episode
from sqcad.lifecycle_bench.independent_ref import differences, verify
from sqcad.lifecycle_bench.unseen import (
    R3_KNOBS, _knob_episodes, _replace_crowding_fillers, _shift_task_slot,
    run_audit,
)

RESULTS = Path("results/lifecycle_bench")


def _sample(n: int = 12) -> list:
    """Small deterministic episode sample, one per family bucket, drawn
    from the generator's own id scheme (so R2 rebuild paths match)."""
    from sqcad.lifecycle_bench.generator import all_episodes
    seen, out = set(), []
    for ep in all_episodes():
        key = f"{ep.world.family}/{ep.world.variant}"
        if key not in seen:
            seen.add(key)
            out.append(ep)
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------------------
# frozen_override
# ---------------------------------------------------------------------------
class TestFrozenOverride:
    def test_patch_and_restore(self):
        assert world.STORAGE_RATE == frozen.STORAGE_RATE == 0.01
        with frozen_override(storage_rate=0.02):
            assert world.STORAGE_RATE == 0.02
            assert evaluator.GAMMA == frozen.GAMMA  # untouched
        assert world.STORAGE_RATE == 0.01

    def test_unknown_key_raises(self):
        with pytest.raises(KeyError):
            with frozen_override(no_such_constant=1):
                pass

    def test_override_changes_outcome(self):
        ep = _sample(1)[0]
        from sqcad.lifecycle_bench.audit import outcome_of
        with frozen_override():
            out0, _ = outcome_of(ep)
        with frozen_override(gamma=0.1):
            out1, _ = outcome_of(ep)
        # heavy discounting must change at least the value magnitudes
        assert out0.lifecycle_value_keep != out1.lifecycle_value_keep


# ---------------------------------------------------------------------------
# R1 metadata shortcut
# ---------------------------------------------------------------------------
class TestR1:
    def test_audit_runs_on_built_dataset(self):
        if not (RESULTS / "public.jsonl").exists():
            pytest.skip("dataset not built")
        res = metadata_shortcut_audit(RESULTS)
        assert res["n"] == 1380
        assert sum(res["oracle_distribution"].values()) == 1380
        m = res["metadata_family_variant"]
        assert m["train_acc"] >= 0.9  # the shortcut is nearly perfect
        assert res["text_only"]["dev"]["acc"] is not None
        # pair ceiling: 15 pairs disagree -> max agreement 1 - 15/1380
        assert res["pair_ceiling"]["n_pairs"] == 15
        assert res["pair_ceiling"]["disagreeing_pairs"] == 15
        assert abs(res["pair_ceiling"]["max_oracle_agreement"]
                   - (1 - 15 / 1380)) < 1e-9


# ---------------------------------------------------------------------------
# R2 sensitivity
# ---------------------------------------------------------------------------
class TestR2:
    def test_sensitivity_on_sample(self):
        from sqcad.lifecycle_bench.audit import R2_PERTURBATIONS
        eps = _sample(12)
        res = sensitivity_audit(eps)
        n_expected = sum(len(v["values"]) for v in R2_PERTURBATIONS.values())
        assert len(res["runs"]) == n_expected == 31
        for r in res["runs"]:
            assert 0.0 <= r["flip_rate"] <= 1.0
            assert r["n_total"] == len(eps)
        assert res["verdict"] in ("robust", "mixed", "fragile")

    def test_harm_penalty_run_rebuilds(self):
        # only HARM_PENALTY forces a design-time rebuild; make sure that
        # path is exercised and stays consistent with the cache path
        eps = _sample(12)
        res = sensitivity_audit(eps)
        hp = [r for r in res["runs"] if r["constant"] == "harm_penalty"]
        assert len(hp) == 2 and all(r["rebuild"] for r in hp)

    def test_thresholds_are_sane(self):
        assert 0.0 < FLIP_ROBUST_THRESHOLD < 1.0


# ---------------------------------------------------------------------------
# R3 unseen mechanisms
# ---------------------------------------------------------------------------
class TestR3:
    def test_slot_shift_keeps_schedule(self):
        ep = build_episode(20260817, "self_obscuring", "crowding", "maya")
        spec = _shift_task_slot(ep.world, 8, 6)
        assert [it.slot for it in spec.future_items] == list(range(1, 11))
        moved = [it for it in spec.future_items if it.slot == 6
                 and it.task is not None and it.task.needed_fid]
        assert len(moved) == 1

    def test_crowding_filler_replacement(self):
        ep = build_episode(20260817, "self_obscuring", "crowding", "maya")
        n_before = sum(1 for m in ep.memories if m.spec.fid.startswith("f_med"))
        assert n_before == 16
        spec = _replace_crowding_fillers(ep.world, 12)
        n_after = sum(1 for m in spec.memories if m.fid.startswith("f_med"))
        assert n_after == 12

    def test_knob_episodes_have_unseen_entities(self):
        for fam, var in (("rare_bridge", "rescue_possible"),
                         ("hitchhiker_pair", "default")):
            eps = _knob_episodes((fam, var), "entity")
            assert len(eps) == 20
            for ep in eps:
                assert ep.memories[0].spec.entity not in (
                    "john", "jane", "daniel", "dana", "ethan", "emma",
                    "lucas", "lily", "maya", "mia", "oliver", "olivia")

    def test_knob_episodes_are_deterministic(self):
        a = _knob_episodes(("rare_bridge", "rescue_possible"), "slot_shift")
        b = _knob_episodes(("rare_bridge", "rescue_possible"), "slot_shift")
        assert [e.world.episode_id for e in a] == [e.world.episode_id for e in b]

    def test_full_audit_smoke(self):
        res = run_audit()
        assert len(res["cells"]) == 15
        assert res["knobs"] == list(R3_KNOBS)
        for cell, knobs in res["cells"].items():
            for knob in R3_KNOBS:
                s = knobs[knob]
                assert s["n"] == 20
                assert 0.0 <= s["oracle_agreement"] <= 1.0
                assert 0.0 <= s["advantage_persists"] <= 1.0
                if "pair_flip_confirmed" in s:
                    assert 0.0 <= s["pair_flip_confirmed"] <= 1.0

    def test_pair_slot_shift_is_pair_flip_confirmation(self):
        # the flip side is DESIGNED to disagree with the base label; the
        # correct transfer test is base=keep AND flip=archive on the same
        # public trace at the moved slot
        res = run_audit()
        s = res["cells"]["hitchhiker_pair/default"]["slot_shift"]
        assert s["pair_flip_confirmed"] == 1.0


# ---------------------------------------------------------------------------
# R5 independent implementation
# ---------------------------------------------------------------------------
class TestR5:
    def test_clean_room_matches_reference(self):
        for ep in _sample(12):
            diffs = differences(ep)
            assert diffs == [], f"{ep.world.episode_id}: {diffs}"

    def test_verify_reports_consistency(self):
        res = verify(_sample(6))
        assert res["checked"] == 6 and res["inconsistent"] == 0

    def test_differences_detects_a_deliberate_break(self):
        """Sanity: the checker really compares behavior (mutate one rule)."""
        import sqcad.lifecycle_bench.independent_ref as ir
        orig = ir.ind_certificate
        ir.ind_certificate = lambda ep, fid, scope: \
            world.CertificateRecord(fid, world.POSITIVE, "broken")
        try:
            diffs = differences(_sample(1)[0])
            assert diffs, "checker must detect a broken certificate"
        finally:
            ir.ind_certificate = orig


# ---------------------------------------------------------------------------
# baseline matrix
# ---------------------------------------------------------------------------
class TestBaselines:
    def test_decision_policies_run(self):
        eps = _sample(12)
        for name in B.DECISION_POLICIES:
            fn = B.DECISION_POLICIES[name]
            for ep in eps:
                a = fn(ep)
                assert a in ("keep", "archive"), name
                B.branch_value(ep, a)  # no exception

    def test_sqcad_cert_expected_signs(self):
        # version_update update_before: old version is conflict-marked ->
        # certificate UNRESOLVED(lineage) -> sqcad_cert KEEPs (loss case,
        # pre-registered), conflict variant archives
        ep = build_episode(20260817, "version_update", "update_before", "ethan")
        assert B.p_sqcad_cert(ep) == "keep"
        assert B.p_sqcad_cert_conflict(ep) == "archive"
        # harmful_stale correction_visible: NEGATIVE certificate -> archive
        ep2 = build_episode(20260817, "harmful_stale", "correction_visible",
                            "lucas")
        assert B.p_sqcad_cert(ep2) == "archive"

    def test_matrix_runs_and_has_oracle_bound(self):
        eps = _sample(12)
        hidden = {}
        from sqcad.lifecycle_bench.audit import outcome_of
        for ep in eps:
            out, _ = outcome_of(ep)
            hidden[ep.world.episode_id] = out
        mat = B.run_decision_matrix(eps, hidden)
        assert "oracle_policy" in mat["summary"]
        # the oracle bound must dominate every decision policy on regret
        for name in B.DECISION_POLICIES:
            assert mat["summary"]["oracle_policy"]["mean_regret"] <= \
                mat["summary"][name]["mean_regret"] + 1e-9

    def test_ablation_matrix_runs(self):
        eps = _sample(12)
        hidden = {}
        from sqcad.lifecycle_bench.audit import outcome_of
        for ep in eps:
            out, _ = outcome_of(ep)
            hidden[ep.world.episode_id] = out
        abl = B.run_ablation_matrix(eps, hidden)
        assert set(abl) == {"no_qualification", "no_censoring",
                            "no_restore", "no_lineage", "no_probe"}

    def test_bootstrap_diff(self):
        r = B.bootstrap_diff([1.0, 2.0, 3.0, 4.0], [0.5, 1.0, 2.0, 3.5],
                             n_boot=200, seed=7)
        assert r["diff_mean"] == pytest.approx(0.75)
        assert r["ci_lo"] < r["ci_hi"]

    def test_events_and_scope_policies(self):
        ep = build_episode(20260817, "scope_mismatch", "future_in_s2",
                           "oliver")
        assert B.p_scope_literal(ep) == "archive"
        ep2 = build_episode(20260817, "scope_mismatch", "future_in_s1",
                            "oliver")
        assert B.p_scope_literal(ep2) == "keep"
        # correction event overlaps the stale memory text -> archive
        ep3 = build_episode(20260817, "harmful_stale", "correction_visible",
                            "lucas")
        assert B.p_event_rule(ep3) == "archive"


# ---------------------------------------------------------------------------
# scoring harness
# ---------------------------------------------------------------------------
class TestScoring:
    def test_score_lifecycle_predictions(self, tmp_path):
        if not (RESULTS / "hidden.jsonl").exists():
            pytest.skip("dataset not built")
        hidden = [json.loads(l) for l in
                  (RESULTS / "hidden.jsonl").read_text(encoding="utf-8")
                  .splitlines()][:10]
        preds = tmp_path / "preds.csv"
        with open(preds, "w", encoding="utf-8", newline="") as f:
            f.write("episode_id,action\n")
            for h in hidden:
                f.write(f"{h['episode_id']},keep\n")
        import subprocess
        out = tmp_path / "score.json"
        subprocess.run([sys.executable, "tools/score_lifecycle_predictions.py",
                        "--predictions", str(preds), "--hidden",
                        str(RESULTS / "hidden.jsonl"), "--out", str(out)],
                       check=True)
        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["n"] == 10
