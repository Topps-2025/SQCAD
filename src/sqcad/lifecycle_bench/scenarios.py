"""Scenario Designer: frozen structured templates and hidden dependency
graphs for the SQCAD-LifecycleBench MVP (doc 22- 5.1, 10).

The designer emits *specifications* -- entities, facts, scopes, risk types,
future-event slots and the hidden dependency graph -- but never the oracle
outcome.  Oracle outcomes are produced only by the Independent Evaluator
after the paired rollout (``evaluator.py``).  All text realization happens
later in ``realizer.py``; the designer only declares what must be realized.

Each family instantiates one counterexample / mechanism from the theory
chain (10- 2.1, 13- / 14- T1/T2, 16- / 19- overlay events):

  hitchhiker      -> Prop A analog: co-exposure makes association signals
                     point at the useless memory (regime association_tie)
  rare_bridge     -> T1/T2 analog: archiving censors the future candidate
                     stream (regime self_obscuring)
  version_update  -> temporal-consistency / E1 overlay (regime version_drift)
  harmful_stale   -> E2/E3 overlay: correction visible or not
                     (regime identified / unidentifiable_absent_correction)
  self_obscuring  -> archive-induced candidate censoring + probe wasted under
                     crowding (regime self_obscuring_crowding)
  scope_mismatch  -> Prop C analog: scope transport limitation
                     (regime scope_transport)
  stable_positive / stable_negative / neutral -> controls (22- 3.6)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .frozen import HARM_PENALTY, HORIZON


@dataclass(frozen=True)
class MemorySpec:
    """A fact the world knows.  ``fact_tokens``/``fact_text`` are realized
    by the realizer; the designer only fixes the semantic content and the
    hidden risk attributes."""

    fid: str
    entity: str
    slot: str                       # e.g. "volunteer_org", "phone"
    value: str                      # the fact value (used by realizer)
    scope: str
    version: int
    role: str                       # critical | evidence | filler | stale | old | new | hitchhiker | neutral
    storage_tokens: int             # persistent-storage size (cost contract)
    wrong_use_penalty: float        # penalty when adopted but not the needed memory
    bridge_rare: bool = False       # low-frequency / rare-access flag
    introduced: bool = True         # known to the policy at the decision point


@dataclass(frozen=True)
class SessionSpec:
    """One pre-decision session; messages are realized later."""

    sid: str
    scope: str
    message_plan: Tuple[str, ...]   # realized texts (filled by the realizer)
    facts_introduced: Tuple[str, ...]


@dataclass(frozen=True)
class TaskSpec:
    """A task in the timeline (slot 0 = the decision-point local task).
    ``needed_fid`` is HIDDEN: it never appears in the public trace."""

    slot: int
    scope: str
    query_plan: str                 # filled by the realizer with a chosen paraphrase
    overlap_target: str             # which fact the query must overlap, and how much
    needed_fid: Optional[str]       # HIDDEN
    difficulty: float = 1.0


@dataclass(frozen=True)
class FutureItemSpec:
    """One item of the chronological future (slots 1..HORIZON)."""

    slot: int
    kind: str                       # "task" | "event"
    event_kind: Optional[str] = None        # "update" | "correction" when kind=="event"
    event_fid: Optional[str] = None         # fact the event targets (requalification)
    event_new_value: Optional[str] = None
    task: Optional[TaskSpec] = None


@dataclass(frozen=True)
class WorldSpec:
    """Full designer output for one episode."""

    episode_id: str
    family: str
    variant: str
    regime: str
    paired_key: Optional[str]
    decision_fid: str
    decision_scope: str
    decision_action_label: str      # designer intent: keep | archive | neutral
    memories: Tuple[MemorySpec, ...]
    sessions: Tuple[SessionSpec, ...]
    decision_task: TaskSpec
    future_items: Tuple[FutureItemSpec, ...]

    # hidden dependency bookkeeping (evaluator-only)
    @property
    def needed_future_ids(self) -> Tuple[str, ...]:
        seen = []
        for it in self.future_items:
            if it.kind == "task" and it.task is not None and it.task.needed_fid:
                if it.task.needed_fid not in seen:
                    seen.append(it.task.needed_fid)
        return tuple(seen)


# ---------------------------------------------------------------------------
# shared pools (realization fills the text)
# ---------------------------------------------------------------------------
TOPICS = {
    "volunteer": ("volunteer", "charity", "local", "food", "bank", "weekend"),
    "diet": ("diet", "meal", "snack", "day", "portion"),
    "schedule": ("meeting", "plan", "week", "project", "timeline"),
    "medication": ("medication", "allergy", "morning", "daily", "dose"),
    "finance": ("budget", "project", "dollars", "quarter", "plan"),
    "phone": ("phone", "number", "contact", "call", "reach"),
    "passport": ("passport", "drawer", "document", "storage", "safe"),
}


def _mem(fid, entity, slot, value, scope, role, storage_tokens,
         penalty=0.0, version=1, bridge_rare=False, introduced=True):
    return MemorySpec(fid=fid, entity=entity, slot=slot, value=value,
                      scope=scope, version=version, role=role,
                      storage_tokens=storage_tokens,
                      wrong_use_penalty=penalty, bridge_rare=bridge_rare,
                      introduced=introduced)


def _task(slot, scope, qplan, overlap, needed, difficulty=1.0):
    return TaskSpec(slot=slot, scope=scope, query_plan=qplan,
                    overlap_target=overlap, needed_fid=needed,
                    difficulty=difficulty)


# ---------------------------------------------------------------------------
# family builders
# ---------------------------------------------------------------------------
def build_hitchhiker(seed: int, variant: str, entity: str,
                     topic: Tuple[str, ...], paired_key: Optional[str]) -> WorldSpec:
    """Prop A analog.  Evidence E is genuinely needed by a future task;
    hitchhiker H co-occurs with E, has no incremental value, and displaces
    E from the budgeted workspace when kept (recency-favored).  Keeping H is
    a false commit driven by association; the correct action is archive."""
    assert topic[0] == "volunteer"
    e_fid, h_fid = "e1", "h1"
    ev = _mem(e_fid, entity, "volunteer_org", "local food bank",
              "s1", "evidence", 9)
    h = _mem(h_fid, entity, "volunteer_chatter", "local food bank stories",
             "s1", "hitchhiker", 40, penalty=0.0)
    # 9 volunteer-place fillers: overlap 3 with BOTH q_volunteer_crowd
    # (crowding: they fill the top-10 workspace with score 3.0) and
    # q_volunteer_chatter (so the archive branch's probe of h1 sees
    # min workspace score 3.0 and is DENIED -- strict inequality).
    vol_fillers = tuple(
        _mem(f"f_vol{i}", entity, "volunteer", f"place {i}", "s1", "filler", 6)
        for i in range(1, 10))
    topic_fillers = tuple(
        _mem(f"f{i}", entity, slot, f"topic {i}", "s1", "filler", 6)
        for i, slot in enumerate(("schedule", "diet", "exercise", "travel",
                                  "finance", "home", "work", "study"), 1))
    sessions = (
        SessionSpec("s1", "s1",
                    ("intro_evidence", "intro_hitchhiker", "chatter_coexpose"),
                    (e_fid, h_fid)),
        SessionSpec("s2", "s1",
                    ("distract", "coexpose_again", "distract2"),
                    (h_fid,)),
    )
    decision = _task(0, "s1", "q_volunteer_org", "e1", e_fid)
    # future: task4 exposes H (feeds its recency bonus), task5 is the
    # crowding task where H displaces E out of the top-10 workspace.
    future = (
        FutureItemSpec(1, "task", task=_task(1, "s1", "q_diet", "f1", None)),
        FutureItemSpec(2, "task", task=_task(2, "s1", "q_schedule", "f2", None)),
        FutureItemSpec(3, "task", task=_task(3, "s1", "q_diet", "f3", None)),
        FutureItemSpec(4, "task", task=_task(4, "s1", "q_volunteer_chatter",
                                             "h1", None)),
        FutureItemSpec(5, "task", task=_task(5, "s1", "q_volunteer_crowd",
                                             "e1", e_fid)),
        FutureItemSpec(6, "task", task=_task(6, "s1", "q_finance", "f5", None)),
        FutureItemSpec(7, "task", task=_task(7, "s1", "q_diet", "f6", None)),
        FutureItemSpec(8, "task", task=_task(8, "s1", "q_travel", "f7", None)),
        FutureItemSpec(9, "task", task=_task(9, "s1", "q_work", "f8", None)),
        FutureItemSpec(10, "task", task=_task(10, "s1", "q_schedule", "f4", None)),
    )
    return WorldSpec(
        episode_id=f"hitchhiker-{variant}-{seed}", family="hitchhiker",
        variant=variant, regime="association_tie", paired_key=paired_key,
        decision_fid=h_fid, decision_scope="s1",
        decision_action_label="archive",
        memories=(ev, h) + vol_fillers + topic_fillers, sessions=sessions,
        decision_task=decision, future_items=future)


def build_rare_bridge(seed: int, variant: str, entity: str,
                      topic: Tuple[str, ...],
                      paired_key: Optional[str]) -> WorldSpec:
    """T1/T2 analog.  A low-frequency memory is needed by exactly one rare
    future task.  Archive censors the candidate stream; the paid probe can
    rescue it only when the query keeps enough lexical overlap
    (rescue_possible) -- otherwise the bridge is lost (rescue_impossible).
    Correct action: keep."""
    assert topic[0] == "passport"
    m_fid = "m1"
    m = _mem(m_fid, entity, "passport_location", "red drawer",
             "s1", "critical", 8, bridge_rare=True)
    fillers = tuple(
        _mem(f"f{i}", entity, slot, f"topic {i}", "s1", "filler", 6)
        for i, slot in enumerate(("schedule", "diet", "finance", "home",
                                  "work", "study", "travel"), 1))
    sessions = (
        SessionSpec("s1", "s1", ("distract",), ()),
        SessionSpec("s2", "s1", ("intro_passport", "distract2"), (m_fid,)),
    )
    decision = _task(0, "s1", "q_passport", "m1", None)   # neutral local task
    items = [
        FutureItemSpec(i, "task", task=_task(i, "s1", "q_schedule", "f1", None))
        for i in range(1, 11)
    ]
    if variant == "rescue_possible":
        # early rescue: the paid probe is still expensive (gamma^2), so keep
        # beats archive despite the successful restore.
        items[1] = FutureItemSpec(2, "task", task=_task(
            2, "s1", "q_passport_rescue_possible", "m1_strong", m_fid))
    else:  # rescue_impossible
        # late bridge with a weak query: overlap 2 < PROBE_THRESHOLD, so the
        # archive branch cannot rescue -> false forgetting (T1/T2).
        items[7] = FutureItemSpec(8, "task", task=_task(
            8, "s1", "q_passport_rescue_impossible", "m1_weak", m_fid))
    return WorldSpec(
        episode_id=f"rare_bridge-{variant}-{seed}", family="rare_bridge",
        variant=variant, regime="self_obscuring", paired_key=paired_key,
        decision_fid=m_fid, decision_scope="s1",
        decision_action_label="keep",
        memories=(m,) + fillers, sessions=sessions,
        decision_task=decision, future_items=tuple(items))


def build_version_update(seed: int, variant: str, entity: str,
                         topic: Tuple[str, ...],
                         paired_key: Optional[str]) -> WorldSpec:
    """E1 temporal-consistency analog.  Variant ``update_before``: the new
    version is visible BEFORE the decision point, so the old version can be
    identified as stale and archived (oracle archive).  Variant
    ``update_after``: the update arrives inside the future, so the old
    version is needed by early tasks and re-qualification handles the late
    switch (oracle keep)."""
    assert topic[0] == "phone"
    old, new = "m_old", "m_new"
    m_old = _mem(old, entity, "phone", "555-0123", "s1", "old", 25,
                 penalty=(HARM_PENALTY if variant == "update_before" else 0.0))
    m_new = _mem(new, entity, "phone", "555-0199", "s1", "new", 6,
                 introduced=(variant == "update_before"))
    fillers = tuple(
        _mem(f"f{i}", entity, slot, f"topic {i}", "s1", "filler", 6)
        for i, slot in enumerate(("schedule", "diet", "finance", "home",
                                  "work", "study", "travel"), 1))
    decision = _task(0, "s1", "q_phone", "m_old", None)
    if variant == "update_before":
        # the new version is known at the decision point (no event needed):
        # lineage conflict marks both UNRESOLVED, so keeping the old version
        # lets it be adopted by every future query (wrong-use harm), while
        # archiving it is safe -- the weak query (overlap 2) never probes.
        sessions = (
            SessionSpec("s1", "s1", ("intro_old_phone",), (old,)),
            SessionSpec("s2", "s1", ("intro_new_phone", "distract"), (new,)),
        )
        items = []
        for i in range(1, 11):
            needed = new if 3 <= i <= 6 else None
            items.append(FutureItemSpec(
                i, "task",
                task=_task(i, "s1", "q_phone", "m_new", needed)))
        action_label = "archive"
    else:  # update_after
        # the update arrives at slot 7: early tasks need the old version
        # (keep), the event re-qualifies it and creates the new version.
        sessions = (
            SessionSpec("s1", "s1", ("intro_old_phone", "distract"), (old,)),
        )
        items = []
        for i in range(1, 11):
            if i <= 6:
                items.append(FutureItemSpec(
                    i, "task", task=_task(i, "s1", "q_phone", "m_old", old)))
            elif i == 7:
                items.append(FutureItemSpec(
                    i, "event", event_kind="update", event_fid=old,
                    event_new_value="555-0199"))
            else:
                items.append(FutureItemSpec(
                    i, "task", task=_task(i, "s1", "q_phone", "m_new", new)))
        action_label = "keep"
    return WorldSpec(
        episode_id=f"version_update-{variant}-{seed}", family="version_update",
        variant=variant, regime="version_drift", paired_key=paired_key,
        decision_fid=old, decision_scope="s1",
        decision_action_label=action_label,
        memories=(m_old, m_new) + fillers, sessions=sessions,
        decision_task=decision, future_items=tuple(items))


def build_harmful_stale(seed: int, variant: str, entity: str,
                        topic: Tuple[str, ...],
                        paired_key: Optional[str]) -> WorldSpec:
    """E2/E3 analog.  A stale (wrong) fact coexists with the correct fact.
    Variant ``correction_visible``: a correction event before the decision
    point lets the policy identify the stale fact (oracle archive).
    Variant ``no_correction``: the policy cannot distinguish the stale fact
    and must abstain (oracle neutral; both branches incur the same wrong-use
    harm, so the dataset rewards defer, not commit)."""
    assert topic[0] == "medication"
    stale, good = "m_stale", "m_good"
    m_stale = _mem(stale, entity, "allergy", "peanuts", "s1", "stale",
                   10, penalty=HARM_PENALTY)
    m_good = _mem(good, entity, "allergy", "shellfish", "s1", "evidence", 6)
    fillers = tuple(
        _mem(f"f{i}", entity, slot, f"topic {i}", "s1", "filler", 6)
        for i, slot in enumerate(("schedule", "diet", "finance", "home",
                                  "work", "study", "travel"), 1))
    if variant == "correction_visible":
        # a visible correction lets the policy identify the stale fact.
        # keep = the stale fact stays in the store and is adopted by the
        # decision task and by the future allergy query (wrong-use harm);
        # the weak query (overlap 2 < PROBE_THRESHOLD) never rescues it.
        sessions = (
            SessionSpec("s1", "s1", ("intro_stale_allergy",), (stale,)),
            SessionSpec("s2", "s1", ("correction_allergy",), (good,)),
        )
        decision = _task(0, "s1", "q_medication", "m_good", None)
        q5plan, action_label = "q_medication", "archive"
    else:
        # no correction: the policy cannot tell stale from good; the future
        # allergy query is strong enough (overlap 3) that archiving lets the
        # paid probe rescue the stale fact, so BOTH branches incur the same
        # wrong-use harm and the two actions differ only in cost -> neutral.
        sessions = (
            SessionSpec("s1", "s1", ("intro_stale_allergy",), (stale,)),
            SessionSpec("s2", "s1", ("intro_good_allergy",), (good,)),
        )
        decision = _task(0, "s1", "q_allergy_generic", "m_good", None)
        q5plan, action_label = "q_medication_strong", "neutral"
    items = [
        FutureItemSpec(i, "task", task=_task(i, "s1", "q_schedule", "f1", None))
        for i in range(1, 11)
    ]
    items[4] = FutureItemSpec(5, "task", task=_task(
        5, "s1", q5plan, "m_good", good))
    return WorldSpec(
        episode_id=f"harmful_stale-{variant}-{seed}", family="harmful_stale",
        variant=variant,
        regime=("identified" if variant == "correction_visible"
                else "unidentifiable_absent_correction"),
        paired_key=paired_key, decision_fid=stale, decision_scope="s1",
        decision_action_label=action_label,
        memories=(m_stale, m_good) + fillers, sessions=sessions,
        decision_task=decision, future_items=tuple(items))


def build_self_obscuring(seed: int, variant: str, entity: str,
                         topic: Tuple[str, ...],
                         paired_key: Optional[str]) -> WorldSpec:
    """T1/T2 core: archiving censors the future candidate stream.  Variant
    ``crowding``: the needed memory is probed at the future task but is
    denied a workspace slot under competitive crowding, so archive causes
    false forgetting even with the paid probe (oracle keep).  Variant
    ``rescue_possible``: probe restores it and the small probe cost remains
    the only archive penalty (oracle keep)."""
    assert topic[0] == "medication" and variant in ("crowding", "rescue_possible")
    m_fid = "m1"
    m = _mem(m_fid, entity, "medication", "loratadine", "s1", "critical",
             9, bridge_rare=True)
    if variant == "crowding":
        # 16 medication fillers each sharing 4 tokens with q_medication:
        # the top-10 workspace is all score-4.0, so the archive branch's
        # probe of m1 (score 4.0) is DENIED by strict competition -- paid
        # probe cannot rescue -> archive causes false forgetting (T1/T2).
        fillers = tuple(
            _mem(f"f_med{i}", entity, "medication", f"place {i}", "s1",
                 "filler", 6)
            for i in range(1, 17))
    else:  # rescue_possible
        fillers = tuple(
            _mem(f"f{i}", entity, slot, f"topic {i}", "s1", "filler", 6)
            for i, slot in enumerate(("schedule", "diet", "finance", "home",
                                      "work", "study", "travel"), 1))
    sessions = (
        SessionSpec("s1", "s1", ("distract",), ()),
        SessionSpec("s2", "s1", ("intro_medication",), (m_fid,)),
    )
    decision = _task(0, "s1", "q_medication", "m1", None)
    items = [
        FutureItemSpec(i, "task", task=_task(i, "s1", "q_schedule", "f1", None))
        for i in range(1, 11)
    ]
    if variant == "rescue_possible":
        # early rescue at slot 2: probe cost gamma^2 still makes keep better
        # even though archive can pay its way back.
        items[1] = FutureItemSpec(2, "task", task=_task(
            2, "s1", "q_medication", "m1", m_fid))
    else:  # crowding
        # late query into a workspace saturated by score-4.0 fillers: the
        # probe is denied by strict competition, archive -> false forgetting.
        items[7] = FutureItemSpec(8, "task", task=_task(
            8, "s1", "q_medication", "m1", m_fid))
    return WorldSpec(
        episode_id=f"self_obscuring-{variant}-{seed}", family="self_obscuring",
        variant=variant,
        regime=("self_obscuring_crowding" if variant == "crowding"
                else "self_obscuring_rescue"),
        paired_key=paired_key, decision_fid=m_fid, decision_scope="s1",
        decision_action_label="keep",
        memories=(m,) + fillers, sessions=sessions,
        decision_task=decision, future_items=tuple(items))


def build_scope_mismatch(seed: int, variant: str, entity: str,
                         topic: Tuple[str, ...],
                         paired_key: Optional[str]) -> WorldSpec:
    """Prop C analog.  The same entity has different meanings per scope
    (s1 marketing vs s2 engineering budgets).  Variant ``future_in_s1``: the
    future stays in the memory's scope (oracle keep).  Variant
    ``future_in_s2``: the future moves out of scope; keeping the memory
    produces negative transfer (oracle archive; the scope gate must also
    forbid probing it across scopes)."""
    assert topic[0] == "finance"
    m_fid, other = "m1", "m2"
    m = _mem(m_fid, entity, "budget", "5000 dollars", "s1", "critical", 10,
             penalty=HARM_PENALTY)
    m2 = _mem(other, entity, "budget", "20000 dollars", "s2", "evidence", 6)
    fillers = tuple(
        _mem(f"f{i}", entity, slot, f"topic {i}", "s1", "filler", 6)
        for i, slot in enumerate(("schedule", "diet", "home", "work",
                                  "study", "travel"), 1))
    sessions = (
        SessionSpec("s1", "s1", ("intro_budget_s1",), (m_fid,)),
        SessionSpec("s2", "s2", ("intro_budget_s2",), (other,)),
    )
    decision = _task(0, "s1", "q_budget", "m1", None)
    if variant == "future_in_s1":
        future_scope, needed, action_label, overlap = "s1", m_fid, "keep", "m1"
    else:
        future_scope, needed, action_label, overlap = "s2", other, "archive", "m2"
    items = [
        FutureItemSpec(i, "task", task=_task(i, "s1", "q_schedule", "f1", None))
        for i in range(1, 11)
    ]
    if variant == "future_in_s1":
        # early queries: the archive branch pays a full probe at slot 1
        # (gamma^1) plus storage back, so keep wins by more than TAU_TOL.
        items[0] = FutureItemSpec(1, "task", task=_task(
            1, future_scope, "q_budget", overlap, needed))
        items[3] = FutureItemSpec(4, "task", task=_task(
            4, future_scope, "q_budget", overlap, needed))
    else:
        items[3] = FutureItemSpec(4, "task", task=_task(
            4, future_scope, "q_budget", overlap, needed))
        items[6] = FutureItemSpec(7, "task", task=_task(
            7, future_scope, "q_budget", overlap, needed))
    return WorldSpec(
        episode_id=f"scope_mismatch-{variant}-{seed}", family="scope_mismatch",
        variant=variant, regime="scope_transport", paired_key=paired_key,
        decision_fid=m_fid, decision_scope="s1",
        decision_action_label=action_label,
        memories=(m, m2) + fillers, sessions=sessions,
        decision_task=decision, future_items=tuple(items))


def build_control(seed: int, family: str, entity: str,
                  topic: Tuple[str, ...]) -> WorldSpec:
    """Stable positive / stable negative / neutral controls (22- 3.6)."""
    m_fid = "m1"
    if family == "stable_positive":
        m = _mem(m_fid, entity, "schedule", "team lunch on fridays",
                 "s1", "critical", 8)
        sessions = (SessionSpec("s1", "s1", ("intro_schedule",), (m_fid,)),)
        items = [
            FutureItemSpec(i, "task",
                           task=_task(i, "s1", "q_schedule", "m1",
                                      m_fid if i in (2, 5, 8) else None))
            for i in range(1, 11)
        ]
        action_label = "keep"
    elif family == "stable_negative":
        m = _mem(m_fid, entity, "allergy", "peanuts", "s1", "stale", 10,
                 penalty=HARM_PENALTY)
        m_good = _mem("m_good", entity, "allergy", "shellfish", "s1",
                      "evidence", 6)
        sessions = (
            SessionSpec("s1", "s1", ("intro_stale_allergy",), (m_fid,)),
            SessionSpec("s2", "s1", ("correction_allergy", "intro_good_allergy"),
                        ("m_good",)),
        )
        items = [
            FutureItemSpec(i, "task",
                           task=_task(i, "s1", "q_schedule", "f1", None))
            for i in range(1, 11)
        ]
        # future allergy query: keep leaves the stale fact adoptable (harm);
        # the negative certificate forbids probing it back after archive.
        items[4] = FutureItemSpec(5, "task", task=_task(
            5, "s1", "q_medication", "m_good", "m_good"))
        action_label = "archive"
    else:  # neutral
        # storage 2: keep/archive differ only by storage + exposure
        # (0.117 + 0.293 + 0.05 slot0 = 0.46 < TAU_TOL) -> NEUTRAL.
        m = _mem(m_fid, entity, "pet", "turtle named shelly", "s1",
                 "neutral", 2)
        sessions = (SessionSpec("s1", "s1", ("intro_neutral",), (m_fid,)),)
        items = [
            FutureItemSpec(i, "task",
                           task=_task(i, "s1", "q_schedule", "f1", None))
            for i in range(1, 11)
        ]
        action_label = "neutral"
    extra = ()
    if family == "stable_negative":
        extra = (m_good,)
    return WorldSpec(
        episode_id=f"{family}-{seed}", family=family, variant="default",
        regime=family, paired_key=None, decision_fid=m_fid,
        decision_scope="s1", decision_action_label=action_label,
        memories=(m,) + extra, sessions=sessions,
        decision_task=_task(0, "s1", "q_schedule", "m1", None),
        future_items=tuple(items))


FAMILY_BUILDERS: Dict[str, callable] = {
    "hitchhiker": build_hitchhiker,
    "rare_bridge": build_rare_bridge,
    "version_update": build_version_update,
    "harmful_stale": build_harmful_stale,
    "self_obscuring": build_self_obscuring,
    "scope_mismatch": build_scope_mismatch,
}


def build_spec(seed: int, family: str, variant: str, entity: str,
               topic: Tuple[str, ...],
               paired_key: Optional[str] = None) -> WorldSpec:
    """Entry point used by the generator (kept out of module global state so
    every episode is a pure function of its seed)."""
    if family == "hitchhiker":
        return build_hitchhiker(seed, variant, entity, topic, paired_key)
    if family == "rare_bridge":
        return build_rare_bridge(seed, variant, entity, topic, paired_key)
    if family == "version_update":
        return build_version_update(seed, variant, entity, topic, paired_key)
    if family == "harmful_stale":
        return build_harmful_stale(seed, variant, entity, topic, paired_key)
    if family == "self_obscuring":
        return build_self_obscuring(seed, variant, entity, topic, paired_key)
    if family == "scope_mismatch":
        return build_scope_mismatch(seed, variant, entity, topic, paired_key)
    return build_control(seed, family, entity, topic)
