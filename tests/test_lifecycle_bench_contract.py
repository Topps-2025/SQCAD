"""Data contract tests for SQCAD-LifecycleBench (doc 22- 3, 8, 10).

The tests verify the SIX mandatory contract features on representative
samples (fast) and, when the built dataset exists under
results/lifecycle_bench/, the full serialized corpus (public / policy log /
hidden layers, splits, pair twins, oracle distribution).

Everything here is deterministic: an episode is a pure function of its seed.
"""

import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.sqcad.lifecycle_bench.evaluator import (
    EpisodeOutcome, evaluate, oracle_of,
)
from src.sqcad.lifecycle_bench.frozen import (
    ADOPT_THRESHOLD, BASE_SEED, GAMMA, PROBE_COST, PROBE_THRESHOLD,
    SPLIT_SEED, TASK_VALUE, TAU_TOL,
)
from src.sqcad.lifecycle_bench.generator import (
    CONTROL_FAMILIES, ENTITIES, FAMILY_VARIANTS, N_PAIRS,
    _pair_episodes, assign_splits, build_episode,
)
from src.sqcad.lifecycle_bench.realizer import RealizedEpisode, overlap
from src.sqcad.lifecycle_bench.rollout import paired_rollout
from src.sqcad.lifecycle_bench.world import (
    NEGATIVE, reference_certificate,
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results",
                           "lifecycle_bench")

# one representative episode per (family, variant); hitchhiker has one
# variant, controls have "default"
ENTITY_OF = {"hitchhiker": "john", "rare_bridge": "daniel",
             "version_update": "ethan", "harmful_stale": "lucas",
             "self_obscuring": "maya", "scope_mismatch": "oliver"}

SAMPLE_SEED = 20260817


def _sample(family: str, variant: str) -> RealizedEpisode:
    entity = (ENTITY_OF[family] if family in ENTITY_OF
              else ENTITIES[family][0])
    return build_episode(SAMPLE_SEED, family, variant, entity, None)


def _paired(family: str, variant: str):
    return paired_rollout(_sample(family, variant))


def _outcome(ep: RealizedEpisode) -> EpisodeOutcome:
    pr = paired_rollout(ep)
    return evaluate(ep, pr.keep, pr.archive)


# ---------------------------------------------------------------------------
# 1. 持久动作分支 (3.1): both branches exist, slot0 is branch-independent
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("family,variant", [
    (f, v) for f, vs in FAMILY_VARIANTS.items() for v in vs
] + [(f, "default") for f in CONTROL_FAMILIES])
def test_persistent_action_branches_and_local_same(family, variant):
    ep = _sample(family, variant)
    pr = paired_rollout(ep)
    out = evaluate(ep, pr.keep, pr.archive)
    assert out.oracle_local_same          # slot0 identical across branches
    assert pr.keep.action == "keep" and pr.archive.action == "archive"


# ---------------------------------------------------------------------------
# 2. 真正的 chronological future (3.2): slots 1..10, no gold in the trace
# ---------------------------------------------------------------------------
def test_chronological_future_schedule():
    ep = _sample("hitchhiker", "default")
    assert [i.spec.slot for i in ep.future_items] == list(range(1, 11))
    # future-only values (555-0199) never appear in pre-decision sessions
    for fam, variants in (("hitchhiker", ("default",)),
                          ("version_update", ("update_after",))):
        for v in variants:
            ep2 = _sample(fam, v)
            for sess in ep2.sessions:
                for msg in sess.messages:
                    assert "555-0199" not in msg.text


def test_hidden_needed_ids_never_leak_into_sessions():
    for family, variants in FAMILY_VARIANTS.items():
        for v in variants:
            ep = _sample(family, v)
            needed = set(ep.world.needed_future_ids)
            for sess in ep.sessions:
                for msg in sess.messages:
                    for nid in needed:
                        assert nid not in msg.text, (
                            f"{ep.world.episode_id}: hidden needed id {nid} "
                            f"leaked into a session")


# ---------------------------------------------------------------------------
# 3. 可执行 outcome (3.3): discounted utility follows the frozen contract
# ---------------------------------------------------------------------------
def test_outcome_is_discounted_contract_value():
    ep = _sample("stable_positive", "default")
    pr = paired_rollout(ep)
    out = evaluate(ep, pr.keep, pr.archive)
    # keep branch: m1 succeeds at slots 2, 5, 8 -> 10 * (g^2+g^5+g^8) - storage
    gross = TASK_VALUE * (GAMMA ** 2 + GAMMA ** 5 + GAMMA ** 8)
    assert out.lifecycle_value_keep > gross - 2.0
    assert out.lifecycle_value_keep < gross + 1.0
    # tau = keep - archive; archive pays a probe at slot 2 (g^2 * PROBE_COST)
    assert out.tau_keep_archive > 0.5


def test_oracle_boundary_uses_tau_tol():
    assert oracle_of(TAU_TOL + 1e-9) == "keep"
    assert oracle_of(-TAU_TOL - 1e-9) == "archive"
    assert oracle_of(0.0) == "neutral"


# ---------------------------------------------------------------------------
# 4. 同源反事实 (3.4): branches share the future stream
# ---------------------------------------------------------------------------
def test_same_source_counterfactual_shared_future():
    ep = _sample("rare_bridge", "rescue_impossible")
    pr = paired_rollout(ep)
    for k, a in zip(pr.keep.logs, pr.archive.logs):
        assert k.slot == a.slot and k.query == a.query
        assert k.scope == a.scope
        assert (k.state.store | k.state.archive) == \
               (a.state.store | a.state.archive)  # same world, diff placement


# ---------------------------------------------------------------------------
# 5. 隐藏可核验标签 (3.5): evaluator-only labels exist and match reality
# ---------------------------------------------------------------------------
def test_hidden_labels_exist_for_all_families():
    for family, variants in FAMILY_VARIANTS.items():
        for v in variants:
            ep = _sample(family, v)
            out = _outcome(ep)
            assert isinstance(out, EpisodeOutcome)
            for attr in ("lifecycle_value_keep", "lifecycle_value_archive",
                         "tau_keep_archive", "oracle_action",
                         "needed_future_ids", "harmful_exposure_keep",
                         "harmful_exposure_archive", "rescue_possible",
                         "scope_validity", "identification_regime",
                         "oracle_local_same"):
                assert hasattr(out, attr)


# ---------------------------------------------------------------------------
# 6. 压力与不可识别世界 (3.6): oracle sign map + controls
# ---------------------------------------------------------------------------
ORACLE_SIGNS = {
    ("hitchhiker", "default"): "archive",
    ("rare_bridge", "rescue_possible"): "keep",
    ("rare_bridge", "rescue_impossible"): "keep",
    ("version_update", "update_before"): "archive",
    ("version_update", "update_after"): "keep",
    ("harmful_stale", "correction_visible"): "archive",
    ("harmful_stale", "no_correction"): "neutral",
    ("self_obscuring", "crowding"): "keep",
    ("self_obscuring", "rescue_possible"): "keep",
    ("scope_mismatch", "future_in_s1"): "keep",
    ("scope_mismatch", "future_in_s2"): "archive",
    ("stable_positive", "default"): "keep",
    ("stable_negative", "default"): "archive",
    ("neutral", "default"): "neutral",
}


@pytest.mark.parametrize("family,variant", list(ORACLE_SIGNS))
def test_oracle_sign_map(family, variant):
    ep = _sample(family, variant)
    out = _outcome(ep)
    assert out.oracle_action == ORACLE_SIGNS[(family, variant)], (
        f"{family}/{variant}: tau={out.tau_keep_archive}")
    # designer label must agree on every strict (keep/archive) family
    if out.decision_action_label in ("keep", "archive"):
        assert out.oracle_action == out.decision_action_label


def test_controls_are_not_all_abstain():
    kept = [ORACLE_SIGNS[("stable_positive", "default")] == "keep"]
    archived = [ORACLE_SIGNS[("stable_negative", "default")] == "archive"]
    neutral = [ORACLE_SIGNS[("neutral", "default")] == "neutral"]
    assert kept and archived and neutral


def test_negative_certificate_forbids_probe():
    """stable_negative: the corrected stale fact may never be probed back."""
    ep = _sample("stable_negative", "default")
    pr = paired_rollout(ep)
    assert pr.archive.count_probes() == 0
    cert = reference_certificate(ep, "m1", "s1")
    assert cert.status is NEGATIVE


def test_crowding_denies_probe_but_paid():
    """self_obscuring crowding: the probe is attempted (paid) but denied."""
    ep = _sample("self_obscuring", "crowding")
    pr = paired_rollout(ep)
    probe_slots = [l for l in pr.archive.logs if l.probes]
    assert len(probe_slots) >= 1
    assert all(l.restore == () for l in probe_slots)   # denied
    assert all(l.probe_cost == PROBE_COST for l in probe_slots)  # still paid
    # the probe attempt at slot 8 exists in the archive branch only
    assert pr.keep.count_probes() == 0


def test_rescue_paths():
    rescue_ok = _sample("rare_bridge", "rescue_possible")
    rescue_bad = _sample("rare_bridge", "rescue_impossible")
    assert paired_rollout(rescue_ok).archive.rescued("m1")
    assert not paired_rollout(rescue_bad).archive.rescued("m1")
    # weak query: overlap 2 < PROBE_THRESHOLD never probes
    ep = _sample("rare_bridge", "rescue_impossible")
    q8 = ep.future_items[7].task
    assert overlap(q8.tokens, ep.tokens("m1")) < PROBE_THRESHOLD
    assert overlap(q8.tokens, ep.tokens("m1")) >= ADOPT_THRESHOLD


# ---------------------------------------------------------------------------
# 观测等价 pairs (3.6 Prop A analog): identical trace, flipped oracle
# ---------------------------------------------------------------------------
def test_observation_pairs_flip_oracle_with_identical_trace():
    pairs = _pair_episodes()
    assert len(pairs) == 2 * N_PAIRS
    by_pair = {}
    for ep, pair in pairs:
        by_pair.setdefault(pair, []).append(ep)
    assert len(by_pair) == N_PAIRS
    for pair, (base, flip) in by_pair.items():
        out_base = _outcome(base)
        out_flip = _outcome(flip)
        # identical public trace: sessions, decision query, memories, future
        def trace_text(ep):
            return [msg.text for s in ep.sessions for msg in s.messages]
        assert trace_text(base) == trace_text(flip)
        assert base.decision_task.query == flip.decision_task.query
        assert [m.text for m in base.memories] == \
               [m.text for m in flip.memories]
        assert [it.task.query if it.task else None
                for it in base.future_items] == \
               [it.task.query if it.task else None
                for it in flip.future_items]
        # flipped oracle: archive -> keep
        assert out_base.oracle_action == "archive"
        assert out_flip.oracle_action == "keep"
        # flipped hidden needed id on slot 5
        assert base.world.future_items[4].task.needed_fid == "e1"
        assert flip.world.future_items[4].task.needed_fid == "h1"
        assert base.world.paired_key == flip.world.paired_key


def test_pairs_stay_in_one_split():
    pairs = _pair_episodes()
    split_of = assign_splits([], pairs)
    by_pair = {}
    for ep, pair in pairs:
        by_pair.setdefault(pair, []).append(ep)
    for pair, eps in by_pair.items():
        assert len({split_of[e.world.episode_id] for e in eps}) == 1, \
            f"pair {pair} split across splits"


# ---------------------------------------------------------------------------
# split hygiene (22- 8): group-level splits, never inside a pair
# ---------------------------------------------------------------------------
def test_split_groups_are_family_variant_entity():
    # 3 seeds per group: if the split were episode-level, same-group episodes
    # would land in different splits with high probability.
    eps = [build_episode(SAMPLE_SEED + k, f, v, e, None)
           for f, vs in FAMILY_VARIANTS.items()
           for v in vs for e in ENTITIES[f] for k in range(3)]
    eps += [build_episode(SAMPLE_SEED + k, f, "default", ENTITIES[f][0], None)
            for f in CONTROL_FAMILIES for k in range(3)]
    split_of = assign_splits([(ep, None) for ep in eps], [])
    by_group = {}
    for ep in eps:
        g = (ep.world.family, ep.world.variant, ep.memories[0].spec.entity)
        by_group.setdefault(g, set()).add(split_of[ep.world.episode_id])
    for g, splits in by_group.items():
        assert len(splits) == 1, f"group {g} split across {splits}"
    # the split is a deterministic function of the group + SPLIT_SEED
    again = assign_splits([(ep, None) for ep in eps], [])
    assert again == split_of


# ---------------------------------------------------------------------------
# built dataset (when present): full-corpus invariants on the 3 layers
# ---------------------------------------------------------------------------
BUILT = os.path.join(RESULTS_DIR, "manifest.json")


@pytest.mark.skipif(not os.path.exists(BUILT),
                    reason="dataset not built; run tools/build_lifecycle_bench.py")
class TestBuiltDataset:
    def test_layers_and_counts(self):
        with open(BUILT, encoding="utf-8") as f:
            manifest = json.load(f)
        assert manifest["counts"]["total"] == 1380
        assert manifest["counts"]["main"] == 1350
        assert manifest["counts"]["pair_episodes"] == 30
        for name in ("public.jsonl", "policy_log.jsonl", "hidden.jsonl"):
            path = os.path.join(RESULTS_DIR, name)
            assert os.path.exists(path)
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f]
            assert len(rows) == 1380

    def test_public_layer_has_no_gold(self):
        with open(os.path.join(RESULTS_DIR, "public.jsonl"),
                  encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        all_text = "\n".join(
            json.dumps(r, ensure_ascii=False) for r in rows)
        # hidden needed ids and true fids never appear in the public layer.
        # Tokenize once into a set (the public pids mem1..memN contain "m1"
        # as a substring, so a naive substring check is invalid; a per-fid
        # regex over the whole corpus is O(N * |text|) -- too slow).
        toks = set(re.findall(r"[a-z0-9]+", all_text))
        with open(os.path.join(RESULTS_DIR, "hidden.jsonl"),
                  encoding="utf-8") as f:
            hidden = [json.loads(line) for line in f]
        for h in hidden:
            for fid in h["labels"]["needed_future_ids"]:
                assert fid not in toks, (
                    f"hidden needed id {fid} leaked into the public layer")
        assert "tau_keep_archive" not in all_text
        assert "oracle_action" not in all_text

    def test_manifest_frozen_constants(self):
        with open(BUILT, encoding="utf-8") as f:
            manifest = json.load(f)
        assert manifest["version"] == "v0.1"
        assert manifest["horizon"] == 10
        assert manifest["episodes_per_family"] == 200
        assert manifest["control_episodes"] == 50
        assert manifest["observation_pairs"] == 15
        assert manifest["policy"] == "reference_sqcad"
        assert manifest["seeds"]["base"] == BASE_SEED

    def test_pairs_in_same_split_in_built_dataset(self):
        with open(BUILT, encoding="utf-8") as f:
            manifest = json.load(f)
        pair_splits = {}
        for eid, split in manifest["splits"].items():
            if eid.startswith("hitchhiker-pair-"):
                pair = eid.split("-pair-")[1].split("-")[0]
                pair_splits.setdefault(pair, set()).add(split)
        for pair, splits in pair_splits.items():
            assert len(splits) == 1, f"pair {pair} in {splits}"

    def test_oracle_distribution_matches_design(self):
        with open(BUILT, encoding="utf-8") as f:
            manifest = json.load(f)
        dist = manifest["counts"]["oracle"]
        assert dist["hitchhiker"] == {"archive": 215, "keep": 15}
        assert dist["rare_bridge"] == {"keep": 200}
        assert dist["version_update"] == {"archive": 100, "keep": 100}
        assert dist["harmful_stale"] == {"archive": 100, "neutral": 100}
        assert dist["self_obscuring"] == {"keep": 200}
        assert dist["scope_mismatch"] == {"keep": 100, "archive": 100}
        assert dist["stable_positive"] == {"keep": 50}
        assert dist["stable_negative"] == {"archive": 50}
        assert dist["neutral"] == {"neutral": 50}

    def test_policy_log_is_gold_free_and_auditable(self):
        with open(os.path.join(RESULTS_DIR, "policy_log.jsonl"),
                  encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        for r in rows:
            assert r["policy"] == "reference_sqcad"
            for branch in ("branch_keep", "branch_archive"):
                assert "needed" not in json.dumps(r[branch])
                assert "success" not in json.dumps(r[branch])
                assert "tau" not in json.dumps(r[branch])
