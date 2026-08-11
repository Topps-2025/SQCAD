# Reproducibility and status

## Frozen local assets

The external database contains hash-frozen LongMemEval-S, LongMemEval Oracle, LoCoMo and Gate A packet assets. Their provenance and SHA-256 values are recorded in `D:\Engineering\SQCAD\database\manifests\storage_manifest_v1.json`.

## Tests

The extracted deterministic research suite was run before repository publication. The source workspace reported 55 passing tests. After extraction, the test suite is rerun with `pytest` from the repository root; failures caused by path assumptions must be fixed before a release claim.

## Reproduction boundary

Controlled simulator output is useful for module decisions and failure analysis. It is not evidence of public benchmark superiority. A public result requires a fixed reader, model/tool contract, candidate stream, evaluator, chronological split, seed protocol and cost accounting. Any unavailable paper implementation is reported as `not reproduced` or as a named behavioral proxy.

## Current status

The repository is an initial English-first public research layout. The Chinese documents preserve the detailed lab record. Public end-to-end SQCAD performance is intentionally left as an open verification task.
