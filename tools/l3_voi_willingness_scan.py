"""L3 crossing-interval VOI willingness scan (round-5 supplement, 34-).

Extends the 33- sqcad_v2_probe row (keep iff crossing interval & the
candidate is rare = single public session & no negative evidence) with a
willingness sweep over how many public sessions a crossing-interval
memory may have and still be kept (probed) rather than deferred-archived:
  sqcad_v2_w1  -- 33- sqcad_v2_probe (recomputed as a zero-diff check)
  sqcad_v2_w2  -- keep iff crossing & session_hits <= 2 & no negative
  sqcad_v2_w3  -- keep iff crossing & session_hits <= 3 & no negative
Higher willingness = more crossing-interval commits = the probe/restore
path is exercised more; the sweep traces the value/cost frontier of the
VOI decision on the FROZEN 1380 episodes (frozen data, new policy rows
only -- the bench itself is untouched).

Reports per row: mean value/regret, abstention/commit breakdown, event
metrics, and bucket-level paired bootstrap vs the frozen sqcad_cert row
(n_boot=2000, seed=20260817 -- honest units, per 33- §3.2).

Usage (PYTHONPATH=src, from the repo root):
  python tools/l3_voi_willingness_scan.py --out \
      remote_results/lifecycle_audit/l3_voi_willingness_scan.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from sqcad.lifecycle_bench.audit import cached_episodes, outcome_of
from sqcad.lifecycle_bench.baselines import (
    BUCKET_KEY, DECISION_POLICIES, branch_value,
)
from sqcad.lifecycle_bench.world import (
    NEGATIVE, POSITIVE, UNRESOLVED, reference_certificate, simulate_branch,
)

from l3_sqcad_v2 import (
    CONFLICT_REASONS, NEG_REASONS, cert_of, event_metrics, session_hits,
    summarize_v2,
)

OUT_DEFAULT = Path("remote_results/lifecycle_audit/l3_voi_willingness_scan.json")
N_BOOT = 2000
SEED = 20260817


def make_willingness(k: int) -> Callable[[object], str]:
    def p_w(ep) -> str:
        c = cert_of(ep)
        if c.status is POSITIVE:
            return "keep"
        if c.status is UNRESOLVED:
            if session_hits(ep) <= k and not c.reason.startswith(NEG_REASONS) \
                    and not c.reason.startswith(CONFLICT_REASONS):
                return "keep"
        return "archive"
    p_w.__name__ = f"sqcad_v2_w{k}"
    return p_w


POLICIES: Dict[str, Callable[[object], str]] = {
    "sqcad_v2_w1": make_willingness(1),
    "sqcad_v2_w2": make_willingness(2),
    "sqcad_v2_w3": make_willingness(3),
}


def run_family(episodes: List, hidden: Dict[str, object]) -> Dict[str, dict]:
    fam: dict = {}
    for name, fn in POLICIES.items():
        rows = []
        for ep in episodes:
            out = hidden[ep.world.episode_id]
            a = fn(ep)
            v = branch_value(ep, a)
            best = max(out.lifecycle_value_keep, out.lifecycle_value_archive)
            roll = simulate_branch(ep, a)
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


def bucket_diff(pa: Sequence[Tuple[str, float]],
                pb: Sequence[Tuple[str, float]]) -> Dict[str, any]:
    """Paired bootstrap over bucket means (identical bucket key sets)."""
    def means(pairs):
        acc = {}
        for b, v in pairs:
            acc.setdefault(b, []).append(v)
        return {b: sum(vs) / len(vs) for b, vs in acc.items()}

    ma, mb = means(pa), means(pb)
    keys = sorted(ma)
    assert keys == sorted(mb), "bucket keys differ"
    rng = random.Random(SEED)
    diffs = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(len(keys)) for _ in range(len(keys))]
        da = sum(ma[keys[i]] for i in idx) / len(idx)
        db = sum(mb[keys[i]] for i in idx) / len(idx)
        diffs.append(da - db)
    diffs.sort()
    lo, hi = diffs[25], diffs[-26]
    return {"diff_mean": round(sum(diffs) / len(diffs), 4),
            "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
            "significant": not (lo <= 0.0 <= hi),
            "n_buckets": len(keys), "n_boot": N_BOOT, "seed": SEED}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()

    episodes = cached_episodes()
    hidden = {ep.world.episode_id: outcome_of(ep)[0] for ep in episodes}
    print(f"episodes: {len(episodes)}")

    fam = run_family(episodes, hidden)
    payload: dict = {
        "config": {
            "n_boot": N_BOOT, "seed": SEED, "method": "bucket-paired",
            "note": ("crossing-interval willingness sweep on the frozen "
                     "1380 episodes; w1 = 33- sqcad_v2_probe (zero-diff "
                     "check)"),
        },
        "policies": {name: {k: v for k, v in d.items() if k != "rows"}
                     for name, d in fam.items()},
    }

    # bucket-level paired diffs vs the frozen sqcad_cert row
    cert_rows = {ep.world.episode_id: None for ep in episodes}
    cert_vals: Dict[str, List[Tuple[str, float]]] = {}
    for name, fn in DECISION_POLICIES.items():
        if "cert" not in name:
            continue
        vals = []
        for ep in episodes:
            a = fn(ep)
            v = branch_value(ep, a)
            vals.append((BUCKET_KEY(ep), round(v, 4)))
        cert_vals[name] = vals
    # choose the frozen sqcad_cert row by name match
    ref_name = next((n for n in cert_vals if "sqcad_cert" in n), None)
    if ref_name is None:
        ref_name = next(iter(cert_vals))
    payload["vs_frozen"] = {"ref": ref_name}
    for name, d in fam.items():
        pa = [(r["bucket"], r["value"]) for r in d["rows"]]
        payload["vs_frozen"][name] = bucket_diff(pa, cert_vals[ref_name])
        print(f"  {name} vs {ref_name}: "
              f"{payload['vs_frozen'][name]['diff_mean']:+.4f} "
              f"[{payload['vs_frozen'][name]['ci_lo']:+.4f}, "
              f"{payload['vs_frozen'][name]['ci_hi']:+.4f}]"
              f"{' *' if payload['vs_frozen'][name]['significant'] else ''}")

    for name, d in fam.items():
        s = {k: v for k, v in d.items() if k != "rows"}
        print(f"== {name}: {s}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
