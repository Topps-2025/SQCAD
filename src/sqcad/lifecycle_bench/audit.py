"""Fairness audit engine (R1-R3/R5 in the 23- experiment plan).

This module implements the four automated fairness channels that keep the
SQCAD-LifecycleBench from being "self-validating" (a dataset whose labels
only agree with its own design):

  R1  metadata-shortcut audit  -- how much of the oracle is recoverable
      from the public layer's metadata (family/variant) vs. from the trace
      text alone.  Outputs the metadata ceiling, a text-only predictor and
      the observation-equivalent-pair agreement ceiling.
  R2  label-sensitivity audit  -- re-compute all oracle labels under
      perturbed frozen contracts (``frozen_override``) and count flips.
  R3  unseen-mechanism holdout -- rebuild episodes under structural knobs
      unseen at design time (slots, crowding counts, entities, difficulties,
      storage sizes) and re-evaluate: do the designed mechanisms transfer?
  R5  independent-implementation consistency -- a second, clean-room
      implementation of the reference policy (``independent_ref.py``) must
      produce bit-identical rollouts.

Every threshold and perturbation set is pre-registered in the 23- plan and
in the freeze registry (freeze_four_piece.CONTRACT_REGISTRY["lifecycle_bench_contract"]["audit"]).
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from . import evaluator, frozen, world
from .evaluator import EpisodeOutcome, evaluate
from .generator import all_episodes
from .realizer import RealizedEpisode
from .rollout import PairedRollout, paired_rollout
from .world import RolloutConfig

# ---------------------------------------------------------------------------
# pre-registered audit configuration (mirrors the 23- plan and the freeze
# registry; do not edit between runs without re-registering)
# ---------------------------------------------------------------------------

# R2: frozen-contract perturbations -> (new value, needs_design_rebuild)
#    needs_design_rebuild = the constant enters the SCENARIO DESIGN (only
#    HARM_PENALTY does); all others are pure cost/behavior constants.
R2_PERTURBATIONS: Dict[str, Dict[str, Any]] = {
    "gamma":            {"values": [0.7, 0.95, 0.99], "rebuild": False},
    "harm_penalty":     {"values": [10.0, 40.0],      "rebuild": True},
    "storage_rate":     {"values": [0.005, 0.02],     "rebuild": False},
    "exposure_unit":    {"values": [0.02, 0.1],       "rebuild": False},
    "probe_cost":       {"values": [0.5, 2.0],        "rebuild": False},
    "task_value":       {"values": [5.0, 20.0],       "rebuild": False},
    "tau_tol":          {"values": [0.2, 1.0],        "rebuild": False},
    "adopt_threshold":  {"values": [1, 3],            "rebuild": False},
    "probe_threshold":  {"values": [2, 4],            "rebuild": False},
    "workspace_budget": {"values": [8, 12],           "rebuild": False},
    "recency_w":        {"values": [0.1, 0.5],        "rebuild": False},
    "frequency_w":      {"values": [0.05, 0.2],       "rebuild": False},
    "negative_attenuation": {"values": [5.0, 20.0],   "rebuild": False},
    "requalify_overlap": {"values": [1, 3],           "rebuild": False},
    "probe_budget_per_task": {"values": [0, 2],       "rebuild": False},
}

# pre-registered verdict thresholds (23- 6.3)
FLIP_ROBUST_THRESHOLD = 0.05    # |flip rate| below -> robust
FLIP_FRAGILE_THRESHOLD = 0.30   # |flip rate| above -> fragile, re-examine

# R3: unseen-mechanism knobs (family-specific structural transforms, applied
# to 20 fresh seeds per bucket; pre-registered in 23- 6.4)
R3_KNOBS = ("entity", "difficulty", "slot_shift")
R3_SEED_BASE = 20260901
R3_EPISODES_PER_BUCKET = 20


# ---------------------------------------------------------------------------
# frozen-contract override
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def frozen_override(**kwargs: Any) -> Iterator[None]:
    """Temporarily patch the frozen constants in every module that binds
    them (frozen / world / evaluator).  Restores exactly on exit.

    Patch order matters for R2: ``frozen`` itself must be patched before
    episodes are (re)built, so scenario design sees the perturbed value.
    """
    targets = (frozen, world, evaluator)
    saved: List[Tuple[str, Any, Any]] = []
    try:
        for name, value in kwargs.items():
            const = name.upper()
            found = False
            for mod in targets:
                if hasattr(mod, const):
                    saved.append((const, mod, getattr(mod, const)))
                    setattr(mod, const, value)
                    found = True
            if not found:
                raise KeyError(f"unknown frozen constant: {name}")
        yield
    finally:
        for const, mod, old in reversed(saved):
            setattr(mod, const, old)


# ---------------------------------------------------------------------------
# shared episode infrastructure
# ---------------------------------------------------------------------------
def cached_episodes(cache: Optional[Path] = None) -> List[RealizedEpisode]:
    """All 1380 episodes; pickled cache for repeated audit runs."""
    if cache is not None and cache.exists():
        import pickle
        return pickle.loads(cache.read_bytes())
    eps = all_episodes()
    if cache is not None:
        import pickle
        cache.write_bytes(pickle.dumps(eps))
    return eps


def outcome_of(ep: RealizedEpisode,
               cfg: RolloutConfig = RolloutConfig()) -> Tuple[EpisodeOutcome, PairedRollout]:
    pr = paired_rollout(ep, cfg)
    return evaluate(ep, pr.keep, pr.archive), pr


# ---------------------------------------------------------------------------
# R1: metadata-shortcut audit
# ---------------------------------------------------------------------------
def metadata_shortcut_audit(results_dir: Path) -> Dict[str, Any]:
    """Load the serialized dataset and measure how much of the oracle is
    recoverable from metadata alone vs. from the trace text alone.

    * metadata ceiling: majority-oracle lookup per (family, variant),
      fit on train, evaluated on dev/test (generalization) and in-sample;
    * text-only predictor: ridge multinomial logistic regression on
      public-layer features, no family/variant/regime/episode_id;
    * pair ceiling: an upper bound on ANY public-trace policy's oracle
      agreement, from the observation-equivalent pairs whose labels differ
      while the trace is identical.
    """
    public = [json.loads(l) for l in
              (results_dir / "public.jsonl").read_text(encoding="utf-8").splitlines()]
    hidden = [json.loads(l) for l in
              (results_dir / "hidden.jsonl").read_text(encoding="utf-8").splitlines()]
    hid_by_id = {h["episode_id"]: h for h in hidden}
    rows = []
    for p in public:
        h = hid_by_id[p["episode_id"]]
        rows.append({"id": p["episode_id"], "split": p["split"],
                     "family": p["family"], "variant": p["variant"],
                     "oracle": h["labels"]["oracle_action"],
                     "pair": h["pair"],
                     "features": _public_text_features(p)})

    out: Dict[str, Any] = {"n": len(rows)}
    out["oracle_distribution"] = {
        k: sum(1 for r in rows if r["oracle"] == k)
        for k in ("keep", "archive", "neutral")}

    # --- metadata lookup (majority per (family, variant)) ----------------
    for scope, key in (("family_variant", lambda r: (r["family"], r["variant"])),
                       ("family", lambda r: (r["family"],))):
        tr = [r for r in rows if r["split"] == "train"]
        de = [r for r in rows if r["split"] == "dev"]
        te = [r for r in rows if r["split"] == "test"]
        lookup = {}
        for r in tr:
            k = key(r)
            lookup.setdefault(k, {})
            lookup[k][r["oracle"]] = lookup[k].get(r["oracle"], 0) + 1
        rule = {k: max(c, key=c.get) for k, c in lookup.items()}
        def acc(pool):
            hit = 0
            for r in pool:
                if rule.get(key(r)) == r["oracle"]:
                    hit += 1
            return hit / len(pool) if pool else None
        out["metadata_" + scope] = {
            "train_acc": acc(tr), "dev_acc": acc(de), "test_acc": acc(te),
            "n_groups": len(rule)}

    # --- text-only predictor (ridge multinomial logistic) ----------------
    out["text_only"] = _text_only_predictor(rows)

    # --- pair ceiling -----------------------------------------------------
    by_pair: Dict[str, List[str]] = {}
    for r in rows:
        if r["pair"]:
            by_pair.setdefault(r["pair"], []).append(r["oracle"])
    disagree = sum(1 for v in by_pair.values() if len(set(v)) > 1)
    out["pair_ceiling"] = {
        "n_pairs": len(by_pair),
        "disagreeing_pairs": disagree,
        "max_oracle_agreement": 1.0 - disagree / len(rows),
    }
    return out


def _public_text_features(p: Dict) -> List[float]:
    """Public-layer features WITHOUT family/variant/episode_id/regime.
    Every feature is computable from sessions + decision task + memories +
    future items, exactly what a metadata-free policy receives."""
    sessions = p["sessions"]
    msgs = [(m["kind"], m["text"]) for m in sessions]
    import re
    def toks(t):
        return set(t for t in re.split(r"[^a-z0-9]+", t.lower()) if t)
    decision_mem = p["decision_memory"]
    dmem = next(m for m in p["memories"] if m["pid"] == decision_mem)
    d_toks = toks(dmem["text"])
    d_scope = p["decision_task"]["scope"]
    futs = p["future"]

    corr_texts = [t for k, t in msgs if k == "correction"]
    upd_texts = [t for k, t in msgs if k == "update"]
    sess_texts = [t for _, t in msgs]
    event_texts = corr_texts + upd_texts

    max_ev_overlap = max((len(d_toks & toks(t)) for t in event_texts),
                         default=0)
    max_sess_overlap = max((len(d_toks & toks(t)) for t in sess_texts),
                           default=0)
    future_scopes = [f["scope"] for f in futs if f["kind"] == "task"]
    n_future_other_scope = sum(
        1 for s in future_scopes if s != d_scope)
    future_events = sum(1 for f in futs if f["kind"] == "event")

    return [
        float(len(msgs)),                         # 0 message count
        float(sum(1 for k, _ in msgs if k == "correction")),  # 1
        float(sum(1 for k, _ in msgs if k == "update")),      # 2
        float(len(event_texts)),                  # 3
        max_ev_overlap,                           # 4 identifiability
        max_sess_overlap,                         # 5 exposure strength
        float(len(p["memories"])),                # 6
        float(dmem["storage_tokens"]),            # 7 decision-mem size
        float(len(d_toks)),                       # 8 decision-mem length
        n_future_other_scope,                     # 9 scope transport
        future_events,                            # 10 future events
        float(len(futs)),                         # 11
        float(len(future_scopes)),                # 12
        float(len({f["query"] for f in futs if f["query"]})),  # 13 query variety
        float(sum(1 for f in futs if f["kind"] == "event"
                  and f["event_text"] is not None)),           # 14
    ]


def _text_only_predictor(rows: List[Dict]) -> Dict[str, Any]:
    """Ridge multinomial logistic regression on the public text features.
    Pure numpy (the audit must run in the remote env with numpy only).
    Fit on train, report dev/test and in-sample accuracy vs. the oracle."""
    import numpy as np
    X = np.array([r["features"] for r in rows], dtype=float)
    classes = ["keep", "archive", "neutral"]
    ys = [r["oracle"] for r in rows]
    idx = np.arange(len(rows))
    tr = np.array([i for i, r in enumerate(rows) if r["split"] == "train"])
    de = np.array([i for i, r in enumerate(rows) if r["split"] == "dev"])
    te = np.array([i for i, r in enumerate(rows) if r["split"] == "test"])

    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    Xs = np.column_stack([Xs, np.ones(len(Xs))])

    W, _ = _logistic_fit(Xs[tr], [ys[i] for i in tr], classes)

    def acc(pool: np.ndarray) -> Dict[str, Any]:
        if len(pool) == 0:
            return {"acc": None}
        pred = np.array(classes)[np.argmax(Xs[pool] @ W, axis=1)]
        yp = np.array([ys[i] for i in pool])
        hit = int((pred == yp).sum())
        per_class = {}
        for c in classes:
            m = yp == c
            if m.sum():
                per_class[c] = float((pred[m] == c).mean())
        return {"acc": hit / len(pool), "n": int(len(pool)),
                "per_class_acc": per_class}

    return {"train": acc(tr), "dev": acc(de), "test": acc(te),
            "classes": classes, "n_features": int(X.shape[1])}


def _logistic_fit(X: Any, y: List[str], classes: Sequence[str]) -> Any:
    """Ridge multinomial logistic fit; returns (W, classes).  Pure numpy."""
    import numpy as np
    Y = np.zeros((len(y), len(classes)))
    for i, c in enumerate(classes):
        Y[np.where(np.array(y) == c)[0], i] = 1.0
    W = np.zeros((X.shape[1], len(classes)))
    lam, lr = 1.0, 0.3
    for _ in range(500):
        logits = X @ W
        logits -= logits.max(1, keepdims=True)
        p = np.exp(logits) / np.exp(logits).sum(1, keepdims=True)
        W -= lr * (X.T @ (p - Y) + lam * W) / len(y)
    return (W, classes)


# ---------------------------------------------------------------------------
# R2: label-sensitivity audit
# ---------------------------------------------------------------------------
def sensitivity_audit(episodes: List[RealizedEpisode],
                      baseline: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Re-compute all 1380 oracle labels under each pre-registered
    perturbation; report flip rates overall and per family."""
    if baseline is None:
        with frozen_override():
            baseline = {}
            for ep in episodes:
                out, _ = outcome_of(ep)
                baseline[ep.world.episode_id] = out.oracle_action

    results = []
    for const, cfg in R2_PERTURBATIONS.items():
        for value in cfg["values"]:
            # rebuild runs need the design-time constant: rebuild the SAME
            # episode ids the baseline covers (all_episodes() on the full
            # dataset is a superset only if the caller passed a sample)
            pool = [ep for ep in all_episodes()
                    if ep.world.episode_id in baseline] \
                if cfg["rebuild"] else episodes
            flips: Dict[str, Dict[str, int]] = {}
            n_flip = 0
            n_total = 0
            with frozen_override(**{const: value}):
                for ep in pool:
                    out, _ = outcome_of(ep)
                    old = baseline[ep.world.episode_id]
                    n_total += 1
                    if out.oracle_action != old:
                        n_flip += 1
                        fam = ep.world.family
                        flips.setdefault(fam, {})
                        flips[fam][old] = flips[fam].get(old, 0) + 1
            results.append({
                "constant": const, "value": value, "rebuild": cfg["rebuild"],
                "flip_rate": n_flip / n_total, "n_flip": n_flip,
                "n_total": n_total,
                "per_family": {k: v for k, v in sorted(flips.items())},
            })

    verdict = "robust" if all(r["flip_rate"] <= FLIP_ROBUST_THRESHOLD
                              for r in results) else \
        ("fragile" if any(r["flip_rate"] >= FLIP_FRAGILE_THRESHOLD
                          for r in results) else "mixed")
    return {"verdict": verdict, "runs": results,
            "thresholds": {"robust": FLIP_ROBUST_THRESHOLD,
                           "fragile": FLIP_FRAGILE_THRESHOLD}}


# ---------------------------------------------------------------------------
# R3: unseen-mechanism holdout
# ---------------------------------------------------------------------------
def unseen_audit() -> Dict[str, Any]:
    """Rebuild episodes under structural knobs unseen at design time and
    re-evaluate the designed mechanisms (implemented in ``unseen.py``)."""
    from . import unseen
    return unseen.run_audit()
