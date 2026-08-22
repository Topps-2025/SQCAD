"""Run the small constructive baseline-internal lifecycle-gap audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqcad.baseline_internal_gap_audit import compact_summary, write_audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=Path("results/baseline_internal_lifecycle_gap_audit_20260822.json"))
    parser.add_argument("--control-pairs", type=int, default=4)
    parser.add_argument("--score-digits", type=int, default=8)
    args = parser.parse_args()
    result = write_audit(args.output, score_digits=args.score_digits,
                         control_pairs=args.control_pairs)
    print(json.dumps(compact_summary(result), ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

