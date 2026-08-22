"""Decision-identification-aware qualification and access primitives.

This module is deliberately separate from ``public_unified_contract``.  The
public QA traces contain evidence-recall labels, but not the interventions or
long-run outcomes needed to estimate a persistent-access lifecycle contrast.
It would therefore be unsound to turn a BM25 score in that runner into a
causal authorization.  These primitives are for the controlled and
semi-synthetic protocol where such evidence is available.

Design boundary
---------------
* Retrieval scores may propose and rank *eligible* candidates.
* Only a qualification certificate can authorize a persistent action.
* An interval that crosses the keep/archive boundary never commits.  It can
  only defer or buy a pre-specified probe.
* A probe is prioritized by expected decision-risk reduction per cost; a
  retrieval score is only a deterministic tie breaker.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .decision_identification_theory import r_star
from .safe_recovery_theory import anytime_boundary


class QualificationStatus(str, Enum):
    """Scoped status of the keep-vs-archive lifecycle contrast."""

    POINT = "point"
    BOUND = "bound"
    UNRESOLVED = "unresolved"
    MISMATCH = "mismatch"


class PersistentAction(str, Enum):
    KEEP = "keep"
    ARCHIVE = "archive"
    RESTORE = "restore"


class GovernanceAction(str, Enum):
    KEEP = "keep"
    ARCHIVE = "archive"
    PROBE = "probe"
    DEFER = "defer"


@dataclass(frozen=True)
class ScopeKey:
    """The scope for which an authorization is valid.

    A certificate must not silently transfer across any of these fields.
    Callers may use stable ids instead of raw user/model metadata.
    """

    task_family: str
    user_partition: str
    tool_version: str
    model_version: str
    policy_version: str


@dataclass(frozen=True)
class QualificationCertificate:
    """Auditable evidence for a *persistent* keep-vs-archive decision.

    ``lower`` and ``upper`` bound
    ``V(keep) - V(archive)`` in this certificate's scope.  Positive values
    authorize keep, negative values authorize archive.  The source ids and
    diagnostics are immutable audit handles; their interpretation remains
    external to this small domain object.
    """

    memory_id: str
    scope: ScopeKey
    status: QualificationStatus
    lower: Optional[float]
    upper: Optional[float]
    evidence_ids: Tuple[str, ...] = ()
    diagnostics: Tuple[str, ...] = ()
    expires_at_epoch: Optional[int] = None

    def __post_init__(self) -> None:
        if self.status in (QualificationStatus.POINT,
                           QualificationStatus.BOUND):
            if self.lower is None or self.upper is None:
                raise ValueError("point/bound certificates require [lower, upper]")
            if self.lower > self.upper:
                raise ValueError("qualification lower bound exceeds upper bound")
        elif ((self.lower is None) != (self.upper is None)):
            raise ValueError("an interval must provide both endpoints or neither")

    @property
    def has_interval(self) -> bool:
        return self.lower is not None and self.upper is not None

    def authorized_action(self) -> Optional[PersistentAction]:
        """Return an action only when the interval is on one side of zero."""
        if self.status not in (QualificationStatus.POINT,
                               QualificationStatus.BOUND):
            return None
        assert self.lower is not None and self.upper is not None
        if self.lower > 0.0:
            return PersistentAction.KEEP
        if self.upper < 0.0:
            return PersistentAction.ARCHIVE
        return None


def anytime_qualification_certificate(
        memory_id: str,
        scope: ScopeKey,
        observations: Sequence[float],
        *,
        sigma: float,
        alpha: float,
        evidence_ids: Tuple[str, ...] = (),
        ) -> QualificationCertificate:
    """Build the Theorem-13 anytime certificate from successful probes.

    The returned interval is auditable and conservative: a persistent action
    is authorized only when the confidence interval is strictly on one side
    of zero.  A crossing interval remains ``UNRESOLVED``; callers may append a
    later successful-probe observation and call this function again.  This is
    deliberately a pure function so the stopping rule cannot silently use
    failed-probe counts as statistical samples.
    """
    if sigma <= 0.0 or not 0.0 < alpha < 1.0:
        raise ValueError("sigma must be positive and alpha must lie in (0, 1)")
    values = tuple(float(x) for x in observations)
    if not all(math.isfinite(x) for x in values):
        raise ValueError("observations must be finite real numbers")
    if not values:
        return QualificationCertificate(
            memory_id, scope, QualificationStatus.UNRESOLVED, None, None,
            evidence_ids=evidence_ids,
            diagnostics=("n=0", f"alpha={alpha:g}"),
        )
    n = len(values)
    mean = sum(values) / n
    radius = anytime_boundary(n, sigma, alpha)
    lower, upper = mean - radius, mean + radius
    status = QualificationStatus.BOUND
    if lower <= 0.0 <= upper:
        status = QualificationStatus.UNRESOLVED
    return QualificationCertificate(
        memory_id, scope, status, lower, upper,
        evidence_ids=evidence_ids,
        diagnostics=(f"n={n}", f"sigma={sigma:g}", f"alpha={alpha:g}",
                     f"radius={radius:.12g}"),
    )


@dataclass
class SequentialQualificationGate:
    """Stateful terminal wrapper for the Theorem-13 certificate gate.

    The pure ``anytime_qualification_certificate`` function is convenient for
    replay, but it cannot by itself enforce the Safe-class lifecycle rule that
    no probe is accepted after terminal keep/archive.  This wrapper enforces
    that rule and makes horizon close explicit.  It does not estimate ``sigma``,
    ``rho`` or the attempt rate; those remain caller-supplied contract fields.
    """

    memory_id: str
    scope: ScopeKey
    sigma: float
    alpha: float
    evidence_ids: Tuple[str, ...] = ()
    _observations: Tuple[float, ...] = field(default_factory=tuple, init=False,
                                             repr=False)
    _evidence_trace: Tuple[str, ...] = field(default_factory=tuple, init=False,
                                               repr=False)
    _certificate: Optional[QualificationCertificate] = field(
        default=None, init=False, repr=False)
    _terminal_action: Optional[PersistentAction] = field(
        default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.sigma <= 0.0 or not 0.0 < self.alpha < 1.0:
            raise ValueError("sigma must be positive and alpha must lie in (0, 1)")
        self._evidence_trace = tuple(self.evidence_ids)

    @property
    def observations(self) -> Tuple[float, ...]:
        return self._observations

    @property
    def certificate(self) -> QualificationCertificate:
        if self._certificate is None:
            return anytime_qualification_certificate(
                self.memory_id, self.scope, (), sigma=self.sigma,
                alpha=self.alpha, evidence_ids=self.evidence_ids)
        return self._certificate

    @property
    def terminal_action(self) -> Optional[PersistentAction]:
        return self._terminal_action

    @property
    def is_terminal(self) -> bool:
        return self._closed or self._terminal_action is not None

    def observe(self, value: float,
                evidence_id: Optional[str] = None) -> QualificationCertificate:
        """Append one successful-probe observation before terminal close."""
        if self.is_terminal:
            raise RuntimeError("terminal qualification gate rejects new probes")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("observations must be finite real numbers")
        self._observations = self._observations + (value,)
        ids = self._evidence_trace
        if evidence_id is not None:
            ids = ids + (str(evidence_id),)
        self._evidence_trace = ids
        self._certificate = anytime_qualification_certificate(
            self.memory_id, self.scope, self._observations,
            sigma=self.sigma, alpha=self.alpha, evidence_ids=ids)
        action = self._certificate.authorized_action()
        if action in (PersistentAction.KEEP, PersistentAction.ARCHIVE):
            self._terminal_action = action
        return self._certificate

    def close_horizon(self) -> QualificationCertificate:
        """Stop probing at horizon; unresolved evidence remains non-authorizing."""
        self._closed = True
        return self.certificate


@dataclass(frozen=True)
class ProbeOption:
    """Pre-registered expected post-probe identification interval and cost."""

    memory_id: str
    cost: float
    post_lower: float
    post_upper: float
    evidence_type: str = "micro_intervention"

    def __post_init__(self) -> None:
        if self.cost < 0.0:
            raise ValueError("probe cost must be non-negative")
        if self.post_lower > self.post_upper:
            raise ValueError("post-probe lower bound exceeds upper bound")

    @property
    def post_decision_risk(self) -> float:
        return r_star(self.post_lower, self.post_upper)


@dataclass(frozen=True)
class ActionDecision:
    memory_id: str
    action: GovernanceAction
    expected_risk: float
    reason: str


def decide_persistent_action(certificate: QualificationCertificate,
                             defer_cost: float,
                             probe: Optional[ProbeOption] = None,
                             ) -> ActionDecision:
    """Apply the strict action-boundary rule.

    This function intentionally differs from a generic minimax committing
    rule: a crossing interval is not allowed to commit.  It selects between
    defer and a probe that can reduce the future decision risk.  That is the
    minimal authorization condition used by SQCAD's framework claim.
    """
    if defer_cost < 0.0:
        raise ValueError("defer cost must be non-negative")
    action = certificate.authorized_action()
    if action is PersistentAction.KEEP:
        return ActionDecision(certificate.memory_id, GovernanceAction.KEEP,
                              0.0, "interval_strictly_positive")
    if action is PersistentAction.ARCHIVE:
        return ActionDecision(certificate.memory_id,
                              GovernanceAction.ARCHIVE, 0.0,
                              "interval_strictly_negative")
    if certificate.status is QualificationStatus.MISMATCH:
        return ActionDecision(certificate.memory_id, GovernanceAction.DEFER,
                              defer_cost, "scope_or_version_mismatch")

    if probe is not None and probe.memory_id != certificate.memory_id:
        raise ValueError("probe and certificate memory_id differ")
    if probe is not None:
        probe_risk = probe.cost + probe.post_decision_risk
        if probe_risk < defer_cost:
            return ActionDecision(certificate.memory_id,
                                  GovernanceAction.PROBE, probe_risk,
                                  "probe_reduces_decision_risk")
    return ActionDecision(certificate.memory_id, GovernanceAction.DEFER,
                          defer_cost, "interval_crosses_action_boundary")


def probe_value(defer_cost: float, probe: ProbeOption) -> float:
    """Expected reduction in decision risk obtained by buying ``probe``."""
    if defer_cost < 0.0:
        raise ValueError("defer cost must be non-negative")
    return defer_cost - (probe.cost + probe.post_decision_risk)


@dataclass(frozen=True)
class AccessCandidate:
    """A retrieval proposal plus its authorization state.

    ``retrieval_score`` can originate from BM25, dense retrieval, or another
    frozen proposer.  It never appears in ``decide_persistent_action``.
    """

    memory_id: str
    retrieval_score: float
    certificate: QualificationCertificate
    persistent: bool

    def __post_init__(self) -> None:
        if self.memory_id != self.certificate.memory_id:
            raise ValueError("candidate and certificate memory_id differ")


@dataclass(frozen=True)
class AccessPlan:
    exposure_ids: Tuple[str, ...]
    probe_ids: Tuple[str, ...]
    persistent_actions: Mapping[str, PersistentAction]
    decisions: Mapping[str, ActionDecision]


def plan_access(candidates: Iterable[AccessCandidate], *,
                workspace_budget: int, probe_budget: int,
                defer_cost: float,
                probes: Mapping[str, ProbeOption],
                ) -> AccessPlan:
    """Project authorization-compatible candidates into a bounded workspace.

    Non-persistent unresolved candidates enter the workspace only through a
    selected probe.  A non-persistent positive certificate becomes ``restore``
    only when it both enters the workspace and is already authorized.  Thus a
    high BM25 score alone cannot create a persistent write.
    """
    if workspace_budget < 0 or probe_budget < 0:
        raise ValueError("budgets must be non-negative")
    items = tuple(candidates)
    ids = [c.memory_id for c in items]
    if len(set(ids)) != len(ids):
        raise ValueError("access candidates must have unique memory ids")

    decisions: Dict[str, ActionDecision] = {
        c.memory_id: decide_persistent_action(
            c.certificate, defer_cost, probes.get(c.memory_id))
        for c in items
    }
    by_id = {c.memory_id: c for c in items}
    probe_ranked = sorted(
        (mid for mid, d in decisions.items() if d.action is GovernanceAction.PROBE),
        key=lambda mid: (-probe_value(defer_cost, probes[mid]),
                         -by_id[mid].retrieval_score, mid),
    )
    probe_ids = tuple(probe_ranked[:probe_budget])
    probe_set = set(probe_ids)

    eligible = []
    for candidate in items:
        decision = decisions[candidate.memory_id]
        if candidate.persistent and decision.action is not GovernanceAction.ARCHIVE:
            eligible.append(candidate)
        elif not candidate.persistent:
            # A valid positive certificate may restore only after it gets an
            # actual exposure slot; unresolved proposals require a probe.
            if decision.action is GovernanceAction.KEEP or candidate.memory_id in probe_set:
                eligible.append(candidate)

    ranked = sorted(eligible,
                    key=lambda c: (-c.retrieval_score, c.memory_id))
    exposure_ids = tuple(c.memory_id for c in ranked[:workspace_budget])
    exposure_set = set(exposure_ids)

    persistent_actions: Dict[str, PersistentAction] = {}
    for candidate in items:
        decision = decisions[candidate.memory_id]
        if candidate.persistent and decision.action is GovernanceAction.ARCHIVE:
            persistent_actions[candidate.memory_id] = PersistentAction.ARCHIVE
        elif candidate.persistent and decision.action is GovernanceAction.KEEP:
            persistent_actions[candidate.memory_id] = PersistentAction.KEEP
        elif (not candidate.persistent
              and decision.action is GovernanceAction.KEEP
              and candidate.memory_id in exposure_set):
            persistent_actions[candidate.memory_id] = PersistentAction.RESTORE

    return AccessPlan(exposure_ids=exposure_ids, probe_ids=probe_ids,
                      persistent_actions=persistent_actions,
                      decisions=decisions)
