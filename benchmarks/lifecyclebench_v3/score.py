"""Score a keep/archive controller against the frozen LifecycleBench-v3 contract.

A submission is a JSON or JSONL file mapping ``episode_id`` to an action in
{"keep", "archive"}.  Either shape works::

    {"v3-hitchhiker-default-johnu076522-2026082600": "archive", ...}
    {"episode_id": "v3-...-2026082600", "action": "archive"}   # one per line

Scoring uses the frozen paired rollout values in ``hidden.jsonl`` only, so a
controller never needs -- and must never read -- the hidden file itself.

Usage::

    python score.py --actions my_controller.json
    python score.py --actions my_controller.json --by-family
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ACTIONS = ("keep", "archive")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_actions(path: Path) -> dict[str, str]:
    """Accept a flat id->action mapping, a JSONL stream, or a list of records."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(f"{path} is empty")

    records: list[dict[str, Any]]
    try:
        blob = json.loads(text)
    except json.JSONDecodeError:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        if isinstance(blob, dict) and all(isinstance(v, str) for v in blob.values()):
            return {str(k): v.strip().lower() for k, v in blob.items()}
        if isinstance(blob, dict):
            records = [blob]
        elif isinstance(blob, list):
            records = blob
        else:
            raise SystemExit(f"{path}: unsupported submission shape")

    out: dict[str, str] = {}
    for row in records:
        eid = row.get("episode_id")
        action = row.get("action")
        if eid is None or action is None:
            raise SystemExit(f"{path}: record missing episode_id/action: {row!r}")
        out[str(eid)] = str(action).strip().lower()
    return out


def family_cluster_ci(
    per_family: dict[str, list[float]],
    n_boot: int = 2000,
    seed: int = 20260826,
) -> tuple[float, float]:
    """Percentile CI resampling whole mechanism families, not single worlds.

    Worlds inside a family share a generator, so the family is the independent
    cluster; resampling worlds would understate the interval.
    """
    families = sorted(per_family)
    if len(families) < 2:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        drawn = [rng.choice(families) for _ in families]
        pooled = [v for fam in drawn for v in per_family[fam]]
        means.append(sum(pooled) / len(pooled))
    means.sort()
    lo = means[int(0.025 * (n_boot - 1))]
    hi = means[int(0.975 * (n_boot - 1))]
    return (lo, hi)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--actions", required=True, type=Path,
                    help="submission file: episode_id -> keep|archive")
    ap.add_argument("--data", type=Path, default=HERE,
                    help="directory holding hidden.jsonl (default: this directory)")
    ap.add_argument("--by-family", action="store_true",
                    help="also print a per-mechanism-family breakdown")
    ap.add_argument("--json-out", type=Path, default=None,
                    help="write the full metric block to this path")
    args = ap.parse_args()

    hidden = {row["episode_id"]: row for row in read_jsonl(args.data / "hidden.jsonl")}
    actions = load_actions(args.actions)

    missing = sorted(set(hidden) - set(actions))
    unknown = sorted(set(actions) - set(hidden))
    if unknown:
        raise SystemExit(
            f"{len(unknown)} unknown episode_id(s), first: {unknown[0]}")
    if missing:
        raise SystemExit(
            f"submission covers {len(actions)}/{len(hidden)} worlds; "
            f"{len(missing)} missing, first: {missing[0]}. "
            "Partial submissions are not scored -- the inferential unit is the "
            "world signature and dropping worlds changes the estimand.")

    bad = {eid: a for eid, a in actions.items() if a not in ACTIONS}
    if bad:
        eid, act = next(iter(bad.items()))
        raise SystemExit(f"action must be keep or archive; got {act!r} for {eid}")

    values: list[float] = []
    regrets: list[float] = []
    false_commits: list[float] = []
    missed_commits: list[float] = []
    recoverable: list[float] = []
    scope_rows: list[float] = []
    per_family_value: dict[str, list[float]] = {}
    per_family_regret: dict[str, list[float]] = {}
    fam_rows: dict[str, list[tuple[float, float]]] = {}

    scope_families = {"scope_mismatch", "version_update"}

    for eid, row in hidden.items():
        action = actions[eid]
        v_keep = float(row["lifecycle_value_keep"])
        v_archive = float(row["lifecycle_value_archive"])
        oracle = str(row["oracle_action"])
        family = str(row["family"])

        value = v_keep if action == "keep" else v_archive
        regret = max(v_keep, v_archive) - value

        values.append(value)
        regrets.append(regret)
        false_commits.append(1.0 if action == "keep" and oracle == "archive" else 0.0)
        missed_commits.append(1.0 if action == "archive" and oracle == "keep" else 0.0)
        # keep is trivially still available; archive counts only when the frozen
        # branch says the item could actually be rescued at budget.
        recoverable.append(1.0 if action == "keep"
                           else (1.0 if row.get("rescue_possible") else 0.0))
        if family in scope_families:
            scope_rows.append(1.0 if action == oracle else 0.0)

        per_family_value.setdefault(family, []).append(value)
        per_family_regret.setdefault(family, []).append(regret)
        fam_rows.setdefault(family, []).append((value, regret))

    n = len(values)
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    v_lo, v_hi = family_cluster_ci(per_family_value)
    r_lo, r_hi = family_cluster_ci(per_family_regret)

    report = {
        "n_worlds": n,
        "n_families": len(per_family_value),
        "mean_value": mean(values),
        "mean_value_ci95": [v_lo, v_hi],
        "mean_regret": mean(regrets),
        "mean_regret_ci95": [r_lo, r_hi],
        "false_commit_rate": mean(false_commits),
        "missed_commit_rate": mean(missed_commits),
        "recoverability_at_budget": mean(recoverable),
        "scope_version_correctness": mean(scope_rows) if scope_rows else None,
        "scope_version_n_worlds": len(scope_rows),
        "keep_rate": mean([1.0 if actions[e] == "keep" else 0.0 for e in hidden]),
        "bootstrap": "family-cluster percentile, 2000 draws, seed 20260826",
    }

    print(f"worlds            {n} across {report['n_families']} families")
    print(f"mean value        {report['mean_value']:+.4f}  "
          f"[{v_lo:+.4f}, {v_hi:+.4f}]")
    print(f"mean regret       {report['mean_regret']:.4f}  "
          f"[{r_lo:.4f}, {r_hi:.4f}]   (lower is better)")
    print(f"false commit      {report['false_commit_rate']:.4f}   "
          f"(kept when archive was right)")
    print(f"missed commit     {report['missed_commit_rate']:.4f}   "
          f"(archived when keep was right)")
    print(f"recoverability    {report['recoverability_at_budget']:.4f}")
    if scope_rows:
        print(f"scope/version     {report['scope_version_correctness']:.4f}   "
              f"(on {len(scope_rows)} scoped worlds)")
    print(f"keep rate         {report['keep_rate']:.4f}")

    if args.by_family:
        print("\nper family:")
        for fam in sorted(fam_rows):
            rows = fam_rows[fam]
            print(f"  {fam:22s} n={len(rows):3d}  "
                  f"value={mean([v for v, _ in rows]):+8.4f}  "
                  f"regret={mean([r for _, r in rows]):8.4f}")
        report["per_family"] = {
            fam: {
                "n_worlds": len(rows),
                "mean_value": mean([v for v, _ in rows]),
                "mean_regret": mean([r for _, r in rows]),
            }
            for fam, rows in sorted(fam_rows.items())
        }

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
