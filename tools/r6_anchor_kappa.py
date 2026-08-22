"""R6 external human anchoring: distinct-presentation audit + Cohen's kappa.

G-10 gate (0823 plan).  The anchor export
`remote_results/lifecycle_audit/r6_anchor/anchor_cases.md` presents 28 cases,
but only 21 of them are DISTINCT presentations: 7 pairs are byte-identical
after the `## Case N` heading is stripped, because two episodes of the same
rule-world template realize the same surface text.  A judge cannot tell the
members of such a pair apart, so scoring agreement over 28 items counts 7
coin flips twice and inflates reliability.

This harness therefore:

  1. groups cases by the SHA-256 of their body text (`--cases`),
  2. verifies that every duplicate group carries one oracle label (a group
     with conflicting labels would mean the export itself is broken, and is
     reported as a hard error, not smoothed over),
  3. computes Cohen's kappa against the private oracle labels on BOTH unit
     counts, and reports the 21-unit value as PRIMARY.

The 28-unit value is emitted only so the inflation is visible; it must not be
quoted as the reliability of the anchor set.

Judge labels are read from a CSV with columns `case,judgment` where judgment
is keep/archive/neutral.  Without `--judge` the tool runs in audit-only mode
and reports the presentation structure, which is what the manuscript needs
even before a judge batch completes.

Disclosure carried in the artifact: during construction of this harness the
operator saw the oracle labels for cases 1, 2, 27 and 28, so those four are
flagged `operator_label_seen` and a kappa excluding them is also reported.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Sequence

CASES = Path("remote_results/lifecycle_audit/r6_anchor/anchor_cases.md")
LABELS = Path("remote_results/lifecycle_audit/r6_anchor/anchor_labels_private.csv")
OUT_DEFAULT = Path("remote_results/lifecycle_audit/r6_anchor/kappa.json")

CLASSES = ("keep", "archive", "neutral")
OPERATOR_SAW = (1, 2, 27, 28)

CASE_RE = re.compile(r"(?mi)^#+\s*case\s*(\d+)")


def parse_cases(path: Path) -> Dict[int, str]:
    parts = CASE_RE.split(path.read_text(encoding="utf-8"))
    return {int(parts[i]): parts[i + 1].strip()
            for i in range(1, len(parts), 2)}


def group_identical(cases: Dict[int, str]) -> List[List[int]]:
    """Group case ids by body hash.  Returns groups sorted by first member."""
    by_hash: Dict[str, List[int]] = collections.defaultdict(list)
    for cid, body in cases.items():
        by_hash[hashlib.sha256(body.encode()).hexdigest()].append(cid)
    return sorted((sorted(g) for g in by_hash.values()), key=lambda g: g[0])


def read_labels(path: Path, key: str) -> Dict[int, str]:
    with path.open(encoding="utf-8") as fh:
        return {int(r["case"]): r[key].strip() for r in csv.DictReader(fh)}


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> Dict[str, float]:
    """Cohen's kappa for two raters over the fixed CLASSES alphabet."""
    n = len(a)
    if n == 0:
        return {"n": 0, "po": None, "pe": None, "kappa": None}
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in CLASSES)
    kappa = None if pe == 1.0 else (po - pe) / (1.0 - pe)
    return {"n": n, "po": round(po, 4), "pe": round(pe, 4),
            "kappa": None if kappa is None else round(kappa, 4)}


def audit(cases: Dict[int, str], oracle: Dict[int, str]) -> Dict[str, object]:
    """Presentation-structure audit.  This is the part of G-10 that stands on
    its own: it is a property of the export, independent of any judge batch."""
    groups = group_identical(cases)
    dup = [g for g in groups if len(g) > 1]
    conflicts = [{"group": g, "labels": [oracle[c] for c in g]}
                 for g in dup if len({oracle[c] for c in g}) > 1]
    representatives = [g[0] for g in groups]
    return {
        "n_presented": len(cases),
        "n_distinct": len(groups),
        "duplicate_groups": dup,
        "n_cases_in_duplicate_groups": sum(len(g) for g in dup),
        "label_conflicts_within_group": conflicts,
        "representatives": representatives,
        "label_distribution_presented": dict(
            collections.Counter(oracle[c] for c in sorted(cases))),
        "label_distribution_distinct": dict(
            collections.Counter(oracle[c] for c in representatives)),
        "inflation_note": (
            f"{len(cases)} presented items collapse to {len(groups)} distinct "
            f"presentations; the {len(dup)} duplicate pairs are byte-identical "
            "after the case heading is stripped, so a judge cannot distinguish "
            "their members. Agreement over the presented count double-counts "
            "those judgements and overstates reliability. PRIMARY unit is the "
            "distinct presentation."),
        "operator_label_seen": list(OPERATOR_SAW),
        "operator_disclosure": (
            "the operator viewed the oracle labels for these cases while "
            "building this harness; a kappa excluding them is reported as "
            "kappa_distinct_blind"),
    }


def score(cases: Dict[int, str], oracle: Dict[int, str],
          judge: Dict[int, str], aud: Dict[str, object]) -> Dict[str, object]:
    """Kappa on both unit counts.  `kappa_distinct` is the reportable one."""
    reps: List[int] = list(aud["representatives"])  # type: ignore[arg-type]
    present = sorted(c for c in cases if c in judge)
    missing = sorted(c for c in cases if c not in judge)
    blind = [c for c in reps if c in judge and c not in OPERATOR_SAW]
    reps_j = [c for c in reps if c in judge]
    return {
        "kappa_distinct": {
            **cohen_kappa([oracle[c] for c in reps_j],
                          [judge[c] for c in reps_j]),
            "unit": "distinct presentation (PRIMARY)",
        },
        "kappa_presented_INFLATED": {
            **cohen_kappa([oracle[c] for c in present],
                          [judge[c] for c in present]),
            "unit": "presented case -- double-counts duplicate pairs, "
                    "do not quote as the anchor set's reliability",
        },
        "kappa_distinct_blind": {
            **cohen_kappa([oracle[c] for c in blind],
                          [judge[c] for c in blind]),
            "unit": "distinct presentation, excluding cases whose label the "
                    "operator saw",
            "excluded": list(OPERATOR_SAW),
        },
        "per_class_agreement_distinct": {
            cls: cohen_kappa(
                [oracle[c] for c in reps_j],
                [judge[c] if judge[c] == cls else f"not_{cls}" for c in reps_j])
            ["po"]
            for cls in CLASSES},
        "judged": len(present),
        "unjudged": missing,
        "disagreements_distinct": [
            {"case": c, "oracle": oracle[c], "judge": judge[c]}
            for c in reps_j if oracle[c] != judge[c]],
        "identical_pair_inconsistency": pair_consistency(aud, judge),
        "degeneracy": degeneracy(oracle, judge, reps_j),
    }


def pair_consistency(aud: Dict[str, object],
                     judge: Dict[int, str]) -> Dict[str, object]:
    """Free reliability diagnostic bought by the duplicated presentations: the
    members of a byte-identical group are indistinguishable to the judge, so a
    split verdict inside one is pure judge noise."""
    groups = [g for g in aud["duplicate_groups"]  # type: ignore[union-attr]
              if all(c in judge for c in g)]
    split = [{"group": g, "judgments": [judge[c] for c in g]}
             for g in groups if len({judge[c] for c in g}) > 1]
    return {
        "groups_checked": len(groups),
        "n_split": len(split),
        "split_groups": split,
        "note": ("a split group is judge noise, not a hard error: the two "
                 "presentations are byte-identical. 0 splits means the "
                 "near-chance kappa below is a validity failure of the judge, "
                 "not decoding instability."),
    }


def degeneracy(oracle: Dict[int, str], judge: Dict[int, str],
               reps: Sequence[int]) -> Dict[str, object]:
    """Guard against reading a near-zero kappa as 'noisy but unbiased'.  A judge
    that never emits a class, or that merely reproduces the majority label, has
    a low kappa for a reason that no additional sampling will fix."""
    jc = collections.Counter(judge[c] for c in reps)
    oc = collections.Counter(oracle[c] for c in reps)
    n = len(reps)
    acc = sum(oracle[c] == judge[c] for c in reps) / n if n else None
    major = oc.most_common(1)[0][0] if oc else None
    base = oc[major] / n if n else None
    return {
        "n": n,
        "judge_class_counts": dict(jc),
        "oracle_class_counts": dict(oc),
        "classes_never_emitted": [c for c in CLASSES if jc[c] == 0],
        "judge_accuracy": None if acc is None else round(acc, 4),
        "majority_class_baseline": {
            "class": major,
            "accuracy": None if base is None else round(base, 4)},
        "matches_majority_baseline": (
            None if acc is None or base is None else abs(acc - base) < 1e-9),
        "note": ("if classes_never_emitted is non-empty, or judge_accuracy "
                 "does not exceed majority_class_baseline, the anchor batch "
                 "does not corroborate the oracle labels and must be reported "
                 "as a failed anchoring attempt rather than as low agreement"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=Path, default=CASES)
    ap.add_argument("--labels", type=Path, default=LABELS)
    ap.add_argument("--judge", type=Path, default=None,
                    help="CSV with columns case,judgment (keep/archive/"
                         "neutral); omit for audit-only mode")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()

    cases = parse_cases(args.cases)
    oracle = read_labels(args.labels, "oracle_action")
    aud = audit(cases, oracle)

    payload: Dict[str, object] = {
        "cases_file": str(args.cases),
        "cases_sha256": hashlib.sha256(
            args.cases.read_bytes()).hexdigest(),
        "audit": aud,
        "mode": "audit_only",
    }

    if aud["label_conflicts_within_group"]:
        print("ERROR: identical presentations carry different oracle labels; "
              "the export is inconsistent:")
        for c in aud["label_conflicts_within_group"]:  # type: ignore
            print(f"  {c}")
        return 2

    if args.judge is not None:
        judge = read_labels(args.judge, "judgment")
        bad = {c: v for c, v in judge.items() if v not in CLASSES}
        if bad:
            print(f"ERROR: judgments outside {CLASSES}: {bad}")
            return 2
        payload["judge_file"] = str(args.judge)
        payload["scores"] = score(cases, oracle, judge, aud)
        payload["mode"] = "scored"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    a = aud
    print(f"presented: {a['n_presented']}  distinct: {a['n_distinct']}  "
          f"duplicate pairs: {len(a['duplicate_groups'])}")  # type: ignore
    for g in a["duplicate_groups"]:  # type: ignore
        print(f"  identical: {g}  label={oracle[g[0]]}")
    print(f"label dist (distinct): {a['label_distribution_distinct']}")
    if "scores" in payload:
        s = payload["scores"]
        for k in ("kappa_distinct", "kappa_presented_INFLATED",
                  "kappa_distinct_blind"):
            r = s[k]  # type: ignore[index]
            print(f"{k}: kappa={r['kappa']} po={r['po']} n={r['n']}")
        pc = s["identical_pair_inconsistency"]  # type: ignore[index]
        print(f"identical-pair splits: {pc['n_split']}/"
              f"{pc['groups_checked']} (judge noise)")
        dg = s["degeneracy"]  # type: ignore[index]
        print(f"judge classes: {dg['judge_class_counts']}"
              f"  never emitted: {dg['classes_never_emitted']}")
        print(f"judge acc {dg['judge_accuracy']} vs majority-class baseline "
              f"{dg['majority_class_baseline']['accuracy']} "
              f"({dg['majority_class_baseline']['class']})"
              f"{'  -- DEGENERATE' if dg['matches_majority_baseline'] else ''}")
        if s["unjudged"]:  # type: ignore[index]
            print(f"UNJUDGED: {s['unjudged']}")  # type: ignore[index]
    else:
        print("audit-only mode: no --judge supplied, no kappa computed")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
