"""Dataset generator (doc 22- 10): assembles the SQCAD-LifecycleBench MVP.

Shape:
  * 6 families x 200 episodes: 2 variants x 2 entities x 50 (hitchhiker:
    1 variant x 2 entities x 100) + 3 controls x 50 = 1350 episodes;
  * + 15 observation-equivalent hitchhiker pairs (30 episodes): the public
    trace is identical but the hidden needed id of slot 5 flips e1 -> h1,
    so the oracle action flips archive <-> keep (Prop A analog, 22- 3.6);
  * group-level splits (family, variant, entity) -> 60/20/20 with SPLIT_SEED;
    every pair lives entirely inside one split;
  * three-layer serialization (22- 4): public.jsonl / policy_log.jsonl /
    hidden.jsonl + manifest.json with the frozen contract.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import random
from dataclasses import replace
from typing import Dict, List, Optional, Tuple

from .evaluator import EpisodeOutcome, evaluate
from .frozen import (
    BASE_SEED, CONTROL_EPISODES, EPISODES_PER_FAMILY, HORIZON, PAIR_SEED,
    SPLIT_SEED, SPLIT_WEIGHTS, VERSION,
)
from .realizer import RealizedEpisode, realize, validate_episode
from .rollout import paired_rollout
from .scenarios import FutureItemSpec, TaskSpec, WorldSpec, build_spec
from .world import Rollout, TaskLog

# ---------------------------------------------------------------------------
# family -> (variants, topics, entities)
# ---------------------------------------------------------------------------
FAMILY_VARIANTS: Dict[str, Tuple[str, ...]] = {
    "hitchhiker": ("default",),
    "rare_bridge": ("rescue_possible", "rescue_impossible"),
    "version_update": ("update_before", "update_after"),
    "harmful_stale": ("correction_visible", "no_correction"),
    "self_obscuring": ("crowding", "rescue_possible"),
    "scope_mismatch": ("future_in_s1", "future_in_s2"),
}
CONTROL_FAMILIES = ("stable_positive", "stable_negative", "neutral")

ENTITIES: Dict[str, Tuple[str, str]] = {
    "hitchhiker": ("john", "jane"),
    "rare_bridge": ("daniel", "dana"),
    "version_update": ("ethan", "emma"),
    "harmful_stale": ("lucas", "lily"),
    "self_obscuring": ("maya", "mia"),
    "scope_mismatch": ("oliver", "olivia"),
    "stable_positive": ("nathan", "nina"),
    "stable_negative": ("nathan", "nina"),
    "neutral": ("nathan", "nina"),
}

TOPIC_OF = {
    "hitchhiker": ("volunteer", "charity", "local", "food", "bank", "weekend"),
    "rare_bridge": ("passport", "drawer", "document", "storage", "safe"),
    "version_update": ("phone", "number", "contact", "call", "reach"),
    "harmful_stale": ("medication", "allergy", "morning", "daily", "dose"),
    "self_obscuring": ("medication", "allergy", "morning", "daily", "dose"),
    "scope_mismatch": ("finance", "budget", "project", "dollars", "quarter"),
    "stable_positive": ("schedule", "meeting", "plan", "week", "timeline"),
    "stable_negative": ("medication", "allergy", "morning", "daily", "dose"),
    "neutral": ("schedule", "meeting", "plan", "week", "timeline"),
}

N_PAIRS = 15


# ---------------------------------------------------------------------------
# episode construction
# ---------------------------------------------------------------------------
def build_episode(seed: int, family: str, variant: str, entity: str,
                  paired_key: Optional[str] = None) -> RealizedEpisode:
    """Deterministic: an episode is a pure function of its seed."""
    spec = build_spec(seed, family, variant, entity, TOPIC_OF[family],
                      paired_key)
    spec = replace(spec, episode_id=f"{family}-{variant}-{entity}-{seed}")
    ep = realize(spec)
    validate_episode(ep)
    return ep


def _flip_hitchhiker_slot5(world: WorldSpec, seed: int,
                           pair_id: int) -> WorldSpec:
    """Observation-equivalent twin: identical public trace, hidden needed id
    of slot 5 flips e1 -> h1, so the oracle action flips archive -> keep."""
    items = []
    for it in world.future_items:
        if it.slot == 5:
            t = it.task
            assert t is not None and t.slot == 5
            nt = TaskSpec(t.slot, t.scope, t.query_plan, "h1", "h1",
                          t.difficulty)
            items.append(FutureItemSpec(it.slot, "task", task=nt))
        else:
            items.append(it)
    return replace(
        world,
        episode_id=f"hitchhiker-pair-{pair_id}-flip-{seed}",
        paired_key=f"pair-{pair_id}",
        decision_action_label="keep",
        future_items=tuple(items))


def _main_episodes() -> List[Tuple[RealizedEpisode, Optional[str]]]:
    """1350 main episodes; returns (episode, paired_key)."""
    out: List[Tuple[RealizedEpisode, Optional[str]]] = []
    k = 0
    for family, variants in FAMILY_VARIANTS.items():
        per_bucket = EPISODES_PER_FAMILY // (
            len(variants) * len(ENTITIES[family]))
        for variant in variants:
            for entity in ENTITIES[family]:
                for _ in range(per_bucket):
                    out.append((build_episode(BASE_SEED + k, family,
                                              variant, entity), None))
                    k += 1
    for family in CONTROL_FAMILIES:
        entity = ENTITIES[family][0]
        for _ in range(CONTROL_EPISODES):
            out.append((build_episode(BASE_SEED + k, family, "default",
                                      entity), None))
            k += 1
    return out


def _pair_episodes() -> List[Tuple[RealizedEpisode, Optional[str]]]:
    """15 observation-equivalent pairs (30 episodes)."""
    out: List[Tuple[RealizedEpisode, Optional[str]]] = []
    for p in range(N_PAIRS):
        seed = PAIR_SEED + 2 * p
        spec = build_spec(seed, "hitchhiker", "default", "john",
                          TOPIC_OF["hitchhiker"], paired_key=f"pair-{p}")
        spec = replace(spec, episode_id=f"hitchhiker-pair-{p}-base-{seed}")
        ep_base = realize(spec)
        validate_episode(ep_base)
        flip = _flip_hitchhiker_slot5(spec, seed + 1, p)
        ep_flip = realize(flip)
        validate_episode(ep_flip)
        out.append((ep_base, f"pair-{p}"))
        out.append((ep_flip, f"pair-{p}"))
    return out


# ---------------------------------------------------------------------------
# group-level splits (22- 8): never split an episode's branches or a pair
# ---------------------------------------------------------------------------
def assign_splits(episodes: List[Tuple[RealizedEpisode, Optional[str]]],
                  pairs: List[Tuple[RealizedEpisode, Optional[str]]]) \
        -> Dict[str, str]:
    all_ep = episodes + pairs
    keys = []
    for ep, pair in all_ep:
        if pair is not None:
            key = f"pair-{pair}"
        else:
            key = (ep.world.family, ep.world.variant,
                   ep.memories[0].spec.entity)
        if key not in keys:
            keys.append(key)
    rng = random.Random(SPLIT_SEED)
    rng.shuffle(keys)
    n = len(keys)
    n_train = round(n * SPLIT_WEIGHTS[0])
    n_dev = round(n * SPLIT_WEIGHTS[1])
    split_of = {}
    for i, key in enumerate(keys):
        if i < n_train:
            split_of[key] = "train"
        elif i < n_train + n_dev:
            split_of[key] = "dev"
        else:
            split_of[key] = "test"
    out = {}
    for ep, pair in all_ep:
        key = f"pair-{pair}" if pair else (
            ep.world.family, ep.world.variant, ep.memories[0].spec.entity)
        out[ep.world.episode_id] = split_of[key]
    return out


def all_episodes() -> List[RealizedEpisode]:
    """All 1380 realized episodes (main + observation-equivalent pairs), for
    audit and baseline tools that recompute rollouts from seeds."""
    return [ep for ep, _ in _main_episodes() + _pair_episodes()]


# ---------------------------------------------------------------------------
# three-layer serialization
# ---------------------------------------------------------------------------
def _pid_of(ep: RealizedEpisode) -> Dict[str, str]:
    """Deterministic anonymous ids: mem1..memN, mapping pid -> fid."""
    return {f"mem{i + 1}": m.spec.fid
            for i, m in enumerate(ep.memories)}


def _public_entry(ep: RealizedEpisode, split: str,
                  pid: Dict[str, str]) -> Dict:
    pid_of_fid = {v: k for k, v in pid.items()}
    return {
        "episode_id": ep.world.episode_id,
        "split": split,
        "family": ep.world.family,
        "variant": ep.world.variant,
        "sessions": [
            {"speaker": m.speaker, "text": m.text, "kind": m.kind}
            for s in ep.sessions for m in s.messages
        ],
        "decision_task": {"query": ep.decision_task.query,
                          "scope": ep.decision_task.spec.scope},
        "decision_memory": pid_of_fid[ep.world.decision_fid],
        "future": [
            {"slot": it.spec.slot, "kind": it.spec.kind,
             "query": it.task.query if it.task is not None else None,
             "scope": it.task.spec.scope if it.task is not None else None,
             "event_text": it.text if it.spec.kind == "event" else None}
            for it in ep.future_items
        ],
        "memories": [
            {"pid": pid_of_fid[m.spec.fid], "text": m.text,
             "scope": m.spec.scope, "storage_tokens": m.spec.storage_tokens}
            for m in ep.memories
        ],
    }


def _log_entry(log: TaskLog, pid_of_fid: Dict[str, str]) -> Dict:
    return {
        "slot": log.slot,
        "query": log.query,
        "scope": log.scope,
        "candidates": [[pid_of_fid[f], round(s, 3), src]
                       for f, s, src in log.candidates],
        "workspace": [pid_of_fid[f] for f in log.workspace],
        "probes": [pid_of_fid[f] for f in log.probes],
        "restore": [pid_of_fid[f] for f in log.restore],
        "adopted": [pid_of_fid[f] for f in log.adopted],
        "storage_cost": round(log.storage_cost, 4),
        "exposure_cost": round(log.exposure_cost, 4),
        "probe_cost": round(log.probe_cost, 4),
        "store": sorted(pid_of_fid[f] for f in log.state.store),
        "archive": sorted(pid_of_fid[f] for f in log.state.archive),
        "certs": {pid_of_fid[f]: str(c.status)
                  for f, c in log.state.certs.items()},
    }


def _rollout_entry(roll: Rollout, pid_of_fid: Dict[str, str]) -> Dict:
    return {
        "slot0": _log_entry(roll.slot0, pid_of_fid),
        "slots": [_log_entry(l, pid_of_fid) for l in roll.logs],
    }


def _policy_entry(ep: RealizedEpisode, split: str, pid: Dict[str, str],
                  keep: Rollout, archive: Rollout) -> Dict:
    pid_of_fid = {v: k for k, v in pid.items()}
    return {
        "episode_id": ep.world.episode_id,
        "split": split,
        "policy": "reference_sqcad",
        "branch_keep": _rollout_entry(keep, pid_of_fid),
        "branch_archive": _rollout_entry(archive, pid_of_fid),
    }


def _hidden_entry(ep: RealizedEpisode, split: str, pid: Dict[str, str],
                  out: EpisodeOutcome) -> Dict:
    return {
        "episode_id": ep.world.episode_id,
        "split": split,
        "pair": ep.world.paired_key,
        "fid_map": pid,
        "labels": dataclasses.asdict(out),
    }


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def build_dataset(out_dir: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)

    main = _main_episodes()
    pairs = _pair_episodes()
    split_of = assign_splits(main, pairs)

    public, policy, hidden = [], [], []
    oracle_counts: Dict[str, Dict[str, int]] = {}
    for ep, _pair in main + pairs:
        split = split_of[ep.world.episode_id]
        paired = paired_rollout(ep)
        outcome = evaluate(ep, paired.keep, paired.archive)
        pid = _pid_of(ep)
        public.append(_public_entry(ep, split, pid))
        policy.append(_policy_entry(ep, split, pid, paired.keep,
                                    paired.archive))
        hidden.append(_hidden_entry(ep, split, pid, outcome))
        fam = ep.world.family
        oracle_counts.setdefault(fam, {}).setdefault(
            outcome.oracle_action, 0)
        oracle_counts[fam][outcome.oracle_action] += 1

    for name, rows in (("public.jsonl", public),
                       ("policy_log.jsonl", policy),
                       ("hidden.jsonl", hidden)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False,
                                   sort_keys=True) + "\n")

    manifest = {
        "version": VERSION,
        "horizon": HORIZON,
        "episodes_per_family": EPISODES_PER_FAMILY,
        "control_episodes": CONTROL_EPISODES,
        "observation_pairs": N_PAIRS,
        "policy": "reference_sqcad",
        "seeds": {"base": BASE_SEED, "pair": PAIR_SEED, "split": SPLIT_SEED},
        "split_weights": list(SPLIT_WEIGHTS),
        "splits": {k: v for k, v in split_of.items()},
        "counts": {"main": len(main), "pair_episodes": len(pairs),
                   "total": len(main) + len(pairs),
                   "oracle": oracle_counts},
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(os.path.join(out_dir, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
    return manifest
