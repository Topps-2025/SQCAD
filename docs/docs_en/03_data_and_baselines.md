# Data and baselines

## Data tiers

| Tier | Dataset | Role | Current status |
|---|---|---|---|
| D0 | controlled mechanism world | potential-outcome and scope ground truth | local simulator |
| D1 | LongMemEval-S | long-term facts, updates and retrieval process | local, hash frozen, retrieval baselines run |
| D2 | LoCoMo | long-horizon multi-hop and temporal QA | local JSON frozen, reader not unified |
| D3 | GoodAI-LTM | dynamic retain/revise/update/recovery | repository accessible, endpoint and adapter pending |
| D4 | MemoryAgentBench | incremental interaction coverage | MIT repository accessible, revision pending |
| D5 | Gate A | factor/relation/provenance/scope annotation audit | packet template ready, double annotation pending |
| D6 | randomized micro-intervention | qualification calibration and overlap | design stage |

## Baseline tiers

**Simple controls:** no-memory, keep-all, recency/FIFO/LRU, fixed exponential decay, frequency decay, BM25, dense and BM25+dense RRF.

**Governance systems:** SAGE, SimpleMem, FadeMem, Oblivion, Memory Worth and DeMem, only when the paper method, code, data, model, evaluator and protocol can be aligned. Otherwise report `not reproduced` or a clearly named behavioral proxy.

**Internal controls:** v3 qualification gate, global qualification, scoped qualification without competition, competition without qualification, no positive protection, no negative attenuation, default-cold unresolved, bounded fallback, no mismatch penalty, item-level causal stable and risk-gated fallback.

## Fairness contract

Every main-table comparison uses the same candidate stream, reader, prompt, model/tool version, top-k, workspace tokens, storage budget, evaluator, time split, seeds and cost contract. Paper-reported numbers are not local reproductions. Oracle policies are diagnostic upper bounds, not baselines.

## Reachability snapshot (web-verified 2026-08-13; full detail in [BASELINE_AUDIT.md](../BASELINE_AUDIT.md))

- LongMemEval: ICLR 2025 (arXiv 2410.10813); MIT repo and HF data; local S/Oracle data and upstream commit are frozen. The M split is still missing locally. BM25 retrieval is pure CPU (locally run); the QA judge needs an OpenAI API key (or a 70B vLLM GPU); dense retrievers hard-code CUDA.
- LoCoMo: ACL 2024 (arXiv 2402.17753); repo public, `LICENSE.txt` resolves to **CC BY-NC 4.0** (GitHub metadata says `NOASSERTION`). `data/locomo10.json` is in-repo (2.8 MB). The official QA metric is a deterministic token-F1 — no LLM judge, CPU-only; only answer generation needs API/GPU.
- GoodAI-LTM: NeurIPS 2024 D&B (arXiv 2409.20222); MIT LICENSE file (metadata stale); data bundled in-repo; every LLM call goes through litellm — API keys are the blocker, GPU is not needed.
- MemoryAgentBench: ICLR 2026 (arXiv 2507.05257); MIT repo and HF dataset; string metrics are CPU; the GPT-4o judge covers two subsets.
- Oblivion: local source snapshot at commit `b2512f9`; Python 3.12, Poetry and API endpoints are required for full benchmarks. **License is proprietary (NEC Laboratories Europe)** — not open source; the snapshot stays in the external database and is not redistributed.
- SimpleMem: MIT repo (aiming-lab/SimpleMem). The current main branch contains post-paper Omni/EvolveMem changes. Commit `16912523` (`released version`, 2026-01-02) is frozen separately as the original paper-release candidate. Its LoCoMo protocol requires GPT-4.1-mini (API key) and Qwen3-Embedding-0.6B (CPU-runnable, slow).
- FadeMem: the `aniki-ly/FadeMem` repository is arXiv:2606.10671 (autoregressive video diffusion), not the cited Agent Memory forgetting paper arXiv:2601.18642. Identity mismatch — excluded until an official Agent Memory implementation appears. No official code found for 2601.18642.
- DeMem: no official implementation found (arXiv 2605.10870); the algorithm is disclosed and a behavioral proxy is used in the unified contract.
