"""Tests for estimation_validity_experiment — Theorem 3(b)(c) observational route.

The module must demonstrate, on worlds with known truth:

  A. Double robustness: g-formula/IPW/DR recover the local do-effect with
     correct models; DR stays unbiased when exactly ONE of the outcome or
     propensity models is misspecified; every estimator collapses when the
     C6 adoption proxy D replaces true exposure E.
  B. Sequential g-formula: the estimand/support failure — memories whose
     persistent-action support is absent from the deployment log (short_term
     never active) get point estimates with the WRONG SIGN (predict keep,
     truth archive), while identified memories (useful/bridge/harmful) get
     the right decision.
  C. Partial identification: where support fails, bounds over the
     unidentified mechanism abstain (unresolved) with truth inside the
     bounds; the gate never emits a wrong confident decision.
  D. Qualification calibration: zero confident errors at z=1.96 comes at a
     measured coverage/value cost (the coverage-risk curve), not for free.
  E. Sample-size curves: RCT RMSE falls with n_trajectories; DR
     observational bias and bias_sd fall with n_steps.
"""

import math

import pytest

from src.sqcad.estimation_validity_experiment import (
    ConfoundedStepConfig,
    BoundsConfig,
    WorldConfig,
    sample_confounded_log,
    regression_adjustment, ipw, doubly_robust, naive_contrast,
    run_double_robustness,
    sample_observational_log,
    estimate_sequential_g_formula,
    partial_identification_bounds,
    run_partial_identification,
    run_coexposure_identification,
    run_calibration,
    run_sample_size_curves,
)
from src.sqcad.identification_recovery_experiment import (
    ROLE_SHORT_TERM,
    World,
    compute_oracle_values,
)

# Small configs so the suite stays fast; the assertions are structural
# (signs, abstention sets, robustness boundaries), not size-dependent.
CFG_A = ConfoundedStepConfig(n_steps=800, n_seeds=3, seed=101)
CFG_B = WorldConfig(seed=7, n_epochs=60, n_trajectories=20, n_oracle=40,
                    n_source_steps=800)
BC = BoundsConfig(n_sims=30, crowding_grid=(0.0, 0.15, 0.5, 1.0))


def _roles(world: World):
    return {m.mem_id: m.role for m in world.memories}


def _role_ids(world: World, role: str):
    return [mid for mid, r in _roles(world).items() if r == role]


# ---------------------------------------------------------------------------
# A. Double robustness
# ---------------------------------------------------------------------------

class TestDoubleRobustness:
    def _bias(self, table, estimator, oc, pc):
        return table[f"{estimator}/outcome={oc}/propensity={pc}"]["bias_mean"]

    def _sub(self, r, treatment):
        return r["double_robustness_table"][treatment]

    def test_correct_models_are_unbiased(self):
        r = run_double_robustness(CFG_A)
        t = self._sub(r, "exposure")
        for est in ("gformula", "ipw", "dr"):
            assert abs(self._bias(t, est, "correct", "correct")) < 0.05, est

    def test_naive_contrast_biased(self):
        r = run_double_robustness(CFG_A)
        t = self._sub(r, "exposure")
        assert self._bias(t, "naive", "correct", "correct") < -0.10

    def test_dr_robust_to_single_misspecification(self):
        r = run_double_robustness(CFG_A)
        t = self._sub(r, "exposure")
        # outcome correct / propensity wrong, and vice versa
        assert abs(self._bias(t, "dr", "correct", "misspecified")) < 0.05
        assert abs(self._bias(t, "dr", "misspecified", "correct")) < 0.05

    def test_dr_not_robust_when_both_misspecified(self):
        r = run_double_robustness(CFG_A)
        t = self._sub(r, "exposure")
        assert self._bias(t, "dr", "misspecified", "misspecified") < -0.10

    def test_ipw_sensitive_to_propensity_only(self):
        r = run_double_robustness(CFG_A)
        t = self._sub(r, "exposure")
        assert abs(self._bias(t, "ipw", "misspecified", "correct")) < 0.05
        assert self._bias(t, "ipw", "correct", "misspecified") < -0.10

    def test_gformula_sensitive_to_outcome_only(self):
        r = run_double_robustness(CFG_A)
        t = self._sub(r, "exposure")
        assert abs(self._bias(t, "gformula", "correct", "misspecified")) < 0.05
        assert self._bias(t, "gformula", "misspecified", "correct") < -0.10

    def test_adoption_proxy_collapses_every_estimator(self):
        """C6: when D replaces E, even double robustness is badly biased."""
        r = run_double_robustness(CFG_A)
        t = self._sub(r, "adoption_proxy")
        for est in ("gformula", "ipw", "dr", "naive"):
            b = self._bias(t, est, "correct", "correct")
            assert b < -0.30, (est, b)

    def test_dr_on_E_stable_across_adoption_error(self):
        r = run_double_robustness(CFG_A)
        sens = r["adoption_error_sensitivity"]
        e0 = sens["adoption_error_0.0"]["dr_on_E"]["mean"]
        e5 = sens["adoption_error_0.5"]["dr_on_E"]["mean"]
        assert abs(e0 - e5) < 0.10
        # while dr_on_D degrades with misattribution
        d0 = sens["adoption_error_0.0"]["dr_on_D"]["mean"]
        d5 = sens["adoption_error_0.5"]["dr_on_D"]["mean"]
        assert d0 - d5 > 0.5


# ---------------------------------------------------------------------------
# B. Sequential g-formula: estimand/support failure
# ---------------------------------------------------------------------------

class TestSequentialGFormula:
    def test_identified_memories_get_right_decisions(self):
        world = World(CFG_B)
        log = sample_observational_log(world, CFG_B, CFG_B.n_source_steps,
                                       CFG_B.seed + 1)
        gf = estimate_sequential_g_formula(world, CFG_B, log, n_sims=30)
        v = gf["values"]
        truth = compute_oracle_values(world, CFG_B)
        for mid in _role_ids(world, "useful") + _role_ids(world, "bridge"):
            assert (v[mid]["lifecycle"] > 0) == (truth[mid] > 0), mid
        for mid in _role_ids(world, "harmful"):
            assert (v[mid]["lifecycle"] < 0) == (truth[mid] < 0), mid

    def test_short_term_support_failure_sign_error(self):
        """The headline failure: short_term is never active in the
        deployment log, so its active-status cell is unidentified and the
        point estimate extrapolates from the probed rate -> predicts keep,
        truth archives."""
        world = World(CFG_B)
        log = sample_observational_log(world, CFG_B, CFG_B.n_source_steps,
                                       CFG_B.seed + 1)
        gf = estimate_sequential_g_formula(world, CFG_B, log, n_sims=30)
        v = gf["values"]
        truth = compute_oracle_values(world, CFG_B)
        short = _role_ids(world, ROLE_SHORT_TERM)
        assert short, "world must contain short_term memories"
        sign_errors = [mid for mid in short
                       if (v[mid]["lifecycle"] > 0) != (truth[mid] > 0)]
        assert sign_errors, "expected sign errors on the support-failed cells"
        for mid in sign_errors:
            assert v[mid]["active_support"] == 0, \
                f"{mid} should have no active-status support in the log"
            assert 0.10 < v[mid]["archived_rate"] <= 0.30, \
                f"{mid} probed archived rate should be ~p_probe"

    def test_neutral_point_estimates_near_zero(self):
        world = World(CFG_B)
        log = sample_observational_log(world, CFG_B, CFG_B.n_source_steps,
                                       CFG_B.seed + 1)
        gf = estimate_sequential_g_formula(world, CFG_B, log, n_sims=30)
        for mid in _role_ids(world, "neutral"):
            assert abs(gf["values"][mid]["lifecycle"]) < 6.0, mid


# ---------------------------------------------------------------------------
# C. Partial identification rescues the gate
# ---------------------------------------------------------------------------

class TestPartialIdentification:
    def test_bounds_abstain_where_support_fails(self):
        world = World(CFG_B)
        log = sample_observational_log(world, CFG_B, CFG_B.n_source_steps,
                                       CFG_B.seed + 1)
        r = run_partial_identification(world, CFG_B, log, BC)
        table = r["table"]
        short = _role_ids(world, ROLE_SHORT_TERM)
        unresolved = [t for t in table.values()
                      if t["bound_decision"] == "unresolved"]
        assert len(unresolved) == len(short)
        for t in unresolved:
            assert t["bounds_nondegenerate"]
            assert t["truth_inside_bounds"]
            assert t["bounds_avoid_point_sign_error"] is True

    def test_no_wrong_confident_decisions(self):
        world = World(CFG_B)
        log = sample_observational_log(world, CFG_B, CFG_B.n_source_steps,
                                       CFG_B.seed + 1)
        r = run_partial_identification(world, CFG_B, log, BC)
        # no wrong confident decision where the oracle truth is actually
        # distinguishable from zero (raw counts may include MC-noise neutrals)
        assert r["bound_decision_errors_on_nonzero_truth"] == 0
        assert r["point_sign_errors_on_nonzero_truth"] > 0, \
            "the forced point estimate should fail somewhere for the rescue story"
        assert r["bounds_rescue_count"] >= r["point_sign_errors_on_nonzero_truth"]

    def test_useful_memories_bounds_confirm_keep(self):
        world = World(CFG_B)
        log = sample_observational_log(world, CFG_B, CFG_B.n_source_steps,
                                       CFG_B.seed + 1)
        r = run_partial_identification(world, CFG_B, log, BC)
        for mid in _role_ids(world, "useful"):
            assert r["table"][mid]["bound_decision"] == "keep"
            assert r["table"][mid]["point_sign_error"] is False

    def test_c7_bundle_identified_per_item_not(self):
        r = run_coexposure_identification(CFG_B)
        assert r["exposure_correlation"] > 0.999
        assert r["rank_deficient"] is True
        assert r["bundle_recovered"] is True
        assert "unresolved" in r["gate"]


# ---------------------------------------------------------------------------
# D. Qualification calibration and the coverage-risk curve
# ---------------------------------------------------------------------------

class TestCalibration:
    def test_zero_confident_errors_at_z196(self):
        r = run_calibration(CFG_B, n_seeds=3, z_grid=(0.5, 1.64, 1.96))
        assert r["sign_error_confident_z196"] == 0.0

    def test_coverage_risk_curve_trades_coverage_for_safety(self):
        r = run_calibration(CFG_B, n_seeds=3, z_grid=(0.5, 1.0, 1.64, 1.96))
        curve = r["coverage_risk_curve"]
        zs = [float(k.split("=")[1]) for k in curve]
        ordered = sorted(zs)
        errors = [curve[f"z={z}"]["error_rate"] or 0.0 for z in ordered]
        coverages = [curve[f"z={z}"]["coverage"] for z in ordered]
        nd = [curve[f"z={z}"]["n_decided"] for z in ordered]
        fg = [curve[f"z={z}"]["forgone_value"] for z in ordered]
        # higher threshold -> no more errors, no more coverage, no less value
        assert errors[-1] == 0.0
        assert coverages[-1] <= coverages[0]
        assert nd[-1] <= nd[0]
        assert fg[-1] >= fg[0]

    def test_brier_and_ece_in_range(self):
        r = run_calibration(CFG_B, n_seeds=3)
        assert 0.0 < r["brier"] < 0.25
        assert 0.0 <= r["ece"] < 0.25


# ---------------------------------------------------------------------------
# E. Sample-size curves
# ---------------------------------------------------------------------------

class TestSampleSizeCurves:
    def test_rct_rmse_falls_with_n(self):
        r = run_sample_size_curves()["rct"]
        rmses = [r[k]["rmse"] for k in ("n_trajectories=10", "n_trajectories=100")]
        assert rmses[1] < rmses[0]

    def test_dr_bias_sd_falls_with_n_steps(self):
        r = run_sample_size_curves()["dr_observational"]
        sd = [r[k]["bias_sd"] for k in ("n_steps=300", "n_steps=10000")]
        assert sd[1] < sd[0]
        assert abs(r["n_steps=10000"]["bias"]) < 0.05
