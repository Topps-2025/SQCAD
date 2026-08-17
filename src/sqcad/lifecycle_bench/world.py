"""World Simulator + frozen reference policy for SQCAD-LifecycleBench
(doc 22- 5.3, 4 Policy Log Layer).

The world maintains user/task/memory/tool/risk and candidate-generator
state.  At the decision point the state is forked; the future event stream
(queries, updates, corrections, tool returns) is *shared* by both branches
-- the only allowed difference is the persistent action (keep/archive) and
its downstream consequences.  Outcomes, risks, candidate changes and task
success are decided by auditable rules; LLM/text generation never decides
truth.

Reference policy (frozen, gold-free -- it reads only public observables):

* certificate at the decision point, from pre-decision sessions only:
    MISMATCH       memory scope != decision scope
    NEGATIVE       a visible update/correction event overlaps the memory
                   (or targets its fid)
    UNRESOLVED     version/lineage conflict with another same-scope fact,
                   or the memory is a co-exposure hitchhiker (Prop A), or
                   no other signal
    POSITIVE       adopted by the decision task and no negative signal
  A NEGATIVE certificate attenuates natural exposure and forbids probes;
  an UNRESOLVED certificate keeps the memory exposed but allows probes.
* per task: at most PROBE_BUDGET_PER_TASK probes at the strongest-overlap
  archived memory (scope gate, non-negative certificate,
  overlap >= PROBE_THRESHOLD); a probed memory earns a workspace slot and a
  permanent restore only if its proposer score strictly exceeds the lowest
  score of the current workspace (budgeted competitive access, 16-);
* a future update/correction event re-qualifies a memory to NEGATIVE
  (version/lineage gate, E1/E2 overlay semantics), archiving it; an update
  event also creates the new-version fact as POSITIVE.

Costs (frozen in ``frozen.py``) are charged to the policy log; the
evaluator discounts them with the same contract.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .frozen import (
    ADOPT_THRESHOLD, FREQUENCY_W, HARM_PENALTY, NEGATIVE_ATTENUATION,
    PROBE_BUDGET_PER_TASK, PROBE_COST, PROBE_THRESHOLD, RECENCY_W,
    REQUALIFY_OVERLAP, TASK_VALUE, WORKSPACE_BUDGET,
)
from .realizer import RealizedEpisode, RealizedFutureItem, RealizedTask, overlap
from .scenarios import WorldSpec


# ---------------------------------------------------------------------------
# certificate model (reference policy, observable-only)
# ---------------------------------------------------------------------------
class Cert(str):
    """One of: positive / unresolved / negative / mismatch."""


POSITIVE = Cert("positive")
UNRESOLVED = Cert("unresolved")
NEGATIVE = Cert("negative")
MISMATCH = Cert("mismatch")


@dataclass(frozen=True)
class CertificateRecord:
    fid: str
    status: Cert
    reason: str


_CONFLICT_ROLES = {"old", "new", "critical", "evidence"}


def reference_certificate(ep: RealizedEpisode, fid: str,
                          decision_scope: str) -> CertificateRecord:
    """Gold-free qualification: only pre-decision sessions are consulted."""
    m = ep.memory(fid)
    if m.spec.scope != decision_scope and m.spec.scope != "any":
        return CertificateRecord(fid, MISMATCH, "scope_outside_decision_scope")

    # visible update/correction events before the decision point.  An update
    # event only re-qualifies the fact it targets (its text carries the NEW
    # value, which must not drag the new-version fact into NEGATIVE); a
    # correction re-qualifies by lexical overlap too.
    for sess in ep.sessions:
        for msg in sess.messages:
            if msg.kind == "update":
                if msg.fid == fid:
                    return CertificateRecord(fid, NEGATIVE, "event_targets_fid")
            elif msg.kind == "correction":
                if msg.fid == fid:
                    return CertificateRecord(fid, NEGATIVE, "event_targets_fid")
                if overlap(_toks(msg.text), ep.tokens(fid)) >= REQUALIFY_OVERLAP:
                    return CertificateRecord(fid, NEGATIVE, "event_overlap")

    # version/lineage conflict: both sides must be version-carrying facts
    # (old/new/critical/evidence), both introduced, and the counterpart must
    # not already be event-resolved (an event-corrected fact is not a
    # "conflicting version" -- its successor is the live one).
    conflict = None
    if m.spec.role in _CONFLICT_ROLES:
        for other in ep.memories:
            if other.spec.fid == fid or other.spec.role not in _CONFLICT_ROLES:
                continue
            if not other.spec.introduced:
                continue
            if (other.spec.entity == m.spec.entity
                    and other.spec.slot == m.spec.slot
                    and other.spec.scope == m.spec.scope):
                if overlap(ep.tokens(other.spec.fid), ep.tokens(fid)) >= 3:
                    if _event_resolved(ep, other.spec.fid):
                        continue
                    conflict = other.spec.fid
                    break
    if conflict is not None:
        return CertificateRecord(fid, UNRESOLVED,
                                 f"lineage_conflict_with_{conflict}")

    # hitchhiker: high co-exposure with evidence, no independent signal
    if m.spec.role == "hitchhiker":
        return CertificateRecord(fid, UNRESOLVED, "association_only_hitchhiker")

    # adopted by the decision task -> positive
    q0 = ep.decision_task
    if overlap(q0.tokens, ep.tokens(fid)) >= ADOPT_THRESHOLD:
        return CertificateRecord(fid, POSITIVE, "adopted_at_decision_task")
    return CertificateRecord(fid, UNRESOLVED, "no_observable_signal")


def _event_resolved(ep: RealizedEpisode, fid: str) -> bool:
    """True if a pre-decision event already resolved ``fid`` to NEGATIVE."""
    for sess in ep.sessions:
        for msg in sess.messages:
            if msg.kind in ("update", "correction") and msg.fid == fid:
                return True
    return False


def _toks(text: str):
    from .realizer import tokenize
    return tokenize(text)


# ---------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------
@dataclass
class TaskLog:
    slot: int
    query: Optional[str] = None
    scope: Optional[str] = None
    difficulty: float = 1.0
    candidates: List[Tuple[str, float, str]] = field(default_factory=list)
    workspace: Tuple[str, ...] = ()
    probes: Tuple[str, ...] = ()
    restore: Tuple[str, ...] = ()
    adopted: Tuple[str, ...] = ()
    needed: Optional[str] = None
    success: bool = False
    penalties: Tuple[Tuple[str, float], ...] = ()
    utility: float = 0.0
    storage_cost: float = 0.0
    exposure_cost: float = 0.0
    probe_cost: float = 0.0
    state: Optional["WorldState"] = None     # post-task state snapshot


@dataclass
class WorldState:
    store: set                       # fids physically in the persistent store
    archive: set
    certs: Dict[str, CertificateRecord]
    exposure_count: Dict[str, int]
    last_exposed: Dict[str, int]     # slot of last exposure (recency)
    exposed_at_prev: set             # exposed at the previous task item


def proposer_score(ep: RealizedEpisode, fid: str, q_tokens: Tuple[str, ...],
                   st: WorldState) -> float:
    m = ep.memory(fid)
    score = float(overlap(q_tokens, m.tokens))
    if st.exposed_at_prev and fid in st.exposed_at_prev:
        score += RECENCY_W
    if st.exposure_count.get(fid, 0):
        score += FREQUENCY_W * math.log1p(st.exposure_count[fid])
    if st.certs.get(fid, UNRESOLVED).status is NEGATIVE:
        score -= NEGATIVE_ATTENUATION
    return score


def simulate_task(ep: RealizedEpisode, item: RealizedFutureItem, slot: int,
                  st: WorldState) -> TaskLog:
    """One future task under the frozen reference policy."""
    t = item.task
    assert t is not None, f"slot {slot}: item kind=task without task spec"
    log = TaskLog(slot=slot, difficulty=t.spec.difficulty)
    q = t.tokens
    log.query, log.scope = t.query, t.spec.scope
    log.needed = t.spec.needed_fid

    # candidates from the persistent store (scope gate + negative attenuation)
    candidates = []
    for fid in sorted(st.store):
        m = ep.memory(fid)
        if m.spec.scope != t.spec.scope and m.spec.scope != "any":
            continue
        candidates.append((fid, proposer_score(ep, fid, q, st), "store"))
    candidates.sort(key=lambda c: (-c[1], _tie_key(c[0])))
    workspace = [fid for fid, _, _ in candidates][:WORKSPACE_BUDGET]
    min_score = min((s for _, s, _ in candidates[:WORKSPACE_BUDGET]),
                    default=0.0)

    # probes: strongest archived, scope-valid, non-negative, strong overlap
    probes = []
    archived = [
        fid for fid in sorted(st.archive)
        if st.certs.get(fid, UNRESOLVED).status is not NEGATIVE
        and (ep.memory(fid).spec.scope == t.spec.scope
             or ep.memory(fid).spec.scope == "any")
    ]
    ranked = sorted(
        archived, key=lambda fid: (-overlap(q, ep.tokens(fid)), _tie_key(fid)))
    probe_budget = PROBE_BUDGET_PER_TASK
    restored = []
    for fid in ranked:
        if probe_budget <= 0:
            break
        if overlap(q, ep.tokens(fid)) < PROBE_THRESHOLD:
            continue
        score = proposer_score(ep, fid, q, st)
        if score > min_score:      # earns a slot (strict, budgeted access)
            workspace.append(fid)
            restored.append(fid)
            st.store.add(fid)
            st.archive.discard(fid)
        log.probe_cost += PROBE_COST     # paid even when the probe is wasted
        probes.append(fid)
        probe_budget -= 1
    log.probes = tuple(probes)
    log.restore = tuple(restored)

    log.workspace = tuple(workspace[:WORKSPACE_BUDGET])
    log.candidates = [(fid, s, src) for fid, s, src in candidates] + \
                     [(fid, 0.0, "probe") for fid in restored]

    # adoption: exposed AND overlap >= ADOPT_THRESHOLD
    adopted = [fid for fid in log.workspace
               if overlap(q, ep.tokens(fid)) >= ADOPT_THRESHOLD]
    log.adopted = tuple(adopted)

    # outcome
    if t.spec.needed_fid is not None and t.spec.needed_fid in adopted:
        log.success = True
    penalties = []
    for fid in adopted:
        m = ep.memory(fid)
        if fid != t.spec.needed_fid and m.spec.wrong_use_penalty > 0.0:
            penalties.append((fid, m.spec.wrong_use_penalty))
    log.penalties = tuple(penalties)

    # costs (storage charged on the store during this task, exposure per
    # exposed memory; STORAGE_RATE / EXPOSURE_UNIT live in frozen.py)
    log.storage_cost = sum(ep.memory(fid).spec.storage_tokens
                           for fid in st.store) * 0.01
    log.exposure_cost = 0.05 * len(log.workspace)

    # state update
    for fid in log.workspace:
        st.exposure_count[fid] = st.exposure_count.get(fid, 0) + 1
        st.last_exposed[fid] = slot
    st.exposed_at_prev = set(log.workspace)

    log.state = WorldState(set(st.store), set(st.archive), dict(st.certs),
                           dict(st.exposure_count), dict(st.last_exposed),
                           set(st.exposed_at_prev))
    return log


def simulate_event(ep: RealizedEpisode, item: RealizedFutureItem, slot: int,
                   st: WorldState) -> TaskLog:
    """A visible future event: re-qualify (version/lineage gate) and, for
    updates, create the new-version fact.  Logged like a task for a uniform
    policy-log schema."""
    log = TaskLog(slot=slot)
    log.storage_cost = sum(ep.memory(fid).spec.storage_tokens
                           for fid in st.store) * 0.01
    fid = item.event_fid
    if fid is not None:
        old = st.certs.get(fid, UNRESOLVED)
        if old.status is not NEGATIVE:
            st.certs[fid] = CertificateRecord(fid, NEGATIVE, "future_event")
            st.store.discard(fid)
            st.archive.add(fid)
    # create the new version (both branches process the event identically).
    # Unconditional: in the update_after variant m_new is not introduced at
    # the decision point and must NOT be probable from the archive before
    # its event (the event is the only birth path).
    if item.event_kind == "update":
        new_fid = "m_new"
        st.store.add(new_fid)
        st.archive.discard(new_fid)
        st.certs[new_fid] = CertificateRecord(
            new_fid, POSITIVE, "created_by_update_event")
    log.state = WorldState(set(st.store), set(st.archive), dict(st.certs),
                           dict(st.exposure_count), dict(st.last_exposed),
                           set(st.exposed_at_prev))
    return log


def _tie_key(fid: str) -> str:
    # deterministic tie-break: descending fid string (matches the design of
    # the hitchhiker crowding episode: h1 must outrank e1 at equal score)
    return "".join(chr(127 - ord(c)) if ord(c) < 128 else c for c in fid)


@dataclass
class Rollout:
    action: str                       # "keep" | "archive"
    slot0: TaskLog                    # decision-point local task (pre-action)
    logs: Tuple[TaskLog, ...]         # slots 1..HORIZON
    certs: Dict[str, CertificateRecord]

    @property
    def harmful_exposure(self) -> int:
        return sum(len(l.penalties) for l in self.logs)

    def count_probes(self) -> int:
        return sum(1 for l in self.logs if l.probes)

    def rescued(self, fid: str) -> bool:
        return any(fid in l.restore for l in self.logs)


def simulate_branch(ep: RealizedEpisode, action: str) -> Rollout:
    """Paired rollout of one branch with the frozen reference policy.

    Slot 0 runs BEFORE the persistent action is applied (both branches see
    the identical pre-action state), which guarantees the local task is
    branch-independent by construction (22- 3.4 same-source counterfactual).
    """
    certs = {m.spec.fid: reference_certificate(ep, m.spec.fid,
                                               ep.world.decision_scope)
             for m in ep.memories}

    introduced = {m.spec.fid for m in ep.memories if m.spec.introduced}
    pre = WorldState(
        store=set(introduced),
        archive=set(), certs=dict(certs),
        exposure_count={}, last_exposed={}, exposed_at_prev=set())

    # slot 0: decision-point local task (branch-independent state)
    slot0 = TaskLog(slot=0)
    q0 = ep.decision_task.tokens
    slot0.query, slot0.scope = ep.decision_task.query, ep.world.decision_scope
    slot0.needed = ep.world.decision_task.needed_fid
    cands = []
    for fid in sorted(pre.store):
        m = ep.memory(fid)
        if m.spec.scope != ep.world.decision_scope and m.spec.scope != "any":
            continue
        cands.append((fid, proposer_score(ep, fid, q0, pre), "store"))
    cands.sort(key=lambda c: (-c[1], _tie_key(c[0])))
    slot0.candidates = cands
    slot0.workspace = tuple(fid for fid, _, _ in cands[:WORKSPACE_BUDGET])
    adopted = [fid for fid in slot0.workspace
               if overlap(q0, ep.tokens(fid)) >= ADOPT_THRESHOLD]
    slot0.adopted = tuple(adopted)
    needed0 = ep.world.decision_task.needed_fid
    if needed0 is not None and needed0 in adopted:
        slot0.success = True
    penalties = []
    for fid in adopted:
        m = ep.memory(fid)
        if fid != needed0 and m.spec.wrong_use_penalty > 0.0:
            penalties.append((fid, m.spec.wrong_use_penalty))
    slot0.penalties = tuple(penalties)
    slot0.exposure_cost = 0.05 * len(slot0.workspace)
    # pre-action snapshot (branch-independent, kept for the policy log)
    slot0.state = WorldState(set(pre.store), set(), dict(certs),
                             {}, {}, set(slot0.workspace))

    # apply the persistent action (intervention) after slot 0.  Keep is a
    # LITERAL action: the decision memory stays in the store and is only
    # evicted by a future event's re-qualification (version/lineage gate).
    # A decision-point NEGATIVE certificate attenuates and forbids probes
    # but does not pre-empt the store -- that keeps the keep/archive branch
    # difference observable (a pre-evicted keep would equal archive).
    # Not-yet-introduced memories live in no set: they are unreachable and
    # incur no cost until their future event creates them.
    st = WorldState(
        store=set(pre.store), archive=set(), certs=dict(certs),
        exposure_count={}, last_exposed={}, exposed_at_prev=set(slot0.workspace))
    if action == "archive":
        st.store.discard(ep.world.decision_fid)
        st.archive.add(ep.world.decision_fid)

    logs = []
    for item in ep.future_items:
        slot = item.spec.slot
        if item.spec.kind == "event":
            logs.append(simulate_event(ep, item, slot, st))
        else:
            logs.append(simulate_task(ep, item, slot, st))
    return Rollout(action=action, slot0=slot0, logs=tuple(logs),
                   certs=dict(certs))


def utilities(ep: RealizedEpisode, roll: Rollout) -> List[float]:
    """Per-slot utility before discounting (evaluator applies GAMMA)."""
    out = []
    # slot 0
    u0 = 0.0
    if roll.slot0.success:
        u0 += TASK_VALUE * ep.world.decision_task.difficulty
    for _, pen in roll.slot0.penalties:
        u0 -= pen
    u0 -= roll.slot0.exposure_cost
    out.append(u0)
    for l in roll.logs:
        u = 0.0
        if l.success:
            u += TASK_VALUE * l.difficulty
        for _, pen in l.penalties:
            u -= pen
        u -= l.storage_cost + l.exposure_cost + l.probe_cost
        out.append(u)
    return out
