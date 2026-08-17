"""Independent Evaluator (doc 22- 5.4): computes the hidden counterfactual
labels from the paired rollouts.  The evaluator is the ONLY component that
reads gold; nothing it computes ever appears in the public trace.

Lifecycle value (doc 22- 2):
    V_s^pi(a) = sum_t GAMMA^t * u_t(slot t, branch a)
with u_t from the frozen cost contract (utilities() in world.py).

Labels produced:
    lifecycle_value_keep / _archive / tau_keep_archive / oracle_action,
    needed_future_ids, harmful_exposure per branch, rescue_possible,
    scope_validity, identification_regime, oracle_local_same.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from .frozen import GAMMA, TAU_TOL
from .realizer import RealizedEpisode
from .world import Rollout, utilities


def discounted_value(ep: RealizedEpisode, roll: Rollout) -> float:
    us = utilities(ep, roll)
    return float(sum(u * GAMMA ** i for i, u in enumerate(us)))


@dataclass(frozen=True)
class EpisodeOutcome:
    episode_id: str
    family: str
    variant: str
    regime: str
    paired_key: Optional[str]
    decision_fid: str
    decision_scope: str
    decision_action_label: str
    lifecycle_value_keep: float
    lifecycle_value_archive: float
    tau_keep_archive: float
    oracle_action: str                      # keep | archive | neutral
    needed_future_ids: Tuple[str, ...]
    harmful_exposure_keep: int
    harmful_exposure_archive: int
    rescue_possible: bool
    scope_validity: bool
    identification_regime: str
    oracle_local_same: bool


def oracle_of(tau: float) -> str:
    if tau > TAU_TOL:
        return "keep"
    if tau < -TAU_TOL:
        return "archive"
    return "neutral"


def evaluate(ep: RealizedEpisode, keep: Rollout,
             archive: Rollout) -> EpisodeOutcome:
    """Hidden labels for one episode (paired rollout inputs)."""
    v_keep = discounted_value(ep, keep)
    v_archive = discounted_value(ep, archive)
    tau = v_keep - v_archive

    needed = ep.world.needed_future_ids
    rescue = archive.rescued(ep.world.decision_fid)

    return EpisodeOutcome(
        episode_id=ep.world.episode_id,
        family=ep.world.family,
        variant=ep.world.variant,
        regime=ep.world.regime,
        paired_key=ep.world.paired_key,
        decision_fid=ep.world.decision_fid,
        decision_scope=ep.world.decision_scope,
        decision_action_label=ep.world.decision_action_label,
        lifecycle_value_keep=round(v_keep, 4),
        lifecycle_value_archive=round(v_archive, 4),
        tau_keep_archive=round(tau, 4),
        oracle_action=oracle_of(tau),
        needed_future_ids=needed,
        harmful_exposure_keep=keep.harmful_exposure,
        harmful_exposure_archive=archive.harmful_exposure,
        rescue_possible=rescue,
        scope_validity=ep.world.decision_fid in needed,
        identification_regime=ep.world.regime,
        oracle_local_same=(
            keep.slot0.workspace == archive.slot0.workspace
            and keep.slot0.adopted == archive.slot0.adopted),
    )
