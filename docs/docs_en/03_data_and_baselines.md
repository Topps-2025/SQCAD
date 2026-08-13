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

## Reachability snapshot

- LongMemEval: ICLR 2025; MIT repository; local S/Oracle data and upstream commit are frozen. The M split is still missing locally.
- LoCoMo repository: public, but GitHub metadata reports `NOASSERTION`; verify `LICENSE.txt` and data terms before redistribution.
- GoodAI-LTM: public runner and configurations; model/judge endpoint and third-party data terms require verification.
- Oblivion: local source snapshot; Python 3.12, Poetry and API endpoints are required for full benchmarks.
- SimpleMem: the current main branch contains post-paper Omni/EvolveMem changes. Commit `16912523f6f0de10c01f7701cdbb79d8fa4f5280` (`released version`, 2026-01-02) is frozen separately as the original paper-release candidate. Its LoCoMo protocol requires GPT-4.1-mini or Qwen and Qwen3-Embedding-0.6B.
- FadeMem: the previously found `aniki-ly/FadeMem` repository is arXiv:2606.10671 for autoregressive video diffusion, not the cited Agent Memory forgetting paper arXiv:2601.18642. It is an identity mismatch and is excluded from the baseline table until the official Agent Memory implementation is verified.
- DeMem: the currently found repository is not yet verified as the official paper implementation.
