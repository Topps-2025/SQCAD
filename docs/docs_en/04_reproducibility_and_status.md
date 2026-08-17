# Reproducibility and status

## Frozen assets

The external database contains hash-frozen LongMemEval-S, LongMemEval Oracle, LoCoMo and Gate A assets; provenance and SHA-256 recorded in `D:\Engineering\SQCAD\database\manifests\storage_manifest_v1.json` and chained into `results/freeze_manifest.json` (config piece). LifecycleBench assets (`results/lifecycle_bench/`) are seed-determined; their three serialization layers hash-match the AutoDL remote rebuild.

## Four-piece freeze

`src/sqcad/freeze_four_piece.py` (Gate 5) generates a deterministic SHA-256 manifest over four pieces — code (`src/sqcad/*.py`, `tests/*.py`), config (frozen contract registry + byte hashes of frozen real-data files), results (`results/*.json`) and reports (`docs/自用/03-实验证据链/*.md`) — with a chained aggregate hash. Any change to any piece breaks the chain. Regenerate with:

```bash
PYTHONPATH=src python -m sqcad.freeze_four_piece
```

## Tests

The deterministic research suite (all CPU-only, no API keys, no network): 47 LifecycleBench contract tests + 23 fairness tests + the full core suite; R5 independent-implementation check 1380/1380 bit-identical (16.9 s).

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

## Remote GPU re-check (AutoDL)

Public-data pipeline and LifecycleBench rebuild/audit were executed on an AutoDL RTX 4080 SUPER (data-disk only, `sqcad-py310` env): dataset hashes identical to local (public/hidden/policy-log all match; manifest differs only in the non-deterministic `generated_at`), audit suite semantics identical. The cloud session is closed.

## Reproduction boundary

Controlled-simulator output is useful for module decisions and failure analysis; it is not evidence of public benchmark superiority. A public result requires a fixed reader, model/tool contract, candidate stream, evaluator, chronological split, seed protocol and cost accounting. Unavailable paper implementations are reported `not reproduced` or as named behavioral proxies.

## Current status (2026-08-17)

| Work package | Status | Result / next step |
|---|---|---|
| Theory core (T1/T2/P4) | done | strict proofs + numeric corroboration (reports 13/14, proofs 15/16) |
| Public-data reproduction + Guard | done | Guard-1 LoCoMo F1 0.0344 → 0.0455; GPU re-checked (report 19) |
| LifecycleBench build | done | 1,380 episodes, hash-consistent, 47 contract tests (report 20) |
| Fairness audit R1–R5, R7 | done | four channels green; R2 relocated to valid domain |
| Framework changes | done | 3 verdicts: lineage→archive, hitchhiker→archive, scope lookahead → Phase B |
| R6 human anchoring | pending external | 28 blinded cases exported, $\kappa \ge 0.6$ criterion |
| Named baseline extensions | pending | FadeMem/Oblivion/Memory Worth/DeMem/SimpleMem under unified contract (agent vs official columns) |
| Phase B end-to-end | pending | freeze reader/LLM/tools, switch only persistent state; first validation of scope lookahead |
| dense/RRF | blocked | official weights unavailable (documented in report 19) |
