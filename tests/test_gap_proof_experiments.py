"""Tests for gap_proof_experiments v2 — revised with formal rigour."""

import json
import pytest

from src.sqcad.gap_proof_experiments import (
    PropAConfig, PropBConfig, PropCConfig,
    run_proposition_a, run_proposition_b, run_proposition_c,
    run_integrated, run_multi_seed,
    score_memory_worth, score_fade_like,
    decide_by_score, decide_by_oracle, compute_regret,
)


# ---------------------------------------------------------------------------
# Proposition A
# ---------------------------------------------------------------------------

class TestPropositionA:
    def test_holds_with_default_config(self):
        result = run_proposition_a()
        assert result["verdict"]["proposition_holds"], result["verdict"]["summary"]

    def test_P_O_identical(self):
        """P(O|M1) = P(O|M2) — max outcome diff should be < 1e-9."""
        result = run_proposition_a()
        dc = result["distribution_check"]
        assert dc["outcome_identical"], f"Max diff = {dc['max_outcome_diff']}"

    def test_m_star_opposite_signs(self):
        """m_star lifecycle value positive in M1, negative in M2."""
        result = run_proposition_a()
        lv = result["lifecycle_values"]
        assert lv["m_star_M1"] > 0.5, f"M1: {lv['m_star_M1']}"
        assert lv["m_star_M2"] < -0.5, f"M2: {lv['m_star_M2']}"

    def test_memory_worth_regret_positive_in_M2(self):
        """Memory Worth should produce strict positive regret in M2."""
        result = run_proposition_a()
        mw_regret = result["regret"]["M2"]["memory_worth"]["regret"]
        assert mw_regret > 0.1, f"MW regret in M2 = {mw_regret}"

    def test_oracle_zero_regret(self):
        """Oracle should have zero regret in both worlds."""
        result = run_proposition_a()
        assert result["regret"]["oracle_M1"]["regret"] == 0.0
        assert result["regret"]["oracle_M2"]["regret"] == 0.0


# ---------------------------------------------------------------------------
# Proposition B
# ---------------------------------------------------------------------------

class TestPropositionB:
    def test_holds_with_default_config(self):
        result = run_proposition_b()
        assert result["verdict"]["proposition_holds"], result["verdict"]["summary"]

    def test_do_effects_exactly_equal(self):
        """Δ_do(m_short) and Δ_do(m_long) must be exactly equal by construction."""
        result = run_proposition_b()
        de = result["true_do_effects"]
        assert de["exactly_equal"], f"diff = {de['diff']}"

    def test_lifecycle_values_opposite_signs(self):
        """m_short and m_long must have opposite lifecycle signs."""
        result = run_proposition_b()
        assert result["verdict"]["lifecycle_opposite_sign"]

    def test_cmi_regret_positive(self):
        """CMI observational decision should produce regret > 0."""
        result = run_proposition_b()
        cmi_regret = result["regret"]["cmi_observational"]["regret"]
        assert cmi_regret > 0.1, f"CMI regret = {cmi_regret}"

    def test_true_do_not_observational(self):
        """True do-effects should be precise (alpha), not estimated from obs."""
        result = run_proposition_b()
        de = result["true_do_effects"]
        assert abs(de["m_short"] - 2.0) < 0.01
        assert abs(de["m_long"] - 2.0) < 0.01


# ---------------------------------------------------------------------------
# Proposition C
# ---------------------------------------------------------------------------

class TestPropositionC:
    def test_holds_with_default_config(self):
        result = run_proposition_c()
        assert result["verdict"]["proposition_holds"], result["verdict"]["summary"]

    def test_source_data_identical(self):
        result = run_proposition_c()
        assert result["source_data_identical"]

    def test_target_signs_differ(self):
        result = run_proposition_c()
        assert result["verdict"]["target_signs_differ"]

    def test_source_misleads_at_least_one_world(self):
        result = run_proposition_c()
        assert result["verdict"]["source_misleads_at_least_one_world"]

    def test_scope_weighted_estimate_uses_weights(self):
        """Scope-weighted estimate should use proper scope weights, not simple avg."""
        result = run_proposition_c()
        se = result["source_estimates"]
        # Design weighted average
        cfg = PropCConfig()
        design = cfg.scope_s1_weight * cfg.tau_s1 + cfg.scope_s2_weight * cfg.tau_s2
        # Estimated should be close to design
        assert abs(se["scope_weighted_average_estimated"] - design) < 0.5


# ---------------------------------------------------------------------------
# Integrated
# ---------------------------------------------------------------------------

class TestIntegrated:
    def test_all_hold(self):
        result = run_integrated()
        assert result["overall_verdict"]["all_hold"]

    def test_regret_keys_exist(self):
        """All regret keys must reference existing data (no KeyError from old names)."""
        result = run_integrated()
        rs = result["regret_summary"]
        assert rs["A_memory_worth_regret_M2"] > 0
        assert rs["B_cmi_regret"] > 0
        # C may have regret in either world (at least one should mislead)

    def test_json_serializable(self):
        result = run_integrated()
        s = json.dumps(result, ensure_ascii=False)
        d = json.loads(s)
        assert d["overall_verdict"]["all_hold"]


# ---------------------------------------------------------------------------
# Multi-seed stability
# ---------------------------------------------------------------------------

class TestMultiSeed:
    def test_all_hold_across_seeds(self):
        stability = run_multi_seed(n_seeds=5, base_seed=0)
        assert stability["proposition_A"]["all_hold"]
        assert stability["proposition_B"]["all_hold"]
        assert stability["proposition_C"]["all_hold"]

    def test_hold_rates_are_1_0(self):
        stability = run_multi_seed(n_seeds=5, base_seed=100)
        for prop in ["proposition_A", "proposition_B", "proposition_C"]:
            assert stability[prop]["hold_rate"] == 1.0, f"{prop} hold_rate < 1.0"


# ---------------------------------------------------------------------------
# Baseline methods
# ---------------------------------------------------------------------------

class TestBaselineMethods:
    def test_memory_worth_range(self):
        logs = [
            {"item": "a", "exposed": 1.0, "success": 1.0, "time": 0.0, "scope": 0.0},
            {"item": "a", "exposed": 1.0, "success": 1.0, "time": 1.0, "scope": 0.0},
            {"item": "b", "exposed": 1.0, "success": 0.0, "time": 0.0, "scope": 0.0},
        ]
        scores = score_memory_worth(logs, ["a", "b"])
        assert 0 <= scores["a"] <= 1
        assert 0 <= scores["b"] <= 1
        assert scores["a"] > scores["b"]

    def test_fade_like_decays(self):
        logs = [
            {"item": "x", "exposed": 1.0, "success": 1.0, "time": 0.0, "scope": 0.0},
            {"item": "y", "exposed": 1.0, "success": 1.0, "time": 100.0, "scope": 0.0},
        ]
        scores = score_fade_like(logs, ["x", "y"], half_life=50.0)
        assert scores["y"] > scores["x"]


class TestDecisionRegret:
    def test_oracle_zero_regret(self):
        tv = {"a": 3.0, "b": -1.0}
        assert compute_regret(decide_by_oracle(tv), tv)["regret"] == 0.0

    def test_wrong_decision_positive_regret(self):
        tv = {"a": 3.0, "b": -1.0}
        bad = {"a": "archive", "b": "keep"}
        assert compute_regret(bad, tv)["regret"] > 0


# ---------------------------------------------------------------------------
# Identification conditions
# ---------------------------------------------------------------------------

class TestIdentificationConditions:
    def test_conditions_are_documented(self):
        from src.sqcad.gap_proof_experiments import IDENTIFICATION_CONDITIONS
        required = ["CONSISTENCY", "EXCHANGEABILITY", "POSITIVITY",
                    "TREATMENT OBSERVABILITY", "EXPOSURE OBSERVABILITY",
                    "ADOPTION MEASUREMENT", "INTERFERENCE", "SCOPE TRANSPORT"]
        for term in required:
            assert term.upper() in IDENTIFICATION_CONDITIONS.upper(), \
                f"Missing condition: {term}"
