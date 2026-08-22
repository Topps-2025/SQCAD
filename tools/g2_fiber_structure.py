"""G-2 companion diagnostic: separate lifecycle-completeness from fiber starvation.

A surface reporting zero opposite-sign fibers has NOT been shown
lifecycle-complete if almost every fiber is a singleton.  A witness needs TWO
rows sharing one fiber, so a score fine enough to separate every row cannot be
contradicted by construction.  Reading that as "complete" is a false negative,
which is exactly the error the G-2 harness warns about for a zero-row artifact.

This prints the coverage denominator next to each verdict: how many fibers are
non-trivial, and how many rows live in a fiber that could host a witness at all.
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    path = sys.argv[1]
    d = json.load(open(path, encoding="utf-8"))
    caps = d["caps"]
    print("dataset={} rows={} cap={} budget={}".format(
        d["dataset"], d["n_rows_total"], caps["max_candidates_per_trace"],
        caps["workspace_budget"]))
    print("primary_contrast={}".format(d.get("primary_contrast", "?")))
    print()
    cols = ("surface", "fibers", "nontriv", "singl%", "testable_rows", "opp",
            "eps_lc", "branch")
    hdr = "{:20s} {:>6s} {:>7s} {:>7s} {:>13s} {:>4s} {:>8s}  {}".format(*cols)
    print(hdr)
    print("-" * len(hdr))
    starved = []
    for name, v in d["per_surface"].items():
        n_fib = v["n_fibers"]
        n_non = v["n_nontrivial_fibers"]
        n_row = v["n_rows"]
        singletons = n_fib - n_non
        # rows that share a fiber with at least one other row
        testable = n_row - singletons
        pct = 100.0 * singletons / max(n_fib, 1)
        print("{:20s} {:6d} {:7d} {:6.1f}% {:13d} {:4d} {:8.4f}  {}".format(
            name, n_fib, n_non, pct, testable,
            v["n_opposite_sign_fibers"], v["epsilon_lc"], v["branch"]))
        if v["n_opposite_sign_fibers"] == 0 and testable < 0.2 * n_row:
            starved.append(name)
    print()
    if starved:
        print("FIBER-STARVED (zero-witness result is uninformative, NOT a "
              "completeness finding): " + ", ".join(starved))
    else:
        print("No surface is fiber-starved: every zero-witness verdict rests "
              "on a fiber population that could have carried a witness.")

    # Witness thinness: how many DISTINCT rows can play the archive side.  If it
    # is one, the branch verdict rests on a single episode and must be reported
    # as such rather than as a rate.
    supports = {}
    for name, v in d["per_surface"].items():
        ws = v.get("witness_support")
        if ws:
            supports[name] = (ws["n_distinct_keep_rows"],
                              ws["n_distinct_archive_rows"],
                              ws.get("archive_side_rows", []))
    if supports:
        print()
        print("witness support (distinct rows per side):")
        for name, (k, a, rows) in supports.items():
            print("  {:20s} keep={:4d} archive={:3d} archive_rows={}".format(
                name, k, a, rows))
    else:
        print()
        print("witness_support absent from this artifact (predates the field); "
              "rerun the harness to record archive-side row identity.")


if __name__ == "__main__":
    main()
