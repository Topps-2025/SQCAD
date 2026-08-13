"""Structural ablation of self-obscuring memory governance (14- §5/§7).

Executes the W0-W3 structural-ablation matrix, the reduction control groups
(static bandit / contextual bandit / standard OPE), and the self-confirming
policy comparison of `docs/研究逻辑与理论证明/14-Agent-Memory基础理论空缺与下一阶段实验路线-20260813.md`
(14- §5 缺口 A/B, §7.1/§7.2/§7.3, §10 执行顺序 3/4).

The question the module answers: is the "self-confirming unidentifiability"
of a wrongly archived memory an artefact of the example, or is it produced by
the lifecycle structure itself?  One unified DGP is toggled on three axes:

  persistent_action   archive is a persistent state vs a query-local skip
  candidate_feedback  archive removes the memory from the candidate/evidence
                      stream (exposure prob while archived: 0.0) vs evidence
                      flows regardless of the action (0.4)
  restore_channel     a probe/restore action can re-open the evidence stream
                      at a cost

Worlds (14- §7.1):
  W0  local, uncensored, no restore  -> static bandit (standard methods work)
  W1  persistent, uncensored, restore-> long-horizon action, but wrong
                      archives stay correctable by continued evidence
  W2  persistent, censored, no restore-> SELF-CONFIRMING: wrong archive stops
                      the evidence that could correct it (the new boundary)
  W3  persistent, censored, restore  -> restore re-opens the stream at a cost

Two latent worlds share the SAME early-phase logs (a confounded negative
signal) but have opposite lifecycle values: K (keep-optimal, tau=+10) and A
(archive-optimal, tau=-10).  The early logs are bit-identical across K/A
(checked by `observational_equivalence`), so any policy committing from the
prior alone is wrong in exactly one of them -- the Theorem 1 structure at the
mechanism level.

Reduction controls (14- §7.2): the SAME standard machinery (UCB bandit,
log-based OPE) that achieves sublinear regret / correct decisions in W0/W1
fails linearly in W2, because the governance action censors the candidate
flow -- exploration of existing candidates cannot reach a memory removed from
the candidate stream; a restore channel (exploration of the candidate
generator itself) is the missing state.  This is the numerical counterpart of
the reduction-separation claim (14- §6 T2).

Self-confirming comparison (14- §7.3): in the auto-archived setting (state =
archived at the decision point), no-restore rules (association commit,
local-causal commit, gate without probing) accrue linear regret in K
(slope = tau*p_expose exactly) -- the gate commits because the CONFOUNDED
early signal is statistically resolved-negative (CI excludes 0): its
resolution is the trap, not an estimation failure.  Fixed-probability
restore, uncertainty-triggered restore (staleness-based: prolonged silence
is self-generated under the archive, so the policy re-opens the stream) and
cost-aware commit/defer/probe (the P2 comparison on the prior-widened
identification set, decision_identification_theory.r_star) plateau after
evidence-driven correction and pay probe/restore cost.

Claim discipline: this module provides computational/mechanism evidence;
the formal theorems (T1 Omega(T) lower bound and restore upper bound,
T2 reduction separation) are stated and proved in the theory documents.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, pstdev, stdev
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqcad.bootstrap_ci import paired_seed_diff_ci, paired_seed_ci
from sqcad.decision_identification_theory import r_star

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorldConfig:
    """One latent world: K (keep-optimal) or A (archive-optimal).

    `p_evid_archived` is the exposure/evidence rate while archived (the
    candidate-feedback axis): 0.0 = total censoring (self-obscuring),
    0.4 = evidence flows regardless of the governance action.
    `persistent=False` (W0) makes the ENVIRONMENT's treatment query-local:
    it never removes the memory from the candidate stream, so the evidence
    rate while archived equals p_expose (uncensored).  The policy's committed
    archive decision still persists as its state -- the same commitment that
    becomes self-confirming in W2 -- but the environment keeps exposing it,
    so standard watchful/bandit methods stay correctable.
    """

    seed: int
    world: str  # "K" keep-optimal | "A" archive-optimal
    horizon: int = 2000
    n_early: int = 50
    tau: float = 10.0
    p_expose: float = 0.6
    p_evid_archived: float = 0.0
    noise_sd: float = 1.0
    delta_early: float = -0.5  # confounded early-phase signal (shared K/A)
    persistent: bool = True
    restore_channel: bool = False
    threshold_keep: float = 2.0
    threshold_archive: float = -2.0
    prior_sd: float = 1.15
    c_probe: float = 30.0
    c_restore: float = 80.0
    probe_q: float = 0.05
    probe_interval: int = 10
    uncertainty_stale_gap: float = 100.0  # silence threshold (steps without
                                          # exposure) for staleness-triggered
                                          # restore
    defer_resolve_steps: float = 8.0      # P2: steps to resolve after restore
    expected_probes: float = 5.0          # P2: budgeted probes to resolve sign

    @property
    def tau_true(self) -> float:
        return self.tau if self.world == "K" else -self.tau

    @property
    def kept_value(self) -> float:
        """Expected per-step value while kept (exposure-gated benefit)."""
        return self.tau_true * self.p_expose

    @property
    def evid_rate_archived(self) -> float:
        """Evidence arrival rate while archived, after the persistent/
        candidate-feedback structure is applied."""
        if not self.persistent:
            return self.p_expose  # query-local archive never censors evidence
        return self.p_evid_archived


WORLD_SPECS: Dict[str, Dict[str, Any]] = {
    "W0": {"persistent": False, "p_evid_archived": 0.0,
           "restore_channel": False,
           "note": "query-local action; candidate stream independent of action"},
    "W1": {"persistent": True, "p_evid_archived": 0.4,
           "restore_channel": True,
           "note": "persistent action; evidence uncensored (0.4)"},
    "W2": {"persistent": True, "p_evid_archived": 0.0,
           "restore_channel": False,
           "note": "persistent action; archive censors evidence -> "
                   "self-confirming"},
    "W3": {"persistent": True, "p_evid_archived": 0.0,
           "restore_channel": True,
           "note": "persistent action; censored evidence; restore channel"},
}

# Part-1 decision-time policies (state = kept until the decision point, then
# the policy commits the confounded prior archive)
DECISION_POLICIES = ("association_commit", "watchful_no_restore",
                     "watchful_restore", "gate_keep_default")

# Part-3 auto-archived policies (state = archived already at the decision
# point -- the write-time governance archived it on the confounded prior)
AUTO_ARCHIVED_POLICIES = ("no_probe_commit", "local_causal_commit",
                          "gate_no_probe", "fixed_prob_restore",
                          "uncertainty_triggered_restore",
                          "cost_aware_commit_defer_probe")

# Part-2 reduction controls
CONTROL_POLICIES = ("static_bandit_ucb", "contextual_bandit",
                    "standard_ope", "bandit_ucb")

WATCHFUL = ("watchful_no_restore", "watchful_restore", "gate_keep_default",
            "gate_no_probe", "fixed_prob_restore",
            "uncertainty_triggered_restore", "cost_aware_commit_defer_probe",
            "standard_ope", "bandit_ucb")

PROBE_CAPABLE = ("watchful_restore", "fixed_prob_restore",
                 "cost_aware_commit_defer_probe")
# uncertainty_triggered_restore does not probe: it RESTORES directly when the
# silence gap is exceeded (its re-open IS the evidence action)

INITIAL_STATE = {p: "kept" for p in DECISION_POLICIES}
for p in AUTO_ARCHIVED_POLICIES + ("standard_ope", "bandit_ucb",
                                  "static_bandit_ucb"):
    INITIAL_STATE[p] = "archived"
INITIAL_STATE["contextual_bandit"] = "kept"
INITIAL_STATE["contextual_bandit_oracle"] = "archived"
INITIAL_STATE["random_flip"] = "kept"

PART_OF: Dict[str, str] = {p: "part1" for p in DECISION_POLICIES}
PART_OF.update({p: "part3" for p in AUTO_ARCHIVED_POLICIES})
PART_OF.update({p: "part2" for p in CONTROL_POLICIES})
PART_OF["contextual_bandit_oracle"] = "part2"
PART_OF["random_flip"] = "part2"


# ---------------------------------------------------------------------------
# World construction: shared stream, latent outcomes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class World:
    cfg: WorldConfig
    early_exposed: Tuple[bool, ...]
    early_y: Tuple[float, ...]
    latent_y: Tuple[float, ...]       # potential evidence y_t = tau_true + eps
    exposure_noise: Tuple[float, ...]  # shared Uniform(0,1) draws per step
    stream_hash: str


def stable_hash(value: object) -> str:
    import hashlib
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def build_world(cfg: WorldConfig) -> World:
    """Build the world ONCE per (seed, world).  The early-phase stream is
    identical across K and A for the same seed (same draws, shared delta):
    the lifecycle sign tau_true enters only the latent continuation outcomes.
    The exposure noise and latent outcomes for the whole horizon are
    pre-generated and shared by every policy, so policies on the same
    (seed, world) observe the same stream where their paths coincide."""
    rng = random.Random(cfg.seed)
    early_exposed = tuple(rng.random() < 0.5 for _ in range(cfg.n_early))
    early_y = tuple(cfg.delta_early + rng.gauss(0.0, cfg.noise_sd)
                    for _ in early_exposed)
    latent_y = tuple(cfg.tau_true + rng.gauss(0.0, cfg.noise_sd)
                     for _ in range(cfg.horizon))
    exposure_noise = tuple(rng.random() for _ in range(cfg.horizon))
    stream_hash = stable_hash({
        "seed": cfg.seed, "world": cfg.world,
        "early_exposed": early_exposed, "early_y": early_y,
        "latent_y": latent_y, "exposure_noise": exposure_noise,
    })
    return World(cfg, early_exposed, early_y, latent_y, exposure_noise,
                 stream_hash)


def normal_update(bel_mean: float, bel_sd: float, y: float,
                  obs_sd: float) -> Tuple[float, float]:
    """Normal belief update on one evidence observation."""
    prior_precision = 1.0 / max(bel_sd * bel_sd, 1e-9)
    obs_precision = 1.0 / max(obs_sd * obs_sd, 1e-9)
    variance = 1.0 / (prior_precision + obs_precision)
    new_mean = variance * (prior_precision * bel_mean + obs_precision * y)
    return new_mean, math.sqrt(variance)


# ---------------------------------------------------------------------------
# Policy runner
# ---------------------------------------------------------------------------


def run_policy(world: World, policy: str,
               probe_q: Optional[float] = None) -> Dict[str, Any]:
    """Run one policy on one world; the realized observation log is the
    exposed subset of the shared stream.  `probe_q` overrides the config's
    fixed probe probability (used by the restore-cost sweep)."""
    cfg = world.cfg
    if policy not in INITIAL_STATE:
        raise KeyError(policy)
    # policy-internal randomness (probe decisions) is per-policy; the shared
    # world stream is policy-independent
    rng = random.Random(cfg.seed * 7919 + sum(ord(c) for c in policy)
                        + (0 if cfg.world == "K" else 7))
    # random_flip: T2 pairing-identity control (16- 1.4).  The flip coin is
    # seeded WORLD-INDEPENDENTLY so the K/A state trajectories couple
    # (Lemma 3): at every post-decision step exactly one world accrues the
    # tau*p step loss, and the paired regret sum is the constant
    # tau*p*(T - n_early) even under maximal (random) adaptivity.
    flip_rng = random.Random(cfg.seed * 104729 + 13) \
        if policy == "random_flip" else None
    q = cfg.probe_q if probe_q is None else probe_q

    early_exposed_ys = [y for y, e in zip(world.early_y, world.early_exposed)
                        if e]
    bel_mean = mean(early_exposed_ys) if early_exposed_ys else cfg.delta_early
    bel_sd = cfg.prior_sd
    state = INITIAL_STATE[policy]

    # local-causal commit: early-phase micro-randomized estimate of the
    # exposure effect on early outcomes (by construction ~0: early outcomes
    # do not depend on exposure -- the lifecycle sign is beyond its scope)
    local_est = 0.0
    local_ci_lo = local_ci_hi = 0.0
    if policy == "local_causal_commit":
        exp = [y for y, e in zip(world.early_y, world.early_exposed) if e]
        ctl = [y for y, e in zip(world.early_y, world.early_exposed) if not e]
        n1, n0 = max(1, len(exp)), max(1, len(ctl))
        local_est = (mean(exp) if exp else 0.0) - (mean(ctl) if ctl else 0.0)
        se = cfg.noise_sd * math.sqrt(1.0 / n1 + 1.0 / n0)
        local_ci_lo, local_ci_hi = local_est - 1.96 * se, local_est + 1.96 * se

    # cost-aware rule: the P2 commit/restore/probe comparison at the decision
    # point (decision_identification_theory.r_star, 14- §7.3).  The
    # identification set is the posterior CI WIDENED by the prior lifecycle
    # uncertainty: the policy cannot rule out continuation values in the
    # prior-predictive range (the Theorem-1 structure -- the early stream is
    # compatible with both lifecycle signs), so the naive posterior CI (here
    # excluding 0) is NOT the identification set.  Compare the worst-case
    # commit regret R*(L,U)*T_rem, restore-then-watch, and probe-then-resolve.
    cost_aware_action = "commit"
    if policy == "cost_aware_commit_defer_probe":
        widen = 1.96 * (bel_sd + cfg.prior_sd)
        L = bel_mean - widen
        U = bel_mean + widen
        t_rem = float(cfg.horizon - cfg.n_early)
        r_commit = r_star(L, U) * t_rem
        r_restore = cfg.c_restore + (abs(L) + abs(U)) / 2.0 \
            * cfg.defer_resolve_steps
        r_probe = cfg.c_probe * cfg.expected_probes + cfg.c_restore
        options = [("commit", r_commit), ("restore", r_restore),
                   ("probe", r_probe)]
        cost_aware_action, _ = min(options, key=lambda kv: kv[1])

    regret = 0.0
    observed = 0
    exposed_keep = exposed_archived = 0
    probes = 0
    probe_cost = 0.0
    restores = 0
    restore_cost = 0.0
    false_forgetting = 0
    harmful_retention = 0
    correction_time: Optional[int] = None
    archive_step: Optional[int] = None
    last_probe = -1
    last_exposed = -1          # staleness: steps since the memory was last
                               # exposed (evidence hunger under the archive)
    harm_confirmed = False     # a staleness restore re-opened the stream and
                               # the evidence confirmed the archive: the
                               # silence is now informative, do not re-restore
    log_rows: List[Dict[str, Any]] = []
    ucb_mean = bel_mean if policy in ("bandit_ucb", "static_bandit_ucb") \
        else 0.0
    ucb_n = 0.0 if policy in ("bandit_ucb", "static_bandit_ucb") else 1.0
    ope_log_keep: List[float] = []
    ope_log_archived: List[float] = []
    ope_flipped = False
    # contextual bandit: linear predictor on the cue stream
    ctx = tuple(rng.gauss(0.0, 1.0) for _ in range(cfg.horizon))
    ctx_yy: List[Tuple[float, float]] = []   # (cue, y) observed pairs

    for t in range(cfg.horizon):
        # -- state dynamics ------------------------------------------------
        if t == cfg.n_early and policy in DECISION_POLICIES:
            if policy in ("association_commit", "watchful_no_restore",
                          "watchful_restore"):
                state = "archived"          # confounded prior commit
                archive_step = t
                if cfg.world == "A":
                    correction_time = 0     # the committed action is right
            elif policy == "gate_keep_default":
                L = bel_mean - 1.96 * bel_sd
                U = bel_mean + 1.96 * bel_sd
                if U < 0.0:
                    state = "archived"      # resolved negative: commit
                    archive_step = t
                    if cfg.world == "A":
                        correction_time = 0
                elif cfg.world == "K":
                    correction_time = 0     # keep default is right in K
                # unresolved or resolved positive: keep (default)
        if t == cfg.n_early and policy == "cost_aware_commit_defer_probe" \
                and cost_aware_action == "restore":
            state = "kept"                  # restore now: cheapest option
            restores += 1
            restore_cost += cfg.c_restore
            correction_time = 0
        # W0: the policy's committed action persists as its state; only the
        # ENVIRONMENT is query-local -- the evidence rate while archived is
        # p_expose (uncensored, see evid_rate_archived), so a committed
        # archive never censors the candidate stream in W0.

        # -- probe / restore actions (post-decision, archived, channel) ----

        probe_now = False
        if t >= cfg.n_early and state == "archived" and cfg.restore_channel:
            if policy == "watchful_restore" and rng.random() < q:
                probe_now = True
            elif policy == "fixed_prob_restore" and rng.random() < q:
                probe_now = True
            elif (policy == "cost_aware_commit_defer_probe"
                  and cost_aware_action == "probe"
                  and t - last_probe >= cfg.probe_interval):
                probe_now = True
                last_probe = t

        # -- exposure ------------------------------------------------------
        # Early phase (t < n_early): the SHARED observational history; the
        # same stream in both latent worlds (identical draws, delta_early).
        # Continuation: the exposure probability depends on the persistent
        # state -- the candidate-feedback structure under study.
        if t < cfg.n_early:
            exposed = world.early_exposed[t]
        elif state == "kept":
            exposed = world.exposure_noise[t] < cfg.p_expose
        else:
            exposed = world.exposure_noise[t] < cfg.evid_rate_archived
        if probe_now:
            exposed = True
            probes += 1
            probe_cost += cfg.c_probe
        if exposed:
            last_exposed = t
            observed += 1
            if t >= cfg.n_early:
                if state == "kept":
                    exposed_keep += 1
                else:
                    exposed_archived += 1
            y = world.early_y[t] if t < cfg.n_early else world.latent_y[t]
            # evidence consumers
            if policy in WATCHFUL:
                bel_mean, bel_sd = normal_update(bel_mean, bel_sd, y,
                                                 cfg.noise_sd)
            if policy == "standard_ope":
                (ope_log_keep if state == "kept" else ope_log_archived)\
                    .append(y)
            if policy == "bandit_ucb" and t >= cfg.n_early:
                # post-decision candidate-feedback only: the early stream is
                # the SHARED confounded observational history (bit-identical
                # across K/A -- it cannot discriminate the lifecycle sign), so
                # folding it into the sample count lets a single lucky draw
                # flip the policy at n=1; under censoring (W2) no row ever
                # arrives and candidate exploration is dead by construction
                ucb_mean = (ucb_mean * ucb_n + y) / (ucb_n + 1.0)
                ucb_n += 1.0
            if policy == "contextual_bandit":
                ctx_yy.append((ctx[t], y))
            if policy == "static_bandit_ucb" and t >= cfg.n_early:
                ucb_mean = (ucb_mean * ucb_n + y) / (ucb_n + 1.0)
                ucb_n += 1.0

        # -- decision updates (evidence-driven) ----------------------------
        if policy == "watchful_no_restore" and state == "archived" \
                and bel_mean > cfg.threshold_keep:
            state = "kept"                  # free revision: evidence flowed
            if correction_time is None:
                correction_time = t - cfg.n_early
        if policy in ("watchful_restore", "fixed_prob_restore",
                      "uncertainty_triggered_restore",
                      "cost_aware_commit_defer_probe") \
                and state == "archived" and bel_mean > cfg.threshold_keep:
            state = "kept"                  # restore: re-open persistent access
            if cfg.persistent and cfg.p_evid_archived == 0.0:
                # only a censored world makes the re-open a real paid
                # restore; in W0/W1 the evidence flowed and the flip is a
                # free watchful revision
                restores += 1
                restore_cost += cfg.c_restore
            if correction_time is None:
                correction_time = t - cfg.n_early
        # uncertainty-triggered restore: under the archive the stream is
        # CENSORED, so prolonged silence is self-generated, not evidence of
        # low value.  After `uncertainty_stale_gap` steps without exposure
        # the policy re-opens the stream -- unless the belief is already
        # resolved negative (U < threshold_archive), in which case the
        # silence is consistent with a confirmed harmful memory.  Once a
        # re-opened stream has CONFIRMED the archive (harm_confirmed, set in
        # the re-archive block below), the silence is informative and the
        # restore must not re-fire: the naive guard (U > threshold_archive)
        # is complementary to the re-archive condition (bel < threshold_archive),
        # so without the flag the two blocks re-toggle every step.
        if (policy == "uncertainty_triggered_restore" and cfg.restore_channel
                and state == "archived" and not harm_confirmed
                and t - last_exposed >= cfg.uncertainty_stale_gap
                and bel_mean + 1.96 * bel_sd > cfg.threshold_archive):
            state = "kept"                  # staleness-triggered restore
            restores += 1
            restore_cost += cfg.c_restore
            last_probe = t
            if correction_time is None:
                correction_time = t - cfg.n_early
        if (policy in ("uncertainty_triggered_restore",
                       "cost_aware_commit_defer_probe") and state == "kept"
                and bel_mean < cfg.threshold_archive):
            state = "archived"              # re-opened evidence confirms harm
            archive_step = t
            harm_confirmed = True           # silence is now informative
            if correction_time is None:
                correction_time = t - cfg.n_early
        if policy == "gate_keep_default" and state == "kept" \
                and bel_mean < cfg.threshold_archive:
            state = "archived"              # evidence-driven archive
            archive_step = t
        if policy == "bandit_ucb" and state == "archived" \
                and ucb_n > 0 and ucb_mean - 1.96 * (cfg.noise_sd
                                                     / math.sqrt(ucb_n)) > 0.0:
            state = "kept"                  # UCB lower bound excludes 0
            if correction_time is None:
                correction_time = t - cfg.n_early
        if policy == "static_bandit_ucb" and ucb_n > 0 \
                and ucb_mean - 1.96 * (cfg.noise_sd / math.sqrt(ucb_n)) > 0.0:
            state = "kept"
        if policy == "random_flip" and t >= cfg.n_early \
                and flip_rng.random() < 0.5:
            state = "kept" if state == "archived" else "archived"
        if policy == "standard_ope" and state == "archived":
            # re-estimate the lifecycle value from the log every 25 steps;
            # with overlap (archived exposures exist) the estimate recovers
            # tau and the policy flips; under censoring there are no rows
            if t > cfg.n_early and (t - cfg.n_early) % 25 == 0:
                all_y = ([y for y in ope_log_keep] + [y for y in ope_log_archived]
                         + [y for y, e in zip(world.early_y,
                                              world.early_exposed) if e])
                if len(all_y) >= 5:
                    est = mean(all_y)
                    se = cfg.noise_sd / math.sqrt(len(all_y))
                    if est - 1.96 * se > 0.0:
                        state = "kept"
                        ope_flipped = True
                        if correction_time is None:
                            correction_time = t - cfg.n_early
        if policy == "contextual_bandit":
            # W0 world: cue stream; keep iff predicted value > 0
            n = len(ctx_yy)
            if n >= 8 and t > cfg.n_early:
                mx = mean(c for c, _ in ctx_yy)
                my = mean(y for _, y in ctx_yy)
                cov = mean((c - mx) * (y - my) for c, y in ctx_yy)
                var = mean((c - mx) ** 2 for c, _ in ctx_yy)
                beta = cov / var if var > 1e-9 else 0.0
                alpha = my - beta * mx
                pred = alpha + beta * ctx[t]
                state = "kept" if pred > 0.0 else "archived"
        if policy == "contextual_bandit_oracle":
            # T2 control (16- §1.6): the FORBIDDEN reduction -- the image
            # context would depend on the latent world identity (phi not
            # world-independent).  With the smuggled signal the standard
            # learner trivially succeeds, pinning the impossibility on the
            # phi constraint rather than on learner weakness.
            state = "kept" if cfg.world == "K" else "archived"

        # -- per-step value, regret, mechanism metrics ---------------------
        value = cfg.kept_value if state == "kept" else 0.0
        oracle = cfg.kept_value if cfg.world == "K" else 0.0
        if t >= cfg.n_early:  # regret/retention counted post-decision only
            regret += oracle - value
            if cfg.world == "K" and state == "archived":
                false_forgetting += 1
            if cfg.world == "A" and state == "kept":
                harmful_retention += 1

        log_rows.append({
            "t": t, "state": state, "exposed": int(exposed),
            "y": (world.early_y[t] if t < cfg.n_early
                  else world.latent_y[t]) if exposed else None,
            "value": value, "regret": regret,
        })

    return {
        "policy": policy, "seed": float(cfg.seed), "world": cfg.world,
        "stream_sha256": world.stream_hash,
        "regret_T": regret, "per_step_slope": regret / cfg.horizon,
        "correction_time": float(correction_time
                                 if correction_time is not None
                                 else cfg.horizon),
        "evidence_arrival": observed / cfg.horizon,
        "exposed_keep": exposed_keep, "exposed_archived": exposed_archived,
        "probes": float(probes), "probe_cost": probe_cost,
        "restores": float(restores), "restore_cost": restore_cost,
        "false_forgetting_steps": float(false_forgetting),
        "harmful_retention_steps": float(harmful_retention),
        "local_effect_estimate": local_est,
        "local_ci": [local_ci_lo, local_ci_hi],
        "ope_flipped": int(ope_flipped),
        "log_overlap_archived": float(len(ope_log_archived)),
        "log_overlap_keep": float(len(ope_log_keep)),
        "decision_log": log_rows,
    }


def config_for(seed: int, world: str, label: str) -> WorldConfig:
    spec = WORLD_SPECS[label]
    return WorldConfig(seed=seed, world=world, **{
        k: v for k, v in spec.items() if k != "note"})


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


def structural_ablation(n_seeds: int = 12, seed0: int = 21,
                        horizon: int = 2000) -> Dict[str, Any]:
    """W0-W3 matrix (14- §7.1): 4 worlds x {association_commit,
    watchful_no_restore, watchful_restore} in both K and A, all metrics."""
    rows: List[Dict[str, Any]] = []
    policies = ("association_commit", "watchful_no_restore",
                "watchful_restore")
    for label in ("W0", "W1", "W2", "W3"):
        for seed in range(seed0, seed0 + n_seeds):
            for world_name in ("K", "A"):
                cfg = config_for(seed, world_name, label)
                world = build_world(cfg)
                for policy in policies:
                    row = run_policy(world, policy)
                    row["world_label"] = label
                    rows.append(row)
    return summarize(rows)


def restore_cost_sweep(n_seeds: int = 12, seed0: int = 21,
                       qs: Sequence[float] = (0.01, 0.05, 0.2),
                       horizon: int = 2000) -> Dict[str, Any]:
    """W3 restore-cost/regret curve (14- §7.1 消融 C): fixed-probability
    restore at rate q -- higher q corrects faster and pays more."""
    out: Dict[str, Any] = {}
    for q in qs:
        rows = []
        for seed in range(seed0, seed0 + n_seeds):
            cfg = config_for(seed, "K", "W3")
            world = build_world(cfg)
            rows.append(run_policy(world, "watchful_restore", probe_q=q))
        out[f"q_{q}"] = {
            "mean_regret": mean(r["regret_T"] for r in rows),
            "mean_slope": mean(r["per_step_slope"] for r in rows),
            "mean_correction_time": mean(r["correction_time"] for r in rows),
            "mean_probe_cost": mean(r["probe_cost"] for r in rows),
            "mean_restore_cost": mean(r["restore_cost"] for r in rows),
            "mean_total_cost": mean(r["probe_cost"] + r["restore_cost"]
                                    for r in rows),
            "n_seeds": float(n_seeds),
        }
    out["note"] = ("higher q: earlier correction (lower regret), higher "
                   "probe+restore cost -- the cost-regret tradeoff of the "
                   "restore channel")
    return out


def reduction_controls(n_seeds: int = 12, seed0: int = 21,
                       horizon: int = 2000) -> Dict[str, Any]:
    """14- §7.2 control groups.  Standard machinery (static UCB, contextual
    regression, log-based OPE, candidate-exploring UCB) on the worlds where
    the relevant structure is ABSENT (W0/W1) vs PRESENT (W2).  The controls
    are solvable by standard methods only where the governance action does
    not censor the candidate stream; under censoring the same methods fail
    linearly -- the numerical counterpart of the reduction separation."""
    cells: Dict[str, List[Dict[str, Any]]] = {
        ("static_bandit_ucb", "W0"): [],
        ("contextual_bandit", "W0"): [],
        ("standard_ope", "W1"): [],
        ("standard_ope", "W2"): [],
        ("bandit_ucb", "W1"): [],
        ("bandit_ucb", "W2"): [],
    }
    for (policy, label), rows in cells.items():
        for seed in range(seed0, seed0 + n_seeds):
            cfg = config_for(seed, "K", label)
            world = build_world(cfg)
            rows.append(run_policy(world, policy))
    out: Dict[str, Any] = {}
    for (policy, label), rows in cells.items():
        out[f"{label}_{policy}"] = {
            "mean_slope": mean(r["per_step_slope"] for r in rows),
            "mean_regret": mean(r["regret_T"] for r in rows),
            "mean_correction_time": mean(r["correction_time"] for r in rows),
            "mean_evidence_arrival": mean(r["evidence_arrival"] for r in rows),
            "mean_log_overlap_archived": mean(r["log_overlap_archived"]
                                              for r in rows),
            "mean_log_overlap_keep": mean(r["log_overlap_keep"] for r in rows),
            "n_seeds": float(n_seeds),
        }
    return out


def self_confirming_comparison(n_seeds: int = 12, seed0: int = 21,
                               horizon: int = 2000) -> Dict[str, Any]:
    """14- §7.3: auto-archived setting in the W3 world (censored evidence +
    restore channel), both latent worlds, all six policies plus the
    keep-default gate for the harmful-retention side."""
    rows: List[Dict[str, Any]] = []
    policies = AUTO_ARCHIVED_POLICIES + ("gate_keep_default",)
    for seed in range(seed0, seed0 + n_seeds):
        for world_name in ("K", "A"):
            cfg = config_for(seed, world_name, "W3")
            world = build_world(cfg)
            for policy in policies:
                row = run_policy(world, policy)
                row["world_label"] = "W3"
                rows.append(row)
    return summarize(rows)


def observational_equivalence(seed: int = 5) -> Dict[str, Any]:
    """The Theorem-1 structure at the mechanism level: K and A share the
    SAME early logs; along the committing (archive) trajectory no further
    observations arrive in either world (W2 censoring), so the full realized
    observation logs are bit-identical while the lifecycle values are
    opposite."""
    logs: Dict[str, List[Dict[str, Any]]] = {}
    max_diff = 0.0
    for world_name in ("K", "A"):
        cfg = config_for(seed, world_name, "W2")
        world = build_world(cfg)
        row = run_policy(world, "association_commit")
        obs = [{"t": r["t"], "exposed": r["exposed"], "y": r["y"]}
               for r in row["decision_log"]]
        logs[world_name] = obs
    for k_row, a_row in zip(logs["K"], logs["A"]):
        for key in ("exposed", "y"):
            kv, av = k_row[key], a_row[key]
            diff = 0.0 if (kv == av) or (kv is None and av is None) \
                else abs(float(kv) - float(av))
            max_diff = max(max_diff, diff)
    n_rows = len(logs["K"])
    return {
        "seed": seed, "world_label": "W2", "policy": "association_commit",
        "joint_log_rows": n_rows,
        "max_field_diff": max_diff,
        "bit_identical": max_diff == 0.0,
        "K_lifecycle_value_per_step": config_for(seed, "K", "W2").kept_value,
        "A_lifecycle_value_per_step": config_for(seed, "A", "W2").kept_value,
        "note": "identical realized logs, opposite lifecycle values -- "
                "observationally equivalent worlds with opposite optimal "
                "persistent actions (Theorem 1 mechanism)",
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

METRICS = ("regret_T", "per_step_slope", "correction_time",
           "evidence_arrival", "probe_cost", "restore_cost",
           "false_forgetting_steps", "harmful_retention_steps", "probes",
           "restores", "log_overlap_archived", "log_overlap_keep")


def summarize(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per (world_label, world, policy) with normal CI."""
    out: Dict[str, Any] = {}
    keys = sorted({(str(r["world_label"]), str(r["world"]), str(r["policy"]))
                   for r in rows})
    for label, world_name, policy in keys:
        selected = [r for r in rows
                    if r["world_label"] == label and r["world"] == world_name
                    and r["policy"] == policy]
        cell: Dict[str, Any] = {"n_seeds": float(len(selected))}
        for metric in METRICS:
            values = [float(r[metric]) for r in selected]
            cell[metric] = {
                "mean": mean(values),
                "sd": stdev(values) if len(values) > 1 else 0.0,
                "ci95": (1.96 * stdev(values) / math.sqrt(len(values))
                         if len(values) > 1 else 0.0),
            }
        out[f"{label}_{world_name}_{policy}"] = cell
    return out


def paired_bootstrap(rows: Sequence[Dict[str, Any]],
                     pairs: Sequence[Tuple[str, str, str, str, str, str, str]],
                     n_boot: int = 2000,
                     boot_seed: int = 20260813) -> Dict[str, Any]:
    """Paired seed bootstrap of (mean_a - mean_b) for headline comparisons;
    the sampling unit is the seed (world realization), the same seed index
    is resampled for both cells.

    Pair spec: (name, label_a, world_a, policy_a, label_b, world_b, policy_b).
    """
    by_seed = {(str(r["world_label"]), str(r["world"]), str(r["policy"]),
                int(r["seed"])): r for r in rows}
    out: Dict[str, Any] = {}
    for name, la, wa, pa, lb, wb, pb in pairs:
        a_seeds = sorted({s for (k0, k1, k2, s) in by_seed
                          if k0 == la and k1 == wa and k2 == pa})
        b_seeds = sorted({s for (k0, k1, k2, s) in by_seed
                          if k0 == lb and k1 == wb and k2 == pb})
        common = sorted(set(a_seeds) & set(b_seeds))
        a_vals = [float(by_seed[(la, wa, pa, s)]["per_step_slope"])
                  for s in common]
        b_vals = [float(by_seed[(lb, wb, pb, s)]["per_step_slope"])
                  for s in common]
        out[name] = {
            "a": f"{la}_{wa}_{pa}", "b": f"{lb}_{wb}_{pb}",
            "n_seeds": float(len(common)),
            "slope_diff": paired_seed_diff_ci(a_vals, b_vals,
                                              n_boot=n_boot, seed=boot_seed),
        }
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--seed0", type=int, default=21)
    parser.add_argument("--output", type=Path,
                        default=Path("results/self_obscuring_ablation.json"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    ablation = structural_ablation(n_seeds=args.seeds, seed0=args.seed0)
    controls = reduction_controls(n_seeds=args.seeds, seed0=args.seed0)
    confirming = self_confirming_comparison(n_seeds=args.seeds,
                                            seed0=args.seed0)
    raw_rows: List[Dict[str, Any]] = []
    for label in ("W0", "W1", "W2", "W3"):
        for seed in range(args.seed0, args.seed0 + args.seeds):
            for world_name in ("K", "A"):
                cfg = config_for(seed, world_name, label)
                world = build_world(cfg)
                for policy in ("association_commit", "watchful_no_restore",
                               "watchful_restore"):
                    row = run_policy(world, policy)
                    row["world_label"] = label
                    raw_rows.append(row)
    for seed in range(args.seed0, args.seed0 + args.seeds):
        for world_name in ("K", "A"):
            cfg = config_for(seed, world_name, "W3")
            world = build_world(cfg)
            for policy in AUTO_ARCHIVED_POLICIES + ("gate_keep_default",):
                row = run_policy(world, policy)
                row["world_label"] = "W3"
                raw_rows.append(row)

    # (name, label_a, world_a, policy_a, label_b, world_b, policy_b)
    pairs = (
        ("self_confirming_W2_vs_W1", "W2", "K", "watchful_no_restore",
         "W1", "K", "watchful_no_restore"),
        ("restore_W3_vs_W2", "W3", "K", "watchful_restore",
         "W2", "K", "watchful_restore"),
        ("no_restore_committing_W2", "W2", "K", "watchful_no_restore",
         "W0", "K", "watchful_no_restore"),
        ("sc_no_probe_vs_fixed_restore", "W3", "K", "no_probe_commit",
         "W3", "K", "fixed_prob_restore"),
        ("sc_gate_no_probe_vs_cost_aware", "W3", "K", "gate_no_probe",
         "W3", "K", "cost_aware_commit_defer_probe"),
    )

    result = {
        "protocol": {
            "purpose": "structural ablation of the self-obscuring lifecycle "
                       "structure (14- §5/§7): W0-W3 matrix, reduction "
                       "controls, self-confirming policy comparison",
            "seeds": args.seeds, "seed0": args.seed0,
            "horizon": 2000, "n_early": 50, "tau": 10.0, "p_expose": 0.6,
            "threshold_keep": 2.0, "c_probe": 30.0, "c_restore": 80.0,
            "world_specs": WORLD_SPECS,
            "claim_discipline": ("computational/mechanism evidence; formal "
                                 "theorems T1/T2 in the theory documents"),
        },
        "structural_ablation_W0W3": ablation,
        "restore_cost_sweep": restore_cost_sweep(n_seeds=args.seeds,
                                                 seed0=args.seed0),
        "reduction_controls": controls,
        "self_confirming_W3": confirming,
        "observational_equivalence": observational_equivalence(),
        "paired_bootstrap": paired_bootstrap(raw_rows, pairs),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    if not args.quiet:
        flat = {k: {kk: vv["mean"] for kk, vv in v.items()
                    if isinstance(vv, dict) and "mean" in vv}
                for k, v in result["structural_ablation_W0W3"].items()}
        print(json.dumps({"structural_ablation_slopes": flat,
                          "reduction_controls": {
                              k: v["mean_slope"]
                              for k, v in result["reduction_controls"].items()},
                          "self_confirming": {
                              k: v["per_step_slope"]["mean"]
                              for k, v in
                              result["self_confirming_W3"].items()}},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
