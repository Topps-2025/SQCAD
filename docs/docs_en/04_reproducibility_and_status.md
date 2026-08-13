# Reproducibility and status

## Frozen local assets

The external database contains hash-frozen LongMemEval-S, LongMemEval Oracle, LoCoMo and Gate A packet assets. Their provenance and SHA-256 values are recorded in `D:\Engineering\SQCAD\database\manifests\storage_manifest_v1.json` and chained into `results/freeze_manifest.json` (config piece).

## Four-piece freeze

`src/sqcad/freeze_four_piece.py` (Gate 5) generates a deterministic SHA-256 manifest over four pieces — code (`src/sqcad/*.py`, `tests/*.py`), config (frozen contract registry + byte hashes of the two frozen real-data files), results (`results/*.json`) and reports (`docs/实验证据链/*.md`) — with a chained aggregate hash. Any change to any piece breaks the chain. Regenerate with:

```bash
PYTHONPATH=src python -m sqcad.freeze_four_piece
```

## Tests

The full deterministic research suite (255 tests, CPU-only, no API keys, no network) runs with:

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

## Reproduction boundary

Controlled simulator output is useful for module decisions and failure analysis. It is not evidence of public benchmark superiority. A public result requires a fixed reader, model/tool contract, candidate stream, evaluator, chronological split, seed protocol and cost accounting. Any unavailable paper implementation is reported as `not reproduced` or as a named behavioral proxy. Per-baseline open-source and no-GPU reproduction analysis: `docs/BASELINE_AUDIT.md`.

## Current status (2026-08-13)

- Core store, workflow runner, unified-contract main table (18 policies) and cost contract are implemented and tested.
- Theory core is closed: T1 self-obscuring theorem, T2 reduction separation and P4 minimax probing bounds carry strict proofs (`docs/研究逻辑与理论证明/15-…`, `16-…`) with controlled numeric corroboration (`docs/实验证据链/13-…`, `14-…`).
- Public-data stage is planned but not executed end-to-end (`docs/研究逻辑与理论证明/17-…`): the retrieval protocol is locally runnable on CPU; the end-to-end QA protocol is blocked on LLM endpoints (no GPU / no API key in the working environment — recorded as an environment fact).
- The repository is an English-first public research layout. The Chinese documents preserve the detailed lab record. Public end-to-end SQCAD performance is intentionally left as an open verification task.
