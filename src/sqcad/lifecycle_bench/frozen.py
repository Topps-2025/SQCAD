"""Frozen manifest for the SQCAD-LifecycleBench MVP dataset (doc 22-).

Every constant used by the scenario designer, trace realizer, world
simulator, reference policy and evaluator is pre-registered here BEFORE
generation and shipped inside the built dataset's ``manifest`` so that
consumers can verify the cost contract, budgets and seeds did not move
between construction and evaluation.

Cost contract (per task epoch, discounted by ``GAMMA`` over ``HORIZON``):
  * task success  : +TASK_VALUE * difficulty
  * harm penalty  : -HARM_PENALTY per wrong-use adoption (stale / wrong scope)
  * storage       : -storage_tokens(mem) / 100 per epoch while in the
                    persistent store (archived entries cost zero)
  * exposure      : -EXPOSURE_UNIT per exposed memory per task
  * probe         : -PROBE_COST per probe (paid even if the probe fails to
                    earn a workspace slot)
  * restore       : free once the probed entry earns a slot (16- semantics)

Reference policy (frozen, gold-side only for value computation; it never
reads gold):  the SQCAD-like policy from the unified contract --
    * at the decision point it derives a qualification certificate from
      observables only (visible scope/version/correction events, co-exposure
      counts, frequency);
    * a certificate in {NEGATIVE} forbids future probes and attenuates
      natural exposure; a certificate in {UNRESOLVED} keeps the memory in
      the store but permits paid probes; {POSITIVE} keeps and exposes;
    * per task at most PROBE_BUDGET_PER_TASK probes at the strongest
      lexical-overlap archived memory (probe threshold PROBE_THRESHOLD,
      scope gate, non-negative certificate);
    * a probed memory earns one workspace slot and permanent restore only if
      its proposer score >= the smallest score of the current workspace
      (budgeted competitive access, 16-);
    * a visible correction/update event that lexically overlaps a memory
      re-qualifies it to NEGATIVE (version/lineage gate, E1/E2 overlay).
"""

from __future__ import annotations

# --- dataset shape -------------------------------------------------------
VERSION = "v0.1"
HORIZON = 10                  # future items after the decision point (doc 22- 10)
EPISODES_PER_FAMILY = 200     # doc 22- 10: 6 classes x 200 episodes
CONTROL_EPISODES = 50         # stable-positive / stable-negative / neutral
DECISION_POINTS_PER_EPISODE = 1
N_FUTURE_TASKS = 10

# --- cost contract -------------------------------------------------------
GAMMA = 0.9                   # per-task discount
TASK_VALUE = 10.0             # utility of a successful task (x difficulty)
HARM_PENALTY = 20.0           # wrong-use adoption (stale / wrong scope)
EXPOSURE_UNIT = 0.05          # per exposed memory per task
PROBE_COST = 1.0              # per paid probe (paid even when wasted)
STORAGE_RATE = 0.01           # per storage token per epoch  (tokens/100)
TAU_TOL = 0.5                 # oracle boundary: |tau| <= TAU_TOL -> neutral

# --- budgets -------------------------------------------------------------
WORKSPACE_BUDGET = 10         # B, competitive access budget (16- BUDGET analog)
PROBE_BUDGET_PER_TASK = 1

# --- lexical gates -------------------------------------------------------
ADOPT_THRESHOLD = 2           # shared tokens required for one-time adoption
PROBE_THRESHOLD = 3           # shared tokens required for a paid probe (16- 1.4)

# --- proposer scores -----------------------------------------------------
RECENCY_W = 0.3               # score bonus if the memory was exposed last task
FREQUENCY_W = 0.1             # score bonus x log1p(exposure count)
NEGATIVE_ATTENUATION = 10.0   # score penalty for a NEGATIVE certificate

# --- splits --------------------------------------------------------------
SPLIT_WEIGHTS = (0.6, 0.2, 0.2)   # train / dev / test at group level (22- 8)

# --- seeds ---------------------------------------------------------------
BASE_SEED = 20260817
PAIR_SEED = 20260818
SPLIT_SEED = 20260819

# --- reference policy ----------------------------------------------------
REQUALIFY_OVERLAP = 2         # correction/update event shared tokens needed
