# AGENTS.md

Instructions for coding agents (Codex, Claude Code, and similar) working in this
repository. Human-facing docs: `README.md`, `docs/docs_en/`.

## Project

SQCAD — lifecycle-aware authorization for persistent agent memory. Research
artifact accompanying an ICLR 2027 submission (`paper/SQCAD_ICLR2027.pdf`). It
makes **no SOTA claim** and is not a deployed system; the evidence boundary in
`README.md` is part of the contribution, so preserve it in any text you write.

## Environment

- Python >= 3.10. Only runtime dependency is `numpy`; `pytest` for tests.
- No GPU, model weights, or API keys are required for anything in `src/sqcad/`.

```bash
pip install -e ".[dev]"
```

## Commands

| Task | Command |
|---|---|
| Full test suite (~457 tests, 15-20 min) | `PYTHONPATH=src python -m pytest tests/ -q` |
| Single file | `PYTHONPATH=src python -m pytest tests/test_public_unified_contract.py -q` |
| Public contract main table | `PYTHONPATH=src python -m sqcad.unified_baseline_runner` |
| Score a LifecycleBench submission | `cd benchmarks/lifecyclebench_v3 && python score.py --actions actions.json` |
| Rebuild LifecycleBench-v3 | `PYTHONPATH=src python tools/build_lifecycle_bench_v3.py --out results/lifecycle_bench_v3` |

`PYTHONPATH=src` is required — the package is not installed into site-packages
by the test config. Run the full suite once before committing; it is CPU-only
and deterministic, so a failure is a real failure.

## Hard constraints

1. **No credentials in the repository.** `.ssh_password`, `.env`, and
   `tools/.autodl_pw` are gitignored. Read secrets from `$SQCAD_SSH_PASSWORD`.
   Never inline a password, token, or host key, not even in a comment or an
   example.
2. **No label leakage.** A LifecycleBench controller reads
   `benchmarks/lifecyclebench_v3/public.jsonl` only. `hidden.jsonl` is for the
   evaluator. Harnesses record `gold_sent_to_model: false`; preserve that.
3. **Determinism.** Fixed seeds, sorted iteration over sets, stable tie-breaks.
   Tests assert exact hashes; incidental ordering changes are regressions.
4. **Do not invent numbers.** Every table value in `paper/tex/` traces to a
   frozen artifact with a recorded SHA-256. To change a number, change its
   source artifact and state which one.
5. **`results/` and `remote_results/` stay gitignored.** They live on an
   external drive (`DATA_STORAGE.md`). A fresh clone will not have them.
6. **`benchmarks/` is the one exception to the data policy.** LifecycleBench-v3
   is published deliberately; the `.gitignore` un-ignore rules for it are
   intentional, so do not "clean them up".

## Layout

```text
src/sqcad/
  causal_memory_store.py       evidence store: lineage, scope/version, archive/restore
  qualification_access.py      qualification -> authorization -> access
  public_unified_contract.py   frozen public contract (FIR denoise, structured prior)
  decision_identification_theory.py   commit/defer/probe comparison
  lifecycle_bench/             generator, evaluator, baselines, frozen constants
benchmarks/lifecyclebench_v3/  released dataset, standalone scorer, example controller
paper/                         released PDF (`SQCAD_ICLR2027.pdf`) and LaTeX source
tests/                         deterministic unit and protocol checks
tools/                         builders, audits, report renderers
docs/docs_en/ docs/docs_cn/    English / Chinese documentation
```

## Conventions

- `from __future__ import annotations`; type hints on public functions.
- Standard library first; add a dependency only if genuinely needed.
- Comments explain *why*, especially where the obvious alternative would break
  a contract (ordering, leakage, tie-breaking). Do not restate the code.
- Write docs in the language of the file you are editing (`docs_en` vs
  `docs_cn`).

## Before you finish

- Run the tests and report the real result. If something fails, say so with the
  output rather than describing the change as complete.
- If you touched a paper number, name the frozen artifact it came from.
- If a task turned out to be blocked, finish the rest and state plainly what
  you left undone and why.
