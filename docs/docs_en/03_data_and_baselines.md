# Data and baselines

## Public data (L2)

| Dataset | Role | Status |
|---|---|---|
| LongMemEval-S | long-term facts, updates, retrieval process | frozen; retrieval baselines run; QA via OpenAI endpoint on AutoDL |
| LoCoMo | long-horizon multi-hop and temporal QA | frozen; official deterministic token-F1 (CPU-only) run |

Unified contract: same chronological stream, workspace budget, reader, evaluator, time split, seeds and cost accounting for every compared method. Results in [02 Experiments](02_experiments.md); per-baseline open-source and no-GPU audit in report `docs/自用/03-实验证据链/15-基线开源状态与无GPU复现审计-20260813.md` (internal).

Reachability facts (web-verified 2026-08-13, unchanged): LongMemEval ICLR 2025 (MIT); LoCoMo ACL 2024 (**CC BY-NC 4.0**); GoodAI-LTM NeurIPS 2024 D&B (MIT, litellm keys are the blocker); MemoryAgentBench ICLR 2026 (MIT); Oblivion **proprietary license** (NEC Laboratories Europe, not redistributed); SimpleMem MIT — the released-version commit `16912523` is frozen separately; FadeMem's public repo is an unrelated video-diffusion project (identity mismatch — no official code found for the Agent Memory paper); DeMem has no official implementation (named behavioral proxy only).

## Self-built data (L3): SQCAD-LifecycleBench

1,380 keep/archive same-source counterfactual episodes: 6 mechanism families × 200 (hitchhiker, rare_bridge, version_update, harmful_stale, self_obscuring, scope_mismatch) + 3 control families × 50 + 15 observationally-equivalent pairs. Each episode contains both keep and archive rollouts under the same future stream; the true long-term outcome lives only in the hidden layer (public trace has no oracle labels). Split train/dev/test = 818/354/208; remote AutoDL rebuild is hash-identical to local. Contract frozen via `frozen.py` (GAMMA=0.9, TAU_TOL=0.5, …) and registered in the freeze manifest.

Build plan: `docs/自用/00-论文主体/22-SQCAD-LifecycleBench数据集构建方案-20260817.md`; full audit report: `docs/自用/03-实验证据链/20-SQCAD-LifecycleBench公允性审计与基线矩阵报告-20260817.md` (internal).

## Baseline tiers

**Simple controls:** no-memory, keep-all, recency/FIFO/LRU, fixed exponential decay, frequency decay, storage-size proxies, random50, BM25.

**Governance systems:** SAGE, SimpleMem, FadeMem, Oblivion, Memory Worth, DeMem — only when paper method, code, data, model, evaluator and protocol can be aligned; otherwise reported `not reproduced` or a clearly named behavioral proxy (agent vs official reproduction reported in separate columns).

**Internal controls / ablations:** no-censoring, certificate-off, probe/restore-off, lineage-off, association-only access, bounded fallback, no mismatch penalty, scope-literal, event-rule.

## Fairness contract

Every main-table comparison uses the same candidate stream, reader, prompt, model/tool version, top-k, workspace tokens, storage budget, evaluator, time split, seeds and cost contract. Paper-reported numbers are not local reproductions. Oracle policies are diagnostic upper bounds, not baselines.

Fairness defenses R1–R8 are preregistered (metadata shortcuts, parameter sensitivity, unseen mechanisms, verification regions, independent implementation, human anchoring, release package, iteration log) — verdicts in [02 Experiments](02_experiments.md) and report 20.
