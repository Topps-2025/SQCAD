"""Build the SQCAD-LifecycleBench MVP dataset (doc 22- 10).

Usage:
    python tools/build_lifecycle_bench.py [out_dir]

Default out_dir: results/lifecycle_bench/
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "results", "lifecycle_bench")
    from sqcad.lifecycle_bench.generator import build_dataset
    manifest = build_dataset(out_dir)
    counts = manifest["counts"]
    print(f"[lifecycle-bench] {counts['total']} episodes -> {out_dir}")
    print(f"  main={counts['main']}  pair_episodes={counts['pair_episodes']}")
    print("  oracle per family:")
    for fam, dist in counts["oracle"].items():
        print(f"    {fam}: " + ", ".join(f"{a}={n}" for a, n in dist.items()))
    for split in ("train", "dev", "test"):
        n = sum(1 for s in manifest["splits"].values() if s == split)
        print(f"  split {split}: {n} episodes")


if __name__ == "__main__":
    main()
