"""Identification recovery experiment — two stages (validates Theorem 3).

Stage 1 — Ideal identification environment.
  The SQCAD rollout estimator (randomized persistent action A_i^pers at epoch
  start, then an H-step rollout under target policy pi) must recover the known
  lifecycle value: bias ~= 0, 95% CI coverage ~= 0.95, confident decisions
  match the oracle. Association / CMI / naive OPE fail on the *expected*
  estimand mismatches (short-term useful, lifecycle-harmful memories).

Stage 2 — Progressive condition violation (one violation at a time):
    adoption_error        (C6)   D != E -> gate abstains (unresolved)
    co_exposure           (C7)   bundle treatment -> gate abstains for the pair
    eligibility_selection (C3)   harmful memories never randomized -> unresolved
    measurement_drift     (C8)   version change mid-window -> mismatch
    scope_shift           (Cor1) source evidence for target decision -> mismatch

Estimator/oracle consistency (per reviewer): the oracle computes V_true with
the SAME horizon H, discount gamma, and action window as the estimator; both
sample the same mechanism from independent RNG streams. In Stage 2 the oracle
always evaluates the pre-registered (intended) estimand, so drift / adoption /
selection violations surface as estimator bias, and the gate must abstain.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, pstdev, stdev
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Roles & world structure
# ---------------------------------------------------------------------------

TASK_TYPES = ("common", "rare", "critical")

SOURCE_TASK_DIST = {"common": 0.70, "rare": 0.20, "critical": 0.10}
TARGET_TASK_DIST = {"common": 0.90, "rare": 0.07, "critical": 0.03}

# Memory roles:
#   useful     — positive per-exposure effect on every task. Lifecycle: keep.
#   short_term — positive LOCAL effect, but keeping it suppresses bridge-memory
#                candidate generation (crowding). Lifecycle: archive.
#   bridge     — small local effect; large STATUS bonus on rare/critical when
#                kept (retrieval path). Lifecycle: keep.
#   harmful    — negative per-exposure effect. Lifecycle: archive.
#   neutral    — no effect. Lifecycle ~ 0 (indistinguishable -> unresolved).
ROLE_USEFUL, ROLE_SHORT_TERM, ROLE_BRIDGE, ROLE_HARMFUL, ROLE_NEUTRAL = \
    "useful", "short_term", "bridge", "harmful", "neutral"

SHORT_SUPPRESS = 0.15       # per kept short_term: bridge exposure prob factor
BRIDGE_BONUS = 1.5          # status bonus on rare/critical when bridge kept
DRIFT_BOOST = 2.0           # v2 model: extra outcome per exposed memory

DEFAULT_ROLE_COUNTS: Dict[str, int] = {
    ROLE_USEFUL: 3, ROLE_SHORT_TERM: 2, ROLE_BRIDGE: 2,
    ROLE_HARMFUL: 2, ROLE_NEUTRAL: 3,
}


@dataclass
class WorldConfig:
    n_memories: int = 12
    n_epochs: int = 150              # rollout horizon H (estimator AND oracle)
    n_trajectories: int = 100        # RCT trajectories per (memory, action)
    n_oracle: int = 300              # oracle trajectories per (memory, action)
    n_source_steps: int = 3000       # observational pre-intervention log
    n_query_contexts: int = 300      # query-local CMI forced-in/out contexts
    p_probe: float = 0.2             # exploration: probed exposure of archived
                                     # candidates in the observational log
    gamma: float = 0.98
    lam: float = 0.0                 # cost weight (pre-registered; 0 in v2)
    rho: float = 0.0                 # risk weight (pre-registered; 0 in v2)
    seed: int = 7
    noise: float = 0.5
    p_expose: float = 0.6            # exposure prob of an active memory
    # ---- Stage 2 violation switches (one at a time) ----
    adoption_error: float = 0.0      # C6: P(D != E) per exposure step
    co_exposure: bool = False        # C7: pair treated as a bundle
    eligibility_selection: bool = False  # C3: only local Delta >= threshold randomized
    measurement_drift: bool = False  # C8: v2 boost after H/2
    scope_shift: bool = False        # Cor1: source evidence -> target decision
    eligibility_threshold: float = -0.2
    adoption_audit_steps: int = 200  # gate audit sample size


@dataclass
class MemorySpec:
    mem_id: str
    role: str
    effect: float                    # per-exposure effect on Y (all tasks)
    bridge_bonus: float = 0.0        # status bonus on rare/critical when active


class World:
    """Synthetic memory-augmented agent world with known mechanisms."""

    def __init__(self, cfg: WorldConfig):
        self.cfg = cfg
        self.memories: List[MemorySpec] = self._build_memories()
        self.spec_map: Dict[str, MemorySpec] = {m.mem_id: m for m in self.memories}
        self.bridge_ids = {m.mem_id for m in self.memories if m.role == ROLE_BRIDGE}
        self.short_ids = {m.mem_id for m in self.memories if m.role == ROLE_SHORT_TERM}
        # C7 bundle pair: first useful + first harmful
        useful = [m for m in self.memories if m.role == ROLE_USEFUL]
        harmful = [m for m in self.memories if m.role == ROLE_HARMFUL]
        self.pair: Optional[Tuple[str, str]] = None
        if cfg.co_exposure and useful and harmful:
            self.pair = (useful[0].mem_id, harmful[0].mem_id)

    # -- construction ------------------------------------------------------

    def _build_memories(self) -> List[MemorySpec]:
        cfg = self.cfg
        counts = dict(DEFAULT_ROLE_COUNTS)
        roles: List[str] = []
        for role, n in counts.items():
            roles += [role] * n
        roles = roles[: cfg.n_memories]
        mems: List[MemorySpec] = []
        for k, role in enumerate(roles):
            if role == ROLE_USEFUL:
                eff = 1.2
            elif role == ROLE_SHORT_TERM:
                eff = 0.2            # positive LOCAL effect, lifecycle-negative
            elif role == ROLE_BRIDGE:
                eff = 0.2
            elif role == ROLE_HARMFUL:
                # C7: the bundle pairs a useful (+1.2) with a harmful (-1.0)
                # member, so the composite is positive and the harm is hidden
                # inside the bundle
                eff = -1.0
            else:
                eff = 0.0
            bonus = BRIDGE_BONUS if role == ROLE_BRIDGE else 0.0
            mems.append(MemorySpec(mem_id=f"m{k}", role=role,
                                   effect=eff, bridge_bonus=bonus))
        return mems

    # -- mechanism ---------------------------------------------------------

    def task_dist(self, scope: str) -> Dict[str, float]:
        if self.cfg.scope_shift and scope == "target":
            return dict(TARGET_TASK_DIST)
        return dict(SOURCE_TASK_DIST)

    def _task_cum(self, scope: str) -> Tuple[Tuple[str, ...], Tuple[float, ...]]:
        dist = self.task_dist(scope)
        keys = tuple(dist.keys())
        cum = []
        c = 0.0
        for k in keys:
            c += dist[k]
            cum.append(c)
        return keys, tuple(cum)

    def background_access(self) -> Dict[str, str]:
        """Status-quo retention policy: keep useful + bridge, archive the rest.

        Under the C7 violation the bundle pair is kept TOGETHER by the status
        quo (the pair is always co-proposed) — that is what makes the
        co-exposure observable and the harm hidden inside the bundle.
        """
        keeps = {m.mem_id for m in self.memories
                 if m.role in (ROLE_USEFUL, ROLE_BRIDGE)}
        if self.pair is not None:
            keeps.update(self.pair)
        return {m.mem_id: ("keep" if m.mem_id in keeps else "archive")
                for m in self.memories}

    def active_ids(self, target_id: Optional[str], target_action: Optional[str],
                   background: Dict[str, str]) -> List[str]:
        active = [mid for mid, act in background.items() if act == "keep"]
        if target_id is not None:
            if target_action == "keep" and target_id not in active:
                active.append(target_id)
            elif target_action == "archive" and target_id in active:
                active.remove(target_id)
        return active

    def spec(self, mem_id: str) -> MemorySpec:
        return self.spec_map[mem_id]

    def _task_type(self, rng: random.Random, scope: str) -> str:
        # fast categorical draw (rng.choices rebuilds cumulative weights every
        # call — too slow in the ~1M-step hot loop)
        keys, cum = self._task_cum(scope)
        r = rng.random()
        for k, c in zip(keys, cum):
            if r < c:
                return k
        return keys[-1]

    def sample_rollout(self, rng: random.Random, target_id: Optional[str],
                       target_action: Optional[str],
                       scope: str = "source",
                       drift: bool = False) -> Tuple[float, float, float]:
        """One H-step rollout; returns (utility, mean_y_half1, mean_y_half2).

        target_id/target_action = the do(A_i^pers = a) assignment; others
        follow the background policy. utility = sum gamma^t (Y - lam*C - rho*R).
        The half means are UNWEIGHTED per-step outcomes (discounting removed)
        so the gate's stability check can compare version strata without
        picking up the discount trend.
        """
        bg = self.background_access()
        active = self.active_ids(target_id, target_action, bg)
        return self._rollout_core(rng, active, scope, drift)

    def sample_rollout_joint(self, rng: random.Random, ids: Sequence[str],
                             action: str, scope: str = "source",
                             drift: bool = False) -> Tuple[float, float, float]:
        """Bundle-level rollout (C7): keep/archive ALL of ids jointly."""
        bg = self.background_access()
        active = [mid for mid, act in bg.items() if act == "keep"]
        for mid in ids:
            if action == "keep" and mid not in active:
                active.append(mid)
            elif action == "archive" and mid in active:
                active.remove(mid)
        return self._rollout_core(rng, active, scope, drift)

    def _rollout_core(self, rng: random.Random, active: List[str],
                      scope: str, drift: bool) -> Tuple[float, float, float]:
        cfg = self.cfg
        last_adoption: Dict[str, float] = {}
        total = 0.0
        sum_h1 = 0.0
        sum_h2 = 0.0
        n_h1 = 0
        n_h2 = 0
        for t in range(cfg.n_epochs):
            version = 1 if (drift and t >= cfg.n_epochs // 2) else 0
            task = self._task_type(rng, scope)
            difficulty = rng.random()

            # exposure: base prob + adoption boost (policy acts on adoption)
            n_short = 0
            for mid in active:
                if self.spec_map[mid].role == ROLE_SHORT_TERM:
                    n_short += 1
            E: Dict[str, float] = {}
            for mid in active:
                mem = self.spec_map[mid]
                p = self.cfg.p_expose
                if mem.role == ROLE_BRIDGE and n_short > 0:
                    p *= SHORT_SUPPRESS ** n_short
                p = min(p * (1.0 + 0.5 * last_adoption.get(mid, 0.0)), 1.0)
                E[mid] = 1.0 if rng.random() < p else 0.0
            # C7 violation: pair exposures perfectly coupled (bundle)
            if self.pair is not None and all(m in E for m in self.pair):
                u, h = self.pair
                E[h] = E[u]
            # C6 violation: adoption proxy misattributed
            D: Dict[str, float] = dict(E)
            if cfg.adoption_error > 0.0:
                D = {m: (1.0 - v) if rng.random() < cfg.adoption_error else v
                     for m, v in E.items()}
            last_adoption = D

            # outcome
            y = 0.5 - 0.5 * difficulty
            n_exposed = 0
            for mid, e in E.items():
                n_exposed += int(e)
                y += self.spec_map[mid].effect * e
            # bridge STATUS bonus (retrieval path) — visible only to rollout
            if task in ("rare", "critical"):
                for mid in active:
                    if self.spec_map[mid].role == ROLE_BRIDGE:
                        y += self.spec_map[mid].bridge_bonus
            if version == 1:
                y += DRIFT_BOOST * n_exposed
            y += rng.gauss(0.0, cfg.noise)

            contrib = math.pow(cfg.gamma, t) * (y - cfg.lam * n_exposed
                                                - cfg.rho * n_exposed)
            total += contrib
            if t < cfg.n_epochs // 2:
                sum_h1 += y
                n_h1 += 1
            else:
                sum_h2 += y
                n_h2 += 1
        return total, (sum_h1 / n_h1 if n_h1 else 0.0), \
            (sum_h2 / n_h2 if n_h2 else 0.0)

    def sample_query_local(self, rng: random.Random, mem_id: str,
                           scope: str = "source") -> Tuple[float, float]:
        """One fixed query context; returns (Y|do(E=1), Y|do(E=0)) for mem_id.

        Query-local: only this memory toggled for the CURRENT step (no
        rollout), everything else fixed — what a CMI audit would measure.
        """
        cfg = self.cfg
        task = self._task_type(rng, scope)
        difficulty = rng.random()
        noise = rng.gauss(0.0, cfg.noise)
        mem = self.spec(mem_id)
        base = 0.5 - 0.5 * difficulty + noise
        y_in = base + mem.effect
        if task in ("rare", "critical"):
            y_in += mem.bridge_bonus  # status bonus applies when active
        return y_in, base

    def source_log(self, rng: random.Random) -> List[Dict[str, Any]]:
        """Pre-intervention observational log under the background policy.

        Archived candidates are PROBED with probability p_probe (platform
        exploration, cf. shadow deployment / A/B probes in OPE): otherwise
        observational methods would never see memories the status-quo policy
        archives, and their failure would be a data-vacuum artefact rather
        than an estimand mismatch.
        """
        cfg = self.cfg
        bg = self.background_access()
        active = self.active_ids(None, None, bg)
        rows: List[Dict[str, Any]] = []
        for t in range(cfg.n_source_steps):
            task = self._task_type(rng, "source")
            difficulty = rng.random()
            n_short = 0
            for mid in active:
                if self.spec_map[mid].role == ROLE_SHORT_TERM:
                    n_short += 1
            E: Dict[str, float] = {}
            for mid in active:
                mem = self.spec_map[mid]
                p = self.cfg.p_expose
                if mem.role == ROLE_BRIDGE and n_short > 0:
                    p *= SHORT_SUPPRESS ** n_short
                E[mid] = 1.0 if rng.random() < p else 0.0
            for mid in bg:            # probe archived candidates
                if mid not in active:
                    E[mid] = 1.0 if rng.random() < cfg.p_probe else 0.0
            if self.pair is not None and all(m in E for m in self.pair):
                u, h = self.pair
                E[h] = E[u]
            D = dict(E)
            if cfg.adoption_error > 0.0:
                D = {m: (1.0 - v) if rng.random() < cfg.adoption_error else v
                     for m, v in E.items()}
            y = 0.5 - 0.5 * difficulty
            for mid, e in E.items():
                y += self.spec_map[mid].effect * e
            if task in ("rare", "critical"):
                for mid in active:
                    if self.spec_map[mid].role == ROLE_BRIDGE:
                        y += self.spec_map[mid].bridge_bonus
            y += rng.gauss(0.0, cfg.noise)
            for mid in E:
                rows.append({
                    "time": float(t), "scope": "source", "item": mid,
                    "task": task, "difficulty": difficulty,
                    "exposed": E[mid], "adoption": D[mid],
                    "outcome": y, "success": 1.0 if y > 0.0 else 0.0,
                })
        return rows


# ---------------------------------------------------------------------------
# Oracle: ground-truth lifecycle values (same H, gamma, action window)
# ---------------------------------------------------------------------------

def compute_oracle_values(world: World, cfg: WorldConfig,
                          scope: str = "source") -> Dict[str, float]:
    """V_true(i) = E[rollout | do(keep_i)] - E[rollout | do(archive_i)].

    The oracle samples the INTENDED (pre-registered) estimand: drift/scope
    are never applied to the oracle itself.
    """
    rng = random.Random(cfg.seed + 1)
    values: Dict[str, float] = {}
    for mem in world.memories:
        keep_u = [world.sample_rollout(rng, mem.mem_id, "keep", scope)[0]
                  for _ in range(cfg.n_oracle)]
        arc_u = [world.sample_rollout(rng, mem.mem_id, "archive", scope)[0]
                 for _ in range(cfg.n_oracle)]
        values[mem.mem_id] = mean(keep_u) - mean(arc_u)
    return values


def compute_bundle_oracle(world: World, cfg: WorldConfig,
                          pair: Tuple[str, str]) -> Dict[str, Any]:
    """Oracle for the C7 bundle (both kept vs both archived, jointly)."""
    rng = random.Random(cfg.seed + 11)
    keep_u = [world.sample_rollout_joint(rng, pair, "keep")[0]
              for _ in range(cfg.n_oracle)]
    arc_u = [world.sample_rollout_joint(rng, pair, "archive")[0]
             for _ in range(cfg.n_oracle)]
    return {"pair": list(pair), "bundle_value": mean(keep_u) - mean(arc_u)}


def compute_local_effects(world: World, cfg: WorldConfig) -> Dict[str, float]:
    """True query-local do-effects (CMI oracle): E[Y|do(E=1)]-E[Y|do(E=0)]."""
    rng = random.Random(cfg.seed + 3)
    out: Dict[str, float] = {}
    for mem in world.memories:
        diffs = []
        for _ in range(cfg.n_query_contexts):
            y_in, y_out = world.sample_query_local(rng, mem.mem_id)
            diffs.append(y_in - y_out)
        out[mem.mem_id] = mean(diffs)
    return out


# ---------------------------------------------------------------------------
# Estimators
# ---------------------------------------------------------------------------

def estimate_association(source_log: List[Dict[str, Any]],
                         mem_ids: Sequence[str]) -> Dict[str, float]:
    """Memory Worth: Beta(1,1)-posterior mean success given exposure."""
    by_mem: Dict[str, List[float]] = defaultdict(list)
    for row in source_log:
        if row["exposed"] == 1.0:
            by_mem[row["item"]].append(row["success"])
    return {mem: (sum(by_mem.get(mem, [])) + 1.0) / (len(by_mem.get(mem, [])) + 2.0)
            for mem in mem_ids}


def _exposure_contrast(source_log: List[Dict[str, Any]],
                       mem_ids: Sequence[str]) -> Dict[str, float]:
    """E[Y|E=1] - E[Y|E=0] per memory from the observational log."""
    by_mem: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for row in source_log:
        lst = by_mem[row["item"]]
        if row["exposed"] == 1.0:
            lst[0] += row["outcome"]; lst[2] += 1.0
        else:
            lst[1] += row["outcome"]; lst[3] += 1.0
    out: Dict[str, float] = {}
    for mem in mem_ids:
        s, h, n1, n0 = by_mem[mem]
        out[mem] = (s / n1 if n1 > 0 else 0.0) - (h / n0 if n0 > 0 else 0.0)
    return out


def estimate_naive_ope(source_log: List[Dict[str, Any]],
                       mem_ids: Sequence[str]) -> Dict[str, float]:
    """Naive OPE/MSM: per-scope causal contrast, transported unconditionally
    to the target scope. (Exposure is randomized here, so the contrast is an
    unbiased local do-effect — the failure is the estimand, not the estimate.)"""
    return _exposure_contrast(source_log, mem_ids)


def estimate_cmi_observed(source_log: List[Dict[str, Any]],
                          mem_ids: Sequence[str]) -> Dict[str, float]:
    """What a deployed CMI would estimate from logs (same functional; kept as
    a separate name so the report can state it is unbiased for the local
    effect and still insufficient for the lifecycle decision)."""
    return _exposure_contrast(source_log, mem_ids)


def estimate_sqcad_rct(world: World, cfg: WorldConfig,
                       mem_ids: Sequence[str],
                       eligible: Optional[Set[str]] = None) -> Dict[str, Any]:
    """Protocol route (Theorem 3(a)): randomized persistent action, H-step
    rollout under pi. Returns per-memory {estimate, se, n, ci_low, ci_high}."""
    rng = random.Random(cfg.seed + 5)
    out: Dict[str, Any] = {}
    for mem_id in mem_ids:
        if eligible is not None and mem_id not in eligible:
            out[mem_id] = {"estimate": None, "se": None, "n": 0,
                           "ci_low": None, "ci_high": None}
            continue
        # the estimator samples the ACTUAL world mechanism (which drifts under
        # C8); the oracle always evaluates the pre-registered estimand
        drift = cfg.measurement_drift
        keep_u = [world.sample_rollout(rng, mem_id, "keep", drift=drift)[0]
                  for _ in range(cfg.n_trajectories)]
        arc_u = [world.sample_rollout(rng, mem_id, "archive", drift=drift)[0]
                 for _ in range(cfg.n_trajectories)]
        est = mean(keep_u) - mean(arc_u)
        se = math.sqrt(pstdev(keep_u) ** 2 / len(keep_u) +
                       pstdev(arc_u) ** 2 / len(arc_u))
        out[mem_id] = {
            "estimate": est, "se": se, "n": cfg.n_trajectories,
            "ci_low": est - 1.96 * se, "ci_high": est + 1.96 * se,
        }
    return out


def estimate_bundle_rct(world: World, cfg: WorldConfig,
                        pair: Tuple[str, str]) -> Dict[str, Any]:
    """C7 bundle-level randomized rollout (the only intervention available
    when the pair cannot be separated): keep-both vs archive-both jointly."""
    rng = random.Random(cfg.seed + 7)
    drift = cfg.measurement_drift
    keep_u = [world.sample_rollout_joint(rng, pair, "keep", drift=drift)[0]
              for _ in range(cfg.n_trajectories)]
    arc_u = [world.sample_rollout_joint(rng, pair, "archive", drift=drift)[0]
             for _ in range(cfg.n_trajectories)]
    est = mean(keep_u) - mean(arc_u)
    se = math.sqrt(pstdev(keep_u) ** 2 / len(keep_u) +
                   pstdev(arc_u) ** 2 / len(arc_u))
    return {"pair": list(pair), "estimate": est, "se": se, "n": cfg.n_trajectories}


# ---------------------------------------------------------------------------
# Qualification gate (Theorem 3(d) + access protocol)
# ---------------------------------------------------------------------------

ADOPTION_THRESHOLD = 0.05
CO_EXPOSURE_THRESHOLD = 0.85
STABILITY_Z_THRESHOLD = 3.0


def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def _stability_z(world: World, cfg: WorldConfig) -> float:
    """z-score of per-action half-difference (v2 vs v1), pooled over memories.

    Uses the world's own drift mechanism: with measurement_drift the second
    half of every keep-rollout is inflated, so the pooled half-difference is
    far from zero; without drift it centres on zero.
    """
    rng = random.Random(cfg.seed + 9)
    diffs: List[float] = []
    for mem in world.memories:
        for action in ("keep", "archive"):
            for _ in range(20):
                _, h1, h2 = world.sample_rollout(rng, mem.mem_id, action,
                                                 drift=cfg.measurement_drift)
                diffs.append(h2 - h1)
    m = mean(diffs)
    sd = stdev(diffs) if len(diffs) > 1 else 1.0
    return m / (sd / math.sqrt(len(diffs))) if sd > 0 else 0.0


def run_gate_checks(world: World, cfg: WorldConfig,
                    source_log: List[Dict[str, Any]],
                    rct_estimates: Dict[str, Any]) -> Dict[str, Any]:
    """Check each identification condition; returns per-check pass/fail.

    Global checks: adoption quality (C6), measurement stability (C8),
    scope match (Cor1). Per-memory checks: overlap (C3), co-exposure (C7).
    """
    checks: Dict[str, Any] = {}

    # ---- C6: adoption quality (audit D vs true E on a sample) ----
    audit = [r for r in source_log if r["item"] == world.memories[0].mem_id]
    audit = audit[: cfg.adoption_audit_steps]
    disagreement = mean(abs(r["adoption"] - r["exposed"]) for r in audit) \
        if audit else 0.0
    checks["adoption_quality"] = {
        "passed": disagreement <= ADOPTION_THRESHOLD,
        "disagreement_rate": disagreement,
    }

    # ---- C8: measurement stability (version strata differ?) ----
    z = _stability_z(world, cfg)
    checks["measurement_stability"] = {
        "passed": abs(z) < STABILITY_Z_THRESHOLD, "z": z}

    # ---- Cor1: scope match ----
    checks["scope_match"] = {
        "passed": not cfg.scope_shift,
        "note": "source evidence may not be transported to target scope",
    }

    # ---- C3 per-memory overlap ----
    checks["overlap"] = {}
    for mem in world.memories:
        est = rct_estimates.get(mem.mem_id, {})
        checks["overlap"][mem.mem_id] = {
            "passed": est.get("n", 0) > 0,
            "n_trajectories": est.get("n", 0),
        }

    # ---- C7 per-memory co-exposure ----
    checks["co_exposure"] = {}
    by_mem: Dict[str, List[float]] = defaultdict(list)
    for row in source_log:
        by_mem[row["item"]].append(row["exposed"])
    for mem in world.memories:
        corr_max = 0.0
        for other in world.memories:
            if other.mem_id == mem.mem_id:
                continue
            xs, ys = by_mem[mem.mem_id], by_mem[other.mem_id]
            n = min(len(xs), len(ys))
            if n < 10:
                continue
            corr_max = max(corr_max, abs(_pearson(xs[:n], ys[:n])))
        checks["co_exposure"][mem.mem_id] = {
            "passed": corr_max <= CO_EXPOSURE_THRESHOLD,
            "max_abs_corr": corr_max,
        }

    return checks


def qualification_status(checks: Dict[str, Any], mem_id: str,
                         est: Optional[float], se: Optional[float]) -> str:
    """Output space {keep, archive, unresolved, mismatch}.

    Global identification failures first (scope/version -> mismatch,
    adoption -> unresolved), then per-memory checks, then the decision
    threshold (CI must not cross zero).
    """
    if not checks["scope_match"]["passed"]:
        return "mismatch"
    if not checks["measurement_stability"]["passed"]:
        return "mismatch"
    if not checks["adoption_quality"]["passed"]:
        return "unresolved"
    if not checks["overlap"][mem_id]["passed"]:
        return "unresolved"
    if not checks["co_exposure"][mem_id]["passed"]:
        return "unresolved"
    if est is None or se is None:
        return "unresolved"
    if abs(est) < 1.96 * se:          # CI crosses the decision threshold
        return "unresolved"
    return "keep" if est > 0 else "archive"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _decision_regret(decisions: Dict[str, str],
                     true_values: Dict[str, float]) -> Dict[str, Any]:
    """Regret over CONFIDENT (keep/archive) decisions only; unresolved and
    mismatch defer and incur no regret."""
    oracle_utility = sum(max(v, 0.0) for v in true_values.values())
    actual = 0.0
    n_confident = 0
    n_correct = 0
    n_unresolved = 0
    n_mismatch = 0
    for mem, dec in decisions.items():
        v = true_values.get(mem, 0.0)
        if dec == "keep":
            n_confident += 1
            if v > 0:
                n_correct += 1
            actual += v
        elif dec == "archive":
            n_confident += 1
            if v < 0:
                n_correct += 1
        elif dec == "unresolved":
            n_unresolved += 1
        else:
            n_mismatch += 1
    n_total = len(decisions)
    return {
        "regret": oracle_utility - actual,
        "n_confident": n_confident,
        "n_correct_confident": n_correct,
        "error_rate": (n_confident - n_correct) / n_confident
        if n_confident else 0.0,
        "n_unresolved": n_unresolved,
        "n_mismatch": n_mismatch,
        "unresolved_rate": n_unresolved / n_total if n_total else 0.0,
    }


def _value_recovery(estimates: Dict[str, Any],
                    true_values: Dict[str, float]) -> Dict[str, Any]:
    per_mem: Dict[str, Dict[str, Any]] = {}
    biases: List[float] = []
    covered = 0
    n_ci = 0
    for mem, v_true in true_values.items():
        e = estimates.get(mem, {})
        est, se, lo, hi = e.get("estimate"), e.get("se"), \
            e.get("ci_low"), e.get("ci_high")
        if est is None or se is None:
            per_mem[mem] = {"bias": None, "covered": None}
            continue
        bias = est - v_true
        biases.append(bias)
        covered += 1 if (lo <= v_true <= hi) else 0
        n_ci += 1
        per_mem[mem] = {"estimate": est, "true": v_true, "bias": bias,
                        "ci_low": lo, "ci_high": hi,
                        "covered": lo <= v_true <= hi}
    return {
        "bias": mean(biases) if biases else None,
        "rmse": math.sqrt(mean(b ** 2 for b in biases)) if biases else None,
        "ci_coverage": covered / n_ci if n_ci else None,
        "n_ci": n_ci,
        "per_memory": per_mem,
    }


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

def _baseline_decisions(world: World, cfg: WorldConfig,
                        source_log: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    mem_ids = [m.mem_id for m in world.memories]
    assoc = estimate_association(source_log, mem_ids)
    cmi = estimate_cmi_observed(source_log, mem_ids)
    ope = estimate_naive_ope(source_log, mem_ids)
    return {
        "association": {mem: {"score": assoc[mem],
                              "decision": "keep" if assoc[mem] > 0.5 else "archive"}
                        for mem in mem_ids},
        "cmi": {mem: {"estimate": cmi[mem],
                      "decision": "keep" if cmi[mem] > 0 else "archive"}
                for mem in mem_ids},
        "naive_ope": {mem: {"estimate": ope[mem],
                            "decision": "keep" if ope[mem] > 0 else "archive"}
                      for mem in mem_ids},
    }


def run_stage1(cfg: WorldConfig | None = None) -> Dict[str, Any]:
    cfg = cfg or WorldConfig()
    world = World(cfg)
    mem_ids = [m.mem_id for m in world.memories]

    source_log = world.source_log(random.Random(cfg.seed + 2))
    local_effects = compute_local_effects(world, cfg)
    true_values = compute_oracle_values(world, cfg)

    # SQCAD protocol route
    rct = estimate_sqcad_rct(world, cfg, mem_ids)
    checks = run_gate_checks(world, cfg, source_log, rct)
    sqcad_status = _sqcad_decisions(rct, checks, mem_ids)
    forced: Dict[str, str] = {}
    for mem in mem_ids:
        est = rct[mem].get("estimate")
        forced[mem] = "keep" if (est is not None and est > 0) else "archive"

    baselines = _baseline_decisions(world, cfg, source_log)
    decisions = {
        "sqcad_rct": sqcad_status,
        "sqcad_forced": forced,
        "association": {m: d["decision"] for m, d in baselines["association"].items()},
        "cmi": {m: d["decision"] for m, d in baselines["cmi"].items()},
        "naive_ope": {m: d["decision"] for m, d in baselines["naive_ope"].items()},
    }

    recovery = _value_recovery(rct, true_values)
    decision_quality = {m: _decision_regret(d, true_values)
                        for m, d in decisions.items()}

    confident_wrong = [m for m in mem_ids
                       if sqcad_status[m] in ("keep", "archive")
                       and (true_values[m] > 0) != (sqcad_status[m] == "keep")]
    unresolved_mems = [m for m, s in sqcad_status.items() if s == "unresolved"]

    ok = (recovery["bias"] is not None and abs(recovery["bias"]) < 1.0
          and recovery["ci_coverage"] is not None
          and recovery["ci_coverage"] >= 0.8
          and len(confident_wrong) == 0)

    verdict = (
        f"Stage 1: bias={recovery['bias']:.2f}, "
        f"CI coverage={recovery['ci_coverage']:.2f}, "
        f"confident-wrong={len(confident_wrong)}, "
        f"unresolved={len(unresolved_mems)} "
        f"(expected: neutral). {'PASSES' if ok else 'FAILS'}"
    )

    return {
        "stage": "stage1", "violation": "none",
        "config": asdict(cfg),
        "true_lifecycle_values": true_values,
        "local_effects": local_effects,
        "estimators": {
            mem: {
                "sqcad_rct": rct.get(mem, {}),
                "cmi": baselines["cmi"][mem],
                "association": baselines["association"][mem],
                "naive_ope": baselines["naive_ope"][mem],
            }
            for mem in mem_ids
        },
        "value_recovery": recovery,
        "decision_quality": decision_quality,
        "decisions": decisions,
        "confident_wrong_mems": confident_wrong,
        "unresolved_mems": unresolved_mems,
        "gate": checks,
        "stage1_passes": ok,
        "summary_verdict": verdict,
    }


def _sqcad_decisions(rct: Dict[str, Any], checks: Dict[str, Any],
                     mem_ids: Sequence[str]) -> Dict[str, str]:
    """Gate + CI -> access status per memory."""
    out: Dict[str, str] = {}
    for mem in mem_ids:
        e = rct.get(mem, {})
        out[mem] = qualification_status(checks, mem, e.get("estimate"), e.get("se"))
    return out


def run_stage2(violation: str, cfg: WorldConfig | None = None) -> Dict[str, Any]:
    """One Stage-2 violation at a time (C6/C7/C3/C8/Cor1)."""
    base = cfg or WorldConfig(seed=11)
    if violation == "adoption":
        cfg = WorldConfig(**{**asdict(base), "adoption_error": 0.3})
    elif violation == "co_exposure":
        cfg = WorldConfig(**{**asdict(base), "co_exposure": True})
    elif violation == "eligibility":
        cfg = WorldConfig(**{**asdict(base), "eligibility_selection": True})
    elif violation == "drift":
        cfg = WorldConfig(**{**asdict(base), "measurement_drift": True})
    elif violation == "scope":
        cfg = WorldConfig(**{**asdict(base), "scope_shift": True})
    else:
        raise ValueError(f"unknown violation: {violation}")

    world = World(cfg)
    mem_ids = [m.mem_id for m in world.memories]
    source_log = world.source_log(random.Random(cfg.seed + 2))
    local_effects = compute_local_effects(world, cfg)
    # oracle always evaluates the pre-registered (intended) estimand; under
    # scope shift the decision target is the target scope
    true_values = compute_oracle_values(world, cfg, scope="target"
                                        if cfg.scope_shift else "source")

    # C3 violation: randomize only memories whose local effect clears the
    # safety threshold (harmful memories never get randomized evidence)
    eligible: Optional[Set[str]] = None
    if cfg.eligibility_selection:
        eligible = {mem for mem, d in local_effects.items()
                    if d >= cfg.eligibility_threshold}

    rct = estimate_sqcad_rct(world, cfg, mem_ids, eligible=eligible)
    checks = run_gate_checks(world, cfg, source_log, rct)

    # C7: bundle estimate (the only intervention available for the pair)
    bundle: Optional[Dict[str, Any]] = None
    if world.pair is not None:
        bundle_est = estimate_bundle_rct(world, cfg, world.pair)
        bundle_true = compute_bundle_oracle(world, cfg, world.pair)
        bundle = {"estimate": bundle_est,
                  "bundle_value_true": bundle_true["bundle_value"]}

    sqcad_status = _sqcad_decisions(rct, checks, mem_ids)
    # forced variant: decide by sign; default to status quo (keep) when no
    # randomized evidence exists
    forced: Dict[str, str] = {}
    for mem in mem_ids:
        est = rct.get(mem, {}).get("estimate")
        if est is None:
            forced[mem] = "keep"
        else:
            forced[mem] = "keep" if est > 0 else "archive"
    # C7 forced variant: apply the bundle estimate to BOTH pair members
    if world.pair is not None and bundle is not None:
        bv = bundle["estimate"]["estimate"]
        for mem in world.pair:
            forced[mem] = "keep" if bv > 0 else "archive"

    baselines = _baseline_decisions(world, cfg, source_log)
    decisions = {
        "sqcad_rct": sqcad_status,
        "sqcad_forced": forced,
        "association": {m: d["decision"] for m, d in baselines["association"].items()},
        "cmi": {m: d["decision"] for m, d in baselines["cmi"].items()},
        "naive_ope": {m: d["decision"] for m, d in baselines["naive_ope"].items()},
    }
    decision_quality = {m: _decision_regret(d, true_values)
                        for m, d in decisions.items()}

    n_unresolved = decision_quality["sqcad_rct"]["n_unresolved"]
    n_mismatch = decision_quality["sqcad_rct"]["n_mismatch"]
    forced_regret = decision_quality["sqcad_forced"]["regret"]

    verdict = (
        f"Stage 2 '{violation}': gate abstains on {n_unresolved} unresolved + "
        f"{n_mismatch} mismatch; forced-decision regret={forced_regret:.1f}."
    )

    return {
        "stage": "stage2", "violation": violation,
        "config": asdict(cfg),
        "true_lifecycle_values": true_values,
        "local_effects": local_effects,
        "estimators": {
            mem: {
                "sqcad_rct": rct.get(mem, {}),
                "cmi": baselines["cmi"][mem],
                "association": baselines["association"][mem],
                "naive_ope": baselines["naive_ope"][mem],
            }
            for mem in mem_ids
        },
        "bundle_estimate": bundle,
        "decision_quality": decision_quality,
        "decisions": decisions,
        "gate": checks,
        "gate_abstains": gate_abstains(n_unresolved, n_mismatch),
        "summary_verdict": verdict,
    }


def gate_abstains(n_unresolved: int, n_mismatch: int) -> bool:
    return n_unresolved + n_mismatch > 0


def run_identification_recovery(stage: str = "all",
                                violation: str = "none",
                                cfg: WorldConfig | None = None) -> Dict[str, Any]:
    if stage == "stage1":
        return run_stage1(cfg)
    if stage == "stage2":
        return run_stage2(violation, cfg)
    if stage == "all":
        out: Dict[str, Any] = {
            "stage1": run_stage1(cfg),
            "stage2": {v: run_stage2(v, cfg)
                       for v in ("adoption", "co_exposure", "eligibility",
                                 "drift", "scope")},
        }
        out["summary_verdict"] = (
            "STAGE1: " + out["stage1"]["summary_verdict"] + " | "
            + "; ".join(out["stage2"][v]["summary_verdict"] for v in out["stage2"])
        )
        return out
    raise ValueError(f"unknown stage: {stage}")


# ---------------------------------------------------------------------------
# Multi-seed stability
# ---------------------------------------------------------------------------

def _summarise(values: List[float]) -> Dict[str, float]:
    n = len(values)
    if n == 0:
        return {"mean": float("nan"), "sd": float("nan"), "n": 0}
    sd = stdev(values) if n > 1 else 0.0
    return {"mean": mean(values), "sd": sd, "n": float(n)}


def run_multi_seed(stage: str = "stage1", n_seeds: int = 5,
                   violation: str = "none") -> Dict[str, Any]:
    """Aggregate coverage / regret / unresolved across seeds."""
    coverages: List[float] = []
    biases: List[float] = []
    regrets: Dict[str, List[float]] = defaultdict(list)
    error_rates: Dict[str, List[float]] = defaultdict(list)
    unresolved_rates: List[float] = []
    passed = 0
    for i in range(n_seeds):
        cfg = WorldConfig(seed=100 + i * 17)
        if stage == "stage1":
            res = run_stage1(cfg)
        else:
            res = run_stage2(violation, cfg)
        if stage == "stage1":
            coverages.append(res["value_recovery"]["ci_coverage"])
            biases.append(res["value_recovery"]["bias"])
            passed += 1 if res["stage1_passes"] else 0
        for m, dq in res["decision_quality"].items():
            regrets[m].append(dq["regret"])
            error_rates[m].append(dq["error_rate"])
        unresolved_rates.append(
            res["decision_quality"]["sqcad_rct"]["unresolved_rate"])

    agg: Dict[str, Any] = {"n_seeds": n_seeds, "stage": stage,
                           "violation": violation}
    if stage == "stage1":
        agg["ci_coverage"] = _summarise(coverages)
        agg["bias"] = _summarise(biases)
        agg["stage1_pass_rate"] = passed / n_seeds
    agg["regret"] = {m: _summarise(regrets[m]) for m in regrets}
    agg["error_rate"] = {m: _summarise(error_rates[m]) for m in error_rates}
    agg["unresolved_rate"] = _summarise(unresolved_rates)
    cov = agg.get("ci_coverage", {})
    cov_mean = cov.get("mean", float("nan"))
    cov_sd = cov.get("sd", float("nan"))
    agg["summary_verdict"] = (
        f"{stage} ({violation}): coverage={cov_mean:.2f} +/-{cov_sd:.2f}; "
        f"sqcad regret={agg['regret']['sqcad_rct']['mean']:.1f}+/-"
        f"{agg['regret']['sqcad_rct']['sd']:.1f}; "
        f"forced regret={agg['regret']['sqcad_forced']['mean']:.1f}; "
        f"unresolved rate={agg['unresolved_rate']['mean']:.2f}"
    )
    return agg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", choices=["stage1", "stage2", "all"], default="all")
    p.add_argument("--violation", choices=["none", "adoption", "co_exposure",
                                           "eligibility", "drift", "scope"],
                   default="none")
    p.add_argument("--multi-seed", type=int, default=0,
                   help="aggregate N seeds for the chosen stage")
    p.add_argument("--output", type=Path,
                   default=Path("results/identification_recovery.json"))
    p.add_argument("--compact", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.multi_seed > 0:
        stage = args.stage if args.stage != "all" else "stage1"
        result = run_multi_seed(stage, args.multi_seed, args.violation)
    else:
        result = run_identification_recovery(args.stage, args.violation)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    # database copy (per DATA_STORAGE.md)
    try:
        db = Path(r"D:\Engineering\SQCAD\database\results")
        if db.exists():
            (db / args.output.name).write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8")
    except OSError:
        pass

    if args.compact:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        if isinstance(result, dict) and "summary_verdict" in result:
            print(result["summary_verdict"])
        else:
            print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
