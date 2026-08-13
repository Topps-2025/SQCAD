"""Gate 5: four-piece freeze manifest (代码—配置—结果—报告).

Generates a DETERMINISTIC SHA-256 manifest over:

  code    -- src/sqcad/*.py and tests/*.py (the implementation);
  config  -- the frozen contract registry: seeds / steps / budget /
             probe budget / cost coefficients / thresholds / evaluator
             constants, plus byte hashes of the two frozen real-data files
             (LongMemEval S, LoCoMo) on the external database;
  results -- the evidence result JSONs under results/ (gitignored, synced
             to the D-drive database);
  reports -- docs/实验证据链/*.md (the evidence-chain reports, including
             this gate's report 08).

No timestamps, no absolute paths, sorted file lists: the manifest is
byte-identical on every regeneration from the same tree.  An aggregate
hash chains the four pieces, so a change in any piece breaks the chain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List

# ---------------------------------------------------------------------------
# Frozen contract registry (must match the experiment code; the report
# cross-checks constants against the registry at freeze time)
# ---------------------------------------------------------------------------

CONTRACT_REGISTRY: Dict[str, Any] = {
    "unified_contract": {
        "seeds": 30,
        "steps_per_seed": 100,
        "workspace_budget": 12,
        "group_noise": 0.2,
        "write_order_shuffle": "random.Random(seed * 7919 + 17)",
        "stream_check": "SHA-256 over the candidate stream, identical for "
                        "all policies within a seed block",
        "evaluator": "required-hit utility; stale exposure penalty 0.35 "
                     "per stale step; rare-critical recall over rare ids",
        "thresholds": {
            "semantic_confidence": 0.75,
            "harm_veto_item_effect": -0.25,
            "unidentified_lcb": -1e5,
        },
        "main_table_policies": 18,
        "not_transportable": ["sage", "memaudit", "gatemem"],
    },
    "cost_contract": {
        "gamma": 0.99,
        "lam_tok": 0.001,
        "lam_llm": 0.0,          # LLM layer not reproduced -- no fictional price
        "lam_probe": 0.05,
        "lam_lat": 0.002,
        "rho_harm": 0.35,
        "rho_ff": 0.25,
        "probe_budget": 8,
        "seeds": 10,
        "steps_per_seed": 100,
        "workspace_budget": 12,
        "unidentified_harm_p": 0.75,
        "variant_world": "75% of stale items become unidentified "
                         "(deterministic per seed: "
                         "random.Random(seed * 104729 + 31))",
        "regimes": {
            "default": "as above",
            "risk_averse": {"rho_harm": 1.0},
            "capacity": {"lam_tok": 0.01},
            "latency": {"lam_lat": 0.02},
        },
    },
    "protocol_estimator": {
        "estimand": "persistent-access lifecycle value V_s^pi(a) = "
                    "E^pi[sum_t gamma^(t-1)(Y_t - lam C_t - rho R_t) "
                    "| do(A_i^pers=a), s]",
        "rct_rollout": "randomized persistent action; H=150 steps "
                       "(identification_recovery full config)",
        "gate3_world": "WorldConfig(seed=s, n_trajectories=100, "
                       "n_oracle=150, n_epochs=80) per seed",
        "bootstrap": {
            "sampling_unit": "seed (world realization), paired across "
                             "policies on the shared stream",
            "n_boot": 2000,
            "boot_seed": 20260812,
            "method": "nonparametric percentile; paired resampling of "
                      "the same seed indices across policies",
        },
    },
    "frozen_data": {
        "LongMemEval_S": "D:/Engineering/SQCAD/database/datasets/"
                         "LongMemEval/longmemeval_s_cleaned.json",
        "LoCoMo": "D:/Engineering/SQCAD/database/datasets/LoCoMo/"
                  "locomo10.json",
        "note": "external database, never committed; byte hashes recorded "
                "below",
    },
}

# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def file_entry(path: Path) -> Dict[str, str]:
    return {"path": path.as_posix(), "sha256": sha256_file(path)}


def _sorted_files(root: Path, pattern: str) -> List[Path]:
    return sorted(root.glob(pattern))


def code_manifest(repo: Path) -> Dict[str, Any]:
    files = (_sorted_files(repo / "src" / "sqcad", "*.py")
             + _sorted_files(repo / "tests", "*.py"))
    entries = [file_entry(f) for f in files]
    return {"piece": "code", "n_files": len(entries), "files": entries}


def _database_root() -> Path:
    env = os.environ.get("SQCAD_DATABASE")
    return Path(env) if env else Path("D:/Engineering/SQCAD/database")


def config_manifest(repo: Path, database: Optional[Path] = None) -> Dict[str, Any]:
    """Registry + real-data byte hashes (fail hard if a frozen dataset is
    missing -- the freeze is meaningless without the data it froze)."""
    reg = json.loads(json.dumps(CONTRACT_REGISTRY))  # deep copy
    root = database or _database_root()
    for key, rel in (("LongMemEval_S",
                      "datasets/LongMemEval/longmemeval_s_cleaned.json"),
                     ("LoCoMo", "datasets/LoCoMo/locomo10.json")):
        p = root / rel
        if not p.exists():
            raise FileNotFoundError(
                f"frozen dataset missing: {p} -- freeze aborted")
        reg["frozen_data"][key] = {
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
        }
    return {"piece": "config", "registry": reg}


def results_manifest(repo: Path) -> Dict[str, Any]:
    results_dir = repo / "results"
    files = sorted(
        p for p in results_dir.glob("*.json")
        if p.name not in ("bootstrap_ci_smoke.json", "freeze_manifest.json"))
    entries = [file_entry(f) for f in files]
    return {"piece": "results", "n_files": len(entries), "files": entries}


def reports_manifest(repo: Path) -> Dict[str, Any]:
    files = sorted((repo / "docs" / "实验证据链").glob("*.md"))
    entries = [file_entry(f) for f in files]
    return {"piece": "reports", "n_files": len(entries), "files": entries}


def build_manifest(repo: Path,
                   database: Optional[Path] = None) -> Dict[str, Any]:
    pieces = {
        p["piece"]: p for p in (
            code_manifest(repo), config_manifest(repo, database),
            results_manifest(repo), reports_manifest(repo))
    }
    chain = sha256_bytes(json.dumps(
        pieces, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return {
        "piece": "aggregate",
        "schema": "sqcad-freeze-manifest v1",
        "aggregate_sha256": chain,
        "pieces": pieces,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path,
                        default=Path("results/freeze_manifest.json"))
    args = parser.parse_args()

    manifest = build_manifest(args.repo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8")
    counts = {k: v.get("n_files", "registry") for k, v in manifest["pieces"].items()}
    print(json.dumps({
        "aggregate_sha256": manifest["aggregate_sha256"],
        "files_per_piece": counts,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
