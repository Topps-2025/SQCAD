"""Baseline matrix for the SQCAD-LifecycleBench (22- 9, 23- 5).

Every policy is a DECISION function at the episode's decision point: it
reads the public layer (sessions / decision task / memories / future /
policy-log certificates) and outputs keep or archive.  Its value is the
lifecycle value of the chosen branch under the frozen reference follow-on
(or an ablated follow-on for the ablation family):

    value_policy(ep) = V_s^pi(action_policy(ep)) with the paired rollout
    of the branch the policy chose (evaluator.discounted_value).

Policies (22- 9 baseline family):
  * blind commits      -- keep_all, archive_all, random50
  * exposure heuristics -- recency2, frequency2, storage12, memory_worth
  * text-only rules    -- event_rule (lexical overlap with visible events)
  * scope rule         -- scope_literal
  * SQCAD variants     -- sqcad_cert (NEGATIVE/MISMATCH -> archive, else
                          keep), sqcad_cert_conflict (+ lineage conflict ->
                          archive), probe_willing (archive unless POSITIVE)
  * oracle_policy      -- chooses the oracle action (UPPER BOUND only,
                          reads gold; reported for regret reference)
Ablations (22- 9): the sqcad_cert decision with a RolloutConfig switch off
(no_qualification / no_censoring / no_restore / no_lineage / no_probe).
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .evaluator import EpisodeOutcome, discounted_value
from .frozen import ADOPT_THRESHOLD, REQUALIFY_OVERLAP
from .realizer import RealizedEpisode, overlap, tokenize
from .rollout import PairedRollout
from .world import (
    MISMATCH, NEGATIVE, POSITIVE, UNRESOLVED, RolloutConfig, simulate_branch,
)

# ---------------------------------------------------------------------------
# observable feature helpers
# ---------------------------------------------------------------------------
def _decision_tokens(ep: RealizedEpisode):
    return ep.tokens(ep.world.decision_fid)


def _session_overlaps(ep: RealizedEpisode) -> List[int]:
    """Per-session max overlap between the decision memory and the session
    messages (public-layer only)."""
    d = set(_decision_tokens(ep))
    out = []
    for s in ep.sessions:
        best = max((len(d & set(tokenize(m.text))) for m in s.messages),
                   default=0)
        out.append(best)
    return out


def _event_overlap(ep: RealizedEpisode) -> int:
    d = set(_decision_tokens(ep))
    best = 0
    for s in ep.sessions:
        for m in s.messages:
            if m.kind in ("update", "correction"):
                best = max(best, len(d & set(tokenize(m.text))))
    return best


# ---------------------------------------------------------------------------
# decision policies
# ---------------------------------------------------------------------------
def p_keep_all(ep: RealizedEpisode) -> str:
    return "keep"


def p_archive_all(ep: RealizedEpisode) -> str:
    return "archive"


def p_random50(ep: RealizedEpisode) -> str:
    h = int(hashlib.sha256(ep.world.episode_id.encode()).hexdigest(), 16)
    return "keep" if h % 2 == 0 else "archive"


def p_recency2(ep: RealizedEpisode) -> str:
    """Keep iff the decision memory is mentioned in one of the last two
    sessions (overlap >= ADOPT_THRESHOLD); otherwise archive."""
    ov = _session_overlaps(ep)
    return "keep" if max(ov[-2:], default=0) >= ADOPT_THRESHOLD else "archive"


def p_frequency2(ep: RealizedEpisode) -> str:
    """Keep iff the decision memory is mentioned in >= 2 sessions."""
    ov = _session_overlaps(ep)
    return "keep" if sum(1 for o in ov if o >= ADOPT_THRESHOLD) >= 2 \
        else "archive"


def p_storage12(ep: RealizedEpisode) -> str:
    """Archive iff the decision memory is large (> 12 storage tokens)."""
    return "keep" if ep.memory(ep.world.decision_fid).spec.storage_tokens <= 12 \
        else "archive"


def p_memory_worth(ep: RealizedEpisode) -> str:
    """Memory-worth proxy: keep iff cheap (<= 10 tokens) -- small facts are
    assumed worth keeping."""
    return "keep" if ep.memory(ep.world.decision_fid).spec.storage_tokens <= 10 \
        else "archive"


def p_event_rule(ep: RealizedEpisode) -> str:
    """Text-only identifiability: archive iff a visible update/correction
    event overlaps the decision memory (>= REQUALIFY_OVERLAP shared
    tokens); keep otherwise."""
    return "archive" if _event_overlap(ep) >= REQUALIFY_OVERLAP else "keep"


def p_scope_literal(ep: RealizedEpisode) -> str:
    """Scope-transport heuristic: archive iff some future task moves to a
    scope different from the decision scope (the memory's value would have
    to transport across scopes -- Prop C analog)."""
    d = ep.world.decision_scope
    cross = any(it.task.spec.scope != d
                for it in ep.future_items
                if it.spec.kind == "task" and it.task is not None)
    return "archive" if cross else "keep"


def _cert(ep: RealizedEpisode, fid: str):
    from .world import reference_certificate
    return reference_certificate(ep, fid, ep.world.decision_scope)


def p_sqcad_cert(ep: RealizedEpisode) -> str:
    c = _cert(ep, ep.world.decision_fid)
    return "archive" if c.status in (NEGATIVE, MISMATCH) else "keep"


def p_sqcad_cert_conflict(ep: RealizedEpisode) -> str:
    c = _cert(ep, ep.world.decision_fid)
    if c.status in (NEGATIVE, MISMATCH):
        return "archive"
    if c.status is UNRESOLVED and c.reason.startswith("lineage_conflict"):
        return "archive"
    return "keep"


def p_probe_willing(ep: RealizedEpisode) -> str:
    """Aggressive archive: archive whenever the certificate is not POSITIVE
    (probes can restore cheaply)."""
    c = _cert(ep, ep.world.decision_fid)
    return "keep" if c.status is POSITIVE else "archive"


def p_oracle(ep: RealizedEpisode, hidden: Dict[str, EpisodeOutcome]) -> str:
    return hidden[ep.world.episode_id].oracle_action


DECISION_POLICIES: Dict[str, Callable[[RealizedEpisode], str]] = {
    "keep_all": p_keep_all,
    "archive_all": p_archive_all,
    "random50": p_random50,
    "recency2": p_recency2,
    "frequency2": p_frequency2,
    "storage12": p_storage12,
    "memory_worth": p_memory_worth,
    "event_rule": p_event_rule,
    "scope_literal": p_scope_literal,
    "sqcad_cert": p_sqcad_cert,
    "sqcad_cert_conflict": p_sqcad_cert_conflict,
    "probe_willing": p_probe_willing,
}

ABLATIONS: Dict[str, RolloutConfig] = {
    "no_qualification": RolloutConfig(qualification=False),
    "no_censoring": RolloutConfig(censoring=False),
    "no_restore": RolloutConfig(restore=False),
    "no_lineage": RolloutConfig(lineage=False),
    "no_probe": RolloutConfig(probing=False),
}

BUCKET_KEY = lambda ep: f"{ep.world.family}/{ep.world.variant}"  # noqa: E731


# ---------------------------------------------------------------------------
# value of a policy on one episode
# ---------------------------------------------------------------------------
def branch_value(ep: RealizedEpisode, action: str,
                 cfg: RolloutConfig = RolloutConfig()) -> float:
    return discounted_value(ep, simulate_branch(ep, action, cfg))


def episode_result(ep: RealizedEpisode, action: str, out: EpisodeOutcome,
                   value: float) -> Dict[str, Any]:
    best = max(out.lifecycle_value_keep, out.lifecycle_value_archive)
    return {
        "episode_id": ep.world.episode_id,
        "bucket": BUCKET_KEY(ep),
        "action": action,
        "oracle": out.oracle_action,
        "value": round(value, 4),
        "regret": round(best - value, 4),
        "false_commit": action == "keep" and out.oracle_action == "archive",
        "missed_commit": action == "archive" and out.oracle_action == "keep",
        "agreement": action == out.oracle_action,
        "neutral": out.oracle_action == "neutral",
    }


# ---------------------------------------------------------------------------
# matrix runner
# ---------------------------------------------------------------------------
def run_decision_matrix(episodes: Sequence[RealizedEpisode],
                        hidden: Dict[str, EpisodeOutcome]) -> Dict[str, Any]:
    """Value of every decision policy on every episode (reference follow-on).
    Returns per-policy aggregates + per-bucket leaderboard."""
    rows: Dict[str, List[Dict[str, Any]]] = {}
    for name, fn in DECISION_POLICIES.items():
        rows[name] = []
        for ep in episodes:
            a = fn(ep)
            v = branch_value(ep, a)
            rows[name].append(episode_result(ep, a, hidden[ep.world.episode_id], v))
    # oracle upper bound
    rows["oracle_policy"] = []
    for ep in episodes:
        out = hidden[ep.world.episode_id]
        a = out.oracle_action if out.oracle_action != "neutral" else "keep"
        v = branch_value(ep, a)
        rows["oracle_policy"].append(episode_result(ep, a, out, v))

    summary = {}
    for name, rs in rows.items():
        n = len(rs)
        n_nn = n - sum(1 for r in rs if r["neutral"])
        summary[name] = {
            "mean_value": round(sum(r["value"] for r in rs) / n, 4),
            "mean_regret": round(sum(r["regret"] for r in rs) / n, 4),
            "oracle_agreement": round(
                sum(1 for r in rs if r["agreement"]) / n_nn, 4)
                if n_nn else None,
            "false_commit_rate": round(
                sum(1 for r in rs if r["false_commit"]) / n, 4),
            "missed_commit_rate": round(
                sum(1 for r in rs if r["missed_commit"]) / n, 4),
        }
    return {"summary": summary, "rows": rows}


def run_ablation_matrix(episodes: Sequence[RealizedEpisode],
                        hidden: Dict[str, EpisodeOutcome]) -> Dict[str, Any]:
    """sqcad_cert decision under each ablated follow-on."""
    out = {}
    for name, cfg in ABLATIONS.items():
        vals = []
        for ep in episodes:
            a = p_sqcad_cert(ep)
            v = branch_value(ep, a, cfg)
            vals.append(episode_result(ep, a, hidden[ep.world.episode_id], v))
        n = len(vals)
        out[name] = {
            "mean_value": round(sum(r["value"] for r in vals) / n, 4),
            "mean_regret": round(sum(r["regret"] for r in vals) / n, 4),
            "false_commit_rate": round(
                sum(1 for r in vals if r["false_commit"]) / n, 4),
            "missed_commit_rate": round(
                sum(1 for r in vals if r["missed_commit"]) / n, 4),
        }
    return out


def per_bucket_table(rows: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Mean value per (family, variant) for every policy."""
    buckets = sorted({r["bucket"] for r in next(iter(rows.values()))})
    table = {}
    for b in buckets:
        table[b] = {}
        for name, rs in rows.items():
            vals = [r["value"] for r in rs if r["bucket"] == b]
            table[b][name] = round(sum(vals) / len(vals), 4) if vals else None
    return table


# ---------------------------------------------------------------------------
# paired bootstrap (paired on episode_id, fixed seed)
# ---------------------------------------------------------------------------
def bootstrap_diff(ref_values: Sequence[float], base_values: Sequence[float],
                   n_boot: int = 2000, seed: int = 20260817,
                   alpha: float = 0.05) -> Dict[str, float]:
    """Paired bootstrap 95% CI of mean(ref) - mean(base)."""
    import numpy as np
    assert len(ref_values) == len(base_values)
    rng = np.random.default_rng(seed)
    d = np.asarray(ref_values, dtype=float) - np.asarray(base_values, dtype=float)
    draws = rng.choice(d, size=(n_boot, len(d)), replace=True).mean(axis=1)
    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"diff_mean": float(d.mean()), "ci_lo": float(lo),
            "ci_hi": float(hi), "n_boot": n_boot,
            "significant": bool(lo > 0 or hi < 0)}
