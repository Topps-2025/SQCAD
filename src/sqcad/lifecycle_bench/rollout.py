"""Paired rollout wrapper (doc 22- 3.4 same-source counterfactual).

The two branches share the *entire* future event stream and the identical
pre-action state; the only allowed difference is the persistent action and
its downstream consequences.  The invariant check asserts exactly that:
slot 0 (which runs before the intervention) must be bit-identical across
branches, and the future item schedule must be the same sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .realizer import RealizedEpisode
from .world import Rollout, simulate_branch


@dataclass(frozen=True)
class PairedRollout:
    ep: RealizedEpisode
    keep: Rollout
    archive: Rollout


def paired_rollout(ep: RealizedEpisode) -> PairedRollout:
    """Run both branches of one episode under the frozen reference policy."""
    keep = simulate_branch(ep, "keep")
    archive = simulate_branch(ep, "archive")
    check_branch_invariance(ep, keep, archive)
    return PairedRollout(ep, keep, archive)


def check_branch_invariance(ep: RealizedEpisode, keep: Rollout,
                            archive: Rollout) -> None:
    """Assert the counterfactual contract: pre-action state and the future
    item schedule are branch-independent by construction."""
    if keep.slot0.workspace != archive.slot0.workspace:
        raise AssertionError(
            f"{ep.world.episode_id}: slot0 workspace differs between "
            f"branches ({keep.slot0.workspace} vs {archive.slot0.workspace})")
    if keep.slot0.adopted != archive.slot0.adopted:
        raise AssertionError(
            f"{ep.world.episode_id}: slot0 adoption differs between branches")
    if [i.spec.slot for i in ep.future_items] != list(range(1, 11)):
        raise AssertionError(
            f"{ep.world.episode_id}: future schedule must be slots 1..10")
    if len(keep.logs) != len(archive.logs):
        raise AssertionError(
            f"{ep.world.episode_id}: branch log lengths differ")
    for k, a in zip(keep.logs, archive.logs):
        if k.slot != a.slot or (k.query or "") != (a.query or ""):
            raise AssertionError(
                f"{ep.world.episode_id}: future item mismatch at slot {k.slot}")
