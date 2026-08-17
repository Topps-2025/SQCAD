"""Official scoring harness for SQCAD-LifecycleBench predictions (R7).

A policy submits one line per episode:
    <episode_id>,keep | archive
(csv with a header, or JSONL {"id": ..., "action": ...}).

The scorer matches against the maintainer-side hidden labels (the honest
counterfactual values from doc 22- 5.4) and reports:

  * mean lifecycle value of the chosen branch (discounted, frozen contract);
  * mean regret vs. the best branch;
  * oracle agreement (over non-neutral episodes);
  * false-commit / missed-commit rates.

The submitted predictions are scored on the chosen branch values
``lifecycle_value_keep`` / ``lifecycle_value_archive`` recorded in
hidden.jsonl, so the scorer needs NO simulator -- it is a pure table
lookup, keeping the release package self-contained.

Usage:
  python tools/score_lifecycle_predictions.py --predictions preds.csv \
      --hidden results/lifecycle_bench/hidden.jsonl --out score.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--hidden", default="results/lifecycle_bench/hidden.jsonl")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    hidden = {}
    for line in Path(args.hidden).read_text(encoding="utf-8").splitlines():
        h = json.loads(line)
        hidden[h["episode_id"]] = h

    preds = {}
    p = Path(args.predictions)
    if p.suffix.lower() == ".jsonl":
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            preds[r["id"]] = r["action"]
    else:
        with open(p, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                key = row.get("episode_id") or row.get("id")
                preds[key] = (row["action"]).strip().lower()

    missing = [k for k in preds if k not in hidden]
    if missing:
        raise SystemExit(f"unknown episode ids: {missing[:5]}")

    rows = []
    for pid, action in preds.items():
        labels = hidden[pid]["labels"]
        if action not in ("keep", "archive"):
            raise SystemExit(f"bad action {action!r} for {pid}")
        val = labels["lifecycle_value_keep"] if action == "keep" \
            else labels["lifecycle_value_archive"]
        best = max(labels["lifecycle_value_keep"],
                   labels["lifecycle_value_archive"])
        rows.append({
            "episode_id": pid, "action": action,
            "value": val, "regret": best - val,
            "oracle": labels["oracle_action"],
            "false_commit": action == "keep"
                            and labels["oracle_action"] == "archive",
            "missed_commit": action == "archive"
                             and labels["oracle_action"] == "keep",
            "agreement": action == labels["oracle_action"],
        })

    n = len(rows)
    nn = n - sum(1 for r in rows
                 if r["oracle"] == "neutral")
    report = {
        "n": n,
        "mean_value": round(sum(r["value"] for r in rows) / n, 4),
        "mean_regret": round(sum(r["regret"] for r in rows) / n, 4),
        "oracle_agreement": round(
            sum(1 for r in rows if r["agreement"]) / nn, 4) if nn else None,
        "false_commit_rate": round(
            sum(1 for r in rows if r["false_commit"]) / n, 4),
        "missed_commit_rate": round(
            sum(1 for r in rows if r["missed_commit"]) / n, 4),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
