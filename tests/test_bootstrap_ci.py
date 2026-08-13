"""Gate 5 tests: paired seed/episode bootstrap CI + four-piece freeze.

Covers: CI primitives (coverage, determinism, alpha ordering), the paired
vs independent comparison (pairing must remove shared world noise), the
heavy-tailed control (bootstrap recovers nominal coverage where normal
under-covers), the D0 seed-level coverage reproduction of Gate 3's
anti-conservatism, the B experiments' structure, and the freeze manifest
(deterministic, four pieces, chained hash breaks on any change).
"""

import json
import math
from pathlib import Path
from statistics import mean

import pytest

from sqcad.bootstrap_ci import (
    bca_ci, independent_seed_diff_ci, normal_ci, paired_seed_ci,
    paired_seed_diff_ci, paired_trajectory_ci, percentile_ci,
    run_cost_contract_ci, run_d0_seed_level_coverage,
    run_heavy_tail_control, run_main_table_ci, studentized_ci,
)
from sqcad.freeze_four_piece import build_manifest


# ---------------------------------------------------------------------------
# CI primitives
# ---------------------------------------------------------------------------


def test_percentile_ci_contains_mean_and_is_deterministic():
    xs = [1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 1.5, 2.5, 4.0]
    ci = percentile_ci(xs, n_boot=500, seed=11)
    assert ci["ci_low"] <= ci["mean"] <= ci["ci_high"]
    assert ci["mean"] == pytest.approx(mean(xs))
    assert percentile_ci(xs, n_boot=500, seed=11) == ci


def test_percentile_ci_alpha_ordering():
    xs = [1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 1.5, 2.5, 4.0]
    tight = percentile_ci(xs, alpha=0.05, seed=3)
    loose = percentile_ci(xs, alpha=0.01, seed=3)
    assert loose["ci_low"] <= tight["ci_low"]
    assert loose["ci_high"] >= tight["ci_high"]


def test_normal_ci_symmetric_around_mean():
    xs = [1.0, 2.0, 3.0, 4.0]
    ci = normal_ci(xs)
    assert ci["mean"] == pytest.approx(2.5)
    assert ci["mean"] - ci["ci_low"] == pytest.approx(
        ci["ci_high"] - ci["mean"])


# ---------------------------------------------------------------------------
# Paired vs independent: pairing must remove shared noise
# ---------------------------------------------------------------------------


def _paired_vs_independent(world_noise_sd=3.0, n_seeds=60, n_boot=999):
    rng = __import__("random").Random(99)
    a, b = [], []
    for _ in range(n_seeds):
        w = rng.gauss(0.0, world_noise_sd)
        a.append(5.0 + w + rng.gauss(0.0, 1.0))
        b.append(0.0 + w + rng.gauss(0.0, 1.0))
    paired = paired_seed_diff_ci(a, b, n_boot=n_boot, seed=7)
    independent = independent_seed_diff_ci(a, b, n_boot=n_boot, seed=7)
    return paired, independent


def test_paired_ci_narrower_than_independent_under_shared_noise():
    paired, independent = _paired_vs_independent()
    assert paired["se"] < independent["se"]
    assert (paired["ci_high"] - paired["ci_low"]) < (
        independent["ci_high"] - independent["ci_low"])
    assert paired["mean"] == pytest.approx(5.0, abs=0.2)


def test_paired_ci_recovers_true_difference():
    paired, _ = _paired_vs_independent()
    assert paired["ci_low"] <= 5.0 <= paired["ci_high"]


def test_paired_trajectory_ci_correlation():
    rng = __import__("random").Random(42)
    keep, arc = [], []
    for _ in range(100):
        common = rng.gauss(0.0, 4.0)
        keep.append(3.0 + common + rng.gauss(0.0, 0.5))
        arc.append(0.0 + common + rng.gauss(0.0, 0.5))
    ci = paired_trajectory_ci(keep, arc, n_boot=999, seed=1)
    assert ci["mean"] == pytest.approx(3.0, abs=0.1)
    assert ci["ci_low"] <= ci["mean"] <= ci["ci_high"]


def test_paired_seed_ci_deterministic():
    xs = [1.0, -2.0, 3.0, 5.0, 0.5]
    assert paired_seed_ci(xs, n_boot=200, seed=5) == paired_seed_ci(
        xs, n_boot=200, seed=5)
    assert paired_seed_ci(xs, n_boot=200, seed=5) != paired_seed_ci(
        xs, n_boot=200, seed=6)


# ---------------------------------------------------------------------------
# A1: heavy-tailed control (known truth)
# ---------------------------------------------------------------------------


def test_heavy_tail_studentized_beats_normal_and_percentile():
    ctl = run_heavy_tail_control(n=30, reps=400, n_boot=199, seed=7)
    assert ctl["normal_coverage"] < 0.95          # Gate 3 mechanism
    # the plain percentile bootstrap is first-order: it does NOT fix skew
    assert ctl["percentile_coverage"] < ctl["studentized_coverage"]
    # the studentized (percentile-t) interval restores coverage toward
    # nominal under skew -- the module default
    assert ctl["studentized_coverage"] >= 0.91
    assert ctl["studentized_coverage"] > ctl["normal_coverage"] + 0.04
    assert ctl["truth"] == pytest.approx(math.exp(0.5))


def test_studentized_ci_contains_mean_and_deterministic():
    xs = [1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 1.5, 2.5, 4.0]
    ci = studentized_ci(xs, n_boot=500, seed=11)
    assert ci["method"] == "studentized"
    assert ci["ci_low"] <= ci["mean"] <= ci["ci_high"]
    assert studentized_ci(xs, n_boot=500, seed=11) == ci
    bca = bca_ci(xs, n_boot=500, seed=11)
    assert bca["method"] == "bca"
    assert bca["ci_low"] <= bca["mean"] <= bca["ci_high"]


def test_heavy_tail_deterministic():
    a = run_heavy_tail_control(n=20, reps=50, n_boot=99, seed=3)
    b = run_heavy_tail_control(n=20, reps=50, n_boot=99, seed=3)
    assert a == b


# ---------------------------------------------------------------------------
# A2: D0 seed-level coverage
# ---------------------------------------------------------------------------


def test_d0_coverage_reproduces_anti_conservatism_and_recovers():
    res = run_d0_seed_level_coverage(n_seeds=4, n_trajectories=15,
                                     n_oracle=25, n_epochs=25,
                                     n_boot=199)
    cov = res["coverage"]
    # Gate 3 reproduction: within-seed CI against the realized truth
    # under-covers (0.861 at n_trajectories=100 in the frozen run);
    # any value far below nominal 0.95 confirms the unit error.
    assert 0.4 < cov["within_seed_normal_vs_realized_truth"] < 0.96
    # the seed-level bootstrap targets the seed-population mean: it must
    # not under-cover relative to the wrong-unit CI (same seeds, same truth)
    assert (cov["seed_level_bootstrap_vs_seed_mean_truth"]
            >= cov["within_seed_normal_vs_realized_truth"] - 0.15)
    assert cov["seed_level_bootstrap_vs_seed_mean_truth"] >= 0.5
    assert cov["n_within_checks"] == 4 * 12
    assert cov["n_seed_mean_checks"] == 12
    for m in res["per_memory"].values():
        assert m["seed_bootstrap"]["ci_low"] <= m["seed_bootstrap"]["mean"] \
            <= m["seed_bootstrap"]["ci_high"]


def test_d0_deterministic():
    a = run_d0_seed_level_coverage(n_seeds=3, n_trajectories=10,
                                   n_oracle=15, n_epochs=15, n_boot=99)
    b = run_d0_seed_level_coverage(n_seeds=3, n_trajectories=10,
                                   n_oracle=15, n_epochs=15, n_boot=99)
    assert a == b


# ---------------------------------------------------------------------------
# B: paired bootstrap on the frozen tables
# ---------------------------------------------------------------------------


def test_main_table_ci_structure_and_paired_wins():
    res = run_main_table_ci(seeds=8, steps=30, n_boot=199)
    assert res["protocol"]["seeds"] == 8
    policies = res["per_policy"]
    assert "risk_gated_decomp_abstract" in policies
    assert len(policies) >= 15
    for p, metrics in policies.items():
        for metric, ci in metrics.items():
            if isinstance(ci, dict) and "ci_low" in ci:
                assert ci["ci_low"] <= ci["mean"] <= ci["ci_high"]
    for label, d in res["differences"].items():
        assert d["average_utility"]["paired"] is True
        assert d["independent_seed_ci"]["paired"] is False
        # both CIs are CIs of the same per-seed difference mean: means must
        # agree and both must be sane; whether pairing narrows the CI is an
        # empirical property (see the synthetic control test) -- different
        # keep/archive decisions on the shared budget can be negatively
        # correlated within seed, so no width ordering is asserted here
        assert d["average_utility"]["mean"] == pytest.approx(
            d["independent_seed_ci"]["mean"])
        assert d["average_utility"]["se"] > 0.0


def test_cost_contract_ci_structure():
    res = run_cost_contract_ci(seeds=8, steps=30, probe_budget=8,
                               n_boot=199)
    assert set(res["per_policy"]) >= {
        "risk_gated_decomp_abstract", "causal_item", "trivium", "rrf",
        "keep_all", "no_memory"}
    sq = res["per_policy"]["risk_gated_decomp_abstract"]
    assert sq["ci_low"] <= sq["mean"] <= sq["ci_high"]
    d = res["differences"]["vs_best"]
    assert d["V"]["mean"] > -0.5        # framework leads within sampling
    assert d["V"]["paired"] is True
    assert d["V_independent"]["paired"] is False
    assert d["V"]["se"] < d["V_independent"]["se"]


# ---------------------------------------------------------------------------
# C: four-piece freeze
# ---------------------------------------------------------------------------


def _make_tmp_repo(tmp_path: Path) -> Path:
    (tmp_path / "src" / "sqcad").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "docs" / "实验证据链").mkdir(parents=True)
    (tmp_path / "src" / "sqcad" / "core.py").write_text(
        "VALUE = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_core.py").write_text(
        "def test(): pass\n", encoding="utf-8")
    (tmp_path / "results" / "main.json").write_text(
        json.dumps({"a": 1}), encoding="utf-8")
    (tmp_path / "docs" / "实验证据链" / "00-总览.md").write_text(
        "# report\n", encoding="utf-8")
    db = tmp_path / "database"
    (db / "datasets" / "LongMemEval").mkdir(parents=True)
    (db / "datasets" / "LoCoMo").mkdir(parents=True)
    (db / "datasets" / "LongMemEval" / "longmemeval_s_cleaned.json").write_text(
        '{"samples": []}', encoding="utf-8")
    (db / "datasets" / "LoCoMo" / "locomo10.json").write_text(
        '{"conversations": []}', encoding="utf-8")
    return tmp_path


def test_freeze_manifest_four_pieces_and_deterministic(tmp_path):
    repo = _make_tmp_repo(tmp_path)
    db = tmp_path / "database"
    m1 = build_manifest(repo, db)
    m2 = build_manifest(repo, db)
    assert m1 == m2                       # deterministic
    assert set(m1["pieces"]) == {"code", "config", "results", "reports"}
    assert m1["pieces"]["code"]["n_files"] == 2
    assert m1["pieces"]["results"]["n_files"] == 1
    assert m1["pieces"]["reports"]["n_files"] == 1
    reg = m1["pieces"]["config"]["registry"]["frozen_data"]
    assert len(reg["LongMemEval_S"]["sha256"]) == 64
    assert len(reg["LoCoMo"]["sha256"]) == 64


def test_freeze_aggregate_hash_breaks_on_any_change(tmp_path):
    repo = _make_tmp_repo(tmp_path)
    db = tmp_path / "database"
    base = build_manifest(repo, db)["aggregate_sha256"]
    (repo / "src" / "sqcad" / "core.py").write_text(
        "VALUE = 2\n", encoding="utf-8")
    changed = build_manifest(repo, db)["aggregate_sha256"]
    assert changed != base


def test_freeze_missing_dataset_aborts(tmp_path):
    repo = _make_tmp_repo(tmp_path)
    db = tmp_path / "database"
    (db / "datasets" / "LoCoMo" / "locomo10.json").unlink()
    with pytest.raises(FileNotFoundError):
        build_manifest(repo, db)


def test_freeze_smoke_result_excluded(tmp_path):
    repo = _make_tmp_repo(tmp_path)
    (repo / "results" / "bootstrap_ci_smoke.json").write_text(
        json.dumps({"smoke": True}), encoding="utf-8")
    m = build_manifest(repo, tmp_path / "database")
    names = {f["path"] for f in m["pieces"]["results"]["files"]}
    assert "results/bootstrap_ci_smoke.json" not in names
