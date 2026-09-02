# SQCAD — working notes for coding agents

Research artifact for **lifecycle-aware authorization of persistent agent
memory**. Paper: `paper/SQCAD_ICLR2027.pdf` (ICLR 2027 submission draft).

## What this repo is, and is not

It is a research codebase with a strict evidence boundary. It is **not** a
deployed system and claims **no SOTA** on any public benchmark. Read
"Evidence boundary" in `README.md` before writing anything that characterizes
results — the distinction between `proved`, `measured`, `proxy`, and `smoke` is
load-bearing here, and blurring it is the most damaging edit you can make.

## Setup

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1   |  POSIX: source .venv/bin/activate
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest tests/ -q     # ~457 tests, CPU-only, no API keys
```

The full suite takes roughly 15-20 minutes. When iterating, run the file that
covers your change, then the full suite once before committing.

Everything in `src/sqcad/` is CPU-only and deterministic. No GPU, model weights,
or API keys are needed for the repository's own experiments.

## Layout

```text
src/sqcad/                  core library
  causal_memory_store.py    evidence store: lineage, scope/version, archive/restore
  qualification_access.py   qualification -> authorization -> access separation
  public_unified_contract.py  frozen public-benchmark contract (FIR, structured prior)
  lifecycle_bench/          LifecycleBench generator, evaluator, baselines
benchmarks/lifecyclebench_v3/  the released dataset + standalone scorer
paper/                      released PDF and LaTeX source
tests/                      deterministic unit and protocol checks
tools/                      builders, audits, report renderers
docs/docs_en/               English documentation
```

`results/` and `remote_results/` are **gitignored** and hold hash-frozen run
artifacts on an external drive (see `DATA_STORAGE.md`). They are inputs to the
paper tables; do not expect them in a fresh clone, and do not commit them.

## Rules that are not negotiable

**Never commit credentials.** `.ssh_password`, `.env`, and `tools/.autodl_pw`
are gitignored and must stay that way. Scripts read secrets from
`$SQCAD_SSH_PASSWORD`, never from a literal. If you add a remote helper, take
the secret from the environment.

**Never let a controller read hidden labels.** In `benchmarks/lifecyclebench_v3`,
a controller consumes `public.jsonl` only. `hidden.jsonl` is evaluator-side.
Reference harnesses record `gold_sent_to_model: false` for this reason; keep
that property, and keep recording it.

**Determinism is a contract, not a preference.** Fixed seeds, sorted iteration
over sets, stable tie-breaks. Several tests assert exact hashes, so an
incidental change in iteration order is a real regression, not flakiness.

**Do not silently restate frozen numbers.** Table values in `paper/tex/` trace
to specific frozen artifacts with recorded SHA-256 hashes. If you change a
number, change the artifact it came from and say which one.

## Reproducing the paper's evidence

```bash
# LifecycleBench: the released dataset, scored standalone
cd benchmarks/lifecyclebench_v3
python example_controller.py --rule qualify_lineage --out actions.json
python score.py --actions actions.json --by-family

# Public unified contract (CPU)
PYTHONPATH=src python -m sqcad.unified_baseline_runner

# Rebuild LifecycleBench-v3 from source (same signatures)
PYTHONPATH=src python tools/build_lifecycle_bench_v3.py --out results/lifecycle_bench_v3
```

Building the paper needs a LaTeX toolchain:

```bash
cd paper/tex
pdflatex -interaction=nonstopmode main_iclr2027_draft.tex
bibtex   main_iclr2027_draft
pdflatex -interaction=nonstopmode main_iclr2027_draft.tex
pdflatex -interaction=nonstopmode main_iclr2027_draft.tex
```

## Style

Match the surrounding code: type hints, `from __future__ import annotations`,
standard library first. Comments explain *why* a choice was made — particularly
where a naive alternative would silently break a contract (ordering, leakage,
tie-breaks). Skip comments that restate the code.

Docs are bilingual: `docs/docs_en/` English, `docs/docs_cn/` Chinese. Update
the one matching the language you are writing in.
