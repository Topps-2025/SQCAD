"""R5: independent (clean-room) implementation of the frozen reference
policy, written from the DOCUMENTED rules only (frozen.py / world.py
docstrings and 22- 5.3), NOT from the world.py source.

This is the "second implementation" of the reference policy: the audit
(report 23- 6.5) requires that a reader who only has the published rules
can reproduce the policy-log layer bit-for-bit.  Any divergence between
``ind_rollout`` and ``world.simulate_branch`` on the same episode is a
consistency failure that must be fixed before the dataset ships.

Deliberate structural differences (the point of a clean-room check):
  * state is a plain class with mutating methods, not a dataclass that is
    copied per slot;
  * the future is consumed through a generic per-item dispatcher instead of
    an if/else loop;
  * events are indexed once into a per-fid table instead of re-scanned;
  * the certificate rules are a small rule TABLE applied in a fixed order.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from .frozen import (
    ADOPT_THRESHOLD, EXPOSURE_UNIT, FREQUENCY_W, HARM_PENALTY,
    NEGATIVE_ATTENUATION, PROBE_BUDGET_PER_TASK, PROBE_COST, PROBE_THRESHOLD,
    RECENCY_W, REQUALIFY_OVERLAP, STORAGE_RATE, TASK_VALUE, WORKSPACE_BUDGET,
)
from .realizer import RealizedEpisode, RealizedMsg, RealizedTask, tokenize, overlap
from .world import (
    MISMATCH, NEGATIVE, POSITIVE, UNRESOLVED, CertificateRecord, TaskLog,
    Rollout, WorldState,
)

_VERSION_ROLES = frozenset({"old", "new", "critical", "evidence"})


def _tie_key(fid: str) -> str:
    """Deterministic tie-break documented in 22- 5.3: descending fid."""
    return "".join(chr(127 - ord(c)) if ord(c) < 128 else c for c in fid)


# ---------------------------------------------------------------------------
# clean-room certificate
# ---------------------------------------------------------------------------
def ind_certificate(ep: RealizedEpisode, fid: str,
                    decision_scope: str) -> CertificateRecord:
    m = ep.memory(fid)

    # rule 1: scope gate
    if m.spec.scope not in (decision_scope, "any"):
        return CertificateRecord(fid, MISMATCH, "scope_outside_decision_scope")

    # rule 2: visible events (indexed once)
    for sess in ep.sessions:
        for msg in sess.messages:
            if msg.kind in ("update", "correction"):
                if msg.fid == fid:
                    return CertificateRecord(fid, NEGATIVE, "event_targets_fid")
                if msg.kind == "correction" and \
                        overlap(tokenize(msg.text), ep.tokens(fid)) >= REQUALIFY_OVERLAP:
                    return CertificateRecord(fid, NEGATIVE, "event_overlap")

    # rule 3: lineage conflict (both sides version-carrying, introduced,
    #         counterpart not already resolved by an event)
    if m.spec.role in _VERSION_ROLES:
        for other in ep.memories:
            if other.spec.fid == fid or other.spec.role not in _VERSION_ROLES:
                continue
            if not other.spec.introduced:
                continue
            if (other.spec.entity, other.spec.slot, other.spec.scope) == \
                    (m.spec.entity, m.spec.slot, m.spec.scope):
                if overlap(ep.tokens(other.spec.fid), ep.tokens(fid)) >= 3:
                    if _resolved_by_event(ep, other.spec.fid):
                        continue
                    return CertificateRecord(
                        fid, UNRESOLVED, f"lineage_conflict_with_{other.spec.fid}")

    # rule 4: association-only hitchhiker
    if m.spec.role == "hitchhiker":
        return CertificateRecord(fid, UNRESOLVED, "association_only_hitchhiker")

    # rule 5: adopted at the decision task
    if overlap(ep.decision_task.tokens, ep.tokens(fid)) >= ADOPT_THRESHOLD:
        return CertificateRecord(fid, POSITIVE, "adopted_at_decision_task")

    # rule 6: no observable signal
    return CertificateRecord(fid, UNRESOLVED, "no_observable_signal")


def _resolved_by_event(ep: RealizedEpisode, fid: str) -> bool:
    for sess in ep.sessions:
        for msg in sess.messages:
            if msg.kind in ("update", "correction") and msg.fid == fid:
                return True
    return False


# ---------------------------------------------------------------------------
# clean-room rollout
# ---------------------------------------------------------------------------
class _State:
    """Mutable simulator state (intentionally a different shape from
    world.WorldState: one class owns every transition)."""

    def __init__(self, certs: Dict[str, CertificateRecord],
                 introduced: Sequence[str]):
        self.store = set(introduced)
        self.archive: set = set()
        self.certs = dict(certs)
        self.exposure: Dict[str, int] = {}
        self.last_exposed: Dict[str, int] = {}
        self.prev_exposed: set = set()

    def score(self, ep: RealizedEpisode, fid: str, q: Tuple[str, ...]) -> float:
        m = ep.memory(fid)
        s = float(overlap(q, m.tokens))
        if fid in self.prev_exposed:
            s += RECENCY_W
        if fid in self.exposure:
            s += FREQUENCY_W * math.log1p(self.exposure[fid])
        if self.certs.get(fid, UNRESOLVED).status is NEGATIVE:
            s -= NEGATIVE_ATTENUATION
        return s

    def snapshot(self) -> WorldState:
        return WorldState(set(self.store), set(self.archive), dict(self.certs),
                          dict(self.exposure), dict(self.last_exposed),
                          set(self.prev_exposed))

    def mark_exposed(self, workspace: Sequence[str], slot: int,
                     count: bool = True) -> None:
        if count:
            for fid in workspace:
                self.exposure[fid] = self.exposure.get(fid, 0) + 1
                self.last_exposed[fid] = slot
        self.prev_exposed = set(workspace)


def _task_step(ep: RealizedEpisode, item, slot: int, st: _State) -> TaskLog:
    t = item.task
    log = TaskLog(slot=slot, difficulty=t.spec.difficulty)
    q = t.tokens
    log.query, log.scope = t.query, t.spec.scope
    log.needed = t.spec.needed_fid

    # candidates: store only, scope gate, descending score
    cands = []
    for fid in sorted(st.store):
        m = ep.memory(fid)
        if m.spec.scope not in (t.spec.scope, "any"):
            continue
        cands.append((fid, st.score(ep, fid, q), "store"))
    cands.sort(key=lambda c: (-c[1], _tie_key(c[0])))
    workspace = [fid for fid, _, _ in cands][:WORKSPACE_BUDGET]
    min_score = min((s for _, s, _ in cands[:WORKSPACE_BUDGET]), default=0.0)

    # paid probe: strongest archived, non-negative cert, scope-valid,
    # overlap >= PROBE_THRESHOLD; restore iff score strictly beats the
    # current workspace minimum
    probes: List[str] = []
    restored: List[str] = []
    if PROBE_BUDGET_PER_TASK > 0:
        archived = sorted(
            (fid for fid in st.archive
             if st.certs.get(fid, UNRESOLVED).status is not NEGATIVE
             and ep.memory(fid).spec.scope in (t.spec.scope, "any")),
            key=lambda fid: (-overlap(q, ep.tokens(fid)), _tie_key(fid)))
        for fid in archived[:PROBE_BUDGET_PER_TASK]:
            if overlap(q, ep.tokens(fid)) < PROBE_THRESHOLD:
                continue
            log.probe_cost += PROBE_COST
            probes.append(fid)
            if st.score(ep, fid, q) > min_score:
                workspace.append(fid)
                restored.append(fid)
                st.store.add(fid)
                st.archive.discard(fid)
    log.probes = tuple(probes)
    log.restore = tuple(restored)
    log.workspace = tuple(workspace[:WORKSPACE_BUDGET])
    log.candidates = cands + [(fid, 0.0, "probe") for fid in restored]

    # adoption: exposed AND overlap >= ADOPT_THRESHOLD
    adopted = [fid for fid in log.workspace
               if overlap(q, ep.tokens(fid)) >= ADOPT_THRESHOLD]
    log.adopted = tuple(adopted)

    # outcome + penalties
    if t.spec.needed_fid is not None and t.spec.needed_fid in adopted:
        log.success = True
    pens = []
    for fid in adopted:
        m = ep.memory(fid)
        if fid != t.spec.needed_fid and m.spec.wrong_use_penalty > 0.0:
            pens.append((fid, m.spec.wrong_use_penalty))
    log.penalties = tuple(pens)

    # costs per the documented contract
    log.storage_cost = sum(ep.memory(f).spec.storage_tokens
                           for f in st.store) * STORAGE_RATE
    log.exposure_cost = EXPOSURE_UNIT * len(log.workspace)

    st.mark_exposed(log.workspace, slot)
    log.state = st.snapshot()
    return log


def _event_step(ep: RealizedEpisode, item, slot: int, st: _State) -> TaskLog:
    log = TaskLog(slot=slot)
    log.storage_cost = sum(ep.memory(f).spec.storage_tokens
                           for f in st.store) * STORAGE_RATE
    fid = item.event_fid
    if fid is not None:
        old = st.certs.get(fid, UNRESOLVED)
        if old.status is not NEGATIVE:
            st.certs[fid] = CertificateRecord(fid, NEGATIVE, "future_event")
            st.store.discard(fid)
            st.archive.add(fid)
    if item.event_kind == "update":
        st.store.add("m_new")
        st.archive.discard("m_new")
        st.certs["m_new"] = CertificateRecord(
            "m_new", POSITIVE, "created_by_update_event")
    log.state = st.snapshot()
    return log


def ind_rollout(ep: RealizedEpisode, action: str) -> Rollout:
    """Clean-room branch rollout; must match world.simulate_branch."""
    certs = {m.spec.fid: ind_certificate(ep, m.spec.fid,
                                         ep.world.decision_scope)
             for m in ep.memories}
    introduced = [m.spec.fid for m in ep.memories if m.spec.introduced]
    st = _State(certs, introduced)

    # slot 0: decision-point local task (branch-independent)
    q0 = ep.decision_task.tokens
    slot0 = TaskLog(slot=0)
    slot0.query, slot0.scope = ep.decision_task.query, ep.world.decision_scope
    slot0.needed = ep.world.decision_task.needed_fid
    cands = []
    for fid in sorted(st.store):
        m = ep.memory(fid)
        if m.spec.scope not in (ep.world.decision_scope, "any"):
            continue
        cands.append((fid, st.score(ep, fid, q0), "store"))
    cands.sort(key=lambda c: (-c[1], _tie_key(c[0])))
    slot0.candidates = cands
    slot0.workspace = tuple(fid for fid, _, _ in cands[:WORKSPACE_BUDGET])
    adopted = [fid for fid in slot0.workspace
               if overlap(q0, ep.tokens(fid)) >= ADOPT_THRESHOLD]
    slot0.adopted = tuple(adopted)
    needed0 = ep.world.decision_task.needed_fid
    if needed0 is not None and needed0 in adopted:
        slot0.success = True
    pens = []
    for fid in adopted:
        m = ep.memory(fid)
        if fid != needed0 and m.spec.wrong_use_penalty > 0.0:
            pens.append((fid, m.spec.wrong_use_penalty))
    slot0.penalties = tuple(pens)
    slot0.exposure_cost = EXPOSURE_UNIT * len(slot0.workspace)
    # slot-0 exposure feeds recency (prev_exposed) but not frequency
    st.mark_exposed(slot0.workspace, 0, count=False)
    slot0.state = st.snapshot()

    # persistent action (intervention) after slot 0
    if action == "archive":
        st.store.discard(ep.world.decision_fid)
        st.archive.add(ep.world.decision_fid)

    logs = [_task_step(ep, it, it.spec.slot, st) if it.spec.kind == "task"
            else _event_step(ep, it, it.spec.slot, st)
            for it in ep.future_items]
    return Rollout(action=action, slot0=slot0, logs=tuple(logs),
                   certs=dict(certs))


# ---------------------------------------------------------------------------
# consistency checking
# ---------------------------------------------------------------------------
def _log_bits(log: TaskLog) -> Tuple:
    return (log.slot, log.query, log.scope, log.candidates, log.workspace,
            log.probes, log.restore, log.adopted, log.success,
            round(log.storage_cost, 4), round(log.exposure_cost, 4),
            round(log.probe_cost, 4),
            tuple(sorted(log.state.store)), tuple(sorted(log.state.archive)),
            tuple(sorted((f, str(c.status)) for f, c in log.state.certs.items())))


def differences(ep: RealizedEpisode) -> List[str]:
    """Compare clean-room rollout vs. the frozen world simulator on BOTH
    branches; returns a list of human-readable divergences (empty = OK)."""
    out: List[str] = []
    for action in ("keep", "archive"):
        ref = simulate_branch_ref(ep, action)
        ind = ind_rollout(ep, action)
        if set(ind.certs) != set(ref.certs):
            out.append(f"{action}: certificate key sets differ")
            continue
        for fid in ref.certs:
            if ind.certs[fid].status != ref.certs[fid].status:
                out.append(f"{action}: cert {fid} {ref.certs[fid].status} "
                           f"!= {ind.certs[fid].status} ({ind.certs[fid].reason})")
        if _log_bits(ind.slot0) != _log_bits(ref.slot0):
            out.append(f"{action}: slot0 differs")
        if len(ind.logs) != len(ref.logs):
            out.append(f"{action}: log length differs")
            continue
        for i, (a, b) in enumerate(zip(ind.logs, ref.logs)):
            if _log_bits(a) != _log_bits(b):
                out.append(f"{action}: slot {a.slot} differs "
                           f"(workspace {a.workspace} vs {b.workspace}, "
                           f"probes {a.probes} vs {b.probes})")
    return out


def simulate_branch_ref(ep: RealizedEpisode, action: str) -> Rollout:
    """Reference side used by the checker (kept local so the checker never
    imports the world.simulate_branch symbol path twice)."""
    from .world import simulate_branch
    return simulate_branch(ep, action)


def verify(episodes: Sequence[RealizedEpisode]) -> Dict[str, Any]:
    """Run the consistency check over a sequence of episodes."""
    total, bad = 0, 0
    first_bad: Optional[str] = None
    for ep in episodes:
        total += 1
        diffs = differences(ep)
        if diffs:
            bad += 1
            if first_bad is None:
                first_bad = f"{ep.world.episode_id}: {diffs[0]}"
    return {"checked": total, "inconsistent": bad,
            "consistent": total - bad, "first_divergence": first_bad}
