"""SQCAD-LifecycleBench (doc 22-): a rule-world benchmark for the lifecycle
value of persistent memory actions (keep/archive), with hidden evaluator-only
counterfactual labels and a frozen cost contract.

Layers (doc 22- 4):
  scenarios  -- Scenario Designer (frozen structured templates + hidden graph)
  realizer   -- Trace Realizer (deterministic natural-language realization)
  world      -- World Simulator + frozen reference policy (observable-only)
  rollout    -- paired keep/archive rollouts (same-source counterfactual)
  evaluator  -- Independent Evaluator (the only gold reader)
  generator  -- dataset assembly + splits + three-layer serialization
"""

from .frozen import (
    ADOPT_THRESHOLD, CONTROL_EPISODES, DECISION_POINTS_PER_EPISODE,
    EPISODES_PER_FAMILY, EXPOSURE_UNIT, GAMMA, HARM_PENALTY, HORIZON,
    N_FUTURE_TASKS, NEGATIVE_ATTENUATION, PROBE_BUDGET_PER_TASK, PROBE_COST,
    PROBE_THRESHOLD, RECENCY_W, REQUALIFY_OVERLAP, STORAGE_RATE, TASK_VALUE,
    TAU_TOL, VERSION, WORKSPACE_BUDGET,
)
