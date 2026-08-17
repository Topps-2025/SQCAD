"""SQCAD-LifecycleBench fairness audit CLI (23- 6, R1-R7).

Subcommands:
  shortcut       R1: metadata-shortcut audit on the serialized dataset
                 (results/lifecycle_bench/public.jsonl + hidden.jsonl).
  sensitivity    R2: label flips under perturbed frozen contracts.
  unseen         R3: unseen-mechanism holdout (structural knobs).
  independent    R5: clean-room reference policy consistency check.
  matrix         Baseline matrix (decision policies + ablations + paired
                 bootstrap vs. sqcad_cert).
  human_anchor   R6: export human-anchor cases + Cohen's kappa scorer.
  release        R7: build the public release package (trace-only view +
                 README + scoring harness).

Usage examples:
  python tools/lifecycle_fairness.py shortcut --results results/lifecycle_bench \
      --out remote_results/lifecycle_audit/r1_shortcut.json
  python tools/lifecycle_fairness.py sensitivity --episodes results/lifecycle_bench/episodes.pkl \
      --out remote_results/lifecycle_audit/r2_sensitivity.json
  python tools/lifecycle_fairness.py matrix --episodes results/lifecycle_bench/episodes.pkl \
      --out remote_results/lifecycle_audit/matrix.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def cmd_shortcut(args: argparse.Namespace) -> None:
    from sqcad.lifecycle_bench.audit import metadata_shortcut_audit
    res = metadata_shortcut_audit(Path(args.results))
    _write(args.out, res)
    print(json.dumps(_shortcut_summary(res), ensure_ascii=False, indent=2))


def _shortcut_summary(res: dict) -> dict:
    return {
        "n": res["n"],
        "oracle_distribution": res["oracle_distribution"],
        "metadata_family_variant": res["metadata_family_variant"],
        "metadata_family": res["metadata_family"],
        "text_only_dev": res["text_only"]["dev"]["acc"],
        "text_only_test": res["text_only"]["test"]["acc"],
        "pair_ceiling": res["pair_ceiling"],
    }


def cmd_sensitivity(args: argparse.Namespace) -> None:
    from sqcad.lifecycle_bench.audit import cached_episodes, sensitivity_audit
    eps = cached_episodes(Path(args.episodes) if args.episodes else None)
    res = sensitivity_audit(eps)
    _write(args.out, res)
    runs = [(r["constant"], r["value"], round(r["flip_rate"], 4))
            for r in res["runs"]]
    print(f"verdict: {res['verdict']}")
    for c, v, f in runs:
        print(f"  {c}={v}: flip {f}")


def cmd_unseen(args: argparse.Namespace) -> None:
    from sqcad.lifecycle_bench.unseen import run_audit
    res = run_audit()
    _write(args.out, res)
    bad = []
    for cell, knobs in res["cells"].items():
        for knob, stats in knobs.items():
            if stats["oracle_agreement"] < 0.9 or stats["reversals"]:
                bad.append((cell, knob, stats["oracle_agreement"],
                            len(stats["reversals"])))
    print(f"cells: {len(res['cells'])} x {res['knobs']}")
    if bad:
        print("cells below 0.9 agreement or with reversals:")
        for b in bad:
            print("  ", b)
    else:
        print("all cells >= 0.9 oracle agreement, no reversals")


def cmd_independent(args: argparse.Namespace) -> None:
    from sqcad.lifecycle_bench.audit import cached_episodes
    from sqcad.lifecycle_bench.independent_ref import verify
    eps = cached_episodes(Path(args.episodes) if args.episodes else None)
    res = verify(eps)
    _write(args.out, res)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def cmd_matrix(args: argparse.Namespace) -> None:
    from sqcad.lifecycle_bench.audit import cached_episodes, outcome_of
    from sqcad.lifecycle_bench import baselines as B

    eps = cached_episodes(Path(args.episodes) if args.episodes else None)
    hidden = {}
    for ep in eps:
        out, _ = outcome_of(ep)
        hidden[ep.world.episode_id] = out

    mat = B.run_decision_matrix(eps, hidden)
    abl = B.run_ablation_matrix(eps, hidden)
    buckets = B.per_bucket_table(mat["rows"])

    # paired bootstrap: sqcad_cert (reference decision) vs every baseline
    ref_rows = mat["rows"]["sqcad_cert"]
    boot = {}
    for name in B.DECISION_POLICIES:
        if name == "sqcad_cert":
            continue
        base = mat["rows"][name]
        boot[name] = B.bootstrap_diff(
            [r["value"] for r in ref_rows],
            [r["value"] for r in base], n_boot=args.n_boot, seed=args.boot_seed)

    res = {"summary": mat["summary"], "ablation": abl,
           "per_bucket_value": buckets, "bootstrap_vs_sqcad_cert": boot}
    _write(args.out, res)

    print("== decision policies (mean value / regret / oracle agreement /"
          " false-commit) ==")
    for name, s in sorted(mat["summary"].items(),
                          key=lambda kv: -kv[1]["mean_value"]):
        print(f"  {name:22s} {s['mean_value']:8.3f} {s['mean_regret']:8.3f}"
              f" {s['oracle_agreement'] if s['oracle_agreement'] is not None else float('nan'):8.3f}"
              f" {s['false_commit_rate']:8.3f}")
    print("== ablations (mean value / regret) ==")
    for name, s in sorted(abl.items(), key=lambda kv: -kv[1]["mean_value"]):
        print(f"  {name:20s} {s['mean_value']:8.3f} {s['mean_regret']:8.3f}")
    print("== bootstrap diff (sqcad_cert - baseline), 95% CI ==")
    for name, b in boot.items():
        sig = "sig" if b["significant"] else "    "
        print(f"  {sig} {name:20s} {b['diff_mean']:+8.3f}"
              f" [{b['ci_lo']:+8.3f}, {b['ci_hi']:+8.3f}]")


def cmd_human_anchor(args: argparse.Namespace) -> None:
    from sqcad.lifecycle_bench.audit import cached_episodes
    from sqcad.lifecycle_bench import baselines as B
    import random

    eps = cached_episodes(Path(args.episodes) if args.episodes else None)
    buckets: Dict[str, list] = {}
    for ep in eps:
        buckets.setdefault(B.BUCKET_KEY(ep), []).append(ep)
    rng = random.Random(args.seed)
    n_per = max(1, args.n // len(buckets))
    chosen = []
    for b, lst in sorted(buckets.items()):
        chosen += rng.sample(lst, min(n_per, len(lst)))
    chosen = chosen[: args.n]

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cases, labels = [], []
    for i, ep in enumerate(chosen, 1):
        cases.append(_render_case(i, ep))
        labels.append({"case": i, "episode_id": ep.world.episode_id,
                       "oracle": None})  # filled by the scorer after judging
    (outdir / "anchor_cases.md").write_text(
        "\n\n".join(cases), encoding="utf-8")
    # oracle labels for the maintainer (NOT inside anchor_cases.md)
    hid = []
    for i, ep in enumerate(chosen, 1):
        hid.append({"case": i, "episode_id": ep.world.episode_id,
                    "oracle_action": _oracle_of(ep)})
    (outdir / "anchor_labels_private.csv").write_text(
        "case,episode_id,oracle_action\n" + "\n".join(
            f"{h['case']},{h['episode_id']},{h['oracle_action']}" for h in hid),
        encoding="utf-8")
    print(f"exported {len(chosen)} anchor cases to {outdir / 'anchor_cases.md'}")
    print("scoring: python tools/lifecycle_fairness.py score_anchor "
          "--labels <judge_labels.csv> --out <json>")


def _render_case(i: int, ep) -> str:
    lines = [f"## Case {i}", ""]
    for j, s in enumerate(ep.sessions, 1):
        lines.append(f"**Session {j}**")
        for m in s.messages:
            lines.append(f"- {m.speaker}: {m.text}")
        lines.append("")
    lines.append(f"**Decision task**: {ep.decision_task.query} "
                 f"(scope {ep.world.decision_scope})")
    dm = ep.memory(ep.world.decision_fid)
    lines.append(f"**Decision memory**: {dm.text} "
                 f"(size {dm.spec.storage_tokens} tokens)")
    lines.append("")
    lines.append("**Future items**:")
    for it in ep.future_items:
        if it.spec.kind == "task":
            lines.append(f"- slot {it.spec.slot}: task '{it.task.query}' "
                         f"(scope {it.task.spec.scope})")
        else:
            lines.append(f"- slot {it.spec.slot}: event '{it.text}'")
    lines.append("")
    lines.append(f"**Your judgment**: keep / archive / neutral")
    lines.append("")
    return "\n".join(lines)


def _oracle_of(ep) -> str:
    from sqcad.lifecycle_bench.audit import outcome_of
    out, _ = outcome_of(ep)
    return out.oracle_action


def cmd_score_anchor(args: argparse.Namespace) -> None:
    import csv
    private = {}
    with open(args.private, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            private[int(row["case"])] = row["oracle_action"]
    judge = {}
    with open(args.labels, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            judge[int(row["case"])] = row["judgment"].strip().lower()
    assert set(judge) <= set(private), "judge cases not in private set"
    a = [private[c] for c in sorted(judge)]
    b = [judge[c] for c in sorted(judge)]
    res = {"n": len(a), "agreement": _agreement(a, b),
           "kappa": _cohens_kappa(a, b)}
    _write(args.out, res)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def _agreement(a, b):
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def _cohens_kappa(a, b) -> float:
    n = len(a)
    po = _agreement(a, b)
    classes = set(a) | set(b)
    pa = {c: a.count(c) / n for c in classes}
    pb = {c: b.count(c) / n for c in classes}
    pe = sum(pa[c] * pb[c] for c in classes)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def cmd_release(args: argparse.Namespace) -> None:
    """R7: build the public release package: metadata-free public layer +
    README + scoring harness.  Oracle labels are NOT included."""
    import hashlib
    results = Path(args.results)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    public = [json.loads(l) for l in
              (results / "public.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = []
    for p in public:
        rows.append({
            "id": "sqcad-lb-" + hashlib.sha256(
                p["episode_id"].encode()).hexdigest()[:10],
            "split": p["split"],
            "sessions": p["sessions"],
            "decision_task": p["decision_task"],
            "decision_memory": p["decision_memory"],
            "future": p["future"],
            "memories": p["memories"],
        })
    (outdir / "public_trace_only.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True)
                  for r in rows), encoding="utf-8")
    readme = f"""# SQCAD-LifecycleBench public release (metadata-free view)

{len(rows)} episodes, three-layer structure per doc 22-.

This view strips family / variant / regime / episode_id from the public
layer (R1 metadata-shortcut defense): policies may use sessions, the
decision task, the decision memory and the future schedule, but nothing
that encodes the designed oracle sign directly.

Scoring: implement a policy that outputs one line per episode id
`id,action` (action in keep|archive), then run:

    python tools/score_lifecycle_predictions.py --predictions preds.csv \\
        --hidden <maintainer-hidden> --out score.json

The maintainer-side hidden labels are the official counterfactual values
(doc 22- 5.4).  Pre-registration and the audit reports: docs/23-*.
"""
    (outdir / "README.md").write_text(readme, encoding="utf-8")
    print(f"release package written to {outdir}: "
          f"{len(rows)} trace-only episodes + README")


def _write(out: str, res: dict) -> None:
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1),
                         encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("shortcut", help="R1 metadata-shortcut audit")
    p.add_argument("--results", default="results/lifecycle_bench")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_shortcut)

    p = sub.add_parser("sensitivity", help="R2 label-sensitivity audit")
    p.add_argument("--episodes", default=None, help="pickle cache (optional)")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_sensitivity)

    p = sub.add_parser("unseen", help="R3 unseen-mechanism holdout")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_unseen)

    p = sub.add_parser("independent", help="R5 clean-room consistency")
    p.add_argument("--episodes", default=None, help="pickle cache (optional)")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_independent)

    p = sub.add_parser("matrix", help="baseline matrix + bootstrap")
    p.add_argument("--episodes", default=None, help="pickle cache (optional)")
    p.add_argument("--out", required=True)
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--boot-seed", type=int, default=20260817)
    p.set_defaults(fn=cmd_matrix)

    p = sub.add_parser("human_anchor", help="R6 anchor-case export")
    p.add_argument("--episodes", default=None)
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed", type=int, default=20260820)
    p.add_argument("--outdir", required=True)
    p.set_defaults(fn=cmd_human_anchor)

    p = sub.add_parser("score_anchor", help="R6 Cohen's kappa over judge labels")
    p.add_argument("--labels", required=True, help="judge CSV: case,judgment")
    p.add_argument("--private", required=True,
                   help="private CSV: case,episode_id,oracle_action")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_score_anchor)

    p = sub.add_parser("release", help="R7 public release package")
    p.add_argument("--results", default="results/lifecycle_bench")
    p.add_argument("--outdir", required=True)
    p.set_defaults(fn=cmd_release)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
