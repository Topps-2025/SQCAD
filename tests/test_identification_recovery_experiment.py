"""Tests for identification_recovery_experiment — two-stage design (Theorem 3).

Stage 1: in the ideal identification environment the rollout estimator must
recover the known lifecycle values (bias ~= 0, honest CI coverage, confident
decisions match the oracle) while association / CMI / naive OPE fail on the
expected estimand mismatches.

Stage 2: each violated condition must make the qualification gate abstain
(unresolved / mismatch) rather than produce confident wrong decisions.
"""

import math
import pytest

from src.sqcad.identification_recovery_experiment import (
    ROLE_SHORT_TERM,
    World, WorldConfig,
    run_stage1, run_stage2, run_multi_seed,
    compute_oracle_values, compute_local_effects,
    estimate_sqcad_rct, qualification_status, run_gate_checks,
)

# Small config so the suite stays fast; structural assertions are
# size-independent (roles, unresolved set, gate abstention).
FAST = WorldConfig(n_epochs=60, n_trajectories=30, n_oracle=80,
                   n_source_steps=800, n_query_contexts=80,
                   n_memories=12, seed=7)


def _mem_ids(world: World):
    return [m.mem_id for m in world.memories]


# ---------------------------------------------------------------------------
# World structure
# ---------------------------------------------------------------------------

class TestWorldStructure:
    def test_role_counts(self):
        world = World(FAST)
        roles = [m.role for m in world.memories]
        assert roles.count("useful") == 3
        assert roles.count("short_term") == 2
        assert roles.count("bridge") == 2
        assert roles.count("harmful") == 2
        assert roles.count("neutral") == 3

    def test_spec_map_consistent(self):
        world = World(FAST)
        for m in world.memories:
            assert world.spec(m.mem_id) is world.spec_map[m.mem_id]

    def test_short_term_local_effect_positive_but_lifecycle_negative(self):
        """The Theorem-2 lesson, built into the world: short-term memories
        look good locally (positive query-local effect) yet cost lifecycle
        value via bridge crowding."""
        world = World(FAST)
        cfg = WorldConfig(**{**FAST.__dict__, "n_query_contexts": 2000})
        short = [m for m in world.memories if m.role == ROLE_SHORT_TERM]
        local = compute_local_effects(world, cfg)
        true_v = compute_oracle_values(world, cfg)
        for m in short:
            assert local[m.mem_id] > 0.05, m.mem_id
            assert true_v[m.mem_id] < -1.0, m.mem_id

    def test_pair_only_under_co_exposure(self):
        assert World(FAST).pair is None
        cfg = WorldConfig(**{**FAST.__dict__, "co_exposure": True})
        assert World(cfg).pair is not None


# ---------------------------------------------------------------------------
# Stage 1 — ideal identification environment
# ---------------------------------------------------------------------------

class TestStage1:
    def test_passes_with_default_config(self):
        """Gold test: default config, full criterion."""
        r = run_stage1()
        assert r["stage1_passes"], r["summary_verdict"]

    def test_bias_and_coverage_fast(self):
        # small-sample MC noise gives mean-bias sd ~1.5 at FAST sizes; the
        # strict |bias|<1.0 criterion is the default-config gold test below
        r = run_stage1(FAST)
        vr = r["value_recovery"]
        assert vr["bias"] is not None and abs(vr["bias"]) < 3.0, vr["bias"]
        assert vr["ci_coverage"] >= 0.75, vr["ci_coverage"]

    def test_confident_decisions_match_oracle(self):
        r = run_stage1(FAST)
        assert r["confident_wrong_mems"] == []
        dq = r["decision_quality"]["sqcad_rct"]
        assert dq["error_rate"] == 0.0
        assert dq["n_mismatch"] == 0

    def test_unresolved_only_small_true_values(self):
        """Only memories whose true |V| is within CI reach are deferred; all
        large-|V| memories get confident decisions."""
        r = run_stage1(FAST)
        per = r["value_recovery"]["per_memory"]
        status = r["decisions"]["sqcad_rct"]
        for m, e in per.items():
            if status[m] == "unresolved":
                assert e["true"] is not None and abs(e["true"]) < 3.0, \
                    f"{m} unresolved but |V|={e['true']}"

    def test_role_decisions(self):
        """short_term archived despite positive local effect; useful + bridge
        kept; harmful archived."""
        r = run_stage1(FAST)
        status = r["decisions"]["sqcad_rct"]
        world = World(FAST)
        for m in world.memories:
            if m.role in ("useful", "bridge"):
                assert status[m.mem_id] == "keep", m.mem_id
            elif m.role == "short_term":
                assert status[m.mem_id] == "archive", m.mem_id
            elif m.role == "harmful":
                assert status[m.mem_id] == "archive", m.mem_id

    def test_baselines_fail_on_short_term(self):
        """Association / CMI keep short-term memories (they look useful
        locally) — the estimand mismatch Stage 1 is built to expose."""
        r = run_stage1(FAST)
        for method in ("association", "cmi", "naive_ope"):
            dq = r["decision_quality"][method]
            assert dq["regret"] > 0.5, (method, dq["regret"])

    def test_gate_checks_pass(self):
        r = run_stage1(FAST)
        g = r["gate"]
        assert g["adoption_quality"]["passed"]
        assert g["measurement_stability"]["passed"]
        assert g["scope_match"]["passed"]
        assert all(c["passed"] for c in g["overlap"].values())
        assert all(c["passed"] for c in g["co_exposure"].values())

    def test_estimator_oracle_independent_streams(self):
        """Changing the oracle's sample size must not change the estimator
        (separate RNG streams, same mechanism)."""
        world = World(FAST)
        ids = _mem_ids(world)
        rct_a = estimate_sqcad_rct(world, FAST, ids)
        cfg_b = WorldConfig(**{**FAST.__dict__, "n_oracle": 999})
        rct_b = estimate_sqcad_rct(world, cfg_b, ids)
        for m in ids:
            assert rct_a[m]["estimate"] == rct_b[m]["estimate"], m
            assert rct_a[m]["se"] == rct_b[m]["se"], m

    def test_deterministic_same_seed(self):
        r1 = run_stage1(FAST)
        r2 = run_stage1(FAST)
        assert r1["stage1_passes"] == r2["stage1_passes"]
        assert r1["value_recovery"]["per_memory"] == \
            r2["value_recovery"]["per_memory"]
        assert r1["decisions"] == r2["decisions"]


# ---------------------------------------------------------------------------
# Stage 2 — progressive condition violation
# ---------------------------------------------------------------------------

class TestStage2:
    @pytest.mark.parametrize("violation", ["adoption", "co_exposure",
                                           "eligibility", "drift", "scope"])
    def test_gate_abstains_under_every_violation(self, violation):
        r = run_stage2(violation, FAST)
        dq = r["decision_quality"]["sqcad_rct"]
        assert dq["n_unresolved"] + dq["n_mismatch"] > 0, \
            f"{violation}: gate failed to abstain"
        assert r["gate_abstains"]

    def test_drift_is_mismatch_not_unresolved(self):
        """C8 (version drift) breaks the measurement model -> mismatch."""
        r = run_stage2("drift", FAST)
        dq = r["decision_quality"]["sqcad_rct"]
        assert dq["n_mismatch"] == len(_mem_ids(World(FAST)))
        assert not r["gate"]["measurement_stability"]["passed"]

    def test_scope_shift_is_mismatch(self):
        """Cor1: source evidence is not transportable to the target scope."""
        r = run_stage2("scope", FAST)
        dq = r["decision_quality"]["sqcad_rct"]
        assert dq["n_mismatch"] == len(_mem_ids(World(FAST)))
        assert not r["gate"]["scope_match"]["passed"]

    def test_adoption_error_blocks_confidence(self):
        """C6: if the adoption proxy disagrees with the intervention, no
        memory may be confidently decided."""
        r = run_stage2("adoption", FAST)
        dq = r["decision_quality"]["sqcad_rct"]
        assert dq["n_unresolved"] == len(_mem_ids(World(FAST)))
        assert dq["n_confident"] == 0
        assert not r["gate"]["adoption_quality"]["passed"]

    def test_eligibility_harmful_memories_unresolved(self):
        """C3: harmful memories never get randomized evidence -> unresolved,
        and the forced variant pays for keeping them."""
        r = run_stage2("eligibility", FAST)
        status = r["decisions"]["sqcad_rct"]
        for m in ("m7", "m8"):
            assert status[m] != "keep", m
        forced = r["decision_quality"]["sqcad_forced"]
        gated = r["decision_quality"]["sqcad_rct"]
        assert forced["regret"] > gated["regret"], (forced, gated)

    def test_co_exposure_pair_not_confident(self):
        """C7: the bundle cannot be separated into individual effects; pair
        members must not get confident individual decisions."""
        r = run_stage2("co_exposure", FAST)
        status = r["decisions"]["sqcad_rct"]
        assert r["bundle_estimate"] is not None
        for m in r["bundle_estimate"]["estimate"]["pair"]:
            assert status[m] in ("unresolved", "mismatch"), m
        assert r["decision_quality"]["sqcad_forced"]["regret"] > 0.0

    def test_unviolated_matches_stage1(self):
        """run_stage2('none') is not a valid input; but the same-world
        stage-1 run must still pass (sanity on the stage-2 path with the
        base config)."""
        r = run_stage1(WorldConfig(**{**FAST.__dict__, "seed": 11}))
        assert r["stage1_passes"], r["summary_verdict"]


# ---------------------------------------------------------------------------
# Multi-seed stability
# ---------------------------------------------------------------------------

class TestMultiSeed:
    def test_stage1_stable_across_seeds(self):
        agg = run_multi_seed("stage1", n_seeds=3)
        assert agg["ci_coverage"]["mean"] >= 0.7, agg["ci_coverage"]
        assert agg["stage1_pass_rate"] >= 2 / 3
        assert agg["regret"]["sqcad_rct"]["mean"] < 5.0
        assert agg["unresolved_rate"]["mean"] < 0.5


# ---------------------------------------------------------------------------
# Qualification gate unit
# ---------------------------------------------------------------------------

class TestQualification:
    def _checks(self, overrides=None):
        cfg = WorldConfig(**{**FAST.__dict__, **(overrides or {})})
        world = World(cfg)
        rct = estimate_sqcad_rct(world, cfg, _mem_ids(world))
        return world, cfg, run_gate_checks(
            world, cfg, world.source_log(__import__("random").Random(1)), rct)

    def test_scope_mismatch_wins(self):
        world, cfg, checks = self._checks({"scope_shift": True})
        assert qualification_status(checks, "m0", 5.0, 0.1) == "mismatch"

    def test_stability_mismatch_wins(self):
        world, cfg, checks = self._checks({"measurement_drift": True})
        assert qualification_status(checks, "m0", 5.0, 0.1) == "mismatch"

    def test_adoption_unresolved_wins(self):
        world, cfg, checks = self._checks({"adoption_error": 0.3})
        assert qualification_status(checks, "m0", 5.0, 0.1) == "unresolved"

    def test_ci_crossing_zero_is_unresolved(self):
        world, cfg, checks = self._checks({})
        assert qualification_status(checks, "m0", 0.5, 0.5) == "unresolved"

    def test_keep_and_archive(self):
        world, cfg, checks = self._checks({})
        assert qualification_status(checks, "m0", 3.0, 0.5) == "keep"
        assert qualification_status(checks, "m0", -3.0, 0.5) == "archive"
