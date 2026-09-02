# Paper

**When to Keep and When to Archive: Lifecycle-Aware Authorization for
Persistent Agent Memory** — ICLR 2027 submission draft.

- Released PDF: [`SQCAD_ICLR2027.pdf`](SQCAD_ICLR2027.pdf) (13 pages: 9 main body +
  statements/references + 3 appendix; ICLR counts only the 9-page body)
- Source: [`tex/main_iclr2027_draft.tex`](tex/main_iclr2027_draft.tex)
- Bibliography: `tex/references.bib` · Figures: `tex/figures/`

Earlier drafts (`SQCAD_ICLR2027_v1.pdf`, `SQCAD_ICLR2027_v2.pdf` and their
`tex/main_iclr2027_draft_v[12].tex` sources) are kept locally for diffing and are
gitignored, since only the current draft is the released artifact. The current draft
reorganizes the same evidence around the impossibility result: the score-fiber audit
and the abstention policy are promoted from appendix material to lead results, and
unreproduced named baselines move to the audit appendix. No number changed — the
frozen artifacts below are the same ones v2 drew on.

The author block is anonymous; the paper is under double-blind review.

## Build

Requires a LaTeX toolchain with `pdflatex` and `bibtex`. The ICLR 2027 style
files (`iclr2027_conference.sty`, `.bst`) and `natbib`/`times`/`fancyhdr` are
vendored here, so no additional style download is needed.

```bash
cd tex
pdflatex -interaction=nonstopmode main_iclr2027_draft.tex
bibtex   main_iclr2027_draft
pdflatex -interaction=nonstopmode main_iclr2027_draft.tex
pdflatex -interaction=nonstopmode main_iclr2027_draft.tex
```

Three `pdflatex` passes are needed: one to emit `.aux`, `bibtex` to resolve the
bibliography, then two more to settle cross-references and table placement. The
released PDF builds clean — no undefined references or citations.

## What the numbers trace to

Every table value comes from a frozen run artifact with a recorded SHA-256, not
from a re-derivation at write time. The artifacts live under `results/` and
`remote_results/`, which are gitignored and stored externally (see
`../DATA_STORAGE.md`). The main ones:

| Table | Source artifact |
|---|---|
| 1 — score-fiber audit | `results/baseline_internal_lifecycle_gap_audit_v3_20260826.json` |
| 2, 3 — LoCoMo / LongMemEval-S | `results/submission_experiment_matrix_qwen8b_terra_20260902.json` |
| 4 — deterministic lifecycle | `results/lifecycle_bench_v3/summary.json` (`decision_summary`, `storage_accounting`) |
| 5 — per-family regret | `results/lifecycle_bench_v3/policy_rows.jsonl` (225 rows, family-keyed) |
| 6 — LLM controllers | `results/sqcad_method_lifecycle_{qwen3_8b,gpt56terra}_metrics_20260902*.json` |
| Named-baseline audit (App. F) | `results/0826_controller_derived_lifecycle_metrics.json` |
| Reader-matrix validation | `results/submission_artifact_validator_qwen8b_terra_20260902.json` |

The score-fiber audit's contract is exact equality of published scores after
rounding to 8 digits; its widest witness (shared by four surfaces) is world
`v3-version_update-update_before-ethanu276527-2026282605`, with contrasts
`-134.17` and `+43.4451` and a randomized-minimax floor of `32.81831931519336`.

The LifecycleBench-v3 dataset itself is published in
[`../benchmarks/lifecyclebench_v3/`](../benchmarks/lifecyclebench_v3/), and its
bundled scorer reproduces the deterministic SQCAD row of the paper's lifecycle
table exactly (value 1.083, regret 0.944, recoverability 0.769, scope/version
0.700).

## Evidence conventions used in the text

- **proved** — holds only under the assumptions written in the theorem or appendix.
- **measured** — produced directly by a frozen, named contract.
- **proxy / smoke / partial** — never enters a superiority table as a complete baseline.

Public-benchmark rows are a quality–authorization-cost trade-off, not a SOTA
claim. Named baselines carry an explicit reproduction tier (native, MF, R-C,
literature-only) so that rows measured under different protocols are not read
as directly comparable.
