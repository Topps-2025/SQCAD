"""Auditable registry for SQCAD benchmark and baseline reproduction assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_DATABASE_ROOT = Path(r"D:\Engineering\SQCAD\database")


@dataclass(frozen=True)
class RepositorySpec:
    name: str
    category: str
    relative_path: str
    remote: str
    expected_commit: str
    expected_identity: str
    identity_markers: tuple[str, ...]
    role: str


@dataclass(frozen=True)
class AssetSpec:
    name: str
    relative_path: str
    expected_sha256: str | None
    source: str
    role: str
    required_stage: str


REPOSITORIES = (
    RepositorySpec(
        "LongMemEval", "benchmark", "upstream/benchmarks/LongMemEval",
        "https://github.com/xiaowu0162/LongMemEval.git",
        "9e0b455f4ef0e2ab8f2e582289761153549043fc", "confirmed",
        ("LongMemEval", "longmemeval-cleaned"),
        "official benchmark, data protocol, retrieval and QA evaluators",
    ),
    RepositorySpec(
        "LoCoMo", "benchmark", "upstream/benchmarks/LoCoMo",
        "https://github.com/snap-research/locomo.git",
        "3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376", "confirmed",
        ("LoCoMo", "very long-term conversational memory"),
        "official longitudinal conversation benchmark and evaluator",
    ),
    RepositorySpec(
        "GoodAI-LTM", "benchmark", "upstream/benchmarks/GoodAI-LTM",
        "https://github.com/GoodAI/goodai-ltm-benchmark.git",
        "188e7618413775f1ce783763d5ee0b5ccd4c31c9", "confirmed",
        ("GoodAI LTM Benchmark", "memory over very long conversations"),
        "official dynamic benchmark and published benchmark artifacts",
    ),
    RepositorySpec(
        "MemoryAgentBench", "benchmark", "upstream/benchmarks/MemoryAgentBench",
        "https://github.com/HUST-AI-HYZ/MemoryAgentBench.git",
        "455306dcabc3842526eb83cd4e225e5d486c5c5d", "confirmed",
        ("MemoryAgentBench", "incremental multi-turn"),
        "coverage benchmark for retrieval, learning and selective forgetting",
    ),
    RepositorySpec(
        "Oblivion", "baseline", "upstream/baselines/Oblivion",
        "https://github.com/nec-research/oblivion.git",
        "b2512f9ce3bba9f33a76055e20f41d698ea90e46", "confirmed",
        ("Self-Adaptive Agentic Memory Control", "Decay-Driven Activation"),
        "closest accessibility-decay governance baseline",
    ),
    RepositorySpec(
        "SimpleMem", "baseline", "upstream/baselines/SimpleMem",
        "https://github.com/aiming-lab/SimpleMem.git",
        "db80b6a7c591e0ea730a058e9f5fc4eb06572299", "confirmed",
        ("SimpleMem", "lifelong memory"),
        "latest engineering branch; not used as the original paper result",
    ),
    RepositorySpec(
        "SimpleMem-paper-release", "baseline", "upstream/baselines/SimpleMem-paper-release",
        "https://github.com/aiming-lab/SimpleMem.git",
        "16912523f6f0de10c01f7701cdbb79d8fa4f5280", "confirmed",
        ("SimpleMem", "Reproduce Paper Results", "GPT-4.1-mini", "Qwen3-Embedding-0.6B"),
        "original paper-release candidate used for LoCoMo reproduction",
    ),
    RepositorySpec(
        "FadeMem-name-collision", "rejected-baseline", "upstream/baselines/FadeMem",
        "https://github.com/aniki-ly/FadeMem.git",
        "15b70ce9704d45ccbefd3a4a2991a966bfa4feb7", "mismatch",
        ("Autoregressive Video Diffusion", "arXiv-2606.10671"),
        "name collision: video-diffusion KV memory, not Agent Memory forgetting",
    ),
)


ASSETS = (
    AssetSpec(
        "LongMemEval-S-cleaned", "datasets/LongMemEval/longmemeval_s_cleaned.json",
        "D6F21EA9D60A0D56F34A05B609C79C88A451D2AE03597821EA3D5A9678C3A442",
        "xiaowu0162/longmemeval-cleaned", "public benchmark small split", "P0",
    ),
    AssetSpec(
        "LongMemEval-Oracle", "datasets/LongMemEval/longmemeval_oracle.json",
        "821A2034D219AB45846873DD14C14F12CFE7776E73527A483F9DAC095D38620C",
        "xiaowu0162/longmemeval-cleaned", "diagnostic oracle upper bound", "P0",
    ),
    AssetSpec(
        "LongMemEval-M-cleaned", "datasets/LongMemEval/longmemeval_m_cleaned.json",
        None, "xiaowu0162/longmemeval-cleaned", "public benchmark medium split", "P1",
    ),
    AssetSpec(
        "LoCoMo-local", "datasets/LoCoMo/locomo10.json",
        "79FA87E90F04081343B8C8DEBECB80A9A6842B76A7AA537DC9FDF651EA698FF4",
        "snap-research/locomo-derived-local-copy", "public longitudinal benchmark", "P0",
    ),
    AssetSpec(
        "LoCoMo-upstream-repository-copy", "upstream/benchmarks/LoCoMo/data/locomo10.json",
        "553CD5A15E25F2CECCC6ED185221EBA645080C93E5B91087560A91AA5961F365",
        "snap-research/locomo@3eb6f2c", "canonical repository comparison copy", "P0",
    ),
    AssetSpec(
        "Gate-A-200-template", "datasets/GateA/longmemeval_semantic_gate_a_200.jsonl",
        "7C987647C56055512C2BB9219F5020396320E5103C0EB4B61EB2A54287EF4D5C",
        "SQCAD deterministic packet builder", "annotation template, not gold", "P1",
    ),
    AssetSpec(
        "Gate-A-POS-regex-predictions", "results/gate_a/predictions_pos_regex_baseline.jsonl",
        "D73D43C3EAF353F324DF215E8F67C66983F065311124AC68B9417649D19ED3D9",
        "SQCAD POS/regex negative control", "controlled baseline output", "P1",
    ),
)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def git(path: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args], check=True, capture_output=True, text=True,
            encoding="utf-8", errors="strict",
        )
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return None
    return completed.stdout.strip()


def read_identity_text(path: Path) -> str:
    for name in ("README.md", "README.MD", "pyproject.toml"):
        candidate = path / name
        if candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="strict")
    return ""


def audit_repository(root: Path, spec: RepositorySpec) -> dict[str, object]:
    path = root / Path(spec.relative_path)
    exists = path.is_dir() and (path / ".git").is_dir()
    head = git(path, "rev-parse", "HEAD") if exists else None
    remote = git(path, "remote", "get-url", "origin") if exists else None
    porcelain = git(path, "status", "--porcelain") if exists else None
    tracked_text = git(path, "ls-files") if exists else None
    identity_text = read_identity_text(path) if exists else ""
    markers_found = [marker for marker in spec.identity_markers if marker.lower() in identity_text.lower()]
    checks = {
        "exists": exists,
        "commit_matches": head == spec.expected_commit,
        "remote_matches": remote == spec.remote,
        "clean_worktree": porcelain == "",
        "identity_markers_complete": len(markers_found) == len(spec.identity_markers),
    }
    return {
        **asdict(spec), "absolute_path": str(path), "head": head, "origin": remote,
        "tracked_files": len(tracked_text.splitlines()) if tracked_text else 0,
        "markers_found": markers_found, "checks": checks, "verified": all(checks.values()),
    }


def audit_asset(root: Path, spec: AssetSpec) -> dict[str, object]:
    path = root / Path(spec.relative_path)
    exists = path.is_file()
    actual_hash = sha256_file(path) if exists else None
    hash_matches = exists and (spec.expected_sha256 is None or actual_hash == spec.expected_sha256)
    return {
        **asdict(spec), "absolute_path": str(path), "exists": exists,
        "bytes": path.stat().st_size if exists else None, "actual_sha256": actual_hash,
        "hash_matches": hash_matches, "verified": bool(exists and hash_matches),
    }


def build_manifest(root: Path) -> dict[str, object]:
    repositories = [audit_repository(root, spec) for spec in REPOSITORIES]
    assets = [audit_asset(root, spec) for spec in ASSETS]
    missing = [item["name"] for item in assets if not item["exists"]]
    mismatched = [item["name"] for item in assets if item["exists"] and not item["hash_matches"]]
    return {
        "schema": "sqcad-reproduction-registry.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_root": str(root),
        "repositories": repositories, "assets": assets,
        "summary": {
            "repositories_verified": sum(bool(item["verified"]) for item in repositories),
            "repositories_total": len(repositories),
            "assets_verified": sum(bool(item["verified"]) for item in assets),
            "assets_total": len(assets), "missing_assets": missing,
            "hash_mismatches": mismatched,
        },
    }


def write_manifest(manifest: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-root", type=Path, default=Path(os.getenv("SQCAD_DATABASE_ROOT", DEFAULT_DATABASE_ROOT)))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="Return non-zero if a P0 asset or repository check fails.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.database_root.resolve()
    manifest = build_manifest(root)
    output = args.output or root / "manifests" / "reproduction_registry_v2.json"
    write_manifest(manifest, output)
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    if args.strict:
        repository_failure = any(not item["verified"] and item["category"] != "rejected-baseline" for item in manifest["repositories"])
        p0_failure = any(item["required_stage"] == "P0" and not item["verified"] for item in manifest["assets"])
        return int(repository_failure or p0_failure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
