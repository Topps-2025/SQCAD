"""Readable summary of the public-data unified contract results (doc 16).

Prints, per dataset: the main policy table (hit / recall / tokens / storage /
lifecycle), the chronological-mask accounting, the pre-registered paired
bootstrap verdicts (sqcad vs every R1/R2 row and vs its ablations), and the
quality-cost Pareto ordering.

Usage:
  PYTHONPATH=src python tools/summarize_public_contract.py \
      --input results/public_unified_contract.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqcad.public_unified_contract import (
    METRIC_KEYS, R1_POLICIES, R2_POLICIES, SQCAD_ABLATIONS,
)

HIGHER_BETTER = {"hit_rate", "recall_mean", "rare_recall", "ku_recall"}


def _fmt(v):
    return "   -  " if v is None else f"{v:7.3f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path,
                        default=Path("results/public_unified_contract.json"))
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))

    for ds, ds_out in data["datasets"].items():
        print(f"\n{'=' * 78}\n== {ds}  ({ds_out['n_traces']} traces) ==")
        if ds_out.get("mask"):
            print("  chronological mask:", ds_out["mask"])
        rows = ds_out["policies"]
        order = [p for p in
                 tuple(R1_POLICIES) + tuple(R2_POLICIES) + ("sqcad",)
                 + tuple(SQCAD_ABLATIONS)
                 if p in rows and not rows[p].get("skipped")]
        print(f"\n  {'policy':36s} {'hit':>7s} {'recall':>7s} "
              f"{'tokens':>7s} {'storage':>8s} {'rare':>7s} {'ku':>7s} "
              f"{'probes':>7s} {'restores':>8s} {'archives':>8s}")
        for p in order:
            a = rows[p]
            lm = a["lifecycle_mean"]
            print(f"  {p:36s} {_fmt(a['hit_rate']['mean'])} "
                  f"{_fmt(a['recall_mean']['mean'])} "
                  f"{_fmt(a['tokens_mean']['mean'])} "
                  f"{_fmt(a['storage_tokens']['mean'])} "
                  f"{_fmt(a['rare_recall']['mean'])} "
                  f"{_fmt(a['ku_recall']['mean'])} "
                  f"{lm['probes']:7.1f} {lm['restores']:8.1f} "
                  f"{lm['archives']:8.1f}")
        for p, entry in rows.items():
            if entry.get("skipped"):
                print(f"  {p:36s} SKIPPED")

        print("\n  significance (paired bootstrap, studentized, n_boot="
              f"{data['config']['n_boot']}, seed={data['config']['boot_seed']}):")
        for metric in METRIC_KEYS:
            sig = ds_out["significance"][metric]
            print(f"\n  -- {metric} " +
                  ("(higher is better)" if metric in HIGHER_BETTER
                   else "(lower is better)"))
            for pair, ci in sig.items():
                if ci.get("mean") is None:
                    continue
                star = "*" if ci.get("significant") else " "
                print(f"   {star} {pair:42s} diff={ci['mean']:8.4f} "
                      f"CI=[{ci['ci_low']:8.4f}, {ci['ci_high']:8.4f}] "
                      f"(n={ci.get('n_seeds', '-')})")


if __name__ == "__main__":
    main()
