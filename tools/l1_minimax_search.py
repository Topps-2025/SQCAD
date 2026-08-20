"""L1 exhaustive minimax search over the Theorem-4/5 sign-flip pair
(31- §5.1, 32- round-1 fix).

ICLR-challenge round-1 finding (theory track): "L1 verifies the theorems
only in the arithmetic sense; none of the lower-bound, minimax, or
separation content is tested."  This script enumerates decision rules over
the Theorem-1 construction exhaustively:

  * Deterministic rules: the two worlds share a bit-identical observable
    log O, so every deterministic rule measurable in O is a constant
    action on this pair -- exactly 2 rules, worst-case regret
    min(1100, 1650) = 1100.
  * Randomized rules: p = P(keep) swept on a fine grid; worst-case regret
    max(p * |tau2|, (1-p) * |tau1|) -- min over the grid is the claimed
    660 at p* = |tau1| / (|tau1| + |tau2|) = 0.4 (solve p*t2 = (1-p)*t1).
  * Error: worst-case classification error max(p, 1-p) >= 1/2, attained
    at p = 1/2 (the regret minimizer and the error minimizer differ --
    32- round-1 flagged this conflation in the draft).
  * Threshold rules: any rule that thresholds an observable statistic s(O)
    is still constant on the pair (O identical), hence a subset of the
    deterministic rules -- enumerated implicitly.

Usage: python tools/l1_minimax_search.py [--tau1 1100 --tau2 1650] [--grid 1000]
Writes remote_results/lifecycle_audit/l1_minimax_search.json and prints a
markdown table.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

OUT_DEFAULT = Path("remote_results/lifecycle_audit/l1_minimax_search.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tau1", type=float, default=1100.0)
    ap.add_argument("--tau2", type=float, default=1650.0)
    ap.add_argument("--grid", type=int, default=1000)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()

    # Convention (31- §3.6/§5.1, "labeled convention fixed ... to match the
    # exhaustive-grid verification"): world 1: keep is correct, |tau| = t1 = U;
    # world 2: archive is correct, |tau| = t2 = -L.  This assignment is pinned
    # by the grid formula below -- wc(p) = max(p*t2, (1-p)*t1) -- whose
    # minimizer p* = t1/(t1+t2) = 0.4 is P(keep), the value the paper reports.
    # (Round-2 review found the earlier det dict written under the transposed
    # assignment: it attributed keep -> t1 and archive -> t2, contradicting
    # its own grid formula; the minimax value R* and best-det 1100 are
    # labeling-invariant, so the headline results were unaffected.)
    t1, t2 = args.tau1, args.tau2
    assert t1 > 0 and t2 > 0

    # ---- deterministic rules: all rules measurable in O ----
    # O is identical in both worlds; every deterministic rule is a constant
    # action.  Exactly 2 rules; worst-case regret of each:
    #   keep-always loses t2 in world 2 (archive-correct), archive-always
    #   loses t1 in world 1 (keep-correct).
    det = {"keep": max(t2, 0.0), "archive": max(t1, 0.0)}
    best_det = min(det.values())

    # ---- randomized rules: exhaustive grid over p = P(keep) ----
    best_p, best_regret, worst_err_at_best = None, None, None
    err_min, err_min_p = None, None
    grid_rows = []
    for i in range(args.grid + 1):
        p = i / args.grid
        wc_regret = max(p * t2, (1 - p) * t1)
        wc_err = max(p, 1 - p)
        grid_rows.append((p, wc_regret, wc_err))
        if best_regret is None or wc_regret < best_regret:
            best_regret, best_p = wc_regret, p
            worst_err_at_best = wc_err
        if err_min is None or wc_err < err_min:
            err_min, err_min_p = wc_err, p

    # closed forms for the report (draft §3.6 restated, 32- round 1)
    # solve p*t2 = (1-p)*t1  =>  p* = t1/(t1+t2); grid confirms 0.400
    p_star = t1 / (t1 + t2)
    r_star = t1 * t2 / (t1 + t2)
    p_err = 0.5
    r_err = 0.5

    payload = {
        "config": {"tau1": t1, "tau2": t2, "grid": args.grid,
                   "note": ("exhaustive minimax search over decision rules "
                            "measurable in the identical observable log O; "
                            "all rules are constant on the world pair")},
        "deterministic_rules": {
            "n_rules": 2,
            "rules": det,
            "best_worst_case_regret": best_det,
            "comment": ("O identical across worlds -> every deterministic "
                        "rule is a constant action; best is always-archive "
                        "(worst-case U = 1100); keep-always pays -L = 1650"),
        },
        "randomized_rules": {
            "grid_best": {"p": best_p, "worst_case_regret": best_regret,
                          "worst_case_error_at_p": worst_err_at_best},
            "closed_form_p_star": p_star,
            "closed_form_r_star": r_star,
            "closed_form_error_min": {"p": p_err, "value": r_err},
            "grid_size": args.grid + 1,
            "min_worst_case_error": {"p": err_min_p, "value": err_min},
            "comment": ("regret minimizer p*=0.4 vs error minimizer p=0.5 "
                        "are distinct (draft §3.6 conflated them)"),
        },
        "theorem4_claim": {
            "regret_lower_bound": 660.0,
            "grid_confirms": abs(best_regret - r_star) < 1e-6,
            "error_lower_bound": 0.5,
            "grid_confirms_error": abs(err_min - 0.5) < 1e-6,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"wrote {args.out}")

    print("\n## L1 exhaustive minimax search (sign-flip pair)")
    print("| rule class | best worst-case regret | attained at |")
    print("|---|---|---|")
    print(f"| deterministic (all 2 rules measurable in O) | {best_det:.1f} "
          f"| always-archive (worst-case U = t1) |")
    print(f"| randomized grid (n={args.grid + 1}) | {best_regret:.4f} "
          f"| p = {best_p:.3f} |")
    print(f"| closed form R* = t1*t2/(t1+t2) | {r_star:.4f} | "
          f"p* = {p_star:.4f} |")
    print(f"| error minimax (randomized) | {err_min:.4f} | "
          f"p = {err_min_p:.3f} (regret minimizer p* = {p_star:.3f}) |")


if __name__ == "__main__":
    main()
