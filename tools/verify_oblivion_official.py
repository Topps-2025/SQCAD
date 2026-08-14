"""Official-code verification of Oblivion (frozen commit b2512f9, NEC
proprietary license -- run in place on the D-drive snapshot, NOT
redistributed).

What runs on this machine right now:

1. The pure-stdlib decay math (`src/oblivion/memory/decayer/decay_utils.py`)
   executes VERBATIM (the module's only imports are TYPE_CHECKING-only) on
   synthetic memory stand-ins carrying `decay_curve_score`; its aggregation
   semantics (mean/variance over semantic + preemptive-episodic memories,
   None for empty, variance 0 for a single score) are asserted exactly.
2. The environment blockers for the full offline unit suite are recorded
   precisely: pyproject requires Python >=3.12,<3.15 (local frozen envs are
   3.10), and qdrant-client/omegaconf/instructor/tiktoken/tenacity/cbor2/
   pyjwt/aiohttp are absent with network downloads blocked -- so the
   `pytest -m "not llm"` suite is deferred to environment availability.
3. SHA-256 of the audited files goes into the reproduction registry.

The LLM tiers (uncertainty assessment, structured client) and the Qdrant
store remain `not reproduced (endpoint/deps blocked)`; the verified surface
narrows what still needs endpoints, per audit 15- section 4.5.

Usage (any python, no deps):
  python tools/verify_oblivion_official.py \
      --oblivion D:/Engineering/SQCAD/database/upstream/baselines/Oblivion \
      --out results/oblivion_official_verification.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class _SemanticMemory:
    def __init__(self, score):
        self.decay_curve_score = score


class _EpisodicMemory:
    def __init__(self, score):
        self.decay_curve_score = score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oblivion", type=Path,
                        default=Path("D:/Engineering/SQCAD/database/"
                                     "upstream/baselines/Oblivion"))
    parser.add_argument("--out", type=Path,
                        default=Path("results/"
                                     "oblivion_official_verification.json"))
    args = parser.parse_args()

    decay_utils = args.oblivion / "src/oblivion/memory/decayer/decay_utils.py"
    decayer = args.oblivion / "src/oblivion/memory/decayer/decayer.py"
    pyproject = args.oblivion / "pyproject.toml"
    if not decay_utils.exists():
        print(f"official decay_utils.py missing at {decay_utils}")
        return 1

    # ---- 1. verbatim execution of the pure decay math ----
    spec = importlib.util.spec_from_file_location("oblivion_decay_utils",
                                                  decay_utils)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    s2 = _SemanticMemory(0.2)
    s8 = _SemanticMemory(0.8)
    e5 = _EpisodicMemory(0.5)

    results = {}
    results["empty"] = mod.compute_cluster_decay_stats([], [])
    assert results["empty"] == (None, None)
    results["single"] = mod.compute_cluster_decay_stats([s2], [])
    assert abs(results["single"][0] - 0.2) < 1e-12
    assert results["single"][1] == 0.0
    results["mixed"] = mod.compute_cluster_decay_stats([s2, s8], [e5])
    mean_mixed = (0.2 + 0.8 + 0.5) / 3
    var_mixed = ((0.2 - mean_mixed) ** 2 + (0.8 - mean_mixed) ** 2
                 + (0.5 - mean_mixed) ** 2) / 3
    assert abs(results["mixed"][0] - mean_mixed) < 1e-12
    assert abs(results["mixed"][1] - var_mixed) < 1e-12
    results["mean_only"] = mod.compute_decay_mean([s2, s8], [e5])
    assert abs(results["mean_only"] - mean_mixed) < 1e-12
    results["variance_only"] = mod.compute_decay_variance([s2, s8], [e5])
    assert abs(results["variance_only"] - var_mixed) < 1e-12

    report = {
        "official_commit": "b2512f9 (Releasing Oblivion code base)",
        "license": "proprietary NEC Laboratories Europe GmbH -- snapshot "
                   "audited in place on the D-drive database only, not "
                   "redistributed",
        "verified_surface": {
            "decay_math_verbatim": {
                "file": str(decay_utils),
                "sha256": _sha256(decay_utils),
                "functions_executed": ["compute_cluster_decay_stats",
                                       "compute_decay_mean",
                                       "compute_decay_variance"],
                "assertions": {
                    "empty_cluster_returns_none": True,
                    "single_score_variance_is_zero": True,
                    "mixed_mean_exact": True,
                    "mixed_variance_exact": True,
                },
                "semantics": "aggregates decay_curve_score over semantic + "
                             "preemptive episodic memories; executor-"
                             "authoritative decay aggregation feeding the "
                             "activation threshold",
            },
        },
        "environment_blockers": {
            "python_requirement": ">=3.12,<3.15 (pyproject.toml); frozen "
                                  "local envs are 3.10",
            "missing_deps": ["qdrant-client", "omegaconf", "instructor",
                             "tiktoken", "tenacity", "cbor2", "pyjwt",
                             "aiohttp"],
            "network": "pip/hf downloads blocked by proxy",
            "deferred": "offline unit suite `pytest -m \"not llm\"` and the "
                        "default-route heuristic activation path need the "
                        "3.12+ env; LLM uncertainty/Qdrant tiers stay not "
                        "reproduced until endpoints/deps exist",
        },
        "sha256": {
            str(decay_utils): _sha256(decay_utils),
            str(decayer): _sha256(decayer),
            str(pyproject): _sha256(pyproject),
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("decay math verbatim execution: all assertions passed")
    print(json.dumps(report["environment_blockers"], indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
