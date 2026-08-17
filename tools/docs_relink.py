# -*- coding: utf-8 -*-
"""One-shot docs reorganization tool: move files per MOVE_RULES (git mv) and
rewrite all relative links / `docs/...` path references accordingly.

Usage: python tools/docs_relink.py [--dry-run] [--no-move]
"""
import os
import re
import subprocess
import sys
import posixpath

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs")

# (old_prefix, new_prefix) relative to repo root, longest prefix wins.
# File-level rules must appear before their containing directory rules.
MOVE_RULES = [
    # docs_zn -> docs_cn / 自用 (exact-file rules first)
    ("docs/docs_zn/03-核心问题与框架设计/07-Introduction规范稿.md",
     "docs/自用/02-历史草稿/05-论文写作/07-Introduction规范稿-final-20260807.md"),
    ("docs/docs_zn/05-论文写作/07-Introduction规范稿.md",
     "docs/自用/02-历史草稿/05-论文写作/07-Introduction规范稿-revised-20260811.md"),
    ("docs/docs_zn/03-核心问题与框架设计/归档-旧版草稿-20260806/",
     "docs/自用/02-历史草稿/归档-旧版草稿-20260806/"),
    ("docs/docs_zn/01-研究理念/", "docs/docs_cn/01-研究理念/"),
    ("docs/docs_zn/02-现有工作与痛点/", "docs/docs_cn/02-现有工作与痛点/"),
    ("docs/docs_zn/03-核心问题与框架设计/", "docs/docs_cn/03-核心问题与框架设计/"),
    ("docs/docs_zn/04-数据与实验/", "docs/自用/02-历史草稿/04-数据与实验-旧版/"),
    ("docs/docs_zn/05-论文写作/", "docs/自用/02-历史草稿/05-论文写作/"),
    ("docs/docs_zn/06-当前进度与后续实验/", "docs/自用/02-历史草稿/06-当前进度与后续实验-旧版/"),
    ("docs/docs_zn/07-杂项草稿与实验记录/", "docs/自用/02-历史草稿/07-杂项草稿与实验记录/"),
    ("docs/docs_zn/00-研究总图.md", "docs/docs_cn/00-研究总图.md"),
    # 草稿-draft -> 自用 (A-class files first)
    ("docs/草稿-draft/实验方案与基线/21-资格证书与价值信息访问控制方案-20260817.md",
     "docs/自用/00-论文主体/21-资格证书与价值信息访问控制方案-20260817.md"),
    ("docs/草稿-draft/实验方案与基线/22-SQCAD-LifecycleBench数据集构建方案-20260817.md",
     "docs/自用/00-论文主体/22-SQCAD-LifecycleBench数据集构建方案-20260817.md"),
    ("docs/草稿-draft/实验方案与基线/23-SQCAD完整实验方案-理论公开自建消融-20260817.md",
     "docs/自用/00-论文主体/23-SQCAD完整实验方案-理论公开自建消融-20260817.md"),
    ("docs/草稿-draft/实验方案与基线/", "docs/自用/02-历史草稿/实验方案与基线/"),
    ("docs/草稿-draft/实验报告/", "docs/自用/02-历史草稿/实验报告/"),
    ("docs/草稿-draft/研究路线与方案/", "docs/自用/01-research-gap/研究路线与方案/"),
    ("docs/草稿-draft/项目进度与索引/02-论文主体草稿与证据文档分类-20260817.md",
     "docs/自用/00-论文主体/02-论文主体草稿与证据文档分类-20260817.md"),
    ("docs/草稿-draft/项目进度与索引/", "docs/自用/02-历史草稿/项目进度与索引/"),
    ("docs/草稿-draft/写作目录旧入口归档-20260813/", "docs/自用/02-历史草稿/写作目录旧入口归档-20260813/"),
    # top-level dirs
    ("docs/实验证据链/", "docs/自用/03-实验证据链/"),
    ("docs/研究逻辑与理论证明/", "docs/自用/01-research-gap/研究逻辑与理论证明/"),
]

RULES = sorted(MOVE_RULES, key=lambda r: len(r[0]), reverse=True)


def relink_path(p: str) -> str:
    """Map an old repo-root-relative path to its new location (unchanged if no rule)."""
    for old, new in RULES:
        if p.startswith(old):
            return new + p[len(old):]
    return p


def list_docs_files():
    out = []
    for root, _dirs, files in os.walk(DOCS):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), REPO).replace("\\", "/")
            out.append(rel)
    # root README / DATA_STORAGE are also processed for references
    for f in ("README.md", "DATA_STORAGE.md"):
        if os.path.exists(os.path.join(REPO, f)):
            out.append(f)
    return sorted(out)


def git_mv(old_abs: str, new_rel: str):
    new_abs = os.path.join(REPO, new_rel)
    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
    rel_old = os.path.relpath(old_abs, REPO).replace("\\", "/")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel_old],
        capture_output=True,
    ).returncode == 0
    if tracked:
        subprocess.run(["git", "mv", old_abs, new_abs], check=True, capture_output=True)
    else:
        os.rename(old_abs, new_abs)


def run_move(files, dry_run):
    plan = [(f, relink_path(f)) for f in files]
    moved = [(o, n) for o, n in plan if o != n]
    missing_src = []
    for o, n in moved:
        if not os.path.exists(os.path.join(REPO, o)):
            missing_src.append(o)
    if missing_src:
        print("WARN: source missing (skip):")
        for m in missing_src:
            print("  ", m)
        moved = [(o, n) for o, n in moved if o not in missing_src]
    if dry_run:
        print(f"[dry-run] would move {len(moved)} files:")
        for o, n in moved[:20]:
            print(f"  {o}  ->  {n}")
        if len(moved) > 20:
            print(f"  ... and {len(moved)-20} more")
        return moved
    print(f"moving {len(moved)} files (git mv) ...")
    for i, (o, n) in enumerate(moved, 1):
        if i % 20 == 0 or i == len(moved):
            print(f"  {i}/{len(moved)}")
        git_mv(os.path.join(REPO, o), n)
    return moved


MD_LINK_RE = re.compile(r"\]\(([^()\s<>]+)(?:\s+[^)]*)?\)")
TEXT_PATH_RE = re.compile(r"docs/[^\s`，。；）]+")


# 多源合并目录（00-论文主体）中无法由规则反推旧位置的文件
REVERSE_OVERRIDES = {
    "docs/自用/00-论文主体/21-教师汇报完整实验链路与文档导航-20260817.md":
        "docs/实验证据链/21-教师汇报完整实验链路与文档导航-20260817.md",
}


def reverse_lookup(new_path: str) -> str:
    """Map a current repo-root-relative path back to its pre-reorg location
    (the baseline the file's links were written against)."""
    if new_path in REVERSE_OVERRIDES:
        return REVERSE_OVERRIDES[new_path]
    for old, new in RULES:
        if new_path.startswith(new):
            return old + new_path[len(new):]
    return new_path


def rewrite_md(path_rel, dry_run):
    """Rewrite links in one md file. Links were written relative to the OLD
    location; rewrite them to be relative to the NEW location."""
    abs_path = os.path.join(REPO, path_rel)
    with open(abs_path, encoding="utf-8") as f:
        text = f.read()
    old_path = reverse_lookup(path_rel)
    old_dir = posixpath.dirname(old_path)
    new_dir = posixpath.dirname(path_rel)

    rewrites = 0
    warnings = []

    def fix_link(m):
        nonlocal rewrites
        target = m.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        anchor = ""
        if "#" in target:
            target, anchor = target.rsplit("#", 1)
        if not target:
            return m.group(0)
        # resolve relative to old file location -> docs-root-relative
        abs_tgt = posixpath.normpath(posixpath.join(old_dir, target))
        new_tgt = relink_path(abs_tgt)
        if new_tgt == abs_tgt:
            # not moved: keep as-is (even if broken before, do not touch)
            return m.group(0)
        rel = posixpath.relpath(new_tgt, new_dir)
        if anchor:
            rel += "#" + anchor
        rewrites += 1
        return "](" + rel + ")"

    def fix_text(m):
        nonlocal rewrites
        seg = m.group(0)
        new_seg = relink_path(seg)
        if new_seg != seg:
            rewrites += 1
            return new_seg
        return seg

    text2 = MD_LINK_RE.sub(fix_link, text)
    text2 = TEXT_PATH_RE.sub(fix_text, text2)

    if text2 != text and not dry_run:
        with open(abs_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text2)
    return rewrites, warnings


def main():
    dry_run = "--dry-run" in sys.argv
    no_move = "--no-move" in sys.argv
    files = list_docs_files()
    file_map = {f: relink_path(f) for f in files}

    moved = []
    if not no_move:
        moved = run_move(files, dry_run)
    else:
        print("skip move (--no-move)")
        moved = [(o, relink_path(o)) for o in files if o != relink_path(o)]

    # after moving, resolve new paths of md files
    md_files = []
    for root, _dirs, fs in os.walk(DOCS):
        for f in fs:
            if f.endswith(".md"):
                rel = os.path.relpath(os.path.join(root, f), REPO).replace("\\", "/")
                md_files.append(rel)
    for f in ("README.md", "DATA_STORAGE.md"):
        if os.path.exists(os.path.join(REPO, f)):
            md_files.append(f)

    total_rewrites = 0
    print(f"rewriting links in {len(md_files)} md files ...")
    for mf in sorted(md_files):
        rw, warns = rewrite_md(mf, dry_run)
        total_rewrites += rw
        for w in warns:
            print("  WARN:", mf, w)
    print(f"done: {total_rewrites} link/path rewrites ({'dry-run' if dry_run else 'applied'})")


if __name__ == "__main__":
    main()
