"""Post-conversion validation: $ pairing, residual plain formulas, block-formula placement.

Usage:  PYTHONIOENCODING=utf-8 python tools/validate_md_formulas.py
Prints per-file issues; exit code 0 if clean, 1 otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MARKS = re.compile(r"[αβγδεθτσΣ∑∏∫√≈≠≤≥×−∈Θ→↦·±∞∂λρφΦΨκ]")
# math-expression leftovers that should have been wrapped
PLAIN_FUNC = re.compile(r"\bR\*|V_s\^|Σᵢ|O\(1/|min\{|\bE\[[A-Za-z]|argmin|qρ|α·|β·|γ·|η·")


def check_file(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        txt = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        return [f"  read error: {e}"]
    lines = txt.splitlines()
    n_dollar = txt.count("$")
    if n_dollar % 2 != 0:
        issues.append(f"  ODD $ COUNT ({n_dollar})")
    # $ on a single line must come in pairs on that line (MathJax inline)
    for i, ln in enumerate(lines, 1):
        if ln.count("$") % 2 != 0 and "$$" not in ln:
            issues.append(f"  line {i}: odd $ on line: {ln.strip()[:70]}")
        if "$$" in ln and ln.strip() != "$$" and not ln.strip().startswith("$$") and not ln.strip().endswith("$$"):
            # $$ not alone on its line (GitHub renders poorly) -> report unless full-inline pair
            if ln.strip().count("$$") != 2 or ln.strip().startswith("$$") is False:
                issues.append(f"  line {i}: $$ not block-alone: {ln.strip()[:70]}")
        if "$" not in ln and MARKS.search(ln):
            m = MARKS.search(ln)
            issues.append(f"  line {i}: unwrapped mark {m.group(0)!r}: {ln.strip()[:70]}")
        if "$" not in ln and PLAIN_FUNC.search(ln):
            issues.append(f"  line {i}: unwrapped expr: {ln.strip()[:70]}")
    # unbalanced { } inside $$ blocks (rough check)
    for m in re.finditer(r"\$\$(.*?)\$\$", txt, flags=re.S):
        body = m.group(1)
        if body.count("{") != body.count("}"):
            issues.append(f"  unbalanced braces in $$ block: {body[:60]}")
    return issues


def main() -> int:
    mds = sorted(REPO.glob("docs/**/*.md")) + [REPO / "README.md"]
    n_bad = 0
    for f in mds:
        issues = check_file(f)
        if issues:
            n_bad += 1
            print(f"## {f.relative_to(REPO)}")
            for it in issues:
                print(it)
    print(f"\n{len(mds)} files checked; {n_bad} with issues")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
