# Paper

**When to Keep and When to Archive: Lifecycle-Aware Authorization for
Persistent Agent Memory** — ICLR 2027 submission draft.

- Released PDF: [`SQCAD_ICLR2027.pdf`](SQCAD_ICLR2027.pdf) (11 pages: 8 main + 3 appendix)
- Source: [`tex/main_iclr2027_draft.tex`](tex/main_iclr2027_draft.tex)
- Bibliography: `tex/references.bib` · Figures: `tex/figures/`

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
| LoCoMo / LongMemEval-S | `results/submission_experiment_matrix_qwen8b_terra_20260902.json` |
| Reader-matrix validation | `results/submission_artifact_validator_qwen8b_terra_20260902.json` |
| LifecycleBench deterministic | `results/sqcad_method_lifecycle_deterministic_20260902.json` |
| LifecycleBench named baselines | `results/0826_controller_derived_lifecycle_metrics.json` |
| LifecycleBench SQCAD views | `results/sqcad_method_lifecycle_{qwen3_8b,gpt56terra}_metrics_20260902*.json` |

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
