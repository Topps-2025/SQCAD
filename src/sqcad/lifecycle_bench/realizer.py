"""Trace Realizer: turns a frozen WorldSpec into multi-session natural
language with exact, auditable lexical-overlap properties (doc 22- 5.2).

The realizer is deterministic (a seeded template engine).  In this offline
environment the "agent that writes natural language" is this frozen engine;
an LLM can be swapped in later, but the *schema validation below stays*:
every task's query is checked against the memory it must overlap so the
world's designed thresholds (ADOPT_THRESHOLD / PROBE_THRESHOLD) hold.  The
LLM never decides truth; the designer + evaluator do (22- 5).

Design rule: every fact text and every query is built from a per-family
table.  The generator re-verifies the intended token-overlap matrix after
realization (``validate_episode``), so a drifted template fails the build.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .frozen import ADOPT_THRESHOLD, PROBE_THRESHOLD, REQUALIFY_OVERLAP
from .scenarios import FutureItemSpec, MemorySpec, SessionSpec, TaskSpec, WorldSpec

_STOP = {"a", "an", "the", "and", "or", "of", "for", "with", "at", "in",
         "on", "to", "is", "are", "was", "were", "has", "have", "had",
         "does", "do", "did", "his", "her", "their", "its", "it", "he",
         "she", "they", "we", "i", "you", "what", "which", "where", "when",
         "who", "how", "this", "that", "every", "each", "about", "not",
         "theirs", "ours"}


def tokenize(text: str) -> Tuple[str, ...]:
    """Lowercased alphanumeric tokens (drop stopwords).  Deterministic."""
    toks = [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]
    return tuple(t for t in toks if t not in _STOP)


def overlap(a: Sequence[str], b: Sequence[str]) -> int:
    return len(set(a) & set(b))


# ---------------------------------------------------------------------------
# per-family fact and query tables (parameterized by entity name)
# ---------------------------------------------------------------------------
# Each entry: (text, tokens).  Tokens are derived from text at build time;
# the tables below pin the TEXT, and the generator validates the overlaps.
def _topic_fillers(entity: str, slots: Sequence[str]) -> List[Tuple[str, str]]:
    """Deterministic (entity, slot) filler facts with exactly one shared
    topic token plus the entity token (cross-family interference <= 1)."""
    table = {
        "schedule": (f"{entity} has schedule meeting tuesday",
                     f"which schedule meeting does {entity} have tuesday"),
        "diet": (f"{entity} keeps diet meal plan snacks",
                 f"which diet meal plan does {entity} keep snacks"),
        "exercise": (f"{entity} follows exercise routine morning",
                     f"which exercise routine does {entity} follow morning"),
        "travel": (f"{entity} plans travel trip month",
                   f"which travel trip does {entity} plan month"),
        "finance": (f"{entity} manages finance budget project",
                    f"which finance budget does {entity} manage project"),
        "home": (f"{entity} spends weekend home family",
                 f"which weekend does {entity} spend home family"),
        "work": (f"{entity} writes work report friday",
                 f"which work report does {entity} write friday"),
        "study": (f"{entity} uses study guide course",
                  f"which study guide does {entity} use course"),
    }
    out = []
    for i, slot in enumerate(slots, 1):
        fact, q = table[slot]
        out.append((f"f{i}", fact, q))
    return out


# family -> realized memories; the realizer fills MemorySpec text fields
@dataclass(frozen=True)
class RealizedMemory:
    spec: MemorySpec
    text: str
    tokens: Tuple[str, ...]


@dataclass(frozen=True)
class RealizedMsg:
    speaker: str
    text: str
    kind: str = "msg"               # msg | update | correction
    fid: Optional[str] = None       # fact an event targets


@dataclass(frozen=True)
class RealizedSession:
    sid: str
    scope: str
    messages: Tuple[RealizedMsg, ...]


@dataclass(frozen=True)
class RealizedTask:
    spec: TaskSpec
    query: str
    tokens: Tuple[str, ...]


@dataclass(frozen=True)
class RealizedFutureItem:
    spec: FutureItemSpec
    text: Optional[str] = None      # event text
    event_kind: Optional[str] = None
    event_fid: Optional[str] = None
    task: Optional[RealizedTask] = None


@dataclass(frozen=True)
class RealizedEpisode:
    world: WorldSpec
    memories: Tuple[RealizedMemory, ...]
    sessions: Tuple[RealizedSession, ...]
    decision_task: RealizedTask
    future_items: Tuple[RealizedFutureItem, ...]

    def memory(self, fid: str) -> RealizedMemory:
        for m in self.memories:
            if m.spec.fid == fid:
                return m
        raise KeyError(fid)

    def tokens(self, fid: str) -> Tuple[str, ...]:
        return self.memory(fid).tokens


def _facts_and_queries(world: WorldSpec, entity: str) -> Dict[str, Tuple[str, str]]:
    """Map fid -> (fact_text, query_text) for the family's critical facts."""
    fam = world.family
    if fam == "hitchhiker":
        return {
            "e1": ("{e} talks about the volunteer organization stories",
                   "which organization does {e} volunteer with"),
            "h1": ("{e} likes volunteer stories about the local food bank",
                   "which stories does {e} tell about volunteer work"),
        }
    if fam == "rare_bridge":
        return {
            "m1": ("{e} keeps the passport document in the red drawer",
                   "where does {e} keep the passport document"),
        }
    if fam in ("version_update",):
        return {
            "m_old": ("{e} has contact phone number 555-0123",
                      "which number does {e} have to reach"),
            "m_new": ("{e} has contact phone number 555-0199",
                      "which number does {e} have to reach"),
        }
    if fam == "harmful_stale":
        return {
            # singular "peanut": the strong future query ("peanut food")
            # must overlap >= PROBE_THRESHOLD for the no_correction probe
            # to fire; tokenization is stem-free, so plural breaks it.
            "m_stale": ("{e} is allergic to peanut",
                        "which food is {e} allergic to"),
            "m_good": ("{e} is allergic to shellfish",
                       "which food is {e} allergic to"),
        }
    if fam == "self_obscuring":
        return {
            "m1": ("{e} takes allergy medication every morning",
                   "which allergy medication does {e} take every morning"),
        }
    if fam == "scope_mismatch":
        return {
            "m1": ("{e} has budget 5000 dollars for the marketing project",
                   "which budget does {e} have for the project"),
            "m2": ("{e} has budget 20000 dollars for the engineering project",
                   "which budget does {e} have for the project"),
        }
    if fam == "stable_positive":
        return {
            "m1": ("{e} has team lunch on fridays",
                   "when does {e} have team lunch"),
        }
    if fam == "stable_negative":
        return {
            "m1": ("{e} is allergic to peanut",
                   "which food is {e} allergic to"),
            "m_good": ("{e} is allergic to shellfish",
                       "which food is {e} allergic to"),
        }
    if fam == "neutral":
        return {
            "m1": ("{e} adopted a turtle named shelly",
                   "which schedule meeting does {e} have tuesday"),
        }
    raise KeyError(fam)


def _query_for(world: WorldSpec, entity: str, qplan: str) -> str:
    """Pick the concrete query text for a plan name (paraphrase levels)."""
    fam = world.family
    tables = {
        "hitchhiker": {
            "q_volunteer_org": "which organization does {e} volunteer with",
            "q_volunteer_chatter": "which stories does {e} tell about volunteer work",
            "q_volunteer_crowd": "which volunteer work does {e} do where and when",
            "q_diet": "which diet meal plan does {e} keep snacks",
            "q_schedule": "which schedule meeting does {e} have tuesday",
            "q_finance": "which finance budget does {e} manage project",
            "q_travel": "which travel trip does {e} plan month",
            "q_work": "which work report does {e} write friday",
            "q_study": "which study guide does {e} use course",
        },
        "rare_bridge": {
            "q_passport": "where does {e} keep the passport",
            "q_passport_rescue_possible": "where does {e} keep the passport document",
            "q_passport_rescue_impossible": "where does {e} keep the travel document",
            "q_schedule": "which schedule meeting does {e} have tuesday",
        },
        "version_update": {
            "q_phone": "which number does {e} have to reach",
            "q_schedule": "which schedule meeting does {e} have tuesday",
        },
        "harmful_stale": {
            "q_medication": "which food is {e} allergic to",
            "q_medication_strong": "which peanut food is {e} allergic to",
            "q_allergy_generic": "what is {e} allergy",
            "q_schedule": "which schedule meeting does {e} have tuesday",
        },
        "self_obscuring": {
            "q_medication": "which allergy medication does {e} take every morning",
            "q_medication_censored": "what does {e} take in the morning",
            "q_schedule": "which schedule meeting does {e} have tuesday",
        },
        "scope_mismatch": {
            "q_budget": "which budget does {e} have for the project",
            "q_schedule": "which schedule meeting does {e} have tuesday",
        },
        "stable_positive": {
            "q_schedule": "when does {e} have team lunch",
            "q_diet": "which diet meal plan does {e} keep snacks",
        },
        "stable_negative": {
            "q_medication": "which food is {e} allergic to",
            "q_schedule": "which schedule meeting does {e} have tuesday",
        },
        "neutral": {
            "q_schedule": "which schedule meeting does {e} have tuesday",
        },
    }
    q = tables[fam].get(qplan)
    if q is None:
        raise KeyError(f"{fam}:{qplan}")
    return q.format(e=entity)


def _event_text(world: WorldSpec, entity: str, kind: str, new_value: Optional[str]):
    fam = world.family
    if fam == "version_update":
        return (f"{entity} changed his contact phone number to 555-0199"
                if new_value else f"{entity} changed his contact phone number")
    if fam == "harmful_stale" or fam == "stable_negative":
        # correction REVISION (23- 6.1, dataset-revision round): the old
        # text ("peanuts are no longer part of {e} diet") shared only the
        # entity token with the stale fact under exact tokenization
        # ("peanuts" != "peanut": stem-free), so the lexical-overlap
        # requalification path (>= REQUALIFY_OVERLAP) was unreachable from
        # the public layer -- only the fid link fired.  The new text keeps
        # the exact tokens {entity, peanut}:  overlap 2 with the stale fact
        # (m_stale/m1: {entity, allergic, peanut}) but overlap 1 with the
        # good fact (m_good: {entity, allergic, shellfish}) -- so the good
        # fact's certificate stays POSITIVE and the correction is now
        # detectable by text-only policies too (R1 identifiability).
        return f"{entity}: peanuts -- the old peanut fact is wrong"
    raise KeyError(fam)


def _session_messages(world: WorldSpec, entity: str) -> Tuple[RealizedSession, ...]:
    """Realize the pre-decision sessions from the designer's message plans."""
    fam = world.family
    facts = _facts_and_queries(world, entity)
    out = []
    for s in world.sessions:
        sid, scope, plan, facts_introduced = (
            s.sid, s.scope, s.message_plan, s.facts_introduced)
        msgs = []
        for plan_name in plan:
            if plan_name == "distract":
                msgs.append(RealizedMsg("user",
                                        f"{entity} mentioned their recent {fid_topic(world)} plans"))
                msgs.append(RealizedMsg("assistant", "I will keep that in mind."))
            elif plan_name == "distract2":
                msgs.append(RealizedMsg("user",
                                        f"{entity} talked about the upcoming {fid_topic(world)} again"))
            elif plan_name.startswith("intro_"):
                intro_map = {"intro_evidence": "e1", "intro_hitchhiker": "h1",
                             "intro_passport": "m1", "intro_old_phone": "m_old",
                             "intro_new_phone": "m_new",
                             "intro_good_allergy": "m_good",
                             "intro_medication": "m1", "intro_budget_s1": "m1",
                             "intro_budget_s2": "m2", "intro_schedule": "m1",
                             "intro_neutral": "m1"}
                if plan_name == "intro_stale_allergy":
                    # the stale fact is m_stale in harmful_stale but m1 in
                    # the stable_negative control
                    fid = "m1" if fam == "stable_negative" else "m_stale"
                else:
                    fid = intro_map[plan_name]
                msgs.append(RealizedMsg("user", facts[fid][0].format(e=entity)))
            elif plan_name == "chatter_coexpose":
                msgs.append(RealizedMsg(
                    "user", f"{entity} again told us about the local food bank"))
            elif plan_name == "coexpose_again":
                msgs.append(RealizedMsg(
                    "user", f"{entity} mentioned the volunteer organization again"))
            elif plan_name == "update_phone":
                msgs.append(RealizedMsg(
                    "user", _event_text(world, entity, "update", "555-0199"),
                    kind="update", fid="m_old"))
            elif plan_name == "correction_allergy":
                # the stale fact is m_stale in harmful_stale but m1 in the
                # stable_negative control (same pattern as intro_stale_allergy)
                fid = "m1" if fam == "stable_negative" else "m_stale"
                msgs.append(RealizedMsg(
                    "user", _event_text(world, entity, "correction", None),
                    kind="correction", fid=fid))
            else:
                raise KeyError(plan_name)
        out.append(RealizedSession(sid, scope, tuple(msgs)))
    return tuple(out)


def fid_topic(world: WorldSpec) -> str:
    return {
        "hitchhiker": "volunteer",
        "rare_bridge": "passport",
        "version_update": "phone",
        "harmful_stale": "diet",
        "self_obscuring": "medication",
        "scope_mismatch": "budget",
        "stable_positive": "lunch",
        "stable_negative": "diet",
        "neutral": "schedule",
    }[world.family]


def realize(world: WorldSpec) -> RealizedEpisode:
    """Deterministic realization of one WorldSpec."""
    entity = world.memories[0].entity
    facts = _facts_and_queries(world, entity)

    # critical/evidence facts from the table; fillers from topic tables
    realized = []
    for m in world.memories:
        if m.fid in facts:
            text = facts[m.fid][0].format(e=entity)
        elif m.role == "filler" or m.role == "hitchhiker":
            text = _filler_text_for(m, entity, world)
        else:
            text = _fallback_text(m, entity)
        tokens = tokenize(text)
        realized.append(RealizedMemory(m, text, tokens))

    sessions = _session_messages(world, entity)

    # decision task
    q0 = _query_for(world, entity, world.decision_task.query_plan)
    decision = RealizedTask(world.decision_task, q0, tokenize(q0))

    # future items
    future = []
    for item in world.future_items:
        if item.kind == "event":
            text = _event_text(world, entity, item.event_kind or "",
                               item.event_new_value)
            future.append(RealizedFutureItem(
                item, text=text, event_kind=item.event_kind,
                event_fid=item.event_fid))
        else:
            t = item.task
            assert t is not None
            q = _query_for(world, entity, t.query_plan)
            future.append(RealizedFutureItem(
                item, task=RealizedTask(t, q, tokenize(q))))
    return RealizedEpisode(world, tuple(realized), sessions, decision,
                           tuple(future))


def _filler_text_for(m: MemorySpec, entity: str, world: WorldSpec) -> str:
    """Filler facts: volunteer-flavored for hitchhiker, medication-flavored
    for self_obscuring, topic fillers otherwise."""
    fam = world.family
    fid = m.fid
    if fam == "hitchhiker" and fid.startswith("f_vol"):
        # "work stories" pins overlap 3 with BOTH q_volunteer_crowd and
        # q_volunteer_chatter (crowding / probe-denial geometry, 22-).
        places = ("in the garden", "in the park", "in the kitchen", "at the shelter",
                  "by the river", "at the school", "at the clinic", "on the farm",
                  "in the library")
        idx = int(fid.split("_vol")[1]) - 1
        return f"{entity} does volunteer work stories {places[idx % len(places)]}"
    if fam == "self_obscuring" and fid.startswith("f_med"):
        # four shared tokens with q_medication ("her" is a stopword): the
        # crowding workspace saturates at score 4.0 and denies the probe.
        places = ("in the garden", "in the park", "in the kitchen", "at the shelter",
                  "by the river", "at the school", "at the clinic", "on the farm",
                  "in the library")
        idx = int(fid.split("_med")[1]) - 1
        return f"{entity} takes allergy medication every morning {places[idx % len(places)]}"
    # topic fillers: reuse the topic table
    for table in _topic_fillers(entity, (
            "schedule", "diet", "exercise", "travel", "finance",
            "home", "work", "study")):
        if table[0] == fid:
            return table[1]
    raise KeyError(fid)


def _fallback_text(m: MemorySpec, entity: str) -> str:
    raise KeyError(f"{m.fid} has no realization template")


def validate_episode(ep: RealizedEpisode) -> None:
    """Schema validation (22- 5.2): the intended overlap matrix must hold.

    * every task's needed memory must be adoptable (overlap >= ADOPT);
    * probe-affecting overlaps are asserted per family later in the
      contract tests (they depend on the reference policy's rules);
    * the public trace must not leak hidden gold (future needed ids and
      future-only values appear only from their slot on).
    """
    fam = ep.world.family
    for item in ep.future_items:
        if item.spec.kind != "task" or item.task is None:
            continue
        t = item.task
        if t.spec.needed_fid is not None:
            got = overlap(t.tokens, ep.tokens(t.spec.needed_fid))
            if got < ADOPT_THRESHOLD:
                raise AssertionError(
                    f"{ep.world.episode_id} slot {t.spec.slot}: needed "
                    f"{t.spec.needed_fid} overlap {got} < ADOPT_THRESHOLD")
    # no-leak: hidden needed ids are fid strings, never realize into text
    for item in ep.future_items:
        if item.task is not None and item.task.spec.needed_fid is not None:
            fid = item.task.spec.needed_fid
            for sess in ep.sessions:
                for msg in sess.messages:
                    if fid in msg.text:
                        raise AssertionError(
                            f"{ep.world.episode_id}: needed id {fid} leaked "
                            f"into session {sess.sid}")
    # future-only values (updates) must not appear before their slot
    if fam == "version_update" and ep.world.variant == "update_after":
        for sess in ep.sessions:
            for msg in sess.messages:
                if "555-0199" in msg.text:
                    raise AssertionError(
                        f"{ep.world.episode_id}: future update value leaked "
                        f"into a pre-decision session")
