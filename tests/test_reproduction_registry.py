from pathlib import Path
import hashlib
import subprocess

from sqcad.reproduction_registry import AssetSpec, RepositorySpec, audit_asset, audit_repository, build_manifest


def test_asset_hash_and_missing_asset(tmp_path: Path) -> None:
    asset = tmp_path / "datasets" / "sample.txt"
    asset.parent.mkdir(parents=True)
    asset.write_text("可复现数据\n", encoding="utf-8")
    expected = hashlib.sha256(asset.read_bytes()).hexdigest().upper()
    good = AssetSpec("sample", "datasets/sample.txt", expected, "test", "fixture", "P0")
    missing = AssetSpec("missing", "datasets/missing.txt", None, "test", "fixture", "P1")
    assert audit_asset(tmp_path, good)["verified"] is True
    assert audit_asset(tmp_path, missing)["exists"] is False


def test_repository_requires_commit_remote_cleanliness_and_identity(tmp_path: Path) -> None:
    repo = tmp_path / "upstream" / "demo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("Demo Memory Benchmark", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "https://example.test/demo.git"], cwd=repo, check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    spec = RepositorySpec("demo", "benchmark", "upstream/demo", "https://example.test/demo.git", head, "confirmed", ("Demo", "Memory Benchmark"), "fixture")
    assert audit_repository(tmp_path, spec)["verified"] is True
    (repo / "README.md").write_text("dirty", encoding="utf-8")
    assert audit_repository(tmp_path, spec)["checks"]["clean_worktree"] is False


def test_manifest_schema_uses_registry(tmp_path: Path) -> None:
    manifest = build_manifest(tmp_path)
    assert manifest["schema"] == "sqcad-reproduction-registry.v2"
    assert manifest["summary"]["repositories_total"] > 0
    assert manifest["summary"]["assets_total"] > 0
