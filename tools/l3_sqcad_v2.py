"""L3 theory-aligned supplement (31- §5.3.1, 30- R1/R3).

Implements the Theorem-5 three-decision rule on the frozen LifecycleBench
and aggregates event-level metrics that the frozen matrix does not report:

  sqcad_v2        -- POSITIVE -> keep (interval L > 0), NEGATIVE/MISMATCH ->
                     archive (U < 0), UNRESOLVED -> defer.  In the binary
                     decision world the defer path is realized reversibly:
                     archive + follow-on probe/restore (C_probe = 1.0 per
                     task, budget 1/task).  Refusing to commit on the
                     unidentified class is exactly what Thm 4 forces
                     (committing rules on this class incur regret >= 660).
                     Note: with reversible probes this reduces to the
                     probe-willing action mapping; the new content is (a) the
                     theory attribution, (b) the abstention/authorization
                     audit stats, (c) the cost attribution via ablations.
  sqcad_v2_probe  -- VOI-probe variant: on UNRESOLVED, keep iff the memory
                     is rare (observable: mentioned in exactly one public
                     session) AND carries no known-negative qualification
                     reason (association_only_hitchhiker / lineage_conflict)
                     -- high VOI: a rare candidate will not re-surface
                     naturally, so deferring cheaply now beats paying probe +
                     restore later; else archive.  Tests whether the Thm-5
                     defer rule should resolve rare candidates toward keep.

Event-level metrics (per policy, all 1380 episodes):
  cert_status / abstention_rate
  abstention_precision      P(oracle == archive | decision UNRESOLVED)
  commit_precision          P(oracle == keep | action keep)
  unauthorized_commit       keep with non-POSITIVE cert and oracle==archive
                            (the Thm-4 forbidden blind commit, empirically)
  authorized_safe_commit    keep with POSITIVE cert and oracle==keep
  probe_action_change       fraction of probe events on the decision fid
                            that restored it (access state change)
  restore_precision         P(slot needed == decision fid and success |
                            decision fid restored at that slot)
  recovery_rate             P(restored within horizon | action archive and
                            oracle keep) -- how often the reversible defer
                            path repairs a missed commit
  mean_time_to_recovery     first slot (1..10) of restoration (repaired
                            episodes only)

Runs both policies under the reference follow-on and under each ablation
switch (no_qualification / no_censoring / no_restore / no_lineage /
no_probe) to attribute the defer path's cost to restore/probe availability,
plus paired bootstrap (n_boot=2000, seed=20260817) against the frozen rows.

Writes remote_results/lifecycle_audit/l3_sqcad_v2.json and prints a
markdown table for direct pasting into 31- §5.3.1.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from sqcad.lifecycle_bench.audit import cached_episodes, outcome_of
from sqcad.lifecycle_bench.baselines import (
    ABLATIONS, BUCKET_KEY, DECISION_POLICIES, branch_value,
    bootstrap_diff, per_bucket_table,
)
from sqcad.lifecycle_bench.evaluator import EpisodeOutcome
from sqcad.lifecycle_bench.frozen import ADOPT_THRESHOLD
from sqcad.lifecycle_bench.realizer import RealizedEpisode, tokenize
from sqcad.lifecycle_bench.world import (
    MISMATCH, NEGATIVE, POSITIVE, UNRESOLVED, Rollout, RolloutConfig,
    reference_certificate, simulate_branch,
)

RESULTS = Path("results/lifecycle_bench")
OUT_DEFAULT = Path("remote_results/lifecycle_audit/l3_sqcad_v2.json")

NEG_REASONS = ("association_only_hitchhiker",)
CONFLICT_REASONS = ("lineage_conflict",)


def cert_of(ep: RealizedEpisode):
    return reference_certificate(ep, ep.world.decision_fid,
                                 ep.world.decision_scope)


def session_hits(ep: RealizedEpisode) -> int:
    """Number of public sessions mentioning the decision memory
    (overlap >= ADOPT_THRESHOLD, same convention as p_frequency2)."""
    d = set(ep.tokens(ep.world.decision_fid))
    return sum(
        1 for s in ep.sessions
        if any(len(d & set(tokenize(m.text))) >= ADOPT_THRESHOLD
               for m in s.messages))


# ---------------------------------------------------------------------------
# decision policies (theory-aligned family)
# ---------------------------------------------------------------------------
def p_sqcad_v2(ep: RealizedEpisode) -> str:
    """Thm-5 rule: authorize keep iff the interval is strictly positive
    (POSITIVE cert); archive iff strictly negative (NEGATIVE/MISMATCH);
    on UNRESOLVED (crossing interval) refuse to commit: defer via the
    reversible archive + probe/restore path."""
    c = cert_of(ep)
    if c.status is POSITIVE:
        return "keep"
    return "archive"


def p_sqcad_v2_probe(ep: RealizedEpisode) -> str:
    """VOI-probe on the crossing interval: keep iff the candidate is rare
    (single-session) and carries no known-negative qualification reason;
    otherwise defer-archive.  Rare + no-negative-evidence = highest VOI:
    it will not re-surface naturally, and there is no observable reason to
    believe the memory is harmful."""
    c = cert_of(ep)
    if c.status is POSITIVE:
        return "keep"
    if c.status is UNRESOLVED:
        if session_hits(ep) == 1 and not c.reason.startswith(NEG_REASONS) \
                and not c.reason.startswith(CONFLICT_REASONS):
            return "keep"
    return "archive"


V2_POLICIES: Dict[str, Callable[[RealizedEpisode], str]] = {
    "sqcad_v2": p_sqcad_v2,
    "sqcad_v2_probe": p_sqcad_v2_probe,
}


# ---------------------------------------------------------------------------
# decision + event-level aggregation
# ---------------------------------------------------------------------------
def run_v2_family(episodes: List[RealizedEpisode],
                  hidden: Dict[str, EpisodeOutcome]) -> Dict[str, any]:
    """Rows for the v2 family: standard summary + event-level metrics."""
    fam = {}
    for name, fn in V2_POLICIES.items():
        rows = []
        for ep in episodes:
            out = hidden[ep.world.episode_id]
            a = fn(ep)
            v = branch_value(ep, a)
            roll = simulate_branch(ep, a)
            best = max(out.lifecycle_value_keep, out.lifecycle_value_archive)
            rows.append({
                "episode_id": ep.world.episode_id,
                "bucket": BUCKET_KEY(ep),
                "action": a,
                "oracle": out.oracle_action,
                "value": round(v, 4),
                "regret": round(best - v, 4),
                "cert_status": str(cert_of(ep).status),
                "cert_reason": cert_of(ep).reason,
                "session_hits": session_hits(ep),
                **event_metrics(ep, out, roll),
            })
        fam[name] = {"rows": rows, **summarize_v2(rows)}
    return fam


def event_metrics(ep: RealizedEpisode, out: EpisodeOutcome,
                  roll: Rollout) -> Dict[str, float]:
    fid = ep.world.decision_fid
    probe_slots = [l for l in roll.logs if fid in l.probes]
    restore_slots = [l for l in roll.logs if fid in l.restore]
    ok = restore_slots and all(
        l.needed == fid and l.success for l in restore_slots)
    return {
        "probe_action_change": round(
            len(restore_slots) / len(probe_slots), 4) if probe_slots else None,
        "restore_precision": round(
            sum(1 for l in restore_slots if l.needed == fid and l.success)
            / len(restore_slots), 4) if restore_slots else None,
        "recovered": bool(restore_slots),
        "time_to_recovery": min(l.slot for l in restore_slots)
        if restore_slots else None,
        "rescue_possible": out.rescue_possible,
    }


def summarize_v2(rows: List[Dict[str, any]]) -> Dict[str, any]:
    n = len(rows)
    unresolved = [r for r in rows if r["cert_status"] == str(UNRESOLVED)]
    keeps = [r for r in rows if r["action"] == "keep"]
    pos_keeps = [r for r in rows
                 if r["action"] == "keep" and r["cert_status"] == str(POSITIVE)]
    un_auth = [r for r in rows if r["action"] == "keep"
               and r["cert_status"] != str(POSITIVE)
               and r["oracle"] == "archive"]
    miss = [r for r in rows if r["action"] == "archive"
            and r["oracle"] == "keep"]
    repaired = [r for r in miss if r["recovered"]]
    neut = [r for r in unresolved if r["oracle"] == "neutral"]
    return {
        "n": n,
        "mean_value": round(sum(r["value"] for r in rows) / n, 4),
        "mean_regret": round(sum(r["regret"] for r in rows) / n, 4),
        "abstention_rate": round(len(unresolved) / n, 4),
        "abstention_precision": round(
            sum(1 for r in unresolved if r["oracle"] == "archive")
            / len(unresolved), 4) if unresolved else None,
        "abstention_neutral_rate": round(len(neut) / len(unresolved), 4)
        if unresolved else None,
        "abstention_miss_rate": round(
            sum(1 for r in unresolved if r["oracle"] == "keep")
            / len(unresolved), 4) if unresolved else None,
        "commit_precision": round(
            sum(1 for r in keeps if r["oracle"] == "keep") / len(keeps), 4)
        if keeps else None,
        "authorized_safe_commit": round(
            sum(1 for r in pos_keeps if r["oracle"] == "keep") / n, 4),
        "unauthorized_commit": round(len(un_auth) / n, 4),
        "missed_commit_rate": round(len(miss) / n, 4),
        "recovery_rate": round(len(repaired) / len(miss), 4) if miss else None,
        "mean_time_to_recovery": round(
            sum(r["time_to_recovery"] for r in repaired) / len(repaired), 2)
        if repaired else None,
        "probe_action_change": round(
            sum(r["probe_action_change"] or 0 for r in rows) / n, 4),
        "restore_precision": round(
            sum(r["restore_precision"] or 0 for r in rows) / n, 4),
    }


# ---------------------------------------------------------------------------
# honest statistical units (bucket-level bootstrap)
#
# ICLR-challenge round 1 (32-): episodes within a rule-world bucket are
# surface replications of the same template instantiation -- 13/14 buckets
# carry exactly one distinct value -- so episode-level bootstrap (n=1380)
# overstates precision by ~sqrt(1380/14).  Independent units are the ~14
# rule-world instantiations; the bucket-level bootstrap below pairs policy
# means BY BUCKET and resamples over buckets only.
# ---------------------------------------------------------------------------
def _bucket_means(pairs: Sequence[Tuple[str, float]]) -> Dict[str, float]:
    acc: Dict[str, List[float]] = {}
    for b, v in pairs:
        acc.setdefault(b, []).append(v)
    return {b: sum(vs) / len(vs) for b, vs in acc.items()}


def bootstrap_stratified_diff(pa: Sequence[Tuple[str, float]],
                              pb: Sequence[Tuple[str, float]],
                              n_boot: int = 2000, seed: int = 20260817,
                              label: str = "") -> Dict[str, any]:
    """TWO-STAGE CLUSTER bootstrap: resample BUCKETS with replacement, then
    episodes within each drawn bucket.  This is the correct third view, and it
    is reported alongside the bucket-level CI, never instead of it.

    Measured negative that motivates the two-stage form: an earlier version of
    this function resampled only WITHIN bucket, holding bucket composition
    fixed.  That produced CIs of literally zero width (memory_worth:
    [+4.3405, +4.3405]), because episodes inside a bucket are surface
    replications of one rule world, so almost none of the variance lives
    within a bucket.  A within-bucket-only scheme therefore understates
    uncertainty exactly as the flat n=1380 bootstrap does; it cannot
    corroborate the bucket-level CI.  `within_bucket_only_note` in the
    artifact records this so the discarded scheme is not silently dropped.
    """
    ga: Dict[str, List[float]] = {}
    gb: Dict[str, List[float]] = {}
    for (b, v), (b2, v2) in zip(pa, pb):
        assert b == b2, "stratified pairing requires aligned bucket order"
        ga.setdefault(b, []).append(v)
        gb.setdefault(b, []).append(v2)
    keys = sorted(ga)
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        num = 0.0
        den = 0
        # stage 1: buckets with replacement (the actual unit of variation)
        for _k in range(len(keys)):
            b = keys[rng.randrange(len(keys))]
            va, vb = ga[b], gb[b]
            # stage 2: episodes within the drawn bucket
            for _j in range(len(va)):
                i = rng.randrange(len(va))
                num += va[i] - vb[i]
                den += 1
        diffs.append(num / max(den, 1))
    diffs.sort()
    lo, hi = diffs[25], diffs[-26]
    return {"diff_mean": round(sum(diffs) / len(diffs), 4),
            "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
            "significant": not (lo <= 0.0 <= hi),
            "n_buckets": len(keys), "n_episodes": len(pa),
            "scheme": "two-stage cluster: buckets with replacement, then "
                      "episodes within each drawn bucket",
            "within_bucket_only_note": (
                "a within-bucket-only variant was tried first and rejected: it "
                "yields zero-width CIs because episodes in a bucket are "
                "surface replications of one rule world, so it understates "
                "uncertainty like the flat n=1380 bootstrap"),
            "label": label}


def bootstrap_p_centered(pa: Sequence[Tuple[str, float]],
                         pb: Sequence[Tuple[str, float]],
                         n_boot: int = 2000, seed: int = 20260818) -> float:
    """Two-sided bootstrap p against a CENTERED null, at the bucket unit.

    This is the estimator `tools/l3_stat_robustness.py:107` uses, reproduced
    here so the two Holm families below differ only in the p definition.

    Why both are reported: `bootstrap_bucket_diff`'s `p_boot` is the tail of
    the SAME uncentered draws that produce the percentile CI, so a Holm run on
    it cannot disagree with the CI criterion -- it restates the interval with a
    multiplicity penalty rather than testing anything new.  Centering each
    bucket's paired differences before resampling builds an actual null, under
    which a small but almost perfectly sign-consistent effect (no_restore:
    -0.028 with a CI touching zero) can reject while the percentile interval
    does not.  That is the exact disagreement 31- Sec 5.3 reports, and pinning it
    to a named estimator keeps it from looking like a reporting choice.
    """
    per: Dict[str, List[float]] = {}
    for (b, v), (b2, v2) in zip(pa, pb):
        assert b == b2, "centered-null pairing requires aligned bucket order"
        per.setdefault(b, []).append(v - v2)
    keys = sorted(per)
    obs = sum(sum(per[b]) / len(per[b]) for b in keys) / len(keys)
    centered = {b: [d - sum(per[b]) / len(per[b]) for d in per[b]]
                for b in keys}
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_boot):
        acc = 0.0
        for _k in range(len(keys)):
            a = centered[keys[rng.randrange(len(keys))]]
            acc += sum(a[rng.randrange(len(a))] for _j in range(len(a))) \
                / len(a)
        if abs(acc / len(keys)) >= abs(obs):
            hits += 1
    return (hits + 1) / (n_boot + 1)


SEED_SWEEP = (20260817, 20260812, 1, 2, 3, 7, 42, 999)


def seed_robustness(pa: Sequence[Tuple[str, float]],
                    pb: Sequence[Tuple[str, float]],
                    label: str = "") -> Dict[str, any]:
    """Re-run the two-stage cluster CI across SEED_SWEEP and report how often
    it excludes zero.

    Motivation (a measured negative that changed a main-text claim): at n=14
    buckets some contrasts sit on a knife edge where the percentile lower bound
    is within ~0.01 of zero, so significance flips with the resample seed
    alone.  `storage12`/`memory_worth` is significant in 4/8 seeds while
    `keep_all` is 8/8 and `sqcad_cert` 0/8.  Reporting a single pre-registered
    seed would have made a coin-flip look like a finding, so contrasts below
    `stable_threshold` are reported as seed-fragile rather than significant.
    """
    los, sig = [], 0
    for sd in SEED_SWEEP:
        r = bootstrap_stratified_diff(pa, pb, seed=sd)
        los.append(r["ci_lo"])
        sig += bool(r["significant"])
    n = len(SEED_SWEEP)
    return {"n_seeds": n, "n_significant": sig,
            "ci_lo_min": round(min(los), 5), "ci_lo_max": round(max(los), 5),
            "seeds": list(SEED_SWEEP),
            "stable": sig == n, "seed_fragile": 0 < sig < n,
            "verdict": ("stable across every seed" if sig == n else
                        "never significant" if sig == 0 else
                        f"SEED-FRAGILE: {sig}/{n} seeds -- do not report as "
                        f"significant"),
            "label": label}


def holm_bonferroni(pvals: Dict[str, float],
                    alpha: float = 0.05) -> Dict[str, any]:
    """Holm-Bonferroni over a PRE-REGISTERED family (the five ablations).

    `pvals` may carry either p definition; the caller labels which.  See
    `bootstrap_p_centered` for why both are run.
    """
    order = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(order)
    out: Dict[str, any] = {}
    # Step-down: adjusted p is the running maximum of (m - rank) * p_raw, and a
    # test can only be rejected if every smaller-p test was also rejected.
    running = 0.0
    still_rejecting = True
    for rank, (name, p) in enumerate(order):
        running = max(running, (m - rank) * p)
        p_adj = min(1.0, running)
        if still_rejecting and p_adj > alpha:
            still_rejecting = False
        out[name] = {
            "p_raw": round(p, 6),
            "p_holm": round(p_adj, 6),
            "threshold": round(alpha / (m - rank), 6),
            "reject_at_0.05": bool(still_rejecting),
            "rank": rank + 1,
        }
    return {"family_size": m, "alpha": alpha,
            "note": ("p_raw is the two-sided bootstrap tail probability of the "
                     "opposite sign at the honest bucket-level unit count; "
                     "resolution floor is 1/n_boot"),
            "tests": out}


def bootstrap_bucket_diff(pa: Sequence[Tuple[str, float]],
                          pb: Sequence[Tuple[str, float]],
                          n_boot: int = 2000, seed: int = 20260817,
                          label: str = "") -> Dict[str, any]:
    """Paired bootstrap over bucket means.  Both policies share the same
    episode set, hence the same bucket key set; pairing is exact."""
    ma, mb = _bucket_means(pa), _bucket_means(pb)
    keys = sorted(ma)
    assert keys == sorted(mb), "bucket keys differ"
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(len(keys)) for _ in range(len(keys))]
        da = sum(ma[keys[i]] for i in idx) / len(idx)
        db = sum(mb[keys[i]] for i in idx) / len(idx)
        diffs.append(da - db)
    diffs.sort()
    lo, hi = diffs[25], diffs[-26]
    # Two-sided bootstrap tail of the opposite sign, for the Holm family below.
    # Floor at 1/n_boot: the bootstrap cannot resolve a smaller tail, so
    # reporting 0 would claim precision the resample count does not carry.
    n_opp = sum(1 for d in diffs if d <= 0.0) if sum(diffs) > 0 else \
        sum(1 for d in diffs if d >= 0.0)
    p_boot = min(1.0, max(1.0 / n_boot, 2.0 * n_opp / n_boot))
    return {"diff_mean": round(sum(diffs) / len(diffs), 4),
            "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
            "significant": not (lo <= 0.0 <= hi),
            "p_boot": round(p_boot, 6),
            "n_buckets": len(keys),
            "distinct_per_bucket": {b: len({v for _, v in pa if b == _})
                                    for b in keys},
            "label": label}


# ---------------------------------------------------------------------------
# ablation attribution (defer path cost)
# ---------------------------------------------------------------------------
def run_v2_ablations(episodes, hidden) -> Dict[str, any]:
    out = {}
    for name, fn in V2_POLICIES.items():
        out[name] = {}
        for cfg_name, cfg in ABLATIONS.items():
            vals = []
            for ep in episodes:
                a = fn(ep)
                v = branch_value(ep, a, cfg)
                out_o = hidden[ep.world.episode_id]
                best = max(out_o.lifecycle_value_keep,
                           out_o.lifecycle_value_archive)
                vals.append({"value": round(v, 4),
                             "regret": round(best - v, 4)})
            n = len(vals)
            out[name][cfg_name] = {
                "mean_value": round(sum(x["value"] for x in vals) / n, 4),
                "mean_regret": round(sum(x["regret"] for x in vals) / n, 4),
                "values": [x["value"] for x in vals],
            }
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()

    eps = cached_episodes(RESULTS / "episodes.pkl")
    hidden = {}
    for ep in eps:
        out, _ = outcome_of(ep)
        hidden[ep.world.episode_id] = out
    print(f"episodes: {len(eps)}")

    fam = run_v2_family(eps, hidden)

    ep_by_id = {ep.world.episode_id: ep for ep in eps}

    # reference rows for bootstrap comparison (frozen, already audited)
    # G-8(2): memory_worth / keep_all had NO paired CI artifact anywhere in the
    # tree, yet the main text claimed SQCAD "significantly outperforms all
    # score-only baselines".  They are added here so every significance claim
    # can point at an artifact; `sqcad_cert_conflict` is the lineage-fix row and
    # already carried one.
    frozen_rows = {name: [] for name in
                   ("probe_willing", "sqcad_cert", "sqcad_cert_conflict",
                    "memory_worth", "keep_all")}
    for name, fn in DECISION_POLICIES.items():
        if name not in frozen_rows:
            continue
        for ep in eps:
            a = fn(ep)
            frozen_rows[name].append({
                "episode_id": ep.world.episode_id,
                "action": a,
                "value": branch_value(ep, a),
            })

    def values_of(name: str) -> List[float]:
        if name in fam:
            return [r["value"] for r in fam[name]["rows"]]
        return [r["value"] for r in frozen_rows[name]]

    def bucket_pairs_of(name: str) -> List[Tuple[str, float]]:
        if name in fam:
            return [(r["bucket"], r["value"]) for r in fam[name]["rows"]]
        return [(BUCKET_KEY(ep_by_id[r["episode_id"]]), r["value"])
                for r in frozen_rows[name]]

    # bootstrap: paired on episode_id (round-1 report: episodes are surface
    # replications; bucket-level pairing below is the honest unit)
    boot = {}
    for ref, base in (("sqcad_v2", "probe_willing"),
                      ("sqcad_v2", "sqcad_cert"),
                      ("sqcad_v2", "sqcad_cert_conflict"),
                      ("sqcad_v2", "memory_worth"),
                      ("sqcad_v2", "keep_all"),
                      ("sqcad_v2_probe", "sqcad_v2")):
        boot[f"{ref}-{base}"] = bootstrap_diff(values_of(ref),
                                               values_of(base))
    boot["sqcad_v2-vs-probe_willing_sanity"] = boot["sqcad_v2-probe_willing"]

    # ablation attribution: defer path under each follow-on switch
    abl = run_v2_ablations(eps, hidden)
    for cfg_name in ABLATIONS:
        boot[f"sqcad_v2-no_{cfg_name}"] = bootstrap_diff(
            values_of("sqcad_v2"), abl["sqcad_v2"][cfg_name]["values"])
        boot[f"sqcad_v2_probe-no_{cfg_name}"] = bootstrap_diff(
            values_of("sqcad_v2_probe"),
            abl["sqcad_v2_probe"][cfg_name]["values"])

    # honest units: bootstrap over the ~14 rule-world instantiations
    boot_bucket = {}
    for ref, base in (("sqcad_v2", "probe_willing"),
                      ("sqcad_v2", "sqcad_cert"),
                      ("sqcad_v2", "sqcad_cert_conflict"),
                      ("sqcad_v2", "memory_worth"),
                      ("sqcad_v2", "keep_all"),
                      ("sqcad_v2_probe", "sqcad_v2")):
        boot_bucket[f"{ref}-{base}"] = bootstrap_bucket_diff(
            bucket_pairs_of(ref), bucket_pairs_of(base),
            label=f"{ref}-{base}")
    for cfg_name in ABLATIONS:
        boot_bucket[f"sqcad_v2-no_{cfg_name}"] = bootstrap_bucket_diff(
            bucket_pairs_of("sqcad_v2"),
            [(BUCKET_KEY(ep), v) for ep, v in
             zip(eps, abl["sqcad_v2"][cfg_name]["values"])],
            label=f"sqcad_v2-no_{cfg_name}")

    # G-8(3): stratified episode-level bootstrap (bucket = random effect),
    # reported ALONGSIDE the bucket-level CI so the reader can see the
    # conclusion does not depend on the resampling scheme.
    boot_strat = {}
    for ref, base in (("sqcad_v2", "sqcad_cert"),
                      ("sqcad_v2", "memory_worth"),
                      ("sqcad_v2", "keep_all")):
        boot_strat[f"{ref}-{base}"] = bootstrap_stratified_diff(
            bucket_pairs_of(ref), bucket_pairs_of(base),
            label=f"{ref}-{base}")
    for cfg_name in ABLATIONS:
        boot_strat[f"sqcad_v2-no_{cfg_name}"] = bootstrap_stratified_diff(
            bucket_pairs_of("sqcad_v2"),
            [(BUCKET_KEY(ep), v) for ep, v in
             zip(eps, abl["sqcad_v2"][cfg_name]["values"])],
            label=f"sqcad_v2-no_{cfg_name}")

    # Seed robustness over every baseline the main text calls significant, plus
    # the ablation family.  See `seed_robustness`: this is what demoted the
    # storage12/memory_worth contrast from "significant" to "seed-fragile".
    seed_rob = {}
    for name in ("keep_all", "memory_worth", "sqcad_cert",
                 "sqcad_cert_conflict"):
        seed_rob[f"sqcad_v2-{name}"] = seed_robustness(
            bucket_pairs_of("sqcad_v2"), bucket_pairs_of(name),
            label=f"sqcad_v2-{name}")
    for cfg_name in ABLATIONS:
        seed_rob[f"sqcad_v2-no_{cfg_name}"] = seed_robustness(
            bucket_pairs_of("sqcad_v2"),
            [(BUCKET_KEY(ep), v) for ep, v in
             zip(eps, abl["sqcad_v2"][cfg_name]["values"])],
            label=f"sqcad_v2-no_{cfg_name}")

    # Holm-Bonferroni over the PRE-REGISTERED five-ablation family, at the
    # honest bucket-level unit count, under BOTH p definitions.  They disagree,
    # and the disagreement is the reportable content: see bootstrap_p_centered.
    holm = holm_bonferroni({
        c: boot_bucket[f"sqcad_v2-no_{c}"]["p_boot"] for c in ABLATIONS})
    holm["p_definition"] = ("tail of the same uncentered draws as the "
                            "percentile CI -- cannot disagree with the CI "
                            "criterion by construction")
    holm_centered = holm_bonferroni({
        c: bootstrap_p_centered(
            bucket_pairs_of("sqcad_v2"),
            [(BUCKET_KEY(ep), v) for ep, v in
             zip(eps, abl["sqcad_v2"][c]["values"])])
        for c in ABLATIONS})
    holm_centered["p_definition"] = (
        "centered-null bootstrap at the bucket unit (the estimator of "
        "tools/l3_stat_robustness.py:107); this is the criterion under which "
        "the small sign-consistent probe/restore effects reject while their "
        "percentile CIs still touch zero")

    table = {}
    for b in sorted({r["bucket"] for r in fam["sqcad_v2"]["rows"]}):
        table[b] = {}
        for name in ("sqcad_v2", "sqcad_v2_probe", "probe_willing",
                     "sqcad_cert_conflict", "sqcad_cert",
                     "memory_worth", "keep_all"):
            if name in fam:
                vals = [r["value"] for r in fam[name]["rows"]
                        if r["bucket"] == b]
            else:
                vals = [r["value"] for r in frozen_rows[name]
                        if BUCKET_KEY(ep_by_id[r["episode_id"]]) == b]
            table[b][name] = round(sum(vals) / len(vals), 4) if vals else None

    payload = {"family": fam, "bootstrap": boot, "ablations": abl,
               "per_bucket": table, "bootstrap_bucket": boot_bucket,
               "bootstrap_stratified": boot_strat,
               "holm_ablation_family": holm,
               "holm_ablation_family_centered": holm_centered,
               "seed_robustness": seed_rob,
               "unit_note": ("PRIMARY unit is the bucket (rule-world "
                             "instantiation, n~14). The flat n=1380 episode "
                             "bootstrap is retained for continuity but "
                             "overstates precision, since episodes within a "
                             "bucket are surface replications of one rule "
                             "world. bootstrap_stratified resamples episodes "
                             "WITHIN bucket as a third view. Holm is applied "
                             "to the five-ablation family at bucket level.")}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"wrote {args.out}")

    # ---- console markdown tables ----
    print("\n## L3 theory-aligned summary")
    print("| policy | value | regret | abstention | abst.prec | commit.prec |"
          " unauthorized | safe-commit | missed | recovery | ttr |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for name in ("sqcad_v2", "sqcad_v2_probe"):
        s = fam[name]
        print(f"| {name} | {s['mean_value']} | {s['mean_regret']} | "
              f"{s['abstention_rate']} | {s['abstention_precision']} | "
              f"{s['commit_precision']} | {s['unauthorized_commit']} | "
              f"{s['authorized_safe_commit']} | {s['missed_commit_rate']} | "
              f"{s['recovery_rate']} | {s['mean_time_to_recovery']} |")

    print("\n## bootstrap (mean diff, 95% CI; sig = CI excludes 0)")
    for k, v in boot.items():
        if k.endswith("_sanity"):
            continue
        print(f"| {k} | {v['diff_mean']:.4f} [{v['ci_lo']:.4f}, "
              f"{v['ci_hi']:.4f}] sig={v['significant']} |")

    print("\n## bootstrap BUCKET-LEVEL (n = rule-world instantiations; "
          "honest units)")
    for k, v in boot_bucket.items():
        print(f"| {k} | {v['diff_mean']:.4f} [{v['ci_lo']:.4f}, "
              f"{v['ci_hi']:.4f}] sig={v['significant']} "
              f"(n_buckets={v['n_buckets']}) |")

    print("\n## ablations (mean value)")
    for name, cfgs in abl.items():
        line = " | ".join(f"{k}={v['mean_value']}" for k, v in cfgs.items())
        print(f"| {name} | {line} |")

    print("\n## per-bucket value")
    hdr = "| bucket | " + " | ".join(
        ["sqcad_v2", "sqcad_v2_probe", "probe_willing",
         "sqcad_cert_conflict", "sqcad_cert"]) + " |"
    print(hdr)
    print("|" + "---|" * 6)
    for b, row in table.items():
        vals = " | ".join(str(row[c]) if row[c] is not None else "-"
                          for c in ["sqcad_v2", "sqcad_v2_probe",
                                    "probe_willing", "sqcad_cert_conflict",
                                    "sqcad_cert"])
        print(f"| {b} | {vals} |")


if __name__ == "__main__":
    main()
