"""R3: unseen-mechanism holdout (23- 6.4, fairness channel "generalization
can be challenged").

The MVP scenarios fix one structural geometry per family (rescue slots,
crowding filler counts, entities, task difficulties, decision-memory
storage).  R3 rebuilds episodes under structural knobs that were NOT used
at design time and re-runs the full pipeline (realize -> validate ->
paired rollout -> evaluate).  Oracle labels are recomputed honestly from
the counterfactual values, so the audit measures whether the designed
*mechanisms* transfer to unseen geometry:

  * a slot-shifted rescue task (different discount position),
  * a different crowding pressure (filler count),
  * a held-out entity name,
  * a different future-task difficulty,
  * a different decision-memory storage size,
  * a moved observation-equivalent flip slot.

Reported per (family, variant, knob):
  * oracle agreement with the design label -- should stay ~1.0 if the
    mechanism transfers;
  * reference-branch-advantage rate -- the keep/archive ordering the design
    intended should persist;
  * per-family reversals -- a knob that flips the oracle the OTHER way is a
    genuine generalization finding, not a label error (the evaluator is
    the same honest counterfactual).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Dict, List, Optional, Tuple

from .audit import R3_EPISODES_PER_BUCKET, R3_KNOBS, R3_SEED_BASE
from .evaluator import EpisodeOutcome, evaluate, oracle_of
from .frozen import HORIZON
from .generator import FAMILY_VARIANTS, TOPIC_OF, build_episode
from .realizer import RealizedEpisode, realize, validate_episode
from .rollout import paired_rollout
from .scenarios import FutureItemSpec, MemorySpec, SessionSpec, TaskSpec, WorldSpec

# held-out entities (never used by the MVP design; per-family pools keep the
# realized texts natural -- any name would do, these just never appear in
# the main dataset)
UNSEEN_ENTITIES = ("robert", "ruth", "henry", "hannah", "oscar", "olive",
                   "peter", "paula", "simon", "susan", "thomas", "tina",
                   "victor", "vera", "walter", "wendy")

_KNOB_DIFFICULTIES = (1.5, 2.0)
_KNOB_STORAGE = (6, 12)
_SLOT_SHIFTS = {  # family -> variant -> allowed new rescue slots
    "rare_bridge": {"rescue_possible": (3, 4, 5),
                    "rescue_impossible": (6, 7, 9)},
    "self_obscuring": {"crowding": (6, 7, 9),
                       "rescue_possible": (3, 4, 5)},
}
_CROWDING_COUNTS = (12, 20)
_PAIR_FLIP_SLOTS = (3, 7)


def _family_variant_buckets() -> List[Tuple[str, str]]:
    out = [(f, v) for f, vs in FAMILY_VARIANTS.items() for v in vs]
    out += [("stable_positive", "default"), ("stable_negative", "default"),
            ("neutral", "default")]
    out += [("hitchhiker_pair", "default")]
    return out


def _entity_for(seed: int) -> str:
    return UNSEEN_ENTITIES[seed % len(UNSEEN_ENTITIES)]


def _shift_task_slot(spec: WorldSpec, task_slot: int, new_slot: int) -> WorldSpec:
    """Move the task at ``task_slot`` to ``new_slot`` and renumber 1..HORIZON."""
    items = list(spec.future_items)
    moved = None
    for i, it in enumerate(items):
        if it.slot == task_slot:
            moved = items.pop(i)
            break
    assert moved is not None, f"{spec.episode_id}: no task at slot {task_slot}"
    assert 1 <= new_slot <= HORIZON
    items.insert(new_slot - 1, moved)
    ren = []
    for i, it in enumerate(items, 1):
        if it.kind == "event":
            ren.append(replace(it, slot=i))
        else:
            ren.append(replace(it, slot=i, task=replace(it.task, slot=i)))
    return replace(spec, future_items=tuple(ren))


def _replace_crowding_fillers(spec: WorldSpec, count: int) -> WorldSpec:
    mems = []
    for m in spec.memories:
        if m.fid.startswith("f_med"):
            idx = int(m.fid.split("_med")[1])
            if idx > count:
                continue
        mems.append(m)
    return replace(spec, memories=tuple(mems))


def _replace_entity(spec: WorldSpec, entity: str) -> WorldSpec:
    return replace(
        spec,
        memories=tuple(replace(m, entity=entity) for m in spec.memories))


def _replace_difficulty(spec: WorldSpec, difficulty: float) -> WorldSpec:
    items = []
    for it in spec.future_items:
        if it.kind == "task":
            items.append(replace(it, task=replace(it.task,
                                                  difficulty=difficulty)))
        else:
            items.append(it)
    return replace(spec, future_items=tuple(items))


def _replace_storage(spec: WorldSpec, fid: str, tokens: int) -> WorldSpec:
    return replace(
        spec,
        memories=tuple(
            replace(m, storage_tokens=tokens) if m.fid == fid else m
            for m in spec.memories))


def _flip_pair_slot(spec: WorldSpec, flip_slot: int) -> WorldSpec:
    items = []
    for it in spec.future_items:
        if it.slot == flip_slot:
            t = it.task
            nt = TaskSpec(t.slot, t.scope, t.query_plan, "h1", "h1",
                          t.difficulty)
            items.append(replace(it, task=nt))
        else:
            items.append(it)
    # the flip side of the observation-equivalent pair is labeled keep
    # (mirrors generator._pair_episodes: base=archive, flip=keep on the
    # same public trace)
    return replace(spec, future_items=tuple(items),
                   decision_action_label="keep")


def _knob_episodes(bucket: Tuple[str, str], knob: str) -> List[RealizedEpisode]:
    """Build R3_EPISODES_PER_BUCKET episodes for one (family, variant,
    knob) cell with fresh seeds.  Episodes are pure functions of seeds, so
    this is deterministic and independent of the main dataset's geometry
    (different seed range + structural transforms)."""
    family, variant = bucket
    out: List[RealizedEpisode] = []
    for i in range(R3_EPISODES_PER_BUCKET):
        seed = R3_SEED_BASE + i + sum(ord(c) for c in family + variant)
        if family == "hitchhiker_pair":
            spec = build_spec_pair(seed, variant, _entity_for(seed))
        else:
            ep = build_episode(seed, family, variant, _entity_for(seed),
                               TOPIC_OF[family])
            spec = ep.world
        if knob == "entity":
            pass  # entity already held-out via _entity_for
        elif knob == "difficulty":
            spec = _replace_difficulty(spec, _KNOB_DIFFICULTIES[i % 2])
        elif knob == "slot_shift":
            if family == "hitchhiker_pair":
                # move the crowding task (slot 5) to an unseen slot and
                # flip the hidden needed id THERE (observation-equivalence
                # must hold at any slot: same trace, oracle flips)
                new_slot = _PAIR_FLIP_SLOTS[i % len(_PAIR_FLIP_SLOTS)]
                spec = _shift_task_slot(spec, 5, new_slot)
                spec = _flip_pair_slot(spec, new_slot)
            else:
                slot_map = _SLOT_SHIFTS.get(family, {}).get(variant)
                if slot_map is not None:
                    old_slot = 2 if variant == "rescue_possible" else 8
                    new_slot = slot_map[i % len(slot_map)]
                    spec = _shift_task_slot(spec, old_slot, new_slot)
                else:
                    spec = _replace_storage(
                        spec, _decision_fid_of(family), _KNOB_STORAGE[i % 2])
        if family == "hitchhiker_pair":
            ep = _realize_pair(spec, seed)
        else:
            ep = _realize_spec(spec)
        out.append(ep)
    return out


def build_spec_pair(seed: int, variant: str, entity: str) -> WorldSpec:
    """The base side of an observation-equivalent pair with a fresh seed
    (mirrors generator._pair_episodes without the pair bookkeeping)."""
    from .scenarios import build_spec
    return build_spec(seed, "hitchhiker", "default", entity,
                      TOPIC_OF["hitchhiker"], paired_key=None)


def _decision_fid_of(family: str) -> str:
    return {"hitchhiker": "h1", "rare_bridge": "m1",
            "version_update": "m_old", "harmful_stale": "m_stale",
            "self_obscuring": "m1", "scope_mismatch": "m1",
            "stable_positive": "m1", "stable_negative": "m1",
            "neutral": "m1"}[family]


def _realize_spec(spec: WorldSpec) -> RealizedEpisode:
    ep = realize(spec)
    validate_episode(ep)
    return ep


def _realize_pair(spec: WorldSpec, seed: int) -> RealizedEpisode:
    spec = replace(spec, episode_id=f"hitchhiker-pair-r3-flip-{seed}")
    ep = realize(spec)
    validate_episode(ep)
    return ep


def _design_label(spec: WorldSpec) -> str:
    return spec.decision_action_label


def _pair_flip_confirmation() -> float:
    """hitchhiker-pair slot_shift semantics: observation-equivalence must
    survive at ANY slot -- both sides keep agreeing with their labels on
    the SAME public trace: base (needed e1) oracle=archive, flip (needed
    h1) oracle=keep.  A label is only transferred if BOTH sides hold."""
    conf = 0
    total = R3_EPISODES_PER_BUCKET
    for i in range(total):
        seed = R3_SEED_BASE + i + sum(ord(c) for c in "hitchhiker_pair")
        spec = build_spec_pair(seed, "default", _entity_for(seed))
        new_slot = _PAIR_FLIP_SLOTS[i % len(_PAIR_FLIP_SLOTS)]
        spec = _shift_task_slot(spec, 5, new_slot)
        base = _realize_pair(spec, seed)
        flip = _realize_pair(_flip_pair_slot(spec, new_slot), seed)
        p_base, p_flip = paired_rollout(base), paired_rollout(flip)
        o_base = evaluate(base, p_base.keep, p_base.archive).oracle_action
        o_flip = evaluate(flip, p_flip.keep, p_flip.archive).oracle_action
        conf += (o_base == "archive" and o_flip == "keep")
    return conf / total


def run_audit() -> Dict[str, Any]:
    """Full R3 audit: every (family, variant) x knob cell."""
    cells: Dict[str, Any] = {}
    for bucket in _family_variant_buckets():
        fam, var = bucket
        cell = {}
        for knob in R3_KNOBS:
            eps = _knob_episodes(bucket, knob)
            agree, adv_keep, adv_archive, rev = 0, 0, 0, []
            n = len(eps)
            for ep in eps:
                label = _design_label(ep.world)
                pr = paired_rollout(ep)
                out = evaluate(ep, pr.keep, pr.archive)
                # oracle agreement with the design intent
                if label == "neutral":
                    agree += (out.oracle_action == "neutral")
                elif label == "keep":
                    agree += (out.oracle_action == "keep")
                else:
                    agree += (out.oracle_action == "archive")
                # reference-branch-advantage persistence (tau sign)
                if label == "keep":
                    adv_keep += (out.tau_keep_archive > 0.0)
                elif label == "archive":
                    adv_archive += (out.tau_keep_archive < 0.0)
                # reversals: computed oracle opposite to the design intent
                if label in ("keep", "archive") and \
                        out.oracle_action != label and \
                        out.oracle_action != "neutral":
                    rev.append({"id": ep.world.episode_id,
                                "designed": label,
                                "computed": out.oracle_action,
                                "tau": out.tau_keep_archive})
            stats = {
                "n": n,
                "oracle_agreement": round(agree / n, 4),
                "advantage_persists": round(
                    (adv_keep + adv_archive) / n, 4),
                "reversals": rev,
            }
            if fam == "hitchhiker_pair" and knob == "slot_shift":
                stats["pair_flip_confirmed"] = _pair_flip_confirmation()
            cell[knob] = stats
        cells[f"{fam}/{var}"] = cell
    return {"cells": cells,
            "knobs": list(R3_KNOBS),
            "seed_base": R3_SEED_BASE,
            "episodes_per_cell": R3_EPISODES_PER_BUCKET}
